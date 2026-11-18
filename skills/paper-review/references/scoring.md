# Scoring

The original system has an LLM score 7 dimensions, then maps them to a final
1–10 with a linear regression fit on 150 ICLR 2025 submissions (held-out
Spearman vs. one human reviewer: 0.42, matching human–human at 0.41). The
regression coefficients are not public, so this skill uses documented default
weights (below). Treat the overall score as an estimate with roughly
±1.5-point uncertainty — human reviewers disagree with each other at least
that much.

## The 7 dimensions (score each 1–10)

Score every dimension independently, before computing the overall. Write one
grounded sentence of justification per dimension in your notes (not the
review) — a score you cannot justify gets re-examined.

| # | Dimension | What it measures |
|---|---|---|
| 1 | Originality | Novelty of problem, method, or findings **relative to the retrieved related work**, not to your general impression |
| 2 | Importance of research question | Does the problem matter to the field if solved |
| 3 | Claims supported | Are the paper's claims backed by its own evidence (quote-check the boldest claim) |
| 4 | Soundness of experiments | Baselines, ablations, statistics, datasets adequate for the claims |
| 5 | Clarity of writing | Can a competent reader reconstruct the method and follow the argument |
| 6 | Value to community | Would others build on, use, or cite this (artifacts, generality, insight) |
| 7 | Contextualization | Is prior work cited, compared, and positioned honestly (including works the search found that the paper missed) |

### Anchors (apply to every dimension)

- **2** — Seriously deficient; a reviewer would cite this dimension as a
  reason to reject on its own.
- **4** — Below the bar; clear, fixable problems.
- **5** — Median ICLR submission. Competent but unremarkable. **Most papers
  you review land at 4–6 on most dimensions.**
- **6** — Above the typical bar for this dimension.
- **8** — Clearly strong; top ~15% of submissions.
- **10** — Exceptional; you can defend "best of the year" for this dimension.

## Overall score

```
overall = 0.15·d1 + 0.15·d2 + 0.20·d3 + 0.20·d4 + 0.05·d5 + 0.15·d6 + 0.10·d7
```

Round to one decimal, clamp to [1, 10]. The weights favor
claims-support and soundness (the dimensions human overall scores track most
closely); they are uncalibrated defaults standing in for the original's
fitted regression.

## Venue rule

The original shows a numeric overall score only when the target venue is
ICLR, because its regression was fit on ICLR 2025 reviews. Follow the same
logic:

- **ICLR or a similar top ML conference** (NeurIPS, ICML, and the like):
  report the overall score in the table and the verdict as usual.
- **Any other venue**: still score all 7 dimensions, but label the overall
  row **"ICLR-calibrated estimate"** and say in the verdict that the number
  is not calibrated for this venue's bar; lead the verdict with the
  dimension-level judgments instead.

## Anti-inflation calibration (read before finalizing)

Every published evaluation of LLM reviewers finds systematic score
inflation of 1–2 points and a reluctance to use the bottom half of the
scale. Countermeasures, in order:

1. Score dimensions from the anchors above, not from overall sentiment. The
   anchor for 5 is "median submission — rejected."
2. After computing the overall, ask: "Would a critical, cautious human
   reviewer at this venue score it higher or lower?" If your dimension
   justifications contain any major weakness, an overall above 6 needs an
   explicit reason the weakness doesn't cap it.
3. Interpretation for ICLR-like venues: ≤3 strong reject territory; 4–5
   reject, below bar; 5.5–6.5 borderline; ≥7 likely accept territory; ≥8
   rare (top ~10%). If your score lands ≥7, re-verify the novelty and
   claims-support justifications against the retrieved related work before
   keeping it.
4. Report the score with its caveat: calibrated anchors, not a fitted
   regression; ±1.5 uncertainty; venue-calibrated only for ICLR-style ML
   venues.

## Recalibrating (optional, for the user)

To reproduce the original's method: collect N≥100 papers with known average
human scores (e.g., ICLR via OpenReview), run this skill's 7-dimension
scoring on each, fit `human_avg ~ linear(d1..d7)` on half, validate Spearman
and calibration on the rest, then replace the weights above with the fitted
coefficients and intercept.
