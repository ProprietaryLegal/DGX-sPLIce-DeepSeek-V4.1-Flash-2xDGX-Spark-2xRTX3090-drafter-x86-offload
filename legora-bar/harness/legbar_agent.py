#!/usr/bin/env python3
"""legbar_agent.py: one agent run of the Legora BAR public case (Freshworks FY2023 Master File) against an
OpenAI-compatible chat server with tool calling. Identical on every build; only --base-url / --model / --label change.

    venv/bin/python -I harness/legbar_agent.py --base-url http://HOST:PORT/v1 --model NAME --label sparks-r1 \
        --matter matter --task case/prompt.md --runs runs --tokenizer /path/tokenizer.json \
        --ctx-budget 100000 --max-tokens 16384 --max-turns 300 --wall-s 14400 --seed 1

Design
  * The matter is read only through tools over the pre-extracted text (extract_matter.py output, with
    === [page N] === / [slide N] / [sheet: X] / [section: X] anchors). The model never sees the rubric.
  * Tools: list_files, read_file(path, start, max_chars[, anchor]), search(query, path_glob), save_note(key, text),
    read_notes, write_section(section_id, markdown), read_draft([section_id]), finish([summary]).
  * Notes and the draft live outside the context (runs/<label>/notes.json, draft.json) and survive elision.
  * Context budget: before each request the prompt is counted with the model's own tokenizer (tokenizer.json),
    scaled by the worst observed server/estimate ratio. If prompt + --max-tokens would exceed --ctx-budget, the
    oldest bulky items are replaced by a one-line stub, oldest first, until the prompt is under
    --elide-to x budget: tool outputs, then (same pass, by age) earlier reasoning and the long arguments of
    write_section / save_note calls (their text is already persisted). The newest --keep-recent messages are never
    elided. If the prompt still does not fit, the run ends CONTEXT_EXHAUSTED.
  * Thinking on, reasoning effort 50, via chat_template_kwargs; T 1.0, top_p 1.0, seeded. Earlier reasoning in the
    tool loop is sent back as reasoning_content (the DeepSeek V4.1 template keeps it after the last user turn).
  * Every request is reconstructible from transcript.jsonl: the first record holds the full request, later
    records hold the appended messages and the elision edits; --replay rebuilds any turn's exact body and checks its
    sha256. Every response is logged whole.
  * Outcome (run.json "outcome"), exactly one of:
        FINISHED            the model called finish()
        TIMEOUT             --max-turns or --wall-s was reached (a counted outcome, never a success)
        CONTEXT_EXHAUSTED   the prompt could not be brought under the budget by elision
        ERROR               HTTP / protocol / I/O failure (no retries); detail recorded
    The draft so far is always written to master_file.md, whatever the outcome.

  * Shared-server etiquette: --gate dgx runs the h2h kit's idle gate (kit_gate.py, a pinned copy of
    bench-h2h1103/kit/gate.py) before EVERY request: hold files absent, /health 200, /metrics running+waiting 0.
    Time spent waiting at the gate is logged (gate_wait_s) and does not count against --wall-s.

Stdlib only, plus the `tokenizers` package for counting.
"""
from __future__ import annotations

import argparse
import copy
import fnmatch
import hashlib
import json
import socket
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal, Union

HARNESS_VERSION = "legbar-agent-1"
EFFORT = 50
THINK_ON = {"thinking": True, "reasoning_effort": EFFORT}
EFFORT_MARK = f"Reasoning Effort: {EFFORT} (range 1-100"
SMALLEST_SERVER_LIMIT = 327680  # Sparks max_model_len (V100: 524,288), per the owners 2026-11-04
STUB_MIN_CHARS = 300  # items shorter than this are never worth eliding
MSG_OVERHEAD_TOKENS = 8

SYSTEM_PROMPT = """You are a professional assistant working on a matter. The documents in the matter folder are \
available to you only through the tools provided. Each document has been converted to text, with anchor lines \
such as "=== [page 12] ===", "=== [slide 3] ===", "=== [sheet: Summary] ===" or "=== [section: 2.1 Background] ===". \
Together the documents are far larger than your context window, so you cannot read everything: use list_files, \
search and read_file to find and read what you need.

Working method:
- Keep important findings with save_note; notes persist for the whole task. To save space, older tool outputs may \
later be replaced by a one-line stub; if you need that material again, read it again.
- Write the deliverable with write_section, one section at a time, in Markdown. Sections are assembled in the order \
in which each section_id was first written; writing an existing section_id replaces that section. Use read_draft to \
review what you have written.
- Call finish when the deliverable is complete. Only the text written with write_section is delivered.

The task follows."""

