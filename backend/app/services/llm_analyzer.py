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

    def analyze_clauses(self, file_name: str, full_text: str, clauses: List[Dict[str, str]]) -> ContractAnalysisResponse:
        analyzed_clauses: List[ClauseAnalysis] = []
        high_count, med_count, low_count = 0, 0, 0

        for clause in clauses:
            if self.provider == "openai" and self.openai_client:
                analysis = self._review_with_openai(clause)
            elif self.provider == "gemini" and self.gemini_client:
                analysis = self._review_with_gemini(clause)
            elif self.provider == "anthropic" and self.anthropic_client:
                analysis = self._review_with_anthropic(clause)
            else:
                analysis = self._mock_analysis(clause)

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

    def _get_prompt(self, text: str) -> str:
        return f"""
You are a top corporate attorney analyzing a contract clause for commercial risk.
Analyze the following clause and respond ONLY with a valid JSON object.

JSON Schema:
{{
  "clause_name": "Short descriptive title of clause",
  "risk_level": "High" | "Medium" | "Low",
  "risk_explanation": "Detailed explanation of potential commercial or legal liability",
  "suggested_counter_language": "Safer alternative legal redline text",
  "category": "Indemnity" | "Liability" | "Termination" | "IP" | "Confidentiality" | "General"
}}

Clause Text:
\"\"\"
{text}
\"\"\"
"""

    def _review_with_openai(self, clause: Dict[str, str]) -> ClauseAnalysis:
        try:
            res = self.openai_client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are a legal contract review assistant. Output pure JSON."},
                    {"role": "user", "content": self._get_prompt(clause['text'])}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            data = json.loads(res.choices[0].message.content)
            return self._parse_json_response(clause, data)
        except Exception:
            return self._mock_analysis(clause)

    def _review_with_gemini(self, clause: Dict[str, str]) -> ClauseAnalysis:
        try:
            res = self.gemini_client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=self._get_prompt(clause['text'])
            )
            clean_json = res.text.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_json)
            return self._parse_json_response(clause, data)
        except Exception:
            return self._mock_analysis(clause)

    def _review_with_anthropic(self, clause: Dict[str, str]) -> ClauseAnalysis:
        try:
            res = self.anthropic_client.messages.create(
                model=settings.ANTHROPIC_MODEL,
                max_tokens=1000,
                messages=[
                    {"role": "user", "content": self._get_prompt(clause['text'])}
                ]
            )
            clean_json = res.content[0].text.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_json)
            return self._parse_json_response(clause, data)
        except Exception:
            return self._mock_analysis(clause)

    def _parse_json_response(self, clause: Dict[str, str], data: dict) -> ClauseAnalysis:
        return ClauseAnalysis(
            clause_number=clause["clause_number"],
            clause_name=data.get("clause_name", clause["clause_name"]),
            original_text=clause["text"],
            risk_level=data.get("risk_level", "Low"),
            risk_explanation=data.get("risk_explanation", "Standard legal clause."),
            suggested_counter_language=data.get("suggested_counter_language", "Acceptable as written."),
            category=data.get("category", "General")
        )

    def _mock_analysis(self, clause: Dict[str, str]) -> ClauseAnalysis:
        text_lower = clause["text"].lower()
        if "indemnify" in text_lower or "unlimited liability" in text_lower:
            risk, explanation, counter, cat = "High", "This clause imposes broad indemnity or uncapped liability.", "Replace with capped mutual indemnification limited to direct actual damages.", "Indemnity"
        elif "terminate" in text_lower or "auto-renew" in text_lower:
            risk, explanation, counter, cat = "Medium", "Contains automatic renewal terms without explicit prior notification requirement.", "Require 30 days prior written notification before renewal.", "Termination"
        else:
            risk, explanation, counter, cat = "Low", "Standard customary commercial terms.", "No revision necessary.", "General"

        return ClauseAnalysis(
            clause_number=clause["clause_number"],
            clause_name=clause["clause_name"],
            original_text=clause["text"],
            risk_level=risk,
            risk_explanation=explanation,
            suggested_counter_language=counter,
            category=cat
        )
