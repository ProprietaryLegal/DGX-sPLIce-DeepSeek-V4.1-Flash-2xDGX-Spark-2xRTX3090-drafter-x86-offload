#!/usr/bin/env python3
"""merge_grades.py: merge judge batch results into one score per run label.

    venv/bin/python -I harness/merge_grades.py --grading grading --label sparks-r1 [--label v100-r1 ...]

Reads <grading>/criteria.jsonl and <grading>/results/<label>/batch_NN.jsonl (one JSON object per line:
id, verdict PASS|FAIL|UNGRADABLE, reason, quote). Fails loudly (exit 1) if any criterion is missing, duplicated or
unknown, or a verdict is not one of the three; an incomplete grading is never scored.

Score per label:
  pass_count / 175
  weighted_pct = 100 * sum(weight of PASS) / sum(weight of all criteria); weights high 3, medium 2, low 1
  UNGRADABLE counts as not passed; the count is reported, with the weighted % over graded criteria only beside it.
Writes <grading>/results/<label>/score.json and prints a per-theme table (and a side-by-side table for 2+ labels).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

VERDICTS = ("PASS", "FAIL", "UNGRADABLE")


def load_results(rdir: Path, ids: set[str]) -> dict[str, dict]:
    files = sorted(rdir.glob("batch_*.jsonl"))
    if not files:
        raise SystemExit(f"no batch results in {rdir}")
    got: dict[str, dict] = {}
    problems: list[str] = []
    for f in files:
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError as e:
                problems.append(f"{f.name}:{n}: not JSON ({e})")
                continue
            cid = r.get("id")
            if cid not in ids:
                problems.append(f"{f.name}:{n}: unknown id {cid!r}")
            elif cid in got:
                problems.append(f"{f.name}:{n}: duplicate {cid}")
            elif r.get("verdict") not in VERDICTS:
                problems.append(f"{f.name}:{n}: {cid} verdict {r.get('verdict')!r}")
            else:
                got[cid] = r
    missing = sorted(ids - set(got))
    if missing:
        problems.append(f"missing {len(missing)} criteria: {missing}")
    if problems:
        raise SystemExit(f"grading for {rdir} is incomplete or invalid:\n  " + "\n  ".join(problems))
    return got


def score(crits: list[dict], got: dict[str, dict]) -> dict:
    tot_w = sum(c["weight"] for c in crits)
    pw = sum(c["weight"] for c in crits if got[c["id"]]["verdict"] == "PASS")
    ung = [c for c in crits if got[c["id"]]["verdict"] == "UNGRADABLE"]
    graded_w = tot_w - sum(c["weight"] for c in ung)
    themes: dict[str, dict] = {}
    for c in crits:
        t = themes.setdefault(c["theme"], {"n": 0, "pass": 0, "w": 0, "pw": 0})
        t["n"] += 1
        t["w"] += c["weight"]
        if got[c["id"]]["verdict"] == "PASS":
            t["pass"] += 1
            t["pw"] += c["weight"]
    by_imp: dict[str, list[int]] = {}
    for c in crits:
        v = by_imp.setdefault(c["importance"], [0, 0])
        v[1] += 1
        v[0] += got[c["id"]]["verdict"] == "PASS"
    return {"criteria": len(crits), "pass_count": sum(1 for c in crits if got[c["id"]]["verdict"] == "PASS"),
            "fail_count": sum(1 for c in crits if got[c["id"]]["verdict"] == "FAIL"), "ungradable_count": len(ung),
            "weights": {"high": 3, "medium": 2, "low": 1},
            "weighted_pct": round(100 * pw / tot_w, 2),
            "weighted_pct_graded_only": round(100 * pw / graded_w, 2) if graded_w else None,
            "by_importance": {k: {"pass": v[0], "of": v[1]} for k, v in by_imp.items()},
            "by_theme": themes}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--grading", type=Path, required=True)
    ap.add_argument("--label", action="append", required=True)
    a = ap.parse_args()
    crits = [json.loads(l) for l in (a.grading / "criteria.jsonl").read_text().splitlines() if l.strip()]
    ids = {c["id"] for c in crits}
    scores = {}
    for lab in a.label:
        rdir = a.grading / "results" / lab
        got = load_results(rdir, ids)
        s = score(crits, got)
        s["label"] = lab
        (rdir / "score.json").write_text(json.dumps(s, indent=1))
        scores[lab] = s
    labs = list(scores)
    print("| theme | n | " + " | ".join(f"{l} pass" for l in labs) + " |")
    print("|---|---|" + "---|" * len(labs))
    for th, t in scores[labs[0]]["by_theme"].items():
        print(f"| {th} | {t['n']} | " + " | ".join(str(scores[l]["by_theme"][th]["pass"]) for l in labs) + " |")
    print(f"| **pass count** | {len(crits)} | " + " | ".join(str(scores[l]["pass_count"]) for l in labs) + " |")
    print("| **weighted %** (H3/M2/L1) | | " + " | ".join(f"{scores[l]['weighted_pct']}" for l in labs) + " |")
    print("| ungradable | | " + " | ".join(str(scores[l]["ungradable_count"]) for l in labs) + " |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
