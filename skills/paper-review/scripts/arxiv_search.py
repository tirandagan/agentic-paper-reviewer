#!/usr/bin/env python3
"""arXiv helper for the paper-review skill (Python 3.8+, standard library only).

Subcommands:
  search -q "query" [-q "query2" ...] [--max N] [--exact]
         [--before YYYY-MM-DD] [--exclude ID ...]      relevance-sorted search
  ids <ID> [<ID> ...]                                   metadata for specific IDs
  fetch <ID> [<ID> ...] --out DIR                       download PDFs

IDs may carry a version (2410.01234v1). `ids` and `fetch` keep it; without
one, arXiv serves the latest version, except that `fetch --before` downloads
v1 so a later revision cannot leak post-cutoff content.

--before limits results to papers first submitted on or before that date: a
literature cutoff, so novelty is judged only against work that existed when
the reviewed paper was written. --exclude drops the reviewed paper itself.

Output of search/ids: JSON array on stdout with
  id, version, title, authors, published, abstract, categories, abs_url, pdf_url
(id is version-free; `published` is the v1 submission date.)
"""
import argparse
import json
import pathlib
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

try:
    import fcntl  # POSIX; on Windows requests are spaced per process only
except ImportError:
    fcntl = None

API = "https://export.arxiv.org/api/query"
HEADERS = {"User-Agent": "agentic-paper-reviewer/0.1 (Claude Code plugin; research tool)"}
NS = {"a": "http://www.w3.org/2005/Atom"}
COURTESY_DELAY = 3  # seconds between requests, per arXiv API guidelines
MIN_HITS = 3  # fewer results than this and a search is retried with fewer terms


LOCK_PATH = pathlib.Path(tempfile.gettempdir()) / "agentic-paper-reviewer-arxiv.lock"


class _ArxivSlot:
    """Machine-wide arXiv access: one request at a time across all processes
    (parallel reviews and summarizers share arXiv's per-IP limit), each
    starting >= COURTESY_DELAY after the previous one ENDED. A 429 from any
    process sets a shared "not before" time that every process honours."""

    def __enter__(self):
        self.fh = None
        if fcntl is None:  # Windows: per-process spacing only
            return self
        self.fh = open(LOCK_PATH, "a+")
        fcntl.flock(self.fh, fcntl.LOCK_EX)
        wait = self._not_before() - time.time()
        if wait > 0:
            if wait > 5:
                print("arXiv: waiting %ds for the shared rate limit" % wait, file=sys.stderr)
            time.sleep(wait)
        return self

    def _not_before(self):
        self.fh.seek(0)
        try:
            return float(self.fh.read().strip() or 0)
        except ValueError:
            return 0.0

    def release(self, not_before):
        if self.fh is None:
            time.sleep(max(0, not_before - time.time()))
            return
        self.fh.seek(0)
        self.fh.truncate()
        self.fh.write(str(not_before))
        self.fh.flush()

    def __exit__(self, *exc):
        if self.fh is not None:
            fcntl.flock(self.fh, fcntl.LOCK_UN)
            self.fh.close()


class FetchError(Exception):
    pass


def _get(url, retries=5):
    """GET through the shared limiter. Raises FetchError when arXiv refuses."""
    last = None
    tries = 0
    for attempt in range(retries):
        tries += 1
        with _ArxivSlot() as slot:
            try:
                req = urllib.request.Request(url, headers=HEADERS)
                with urllib.request.urlopen(req, timeout=90) as resp:
                    data = resp.read()
                slot.release(time.time() + COURTESY_DELAY)
                return data
            except urllib.error.HTTPError as exc:
                last = exc
                if exc.code != 429 and exc.code < 500:
                    slot.release(time.time() + COURTESY_DELAY)
                    break
                # Rate limited or overloaded: block every process, honouring Retry-After.
                ra = exc.headers.get("Retry-After") if exc.headers else None
                delay = int(ra) if ra and ra.isdigit() else 30 * (2 ** attempt)
                print("arXiv HTTP %d; all searches pause %ds" % (exc.code, delay), file=sys.stderr)
                slot.release(time.time() + delay)
            except Exception as exc:  # URLError, timeout
                last = exc
                slot.release(time.time() + COURTESY_DELAY * (2 ** attempt))
    raise FetchError("request failed after %d attempt(s): %s" % (tries, last))


def _get_or_exit(url):
    try:
        return _get(url)
    except FetchError as exc:
        sys.exit("error: %s" % exc)


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def norm_id(arxiv_id, keep_version=True):
    """Strip URL/prefix noise from an arXiv ID; optionally drop the version."""
    s = arxiv_id.strip()
    s = re.sub(r"^(https?://)?(www\.|export\.)?arxiv\.org/(abs|pdf)/", "", s)
    s = re.sub(r"^arxiv:", "", s, flags=re.I)
    s = re.sub(r"\.pdf$", "", s)
    if not keep_version:
        s = re.sub(r"v\d+$", "", s)
    return s


def date_filter(before):
    """arXiv query clause limiting first-submission date to <= `before` (YYYY-MM-DD)."""
    if not before:
        return ""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", before):
        sys.exit("error: --before must be YYYY-MM-DD, got %r" % before)
    return " AND submittedDate:[199101010000 TO %s2359]" % before.replace("-", "")


STOPWORDS = set("""a an and are as at be by for from how in into is it of on or that the
their this to towards using via what when which with without""".split())


