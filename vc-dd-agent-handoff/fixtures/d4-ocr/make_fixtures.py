"""Deterministic D4 fixtures: native, scanned, mixed, image-dominated, malformed, encrypted PDFs.
All text is synthetic. Output files are byte-stable across runs (reportlab invariant mode, fixed PNG encoding)."""
import hashlib, io, json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab import rl_config
rl_config.invariant = 1
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
import pypdf

OUT = Path(__file__).parent / "fixtures"; OUT.mkdir(exist_ok=True)
W, H = A4
LINES_A = ["Plinthwick Synthetic Analytics is a fictional company used for testing.",
           "Management accounts for the year ended 31 December 2025.",
           "Revenue 412,000 EUR. Cost of goods sold 118,650 EUR.",
           "Cash at 30 September 2026 was 2,240,000 EUR."]
LINES_B = ["Board minutes, synthetic test document.",
           "The board approved the 2027 budget on 14 October 2026.",
           "Customer count at quarter end was 37 paying customers.",
           "No penetration test was performed in the last twelve months."]

def font(size):
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans.ttf"]:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def scan_image(lines, noise=False):
    img = Image.new("L", (2480, 3508), 255)  # A4 at 300 dpi
    d = ImageDraw.Draw(img); f = font(48)
    for i, line in enumerate(lines):
        d.text((200, 300 + i * 110), line, fill=0, font=f)
    if noise:  # deterministic speckle
        import random; r = random.Random(7)
        for _ in range(4000):
            d.point((r.randrange(2480), r.randrange(3508)), fill=r.choice([0, 160]))
    buf = io.BytesIO(); img.save(buf, format="PNG", optimize=False); return buf.getvalue()

def pdf(pages):
    buf = io.BytesIO(); c = canvas.Canvas(buf, pagesize=A4, invariant=1)
    for kind, payload in pages:
        if kind == "text":
            y = H - 100
            for line in payload:
                c.drawString(72, y, line); y -= 20
        elif kind == "image":
            c.drawImage(ImageReader(io.BytesIO(payload)), 0, 0, width=W, height=H)
        elif kind == "long_caption+image":
            y = H - 40
            for line in ["Figure 2. Synthetic scanned board extract reproduced below for testing purposes only.",
                         "The image underneath carries the authoritative text of the minutes."]:
                c.drawString(72, y, line); y -= 16
            c.drawImage(ImageReader(io.BytesIO(payload)), 0, 0, width=W, height=H - 90)
        elif kind == "garbled+image":
            c.drawString(72, H - 40, "\ue000\ue001\ue002" * 30)
            c.drawImage(ImageReader(io.BytesIO(payload)), 0, 0, width=W, height=H - 60)
        elif kind == "garbled_only":
            y = H - 100
            for _ in range(4):
                c.drawString(72, y, "\ue000\ue001\ue002" * 25 + " ok"); y -= 20
        elif kind == "caption+image":
            c.drawString(72, H - 60, "Figure 1")
            c.drawImage(ImageReader(io.BytesIO(payload)), 0, 0, width=W, height=H - 90)
        c.showPage()
    c.save(); return buf.getvalue()

files = {
    "native.pdf": pdf([("text", LINES_A), ("text", LINES_B)]),
    "scanned.pdf": pdf([("image", scan_image(LINES_A)), ("image", scan_image(LINES_B))]),
    "mixed.pdf": pdf([("text", LINES_A), ("image", scan_image(LINES_B))]),
    "image_dominated.pdf": pdf([("caption+image", scan_image(LINES_B))]),
    "image_dominated_captioned.pdf": pdf([("long_caption+image", scan_image(LINES_B))]),
    "garbled_text_layer.pdf": pdf([("garbled+image", scan_image(LINES_A))]),
    "garbled_only.pdf": pdf([("garbled_only", None)]),
    "noisy_scan.pdf": pdf([("image", scan_image(LINES_A, noise=True))]),
}
files["malformed.pdf"] = files["native.pdf"][: len(files["native.pdf"]) // 3]
w = pypdf.PdfWriter(clone_from=pypdf.PdfReader(io.BytesIO(files["native.pdf"])))
w.encrypt("secret"); b = io.BytesIO(); w.write(b); files["encrypted.pdf"] = b.getvalue()

manifest = {"ground_truth": {"A": LINES_A, "B": LINES_B}, "files": {}}
for name, data in files.items():
    (OUT / name).write_bytes(data)
    manifest["files"][name] = hashlib.sha256(data).hexdigest()
(OUT / "manifest.json").write_text(json.dumps(manifest, indent=2))
print(json.dumps(manifest["files"], indent=1))
