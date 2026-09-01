from fastapi import APIRouter, HTTPException, Body
from app.services.chunking import ChunkingEngine
from app.services.llm_analyzer import LLMAnalyzer
from app.schemas.contract import ContractAnalysisResponse

router = APIRouter()
analyzer = LLMAnalyzer()

@router.post("/analyze", response_model=ContractAnalysisResponse)
async def analyze_contract(
    file_name: str = Body(..., embed=True),
    extracted_text: str = Body(..., embed=True)
):
    """Run semantic chunking & LLM clause-risk analysis returning structured JSON redlines."""
    if not extracted_text.strip():
        raise HTTPException(status_code=400, detail="Extracted contract text cannot be empty.")

    try:
        clauses = ChunkingEngine.split_into_clauses(extracted_text)
        result = analyzer.analyze_clauses(file_name, extracted_text, clauses)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