TOOLS = [
    {"type": "function", "function": {
        "name": "list_files",
        "description": "List the documents in the matter folder with their type, size in units (pages, slides, sheets "
                       "or sections) and approximate length in tokens.",
        "parameters": {"type": "object", "properties": {
            "path_prefix": {"type": "string", "description": "Only list documents whose path starts with this."}},
            "required": []}}},
    {"type": "function", "function": {
        "name": "read_file",
        "description": "Read part of a document's text. Returns up to max_chars characters starting at character "
                       "offset start, or at the anchor line if anchor is given (e.g. \"page 45\", \"slide 2\", "
                       "\"sheet: Summary\", \"section: 3.1 Corporate Identity\"). The reply states the next offset.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "Document path as shown by list_files."},
            "start": {"type": "integer", "description": "Character offset to start at (default 0)."},
            "max_chars": {"type": "integer", "description": "Maximum characters to return."},
            "anchor": {"type": "string", "description": "Optional anchor to start at instead of start."}},
            "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "search",
        "description": "Case-insensitive plain-text search over the documents' text. Each hit gives the document, "
                       "its anchor (page/slide/sheet/section), the character offset and the matching line.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Text to find (matched literally within a line)."},
            "path_glob": {"type": "string", "description": "Optional glob on document paths, e.g. \"*10-K*\" or "
                                                           "\"05 Benchmark Studies/*\" (default all)."}},
            "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "save_note",
        "description": "Save or replace a note under a key. Notes persist for the whole task.",
        "parameters": {"type": "object", "properties": {
            "key": {"type": "string"}, "text": {"type": "string"}}, "required": ["key", "text"]}}},
    {"type": "function", "function": {
        "name": "read_notes",
        "description": "Return all saved notes.",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "write_section",
        "description": "Write or replace one section of the deliverable, in Markdown.",
        "parameters": {"type": "object", "properties": {
            "section_id": {"type": "string", "description": "A stable id for the section, e.g. \"3.1\"."},
            "markdown": {"type": "string"}}, "required": ["section_id", "markdown"]}}},
    {"type": "function", "function": {
        "name": "read_draft",
        "description": "Without section_id: list the draft's sections with their lengths. With section_id: return "
                       "that section's text.",
        "parameters": {"type": "object", "properties": {"section_id": {"type": "string"}}, "required": []}}},
    {"type": "function", "function": {
        "name": "finish",
        "description": "Finish the task. Call this once the deliverable is complete.",
        "parameters": {"type": "object", "properties": {"summary": {"type": "string"}}, "required": []}}},
]


# --------------------------------------------------------------------------- outcomes

@dataclass(frozen=True)
class Finished:
    summary: str
    outcome: Literal["FINISHED"] = "FINISHED"


@dataclass(frozen=True)
class Timeout:
    limit: Literal["turns", "wall"]
    detail: str
    outcome: Literal["TIMEOUT"] = "TIMEOUT"


@dataclass(frozen=True)
class ContextExhausted:
    prompt_tokens: int
    budget: int
    outcome: Literal["CONTEXT_EXHAUSTED"] = "CONTEXT_EXHAUSTED"


@dataclass(frozen=True)
class Error:
    kind: Literal["http", "network", "protocol", "io"]
    detail: str
    outcome: Literal["ERROR"] = "ERROR"


RunOutcome = Union[Finished, Timeout, ContextExhausted, Error]


class WallClockExpired(Exception):
    pass


# --------------------------------------------------------------------------- matter + workspace

class Matter:
    """Read-only view over the extracted matter folder (<rel path>.md files plus _inventory.jsonl)."""

    def __init__(self, root: Path, read_max_chars: int) -> None:
        self.root = root
        self.read_max_chars = read_max_chars
        inv = root / "_inventory.jsonl"
        if not inv.exists():
            raise SystemExit(f"matter inventory missing: {inv} (run extract_matter.py first)")
        self.inventory = [json.loads(l) for l in inv.read_text().splitlines() if l.strip()]
        bad = [r["path"] for r in self.inventory if r["outcome"] != "EXTRACTED"]
        if bad:
            raise SystemExit(f"matter has files that were not extracted: {bad}")
        self.text: dict[str, str] = {}
        for r in self.inventory:
            p = root / (r["path"] + ".md")
            self.text[r["path"]] = p.read_text(encoding="utf-8")
        self.inventory_sha = hashlib.sha256(inv.read_bytes()).hexdigest()

    def resolve(self, path: str) -> str:
        p = path.strip().lstrip("/")
        if p.endswith(".md") and p[:-3] in self.text:
            p = p[:-3]
        if p in self.text:
            return p
        cands = [k for k in self.text if k.endswith("/" + p) or Path(k).name == p]
        if len(cands) == 1:
            return cands[0]
        if not cands:
            raise ToolError(f"no document {path!r}; call list_files for the exact paths")
        raise ToolError(f"{path!r} matches several documents: {cands}")

    @staticmethod
    def anchor_at(text: str, offset: int) -> str:
        i = text.rfind("=== [", 0, offset + 5)  # a marker that starts exactly at offset counts
        if i < 0:
            return "(start)"
        j = text.find("] ===", i)
        return text[i + 5:j] if j > 0 else "(start)"


