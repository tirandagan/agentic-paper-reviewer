#!/usr/bin/env python3
"""Compare calibration runs with the paperreview.ai calibration plot.

Joins manifest.csv (human scores, from sample_iclr2025.py) with each run's
<paper>-review.scores.json, then reports:

- per-band proportion of AI overall scores <= 5.5, next to the values read off
  the paperreview.ai plot (https://paperreview.ai/static/plot.png)
- Spearman correlation of AI overall vs average human rating, with a
  bootstrap 95% interval (theirs: 0.42 on 147 held-out papers)
- mean AI minus human (score inflation) and mean absolute error
- AUC of the AI score for accepted (Poster/Spotlight/Oral) vs not

Runs whose scores JSON lists no related_work_ids (and no positive
related_count) are excluded: no literature means the arXiv search failed, so
the review's novelty judgment was not literature-grounded and its scores are
not comparable.

The raw score is the weighted sum of the 7 dimensions: "overall_raw" in the
scores JSON, or "overall" in files written before the rescale existed. Two
optional modes test the ICLR-scale rescale (human ~ a + b * raw, clamped to
1..10):

- --fit-rescale: fit a and b on these runs and report leave-one-out
  predictions (each paper predicted by a fit on the others), the honest error
  for a fit on so few papers. Prints the all-paper fit to put in scoring.md.
- --rescale=A,B: apply fixed coefficients (use the = form: the value
  starts with a minus sign) (e.g. to test a shipped fit on a
  fresh set of papers).

A straight-line rescale keeps the rank order, so Spearman and AUC do not
change; it moves the mean error, the bias and the per-band shares.

Writes results.csv, summary.json and plot.png to --out; prints a Markdown
summary. Standard library only, plus matplotlib for the plot (skipped with a
warning if matplotlib is missing).

Usage:
  python3 analyze.py --manifest DIR/manifest.csv --runs DIR/runs --out calibration/ [--fit-rescale]
"""
import argparse
import csv
import json
import pathlib
import random
import sys

# Read off the paperreview.ai calibration plot: bin centre, papers per bin,
# proportion of AI score <= 5.5. Bin edges match sample_iclr2025.BAND_EDGES.
THEIRS = [
    (2.97, 10, 0.90), (3.90, 38, 0.76), (4.83, 33, 0.55), (5.75, 33, 0.42),
    (6.68, 26, 0.19), (7.61, 6, 0.33), (8.54, 1, 0.00),
]
THEIR_SPEARMAN, THEIR_HUMAN_SPEARMAN, THEIR_AUC = 0.42, 0.41, 0.75
ACCEPTED = {"Poster", "Spotlight", "Oral"}
EXCLUDED = []
DIMS = ["originality", "importance", "claims_supported", "soundness",
        "clarity", "value", "contextualization"]


def ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def pearson(a, b):
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    va = sum((x - ma) ** 2 for x in a) ** 0.5
    vb = sum((y - mb) ** 2 for y in b) ** 0.5
    return cov / (va * vb) if va and vb else float("nan")


def spearman(a, b):
    return pearson(ranks(a), ranks(b))


def bootstrap_ci(a, b, stat, n=4000, seed=7):
    rng = random.Random(seed)
    vals = []
    for _ in range(n):
        idx = [rng.randrange(len(a)) for _ in a]
        v = stat([a[i] for i in idx], [b[i] for i in idx])
        if v == v:  # drop NaN (constant resample)
            vals.append(v)
    vals.sort()
    return vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals)) - 1]


def auc(scores, labels):
    pos = [s for s, l in zip(scores, labels) if l]
    neg = [s for s, l in zip(scores, labels) if not l]
    if not pos or not neg:
        return float("nan")
    wins = sum((p > q) + 0.5 * (p == q) for p in pos for q in neg)
    return wins / (len(pos) * len(neg))


def linfit(x, y):
    mx, my = sum(x) / len(x), sum(y) / len(y)
    sxx = sum((a - mx) ** 2 for a in x)
    b = sum((a - mx) * (c - my) for a, c in zip(x, y)) / sxx
    return my - b * mx, b


def clamp(v):
    return min(10.0, max(1.0, v))


