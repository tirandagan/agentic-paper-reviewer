#!/usr/bin/env python3
"""PDF -> text fallback for when native PDF page reading is unavailable.

Uses pypdf if installed (python3 -m pip install pypdf), otherwise the
poppler `pdftotext` command if it is on PATH.

Usage:
    python3 pdf_to_text.py <input.pdf> [--out out.txt]

Output is page-delimited text ("--- page N ---" markers). Figures and table
layout are lost in this mode; the review must say so in its caveats.
"""
import argparse
import pathlib
import shutil
import subprocess
import sys


def pages_with_pypdf(path):
    from pypdf import PdfReader  # noqa: imported lazily so the fallback works without it
    return [page.extract_text() or "" for page in PdfReader(path).pages]


def pages_with_pdftotext(path):
    out = subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True,
                         text=True, timeout=300, check=True).stdout
    return out.split("\f")[:-1] if "\f" in out else [out]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--out", help="output .txt path (default: stdout)")
    args = ap.parse_args()

    try:
        pages = pages_with_pypdf(args.pdf)
    except ImportError:
        if not shutil.which("pdftotext"):
            sys.exit("error: neither pypdf nor pdftotext is available - "
                     "run: python3 -m pip install pypdf")
        pages = pages_with_pdftotext(args.pdf)

    text = "".join("\n--- page %d ---\n%s" % (i, p or "[no extractable text]")
                   for i, p in enumerate(pages, 1))
    if args.out:
        out = pathlib.Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print("%s (%d pages, %d chars)" % (out, len(pages), len(text)))
    else:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        print(text)


if __name__ == "__main__":
    main()
