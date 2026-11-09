#!/usr/bin/env python3
"""Rebuild docs/media/product-tour.gif from captured PNG screenshots."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "media"
# Prefer value-forward scenes for the animated tour.
NAMES = [
    "01-home.png",
    "02-l1-overview.png",
    "04-l2-overview.png",
    "06-l3-overview.png",
    "07-l3-risks.png",
    "08-decisions.png",
]


def main() -> None:
    frames = []
    for name in NAMES:
        path = OUT / name
        if not path.exists():
            raise SystemExit(f"missing {path} — run scripts/capture_readme_media.mjs first")
        im = Image.open(path).convert("RGB").resize((960, 600), Image.Resampling.LANCZOS)
        frames.append(im.quantize(colors=128, method=Image.Quantize.MEDIANCUT))
    gif = OUT / "product-tour.gif"
    frames[0].save(
        gif,
        save_all=True,
        append_images=frames[1:],
        duration=2200,
        loop=0,
        optimize=True,
    )
    print(f"wrote {gif.relative_to(ROOT)} ({gif.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
