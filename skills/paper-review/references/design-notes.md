# Design notes — provenance and research basis

Read this only to explain *why* the pipeline is built this way. It is not
needed to run a review.

## Source system

paperreview.ai, the "Stanford Agentic Reviewer", by Yixing Jiang and Andrew
Ng (Stanford ML Group); tech overview at https://paperreview.ai/tech-overview,
read 2026-11-17 and re-checked 2026-11-18. The authors thank Jonathan Chen,
Federico Bianchi, Jeremy Irvin and Yuhui Zhang for discussions and feedback,
and Abe Hou, Alan Li, Boyuan Liang, Chen Geng, Fateme Nateghi, Kameron Collin
Black, Livia Sun, Yuejun Shen and Yuming Shi for testing support. This plugin
is an independent re-implementation from that public description; it is not
affiliated with or endorsed by them. Their pipeline:

1. PDF → markdown via LandingAI Agentic Document Extraction.
2. Extract title; sanity-check the document is an academic paper.
3. LLM generates web-search queries at different specificity levels covering
   benchmarks/baselines, papers on the same problem, and related techniques.
4. Tavily search → relevant arXiv papers; download metadata
   (title/authors/abstract).
5. LLM scores relevance from metadata and selects the most relevant.
6. Per selected paper, the agent chooses: use the abstract as-is, or download
   the PDF, convert, and write a detailed summary guided by named "salient
   focus areas" — an explicit coverage-vs-context-length trade.
7. Final review generated from the paper markdown + related-work summaries,
   following a template. Described by the authors as "a basic agentic
   workflow" — no personas, no multi-pass debate.

Scoring: the LLM scores 7 dimensions; a linear regression (fit on 150 ICLR
2025 submissions, validated on 147 held out) maps them to a 1–10 score.
Held-out results: Spearman AI-vs-one-human 0.42 vs human-vs-human 0.41; AUC
for predicting acceptance 0.75 (AI) vs 0.84 (one human). Score shown only
for ICLR target venue. Review viewer sections: Summary / Strengths /
Weaknesses / Detailed Comments / Questions for Authors / Overall Assessment.

Not disclosed by the site, therefore designed locally: prompt texts, the
template wording, model names, search/selection N, chunking, regression
coefficients, severity scheme.

## Local adaptations

| Original | This skill | Note |
|---|---|---|
| LandingAI ADE PDF→markdown, first 15 pages, 10MB limit | Claude reads the whole PDF natively, appendices included | Upgrade: figures/tables are visible and appendix evidence counts |
| Tavily search API restricted to arXiv | arXiv API (`scripts/arxiv_search.py`), all query terms ANDed | Free, no key; same corpus the original grounds in. arXiv's `all:(a b c)` form returns mostly unrelated papers, so terms are ANDed with trailing-term fallback |
| (not described) | Optional literature cutoff (`--before`) and self-exclusion (`--exclude`) | Lets a paper be judged against the literature that existed when it was written |
| Async job + emailed token + web viewer | Synchronous session; review written to a Markdown file plus a scores JSON | |
| Unnamed hosted LLM | Claude in-session; parallel `related-paper-summarizer` subagents for full-text summaries | |
| Fitted ICLR regression; score shown only for ICLR | Documented default weights + anchors + anti-inflation rules; non-ICLR venues get an "ICLR-calibrated estimate" label | See `scoring.md`, incl. recalibration procedure and the plugin's `calibration/` harness |

## What each cited reference contributed

All 16 references on the tech-overview page were read (13 in full/part, 3
abstract-only where noted). Lessons actually wired into the skill are marked →.

1. **AgentReview** (arXiv:2406.12708) — peer-review *simulation*: reviewer
   biases shifted 37.1% of decisions; reviewers conform when they see each
   other's reviews. → Review generated independently, no simulated
   discussion; numeric score never the sole driver of the verdict.
2. **MARG** (arXiv:2401.04259) — multi-agent review generation; refinement
   pass cut generic comments from 60% to 29%; an "expert" that predicts the
   experiments a paper *should* contain is the mechanism that catches
   missing baselines; recall of real issues is the metric that matters.
   → Stage 2 expected-experiments diff; Stage 8 critic pass; major-over-minor.
3. **Liang et al.** (NEJM AI 1(8), AIoa2400196, 2024, doi:10.1056/AIoa2400196; preprint arXiv:2310.01783) — single-pass GPT-4
   feedback overlapped one human reviewer about as much as humans overlap
   each other (ICLR 39.2% vs 35.2%); 57.4% of 308 authors found it helpful;
   known skews: novelty raised ~10× less than humans, generic "add more
   datasets" advice, figures invisible, input truncated. → Full-paper
   reading, figure checks, anti-generic rules; the four-section review
   lineage the field (and the site) follows.
