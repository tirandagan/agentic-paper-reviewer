"""Offline unit tests for the plugin's Python scripts (stdlib unittest)."""
import csv
import json
import multiprocessing
import time
import pathlib
import subprocess
import sys
import tempfile
import unittest
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "paper-review" / "scripts"))
sys.path.insert(0, str(ROOT / "calibration"))
import arxiv_search as ax  # noqa: E402
import analyze  # noqa: E402
import sample_iclr2025 as samp  # noqa: E402


class ArxivSearch(unittest.TestCase):
    def test_norm_id(self):
        self.assertEqual(ax.norm_id("https://arxiv.org/abs/2410.06215v2"), "2410.06215v2")
        self.assertEqual(ax.norm_id("arXiv:2410.06215v2", keep_version=False), "2410.06215")
        self.assertEqual(ax.norm_id("https://arxiv.org/pdf/2410.06215.pdf"), "2410.06215")
        self.assertEqual(ax.norm_id("hep-th/9901001v1", keep_version=False), "hep-th/9901001")

    def test_parse_feed(self):
        items = ax.parse_feed((ROOT / "tests/fixtures/arxiv_feed.xml").read_bytes())
        self.assertEqual(len(items), 2)  # the error entry is skipped
        first = items[0]
        self.assertEqual(first["id"], "2410.06215")
        self.assertEqual(first["version"], 3)
        self.assertTrue(first["title"].startswith("DataEnvGym: Data Generation Agents in Teacher"))
        self.assertEqual(first["abstract"], "The process of creating training data to teach models is currently driven by humans.")
        self.assertEqual(first["authors"], ["Zaid Khan", "Mohit Bansal"])
        self.assertEqual(first["published"], "2024-10-08")
        self.assertEqual(items[1]["id"], "hep-th/9901001")

    def test_query_terms(self):
        self.assertEqual(ax.query_terms('"direct preference optimization" reward hacking of the LLM'),
                         ['"direct preference optimization"', "reward", "hacking", "LLM"])

    def test_search_url_ands_terms_and_cutoff(self):
        url = ax.build_search_url("data generation agents", 15, before="2024-10-01")
        q = urllib.parse.unquote(url.split("search_query=")[1].split("&")[0])
        self.assertEqual(q, "all:data AND all:generation AND all:agents AND "
                            "submittedDate:[199101010000 TO 202410012359]")
        self.assertIn("max_results=15", url)

    def test_search_url_term_cap_and_exact(self):
        q = urllib.parse.unquote(ax.build_search_url("a1 b2 c3 d4", 5, n_terms=2).split("search_query=")[1].split("&")[0])
        self.assertEqual(q, "all:a1 AND all:b2")
        q = urllib.parse.unquote(ax.build_search_url("vision transformer", 5, exact=True).split("search_query=")[1].split("&")[0])
        self.assertEqual(q, 'all:"vision transformer"')

    def test_bad_cutoff_rejected(self):
        r = subprocess.run([sys.executable, str(ROOT / "skills/paper-review/scripts/arxiv_search.py"),
                            "search", "-q", "x", "--before", "2024/10/01"], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("YYYY-MM-DD", r.stderr)


def _fake_fetch(args):
    """Run in a child process: one _get through the shared limiter with a fake
    300 ms request; returns (start, end) of the fake request."""
    lock_path, delay = args
    import io
    ax.LOCK_PATH = pathlib.Path(lock_path)
    ax.COURTESY_DELAY = delay
    times = {}

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=0):
        times["start"] = time.time()
        time.sleep(0.3)
        times["end"] = time.time()
        return Resp(b"ok")

    ax.urllib.request.urlopen = fake_urlopen
    ax._get("http://example.invalid/")
    return times["start"], times["end"]


class Limiter(unittest.TestCase):
    @unittest.skipIf(ax.fcntl is None, "POSIX only")
    def test_processes_never_overlap_and_keep_the_gap(self):
        with tempfile.TemporaryDirectory() as d:
            lock = str(pathlib.Path(d) / "arxiv.lock")
            with multiprocessing.get_context("fork").Pool(3) as pool:
                spans = sorted(pool.map(_fake_fetch, [(lock, 0.5)] * 3))
        for (s1, e1), (s2, e2) in zip(spans, spans[1:]):
            self.assertGreaterEqual(s2 - e1, 0.45, spans)  # next starts >= delay after previous ENDED


