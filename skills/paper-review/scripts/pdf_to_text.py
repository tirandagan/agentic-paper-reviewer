#!/usr/bin/env python3
"""PDF -> text fallback for machines where native PDF page rendering is
unavailable (no poppler). Uses pypdf (pure Python):
    python -m pip install pypdf

Usage:
    python pdf_to_text.py <input.pdf> [--out out.txt]

Output is page-delimited text ("--- page N ---" markers). Figures and table
layout are lost in this mode; the review must say so in its caveats.
"""
import argparse
import pathlib
import sys

try:
    from pypdf import PdfReader
except ImportError:
    sys.exit("error: pypdf not installed - run: python -m pip install pypdf")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--out", help="output .txt path (default: stdout)")
    args = ap.parse_args()

    reader = PdfReader(args.pdf)
    parts = []
    for i, page in enumerate(reader.pages, 1):
        parts.append(f"\n--- page {i} ---\n")
        parts.append(page.extract_text() or "[no extractable text]")
    text = "".join(parts)

    if args.out:
        out = pathlib.Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"{out} ({len(reader.pages)} pages, {len(text)} chars)")
    else:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        print(text)


if __name__ == "__main__":
    main()