class ToolError(Exception):
    """A tool call the model made wrongly; the message goes back to the model as the tool result."""


@dataclass
class Workspace:
    run_dir: Path
    notes: dict[str, str] = field(default_factory=dict)
    sections: dict[str, str] = field(default_factory=dict)  # insertion order = assembly order

    def save(self) -> None:
        (self.run_dir / "notes.json").write_text(json.dumps(self.notes, indent=1, ensure_ascii=False))
        (self.run_dir / "draft.json").write_text(json.dumps(self.sections, indent=1, ensure_ascii=False))

    def assemble(self) -> str:
        return "\n\n".join(md.rstrip() for md in self.sections.values()).rstrip() + "\n" if self.sections else ""


def run_tool(name: str, args: dict, matter: Matter, ws: Workspace) -> tuple[str, bool]:
    """Execute one tool call. Returns (result text, finished?). Raises ToolError for a bad call."""
    if name == "list_files":
        pre = str(args.get("path_prefix") or "")
        rows = [r for r in matter.inventory if r["path"].startswith(pre)]
        lines = [f"{r['path']}  [{r['kind']}, {r['units']} {r['unit_name']}s, ~{r['tokens']} tokens]" for r in rows]
        return f"{len(rows)} documents\n" + "\n".join(lines), False
    if name == "read_file":
        path = matter.resolve(str(args.get("path", "")))
        text = matter.text[path]
        maxc = int(args.get("max_chars") or matter.read_max_chars)
        if maxc <= 0:
            raise ToolError("max_chars must be positive")
        maxc = min(maxc, matter.read_max_chars)
        anchor = args.get("anchor")
        if anchor:
            a = str(anchor).strip().strip("[]=").strip()
            i = text.find(f"=== [{a}] ===")
            if i < 0:
                low = text.lower()
                i = low.find(f"=== [{a.lower()}")
            if i < 0:
                raise ToolError(f"anchor {anchor!r} not found in {path}")
            start = i
        else:
            start = int(args.get("start") or 0)
        if start < 0 or start > len(text):
            raise ToolError(f"start {start} outside 0..{len(text)}")
        chunk = text[start:start + maxc]
        end = start + len(chunk)
        nxt = f"next start={end}" if end < len(text) else "end of document"
        head = f"[{path} | chars {start}-{end} of {len(text)} | at anchor: {Matter.anchor_at(text, start)} | {nxt}]\n"
        return head + chunk, False
    if name == "search":
        q = str(args.get("query", "")).strip()
        if not q:
            raise ToolError("query is empty")
        glob = str(args.get("path_glob") or "*")
        ql = q.lower()
        hits: list[str] = []
        total = 0
        for path, text in matter.text.items():
            if not fnmatch.fnmatch(path, glob) and not fnmatch.fnmatch(Path(path).name, glob):
                continue
            off = 0
            for line in text.splitlines(keepends=True):
                if ql in line.lower() and not line.startswith("=== ["):
                    total += 1
                    if len(hits) < SEARCH_MAX_HITS:
                        s = line.strip()
                        if len(s) > 300:
                            k = s.lower().find(ql)
                            s = ("…" if k > 120 else "") + s[max(0, k - 120):k + 180] + "…"
                        hits.append(f"{path} | {Matter.anchor_at(text, off)} | offset {off} | {s}")
                off += len(line)
        more = f" (showing first {SEARCH_MAX_HITS}; narrow the query or path_glob)" if total > SEARCH_MAX_HITS else ""
        return f"{total} hits for {q!r} in {glob!r}{more}\n" + "\n".join(hits), False
    if name == "save_note":
        key = str(args.get("key", "")).strip()
        if not key:
            raise ToolError("key is empty")
        ws.notes[key] = str(args.get("text", ""))
        ws.save()
        return f"note {key!r} saved ({len(ws.notes[key])} chars; {len(ws.notes)} notes)", False
    if name == "read_notes":
        if not ws.notes:
            return "no notes saved", False
        return "\n\n".join(f"## {k}\n{v}" for k, v in ws.notes.items()), False
    if name == "write_section":
        sid = str(args.get("section_id", "")).strip()
        if not sid:
            raise ToolError("section_id is empty")
        replaced = sid in ws.sections
        ws.sections[sid] = str(args.get("markdown", ""))
        ws.save()
        return (f"section {sid!r} {'replaced' if replaced else 'written'} ({len(ws.sections[sid])} chars); "
                f"draft has {len(ws.sections)} sections, {len(ws.assemble())} chars"), False
    if name == "read_draft":
        sid = args.get("section_id")
        if sid:
            if sid not in ws.sections:
                raise ToolError(f"no section {sid!r}; sections: {list(ws.sections)}")
            return ws.sections[sid], False
        if not ws.sections:
            return "draft is empty", False
        return "\n".join(f"{k}: {len(v)} chars" for k, v in ws.sections.items()), False
    if name == "finish":
        return "finished", True
    raise ToolError(f"unknown tool {name!r}")