def add_rescale(rows, fixed=None):
    """Add ai_rescaled to each row; return a summary of the rescale."""
    x = [r["ai_overall"] for r in rows]
    y = [r["human_avg"] for r in rows]
    info = {}
    if fixed:
        a, b = fixed
        for r in rows:
            r["ai_rescaled"] = round(clamp(a + b * r["ai_overall"]), 2)
        info.update(mode="fixed", a=a, b=b)
    else:
        folds = []
        for i, r in enumerate(rows):
            a, b = linfit(x[:i] + x[i + 1:], y[:i] + y[i + 1:])
            folds.append((a, b))
            r["ai_rescaled"] = round(clamp(a + b * r["ai_overall"]), 2)
        a, b = linfit(x, y)
        info.update(mode="leave-one-out", a=a, b=b,
                    fold_a_range=[min(f[0] for f in folds), max(f[0] for f in folds)],
                    fold_b_range=[min(f[1] for f in folds), max(f[1] for f in folds)])
    pr = [r["ai_rescaled"] for r in rows]
    info.update(
        mae_raw=sum(abs(p - h) for p, h in zip(x, y)) / len(rows),
        bias_raw=sum(p - h for p, h in zip(x, y)) / len(rows),
        mae=sum(abs(p - h) for p, h in zip(pr, y)) / len(rows),
        bias=sum(p - h for p, h in zip(pr, y)) / len(rows),
        share_le_5_5=sum(p <= 5.5 for p in pr) / len(rows),
        bands=[{"band": bd, "n": len(rb), "k_le_5_5": sum(r["ai_rescaled"] <= 5.5 for r in rb)}
               for bd in range(len(THEIRS)) for rb in [[r for r in rows if r["band"] == bd]]],
    )
    return info


def load(manifest, runs):
    rows = []
    for m in csv.DictReader(open(manifest, encoding="utf-8")):
        f = pathlib.Path(runs) / ("%s-review.scores.json" % m["paper"])
        if not f.exists():
            print("missing run: %s" % f.name, file=sys.stderr)
            continue
        s = json.load(open(f, encoding="utf-8"))
        ids = [i for i in (s.get("related_work_ids") or []) if str(i).strip()]
        if not ids and not s.get("related_count"):
            # No retrieved literature = the arXiv search failed; the novelty and
            # contextualization scores are not comparable, so the run is invalid.
            print("excluded (no related work retrieved): %s" % f.name, file=sys.stderr)
            EXCLUDED.append(m["paper"])
            continue
        row = {
            "paper": m["paper"], "openreview_id": m["openreview_id"], "title": m["title"],
            "band": int(m["band"]), "human_avg": float(m["human_avg"]),
            "human_ratings": m["human_ratings"], "decision": m["decision"],
            "pdf_revision": m.get("pdf_revision", ""),
            "ai_overall": float(s.get("overall_raw", s["overall"])),
        }
        for d in DIMS:
            row[d] = (s.get("dimensions") or {}).get(d, "")
        row["ai_le_5_5"] = int(row["ai_overall"] <= 5.5)
        rows.append(row)
    return rows


def summarize(rows):
    ai = [r["ai_overall"] for r in rows]
    hu = [r["human_avg"] for r in rows]
    acc = [r["decision"] in ACCEPTED for r in rows]
    bands = []
    for b, (centre, n_theirs, p_theirs) in enumerate(THEIRS):
        rb = [r for r in rows if r["band"] == b]
        k = sum(r["ai_le_5_5"] for r in rb)
        bands.append({"band": b, "centre": centre, "n": len(rb), "k_le_5_5": k,
                      "ours": (k / len(rb)) if rb else None, "theirs": p_theirs,
                      "n_theirs": n_theirs})
    rho = spearman(ai, hu)
    lo, hi = bootstrap_ci(ai, hu, spearman)
    return {
        "n": len(rows),
        "excluded_no_literature": list(EXCLUDED),
        "spearman": rho, "spearman_ci95": [lo, hi],
        "pearson": pearson(ai, hu),
        "mean_ai_minus_human": sum(a - h for a, h in zip(ai, hu)) / len(rows),
        "mae": sum(abs(a - h) for a, h in zip(ai, hu)) / len(rows),
        "auc_accept_ai": auc(ai, acc),
        "auc_accept_human_avg": auc(hu, acc),
        "share_le_5_5_ours": sum(r["ai_le_5_5"] for r in rows) / len(rows),
        "bands": bands,
        "theirs": {"spearman": THEIR_SPEARMAN, "human_human_spearman": THEIR_HUMAN_SPEARMAN,
                   "auc_accept_ai": THEIR_AUC, "n_test": 147},
    }


