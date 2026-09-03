import json
from typing import List, Dict
from openai import OpenAI
from anthropic import Anthropic
from google import genai
from app.core.config import settings
from app.schemas.contract import ClauseAnalysis, AnalysisSummary, ContractAnalysisResponse

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

    def _analyze_batch(self, batch: List[Dict[str, str]]) -> List[ClauseAnalysis]:
        """Analyze a batch of up to 50 clauses in a single LLM API call."""
        if self.provider == "openai" and self.openai_client:
            return self._review_batch_openai(batch)
        elif self.provider == "gemini" and self.gemini_client:
            return self._review_batch_gemini(batch)
        elif self.provider == "anthropic" and self.anthropic_client:
            return self._review_batch_anthropic(batch)
        else:
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

    def _review_batch_gemini(self, batch: List[Dict[str, str]]) -> List[ClauseAnalysis]:
        try:
            prompt = self._get_batch_prompt(batch)
            res = self.gemini_client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt
            )
            data_list = self._extract_json_array(res.text)
            if data_list and len(data_list) > 0:
                return self._parse_batch_json(batch, data_list)
            return [self._mock_analysis(c) for c in batch]
        except Exception as e:
            print(f"Gemini batch review error: {e}. Falling back to per-clause review.")
            return [self._mock_analysis(c) for c in batch]

    def _review_batch_openai(self, batch: List[Dict[str, str]]) -> List[ClauseAnalysis]:
        try:
            prompt = self._get_batch_prompt(batch)
            res = self.openai_client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are a legal contract review assistant. Respond ONLY with a valid JSON array."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )
            data_list = self._extract_json_array(res.choices[0].message.content)
            if data_list and len(data_list) > 0:
                return self._parse_batch_json(batch, data_list)
            return [self._mock_analysis(c) for c in batch]
        except Exception as e:
            print(f"OpenAI batch review error: {e}. Falling back.")
            return [self._mock_analysis(c) for c in batch]

    def _review_batch_anthropic(self, batch: List[Dict[str, str]]) -> List[ClauseAnalysis]:
        try:
            prompt = self._get_batch_prompt(batch)
            res = self.anthropic_client.messages.create(
                model=settings.ANTHROPIC_MODEL,
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )
            data_list = self._extract_json_array(res.content[0].text)
            if data_list and len(data_list) > 0:
                return self._parse_batch_json(batch, data_list)
            return [self._mock_analysis(c) for c in batch]
        except Exception as e:
            print(f"Anthropic batch review error: {e}. Falling back.")
            return [self._mock_analysis(c) for c in batch]

    def _parse_batch_json(self, batch: List[Dict[str, str]], data_list: list) -> List[ClauseAnalysis]:
        results: List[ClauseAnalysis] = []
        data_map = {item.get("clause_number"): item for item in data_list if isinstance(item, dict)}

        for idx, c in enumerate(batch):
            num = c["clause_number"]
            data = data_map.get(num)
            
            # Fallback by index position if clause_number match failed
            if not data and idx < len(data_list) and isinstance(data_list[idx], dict):
                data = data_list[idx]
            
            if not data:
                data = {}

            results.append(
                ClauseAnalysis(
                    clause_number=num,
                    clause_name=data.get("clause_name", c["clause_name"]),
                    original_text=c["text"],
                    risk_level=data.get("risk_level", "Low"),
                    risk_explanation=data.get("risk_explanation", f"Analysis for section: {c['clause_name']}"),
                    suggested_counter_language=data.get("suggested_counter_language", "Acceptable as written."),
                    category=data.get("category", "General")
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