4. **Shin et al.** (arXiv:2502.17086) — facet-level audit of 8 LLMs:
   over-focus on validity/experiments; novelty-in-weaknesses F1 0.126 =
   the blind spot; recommends retrieval grounding for novelty. → Mandatory
   "Novelty and relation to prior work" subsection judged against retrieved
   papers by name; fixed facet subsections force coverage.
5. **ReviewerToo** (Sahu, Larochelle, Charlin, Pal; arXiv:2510.08867) — grounding gate: every judgment must
   cite a manuscript span or retrieved literature, rerun until it does;
   meta-review over a panel beat single reviewers (binary acc 81.8% vs
   83.9% avg human); venue reviewer-guidelines conditioning helps; rebuttal
   rounds *reduced* fidelity (sycophancy). → Stage 7 grounding gate; no
   rebuttal simulation; ICLR-style conventions as default.
6. **Thakkar et al.** (arXiv:2504.09737) — ICLR 2025 RCT (~19k reviews):
   actors → aggregator → critic → formatter, reliability tests with
   retry-then-drop, verbatim-quote requirement as the hallucination control;
   27% of reviewers updated vs 9% control; 89% blinded preference for
   post-feedback reviews. → Critic pass checklist; quote-grounding; drop
   rather than publish unverified comments.
7. **The Virtual Lab** (bioRxiv 2024.11.11.623004; abstract via API) — PI
   agent + specialist agents + critic agent, with wet-lab validation.
   Context citation; the recurring load-bearing critic role reinforces
   Stage 8.
8. **Si, Yang & Hashimoto 2024** (arXiv:2409.04109) — 79 expert blind
   reviewers: human novelty agreement is weak (56.1% balanced acc); LLM
   absolute scores poorly calibrated while pairwise ranking hit 71.4% on
   acceptance prediction; novelty must be judged against a literature
   cutoff via retrieval; their review form: anchored 1–10 scales +
   mandatory rationale. → Anchored dimension scores with written
   justification; retrieval-grounded novelty; ±1.5 uncertainty framing.
9. **Si, Hashimoto & Yang 2025** (arXiv:2506.20803) — executing the ideas
   erased the AI novelty advantage (gap ≈ −1 to −2 points); idea-level
   excitement does not predict execution outcomes. → Separate "appears
   novel" from "likely to hold up"; feasibility/effectiveness judgments
   flagged as text-only.
10. **Rizvi et al.** (bioRxiv 2025.04.14.648850; abstract via API) —
    C2S-Scale, 27B single-cell LLM. Context citation; no pipeline influence.
11. **AI co-scientist** (arXiv:2502.18864; abstract only — full text
    login-gated) — generate → critique → refine with tournament ranking
    under test-time compute. Echoed in the draft→critic structure.
12. **Wang et al., Nature 2023** (doi:10.1038/s41586-023-06221-2; abstract
    via Semantic Scholar) — AI-for-science survey. Context citation.
13. **The AI Scientist** (arXiv:2408.06292) — GPT-4o NeurIPS-form reviewer
    on 500 ICLR-2022 papers: balanced acc 0.65 vs human 0.66; reflection
    +2pts, one-shot +2pts, ensembling reduces variance only; inflation is
    model-dependent (decision threshold 6 for GPT-4o, 8 for Sonnet 3.5);
    "be critical and cautious" system framing. → Anti-inflation section of
    `scoring.md`; critical-reviewer stance.
14. **The AI Scientist-v2** (arXiv:2504.08066) — VLM figure/caption review
    and a code-vs-claims audit caught what text review missed (57%
    train/test overlap; experiments described but never run). → Check
    figures/tables against the claims made about them (native PDF vision
    makes this possible here); n=3 is anecdote, not calibration.
15. **Kosmos** (arXiv:2511.02824) — every report statement cites a paper or
    a notebook; measured accuracy differs by claim type (data 85.5%,
    literature 82.1%, interpretation 57.9%). → Per-claim provenance;
    interpretive claims get the most scrutiny; explicit "Unverified
    impression" marker instead of forced verdicts.
16. **Agent Laboratory** (arXiv:2501.04227) — reused the AI-Scientist
    reviewer in-loop; automated scores ran ~2.3 points above humans on
    generated papers. → Absolute scores treated as estimates; calibration
    caveat always attached. Its arXiv-API literature stage mirrors ours.

## Known limitations (inherited and local)

- arXiv grounding: novelty checking is weakest in fields that don't post
  preprints to arXiv (the original states the same).
- English-language papers only.
- Overall score uses uncalibrated default weights, not the original's
  fitted regression; read it ±1.5. `scoring.md` documents how to recalibrate.
- Single reviewer pass, like the original. Evidence (ReviewerToo, AI
  Scientist) says an ensemble + meta-review is better; a user who wants
  that can run the skill 2–3 times and ask for a meta-review of the runs.
- No rebuttal simulation, deliberately (it degraded fidelity in ReviewerToo
  and added little in AgentReview).
- Reviews may contain errors; built for authors improving their own work,
  not for outsourcing assigned conference reviews.
