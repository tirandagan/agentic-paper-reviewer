# User guide: Agentic Research Paper Reviewer

[Back to README](../README.md)

## Contents

- [Install](#install)
- [Run a review](#run-a-review)
- [What you get](#what-you-get)
- [Reading the score](#reading-the-score)
- [Getting the most out of it](#getting-the-most-out-of-it)
- [Recalibrating against your own venue](#recalibrating-against-your-own-venue)
- [Troubleshooting](#troubleshooting)
- [Privacy](#privacy)

## Install

In Claude Code (2.1.275 or later):

```
/plugin install agentic-paper-reviewer --marketplace tirandagan/agentic-paper-reviewer
```

On older versions:

```
/plugin marketplace add tirandagan/agentic-paper-reviewer
/plugin install agentic-paper-reviewer@tirandagan-paper-reviewer
```

Or from a clone, for one session:

```bash
git clone https://github.com/tirandagan/agentic-paper-reviewer.git ~/.claude-plugins/agentic-paper-reviewer
claude --plugin-dir ~/.claude-plugins/agentic-paper-reviewer
```

Requirements: `python3` (3.8 or later; standard library only) and internet
access to `export.arxiv.org` and `arxiv.org`. No API keys. Claude Code reads
PDFs natively when poppler (`pdftoppm`) is installed; without it the skill
falls back to text extraction with `pypdf` (`python3 -m pip install pypdf`)
and says in the review that figures could not be checked.

## Run a review

Ask in plain language, or call the skill directly:

```
/agentic-paper-reviewer:paper-review ~/drafts/my-paper.pdf
/agentic-paper-reviewer:paper-review 2410.06215 NeurIPS
/agentic-paper-reviewer:paper-review ~/drafts/my-paper.pdf ICLR cutoff 2025-09-20
```

Plain-language versions work too:

- "Review my paper draft at ~/drafts/my-paper.pdf before I submit it to ICLR."
- "Referee arXiv 2410.06215. Is the novelty claim defensible?"
- "What would reviewers attack first in main.tex?"

| Input | What it does | Default |
|---|---|---|
| Paper | A local PDF, an arXiv ID or URL, or LaTeX/Markdown source | (required) |
| Venue | Target venue; sets the review conventions and whether the overall score is ICLR-calibrated | ICLR |
| Literature cutoff | Only arXiv papers submitted on or before this date count as prior work | none |
| Output | Where to write the review | `<paper>-review.md` next to the paper |

A review takes roughly 10 to 25 minutes. Most of that time is reading the
paper and the 3 to 5 closest related papers in full. arXiv asks clients to
wait 3 seconds between requests, and the search script follows that.

## What you get

Two files next to your paper:

- **`<paper>-review.md`**, a referee report in the section order of the
  paperreview.ai review viewer:
  - Summary
  - Strengths
  - Weaknesses (tagged major or minor)
  - Detailed Comments, with fixed subsections for novelty and relation to
    prior work, method and soundness, experiments and evidence, and clarity
  - Questions for Authors
  - Overall Assessment: the 7-dimension score table and a verdict
  - Related Work Consulted: every arXiv paper used, which is the audit trail
- **`<paper>-review.scores.json`**: the 7 dimension scores, the raw and the
  overall score, and the arXiv IDs consulted, for scripts and tracking
  across revisions.

Every weakness cites either a place in your paper (section or page plus a
short quote) or a related paper by arXiv ID. A point the reviewer could not
ground is marked "Unverified impression" rather than stated as fact.

## Reading the score

Each of the 7 dimensions is scored 1 to 10 against fixed anchors; on the
anchors, 5 means a median ICLR submission, which is rejected. The dimension
scores are combined with fixed weights into a **raw** score. A rescale
fitted on human ICLR 2025 ratings, `−2.71 + 1.81 × raw`, then turns it into
the **overall** score, so that the overall reads on the human reviewers'
scale. The review table shows both; read the overall.

Why the rescale: the raw scores rank papers well but run about a point low
and bunch up. Raw 5.0 corresponds to about 6.3 on the human scale, and raw
5.5 to about 7.2. See the [calibration report](../calibration/REPORT.md).

| Overall | At an ICLR-like venue |
|---|---|
| 3 or below | Strong reject territory |
| 4 to 5 | Below the bar |
| 5.5 to 6.5 | Borderline |
| 7 or above | Likely accept territory |
| 8 or above | Rare (top ~10%) |

Treat it as an estimate with about ±1.5 points of uncertainty. Human
reviewers of the same paper disagree by at least that much: ICLR reviewers
correlate with each other at only 0.41 (Spearman). The weights are
documented defaults and the rescale was fitted on 14 papers, not a
regression fitted on 150 like the original's. On those papers the overall
score ranked papers about as well as paperreview.ai reports for itself
(Spearman 0.74). Its average error was 1.15 points, and single papers
missed by up to about 3.

For venues that are not ICLR-like, the overall row is labelled
"ICLR-calibrated estimate". Read the dimension scores and the written
weaknesses first. The original paperreview.ai shows no score at all for
other venues.

The written review is worth more than the number. The most useful parts are
usually the major weaknesses, the novelty comparison against named related
papers, and the questions the reviewer could not answer from your text.

## Getting the most out of it

- **Use a literature cutoff when it matters.** To see how a paper looked on
  its submission date, pass that date as the cutoff. Otherwise newer papers
  that build on your work may show up as "prior work".
- **Give it the full PDF, appendices included.** Unlike the original, which
  reads the first 15 pages, this plugin reads everything. Evidence in an
  appendix counts.
- **Run it twice for an important submission.** One pass is one reviewer.
  Research on LLM reviewing (ReviewerToo, The AI Scientist) finds that
  combining several independent reviews is more reliable. Run the skill two
  or three times, then ask Claude for a meta-review that reconciles the runs.
- **Fix, then re-review.** Compare the scores JSON across revisions to see
  which dimensions moved.
- **Outside machine learning:** grounding comes from arXiv, so the novelty
  check is strongest in fields that post preprints there (ML, physics, math,
  CS, quantitative biology). In other fields, treat the novelty section as
  provisional.

## Recalibrating against your own venue

The `calibration/` folder in the repository holds what was used to check
this plugin against paperreview.ai's calibration plot:

1. `sample_iclr2025.py` draws a stratified sample of ICLR 2025 submissions
   from the public [Paper Copilot](https://github.com/papercopilot/paperlists)
   list. It checks each paper's ratings against OpenReview and downloads the
   earliest "Under review" PDF revision, so the camera-ready header cannot
   reveal the decision. It needs an OpenReview account: set
   `OPENREVIEW_USERNAME` and `OPENREVIEW_PASSWORD` in the environment, or
   pass `--env FILE`.
2. Run the skill on each `paper_NN.pdf` with venue ICLR and a literature
   cutoff of the submission deadline (2024-10-01 for ICLR 2025), so each
   review writes its `.scores.json`.
3. `analyze.py` joins the scores with the human ratings. It reports the
   per-band share of AI scores ≤ 5.5 next to paperreview.ai's values, the
   Spearman correlation, the score inflation and the AUC, and draws
   `plot.png`. It always uses the raw score (`overall_raw`).
   - `--fit-rescale` fits a new rescale on your papers and reports its
     leave-one-out error. Put the printed coefficients in
     `skills/paper-review/references/scoring.md`.
   - `--rescale=A,B` tests fixed coefficients, such as the shipped
     `--rescale=-2.71,1.81`, on a fresh set of papers.

   Re-fit the rescale whenever you change the scoring anchors, weights or
   calibration guidance.

With 100 or more papers you can fit your own weights. Regress the average
human score on the 7 dimensions using half the papers, validate on the other
half, and replace the weights in `skills/paper-review/references/scoring.md`.
That reproduces the original's method.

## Troubleshooting

| Symptom | Fix |
|---|---|
| "request failed after 4 attempts" from the search script | arXiv is rate-limiting or down. Wait a few minutes and ask Claude to continue from Stage 4. The review can still be written, but the novelty assessment is then marked as not literature-grounded |
| A search returns nothing relevant | Queries work best as 2 to 5 key terms with technical names in double quotes. The script already drops trailing terms when a query is too narrow |
| "pypdf not installed" | Only needed when native PDF reading fails: `python3 -m pip install pypdf` |
| The review cites your own arXiv preprint as prior work | Give the arXiv ID so the skill can pass `--exclude`, or set a literature cutoff |
| Claude asks to approve Python commands | The skill pre-approves its own two scripts. Other commands, such as the PDF fallback through `pdftotext`, may still ask |

## Privacy

This plugin never uploads your paper anywhere. Claude reads it
inside your Claude Code session, under your normal Claude data settings. The
only network traffic the plugin adds goes to arXiv: the search queries Claude
writes (a few technical terms each) and downloads of related arXiv papers.
Nothing is sent to paperreview.ai, OpenReview, or any other service. The
calibration scripts contact OpenReview only when you run them.
