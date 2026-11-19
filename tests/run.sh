#!/usr/bin/env bash
# Checks for the agentic-paper-reviewer plugin. Needs bash and python3.
#   tests/run.sh          offline checks: manifests, skill frontmatter and paths,
#                         unit tests of the scripts, no secrets or PDFs in the tree
#   tests/run.sh --live   also one real arXiv search with a literature cutoff
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LIVE=0; [ "${1:-}" = "--live" ] && LIVE=1
N_OK=0; N_FAIL=0
check() { # $1 name, $2 problems (empty = good)
  if [ -z "$2" ]; then N_OK=$((N_OK+1)); echo "  ok   $1"; else N_FAIL=$((N_FAIL+1)); echo "  FAIL $1"; printf '       %s\n' "$2"; fi
}

echo "manifests and skill"
check "plugin.json and marketplace.json agree, version matches CHANGELOG" "$(cd "$ROOT" && python3 - <<'PY'
import json, re
p = json.load(open(".claude-plugin/plugin.json"))
m = json.load(open(".claude-plugin/marketplace.json"))
top = re.search(r"^## (\S+)", open("CHANGELOG.md").read(), re.M).group(1)
errs = []
if p.get("name") != "agentic-paper-reviewer": errs.append("plugin name changed: %r" % p.get("name"))
if p.get("version") != top: errs.append("plugin.json version %s != CHANGELOG %s" % (p.get("version"), top))
names = [x["name"] for x in m.get("plugins", [])]
if names != ["agentic-paper-reviewer"]: errs.append("marketplace lists %r" % names)
print("; ".join(errs))
PY
)"
check "SKILL.md frontmatter has name, description, allowed-tools; paths use \${CLAUDE_SKILL_DIR}" "$(cd "$ROOT" && python3 - <<'PY'
import re, pathlib
s = open("skills/paper-review/SKILL.md").read()
fm = s.split("---")[1]
errs = [k for k in ("name: paper-review", "description:", "allowed-tools:") if k not in fm]
if "~/.claude/skills" in s: errs.append("hard-coded ~/.claude/skills path")
for ref in re.findall(r"\$\{CLAUDE_SKILL_DIR\}/([\w./-]+)", s):
    if not pathlib.Path("skills/paper-review", ref).exists(): errs.append("missing " + ref)
print("; ".join(errs))
PY
)"
check "agent file has name and description" "$(grep -q '^name: related-paper-summarizer' "$ROOT/agents/related-paper-summarizer.md" && grep -q '^description:' "$ROOT/agents/related-paper-summarizer.md" || echo 'bad frontmatter')"

echo "scripts"
out="$(cd "$ROOT" && python3 -m unittest tests/test_scripts.py 2>&1)"
check "unit tests (tests/test_scripts.py)" "$(echo "$out" | tail -1 | grep -q '^OK' || echo "$out" | tail -15)"

echo "hygiene"
# Files that would ship: tracked or not ignored by .gitignore (local calibration
# PDFs under calibration/runs/ are ignored, so they never reach the repository).
shipped() { cd "$ROOT" && if git rev-parse --git-dir >/dev/null 2>&1; then git ls-files -co --exclude-standard; else find . -path ./.git -prune -o -type f -print | sed 's|^\./||'; fi; }
check "no PDFs, env files or tokens in the shipped files" "$(shipped | grep -E '(\.pdf$|(^|/)\.env)'; shipped | grep -v '^tests/run.sh$' | (cd "$ROOT" && xargs -r -d '\n' grep -IlE 'OPENREVIEW_PASSWORD=.+|Bearer [A-Za-z0-9._-]{20,}' 2>/dev/null) )"
check "LF line endings in scripts" "$(cd "$ROOT" && grep -rlI $'\r' --include='*.py' --include='*.sh' --include='*.md' . )"

if [ "$LIVE" = 1 ]; then
  echo "live"
  res="$(python3 "$ROOT/skills/paper-review/scripts/arxiv_search.py" search -q '"curriculum learning" teacher student' --max 5 --before 2024-10-01 2>&1)"
  check "arXiv search with cutoff returns papers on or before 2024-10-01" "$(echo "$res" | python3 -c '
import json, sys
d = json.load(sys.stdin)
bad = [x["id"] for x in d if x["published"] > "2024-10-01"]
print("no results" if not d else ("after cutoff: %s" % bad if bad else ""))' 2>&1)"
fi

echo
echo "$N_OK passed, $N_FAIL failed"
[ "$N_FAIL" = 0 ]
