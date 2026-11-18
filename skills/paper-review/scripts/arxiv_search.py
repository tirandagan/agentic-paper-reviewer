#!/usr/bin/env python3
"""arXiv helper for the paper-review skill (Python 3.8+, standard library only).

Subcommands:
  search -q "query" [-q "query2" ...] [--max N] [--exact]
         [--before YYYY-MM-DD] [--exclude ID ...]      relevance-sorted search
  ids <ID> [<ID> ...]                                   metadata for specific IDs
  fetch <ID> [<ID> ...] --out DIR                       download PDFs

IDs may carry a version (2410.01234v1). `ids` and `fetch` keep it; without
one, arXiv serves the latest version.

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
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

API = "https://export.arxiv.org/api/query"
HEADERS = {"User-Agent": "agentic-paper-reviewer/0.1 (Claude Code plugin; research tool)"}
NS = {"a": "http://www.w3.org/2005/Atom"}
COURTESY_DELAY = 3  # seconds between requests, per arXiv API guidelines
MIN_HITS = 3  # fewer results than this and a search is retried with fewer terms


def _get(url, retries=4):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except Exception as exc:  # HTTPError (incl. 429/503), URLError, timeout
            last = exc
            time.sleep(COURTESY_DELAY * (2 ** attempt))
    sys.exit("error: request failed after %d attempts: %s" % (retries, last))


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
        if i:
            time.sleep(COURTESY_DELAY)
        items = parse_feed(_get(build_search_url(query, args.max, args.exact, args.before)))
        # Too narrow? Drop trailing terms (queries put the core terms first) until
        # at least MIN_HITS papers come back or two terms are left.
        n = len(query_terms(query))
        while not args.exact and len(items) < MIN_HITS and n > 2:
            n -= 1
            time.sleep(COURTESY_DELAY)
            items = parse_feed(_get(build_search_url(query, args.max, False, args.before, n)))
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
    _dump(parse_feed(_get(url)))


def cmd_fetch(args):
    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    for i, raw in enumerate(args.id):
        if i:
            time.sleep(COURTESY_DELAY)
        ident = norm_id(raw)
        data = _get("https://arxiv.org/pdf/%s" % ident)
        if not data.startswith(b"%PDF"):
            print("warning: %s: response is not a PDF, skipped" % ident, file=sys.stderr)
            continue
        path = out_dir / (ident.replace("/", "_") + ".pdf")
        path.write_bytes(data)
        print(path)


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
    p.set_defaults(func=cmd_fetch)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
