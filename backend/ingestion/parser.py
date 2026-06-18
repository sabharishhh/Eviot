import fitz  # PyMuPDF
import docx
import io

def parse_file(filename: str, content: bytes) -> str:
    ext = filename.lower().rsplit(".", 1)[-1]
    if ext == "pdf":
        return _parse_pdf(content)
    elif ext == "docx":
        return _parse_docx(content)
    elif ext in ("txt", "md"):
        return content.decode("utf-8", errors="replace")
    else:
        raise ValueError(f"Unsupported file type: {ext}")

def _parse_pdf(content: bytes) -> str:
    doc = fitz.open(stream=content, filetype="pdf")
    return "\n".join(page.get_text() for page in doc)

def _parse_docx(content: bytes) -> str:
    d = docx.Document(io.BytesIO(content))
    return "\n".join(p.text for p in d.paragraphs if p.text.strip())