# Brag plan: Agentic Research Paper Reviewer

## Answers

- **What is it?** A Claude Code plugin that reads a research paper, searches arXiv for related work, and writes a grounded ICLR-style referee report with 7 scored dimensions.
- **Who is it for?** Authors who want detailed feedback on their own draft before they submit, not months after.
- **What sets it apart?** Every weakness has to cite a quote from the paper or an arXiv ID. A critic pass deletes generic comments. Scores were blind-tested against ICLR 2025 human ratings.
- **Most impressive claim:** a hand audit of a real review found 9/9 quotes verbatim and 11/11 arXiv IDs real.
- **Visual hook:** a paper sheet getting slammed with REJECTED stamps, counting up to 6.
- **Real UI and flow to show:** the install command → the review command → pipeline progress → the real `*-review.md` (W4 from the sample review) and its real score table → the calibration data.
- **Tone:** `polished`, warm and academic, with a little bite in the hook.
- **Share caption:** "Get the referee report before the referees do."

## Angle

The usual way to get feedback on a paper is to submit it and wait 6 months. This plugin gives you the review first, and it shows its work.

## Identity (from the icon and README)

- Navy `#1F2A44` background, paper cream `#F6F3EA`, orange `#E69A0F` (the magnifier), green `#2E8B57` (the check), slate `#9AA3B5` (text lines). Stamp red `#B8402F`, used only in the hook.
- Type: Source Serif 4 for headlines and review text (academic), Inter for UI, JetBrains Mono for the terminal. All loaded from local files in `work/fonts`.
- The real icon `icon.png`.

## Honesty constraints (carried into the build)

- Every number on screen comes from a real artifact:
  - Sample run: 11 related papers, 3 read in full, cutoff 2024-10-01, about 10 minutes, overall 4.3 and its 7 dimension scores (`calibration/sample-review.md`).
  - Audit: 9/9 and 11/11.
  - Run 2: Spearman 0.74, AUC 0.82, n = 14 (`calibration/run2/summary.json`). The scatter points come from `run2/results.csv`.
- There is no head-to-head "0.74 vs 0.42" comparison. The two measures differ, and the README says "comparable", not "better".
- The hook anecdote ("6 rejections, 3 years") is phrased generically. It comes from the paperreview.ai tech overview, not from this project.
- The credit line "Follows the paperreview.ai pipeline · independent, not affiliated" stays on screen for at least 2.4s. "Stanford" never appears in the video.
- Nothing from `plugin.json` (email) appears, and no calibration paper titles. The SFESS paper title is not shown; only the review text fragment is.

## Music

- 120 BPM: beat = 0.5s, bar = 2s. 25s = 50 beats = 750 frames at 30fps. Every cut lands on a beat.
- Key: D major. Progression D – Bm – G – A, one chord per bar.
- Hook: low drone, with stamp thuds on the beat grid. From the reveal (2.0s): soft kick, offbeat hats, a root-eighths bass and a pluck arpeggio. The outro rings out on D.
- SFX in key and on the grid:
  - stamp thuds on beats in the hook;
  - very soft key clicks on 16ths while typing;
  - soft chime notes (A5 / D6) on each ✓;
  - a gentle noise swell into each cut.

## Storyboard (25.0s)

| # | Time | Scene | On screen | Reading budget |
|---|---|---|---|---|
| 1 | 0.0–2.0 | **Hook** | Cream paper sheet. "REJECTED" stamps slam on each half-beat (6 of them), with a ×6 counter. Big serif line: **"6 rejections. 3 years."** | 4 words, settled from 0.5 to 1.95 = 1.45s ✓ |
| 2 | 2.0–4.0 | **Reveal** | Navy background. The icon pops in, then "Agentic Research Paper Reviewer" and below it **"Peer review, before you submit."** with a "Claude Code plugin" tag | Subline settled 2.35 to 3.95 = 1.6s for 5 words ✓ |
| 3 | 4.0–7.0 | **Install** | Step label "1 · Install". Terminal: `/plugin install agentic-paper-reviewer --marketplace tirandagan/agentic-paper-reviewer` typed from 4.2 to 5.3, then "✓ Installed". Chips: "python3 only · no API keys · no accounts" | Chips settled 4.6 to 6.95 = 2.3s ✓ |
| 4 | 7.0–11.0 | **Run** | "2 · Review your draft". Terminal: `/agentic-paper-reviewer:paper-review ~/drafts/my-paper.pdf ICLR`. Four ✓ steps, one per beat from 8.5: "Reads the whole PDF, figures included" · "Searches arXiv, cutoff 2024-10-01" · "Reads 11 related papers, 3 in full" · "Critic pass, then 7-dimension score". Chip: "≈ 10 min" | Steps accumulate; the last is held 1.0s+ ✓ |
| 5 | 11.0–15.0 | **Report** | "3 · Get a grounded report". Left: a `my-paper-review.md` card with a real W4 fragment: "W4 (major). The novelty claim (… p. 2) is overstated. SIMPLE [arXiv:2210.01941] already writes the exact conditional score …". An orange marker sweeps over "p. 2" and "[arXiv:2210.01941]". Right: the real 7-dimension score bars, Overall 4.3 / 10. Caption: **"Every weakness cites the paper or an arXiv ID."** | Caption settled 11.6 to 14.95 = 3.3s for 8 words ✓ |
| 6 | 15.0–18.0 | **Rigor: design** | **"Built against the known failures of LLM reviewers"**, plus 4 chips that get a ✓ one per beat: Novelty blind spot · Generic comments · Hallucinated citations · Score drift. Small footer: "16 studies behind the design" | Header settled 15.35 to 17.95 = 2.6s for 8 words ✓ |
| 7 | 18.0–21.5 | **Rigor: evidence** | Left: big "9/9" quotes found verbatim and "11/11" arXiv IDs real ("hand audit of a real review"). Right: animated scatter of the 14 run-2 papers, human average vs. plugin score, green = accepted, red = rejected. Caption: "Blind test · 14 ICLR 2025 papers · Spearman 0.74 · AUC 0.82" | Audit settled about 18.4 to 21.45 = 3s; caption settled 19.0 to 21.45 = 2.45s ✓ |
| 8 | 21.5–25.0 | **Outro** | Icon, then **"Feedback in one sitting, not one review cycle."** Pill: `/plugin install agentic-paper-reviewer` · github.com/tirandagan/agentic-paper-reviewer. Credit: "Follows the paperreview.ai pipeline · independent, not affiliated" | Tagline settled 21.85 to 25 = 3.1s; credit settled 22.2 to 25 = 2.8s ✓ |

Transitions: dip through navy, or a quick slide-up stagger (old out, then new in). No crossfades between busy layouts.