SEARCH_MAX_HITS = 25


# --------------------------------------------------------------------------- tokens and context

class TokenCounter:
    def __init__(self, path: Path) -> None:
        from tokenizers import Tokenizer
        self.tok = Tokenizer.from_file(str(path))

    def n(self, s: str) -> int:
        return len(self.tok.encode(s, add_special_tokens=False).ids) if s else 0

    def message(self, m: dict) -> int:
        t = MSG_OVERHEAD_TOKENS + self.n(m.get("content") or "") + self.n(m.get("reasoning_content") or "")
        for tc in m.get("tool_calls") or []:
            t += self.n(tc["function"]["name"]) + self.n(tc["function"]["arguments"]) + MSG_OVERHEAD_TOKENS
        return t


def elidable(messages: list[dict], keep_recent: int) -> list[tuple[int, str]]:
    """(message index, field) pairs that may be stubbed, oldest first. Index 0/1 (system, task) are never elided."""
    out: list[tuple[int, str]] = []
    last = len(messages) - keep_recent
    for i, m in enumerate(messages[2:last], start=2):
        if m.get("_elided"):
            continue
        if m["role"] == "tool" and len(m.get("content") or "") >= STUB_MIN_CHARS:
            out.append((i, "content"))
        if m["role"] == "assistant":
            if len(m.get("reasoning_content") or "") >= STUB_MIN_CHARS:
                out.append((i, "reasoning_content"))
            for k, tc in enumerate(m.get("tool_calls") or []):
                if tc["function"]["name"] in ("write_section", "save_note") and len(tc["function"]["arguments"]) >= STUB_MIN_CHARS:
                    out.append((i, f"tool_calls.{k}"))
    return out


def stub_item(messages: list[dict], i: int, fld: str) -> dict:
    """Replace one item with a one-line stub in place; returns the edit record for the transcript."""
    m = messages[i]
    if fld == "content":
        old = m["content"]
        first = old.splitlines()[0][:200] if old else ""
        m["content"] = f"[elided to save context: tool output of {len(old)} chars; it began: {first}]"
    elif fld == "reasoning_content":
        old = m["reasoning_content"]
        m["reasoning_content"] = f"[earlier reasoning of {len(old)} chars elided]"
    else:
        k = int(fld.split(".")[1])
        fn = m["tool_calls"][k]["function"]
        args = json.loads(fn["arguments"])
        big = "markdown" if fn["name"] == "write_section" else "text"
        n = len(str(args.get(big, "")))
        args[big] = f"[elided: {n} chars, persisted; use read_draft / read_notes]"
        old = fn["arguments"]
        fn["arguments"] = json.dumps(args, ensure_ascii=False)
    return {"index": i, "field": fld, "old_chars": len(old), "new": _get(messages[i], fld)}


def _get(m: dict, fld: str) -> str:
    if fld.startswith("tool_calls."):
        return m["tool_calls"][int(fld.split(".")[1])]["function"]["arguments"]
    return m[fld]


def _set(m: dict, fld: str, val: str) -> None:
    if fld.startswith("tool_calls."):
        m["tool_calls"][int(fld.split(".")[1])]["function"]["arguments"] = val
    else:
        m[fld] = val


def wire_messages(messages: list[dict]) -> list[dict]:
    return [{k: v for k, v in m.items() if not k.startswith("_")} for m in messages]


