import os
import fitz  # PyMuPDF
import docx

class DocumentParser:
    """Extracts text and structural clause sections from PDF and Word contracts."""

    @staticmethod
    def extract_text_from_pdf_bytes(file_bytes: bytes) -> str:
        text = ""
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for page_num in range(len(doc)):
            page = doc[page_num]
            text += f"\n--- Page {page_num + 1} ---\n"
            text += page.get_text("text")
        return text.strip()

    @staticmethod
    def extract_text_from_docx_bytes(file_bytes: bytes, filename: str) -> str:
        import tempfile
        suffix = ".docx"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        try:
            doc = docx.Document(tmp_path)
            full_text = []
            for para in doc.paragraphs:
                if para.text.strip():
                    full_text.append(para.text.strip())
            return "\n\n".join(full_text)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    @classmethod
    def parse_document(cls, file_bytes: bytes, filename: str) -> str:
        ext = filename.split(".")[-1].lower()
        if ext == "pdf":
            return cls.extract_text_from_pdf_bytes(file_bytes)
        elif ext in ["docx", "doc"]:
            return cls.extract_text_from_docx_bytes(file_bytes, filename)
        else:
            raise ValueError(f"Unsupported file format: .{ext}. Supported formats are .pdf and .docx")
