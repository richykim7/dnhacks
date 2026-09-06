"""Save the unmodified first page of the named comparison paper for the reveal."""
import os
import urllib.request
from pathlib import Path
import fitz
out = Path(os.environ.get("CAPTURE_OUTPUT", Path(__file__).resolve().parents[1] / "public/capture"))
out.mkdir(parents=True, exist_ok=True)
pdf = out / "held-out-paper.pdf"
if not pdf.exists():
    request = urllib.request.Request("https://link.springer.com/content/pdf/10.1186/s12964-026-02865-5.pdf", headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=90) as response:
        pdf.write_bytes(response.read())
with fitz.open(pdf) as document:
    document[0].get_pixmap(matrix=fitz.Matrix(1.7, 1.7)).save(out / "held-out-paper.png")
