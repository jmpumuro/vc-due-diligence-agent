"""D4 acceptance checks run against real Tesseract on the deterministic fixtures."""
import json, re
from pathlib import Path

import pytest
from rapidfuzz.distance import Levenshtein

import ocr_harness as H

FX = Path(__file__).parent / "fixtures"
GT = json.loads((FX / "manifest.json").read_text())["ground_truth"]
norm = lambda s: re.sub(r"\s+", " ", s).strip()
cer = lambda ref, hyp: Levenshtein.distance(norm(ref), norm(hyp)) / max(1, len(norm(ref)))
read = lambda n: (FX / n).read_bytes()


def test_native_pdf_uses_native_text_only():
    r = H.extract(read("native.pdf"))
    assert [p.method for p in r.pages] == ["native_text", "native_text"]
    assert all(p.ocr_engine is None for p in r.pages)


def test_scanned_pdf_falls_back_to_ocr_with_provenance():
    r = H.extract(read("scanned.pdf"))
    assert [p.method for p in r.pages] == ["ocr", "ocr"]
    for p, key in zip(r.pages, ["A", "B"]):
        assert p.reason.startswith("native_chars<")
        assert p.ocr_engine.startswith("tesseract@") and p.ocr_language == "eng"
        assert p.ocr_confidence >= 80, p.ocr_confidence
        assert cer(" ".join(GT[key]), p.text) <= 0.02, (cer(" ".join(GT[key]), p.text), p.text)


def test_mixed_pdf_ocr_only_where_needed():
    r = H.extract(read("mixed.pdf"))
    assert [p.method for p in r.pages] == ["native_text", "ocr"]
    assert [p.page for p in r.pages] == [1, 2]


def test_image_dominated_page_is_ocred():
    r = H.extract(read("image_dominated.pdf"))
    assert r.pages[0].method == "ocr"
    assert r.pages[0].reason in ("native_chars<50", "image_dominated")


def test_image_coverage_rule_triggers_ocr_despite_some_native_text():
    r = H.extract(read("image_dominated_captioned.pdf"))
    p = r.pages[0]
    assert 50 <= p.native_chars < 200 and p.image_coverage >= 0.6
    assert p.method == "ocr" and p.reason == "image_dominated"


def test_garbled_text_layer_triggers_ocr():
    r = H.extract(read("garbled_text_layer.pdf"))
    p = r.pages[0]
    assert p.method == "ocr", (p.reason, p.native_chars)
    assert p.reason in ("garbled_text_layer", "image_dominated")


def test_garbled_text_layer_rule_alone():
    r = H.extract(read("garbled_only.pdf"))
    p = r.pages[0]
    assert p.image_coverage == 0 and p.native_chars >= 50
    assert p.method == "ocr" and p.reason == "garbled_text_layer"


def test_noisy_scan_reports_confidence():
    r = H.extract(read("noisy_scan.pdf"))
    p = r.pages[0]
    assert p.method == "ocr" and p.ocr_confidence is not None
    assert p.low_confidence == (p.ocr_confidence < H.LOW_CONFIDENCE)


def test_page_limit_skips_and_warns():
    r = H.extract(read("scanned.pdf"), max_ocr_pages=1)
    assert [p.method for p in r.pages] == ["ocr", "ocr_skipped_limit"]
    assert r.warnings


def test_malformed_pdf_fails_closed():
    with pytest.raises(H.ParseFailed):
        H.extract(read("malformed.pdf"))


def test_encrypted_pdf_rejected():
    with pytest.raises(H.EncryptedDocument):
        H.extract(read("encrypted.pdf"))


def test_fixtures_are_deterministic():
    import hashlib, subprocess, sys
    before = json.loads((FX / "manifest.json").read_text())["files"]
    subprocess.run([sys.executable, str(Path(__file__).parent / "make_fixtures.py")], check=True, capture_output=True)
    after = json.loads((FX / "manifest.json").read_text())["files"]
    assert before == after
