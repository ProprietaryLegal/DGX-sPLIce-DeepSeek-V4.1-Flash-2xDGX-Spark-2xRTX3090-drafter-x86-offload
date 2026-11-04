#!/usr/bin/env python3
"""extract_matter.py: convert every file of the BAR matter folder to anchored text, once, at the boundary.

    venv/bin/python -I harness/extract_matter.py --case case --out matter --ocr-cache ocr --tessdata tessdata

Each input file becomes <out>/<relative path>.md (the original extension is kept in the name, so
"X.docx" and "X.pdf" never collide). Every unit carries an anchor line the agent's search tool reports:

    pdf   === [page N] ===
    pptx  === [slide N] ===          (shape text with its box @(left,top wxh in), lines, tables, charts,
                                       connector edges, then speaker notes)
    xlsx  === [sheet: Name] ===      (cell-value table, then the formulas with their cached values; a workbook
                                       whose formulas carry no cached values is recalculated by headless
                                       LibreOffice into <recalc-cache> first, and that is noted)
    docx  === [section: Heading] === (body in order, tables as markdown; then headers/footers, footnotes, comments)

Grey-italic runs (template instruction / placeholder text) are wrapped as [[GREY-ITALIC: ...]].

PDF text-layer policy (typed, per file):
    NATIVE      more than half the pages carry a text layer (>= LOW_TEXT_CHARS chars): the text layer is used;
                any page that is low-text AND carries an image is OCR'd on its own (page-level OCR) and marked.
    OCR         half or more of the pages are low-text: the whole file is rasterised and OCR'd with ocrmypdf
                --force-ocr into <ocr-cache>/<relative path> (reused when newer than the source), then read.
A file that cannot be read, or an OCR that fails, is an outcome (FAILED / NEEDS_OCR_BLOCKED), printed loudly
and written to the inventory; the script exits 1 if any file ends that way. Nothing is skipped silently.

Writes <out>/_inventory.jsonl and <out>/_inventory.md (per file: kind, outcome, text source, units, chars,
DeepSeek tokens counted with the local tokenizer, low-text units).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import subprocess
import sys
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Literal, Union

from lxml import etree

LOW_TEXT_CHARS = 50
# Explicit OCR language per file-name prefix. The French SAS statutory accounts need the French model;
# everything else in the matter is English.
OCR_LANG_BY_PREFIX: dict[str, str] = {"Freshworks SAS": "fra+eng"}
DEFAULT_OCR_LANG = "eng"
OCR_JOBS = 24

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"


def wq(tag: str) -> str:
    return f"{{{W}}}{tag}"


# --------------------------------------------------------------------------- outcome types

@dataclass(frozen=True)
class Extracted:
    text_source: Literal["native", "ocr", "native+page-ocr"]
    units: int
    unit_name: Literal["page", "slide", "sheet", "section"]
    chars: int
    tokens: int
    low_text_units: list[int]
    notes: list[str]
    outcome: Literal["EXTRACTED"] = "EXTRACTED"


@dataclass(frozen=True)
class NeedsOcrBlocked:
    reason: str
    outcome: Literal["NEEDS_OCR_BLOCKED"] = "NEEDS_OCR_BLOCKED"


@dataclass(frozen=True)
class Failed:
    error: str
    outcome: Literal["FAILED"] = "FAILED"


FileOutcome = Union[Extracted, NeedsOcrBlocked, Failed]


@dataclass
class Doc:
    """Text being built for one file, plus facts the inventory needs."""
    parts: list[str] = field(default_factory=list)
    units: int = 0
    low: list[int] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def add(self, s: str) -> None:
        self.parts.append(s)

    def text(self) -> str:
        return "\n".join(self.parts).rstrip() + "\n"


class Counter:
    """DeepSeek token counter from the local tokenizer.json (fails loudly if it is missing)."""

    def __init__(self, path: Path) -> None:
        from tokenizers import Tokenizer
        self.tok = Tokenizer.from_file(str(path))

    def __call__(self, text: str) -> int:
        return len(self.tok.encode(text, add_special_tokens=False).ids)


# --------------------------------------------------------------------------- PDF

def ocr_lang_for(rel: Path) -> str:
    for prefix, lang in OCR_LANG_BY_PREFIX.items():
        if rel.name.startswith(prefix):
            return lang
    return DEFAULT_OCR_LANG


def run_ocrmypdf(src: Path, dst: Path, lang: str, tessdata: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, TESSDATA_PREFIX=str(tessdata))
    cmd = ["ocrmypdf", "--force-ocr", "--rotate-pages", "-l", lang, "--jobs", str(OCR_JOBS),
           "--output-type", "pdf", "--optimize", "0", str(src), str(dst)]
    p = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"ocrmypdf exit {p.returncode}: {p.stderr.strip()[-800:]}")


def extract_pdf(src: Path, rel: Path, ocr_cache: Path, tessdata: Path, ocr: bool) -> tuple[Doc, str] | NeedsOcrBlocked:
    import pymupdf
    d = pymupdf.open(src)
    texts = [pg.get_text() for pg in d]
    low = [i for i, t in enumerate(texts) if len(t.strip()) < LOW_TEXT_CHARS]
    doc = Doc()
    if len(low) * 2 >= len(texts):
        lang = ocr_lang_for(rel)
        out = ocr_cache / rel
        if not (out.exists() and out.stat().st_mtime >= src.stat().st_mtime):
            if not ocr:
                return NeedsOcrBlocked(f"{len(low)}/{len(texts)} pages have no text layer; run without --no-ocr")
            print(f"  OCR ({lang}, {len(texts)} pages): {rel}", flush=True)
            run_ocrmypdf(src, out, lang, tessdata)
        d = pymupdf.open(out)
        texts = [pg.get_text() for pg in d]
        source = "ocr"
        doc.notes.append(f"whole file OCR'd: ocrmypdf --force-ocr -l {lang}; {len(low)}/{len(texts)} pages had no text layer")
        doc.low = [i + 1 for i, t in enumerate(texts) if len(t.strip()) < LOW_TEXT_CHARS]
    else:
        source = "native"
        tessdata_s = str(tessdata)
        for i in low:
            pg = d[i]
            if pg.get_images():
                tp = pg.get_textpage_ocr(language=ocr_lang_for(rel), dpi=300, full=True, tessdata=tessdata_s)
                t = pg.get_text(textpage=tp)
                texts[i] = "[page-level OCR: this page has no text layer]\n" + t
                source = "native+page-ocr"
                doc.notes.append(f"page {i + 1}: page-level OCR ({len(t.strip())} chars)")
            if len(texts[i].strip()) < LOW_TEXT_CHARS:
                doc.low.append(i + 1)
    for i, t in enumerate(texts):
        doc.add(f"=== [page {i + 1}] ===")
        doc.add(t.rstrip())
        doc.add("")
    doc.units = len(texts)
    return doc, source


# --------------------------------------------------------------------------- DOCX

class Styles:
    """Effective italic / colour through the run style, paragraph style and basedOn chains."""

    def __init__(self, root: etree._Element | None) -> None:
        self.by_id: dict[str, etree._Element] = {}
        self.default_rpr: etree._Element | None = None
        self.heading_level: dict[str, int] = {}
        if root is None:
            return
        for st in root.iter(wq("style")):
            sid = st.get(wq("styleId"))
            if sid:
                self.by_id[sid] = st
                name_el = st.find(wq("name"))
                name = (name_el.get(wq("val")) if name_el is not None else sid).lower()
                m = re.fullmatch(r"heading (\d)", name)
                if m:
                    self.heading_level[sid] = int(m.group(1))
                elif name == "title":
                    self.heading_level[sid] = 1
                ol = st.find(f"{wq('pPr')}/{wq('outlineLvl')}")
                if ol is not None and sid not in self.heading_level:
                    self.heading_level[sid] = int(ol.get(wq("val"))) + 1
        dd = root.find(f"{wq('docDefaults')}/{wq('rPrDefault')}/{wq('rPr')}")
        self.default_rpr = dd

    def _chain(self, sid: str | None) -> list[etree._Element]:
        out: list[etree._Element] = []
        seen: set[str] = set()
        while sid and sid in self.by_id and sid not in seen:
            seen.add(sid)
            st = self.by_id[sid]
            rpr = st.find(wq("rPr"))
            if rpr is not None:
                out.append(rpr)
            b = st.find(wq("basedOn"))
            sid = b.get(wq("val")) if b is not None else None
        return out

    def run_props(self, r: etree._Element, p_style: str | None) -> tuple[bool, str | None]:
        rpr = r.find(wq("rPr"))
        rstyle = None
        if rpr is not None:
            rs = rpr.find(wq("rStyle"))
            rstyle = rs.get(wq("val")) if rs is not None else None
        layers = ([rpr] if rpr is not None else []) + self._chain(rstyle) + self._chain(p_style)
        if self.default_rpr is not None:
            layers.append(self.default_rpr)
        italic: bool | None = None
        color: str | None = None
        for lay in layers:
            if italic is None:
                i = lay.find(wq("i"))
                if i is not None:
                    italic = i.get(wq("val"), "true") not in ("0", "false", "off")
            if color is None:
                c = lay.find(wq("color"))
                if c is not None and c.get(wq("val")):
                    color = c.get(wq("val"))
        return bool(italic), color


def is_grey(color: str | None) -> bool:
    if not color or not re.fullmatch(r"[0-9A-Fa-f]{6}", color):
        return False
    r, g, b = (int(color[i:i + 2], 16) for i in (0, 2, 4))
    return max(r, g, b) - min(r, g, b) <= 12 and 0x30 <= r <= 0xD8


class DocxReader:
    def __init__(self, z: zipfile.ZipFile) -> None:
        self.z = z
        names = set(z.namelist())
        self.styles = Styles(etree.fromstring(z.read("word/styles.xml")) if "word/styles.xml" in names else None)
        self.grey_runs = 0
        self.deleted_runs = 0
        self.table_no = 0

    def para_text(self, p: etree._Element) -> str:
        ppr = p.find(wq("pPr"))
        p_style = None
        if ppr is not None:
            ps = ppr.find(wq("pStyle"))
            p_style = ps.get(wq("val")) if ps is not None else None
        pieces: list[tuple[bool, str]] = []  # (grey_italic, text)

        def walk(el: etree._Element) -> None:
            for ch in el:
                tag = etree.QName(ch).localname if isinstance(ch.tag, str) else ""
                ns = etree.QName(ch).namespace if isinstance(ch.tag, str) else ""
                if ns == MC and tag == "Fallback":
                    continue  # duplicate of mc:Choice content
                if ns == W and tag == "del":
                    self.deleted_runs += 1
                    continue
                if ns == W and tag == "r":
                    gi = False
                    it, col = self.styles.run_props(ch, p_style)
                    if it and is_grey(col):
                        gi = True
                    buf: list[str] = []
                    for rc in ch:
                        rt = etree.QName(rc).localname if isinstance(rc.tag, str) else ""
                        if rt == "t":
                            buf.append(rc.text or "")
                        elif rt == "tab":
                            buf.append("\t")
                        elif rt in ("br", "cr"):
                            if rc.get(wq("type")) != "page":
                                buf.append("\n")
                        elif rt == "noBreakHyphen":
                            buf.append("-")
                        elif rt == "sym":
                            buf.append("?")
                        elif rt == "footnoteReference":
                            buf.append(f"[^fn{rc.get(wq('id'))}]")
                        elif rt == "endnoteReference":
                            buf.append(f"[^en{rc.get(wq('id'))}]")
                        elif rt == "commentReference":
                            pass
                        elif rt in ("drawing", "pict", "AlternateContent", "object"):
                            tb = [self.para_text(tp) for tp in rc.iter(wq("p"))
                                  if not any(etree.QName(a).namespace == MC and etree.QName(a).localname == "Fallback"
                                             for a in tp.iterancestors())]
                            tb = [t for t in tb if t.strip()]
                            if tb:
                                buf.append(" [text box: " + " / ".join(tb) + "] ")
                    if buf:
                        pieces.append((gi, "".join(buf)))
                        if gi:
                            self.grey_runs += 1
                    continue
                if ns == W and tag == "commentRangeStart":
                    pieces.append((False, f"[comment {ch.get(wq('id'))}: "))
                    continue
                if ns == W and tag == "commentRangeEnd":
                    pieces.append((False, "]"))
                    continue
                if ns == W and tag in ("pPr", "rPr"):
                    continue
                walk(ch)  # hyperlink, ins, smartTag, sdt, sdtContent, fldSimple, mc:AlternateContent/Choice ...

        walk(p)
        out: list[str] = []
        for gi, group in _group(pieces):
            out.append(f"[[GREY-ITALIC: {group}]]" if gi and group.strip() else group)
        return "".join(out)

    def heading_level(self, p: etree._Element) -> int | None:
        ppr = p.find(wq("pPr"))
        if ppr is None:
            return None
        ps = ppr.find(wq("pStyle"))
        if ps is not None and ps.get(wq("val")) in self.styles.heading_level:
            return self.styles.heading_level[ps.get(wq("val"))]
        ol = ppr.find(wq("outlineLvl"))
        if ol is not None and int(ol.get(wq("val"))) < 9:
            return int(ol.get(wq("val"))) + 1
        return None

    def is_list(self, p: etree._Element) -> bool:
        return p.find(f"{wq('pPr')}/{wq('numPr')}") is not None

    def block_items(self, container: etree._Element) -> list[etree._Element]:
        out: list[etree._Element] = []
        for ch in container:
            if not isinstance(ch.tag, str):
                continue
            if ch.tag in (wq("p"), wq("tbl")):
                out.append(ch)
            elif ch.tag in (wq("sdt"),):
                c = ch.find(wq("sdtContent"))
                if c is not None:
                    out.extend(self.block_items(c))
            elif ch.tag in (wq("customXml"),):
                out.extend(self.block_items(ch))
        return out

    def table_md(self, tbl: etree._Element) -> list[str]:
        self.table_no += 1
        rows: list[list[str]] = []
        for tr in tbl.iter(wq("tr")):
            if next(tr.iterancestors(wq("tbl"))) is not tbl:
                continue  # rows of a nested table are rendered inside their cell
            row: list[str] = []
            for tc in tr.findall(wq("tc")):
                cell_parts: list[str] = []
                for b in self.block_items(tc):
                    if b.tag == wq("p"):
                        t = self.para_text(b).strip()
                        if t:
                            cell_parts.append(t)
                    else:
                        cell_parts.append("[nested table: " + " ; ".join(self.table_md(b)) + "]")
                text = "<br>".join(cell_parts).replace("|", "\\|").replace("\n", "<br>")
                vm = tc.find(f"{wq('tcPr')}/{wq('vMerge')}")
                if vm is not None and vm.get(wq("val")) != "restart" and not text:
                    text = "(merged above)"
                row.append(text)
                gs = tc.find(f"{wq('tcPr')}/{wq('gridSpan')}")
                if gs is not None:
                    row.extend([""] * (int(gs.get(wq("val"))) - 1))
            rows.append(row)
        if not rows:
            return [f"[Table {self.table_no}: empty]"]
        width = max(len(r) for r in rows)
        rows = [r + [""] * (width - len(r)) for r in rows]
        md = [f"[Table {self.table_no}]", "| " + " | ".join(rows[0]) + " |", "|" + "---|" * width]
        md += ["| " + " | ".join(r) + " |" for r in rows[1:]]
        return md

    def render_blocks(self, container: etree._Element, doc: Doc, anchors: bool) -> None:
        for b in self.block_items(container):
            if b.tag == wq("tbl"):
                doc.add("")
                doc.parts.extend(self.table_md(b))
                doc.add("")
                continue
            text = self.para_text(b)
            lvl = self.heading_level(b)
            if lvl is not None and text.strip():
                if anchors:
                    doc.units += 1
                    doc.add("")
                    doc.add(f"=== [section: {text.strip()}] ===")
                doc.add("#" * min(lvl, 6) + " " + text.strip())
            elif text.strip():
                doc.add(("- " if self.is_list(b) else "") + text)
            else:
                doc.add("")

    def part_root(self, name: str) -> etree._Element | None:
        return etree.fromstring(self.z.read(name)) if name in self.z.namelist() else None


def _group(pieces: list[tuple[bool, str]]) -> list[tuple[bool, str]]:
    out: list[tuple[bool, str]] = []
    for gi, t in pieces:
        if out and out[-1][0] == gi:
            out[-1] = (gi, out[-1][1] + t)
        else:
            out.append((gi, t))
    return out


def extract_docx(src: Path) -> Doc:
    z = zipfile.ZipFile(src)
    rd = DocxReader(z)
    doc = Doc()
    body = etree.fromstring(z.read("word/document.xml")).find(wq("body"))
    doc.add("=== [section: (start of document)] ===")
    doc.units = 1
    rd.render_blocks(body, doc, anchors=True)
    hf = sorted(n for n in z.namelist() if re.fullmatch(r"word/(header|footer)\d*\.xml", n))
    if hf:
        doc.add("")
        doc.add("=== [headers and footers] ===")
        for n in hf:
            sub = Doc()
            rd.render_blocks(rd.part_root(n), sub, anchors=False)
            t = sub.text().strip()
            if t:
                doc.add(f"{Path(n).stem}: {t}")
    for part, label, kind in (("word/footnotes.xml", "footnotes", "footnote"), ("word/endnotes.xml", "endnotes", "endnote")):
        root = rd.part_root(part)
        if root is None:
            continue
        notes = [n for n in root.findall(wq(kind)) if n.get(wq("type")) in (None, "normal")]
        lines = []
        for n in notes:
            sub = Doc()
            rd.render_blocks(n, sub, anchors=False)
            t = " ".join(sub.text().split())
            if t:
                lines.append(f"[^{'fn' if kind == 'footnote' else 'en'}{n.get(wq('id'))}]: {t}")
        if lines:
            doc.add("")
            doc.add(f"=== [{label}] ===")
            doc.parts.extend(lines)
    root = rd.part_root("word/comments.xml")
    if root is not None:
        cs = root.findall(wq("comment"))
        if cs:
            doc.add("")
            doc.add("=== [comments] ===")
            for c in cs:
                sub = Doc()
                rd.render_blocks(c, sub, anchors=False)
                t = " ".join(sub.text().split())
                doc.add(f"comment {c.get(wq('id'))} ({c.get(wq('author'))}, {c.get(wq('date'))}): {t}")
            doc.notes.append(f"{len(cs)} comments")
    if rd.grey_runs:
        doc.notes.append(f"{rd.grey_runs} grey-italic runs marked")
    if rd.deleted_runs:
        doc.notes.append(f"{rd.deleted_runs} tracked deletions omitted")
    return doc


# --------------------------------------------------------------------------- PPTX

def _pos(sh) -> str:
    """Shape box in inches, so a chart's layout (who sits above whom) survives as text."""
    if sh.left is None or sh.top is None:
        return ""
    return f"@({sh.left / 914400:.2f},{sh.top / 914400:.2f} {sh.width / 914400:.2f}x{sh.height / 914400:.2f}in)"


