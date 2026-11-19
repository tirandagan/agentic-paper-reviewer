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
- **5** — Median ICLR submission. Competent but unremarkable.
- **6** — Above the typical bar for this dimension. A paper whose claims
  hold up and whose experiments are adequate for those claims scores 6 or
  more on claims-supported and soundness, even with fixable gaps.
- **8** — Clearly strong; top ~15% of submissions.
- **10** — Exceptional; you can defend "best of the year" for this dimension.

## Overall score

Two steps: a weighted sum of the dimensions (the raw score), then a fixed
rescale onto the ICLR human-rating scale.

```
raw     = 0.15·d1 + 0.15·d2 + 0.20·d3 + 0.20·d4 + 0.05·d5 + 0.15·d6 + 0.10·d7
overall = clamp(−2.71 + 1.81 · raw, 1, 10)
```

Round each to one decimal (compute `overall` from the unrounded raw). Report
`overall` as the score; keep `raw` alongside it in the scores JSON.

- **Weights.** They favor claims-support and soundness, the dimensions human
  overall scores track most closely. They are documented defaults, standing
  in for the original's fitted regression, whose coefficients are not public.
- **Rescale.** Raw scores rank papers well but run low and bunch up between
  3.5 and 6. On 14 ICLR 2025 papers the raw score averaged 1.1 points below
  the human average. The rescale (fitted human average ≈ a + b · raw)
  corrects that.
  - Fitted on calibration run 2: 14 ICLR 2025 papers, scoring guidance as of
    v0.1.0.
  - Checked by leaving one paper out at a time:
    - Mean error went from 1.28 to 1.15 points.
    - The average gap went from −1.08 to 0.00.
    - It keeps the rank order, so it cannot change how well papers are ranked.
  - **Re-fit it after any change to the anchors, the weights or the
    calibration section below**, using `calibration/analyze.py --fit-rescale`.
    The coefficients belong to this exact guidance.
  - A slope near 2 means one point on one dimension moves `overall` by up to
    about 0.4. This is one more reason to treat the score as ±1.5.

Worked example: d = (5, 6, 6, 5, 6, 6, 4) gives raw 5.45 and overall
−2.71 + 1.81 × 5.45 = 7.15, reported as raw 5.5 and overall 7.2.

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

## Calibration (read before finalizing)

Score drift runs both ways. Published evaluations of GPT-4-era reviewers
found inflation of 1–2 points. This plugin's own check on 14 ICLR 2025
papers found the opposite with Claude and stricter rules: scores ran about
1.4 points *low*, with accepted and even Oral papers scored 3–4 on
claims-supported and soundness (see `calibration/` in the repository). Never
adjust dimension scores to hit a target overall. So:

1. Score each dimension from the anchors above, not from overall sentiment
   and not from the length of your weakness list. Every paper has
   weaknesses, and accepted papers get long weakness lists from human
   reviewers too. Ask how serious each one is: does it break the main claim
   (pulls the dimension to 4 or below), or is it a gap a revision can fill
   (keeps it at 5–6 if the core evidence holds)?
2. Check both directions. After computing the raw score (before the
   rescale), ask "Would a careful
   human reviewer at this venue score it higher or lower?" Credit what the
   paper demonstrably delivers (new capability, strong results, a useful
   artifact) as firmly as you mark what it lacks.
3. Interpretation of the (rescaled) overall for ICLR-like venues: ≤3
   strong reject territory; 4–5 reject, below bar; 5.5–6.5 borderline; ≥7
   likely accept territory; ≥8 rare (top ~10%). Any score of 8 or more on a
   dimension needs a grounded reason, like every other score.
4. Report the score with its caveat: default weights and a rescale fitted
   on 14 papers, not the original's regression on 150; ±1.5 uncertainty;
   calibrated only for ICLR-style ML venues.

## Recalibrating (optional, for the user)

To reproduce the original's method: collect N≥100 papers with known average
human scores (e.g., ICLR via OpenReview), run this skill's 7-dimension
scoring on each, fit `human_avg ~ linear(d1..d7)` on half, validate Spearman
and calibration on the rest, then replace the weights above with the fitted
coefficients and intercept. A full regression replaces both steps: set the
rescale to a = 0, b = 1.