def query_terms(query):
    """Split a query into arXiv field terms: "quoted phrases" stay whole,
    other words become single terms; stopwords and punctuation are dropped."""
    terms = ['"%s"' % ph.strip() for ph in re.findall(r'"([^"]+)"', query) if ph.strip()]
    rest = re.sub(r'"[^"]*"', " ", query)
    for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9\-\.]*", rest):
        w = w.strip(".-")
        if w and w.lower() not in STOPWORDS:
            terms.append(w)
    return terms


def build_search_url(query, max_results, exact=False, before=None, n_terms=None):
    """All terms must match (AND). arXiv's `all:(a b c)` form returns mostly
    unrelated papers, so it is not used. n_terms keeps only the first n terms."""
    if exact:
        clauses = ['all:"%s"' % query.replace('"', "")]
    else:
        terms = query_terms(query)
        if n_terms:
            terms = terms[:n_terms]
        clauses = ["all:%s" % t for t in terms] or ['all:"%s"' % query]
    expr = " AND ".join(clauses) + date_filter(before)
    return "%s?search_query=%s&sortBy=relevance&max_results=%d" % (
        API, urllib.parse.quote(expr), max_results)


def parse_feed(xml_bytes):
    root = ET.fromstring(xml_bytes)
    entries = []
    for e in root.findall("a:entry", NS):
        raw_id = e.findtext("a:id", default="", namespaces=NS)
        m = re.search(r"arxiv\.org/abs/(.+)$", raw_id)
        if not m:  # the API sometimes returns an <entry> carrying an error message
            continue
        versioned = norm_id(m.group(1))
        bare = norm_id(versioned, keep_version=False)
        vm = re.search(r"v(\d+)$", versioned)
        entries.append({
            "id": bare,
            "version": int(vm.group(1)) if vm else None,
            "title": _clean(e.findtext("a:title", default="", namespaces=NS)),
            "authors": [_clean(a.findtext("a:name", default="", namespaces=NS))
                        for a in e.findall("a:author", NS)],
            "published": e.findtext("a:published", default="", namespaces=NS)[:10],
            "abstract": _clean(e.findtext("a:summary", default="", namespaces=NS)),
            "categories": [c.get("term", "") for c in e.findall("a:category", NS)],
            "abs_url": "https://arxiv.org/abs/%s" % bare,
            "pdf_url": "https://arxiv.org/pdf/%s" % bare,
        })
    return entries


def _dump(obj):
    json.dump(obj, sys.stdout, indent=1, ensure_ascii=False)
    sys.stdout.write("\n")


def cmd_search(args):
    excluded = {norm_id(i, keep_version=False) for i in (args.exclude or [])}
    results, seen = [], set(excluded)
    for i, query in enumerate(args.query):
        items = parse_feed(_get_or_exit(build_search_url(query, args.max, args.exact, args.before)))
        # Too narrow? Drop trailing terms (queries put the core terms first) until
        # at least MIN_HITS papers come back or two terms are left.
        n = len(query_terms(query))
        while not args.exact and len(items) < MIN_HITS and n > 2:
            n -= 1
            items = parse_feed(_get_or_exit(build_search_url(query, args.max, False, args.before, n)))
        for item in items:
            if args.before and item["published"] and item["published"] > args.before:
                continue  # belt and braces: the API filter should already drop these
            if item["id"] not in seen:
                seen.add(item["id"])
                item["query"] = query
                results.append(item)
    _dump(results)


def cmd_ids(args):
    id_list = ",".join(norm_id(i) for i in args.id)
    url = "%s?id_list=%s&max_results=%d" % (API, urllib.parse.quote(id_list), len(args.id))
    _dump(parse_feed(_get_or_exit(url)))


def cmd_fetch(args):
    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    failed = []
    for raw in args.id:
        ident = norm_id(raw)
        if args.before and not re.search(r"v\d+$", ident):
            # With a literature cutoff, read v1: later versions may postdate the cutoff.
            ident += "v1"
        try:
            data = _get("https://arxiv.org/pdf/%s" % ident)
        except FetchError as exc:
            # One missing PDF must not stop the rest; the caller falls back to the abstract.
            failed.append(ident)
            print("warning: %s: %s; skipped" % (ident, exc), file=sys.stderr)
            continue
        if not data.startswith(b"%PDF"):
            print("warning: %s: response is not a PDF, skipped" % ident, file=sys.stderr)
            continue
        path = out_dir / (ident.replace("/", "_") + ".pdf")
        path.write_bytes(data)
        print(path)
    if failed and len(failed) == len(args.id):
        sys.exit("error: no PDF could be downloaded")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd")
    sub.required = True

    p = sub.add_parser("search", help="search arXiv, relevance-sorted")
    p.add_argument("-q", "--query", action="append", required=True,
                   help="query text (repeatable)")
    p.add_argument("--max", type=int, default=15, help="max results per query")
    p.add_argument("--exact", action="store_true", help="phrase match")
    p.add_argument("--before", metavar="YYYY-MM-DD",
                   help="only papers first submitted on or before this date")
    p.add_argument("--exclude", action="append", metavar="ID",
                   help="arXiv ID to leave out, e.g. the paper under review (repeatable)")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("ids", help="metadata for specific arXiv IDs")
    p.add_argument("id", nargs="+")
    p.set_defaults(func=cmd_ids)

    p = sub.add_parser("fetch", help="download PDFs for arXiv IDs")
    p.add_argument("id", nargs="+")
    p.add_argument("--out", required=True, help="output directory")
    p.add_argument("--before", metavar="YYYY-MM-DD",
                   help="literature cutoff: download v1 (unless a version is given), "
                        "since later versions may postdate the cutoff")
    p.set_defaults(func=cmd_fetch)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
