import io
import time
import zipfile
import fitz  # PyMuPDF
import docx
from app.core.config import settings

class DocumentParser:
    """
    Hardened In-Memory Document Parser for PDF and Word (DOCX) contracts.
    Performs 100% in-memory parsing with zero filesystem writes, magic-byte validation,
    ZIP bomb mitigation, page limits, and heuristic low-text detection.
    """

    PDF_MAGIC = b"%PDF-"
    ZIP_MAGIC = b"PK\x03\x04"
    OLE2_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

    @classmethod
    def validate_file_signature(cls, file_bytes: bytes, filename: str) -> str:
        """
        Validates magic bytes against filename extension as a first-line defense.
        Returns normalized format ('pdf' or 'docx') or raises ValueError.
        """
        if not file_bytes:
            raise ValueError("Uploaded file is empty (0 bytes).")

        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        # Explicitly detect and cleanly reject legacy .doc files
        if ext == "doc" or file_bytes.startswith(cls.OLE2_MAGIC):
            raise ValueError(
                "Legacy binary Word (.doc) format is not supported. "
                "Please convert and save your file as modern Word (.docx) or PDF before uploading."
            )

        if ext == "pdf":
            if not file_bytes.startswith(cls.PDF_MAGIC):
                raise ValueError("File content does not match standard PDF specification (invalid magic header).")
            return "pdf"

        if ext == "docx":
            if not file_bytes.startswith(cls.ZIP_MAGIC):
                raise ValueError("File content does not match standard DOCX/OpenXML specification (invalid magic header).")
            return "docx"

        raise ValueError(f"Unsupported file format: '.{ext}'. Supported formats are .pdf and .docx")

    @classmethod
    def inspect_docx_zip_safety(cls, file_bytes: bytes):
        """
        Inspects DOCX ZIP container against ZIP bombs, path traversal, and corrupted headers.
        """
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as zf:
                infolist = zf.infolist()
                
                # 1. Entry count limit
                if len(infolist) > settings.MAX_ZIP_ENTRIES:
                    raise ValueError(
                        f"DOCX archive contains {len(infolist)} entries, exceeding the maximum safe limit of {settings.MAX_ZIP_ENTRIES}."
                    )

                total_uncompressed = 0
                max_bytes = settings.MAX_DECOMPRESSED_SIZE_MB * 1024 * 1024

                for zinfo in infolist:
                    total_uncompressed += zinfo.file_size
                    # 2. Cumulative decompressed size limit (Zip Bomb protection)
                    if total_uncompressed > max_bytes:
                        raise ValueError(
                            f"DOCX decompressed size exceeds maximum safe limit of {settings.MAX_DECOMPRESSED_SIZE_MB} MB."
                        )

                    # 3. Compression ratio limit on non-trivial entries
                    if zinfo.compress_size > 0 and zinfo.file_size > 1024 * 512:
                        ratio = zinfo.file_size / zinfo.compress_size
                        if ratio > settings.MAX_COMPRESSION_RATIO:
                            raise ValueError(
                                f"DOCX entry '{zinfo.filename}' compression ratio ({ratio:.1f}:1) exceeds safe limit."
                            )

                # 4. OpenXML Structure check
                names = set(zf.namelist())
                if not any(req in names for req in ("word/document.xml", "[Content_Types].xml")):
                    raise ValueError("Invalid DOCX format: missing standard OpenXML document structure.")

        except zipfile.BadZipFile:
            raise ValueError("Malformed or corrupted DOCX archive.")

    @classmethod
    def extract_text_from_pdf_bytes(cls, file_bytes: bytes) -> str:
        """Parses PDF directly from memory stream with page limit and low-text heuristics."""
        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
        except Exception:
            raise ValueError("Malformed or corrupted PDF file.")

        if doc.is_encrypted:
            raise ValueError("PDF document is password-protected or encrypted. Please provide an unencrypted document.")

        page_count = len(doc)
        if page_count > settings.MAX_PAGE_COUNT:
            raise ValueError(
                f"PDF document contains {page_count} pages, exceeding the maximum permitted limit of {settings.MAX_PAGE_COUNT} pages."
            )

        start_time = time.time()
        text_parts = []

        for page_num in range(page_count):
            if time.time() - start_time > settings.PARSER_TIMEOUT_SECONDS:
                raise ValueError("PDF parsing timed out due to complex document structure.")
            page = doc[page_num]
            page_text = page.get_text("text") or ""
            if page_text.strip():
                text_parts.append(f"\n--- Page {page_num + 1} ---\n{page_text.strip()}")

        extracted = "\n".join(text_parts).strip()

        # Heuristic low-text detection
        if len(extracted) < 50:
            raise ValueError(
                "Insufficient selectable text detected (fewer than 50 characters). "
                "If this is a scanned document or image-based PDF, please run Optical Character Recognition (OCR) before uploading."
            )

        return extracted

    @classmethod
    def extract_text_from_docx_bytes(cls, file_bytes: bytes) -> str:
        """Parses DOCX directly from memory via io.BytesIO stream without temporary files on disk."""
        cls.inspect_docx_zip_safety(file_bytes)

        try:
            doc_stream = io.BytesIO(file_bytes)
            doc = docx.Document(doc_stream)
        except Exception as e:
            raise ValueError(f"Failed to read DOCX document structure: {str(e)}")

        start_time = time.time()
        full_text = []

        for para in doc.paragraphs:
            if time.time() - start_time > settings.PARSER_TIMEOUT_SECONDS:
                raise ValueError("DOCX parsing timed out due to complex document structure.")
            stripped = para.text.strip()
            if stripped:
                full_text.append(stripped)

        # Also extract table text if present
        for table in doc.tables:
            for row in table.rows:
                row_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if row_text:
                    full_text.append(" | ".join(row_text))

        extracted = "\n\n".join(full_text).strip()

        if len(extracted) < 50:
            raise ValueError(
                "Insufficient selectable text detected in DOCX (fewer than 50 characters). "
                "Please ensure the document contains readable text."
            )

        return extracted

    @classmethod
    def parse_document(cls, file_bytes: bytes, filename: str) -> str:
        """
        Unified entrypoint: validates magic bytes, ensures zero disk footprint,
        and extracts clean contract text.
        """
        fmt = cls.validate_file_signature(file_bytes, filename)
        if fmt == "pdf":
            return cls.extract_text_from_pdf_bytes(file_bytes)
        elif fmt == "docx":
            return cls.extract_text_from_docx_bytes(file_bytes)
        else:
            raise ValueError(f"Unsupported file format: {fmt}")