class Calibration(unittest.TestCase):
    def test_band_edges(self):
        self.assertEqual(samp.band_of(2.5), 0)
        self.assertEqual(samp.band_of(3.0), 0)
        self.assertEqual(samp.band_of(4.0), 1)
        self.assertEqual(samp.band_of(6.0), 3)
        self.assertEqual(samp.band_of(9.0), 6)
        self.assertIsNone(samp.band_of(2.0))
        self.assertEqual(len(analyze.THEIRS), len(samp.BAND_EDGES) - 1)

    def test_stats(self):
        self.assertAlmostEqual(analyze.spearman([1, 2, 3, 4], [10, 20, 30, 40]), 1.0)
        self.assertAlmostEqual(analyze.spearman([1, 2, 3, 4], [4, 3, 2, 1]), -1.0)
        self.assertEqual(analyze.ranks([5, 1, 5]), [2.5, 1.0, 2.5])
        self.assertAlmostEqual(analyze.auc([3, 4, 1, 2], [True, True, False, False]), 1.0)
        self.assertAlmostEqual(analyze.auc([1, 1], [True, False]), 0.5)

    def test_analyze_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            runs = d / "runs"
            runs.mkdir()
            rows = [("paper_01", 0, 3.0, "Reject", 4.1), ("paper_02", 2, 5.0, "Reject", 5.2),
                    ("paper_03", 4, 6.7, "Poster", 6.3), ("paper_04", 6, 8.5, "Oral", 7.4)]
            with open(d / "manifest.csv", "w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["paper", "openreview_id", "title", "band", "human_ratings",
                            "human_avg", "decision", "pdf_revision"])
                for p, b, h, dec, a in rows:
                    w.writerow([p, "id" + p, "T", b, "x", h, dec, "rev"])
                    json.dump({"overall": a, "dimensions": {"originality": 5},
                               "related_work_ids": ["2401.00001"]},
                              open(runs / ("%s-review.scores.json" % p), "w"))
                w.writerow(["paper_05", "idp5", "T", 3, "x", 5.5, "Reject", "rev"])
                json.dump({"overall": 2.0, "related_work_ids": []},
                          open(runs / "paper_05-review.scores.json", "w"))
            out = d / "out"
            r = subprocess.run([sys.executable, str(ROOT / "calibration/analyze.py"),
                                "--manifest", str(d / "manifest.csv"), "--runs", str(runs),
                                "--out", str(out)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            s = json.load(open(out / "summary.json"))
            self.assertEqual(s["n"], 4)
            self.assertEqual(s["excluded_no_literature"], ["paper_05"])
            self.assertAlmostEqual(s["spearman"], 1.0)
            self.assertEqual(s["bands"][0]["k_le_5_5"], 1)
            self.assertEqual(s["bands"][4]["k_le_5_5"], 0)
            self.assertTrue((out / "results.csv").exists())

    def test_rescale_leave_one_out_and_fixed(self):
        a, b = analyze.linfit([1, 2, 3], [3, 5, 7])
        self.assertAlmostEqual(a, 1.0)
        self.assertAlmostEqual(b, 2.0)
        rows = [{"ai_overall": x, "human_avg": 2 * x - 3, "band": 0} for x in (3, 4, 5, 6)]
        info = analyze.add_rescale(rows)
        self.assertEqual(info["mode"], "leave-one-out")
        self.assertAlmostEqual(info["mae"], 0.0)  # exact line: every held-out paper predicted
        self.assertAlmostEqual(info["b"], 2.0)
        info = analyze.add_rescale(rows, (-3.0, 3.0))
        self.assertEqual(rows[-1]["ai_rescaled"], 10.0)  # clamped from 15
        self.assertEqual(rows[0]["ai_rescaled"], 6.0)

    def test_raw_score_and_related_count(self):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            with open(d / "manifest.csv", "w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["paper", "openreview_id", "title", "band", "human_ratings",
                            "human_avg", "decision", "pdf_revision"])
                w.writerow(["paper_01", "x", "T", 0, "3", 3.0, "Reject", ""])
            json.dump({"overall": 6.1, "overall_raw": 4.0, "related_work_ids": [],
                       "related_count": 9}, open(d / "paper_01-review.scores.json", "w"))
            rows = analyze.load(d / "manifest.csv", d)
            self.assertEqual(len(rows), 1)  # counted literature passes the gate
            self.assertEqual(rows[0]["ai_overall"], 4.0)  # raw, never the rescaled value


if __name__ == "__main__":
    unittest.main()