# --------------------------------------------------------------------------- HTTP

def post_json(url: str, body: dict, timeout_s: float) -> dict:
    data = json.dumps(body, ensure_ascii=False).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout_s) as r:
        return json.loads(r.read())


def preflight(base_url: str, model: str) -> dict:
    """Render one turn through /tokenize + /detokenize (no generation) and require the effort-50 prefix."""
    root = base_url.rstrip("/")
    root = root[:-3] if root.endswith("/v1") else root
    def render(kw: dict) -> str:
        out = post_json(root + "/tokenize", {"model": model, "messages": [{"role": "user", "content": "preflight"}],
                                             "add_generation_prompt": True, "chat_template_kwargs": kw}, 60)
        ids = out.get("tokens")
        if not isinstance(ids, list) or not ids:
            raise RuntimeError(f"/tokenize returned no tokens (keys {sorted(out)})")
        text = post_json(root + "/detokenize", {"model": model, "tokens": ids}, 60).get("prompt")
        if not isinstance(text, str):
            raise RuntimeError("/detokenize returned no prompt text")
        return text
    on, off = render(THINK_ON), render({"thinking": False})
    if EFFORT_MARK not in on or EFFORT_MARK in off or on == off:
        raise RuntimeError(f"EFFORT-PREFLIGHT FAIL: on tail {on[-200:]!r} | off tail {off[-120:]!r}")
    return {"effort": EFFORT, "mark": EFFORT_MARK}