def band_shares(rows):
    out = []
    for b, (centre, _, _) in enumerate(THEIRS):
        rb = [r for r in rows if int(r["band"]) == b]
        if rb:
            out.append((centre, 100.0 * sum(float(r["ai_overall"]) <= 5.5 for r in rb) / len(rb)))
    return out


def plot(rows, summ, path, compare=None, compare_label="earlier run", label="this plugin"):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("warning: matplotlib not installed, plot skipped", file=sys.stderr)
        return
    fig, (ax, ax3) = plt.subplots(1, 2, figsize=(13, 6.4), gridspec_kw={"width_ratios": [1.25, 1]})
    centres = [t[0] for t in THEIRS]
    ax.bar(centres, [t[1] for t in THEIRS], width=0.92, color="#4C9BCB", alpha=0.35,
           label="paperreview.ai: papers per bin (n=147)")
    ax.set_xlabel("Average human rating (ICLR 2025)")
    ax.set_ylabel("Papers per bin (theirs)")
    ax2 = ax.twinx()
    ax2.plot(centres, [t[2] * 100 for t in THEIRS], "-o", color="#E69500",
             label="paperreview.ai: AI score <= 5.5")
    if compare:
        cb = band_shares(compare)
        ax2.plot([c for c, _ in cb], [v for _, v in cb], ":s", color="#888888", markersize=6,
                 label="%s: AI score <= 5.5 (n=%d)" % (compare_label, len(compare)))
    ob = [b for b in summ["bands"] if b["n"]]
    ax2.plot([b["centre"] for b in ob], [b["ours"] * 100 for b in ob], "--D", color="#B83280",
             markersize=8, label="%s: AI score <= 5.5 (n=%d)" % (label, summ["n"]))
    for b in ob:
        ax2.annotate("%d/%d" % (b["k_le_5_5"], b["n"]), (b["centre"], b["ours"] * 100),
                     textcoords="offset points", xytext=(6, 6), fontsize=8, color="#B83280")
    rs = summ.get("rescale")
    if rs:
        rb = [(THEIRS[b["band"]][0], 100.0 * b["k_le_5_5"] / b["n"]) for b in rs["bands"] if b["n"]]
        ax2.plot([c for c, _ in rb], [v for _, v in rb], "-^", color="#2E7D32", markersize=7,
                 label="%s, rescaled (%s): score <= 5.5" % (label, rs["mode"]))
    ax2.set_ylim(-5, 105)
    ax2.set_ylabel("Share of papers with AI score <= 5.5 (%)")
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax2.legend(h1 + h2, l1 + l2, loc="upper center", bbox_to_anchor=(0.5, -0.13),
               ncol=2, fontsize=8, frameon=False)
    ax.set_title("Calibration vs paperreview.ai")

    acc = [r["decision"] in ACCEPTED for r in rows]
    if compare:
        ax3.scatter([float(r["human_avg"]) for r in compare], [float(r["ai_overall"]) for r in compare],
                    facecolors="none", edgecolors="#999999", s=40, zorder=2, label=compare_label)
    ax3.scatter([r["human_avg"] for r in rows], [r["ai_overall"] for r in rows],
                c=["#2E8B57" if a else "#C0392B" for a in acc], s=45, zorder=3)
    if rs:
        ax3.scatter([r["human_avg"] for r in rows], [r["ai_rescaled"] for r in rows], marker="^",
                    facecolors="none", edgecolors=["#2E8B57" if a else "#C0392B" for a in acc],
                    s=55, zorder=3, label="rescaled (%s)" % rs["mode"])
    ax3.plot([1, 10], [1, 10], ":", color="grey", label="AI = human")
    ax3.axhline(5.5, color="#E69500", lw=1, label="5.5 threshold")
    ax3.set_xlim(2, 9.5)
    ax3.set_ylim(1, 10)
    ax3.set_xlabel("Average human rating")
    ax3.set_ylabel("AI score (dots: raw; triangles: rescaled)" if rs else "AI overall score (this plugin)")
    ax3.set_title("Per paper: Spearman %.2f (95%% CI %.2f to %.2f)" % (
        summ["spearman"], *summ["spearman_ci95"]), fontsize=10)
    ax3.scatter([], [], c="#2E8B57", label="accepted")
    ax3.scatter([], [], c="#C0392B", label="rejected / withdrawn")
    ax3.legend(fontsize=8, loc="upper left")
    fig.tight_layout()
    fig.savefig(path, dpi=150)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--runs", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", default="this plugin", help="legend label for this run")
    ap.add_argument("--compare", help="results.csv of an earlier run to draw alongside")
    ap.add_argument("--compare-label", default="earlier run")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--fit-rescale", action="store_true",
                   help="fit human ~ a + b*raw; report leave-one-out predictions")
    g.add_argument("--rescale", metavar="A,B", help="apply fixed rescale coefficients")
    args = ap.parse_args()
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = load(args.manifest, args.runs)
    if len(rows) < 3:
        sys.exit("error: need at least 3 completed runs, have %d" % len(rows))
    summ = summarize(rows)
    if args.fit_rescale or args.rescale:
        fixed = tuple(float(v) for v in args.rescale.split(",")) if args.rescale else None
        summ["rescale"] = add_rescale(rows, fixed)
    with open(out / "results.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    json.dump(summ, open(out / "summary.json", "w"), indent=1)
    compare = list(csv.DictReader(open(args.compare, encoding="utf-8"))) if args.compare else None
    plot(rows, summ, out / "plot.png", compare, args.compare_label, args.label)

    print("| Band (human avg) | Theirs: AI <= 5.5 | Ours | n |")
    print("|---|---|---|---|")
    for b in summ["bands"]:
        ours = "%d/%d (%.0f%%)" % (b["k_le_5_5"], b["n"], 100 * b["ours"]) if b["n"] else "-"
        print("| ~%.1f | %.0f%% | %s | %d |" % (b["centre"], 100 * b["theirs"], ours, b["n"]))
    print()
    print("n=%d  Spearman %.2f (95%% CI %.2f to %.2f; theirs %.2f)  Pearson %.2f" % (
        summ["n"], summ["spearman"], summ["spearman_ci95"][0], summ["spearman_ci95"][1],
        THEIR_SPEARMAN, summ["pearson"]))
    print("mean AI-human %+.2f  MAE %.2f  AUC accept: AI %.2f (theirs %.2f), human avg %.2f" % (
        summ["mean_ai_minus_human"], summ["mae"], summ["auc_accept_ai"], THEIR_AUC,
        summ["auc_accept_human_avg"]))
    rs = summ.get("rescale")
    if rs:
        print()
        print("Rescale (%s): human ~ %.2f + %.2f * raw%s" % (
            rs["mode"], rs["a"], rs["b"],
            " (fit on all %d)" % summ["n"] if rs["mode"] != "fixed" else " (given)"))
        if "fold_a_range" in rs:
            print("  across folds: a %.2f to %.2f, b %.2f to %.2f" % (
                *rs["fold_a_range"], *rs["fold_b_range"]))
        print("  MAE %.2f -> %.2f   bias %+.2f -> %+.2f   share <= 5.5: %.0f%% -> %.0f%%" % (
            rs["mae_raw"], rs["mae"], rs["bias_raw"], rs["bias"],
            100 * summ["share_le_5_5_ours"], 100 * rs["share_le_5_5"]))
        print("| Band | Theirs: <= 5.5 | Ours raw | Ours rescaled |")
        print("|---|---|---|---|")
        for b, r in zip(summ["bands"], rs["bands"]):
            if b["n"]:
                print("| ~%.1f | %.0f%% | %d/%d | %d/%d |" % (
                    b["centre"], 100 * b["theirs"], b["k_le_5_5"], b["n"], r["k_le_5_5"], r["n"]))


if __name__ == "__main__":
    main()
