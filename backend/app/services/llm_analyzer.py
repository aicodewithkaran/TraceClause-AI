import json
import logging
from typing import List, Dict
from openai import OpenAI
from anthropic import Anthropic
from google import genai
from tenacity import retry, stop_after_attempt, wait_random_exponential
from app.core.config import settings
from app.schemas.contract import ClauseAnalysis, AnalysisSummary, ContractAnalysisResponse

logger = logging.getLogger(__name__)

def _is_transient_error(e: BaseException) -> bool:
    """Detect rate limits, network timeouts, and temporary upstream 5xx errors."""
    err_name = type(e).__name__.lower()
    err_str = str(e).lower()
    transient_indicators = (
        "rate", "429", "timeout", "busy", "overload", "connection",
        "temporarily", "503", "500", "502", "504", "resourceexhausted"
    )
    return any(ind in err_name or ind in err_str for ind in transient_indicators)

@retry(
    wait=wait_random_exponential(min=1, max=10),
    stop=stop_after_attempt(4),
    retry=_is_transient_error,
    reraise=True
)
def _call_gemini_with_retry(client, model: str, prompt: str):
    return client.models.generate_content(model=model, contents=prompt)

@retry(
    wait=wait_random_exponential(min=1, max=10),
    stop=stop_after_attempt(4),
    retry=_is_transient_error,
    reraise=True
)
def _call_openai_with_retry(client, model: str, prompt: str):
    return client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a legal contract review assistant. Respond ONLY with a valid JSON array."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.1
    )

@retry(
    wait=wait_random_exponential(min=1, max=10),
    stop=stop_after_attempt(4),
    retry=_is_transient_error,
    reraise=True
)
def _call_anthropic_with_retry(client, model: str, prompt: str):
    return client.messages.create(
        model=model,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )

class LLMAnalyzer:
    """Multi-Provider LLM Clause Risk Analysis Engine supporting OpenAI, Gemini & Claude."""

    def __init__(self):
        # Auto-detect available API key if provider is not explicitly set
        self.provider = settings.LLM_PROVIDER.lower() if settings.LLM_PROVIDER else self._detect_provider()
        
        # Clients
        self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
        self.anthropic_client = Anthropic(api_key=settings.ANTHROPIC_API_KEY) if settings.ANTHROPIC_API_KEY else None
        self.gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY) if settings.GEMINI_API_KEY else None

    def _detect_provider(self) -> str:
        if settings.OPENAI_API_KEY:
            return "openai"
        elif settings.GEMINI_API_KEY:
            return "gemini"
        elif settings.ANTHROPIC_API_KEY:
            return "anthropic"
        return "mock"

    BATCH_SIZE = 50

    def analyze_clauses(self, file_name: str, full_text: str, clauses: List[Dict[str, str]]) -> ContractAnalysisResponse:
        analyzed_clauses: List[ClauseAnalysis] = []
        high_count, med_count, low_count = 0, 0, 0

        # Process clauses in batches of up to 50 clauses per LLM call
        for i in range(0, len(clauses), self.BATCH_SIZE):
            batch = clauses[i:i + self.BATCH_SIZE]
            batch_analyses = self._analyze_batch(batch)

            for analysis in batch_analyses:
                analyzed_clauses.append(analysis)
                if analysis.risk_level.upper() == "HIGH":
                    high_count += 1
                elif analysis.risk_level.upper() == "MEDIUM":
                    med_count += 1
                else:
                    low_count += 1

        overall_score = "HIGH RISK" if high_count > 0 else ("MEDIUM RISK" if med_count > 0 else "LOW RISK")

        return ContractAnalysisResponse(
            file_name=file_name,
            extracted_text=full_text,
            summary=AnalysisSummary(
                total_clauses=len(analyzed_clauses),
                high_risks=high_count,
                medium_risks=med_count,
                low_risks=low_count,
                overall_risk_score=overall_score
            ),
            clauses=analyzed_clauses
        )

    @classmethod
    def is_mock_allowed(cls) -> bool:
        """Mock analysis is strictly restricted to development/test environments with demo auth enabled."""
        return settings.ALLOW_DEMO_AUTH and settings.ENVIRONMENT.lower() in ("development", "test")

    def _analyze_batch(self, batch: List[Dict[str, str]]) -> List[ClauseAnalysis]:
        """Analyze a batch of up to 50 clauses in a single LLM API call."""
        from app.core.rate_limiter import budget_tracker
        if budget_tracker.is_budget_exceeded():
            raise RuntimeError(
                f"Monthly AI budget hard limit (${budget_tracker.monthly_budget_usd:.2f} USD) has been reached. "
                "AI analysis is temporarily paused by circuit breaker to prevent cost overruns."
            )

        if self.provider == "openai" and self.openai_client:
            return self._review_batch_openai(batch)
        elif self.provider == "gemini" and self.gemini_client:
            return self._review_batch_gemini(batch)
        elif self.provider == "anthropic" and self.anthropic_client:
            return self._review_batch_anthropic(batch)
        else:
            if not self.is_mock_allowed():
                raise RuntimeError(
                    f"No active AI provider configured (provider={self.provider}). "
                    "Mock legal analysis is strictly prohibited in production."
                )
            return [self._mock_analysis(clause) for clause in batch]

    def _get_batch_prompt(self, batch: List[Dict[str, str]]) -> str:
        batch_input = [
            {
                "clause_number": c["clause_number"],
                "clause_name": c["clause_name"],
                "text": c["text"]
            }
            for c in batch
        ]

        return f"""
You are an elite corporate legal counsel reviewing commercial contract clauses for liability risks.
Analyze the following batch of contract clauses and respond ONLY with a valid JSON ARRAY of objects.

JSON Array Item Schema:
[
  {{
    "clause_number": 1,
    "clause_name": "Short descriptive title",
    "risk_level": "High" | "Medium" | "Low",
    "risk_explanation": "Detailed explanation of commercial/legal risk and liability",
    "suggested_counter_language": "Safer alternative legal redline text",
    "category": "Indemnity" | "Liability" | "Termination" | "IP" | "Confidentiality" | "General"
  }}
]

Batch Clauses to Review:
```json
{json.dumps(batch_input, indent=2)}
```
"""

    def _extract_json_array(self, text: str) -> list:
        """Extract a valid JSON array from raw LLM output even if surrounded by text or markdown."""
        import re
        if not text:
            return []
        
        # Try direct json.loads after removing markdown block syntax
        cleaned = text.replace("```json", "").replace("```", "").strip()
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                return parsed.get("clauses", parsed.get("items", parsed.get("data", [])))
        except Exception:
            pass

        # Use regex to find array boundaries [...]
        match = re.search(r'\[\s*\{.*\}\s*\]', text, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                pass
        return []

    def _execute_provider_call(self, provider: str, model: str, prompt: str, call_func):
        """
        Executes a provider call wrapped in the durable, concurrency-safe database budget ledger:
        1. Reserve maximum plausible cost via PostgreSQL FOR UPDATE.
        2. Execute the model call with tenacity retries.
        3. If successful, settle with actual token cost.
        4. If timeout/network uncertainty, settle as 'uncertain'.
        5. If definite client error, release reservation.
        """
        import uuid
        from app.services.ai_budget_service import ai_budget_service, AIBudgetService
        from app.core.rate_limiter import budget_tracker

        req_id = f"ai_req_{uuid.uuid4().hex}"
        estimated_microdollars = AIBudgetService.estimate_cost_microdollars(model, prompt)

        # 1. Atomically check and reserve in PostgreSQL ledger
        reserved = ai_budget_service.reserve(
            reservation_id=req_id,
            estimated_microdollars=estimated_microdollars,
            provider=provider,
            model=model
        )
        if not reserved:
            raise RuntimeError(
                f"Monthly AI budget limit (${ai_budget_service.cap_microdollars / 1_000_000:.2f} USD) exceeded. "
                "AI analysis is halted by database budget ledger."
            )

        try:
            res = call_func()
            
            # 2. Extract actual tokens and settle
            tokens_in, tokens_out = 0, 0
            if provider == "gemini":
                tokens_in = getattr(res.usage_metadata, 'prompt_token_count', len(prompt) // 4)
                tokens_out = getattr(res.usage_metadata, 'candidates_token_count', 800)
            elif provider == "openai":
                tokens_in = res.usage.prompt_tokens if hasattr(res, 'usage') and res.usage else len(prompt) // 4
                tokens_out = res.usage.completion_tokens if hasattr(res, 'usage') and res.usage else 800
            elif provider == "anthropic":
                tokens_in = res.usage.input_tokens if hasattr(res, 'usage') and res.usage else len(prompt) // 4
                tokens_out = res.usage.output_tokens if hasattr(res, 'usage') and res.usage else 800

            actual_microdollars = AIBudgetService.calculate_actual_cost_microdollars(model, tokens_in, tokens_out)
            ai_budget_service.settle(req_id, actual_microdollars, status="settled")
            budget_tracker.record_usage(actual_microdollars / 1_000_000)
            return res
        except Exception as e:
            err_str = str(e).lower()
            if "timeout" in err_str or "timed out" in err_str:
                # Uncertain billing: settle at estimated cost so budget is not under-counted
                ai_budget_service.settle(req_id, estimated_microdollars, status="uncertain", metadata={"error": str(e)[:200]})
            else:
                ai_budget_service.release(req_id, reason=str(e)[:200])
            raise

    def _review_batch_gemini(self, batch: List[Dict[str, str]]) -> List[ClauseAnalysis]:
        prompt = self._get_batch_prompt(batch)
        try:
            res = self._execute_provider_call(
                "gemini", 
                settings.GEMINI_MODEL, 
                prompt, 
                lambda: _call_gemini_with_retry(self.gemini_client, settings.GEMINI_MODEL, prompt)
            )

            data_list = self._extract_json_array(res.text)
            if data_list and len(data_list) > 0:
                return self._parse_batch_json(batch, data_list)
            
            if self.is_mock_allowed():
                return [self._mock_analysis(c) for c in batch]
            raise RuntimeError("Gemini returned response without a parseable clause JSON array.")
        except Exception as e:
            if self.is_mock_allowed():
                return [self._mock_analysis(c) for c in batch]
            logger.error(f"Gemini batch analysis failed: {type(e).__name__} - {e}")
            raise RuntimeError(f"AI contract analysis failed ({type(e).__name__}). Quota has been preserved.")

    def _review_batch_openai(self, batch: List[Dict[str, str]]) -> List[ClauseAnalysis]:
        prompt = self._get_batch_prompt(batch)
        try:
            res = self._execute_provider_call(
                "openai",
                settings.OPENAI_MODEL,
                prompt,
                lambda: _call_openai_with_retry(self.openai_client, settings.OPENAI_MODEL, prompt)
            )

            data_list = self._extract_json_array(res.choices[0].message.content)
            if data_list and len(data_list) > 0:
                return self._parse_batch_json(batch, data_list)
            
            if self.is_mock_allowed():
                return [self._mock_analysis(c) for c in batch]
            raise RuntimeError("OpenAI returned response without a parseable clause JSON array.")
        except Exception as e:
            if self.is_mock_allowed():
                return [self._mock_analysis(c) for c in batch]
            logger.error(f"OpenAI batch analysis failed: {type(e).__name__} - {e}")
            raise RuntimeError(f"AI contract analysis failed ({type(e).__name__}). Quota has been preserved.")

    def _review_batch_anthropic(self, batch: List[Dict[str, str]]) -> List[ClauseAnalysis]:
        prompt = self._get_batch_prompt(batch)
        try:
            res = self._execute_provider_call(
                "anthropic",
                settings.ANTHROPIC_MODEL,
                prompt,
                lambda: _call_anthropic_with_retry(self.anthropic_client, settings.ANTHROPIC_MODEL, prompt)
            )

            data_list = self._extract_json_array(res.content[0].text)
            if data_list and len(data_list) > 0:
                return self._parse_batch_json(batch, data_list)
            
            if self.is_mock_allowed():
                return [self._mock_analysis(c) for c in batch]
            raise RuntimeError("Anthropic returned response without a parseable clause JSON array.")
        except Exception as e:
            if self.is_mock_allowed():
                return [self._mock_analysis(c) for c in batch]
            logger.error(f"Anthropic batch analysis failed: {type(e).__name__} - {e}")
            raise RuntimeError(f"AI contract analysis failed ({type(e).__name__}). Quota has been preserved.")

    def _parse_batch_json(self, batch: List[Dict[str, str]], data_list: list) -> List[ClauseAnalysis]:
        """
        Parses LLM JSON array into structured ClauseAnalysis objects.
        Strict verification: Any missing, incomplete, or unverified clause results in an
        immediate failure rather than falling back to false-negative 'Low' / 'Acceptable' defaults.
        """
        results: List[ClauseAnalysis] = []
        data_map = {item.get("clause_number"): item for item in data_list if isinstance(item, dict)}

        for idx, c in enumerate(batch):
            num = c["clause_number"]
            data = data_map.get(num)
            
            # Fallback by index position only if clause_number matching was omitted by the model
            if not data and idx < len(data_list) and isinstance(data_list[idx], dict):
                data = data_list[idx]
            
            # Fail closed: Do NOT mask missing AI evaluations with reassuring defaults
            if not data or not data.get("risk_level"):
                raise RuntimeError(
                    f"AI analysis returned incomplete results: Clause {num} ('{c.get('clause_name', '')}') "
                    "was omitted from the model output. Batch failed to prevent unreviewed clauses appearing safe."
                )

            raw_risk = str(data.get("risk_level", "")).strip().upper()
            if raw_risk not in ("HIGH", "MEDIUM", "LOW"):
                raise RuntimeError(
                    f"AI analysis returned unrecognized risk level '{raw_risk}' for Clause {num}. "
                    "Batch failed to ensure rigorous legal risk standards."
                )

            results.append(
                ClauseAnalysis(
                    clause_number=num,
                    clause_name=data.get("clause_name") or c["clause_name"],
                    original_text=c["text"],
                    risk_level=raw_risk.capitalize(),
                    risk_explanation=data.get("risk_explanation") or f"Analysis for section: {c['clause_name']}",
                    suggested_counter_language=data.get("suggested_counter_language") or "Acceptable as written.",
                    category=data.get("category") or "General"
                )
            )
        return results

    def _mock_analysis(self, clause: Dict[str, str]) -> ClauseAnalysis:
        name = clause.get("clause_name", f"Clause {clause['clause_number']}")
        text_lower = clause["text"].lower()
        
        if "indemnify" in text_lower or "uncapped liability" in text_lower:
            risk = "High"
            explanation = f"High liability risk detected in {name}. Imposes broad indemnification covenants on Customer."
            counter = f"Modify {name} to provide capped, mutual indemnification strictly limited to direct third-party losses."
            cat = "Indemnity"
        elif "terminate" in text_lower or "auto-renew" in text_lower or "renewal" in text_lower:
            risk = "Medium"
            explanation = f"Commercial renewal risk in {name}. Subscriptions auto-renew without advance notification window."
            counter = f"Revise {name} to require 60-day prior written notification before any automatic subscription renewal."
            cat = "Termination"
        elif "intellectual property" in text_lower or "ownership" in text_lower or "reverse engineer" in text_lower:
            risk = "Medium"
            explanation = f"IP restriction in {name}. Strictly prohibits decompilation, modification, or derivative creation."
            counter = f"Standard IP protection in {name}. Ensure mutual retention of pre-existing background IP."
            cat = "IP"
        elif "audit" in text_lower or "fee" in text_lower or "tax" in text_lower:
            risk = "Medium"
            explanation = f"Financial audit exposure in {name}. Grants Vendor audit rights and late payment interest fees."
            counter = f"Limit audit frequency in {name} to once per 12 months with 30 days prior written notice."
            cat = "General"
        else:
            risk = "Low"
            explanation = f"Standard customary commercial provision in {name}."
            counter = "No revision necessary. Customary standard legal language."
            cat = "General"

        return ClauseAnalysis(
            clause_number=clause["clause_number"],
            clause_name=name,
            original_text=clause["text"],
            risk_level=risk,
            risk_explanation=explanation,
            suggested_counter_language=counter,
            category=cat
        )
