#!/usr/bin/env python3
"""build_grading_pack.py: parse 'Rubric with citations.md' into criteria.jsonl and judge batches.

    venv/bin/python -I harness/build_grading_pack.py --rubric "case/Rubric with citations.md" --out grading

Writes
  <out>/criteria.jsonl          one criterion per line: id, theme, importance, weight, criterion, citations[], citations_md
  <out>/batches/batch_NN.json   ~--batch-size criteria each, in rubric order
  <out>/JUDGE_PROMPT.md         the instruction for one Claude judge call per batch (the owner fills in the paths)
The parse is checked against the count the rubric states in its own header ("contains N quality criteria") and
fails loudly on any duplicate id, unknown importance, empty criterion or stray heading.

Weights (stated, used by merge_grades.py): high 3, medium 2, low 1.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

WEIGHTS = {"high": 3, "medium": 2, "low": 1}
HEAD_RE = re.compile(r"^### (R-\d{3}[a-z]?) \(importance: ([a-z]+)\)\s*$")
THEME_RE = re.compile(r"^## (\d+)\. (.+?)\s*$")
CIT_RE = re.compile(r"^(\d+)\. \*(top|additional)\* - (.+)$")


def parse(text: str) -> list[dict]:
    lines = text.splitlines()
    m = re.search(r"contains (\d+) quality criteria", text)
    if not m:
        raise SystemExit("rubric header does not state the criterion count")
    stated = int(m.group(1))
    crits: list[dict] = []
    theme = None
    cur: dict | None = None
    mode = None
    for ln in lines:
        tm = THEME_RE.match(ln)
        if tm:
            theme = f"{tm.group(1)}. {tm.group(2)}"
            cur = None
            continue
        if ln.startswith("## "):  # e.g. "## Coverage summary": ends the criteria
            cur = None
            theme = None
            continue
        hm = HEAD_RE.match(ln)
        if ln.startswith("### ") and not hm:
            raise SystemExit(f"unparsed criterion heading: {ln!r}")
        if hm:
            if theme is None:
                raise SystemExit(f"criterion {hm.group(1)} outside a numbered theme")
            cur = {"id": hm.group(1), "theme": theme, "importance": hm.group(2), "criterion": "", "citations": [],
                   "_cit_lines": []}
            crits.append(cur)
            mode = None
            continue
        if cur is None:
            continue
        if ln.startswith("**Criterion.**"):
            cur["criterion"] = ln[len("**Criterion.**"):].strip()
            mode = "crit"
            continue
        if ln.startswith("**Citation/Evidence.**"):
            mode = "cit"
            rest = ln[len("**Citation/Evidence.**"):].strip()
            if rest:  # an evidence note written on the heading line itself (absence-based guards)
                cur["_cit_lines"].append(rest)
                cur["citations"].append({"n": 0, "rank": "note", "text": rest})
            continue
        if mode == "crit" and ln.strip():
            cur["criterion"] += " " + ln.strip()
        elif mode == "cit":
            cur["_cit_lines"].append(ln)
            cm = CIT_RE.match(ln)
            if cm:
                cur["citations"].append({"n": int(cm.group(1)), "rank": cm.group(2), "text": cm.group(3).strip()})
            elif ln.strip() and cur["citations"]:
                cur["citations"][-1]["text"] += "\n" + ln.strip()
            elif ln.strip():
                cur["citations"].append({"n": 0, "rank": "note", "text": ln.strip()})
    problems = []
    ids = [c["id"] for c in crits]
    dups = sorted({i for i in ids if ids.count(i) > 1})
    if dups:
        problems.append(f"duplicate ids {dups}")
    for c in crits:
        if c["importance"] not in WEIGHTS:
            problems.append(f"{c['id']}: unknown importance {c['importance']!r}")
        if not c["criterion"]:
            problems.append(f"{c['id']}: empty criterion")
        c["weight"] = WEIGHTS.get(c["importance"], 0)
        c["citations_md"] = "\n".join(c.pop("_cit_lines")).strip()
        if not c["citations_md"]:
            problems.append(f"{c['id']}: no citation/evidence text")
    if len(crits) != stated:
        problems.append(f"parsed {len(crits)} criteria, rubric states {stated}")
    if problems:
        raise SystemExit("rubric parse failed: " + "; ".join(problems))
    return crits


JUDGE_PROMPT = """# BAR judge instruction (one call per batch)

You are grading a candidate transfer pricing Master File (Freshworks Group, FY2023) against a batch of rubric
criteria. Read the whole candidate file first: {{CANDIDATE_PATH}}
Then read the batch file: {{BATCH_PATH}} (JSON: a list of criteria, each with id, importance, criterion and the
citation/evidence passages from the matter documents that ground it).

Grading guidance (binding, verbatim from the rubric):

> Grade the substance, not the wording or location. A criterion is satisfied whenever the candidate output contains
> the fact or makes the point, regardless of phrasing, ordering, or where it appears (which section, paragraph, or
> heading). Do not require an exact paragraph or section number, an exact quote, or a specific computed form
> (components vs a multiplied total) unless the criterion explicitly makes that citation or figure the graded point.
> Equivalent phrasings and reasonable paraphrases pass.

For each criterion give exactly one verdict:
- PASS: the candidate satisfies the criterion. For a "must not" criterion, PASS means the candidate does not make the
  prohibited statement.
- FAIL: it does not (the point is missing, wrong, contradicted, or a prohibited statement is made).
- UNGRADABLE: only if the criterion cannot be judged from the candidate at all (for example the candidate file is
  empty or truncated before the relevant material). Do not use UNGRADABLE for a point that is simply missing; that
  is FAIL.

The citations tell you what the correct facts are; the candidate does not need to cite them. Judge each criterion
independently. Do not reward length or style.

Output: write one JSON object per line, one line per criterion in the batch, in batch order, and nothing else, to
{{RESULT_PATH}}:
{"id": "R-001", "verdict": "PASS", "reason": "<one line>", "quote": "<short verbatim quote from the candidate, or empty if none applies>"}
The reason is one line. For PASS quote the candidate text that satisfies the criterion. For FAIL quote the wrong or
prohibited text if there is one, otherwise leave quote empty and say what is missing.
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rubric", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--batch-size", type=int, default=15)
    a = ap.parse_args()
    crits = parse(a.rubric.read_text(encoding="utf-8"))
    a.out.mkdir(parents=True, exist_ok=True)
    with open(a.out / "criteria.jsonl", "w", encoding="utf-8") as f:
        for c in crits:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    bdir = a.out / "batches"
    bdir.mkdir(exist_ok=True)
    nb = math.ceil(len(crits) / a.batch_size)
    size = math.ceil(len(crits) / nb)  # even batches: 175 -> 12 batches of 15/14
    for b in range(nb):
        part = crits[b * size:(b + 1) * size]
        payload = [{"id": c["id"], "importance": c["importance"], "theme": c["theme"], "criterion": c["criterion"],
                    "citations": c["citations_md"]} for c in part]
        (bdir / f"batch_{b + 1:02d}.json").write_text(json.dumps(payload, indent=1, ensure_ascii=False))
    (a.out / "JUDGE_PROMPT.md").write_text(JUDGE_PROMPT)
    by = {k: sum(1 for c in crits if c["importance"] == k) for k in WEIGHTS}
    print(json.dumps({"criteria": len(crits), "by_importance": by, "batches": nb, "batch_size": size,
                      "max_weight": sum(c["weight"] for c in crits)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
