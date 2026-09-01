from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.document_parser import DocumentParser
from app.services.chunking import ChunkingEngine
from app.schemas.contract import DocumentExtractResponse

router = APIRouter()

@router.post("/upload", response_model=DocumentExtractResponse)
async def upload_contract(file: UploadFile = File(...)):
    """Upload PDF or Word contract and extract clean text & initial clauses."""
    filename = file.filename
    if not filename.endswith((".pdf", ".docx", ".doc")):
        raise HTTPException(
            status_code=400, 
            detail="Unsupported file extension. Only .pdf and .docx files are permitted."
        )

    try:
        contents = await file.read()
        extracted_text = DocumentParser.parse_document(contents, filename)
        clauses = ChunkingEngine.split_into_clauses(extracted_text)

        preview = extracted_text[:300] + "..." if len(extracted_text) > 300 else extracted_text

        return DocumentExtractResponse(
            filename=filename,
            file_type=filename.split(".")[-1].upper(),
            char_count=len(extracted_text),
            clause_count=len(clauses),
            text_preview=preview,
            extracted_text=extracted_text
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process document: {str(e)}")
