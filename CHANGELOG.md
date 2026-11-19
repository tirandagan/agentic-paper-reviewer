# Changelog

## 0.1.0

First release.

- `paper-review` skill: a 10-stage agentic review pipeline following the one
  published at https://paperreview.ai/tech-overview (Jiang & Ng, Stanford ML
  Group). It ingests the full PDF, analyzes the paper, searches arXiv, selects
  and summarizes related work, writes an ICLR-style review with a grounding
  gate and a critic pass, and scores 7 dimensions into a 1-10 overall score.
- Scoring: anchored dimension scores, documented weights, then a rescale onto
  the human ICLR scale (`overall = clamp(-2.71 + 1.81 * raw, 1, 10)`), fitted
  on 14 blinded ICLR 2025 papers. The scores JSON keeps both `overall_raw`
  and `overall`. The calibration guidance checks for under-scoring as well as
  over-scoring, after a first run showed scores about 1.4 points low.
- `related-paper-summarizer` agent for focus-guided summaries of related
  papers. It returns its summary as its reply; the skill saves it.
- `arxiv_search.py`:
  - AND-joined query terms; arXiv's `all:(a b c)` form returns mostly
    unrelated papers. Falls back to fewer terms when too little comes back.
  - A literature cutoff (`--before`), which also makes `fetch` download each
    paper's first version, and self-exclusion (`--exclude`).
  - A machine-wide rate limiter: one arXiv request at a time, 3 seconds
    apart, with a shared back-off on HTTP 429 and 5xx, so parallel reviews
    don't get the machine blocked.
  - `fetch` skips a PDF that fails to download and continues with the rest.
- `pdf_to_text.py` falls back to poppler's `pdftotext` when pypdf is not
  installed.
- Query guidance: spell out acronyms and quote multi-word terms.
- Venue rule: the overall score is labelled an "ICLR-calibrated estimate" for
  venues that are not ICLR-like, as the original shows a score only for ICLR.
- `calibration/`:
  - A stratified ICLR 2025 sampler: OpenReview, blinded PDFs.
  - An analysis script that compares results with the paperreview.ai
    calibration plot, refuses runs that retrieved no literature, and fits or
    applies the rescale (`--fit-rescale`, `--rescale`).
  - Two 14-paper calibration runs and the report.
