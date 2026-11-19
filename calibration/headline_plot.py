#!/usr/bin/env python3
"""Draw calibration/headline.png, the summary figure shown in the README.

Left: the paperreview.ai calibration curve (share of papers the AI scored
5.5 or less, by average human rating) next to this plugin's run 2, after the
rescale (leave-one-out) and before it (raw).

Right: ranking quality - Spearman correlation with the human average and AUC
for accepted vs. not - for paperreview.ai (as published, no interval given)
and for each run of this plugin, with bootstrap 95% intervals.

Usage:
  python3 calibration/headline_plot.py            # reads run1/ and run2/ results.csv
"""
import csv
import pathlib
import random

import analyze

HERE = pathlib.Path(__file__).resolve().parent
BLUE, ORANGE = "#2a78d6", "#eb6834"          # validated pair (dataviz reference palette)
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"


def rows(path):
    out = []
    for r in csv.DictReader(open(path, encoding="utf-8")):
        out.append({"band": int(r["band"]), "human": float(r["human_avg"]),
                    "raw": float(r["ai_overall"]),
                    "rescaled": float(r["ai_rescaled"]) if r.get("ai_rescaled") else None,
                    "acc": r["decision"] in analyze.ACCEPTED})
    return out


def shares(rs, key):
    pts = []
    for b, (centre, _, _) in enumerate(analyze.THEIRS):
        rb = [r for r in rs if r["band"] == b]
        if rb:
            pts.append((centre, 100.0 * sum(r[key] <= 5.5 for r in rb) / len(rb)))
    return pts


def boot(rs, stat, n=4000, seed=7):
    rng = random.Random(seed)
    vals = []
    for _ in range(n):
        s = [rs[rng.randrange(len(rs))] for _ in rs]
        v = stat(s)
        if v == v:
            vals.append(v)
    vals.sort()
    return vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals)) - 1]


def rho(rs):
    return analyze.spearman([r["raw"] for r in rs], [r["human"] for r in rs])


def auc(rs):
    return analyze.auc([r["raw"] for r in rs], [r["acc"] for r in rs])


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    r1, r2 = rows(HERE / "run1/results.csv"), rows(HERE / "run2/results.csv")
    plt.rcParams.update({"font.size": 10, "axes.edgecolor": INK2, "axes.labelcolor": INK2,
                         "xtick.color": INK2, "ytick.color": INK2, "text.color": INK})
    fig, (a, b) = plt.subplots(1, 2, figsize=(12.5, 5.0), facecolor=SURFACE,
                               gridspec_kw={"width_ratios": [1.15, 1], "wspace": 0.32})
    for ax in (a, b):
        ax.set_facecolor(SURFACE)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)

    # Left: the calibration curve.
    theirs = [(c, p * 100) for c, _, p in analyze.THEIRS]
    ours = shares(r2, "rescaled")
    raw = shares(r2, "raw")
    a.plot(*zip(*raw), ":", color=INK2, lw=1.5, marker="o", ms=4, mfc=SURFACE, zorder=2)
    a.plot(*zip(*theirs), "-", color=ORANGE, lw=2, marker="o", ms=8, mec=SURFACE, mew=2, zorder=3)
    a.plot(*zip(*ours), "-", color=BLUE, lw=2, marker="D", ms=8, mec=SURFACE, mew=2, zorder=4)
    a.annotate("paperreview.ai\n(147 papers)", theirs[2], xytext=(8, 10),
               textcoords="offset points", fontsize=9, color=INK)
    a.annotate("This plugin\n(14 papers, rescaled)", ours[1], xytext=(-4, -36),
               textcoords="offset points", fontsize=9, color=INK, ha="center")
    a.text(5.3, 104, "this plugin before rescale", fontsize=8, color=INK2, ha="center",
           va="bottom")
    a.set_xlim(2.6, 8.9)
    a.set_ylim(-4, 112)
    a.set_yticks([0, 25, 50, 75, 100])
    a.set_yticklabels(["0%", "25%", "50%", "75%", "100%"])
    a.grid(axis="y", color=GRID, lw=0.8)
    a.set_axisbelow(True)
    a.set_xlabel("Average human reviewer rating, ICLR 2025")
    a.set_ylabel("Papers the AI scored 5.5 or less")
    a.set_title("Calibration: scores fall as human ratings rise", loc="left",
                fontsize=11, color=INK, pad=10)

    # Right: ranking quality, dot-and-whisker.
    items = [("paperreview.ai", 0.42, None, 0.75, None, ORANGE),
             ("This plugin, run 1", rho(r1), boot(r1, rho), auc(r1), boot(r1, auc), BLUE),
             ("This plugin, run 2", rho(r2), boot(r2, rho), auc(r2), boot(r2, auc), BLUE)]
    groups = [("Rank agreement with\nhuman reviewers (Spearman)", 1, 0.41, "human vs. human 0.41"),
              ("Separating accepted from\nrejected papers (AUC)", 3, 0.84, "one human 0.84")]
    for gi, (gname, idx, ref, reflab) in enumerate(groups):
        base = (1 - gi) * 4.8
        for k, it in enumerate(items):
            y = base + (2 - k) * 1.0
            v, ci = it[idx], it[idx + 1]
            if ci:
                b.plot(ci, [y, y], color=it[5], lw=2, solid_capstyle="round", alpha=0.45)
            b.plot([v], [y], "o" if it[0] == "paperreview.ai" else "D", color=it[5], ms=9,
                   mec=SURFACE, mew=2, zorder=3)
            b.annotate("%.2f" % v, (v, y), xytext=(0, 9), textcoords="offset points",
                       ha="center", fontsize=8.5, color=INK)
            b.text(-0.03, y, it[0], ha="right", va="center", fontsize=9, color=INK)
        b.plot([ref, ref], [base - 0.5, base + 2.5], "--", color=INK2, lw=1)
        b.text(ref, base - 0.75, reflab, ha="center", va="top", fontsize=8, color=INK2)
        b.text(-0.03, base + 2.7, gname, ha="right", va="bottom", fontsize=9.5,
               color=INK, fontweight="bold")
    b.set_xlim(0, 1.02)
    b.set_ylim(-1.3, 9.0)
    b.set_yticks([])
    b.spines["left"].set_visible(False)
    b.grid(axis="x", color=GRID, lw=0.8)
    b.set_axisbelow(True)
    b.set_xlabel("Higher is better · bars: 95% bootstrap interval")
    b.set_title("Ranking quality", loc="left", fontsize=11, color=INK, pad=10)

    fig.text(0.01, 0.005, "Blinded ICLR 2025 submissions, 2 per human-rating bin; literature "
             "cutoff 2024-10-01. Rescaled points are leave-one-out. paperreview.ai values from "
             "paperreview.ai/tech-overview.", fontsize=7.5, color=INK2)
    fig.subplots_adjust(left=0.07, right=0.98, top=0.9, bottom=0.14)
    out = HERE / "headline.png"
    fig.savefig(out, dpi=160, facecolor=SURFACE)
    print(out)


if __name__ == "__main__":
    main()
