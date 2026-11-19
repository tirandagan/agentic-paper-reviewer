# Review output template

Produce a single Markdown file with exactly these sections, in this order
(matching the paperreview.ai review viewer). Guidance for each section is
below the skeleton — follow it, then delete nothing from the skeleton's
structure.

```markdown
# Review: <Paper title>

> AI-generated review (Agentic Research Paper Reviewer, following the
> paperreview.ai pipeline). May contain errors; use as guidance and apply
> your own judgment. Target venue: <venue>. Literature cutoff: <date or
> none>. Date: <YYYY-MM-DD>.

## Summary

<2 paragraphs max>

## Strengths

- **S1.** ...
- **S2.** ...

## Weaknesses

- **W1 (major).** ...
- **W2 (major).** ...
- **W3 (minor).** ...

## Detailed Comments

### Novelty and relation to prior work
...

### Method and soundness
...

### Experiments and evidence
...

### Clarity and presentation
...

## Questions for Authors

1. ...
2. ...

## Overall Assessment

| Dimension | Score (1–10) |
|---|---|
| Originality | |
| Importance of research question | |
| Claims supported by evidence | |
| Soundness of experiments | |
| Clarity of writing | |
| Value to the research community | |
| Contextualization vs. prior work | |
| Weighted sum of dimensions (raw) | x.x |
| **Overall (ICLR scale)** | **x.x / 10** |

<Verdict paragraph>

## Related Work Consulted

- arXiv:XXXX.XXXXX — <title> (<how it was used: abstract / full summary>)
...
```

## Section guidance

**Summary** — Neutral restatement of the problem, approach, and claimed
contributions, in your own words. No evaluation here. An author reading it
should say "yes, that is my paper." Getting this wrong poisons trust in
everything after it.

**Strengths** — 2–5 genuine strengths, each specific to this paper (cite the
section or result that demonstrates it). No bare praise ("well written",
"important area") without evidence attached.

**Weaknesses** — 3–7 items, ordered by severity, each tagged **(major)** or
**(minor)**. Major = could change the conclusions or the accept/reject
outcome; minor = should be fixed but not outcome-changing. Each weakness
must: (a) point at specific evidence — a quoted phrase + section/page, a
figure/table, or a named related work [arXiv:ID]; (b) say why it matters;
(c) say what would resolve it. One line each in this section; elaboration
belongs in Detailed Comments.

**Detailed Comments** — The four fixed subsections force facet coverage:

- *Novelty and relation to prior work*: name the 2–4 closest retrieved
  papers and state, per paper, what this submission adds beyond it. If a
  retrieved paper already does substantially the same thing, say so plainly
  with the ID. If the paper fails to cite a clearly relevant retrieved work,
  flag it. This subsection may never be empty or generic.
- *Method and soundness*: correctness of the formulation, hidden
  assumptions, failure modes, theoretical gaps.
- *Experiments and evidence*: run through the expected-experiments diff from
  Stage 2 — missing baselines, missing ablations, dataset or metric issues,
  claims stronger than the evidence (quote the claim, cite the table that
  falls short). Check figures against the claims made about them.
- *Clarity and presentation*: structural issues, undefined terms,
  figure/notation problems. Keep short; end with at most one line of nits.

**Questions for Authors** — 3–6 questions that are (a) answerable, (b)
material — the answer would change your assessment, and (c) not already
answered in the paper (re-check before including; asking an answered
question is the most embarrassing reviewer failure).

**Overall Assessment** — Fill the table per `scoring.md`: the raw weighted sum, then the overall score after the rescale. For a venue that is not ICLR-like, label the overall row "Overall (ICLR-calibrated estimate)" per the venue rule. The verdict
paragraph states the overall score, what primarily drove it (the 1–2
decisive dimensions), what would most improve the paper, and — for an
ICLR-style venue — where the score sits relative to the accept borderline
(≈6), with the calibration caveat from `scoring.md`.

**Related Work Consulted** — Every arXiv paper actually used, with how it
was used. This is the audit trail for the grounding gate; a reader must be
able to check every novelty claim against it.