def extract_pptx(src: Path) -> Doc:
    from pptx import Presentation
    from pptx.util import Emu  # noqa: F401  (python-pptx import check)
    prs = Presentation(str(src))
    doc = Doc()
    for sn, slide in enumerate(prs.slides, start=1):
        doc.add(f"=== [slide {sn}] ===")
        names: dict[str, str] = {}

        def shape_lines(shapes, depth: int) -> list[str]:
            out: list[str] = []
            for sh in shapes:
                ind = "  " * depth
                sid = str(sh.shape_id)
                if sh.shape_type is not None and sh.shape_type == 6:  # GROUP
                    out.append(f"{ind}[group {sh.name}]")
                    out.extend(shape_lines(sh.shapes, depth + 1))
                    continue
                pos = _pos(sh)
                if getattr(sh, "has_text_frame", False) and sh.has_text_frame:
                    t = "\n".join(p.text for p in sh.text_frame.paragraphs).strip()
                    if t:
                        names[sid] = " / ".join(x for x in t.splitlines() if x.strip())
                        out.append(f"{ind}- {t.replace(chr(10), chr(10) + ind + '  ')}  {pos}")
                geom = sh._element.find(f".//{{{A_NS}}}prstGeom")
                if (geom is not None and geom.get("prst") in ("line", "straightConnector1")) or sh._element.tag == f"{{{P_NS}}}cxnSp":
                    if sh.left is not None:
                        x1, y1 = sh.left / 914400, sh.top / 914400
                        x2, y2 = x1 + sh.width / 914400, y1 + sh.height / 914400
                        out.append(f"{ind}[line from ({x1:.2f},{y1:.2f}) to ({x2:.2f},{y2:.2f}) in]")
                if getattr(sh, "has_table", False) and sh.has_table:
                    rows = [[c.text.replace("|", "\\|").replace("\n", "<br>") for c in r.cells] for r in sh.table.rows]
                    if rows:
                        w = max(len(r) for r in rows)
                        out.append(f"{ind}[table {sh.name}]")
                        out.append(ind + "| " + " | ".join(rows[0]) + " |")
                        out.append(ind + "|" + "---|" * w)
                        out.extend(ind + "| " + " | ".join(r) + " |" for r in rows[1:])
                if getattr(sh, "has_chart", False) and sh.has_chart:
                    ch = sh.chart
                    title = ch.chart_title.text_frame.text if ch.has_title and ch.chart_title.has_text_frame else ""
                    out.append(f"{ind}[chart {sh.name}: {ch.chart_type} {title!r}]")
                    for plot in ch.plots:
                        cats = [str(c) for c in plot.categories]
                        out.append(f"{ind}  categories: {cats}")
                        for s in plot.series:
                            out.append(f"{ind}  series {s.name!r}: {list(s.values)}")
                if sh.shape_type == 13:  # PICTURE
                    out.append(f"{ind}[picture {sh.name}]")
            return out

        lines = shape_lines(slide.shapes, 0)
        # connector edges (org / legal structure charts): start shape -> end shape
        edges = []
        for cx in slide.shapes._spTree.iter(f"{{{P_NS}}}cxnSp"):
            st = cx.find(f".//{{{A_NS}}}stCxn")
            en = cx.find(f".//{{{A_NS}}}endCxn")
            if st is not None and en is not None:
                edges.append(f"  {names.get(st.get('id'), '#' + st.get('id'))}  -->  {names.get(en.get('id'), '#' + en.get('id'))}")
        doc.parts.extend(lines)
        if edges:
            doc.add("[connectors: start shape --> end shape]")
            doc.parts.extend(edges)
        if slide.has_notes_slide:
            nt = slide.notes_slide.notes_text_frame.text.strip() if slide.notes_slide.notes_text_frame else ""
            if nt:
                doc.add("--- speaker notes ---")
                doc.add(nt)
        doc.add("")
        if not lines and not edges:
            doc.low.append(sn)
    doc.units = len(prs.slides)
    return doc


