from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, status
from app.services.document_parser import DocumentParser
from app.services.chunking import ChunkingEngine
from app.schemas.contract import DocumentExtractResponse
from app.core.security import get_current_user, AuthenticatedUser
from app.core.config import settings

router = APIRouter()

@router.post("/upload", response_model=DocumentExtractResponse)
async def upload_contract(
    file: UploadFile = File(...),
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Upload and parse PDF or Word (.docx) contracts directly in memory.
    Protected endpoint: Enforces authenticated session, streaming file size limit (15MB),
    magic byte validation, ZIP bomb checks, page limits, and heuristic low-text detection.
    """
    filename = file.filename or ""
    lower_name = filename.lower()

    # Reject legacy .doc immediately
    if lower_name.endswith(".doc"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Legacy binary Word (.doc) format is not supported. Please convert and save your file as modern Word (.docx) or PDF before uploading."
        )

    if not lower_name.endswith((".pdf", ".docx")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file extension. Only modern .pdf and .docx files are permitted."
        )

    # Enforce streaming file size limit to prevent memory exhaustion
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    content_chunks = []
    total_bytes = 0
    chunk_size = 64 * 1024  # 64 KB chunks

    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total_bytes += len(chunk)
        if total_bytes > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Uploaded file exceeds the maximum permitted limit of {settings.MAX_UPLOAD_SIZE_MB} MB."
            )
        content_chunks.append(chunk)

    file_bytes = b"".join(content_chunks)

    try:
        extracted_text = DocumentParser.parse_document(file_bytes, filename)
        clauses = ChunkingEngine.split_into_clauses(extracted_text)

        preview = extracted_text[:300] + "..." if len(extracted_text) > 300 else extracted_text

        return DocumentExtractResponse(
            filename=filename,
            file_type=filename.rsplit(".", 1)[-1].upper(),
            char_count=len(extracted_text),
            clause_count=len(clauses),
            text_preview=preview,
            extracted_text=extracted_text
        )
    except ValueError as ve:
        err_msg = str(ve)
        if "Legacy binary Word" in err_msg or "Unsupported file format" in err_msg:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=err_msg)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while processing document: {str(e)}"
        )
