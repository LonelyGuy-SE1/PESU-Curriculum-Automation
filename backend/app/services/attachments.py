import re
import subprocess
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree

MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_TEXT_CHARS = 50000
SPACE = re.compile(r"[ \t]+")
BLANKS = re.compile(r"\n{3,}")


def extract_text(filename: str, content_type: str, data: bytes) -> tuple[str, str, str]:
    if len(data) > MAX_FILE_BYTES:
        return "", "failed", "File is larger than 8 MB"
    suffix = Path(filename or "").suffix.lower()
    try:
        if suffix == ".pdf" or content_type == "application/pdf":
            return _clean(_pdf_text(data)), "ready", ""
        if suffix == ".docx":
            return _clean(_docx_text(data)), "ready", ""
        if suffix == ".xlsx":
            return _clean(_xlsx_text(data)), "ready", ""
        if suffix in {".txt", ".md", ".csv"} or content_type.startswith("text/"):
            return _clean(_decode(data)), "ready", ""
        if content_type.startswith("image/"):
            return "", "unsupported", "Image OCR is not enabled yet"
        return "", "unsupported", "File type is not supported yet"
    except Exception as exc:
        return "", "failed", str(exc)


def _pdf_text(data: bytes) -> str:
    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "upload.pdf"
        path.write_bytes(data)
        result = subprocess.run(
            ["pdftotext", "-layout", str(path), "-"],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout


def _docx_text(data: bytes) -> str:
    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "upload.docx"
        path.write_bytes(data)
        with zipfile.ZipFile(path) as docx:
            xml = docx.read("word/document.xml")
    root = ElementTree.fromstring(xml)
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    lines = []
    for paragraph in root.iter(f"{ns}p"):
        text = "".join(node.text or "" for node in paragraph.iter(f"{ns}t")).strip()
        if text:
            lines.append(text)
    return "\n".join(lines)


def _xlsx_text(data: bytes) -> str:
    import openpyxl
    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "upload.xlsx"
        path.write_bytes(data)
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        rows = []
        for sheet in wb:
            for row in sheet.iter_rows(values_only=True):
                line = "\t".join(str(c or "") for c in row)
                if line.strip():
                    rows.append(line)
        return "\n".join(rows)


def _decode(data: bytes) -> str:
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def _clean(text: str) -> str:
    text = SPACE.sub(" ", text.replace("\r\n", "\n").replace("\r", "\n"))
    text = BLANKS.sub("\n\n", text).strip()
    return text[:MAX_TEXT_CHARS]
