import io
import zipfile
import fitz
import docx
import pytest
from app.core.config import settings

def create_valid_pdf_bytes(text: str = "Standard commercial legal contract clause with sufficient text to satisfy length requirements.") -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), text)
    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes

def create_valid_docx_bytes(text: str = "Standard commercial legal contract clause with sufficient text to satisfy length requirements.") -> bytes:
    doc = docx.Document()
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()

def test_upload_missing_auth(client):
    """Assert upload endpoint returns 401 Unauthorized when no credentials provided."""
    files = {"file": ("contract.pdf", create_valid_pdf_bytes(), "application/pdf")}
    res = client.post("/api/v1/documents/upload", files=files)
    assert res.status_code == 401
    assert "Authentication credentials were not provided" in res.json()["detail"]

def test_upload_invalid_auth_header(client):
    """Assert upload returns 401 when Authorization header is malformed."""
    files = {"file": ("contract.pdf", create_valid_pdf_bytes(), "application/pdf")}
    res = client.post("/api/v1/documents/upload", files=files, headers={"Authorization": "Token 12345"})
    assert res.status_code == 401
    assert "Invalid authorization header format" in res.json()["detail"]

def test_upload_legacy_doc_rejection(client, auth_headers):
    """Assert legacy .doc files are cleanly rejected with HTTP 400."""
    ole2_bytes = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"legacy doc binary content"
    files = {"file": ("old_contract.doc", ole2_bytes, "application/msword")}
    res = client.post("/api/v1/documents/upload", files=files, headers=auth_headers)
    assert res.status_code == 400
    assert "Legacy binary Word (.doc) format is not supported" in res.json()["detail"]

def test_upload_disguised_fake_pdf(client, auth_headers):
    """Assert text/binary files disguised with .pdf extension are blocked via magic byte check."""
    fake_bytes = b"This is plain text without PDF magic bytes header."
    files = {"file": ("disguised.pdf", fake_bytes, "application/pdf")}
    res = client.post("/api/v1/documents/upload", files=files, headers=auth_headers)
    assert res.status_code == 422
    assert "invalid magic header" in res.json()["detail"].lower()

def test_upload_disguised_fake_docx(client, auth_headers):
    """Assert fake DOCX files without standard ZIP/OpenXML headers are blocked."""
    fake_bytes = b"Not a zip file"
    files = {"file": ("disguised.docx", fake_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    res = client.post("/api/v1/documents/upload", files=files, headers=auth_headers)
    assert res.status_code == 422
    assert "invalid magic header" in res.json()["detail"].lower()

def test_upload_low_text_pdf_heuristic(client, auth_headers):
    """Assert PDFs with insufficient selectable text return 422 with OCR guidance."""
    # Create PDF with only 10 characters
    short_text_pdf = create_valid_pdf_bytes("Too short")
    files = {"file": ("short.pdf", short_text_pdf, "application/pdf")}
    res = client.post("/api/v1/documents/upload", files=files, headers=auth_headers)
    assert res.status_code == 422
    assert "Insufficient selectable text detected" in res.json()["detail"]
    assert "Optical Character Recognition (OCR)" in res.json()["detail"]

def test_upload_zip_bomb_entry_limit(client, auth_headers):
    """Assert DOCX archive with excessive entry count (> 500 entries) is rejected."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("word/document.xml", "<document/>")
        # Add 501 small dummy entries
        for i in range(505):
            zf.writestr(f"word/dummy_{i}.xml", "x")

    files = {"file": ("bomb.docx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    res = client.post("/api/v1/documents/upload", files=files, headers=auth_headers)
    assert res.status_code == 422
    assert "exceeding the maximum safe limit" in res.json()["detail"]

def test_upload_streaming_size_limit(client, auth_headers, monkeypatch):
    """Assert upload exceeding MAX_UPLOAD_SIZE_MB triggers HTTP 413 Payload Too Large."""
    # Temporarily set max size to 1 MB for testing
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 1)
    
    # 1.5 MB dummy PDF bytes starting with %PDF-
    large_bytes = b"%PDF-" + b"0" * (int(1.5 * 1024 * 1024))
    files = {"file": ("large.pdf", large_bytes, "application/pdf")}
    res = client.post("/api/v1/documents/upload", files=files, headers=auth_headers)
    assert res.status_code == 413
    assert "exceeds the maximum permitted limit" in res.json()["detail"]

def test_upload_valid_pdf(client, auth_headers):
    """Assert valid PDF upload extracts text cleanly in memory."""
    valid_text = "Clause 1: Confidentiality. The recipient agrees to maintain strict confidentiality of all proprietary materials. Clause 2: Termination on 30 days notice."
    pdf_bytes = create_valid_pdf_bytes(valid_text)
    files = {"file": ("commercial_agreement.pdf", pdf_bytes, "application/pdf")}
    res = client.post("/api/v1/documents/upload", files=files, headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["filename"] == "commercial_agreement.pdf"
    assert data["file_type"] == "PDF"
    assert data["char_count"] > 50
    assert "Confidentiality" in data["extracted_text"]

def test_upload_valid_docx(client, auth_headers):
    """Assert valid DOCX upload extracts text cleanly via BytesIO with zero disk temporary files."""
    valid_text = "Clause 1: Limitation of Liability. Vendor cumulative aggregate liability shall not exceed the total fees paid in the prior 12 months."
    docx_bytes = create_valid_docx_bytes(valid_text)
    files = {"file": ("master_services_agreement.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    res = client.post("/api/v1/documents/upload", files=files, headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["filename"] == "master_services_agreement.docx"
    assert data["file_type"] == "DOCX"
    assert "Limitation of Liability" in data["extracted_text"]

