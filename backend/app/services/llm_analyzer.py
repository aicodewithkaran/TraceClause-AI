import json
from typing import List, Dict
from openai import OpenAI
from app.core.config import settings
from app.schemas.contract import ClauseAnalysis, AnalysisSummary, ContractAnalysisResponse

class LLMAnalyzer:
    """OpenAI / LLM Clause Risk Analysis Engine returning structured redlines."""

    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.client = OpenAI(api_key=self.api_key) if self.api_key else None
        self.model = settings.LLM_MODEL

    def analyze_clauses(self, file_name: str, full_text: str, clauses: List[Dict[str, str]]) -> ContractAnalysisResponse:
        analyzed_clauses: List[ClauseAnalysis] = []
        high_count, med_count, low_count = 0, 0, 0

        for clause in clauses:
            # If no API key configured, use intelligent mock risk output for testing
            if not self.client:
                analysis = self._mock_analysis(clause)
            else:
                analysis = self._llm_clause_review(clause)

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

    def _llm_clause_review(self, clause: Dict[str, str]) -> ClauseAnalysis:
        prompt = f"""
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
{clause['text']}
\"\"\"
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a legal contract review assistant. Output pure JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            data = json.loads(response.choices[0].message.content)
            return ClauseAnalysis(
                clause_number=clause["clause_number"],
                clause_name=data.get("clause_name", clause["clause_name"]),
                original_text=clause["text"],
                risk_level=data.get("risk_level", "Low"),
                risk_explanation=data.get("risk_explanation", "Standard legal clause."),
                suggested_counter_language=data.get("suggested_counter_language", "Acceptable as written."),
                category=data.get("category", "General")
            )
        except Exception as e:
            return self._mock_analysis(clause, error=str(e))

    def _mock_analysis(self, clause: Dict[str, str], error: str = None) -> ClauseAnalysis:
        text_lower = clause["text"].lower()
        if "indemnify" in text_lower or "unlimited liability" in text_lower or "sole discretion" in text_lower:
            risk = "High"
            explanation = "This clause imposes broad indemnity or uncapped liability on your organization."
            counter = "Replace with capped mutual indemnification limited to direct actual damages."
            cat = "Indemnity"
        elif "terminate" in text_lower or "auto-renew" in text_lower:
            risk = "Medium"
            explanation = "Contains automatic renewal terms without explicit prior notification requirement."
            counter = "Require 30 days prior written notification before renewal."
            cat = "Termination"
        else:
            risk = "Low"
            explanation = "Standard customary commercial terms."
            counter = "No revision necessary."
            cat = "General"

        return ClauseAnalysis(
            clause_number=clause["clause_number"],
            clause_name=clause["clause_name"],
            original_text=clause["text"],
            risk_level=risk,
            risk_explanation=explanation,
            suggested_counter_language=counter,
            category=cat
        )
