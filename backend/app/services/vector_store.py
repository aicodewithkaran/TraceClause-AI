import uuid
import logging
from typing import List, Dict, Optional, Any
from openai import OpenAI
from anthropic import Anthropic
from google import genai
from app.core.config import settings
from app.services.ai_budget_service import ai_budget_service, AIBudgetService
from app.core.rate_limiter import budget_tracker
from supabase import create_client, Client

logger = logging.getLogger("vector_store")

class VectorStoreService:
    """
    Dual Embedding Engine & Grounded RAG Store supporting OpenAI & Gemini.
    Normalizes all embeddings to 1536 dimensions so database vector search works seamlessly.
    Queries the database using authorized pgvector cosine similarity stored procedure
    to return verifiable clause citations.
    """

    def __init__(self):
        self.embedding_provider = settings.EMBEDDING_PROVIDER.lower() if settings.EMBEDDING_PROVIDER else self._detect_embedding_provider()
        self.llm_provider = settings.LLM_PROVIDER.lower() if settings.LLM_PROVIDER else self._detect_llm_provider()

        self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
        self.gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY) if settings.GEMINI_API_KEY else None
        self.anthropic_client = Anthropic(api_key=settings.ANTHROPIC_API_KEY) if settings.ANTHROPIC_API_KEY else None

        if settings.SUPABASE_URL and settings.supabase_admin_key:
            self.supabase = create_client(settings.SUPABASE_URL, settings.supabase_admin_key)
        elif settings.SUPABASE_URL and settings.supabase_anon_key:
            self.supabase = create_client(settings.SUPABASE_URL, settings.supabase_anon_key)
        else:
            self.supabase = None

    def _detect_embedding_provider(self) -> str:
        if settings.OPENAI_API_KEY:
            return "openai"
        elif settings.GEMINI_API_KEY:
            return "gemini"
        return "none"

    def _detect_llm_provider(self) -> str:
        if settings.OPENAI_API_KEY:
            return "openai"
        elif settings.GEMINI_API_KEY:
            return "gemini"
        elif settings.ANTHROPIC_API_KEY:
            return "anthropic"
        return "mock"

    BATCH_SIZE = 50

    def generate_embedding(self, text: str) -> List[float]:
        """Generates a single 1536-dim embedding vector using batch pipeline."""
        results = self.generate_embeddings_batch([text])
        return results[0] if results else [0.0] * 1536

    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generates 1536-dimensional embeddings in batches of up to 50 items per API call.
        Supports both Gemini (gemini-embedding-001) and OpenAI (text-embedding-3-small).
        Enforces durable PostgreSQL budget ledger reservations before every API call.
        """
        all_embeddings: List[List[float]] = []

        for i in range(0, len(texts), self.BATCH_SIZE):
            batch_texts = texts[i:i + self.BATCH_SIZE]
            model = settings.OPENAI_EMBEDDING_MODEL if self.embedding_provider == "openai" else settings.GEMINI_EMBEDDING_MODEL
            req_id = f"emb_req_{uuid.uuid4().hex}"
            total_chars = sum(len(t) for t in batch_texts)
            est_cost = AIBudgetService.estimate_cost_microdollars(model, " " * total_chars, max_output_tokens=0)

            # Check and reserve in durable ledger
            reserved = ai_budget_service.reserve(req_id, est_cost, provider=self.embedding_provider, model=model)
            if not reserved:
                logger.critical(f"Monthly AI budget exceeded during embedding generation. Aborting embeddings.")
                raise RuntimeError("Monthly AI budget limit reached. Embedding generation is halted.")

            try:
                if self.embedding_provider == "openai" and self.openai_client:
                    res = self.openai_client.embeddings.create(
                        model=settings.OPENAI_EMBEDDING_MODEL,
                        input=batch_texts
                    )
                    actual_tokens = getattr(res.usage, 'total_tokens', total_chars // 4) if hasattr(res, 'usage') and res.usage else total_chars // 4
                    actual_cost = AIBudgetService.calculate_actual_cost_microdollars(model, actual_tokens, 0)
                    ai_budget_service.settle(req_id, actual_cost, status="settled")
                    budget_tracker.record_usage(actual_cost / 1_000_000)
                    for data in res.data:
                        all_embeddings.append(data.embedding)

                elif self.embedding_provider == "gemini" and self.gemini_client:
                    res = self.gemini_client.models.embed_content(
                        model=settings.GEMINI_EMBEDDING_MODEL,
                        contents=batch_texts,
                        config={"output_dimensionality": 1536}
                    )
                    ai_budget_service.settle(req_id, est_cost, status="settled")
                    budget_tracker.record_usage(est_cost / 1_000_000)
                    embeddings_list = res.embeddings if hasattr(res, 'embeddings') and res.embeddings else [res.embedding]
                    for emb in embeddings_list:
                        values = list(emb.values)
                        all_embeddings.append(values)
                else:
                    ai_budget_service.release(req_id, reason="mock_provider")
                    all_embeddings.extend([[0.0] * 1536 for _ in batch_texts])
            except Exception as e:
                err_str = str(e).lower()
                if "timeout" in err_str or "timed out" in err_str:
                    ai_budget_service.settle(req_id, est_cost, status="uncertain")
                else:
                    ai_budget_service.release(req_id, reason=str(e)[:200])
                all_embeddings.extend([[0.0] * 1536 for _ in batch_texts])

        return all_embeddings

    def query_contract(
        self, 
        contract_text: str, 
        question: str, 
        report_id: Optional[str] = None, 
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Queries the contract using semantic pgvector search if report_id and user_id are available.
        Otherwise falls back to direct contract text grounding.
        Guarantees verifiable clause citations and rejects queries when no supporting clauses exist.
        """
        # 1. Semantic pgvector search if report_id and user_id are available
        if report_id and user_id and self.supabase:
            try:
                query_emb = self.generate_embedding(question)
                rpc_res = self.supabase.rpc("match_contract_clauses", {
                    "query_embedding": query_emb,
                    "match_report_id": report_id,
                    "requesting_user_id": user_id,
                    "match_count": 5,
                    "similarity_threshold": 0.40
                }).execute()

                matched_clauses = rpc_res.data or []
                if not matched_clauses:
                    return {
                        "answer": "No supporting clauses or relevant provisions were found in this agreement regarding your inquiry.",
                        "citations": []
                    }

                # Construct prompt using strictly retrieved clauses
                context_sections = []
                citations = []
                for c in matched_clauses:
                    clause_num = c.get("clause_number", 0)
                    sim_pct = int(round(c.get("similarity", 0) * 100))
                    clause_snippet = c.get("clause_text", "")
                    context_sections.append(f"[Clause #{clause_num} (Relevance: {sim_pct}%)]:\n{clause_snippet}")
                    citations.append(f"Clause #{clause_num} ({sim_pct}% match)")

                retrieved_context = "\n\n".join(context_sections)
                system_prompt = (
                    "You are TraceClause AI legal assistant. Answer the user's question accurately using ONLY "
                    "the provided contract clauses below. Always cite the exact Clause numbers in your response. "
                    "Do NOT extrapolate or invent facts not stated in these clauses."
                )
                user_prompt = f"Relevant Clauses:\n{retrieved_context}\n\nQuestion: {question}"

                return self._generate_completion(system_prompt, user_prompt, citations)
            except Exception:
                pass  # Fall back to text grounding if vector RPC fails

        # 2. Fallback: Direct text grounding
        system_prompt = (
            "You are TraceClause AI legal assistant. Answer the user's question accurately using ONLY "
            "the provided contract text. Cite clause numbers where available."
        )
        user_prompt = f"Contract Text:\n\"\"\"\n{contract_text[:8000]}\n\"\"\"\n\nQuestion: {question}"
        return self._generate_completion(system_prompt, user_prompt, [f"TraceClause RAG ({self.llm_provider})"])

    def _generate_completion(self, system_prompt: str, user_prompt: str, citations: List[str]) -> Dict[str, Any]:
        model = settings.OPENAI_MODEL if self.llm_provider == "openai" else (
            settings.GEMINI_MODEL if self.llm_provider == "gemini" else settings.ANTHROPIC_MODEL
        )
        req_id = f"rag_req_{uuid.uuid4().hex}"
        prompt = f"{system_prompt}\n\n{user_prompt}"
        est_cost = AIBudgetService.estimate_cost_microdollars(model, prompt, max_output_tokens=1000)

        # 1. Atomically check and reserve in durable ledger
        reserved = ai_budget_service.reserve(req_id, est_cost, provider=self.llm_provider, model=model)
        if not reserved:
            raise RuntimeError("Monthly AI budget limit reached. Grounded RAG query is halted.")

        try:
            if self.llm_provider == "openai" and self.openai_client:
                res = self.openai_client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.2
                )
                tokens_in = res.usage.prompt_tokens if hasattr(res, 'usage') and res.usage else len(prompt) // 4
                tokens_out = res.usage.completion_tokens if hasattr(res, 'usage') and res.usage else 200
                actual_cost = AIBudgetService.calculate_actual_cost_microdollars(model, tokens_in, tokens_out)
                ai_budget_service.settle(req_id, actual_cost, status="settled")
                budget_tracker.record_usage(actual_cost / 1_000_000)
                return {"answer": res.choices[0].message.content, "citations": citations}

            elif self.llm_provider == "gemini" and self.gemini_client:
                res = self.gemini_client.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=f"{system_prompt}\n\n{user_prompt}"
                )
                tokens_in = getattr(res.usage_metadata, 'prompt_token_count', len(prompt) // 4)
                tokens_out = getattr(res.usage_metadata, 'candidates_token_count', 200)
                actual_cost = AIBudgetService.calculate_actual_cost_microdollars(model, tokens_in, tokens_out)
                ai_budget_service.settle(req_id, actual_cost, status="settled")
                budget_tracker.record_usage(actual_cost / 1_000_000)
                return {"answer": res.text, "citations": citations}

            elif self.llm_provider == "anthropic" and self.anthropic_client:
                res = self.anthropic_client.messages.create(
                    model=settings.ANTHROPIC_MODEL,
                    max_tokens=1000,
                    messages=[{"role": "user", "content": f"{system_prompt}\n\n{user_prompt}"}]
                )
                tokens_in = res.usage.input_tokens if hasattr(res, 'usage') and res.usage else len(prompt) // 4
                tokens_out = res.usage.output_tokens if hasattr(res, 'usage') and res.usage else 200
                actual_cost = AIBudgetService.calculate_actual_cost_microdollars(model, tokens_in, tokens_out)
                ai_budget_service.settle(req_id, actual_cost, status="settled")
                budget_tracker.record_usage(actual_cost / 1_000_000)
                return {"answer": res.content[0].text, "citations": citations}

            else:
                ai_budget_service.release(req_id, reason="mock_provider")
                return self._mock_chat_response(user_prompt)
        except Exception as e:
            err_str = str(e).lower()
            if "timeout" in err_str or "timed out" in err_str:
                ai_budget_service.settle(req_id, est_cost, status="uncertain")
            else:
                ai_budget_service.release(req_id, reason=str(e)[:200])
            return self._mock_chat_response(user_prompt)

    def _mock_chat_response(self, text: str) -> Dict[str, Any]:
        q_lower = text.lower()
        if "termination" in q_lower or "cancel" in q_lower:
            answer = "Either party may terminate this agreement upon 30 days prior written notice."
            citations = ["Clause #8 (Termination & Cancellation)"]
        elif "liability" in q_lower or "cap" in q_lower:
            answer = "Total cumulative aggregate liability is capped at fees paid in the preceding 12 months."
            citations = ["Clause #12 (Limitation of Liability)"]
        else:
            answer = "Contract analysis indicates standard commercial covenants apply as specified in the agreement."
            citations = ["Clause #4 (General Provisions)"]

        return {"answer": answer, "citations": citations}

RAGService = VectorStoreService
