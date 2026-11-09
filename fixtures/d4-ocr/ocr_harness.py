"""D4 harness: native-first extraction with page-level local OCR fallback (Tesseract).

This is a test harness for the D4 specification (thresholds, fallback, provenance), NOT the product
implementation. It runs the specified algorithm on deterministic fixtures so the thresholds are checked
against real Tesseract output.
"""
from __future__ import annotations

import io
import time
from dataclasses import dataclass, field

import pdfplumber
import pypdf
import pypdfium2 as pdfium
import pytesseract

# ---- D4 defaults (mirrors the spec) ----
MIN_NATIVE_CHARS = 50          # fewer extractable chars than this -> page needs OCR
MAX_GARBAGE_RATIO = 0.10       # share of symbol/private-use/control/replacement chars -> garbled text layer
MIN_WORD_RATIO = 0.50          # share of whitespace tokens that look like words
IMAGE_COVERAGE_OCR = 0.60      # image-dominated page with little text -> OCR
IMAGE_PAGE_TEXT_CEILING = 200  # ...unless it already has this much native text
OCR_DPI = 300
OCR_MAX_PAGES = 200
OCR_PAGE_TIMEOUT_S = 60
OCR_LANGS = "eng"
LOW_CONFIDENCE = 60.0


class ParseFailed(Exception):
    code = "PARSE_FAILED"


class EncryptedDocument(Exception):
    code = "ENCRYPTED_DOCUMENT"


@dataclass
class PageResult:
    page: int                      # 1-based
    method: str                    # native_text | ocr | ocr_skipped_limit | ocr_failed
    reason: str
    text: str
    native_chars: int
    image_coverage: float
    ocr_engine: str | None = None
    ocr_language: str | None = None
    ocr_confidence: float | None = None
    low_confidence: bool = False
    seconds: float = 0.0


@dataclass
class DocResult:
    pages: list[PageResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


import re as _re
import unicodedata as _ud
_GARBAGE_CATS = {"So", "Co", "Cn", "Cs", "Cf"}


def garbage_ratio(s: str) -> float:
    """Share of non-space chars that indicate a broken text layer: symbols (e.g. U+25A0 boxes),
    private-use, unassigned, surrogates, format and control chars, U+FFFD, and '(cid:N)' runs."""
    s2 = _re.sub(r"\(cid:\d+\)", "\ufffd", s)
    chars = [c for c in s2 if not c.isspace()]
    if not chars:
        return 1.0
    bad = sum(1 for c in chars if c == "\ufffd" or _ud.category(c) in _GARBAGE_CATS
              or (_ud.category(c) == "Cc"))
    return bad / len(chars)


def word_ratio(s: str) -> float:
    toks = s.split()
    if not toks:
        return 0.0
    wordish = sum(1 for t in toks if _re.fullmatch(r"[\w.,;:%€$£()\-–/'’&]+", t) and _re.search(r"[A-Za-z0-9]", t))
    return wordish / len(toks)


def classify(native: str, image_coverage: float) -> tuple[bool, str]:
    n = len(native.strip())
    if n < MIN_NATIVE_CHARS:
        return True, f"native_chars<{MIN_NATIVE_CHARS}"
    if garbage_ratio(native) > MAX_GARBAGE_RATIO or word_ratio(native) < MIN_WORD_RATIO:
        return True, "garbled_text_layer"
    if image_coverage >= IMAGE_COVERAGE_OCR and n < IMAGE_PAGE_TEXT_CEILING:
        return True, "image_dominated"
    return False, "native_ok"


def extract(pdf_bytes: bytes, max_ocr_pages: int = OCR_MAX_PAGES, langs: str = OCR_LANGS) -> DocResult:
    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        if reader.is_encrypted:
            raise EncryptedDocument("password-protected PDF")
        n_pages = len(reader.pages)
    except EncryptedDocument:
        raise
    except Exception as e:  # malformed
        raise ParseFailed(str(e)[:200]) from e

    out = DocResult()
    ocr_used = 0
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as plumber:
        pdf = pdfium.PdfDocument(pdf_bytes)
        for i in range(n_pages):
            native = reader.pages[i].extract_text() or ""
            p = plumber.pages[i]
            area = float(p.width * p.height) or 1.0
            img_area = sum(float(im["width"]) * float(im["height"]) for im in p.images)
            cov = min(1.0, img_area / area)
            needs, reason = classify(native, cov)
            if not needs:
                out.pages.append(PageResult(i + 1, "native_text", reason, native, len(native.strip()), cov))
                continue
            if ocr_used >= max_ocr_pages:
                out.pages.append(PageResult(i + 1, "ocr_skipped_limit", reason, native, len(native.strip()), cov))
                out.warnings.append(f"page {i+1}: OCR page limit {max_ocr_pages} reached")
                continue
            t0 = time.monotonic()
            try:
                img = pdf[i].render(scale=OCR_DPI / 72).to_pil()
                data = pytesseract.image_to_data(img, lang=langs, config="--oem 1 --psm 3",
                                                 output_type=pytesseract.Output.DICT, timeout=OCR_PAGE_TIMEOUT_S)
            except RuntimeError as e:  # pytesseract timeout
                out.pages.append(PageResult(i + 1, "ocr_failed", f"timeout: {e}", native, len(native.strip()), cov))
                continue
            words = [(w, float(c)) for w, c in zip(data["text"], data["conf"]) if w.strip() and float(c) >= 0]
            text = " ".join(w for w, _ in words)
            conf = sum(c for _, c in words) / len(words) if words else 0.0
            ocr_used += 1
            out.pages.append(PageResult(i + 1, "ocr", reason, text, len(native.strip()), cov,
                                        ocr_engine=f"tesseract@{pytesseract.get_tesseract_version()}",
                                        ocr_language=langs, ocr_confidence=round(conf, 1),
                                        low_confidence=conf < LOW_CONFIDENCE, seconds=round(time.monotonic() - t0, 2)))
    return out