# --------------------------------------------------------------------------- XLSX

def fmt_cell(v: object, number_format: str) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        s = repr(v) if abs(v) < 1e15 else f"{v:.6g}"
        if "%" in number_format:
            s = f"{v * 100:.2f}% ({s})"
        return s
    if isinstance(v, (_dt.datetime, _dt.date)):
        return v.isoformat()[:10] if isinstance(v, _dt.datetime) and v.time() == _dt.time() else v.isoformat()
    return str(v).replace("|", "\\|").replace("\n", "<br>")


def recalc_with_libreoffice(src: Path, dst: Path, recalc_root: Path) -> None:
    """Open and re-save the workbook with headless LibreOffice Calc, which computes formula cells that carry no
    cached value (the matter workbooks were generated without ever being recalculated)."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    profile = recalc_root / ".lo-profile"  # one profile at the cache root; as_uri() escapes spaces in the path
    tmp = dst.parent / ".lo-out"
    tmp.mkdir(parents=True, exist_ok=True)
    cmd = ["soffice", f"-env:UserInstallation={profile.resolve().as_uri()}", "--headless", "--calc",
           "--convert-to", "xlsx:Calc MS Excel 2007 XML", "--outdir", str(tmp), str(src)]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    out = tmp / src.name
    if p.returncode != 0 or not out.exists():
        raise RuntimeError(f"LibreOffice recalculation failed (exit {p.returncode}): {p.stderr.strip()[-500:]}")
    out.replace(dst)


def count_uncached(wf, wv) -> int:
    n = 0
    for ws in wf.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.startswith("=") and wv[ws.title][c.coordinate].value is None:
                    n += 1
    return n


def extract_xlsx(src: Path, rel: Path, recalc_cache: Path) -> Doc:
    import openpyxl
    from openpyxl.utils import get_column_letter
    wf = openpyxl.load_workbook(src, data_only=False)
    wv = openpyxl.load_workbook(src, data_only=True)
    doc = Doc()
    before = count_uncached(wf, wv)
    if before:
        rc = recalc_cache / rel
        if not (rc.exists() and rc.stat().st_mtime >= src.stat().st_mtime):
            recalc_with_libreoffice(src, rc, recalc_cache)
        wv = openpyxl.load_workbook(rc, data_only=True)
        doc.notes.append(f"{before} formula cells had no cached value in the source; values computed by headless "
                         f"LibreOffice recalculation ({rc.name})")
    uncached = 0
    for ws_f in wf.worksheets:
        ws_v = wv[ws_f.title]
        state = "" if ws_f.sheet_state == "visible" else f" ({ws_f.sheet_state})"
        doc.add(f"=== [sheet: {ws_f.title}] ===")
        doc.add(f"sheet {ws_f.title!r}{state}; used range {ws_f.dimensions}")
        rows = []
        formulas = []
        max_c = ws_f.max_column
        for r in range(1, ws_f.max_row + 1):
            vals = []
            for c in range(1, max_c + 1):
                cf = ws_f.cell(r, c)
                cv = ws_v.cell(r, c)
                vals.append(fmt_cell(cv.value, cf.number_format))
                if isinstance(cf.value, str) and cf.value.startswith("="):
                    if cv.value is None:
                        uncached += 1
                    formulas.append(f"{cf.coordinate}: {cf.value}  -> cached {fmt_cell(cv.value, cf.number_format) or '(none)'}")
            if any(vals):
                rows.append((r, vals))
        if rows:
            # only columns that hold a value anywhere on the sheet (the header keeps the real column letters)
            cols = sorted({i for _, v in rows for i, x in enumerate(v) if x})
            doc.add("| row | " + " | ".join(get_column_letter(c + 1) for c in cols) + " |")
            doc.add("|---|" + "---|" * len(cols))
            for r, v in rows:
                doc.add(f"| {r} | " + " | ".join(v[c] for c in cols) + " |")
        else:
            doc.add("(empty sheet)")
            doc.low.append(len(doc.parts))
        if ws_f.merged_cells.ranges:
            doc.add("merged cells: " + ", ".join(str(m) for m in ws_f.merged_cells.ranges))
        if formulas:
            doc.add("--- formulas (cell: formula -> cached value) ---")
            doc.parts.extend(formulas)
        doc.add("")
        doc.units += 1
    doc.low = []
    if uncached:
        doc.notes.append(f"STILL UNCACHED after recalculation: {uncached} formula cells")
        print(f"!!! {rel}: {uncached} formula cells still have no value after LibreOffice recalculation", file=sys.stderr)
    return doc


# --------------------------------------------------------------------------- driver

def extract_one(src: Path, rel: Path, out_root: Path, ocr_cache: Path, tessdata: Path, count: Counter, ocr: bool,
                recalc_cache: Path) -> FileOutcome:
    kind = src.suffix.lower().lstrip(".")
    try:
        if kind == "pdf":
            r = extract_pdf(src, rel, ocr_cache, tessdata, ocr)
            if isinstance(r, NeedsOcrBlocked):
                return r
            doc, source = r
            unit = "page"
        elif kind == "docx":
            doc, source, unit = extract_docx(src), "native", "section"
        elif kind == "pptx":
            doc, source, unit = extract_pptx(src), "native", "slide"
        elif kind == "xlsx":
            doc, source, unit = extract_xlsx(src, rel, recalc_cache), "native", "sheet"
        else:
            return Failed(f"unsupported file type .{kind}")
    except Exception as e:  # recorded as a typed FAILED outcome and printed loudly; the run exits 1
        return Failed(f"{type(e).__name__}: {e}")
    header = f"# {rel.as_posix()}\nsource: {kind}, {doc.units} {unit}(s), text: {source}\n"
    body = header + "\n" + doc.text()
    dst = out_root / (rel.as_posix() + ".md")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(body, encoding="utf-8")
    return Extracted(text_source=source, units=doc.units, unit_name=unit, chars=len(body), tokens=count(body),
                     low_text_units=doc.low, notes=doc.notes)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--case", type=Path, required=True, help="case root (contains 'Input Documents/')")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--ocr-cache", type=Path, required=True)
    ap.add_argument("--tessdata", type=Path, required=True)
    ap.add_argument("--recalc-cache", type=Path, required=True, help="LibreOffice-recalculated workbook copies")
    ap.add_argument("--tokenizer", type=Path, default=Path("/opt/dsv41/tokenizer/tokenizer.json"))
    ap.add_argument("--no-ocr", action="store_true", help="never run OCR; scanned files end NEEDS_OCR_BLOCKED")
    ap.add_argument("--only", default="", help="substring filter on the relative path (testing)")
    a = ap.parse_args()
    inp = a.case / "Input Documents"
    if not inp.is_dir():
        raise SystemExit(f"no 'Input Documents' under {a.case}")
    count = Counter(a.tokenizer)
    files = sorted(p for p in inp.rglob("*") if p.is_file() and a.only in str(p))
    a.out.mkdir(parents=True, exist_ok=True)
    rows = []
    bad = 0
    for src in files:
        rel = src.relative_to(inp)
        res = extract_one(src, rel, a.out, a.ocr_cache, a.tessdata, count, not a.no_ocr, a.recalc_cache)
        row = {"path": rel.as_posix(), "kind": src.suffix.lower().lstrip("."), "bytes": src.stat().st_size, **asdict(res)}
        rows.append(row)
        if isinstance(res, Extracted):
            flag = f"  LOW-TEXT {res.unit_name}s {res.low_text_units}" if res.low_text_units else ""
            print(f"{res.outcome:9s} {res.text_source:15s} {res.units:4d} {res.unit_name:7s} {res.chars:9d}c {res.tokens:8d}t  {rel}{flag}", flush=True)
        else:
            bad += 1
            print(f"!!! {res.outcome}: {rel}: {getattr(res, 'reason', getattr(res, 'error', ''))}", file=sys.stderr, flush=True)
    with open(a.out / "_inventory.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    ok = [r for r in rows if r["outcome"] == "EXTRACTED"]
    by_kind: dict[str, list[int]] = {}
    for r in ok:
        k = by_kind.setdefault(r["kind"], [0, 0, 0, 0])
        k[0] += 1; k[1] += r["units"]; k[2] += r["chars"]; k[3] += r["tokens"]
    md = ["# Matter inventory", "",
          f"{len(rows)} files; {len(ok)} extracted; {bad} not extracted. Tokens counted with {a.tokenizer}.", "",
          "| kind | files | units | chars | tokens |", "|---|---|---|---|---|"]
    for k, (n, u, c, t) in sorted(by_kind.items()):
        md.append(f"| {k} | {n} | {u} | {c:,} | {t:,} |")
    md.append(f"| **all** | {len(ok)} | {sum(v[1] for v in by_kind.values())} | {sum(v[2] for v in by_kind.values()):,} | {sum(v[3] for v in by_kind.values()):,} |")
    md += ["", "| file | outcome | source | units | chars | tokens | low-text units | notes |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if r["outcome"] == "EXTRACTED":
            md.append(f"| {r['path']} | EXTRACTED | {r['text_source']} | {r['units']} {r['unit_name']} | {r['chars']:,} | {r['tokens']:,} | "
                      f"{r['low_text_units'] or ''} | {'; '.join(r['notes'])} |")
        else:
            md.append(f"| {r['path']} | **{r['outcome']}** | | | | | | {r.get('reason') or r.get('error')} |")
    (a.out / "_inventory.md").write_text("\n".join(md) + "\n")
    print(f"\n{len(ok)}/{len(rows)} extracted; {bad} NOT extracted", file=sys.stderr if bad else sys.stdout)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