def smoke(base_url: str, model: str, seed: int) -> dict:
    """One generation request with the real tools and thinking settings: the server must answer with a tool call,
    with the reasoning in its own field (a reasoning parser is on) and none of it inside content."""
    body = {"model": model, "temperature": 1.0, "top_p": 1.0, "max_tokens": 4096, "seed": seed, "tools": TOOLS,
            "tool_choice": "auto", "chat_template_kwargs": dict(THINK_ON),
            "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                         {"role": "user", "content": "Smoke test: call the list_files tool once, with no arguments."}]}
    resp = post_json(base_url.rstrip("/") + "/chat/completions", body, 900)
    msg = (resp.get("choices") or [{}])[0].get("message") or {}
    content = msg.get("content") or ""
    reasoning = msg.get("reasoning_content") or msg.get("reasoning") or ""
    tcs = msg.get("tool_calls") or []
    problems = []
    if not tcs:
        problems.append("no tool call (is --enable-auto-tool-choice with the DeepSeek tool parser on?)")
    if "<think>" in content or "</think>" in content:
        problems.append("reasoning inside content (no reasoning parser)")
    # Thinking is verified by the rendered prompt (preflight: "<think>" open + effort mark). On a trivial step the model
    # may close its thinking at once (MEASURED on the Sparks 2026-11-04: 0 reasoning chars at effort 50 and 75 with tools),
    # so an empty reasoning field cannot decide anything: reported as INCONCLUSIVE, never pass or fail. The run's
    # run.json reasoning_tokens is the real measure.
    reasoning_check = "present" if reasoning else "INCONCLUSIVE: no reasoning on this trivial step (see run.json reasoning_tokens)"
    for tc in tcs:
        try:
            json.loads(tc["function"].get("arguments") or "{}")
        except ValueError:
            problems.append(f"tool-call arguments are not JSON: {tc['function'].get('arguments')!r}")
    out = {"tool_calls": [tc["function"]["name"] for tc in tcs], "reasoning_chars": len(reasoning),
           "reasoning_check": reasoning_check,
           "content_chars": len(content), "usage": resp.get("usage"), "problems": problems}
    if problems:
        raise RuntimeError("SMOKE FAIL: " + json.dumps(out))
    return out


# --------------------------------------------------------------------------- run loop

@dataclass
class Stats:
    turns: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    cached_prompt_tokens: int = 0
    max_prompt_tokens: int = 0
    tool_calls: dict[str, int] = field(default_factory=dict)
    tool_errors: int = 0
    bad_json_args: int = 0
    no_tool_call_replies: int = 0
    length_truncations: int = 0
    elisions: int = 0
    elision_passes: int = 0
    est_ratio_max: float = 1.0


def run(a: argparse.Namespace) -> int:
    run_dir = a.runs / a.label
    if run_dir.exists() and any(run_dir.iterdir()):
        raise SystemExit(f"run directory {run_dir} exists and is not empty; pick a new --label")
    run_dir.mkdir(parents=True, exist_ok=True)
    matter = Matter(a.matter, a.read_max_chars)
    task = a.task.read_text(encoding="utf-8")
    tok = TokenCounter(a.tokenizer)
    ws = Workspace(run_dir)
    ws.save()
    tools_tokens = tok.n(json.dumps(TOOLS))
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": task}]
    params = {"model": a.model, "temperature": a.temperature, "top_p": a.top_p, "max_tokens": a.max_tokens,
              "seed": a.seed, "tools": TOOLS, "tool_choice": "auto",
              "chat_template_kwargs": dict(THINK_ON)}
    st = Stats()
    gate = None
    gate_wait = 0.0
    if a.gate != "none":
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import kit_gate
        root = a.base_url.rstrip("/")
        gate = kit_gate.Gate(a.gate, root[:-3] if root.endswith("/v1") else root, str(run_dir / "gate.jsonl"),
                             hold_cmd=a.gate_hold_cmd or kit_gate.DGX_HOLD_CMD, poll_s=a.gate_poll)
    t0 = time.monotonic()
    started = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    tlog = open(run_dir / "transcript.jsonl", "w", encoding="utf-8")
    sent_upto = 0  # messages already recorded in the transcript
    outcome: RunOutcome

    def log(rec: dict) -> None:
        tlog.write(json.dumps(rec, ensure_ascii=False) + "\n")
        tlog.flush()

    def est_prompt() -> int:
        return tools_tokens + sum(tok.message(m) for m in messages)

    try:
        while True:
            if st.turns >= a.max_turns:
                outcome = Timeout("turns", f"{st.turns} turns reached --max-turns {a.max_turns}")
                break
            remaining = a.wall_s - (time.monotonic() - t0 - gate_wait)
            if remaining <= 0:
                outcome = Timeout("wall", f"{a.wall_s}s wall-clock limit reached before turn {st.turns + 1}")
                break
            # context budget
            edits: list[dict] = []
            est = est_prompt()
            limit = a.ctx_budget - a.max_tokens
            if est * st.est_ratio_max > limit:
                st.elision_passes += 1
                target = int(a.elide_to * a.ctx_budget) - a.max_tokens
                for i, fld in elidable(messages, a.keep_recent):
                    if est * st.est_ratio_max <= target:
                        break
                    before = tok.message(messages[i])
                    edits.append(stub_item(messages, i, fld))
                    if fld == "content":
                        messages[i]["_elided"] = True
                    est += tok.message(messages[i]) - before
                    st.elisions += 1
                if est * st.est_ratio_max > limit:
                    outcome = ContextExhausted(int(est * st.est_ratio_max), limit)
                    log({"event": "context_exhausted", "turn": st.turns + 1, "est": est, "limit": limit,
                         "edits": edits})
                    break
            if gate is not None:
                gate_wait += gate.wait_idle(f"turn {st.turns + 1}")
            body = dict(params, messages=wire_messages(messages))
            body_bytes = json.dumps(body, ensure_ascii=False, sort_keys=True).encode()
            rec: dict = {"event": "request", "turn": st.turns + 1, "t": round(time.monotonic() - t0, 3),
                         "sha256": hashlib.sha256(body_bytes).hexdigest(), "est_prompt_tokens": est}
            if st.turns == 0:
                rec["body"] = body
            else:
                rec["edits"] = edits
                rec["append"] = wire_messages(messages[sent_upto:])
            log(rec)
            sent_upto = len(messages)
            timeout_s = min(a.request_timeout, max(1.0, remaining))
            t_req = time.monotonic()
            try:
                resp = post_json(a.base_url.rstrip("/") + "/chat/completions", body, timeout_s)
            except (socket.timeout, TimeoutError) as e:
                if timeout_s < a.request_timeout:
                    raise WallClockExpired(f"wall-clock limit reached during turn {st.turns + 1}") from e
                outcome = Error("network", f"request timed out after {a.request_timeout}s on turn {st.turns + 1}")
                log({"event": "error", "turn": st.turns + 1, "detail": outcome.detail})
                break
            except urllib.error.HTTPError as e:
                detail = e.read().decode(errors="replace")[:2000]
                outcome = Error("http", f"HTTP {e.code} on turn {st.turns + 1}: {detail}")
                log({"event": "error", "turn": st.turns + 1, "detail": outcome.detail})
                break
            except urllib.error.URLError as e:
                if isinstance(e.reason, (socket.timeout, TimeoutError)) and timeout_s < a.request_timeout:
                    raise WallClockExpired(f"wall-clock limit reached during turn {st.turns + 1}") from e
                outcome = Error("network", f"{e.reason} on turn {st.turns + 1}")
                log({"event": "error", "turn": st.turns + 1, "detail": outcome.detail})
                break
            st.turns += 1
            log({"event": "response", "turn": st.turns, "t": round(time.monotonic() - t0, 3),
                 "latency_s": round(time.monotonic() - t_req, 3), "body": resp})
            usage = resp.get("usage") or {}
            pt = int(usage.get("prompt_tokens") or 0)
            st.prompt_tokens += pt
            st.completion_tokens += int(usage.get("completion_tokens") or 0)
            st.reasoning_tokens += int((usage.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0)
            st.cached_prompt_tokens += int((usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0)
            st.max_prompt_tokens = max(st.max_prompt_tokens, pt)
            if pt and est:
                st.est_ratio_max = max(st.est_ratio_max, pt / est)
            choices = resp.get("choices")
            if not choices:
                outcome = Error("protocol", f"response without choices on turn {st.turns}: {str(resp)[:500]}")
                break
            ch = choices[0]
            msg = ch.get("message") or {}
            reasoning = msg.get("reasoning_content") or msg.get("reasoning") or ""
            content = msg.get("content") or ""
            tcs = msg.get("tool_calls") or []
            am: dict = {"role": "assistant", "content": content}
            if reasoning:
                am["reasoning_content"] = reasoning
            if tcs:
                am["tool_calls"] = [{"id": tc["id"], "type": "function",
                                     "function": {"name": tc["function"]["name"],
                                                  "arguments": tc["function"].get("arguments") or "{}"}} for tc in tcs]
            messages.append(am)
            if not tcs:
                st.no_tool_call_replies += 1
                if ch.get("finish_reason") == "length":
                    st.length_truncations += 1
                    nudge = ("Your previous reply reached the output token limit before any tool call. Continue the "
                             "task using the tools; write long sections in several write_section calls if needed.")
                else:
                    nudge = ("Continue the task using the tools. Only text written with write_section is delivered; "
                             "call finish when the deliverable is complete.")
                messages.append({"role": "user", "content": nudge})
                continue
            done = False
            summary = ""
            for tc in am["tool_calls"]:
                name = tc["function"]["name"]
                st.tool_calls[name] = st.tool_calls.get(name, 0) + 1
                try:
                    args = json.loads(tc["function"]["arguments"] or "{}")
                    if not isinstance(args, dict):
                        raise ValueError("arguments must be a JSON object")
                except ValueError as e:
                    st.bad_json_args += 1
                    st.tool_errors += 1
                    result = f"error: arguments are not a valid JSON object ({e}); call the tool again"
                else:
                    try:
                        result, fin = run_tool(name, args, matter, ws)
                        if fin:
                            done = True
                            summary = str(args.get("summary") or "")
                    except ToolError as e:
                        st.tool_errors += 1
                        result = f"error: {e}"
                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
            if done:
                outcome = Finished(summary)
                break
    except WallClockExpired as e:
        outcome = Timeout("wall", str(e))
    except OSError as e:
        outcome = Error("io", f"{type(e).__name__}: {e}")
    finally:
        ws.save()
        (run_dir / "master_file.md").write_text(ws.assemble(), encoding="utf-8")
    log({"event": "end", **asdict(outcome)})
    tlog.close()
    wall = time.monotonic() - t0
    rj = {
        "label": a.label, "harness": HARNESS_VERSION,
        "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "matter_inventory_sha256": matter.inventory_sha,
        "base_url": a.base_url, "model": a.model, "started": started,
        "args": {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(a).items()},
        "outcome": outcome.outcome, "outcome_detail": asdict(outcome),
        "turns": st.turns, "wall_s": round(wall, 1), "gate": a.gate, "gate_wait_s": round(gate_wait, 1),
        "tokens_in": st.prompt_tokens, "tokens_out": st.completion_tokens,
        "reasoning_tokens": st.reasoning_tokens, "cached_prompt_tokens": st.cached_prompt_tokens,
        "max_prompt_tokens": st.max_prompt_tokens, "est_ratio_max": round(st.est_ratio_max, 4),
        "tool_calls": st.tool_calls, "tool_calls_total": sum(st.tool_calls.values()),
        "tool_errors": st.tool_errors, "bad_json_args": st.bad_json_args,
        "no_tool_call_replies": st.no_tool_call_replies, "length_truncations": st.length_truncations,
        "elisions": st.elisions, "elision_passes": st.elision_passes,
        "draft_sections": len(ws.sections), "notes": len(ws.notes),
        "master_file_chars": len(ws.assemble()),
    }
    (run_dir / "run.json").write_text(json.dumps(rj, indent=1, ensure_ascii=False))
    print(json.dumps({k: rj[k] for k in ("label", "outcome", "turns", "wall_s", "tokens_in", "tokens_out",
                                          "tool_calls_total", "draft_sections", "master_file_chars")}))
    return 0 if outcome.outcome == "FINISHED" else 2


def replay(path: Path, turn: int) -> dict:
    """Rebuild the exact request body of `turn` from a transcript and check it against the logged sha256."""
    body: dict | None = None
    msgs: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        if rec.get("event") != "request":
            continue
        if rec["turn"] == 1:
            body = copy.deepcopy(rec["body"])
            msgs = body["messages"]
        else:
            if body is None:
                raise RuntimeError("transcript lacks the turn-1 request")
            # appended messages are logged in their post-edit state, so extend first, then apply the edits
            # (an edit to a just-appended message is then a no-op re-set to the same value)
            msgs.extend(copy.deepcopy(rec["append"]))
            for e in rec["edits"]:
                _set(msgs[e["index"]], e["field"], e["new"])
        if rec["turn"] == turn:
            assert body is not None
            body["messages"] = msgs
            got = hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
            if got != rec["sha256"]:
                raise RuntimeError(f"replay sha256 mismatch on turn {turn}: {got} != {rec['sha256']}")
            return body
    raise RuntimeError(f"turn {turn} not in transcript")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", help="OpenAI-compatible root including /v1")
    ap.add_argument("--model")
    ap.add_argument("--label")
    ap.add_argument("--matter", type=Path)
    ap.add_argument("--task", type=Path, help="prompt.md of the case (sent verbatim)")
    ap.add_argument("--runs", type=Path)
    ap.add_argument("--tokenizer", type=Path, help="the served model's tokenizer.json")
    ap.add_argument("--ctx-budget", type=int, default=131072,
                    help="prompt + max_tokens ceiling, one value for both builds. Default 131072 = 40%% of the "
                         "smaller server limit (Sparks 327,680; V100 524,288), so completion + thinking always fit")
    ap.add_argument("--max-tokens", type=int, default=16384)
    ap.add_argument("--max-turns", type=int)
    ap.add_argument("--wall-s", type=float)
    ap.add_argument("--seed", type=int)
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--top-p", type=float, default=1.0)
    ap.add_argument("--read-max-chars", type=int, default=16000)
    ap.add_argument("--keep-recent", type=int, default=6)
    ap.add_argument("--elide-to", type=float, default=0.6, help="after an elision pass the prompt is under this x budget")
    ap.add_argument("--request-timeout", type=float, default=1800)
    ap.add_argument("--gate", choices=["none", "dgx"], default="none",
                    help="dgx: the kit's idle gate before every request (Sparks etiquette)")
    ap.add_argument("--gate-poll", type=float, default=30.0)
    ap.add_argument("--gate-hold-cmd", help="override the kit's ssh hold-file check (tests point it at a local dir)")
    ap.add_argument("--preflight", action="store_true", help="check the effort-50 render via /tokenize, then exit")
    ap.add_argument("--smoke", action="store_true", help="one tool-call request (generation) to check the server, then exit")
    ap.add_argument("--replay", type=Path, help="transcript.jsonl to rebuild a request from")
    ap.add_argument("--turn", type=int, default=1)
    a = ap.parse_args()
    if a.replay:
        print(json.dumps(replay(a.replay, a.turn), ensure_ascii=False))
        return 0
    if a.smoke:
        if not (a.base_url and a.model):
            ap.error("--smoke needs --base-url and --model")
        print(json.dumps(smoke(a.base_url, a.model, a.seed or 0)))
        return 0
    if a.preflight:
        if not (a.base_url and a.model):
            ap.error("--preflight needs --base-url and --model")
        print(json.dumps(preflight(a.base_url, a.model)))
        return 0
    need = ["base_url", "model", "label", "matter", "task", "runs", "tokenizer", "max_turns", "wall_s", "seed"]
    missing = [n for n in need if getattr(a, n) is None]
    if missing:
        ap.error("missing required arguments: " + ", ".join("--" + m.replace("_", "-") for m in missing))
    if a.max_tokens >= a.ctx_budget:
        ap.error("--max-tokens must be below --ctx-budget")
    if a.ctx_budget > SMALLEST_SERVER_LIMIT:
        ap.error(f"--ctx-budget {a.ctx_budget} exceeds the smaller server limit {SMALLEST_SERVER_LIMIT} (Sparks)")
    return run(a)


if __name__ == "__main__":
    sys.exit(main())
