#!/usr/bin/env python3
"""Draw a stratified ICLR 2025 calibration sample and download blinded PDFs.

Mirrors the paperreview.ai calibration set-up (ICLR 2025 submissions, average
human rating as ground truth) at small scale:

1. Read the Paper Copilot ICLR 2025 list (public; every submission with its
   reviewer ratings and decision). Downloaded if --paperlist is not given.
2. Keep submissions with at least one rating (withdrawn ones included, as in
   the original); drop desk rejects. Bin by average rating into the 7 bands of
   the paperreview.ai calibration plot.
3. Draw --per-band papers per band at random (--seed). For each, log in to
   OpenReview, re-read the ratings from the official reviews (they must match),
   and download the EARLIEST revision's PDF. The current PDF of an accepted
   paper is the camera-ready ("Published as a conference paper at ICLR 2025"),
   which would leak the outcome; page 1 must say "Under review" or the paper
   is redrawn.
4. Write <out>/paper_NN.pdf (neutral names) and <out>/manifest.csv. The
   reviewer runs see only the PDFs; the manifest is joined back afterwards.

Credentials: OPENREVIEW_USERNAME and OPENREVIEW_PASSWORD from the process
environment or from --env FILE (KEY=VALUE lines). They are never printed.

Usage:
  python3 sample_iclr2025.py --env ~/.env.local --out /tmp/calib --per-band 2 --seed 2025
"""
import argparse
import csv
import json
import os
import pathlib
import random
import subprocess
import sys
import time
import urllib.error
import urllib.request

PAPERLIST_URL = ("https://media.githubusercontent.com/media/papercopilot/"
                 "paperlists/main/iclr/iclr2025.json")
API = "https://api2.openreview.net"
UA = {"User-Agent": "agentic-paper-reviewer-calibration/0.1"}
# Bar edges of the paperreview.ai calibration plot (7 equal-width bins, read
# off https://paperreview.ai/static/plot.png).
BAND_EDGES = [2.5, 3.43, 4.36, 5.29, 6.21, 7.14, 8.07, 9.0]


def band_of(avg):
    for i in range(len(BAND_EDGES) - 1):
        last = i == len(BAND_EDGES) - 2
        if BAND_EDGES[i] <= avg < BAND_EDGES[i + 1] or (last and avg == BAND_EDGES[-1]):
            return i
    return None


def load_env(path):
    env = dict(os.environ)
    if path:
        for line in open(os.path.expanduser(path), encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    user, pw = env.get("OPENREVIEW_USERNAME"), env.get("OPENREVIEW_PASSWORD")
    if not user or not pw:
        sys.exit("error: OPENREVIEW_USERNAME / OPENREVIEW_PASSWORD not set")
    return user, pw


def call(path, token=None, data=None, raw=False):
    headers = dict(UA, **{"Content-Type": "application/json"})
    if token:
        headers["Authorization"] = "Bearer " + token
    body = json.dumps(data).encode() if data is not None else None
    for attempt in range(6):
        req = urllib.request.Request(API + path, data=body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                b = r.read()
                return b if raw else json.loads(b)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < 5:
                ra = e.headers.get("Retry-After") if e.headers else None
                delay = int(ra) + 5 if ra and ra.isdigit() else 30 * (attempt + 1)
                print("OpenReview HTTP %d; waiting %ds" % (e.code, delay), file=sys.stderr)
                time.sleep(delay)
                continue
            raise RuntimeError("OpenReview %s -> HTTP %s" % (path.split("?")[0], e.code))
    raise RuntimeError("OpenReview %s failed" % path)


def ratings_from_paperlist(row):
    try:
        return [float(x) for x in (row.get("rating") or "").split(";") if x.strip()]
    except ValueError:
        return []


def official_ratings(forum, token):
    notes = call("/notes?forum=%s" % forum, token)["notes"]
    out = []
    for n in notes:
        r = (n.get("content") or {}).get("rating")
        if r is not None:
            v = r.get("value") if isinstance(r, dict) else r
            out.append(float(str(v).split(":")[0]))
    return sorted(out)


def earliest_pdf(forum, token):
    """Return (pdf_bytes, revision_label). Earliest revision with a PDF, else current."""
    edits = call("/notes/edits?note.id=%s&sort=tcdate:asc" % forum, token).get("edits", [])
    for e in edits:
        content = (e.get("note") or {}).get("content") or {}
        if "pdf" in content:
            b = call("/notes/edits/attachment?id=%s&name=pdf" % e["id"], token, raw=True)
            when = time.strftime("%Y-%m-%d", time.gmtime(e["tcdate"] / 1000))
            return b, "%s %s" % (e["invitation"].split("/")[-1], when)
    return call("/pdf?id=%s" % forum, token, raw=True), "current (no revisions)"


def page1_text(pdf_path):
    try:
        return subprocess.run(["pdftotext", "-l", "1", str(pdf_path), "-"],
                              capture_output=True, text=True, timeout=60).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="directory for PDFs and manifest.csv")
    ap.add_argument("--env", help="KEY=VALUE file holding the OpenReview login")
    ap.add_argument("--paperlist", help="local copy of Paper Copilot iclr2025.json")
    ap.add_argument("--per-band", type=int, default=2)
    ap.add_argument("--seed", type=int, default=2025)
    ap.add_argument("--exclude-manifest", action="append", default=[], metavar="CSV",
                    help="skip papers listed in an earlier manifest.csv (repeatable), "
                         "e.g. to validate a change on fresh papers")
    ap.add_argument("--append", action="store_true",
                    help="keep an existing manifest.csv and only fill bands that are short")
    args = ap.parse_args()

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if args.paperlist:
        rows = json.load(open(args.paperlist, encoding="utf-8"))
    else:
        req = urllib.request.Request(PAPERLIST_URL, headers=UA)
        rows = json.loads(urllib.request.urlopen(req, timeout=300).read())

    bands = [[] for _ in range(len(BAND_EDGES) - 1)]
    for row in rows:
        if row.get("status") == "Desk Reject" or row.get("track", "main") != "main":
            continue
        r = ratings_from_paperlist(row)
        if not r:
            continue
        b = band_of(sum(r) / len(r))
        if b is not None:
            bands[b].append(row)
    print("eligible per band:", [len(b) for b in bands], file=sys.stderr)

    user, pw = load_env(args.env)
    token = call("/login", data={"id": user, "password": pw})["token"]
    rng = random.Random(args.seed)
    manifest, n = [], 0
    mpath = out / "manifest.csv"
    if args.append and mpath.exists():
        manifest = list(csv.DictReader(open(mpath, encoding="utf-8")))
        n = max(int(m["paper"].split("_")[1]) for m in manifest)
    taken = {m["openreview_id"] for m in manifest}
    for prior in args.exclude_manifest:
        taken |= {m["openreview_id"] for m in csv.DictReader(open(prior, encoding="utf-8"))}
    for bi, pool in enumerate(bands):
        rng.shuffle(pool)
        got = sum(1 for m in manifest if int(m["band"]) == bi)
        for row in pool:
            if got >= args.per_band:
                break
            forum = row["id"]
            if forum in taken:
                continue
            try:
                ratings = official_ratings(forum, token)
                listed = sorted(ratings_from_paperlist(row))
                if ratings != listed:
                    print("skip %s: ratings %s != list %s" % (forum, ratings, listed), file=sys.stderr)
                    continue
                pdf, rev = earliest_pdf(forum, token)
            except RuntimeError as exc:
                print("skip %s: %s" % (forum, exc), file=sys.stderr)
                continue
            if not pdf.startswith(b"%PDF"):
                print("skip %s: not a PDF" % forum, file=sys.stderr)
                continue
            n += 1
            path = out / ("paper_%02d.pdf" % n)
            path.write_bytes(pdf)
            head = page1_text(path)
            if "Published as" in head or "Under review" not in head:
                print("skip %s: page 1 lacks 'Under review' header" % forum, file=sys.stderr)
                path.unlink()
                n -= 1
                continue
            avg = sum(ratings) / len(ratings)
            manifest.append({
                "paper": path.stem, "openreview_id": forum, "title": row["title"],
                "band": bi, "human_ratings": ";".join("%g" % x for x in ratings),
                "human_avg": round(avg, 3), "decision": row.get("status", ""),
                "pdf_revision": rev,
            })
            got += 1
            print("band %d: %s avg %.2f %s [%s]" % (bi, path.stem, avg, row.get("status"), rev),
                  file=sys.stderr)
            time.sleep(1)
        if got < args.per_band:
            print("warning: band %d has only %d usable papers" % (bi, got), file=sys.stderr)

    manifest.sort(key=lambda m: m["paper"])
    with open(mpath, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(manifest[0].keys()))
        w.writeheader()
        w.writerows(manifest)
    print(mpath)


if __name__ == "__main__":
    main()
