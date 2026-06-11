# Scripted .docx Editing Playbook (portable)

Hand this to a Claude instance in another project. It captures a workflow for
editing Microsoft Word `.docx` files **programmatically, reproducibly, and
without destroying formatting**. It was developed for a long-lived proposal
document and has been generalized here. Nothing below is specific to that
project except where noted.

The approach: **never hand-edit the binary, never let a model free-form rewrite
the file.** Every change is a small Python script using `python-docx` that reads
a canonical file and writes a *draft* copy. The human reviews the draft in Word
(Compare Documents) and promotes it by renaming. This gives you a reproducible,
auditable, reversible edit history with the original formatting intact.

---

## 1. Why scripts instead of "just edit the doc"

- **Formatting survives.** Word stores fonts/spacing/numbering as per-run XML
  (`rPr`, `rFonts`, etc.). Naive edits (or regenerating the doc from Markdown)
  silently drop these and the document re-flows. The helpers below copy the
  existing run properties onto new text so the result looks untouched except for
  the words you changed.
- **Reproducible + auditable.** The script *is* the changelog. Re-running it
  reproduces the edit. `git diff` on the script shows intent.
- **Reversible.** The canonical file is read-only by convention; output goes to
  a `_draft` copy. You can never clobber the source.
- **Idempotent.** Guard insertions (`if marker not in text`) so re-running
  doesn't duplicate content.

---

## 2. The promote-and-replace workflow

```
canonical.docx  --(script reads)-->  script  --(writes)-->  canonical_draft.docx
                                                                    |
                                              human reviews in Word (Compare)
                                                                    |
                                              human renames draft -> canonical
```

Rules:
1. Scripts **READ** from the canonical file, **WRITE** to a `_draft` file.
2. **Never auto-promote.** The human renames the draft to canonical after review.
   Keep the previous canonical on disk as an audit artifact (e.g. `_old.docx`).
3. When a change is large enough to be a new "generation", bump a version number
   in the filename (`_v4.docx` -> `_v5.docx`) and update the path constants.
4. Each edit is its own numbered script (`rewrite_v1.py`, `rewrite_v2.py`, ...).
   Don't mutate old scripts; add new ones. The sequence is the history.

---

## 3. Setup

```bash
python3 -m pip install python-docx
```

`python-docx` imports as `docx`. Everything below uses only `python-docx` plus
the stdlib (`copy`, `re`, `pathlib`).

---

## 4. The library (`docx_edit_lib.py`)

Drop this file into the other project's `scripts/`. Set the two path constants
at the top to that project's files. These helpers exist because each one solves
a formatting-preservation bug discovered the hard way (see §7 Gotchas).

```python
"""Reusable helpers for editing a .docx in place with python-docx while
preserving run-level formatting (font, size, bold, list membership, etc.).

Workflow:
    from docx import Document
    from docx_edit_lib import (
        CANONICAL_DOCX, DRAFT_DOCX,
        replace_paragraph_text, set_cell_text, normalize_run_rfonts,
        insert_paragraph_after, insert_paragraphs_after, create_table_after,
        find_paragraph_by_text,
    )
    doc = Document(str(CANONICAL_DOCX))
    # ...edits...
    doc.save(str(DRAFT_DOCX))
"""
from __future__ import annotations

import copy
import re
from pathlib import Path

from docx import Document  # noqa: F401  (re-exported for convenience)
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

# --- Configure these two for the target project --------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS = REPO_ROOT / "docs"
CANONICAL_DOCX = DOCS / "YOUR_DOCUMENT.docx"          # script READS this
DRAFT_DOCX = DOCS / "YOUR_DOCUMENT_draft.docx"        # script WRITES this

# Body font used throughout the document. Inspect the source first: the
# document *default* may differ from what body text actually uses. (In the
# origin project the default was Arial but body runs set Times New Roman
# explicitly — see normalize_run_rfonts.)
BODY_FONT = "Times New Roman"


# --- Run-level font normalization ----------------------------------------
def normalize_run_rfonts(run, font: str = BODY_FONT) -> None:
    """Force a run's rFonts to set ascii + hAnsi + cs + eastAsia = font, plus
    an explicit <w:rtl val="0"/>.

    THE #1 GOTCHA: if eastAsia (or cs) is unset, Word falls back to the
    *document default* font for any character it classifies under that script,
    so newly inserted runs render in the wrong font even though you "set" the
    font. Always call this on every run you create.
    """
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(attr), font)
    rtl = rpr.find(qn("w:rtl"))
    if rtl is None:
        rtl = OxmlElement("w:rtl")
        rpr.append(rtl)
    rtl.set(qn("w:val"), "0")


# --- Paragraph-text replacement (preserves first-run rPr) ----------------
def replace_paragraph_text(p: Paragraph, new_text: str) -> None:
    """Replace ALL text of a paragraph while preserving the first run's rPr
    (font, size, color, bold...). Clears existing runs, adds one new run with
    the captured rPr.

    Use for single-styled paragraphs. NOT for paragraphs with intentionally
    mixed runs (inline bold/italic spans) — it flattens them to one style.
    """
    first_run_props = None
    if p.runs:
        rpr = p.runs[0]._element.find(qn("w:rPr"))
        first_run_props = copy.deepcopy(rpr) if rpr is not None else None
    for r in list(p.runs):
        r._element.getparent().remove(r._element)
    new_run = p.add_run(new_text)
    if first_run_props is not None:
        existing = new_run._element.find(qn("w:rPr"))
        if existing is not None:
            new_run._element.remove(existing)
        new_run._element.insert(0, first_run_props)


# --- Table cell text replacement -----------------------------------------
def set_cell_text(cell, text: str, ensure_body_font: bool = False) -> None:
    """Replace a table cell's text, preserving the first paragraph's style.
    Set ensure_body_font=True for cells in rows added via table.add_row()
    (those inherit no run formatting and would fall back to the default font).
    """
    if not cell.paragraphs:
        cell.text = text
        return
    first_p = cell.paragraphs[0]
    replace_paragraph_text(first_p, text)
    for extra_p in cell.paragraphs[1:]:
        extra_p._element.getparent().remove(extra_p._element)
    if ensure_body_font:
        for r in first_p.runs:
            normalize_run_rfonts(r)


# --- Paragraph insertion --------------------------------------------------
def insert_paragraph_after(anchor: Paragraph, text: str,
                           style_name: str | None = None) -> Paragraph:
    """Insert a new paragraph immediately after `anchor`, inheriting anchor's
    paragraph properties (incl. list/bullet membership), with runs stripped.
    Adds one run normalized to BODY_FONT. Optionally set a style by name
    (e.g. "Heading 3", "Normal").
    """
    new_elem = copy.deepcopy(anchor._element)
    for r in new_elem.findall(qn("w:r")):
        new_elem.remove(r)
    anchor._element.addnext(new_elem)
    new_para = Paragraph(new_elem, anchor._parent)
    if style_name is not None:
        try:
            new_para.style = anchor.part.document.styles[style_name]
        except KeyError:
            pass
    run = new_para.add_run(text)
    normalize_run_rfonts(run)
    return new_para


def insert_paragraphs_after(anchor: Paragraph,
                            items: list[tuple[str, str | None]]) -> Paragraph:
    """Insert a sequence of (text, style_name) tuples after `anchor`.
    Returns the last inserted paragraph so inserts can chain."""
    last = anchor
    for text, style in items:
        last = insert_paragraph_after(last, text, style)
    return last


# --- Table insertion mid-document ----------------------------------------
def create_table_after(anchor: Paragraph, rows_data: list[list[str]],
                       style: str = "Table Grid"):
    """Create a table from rows_data (list of rows; each row a list of cell
    strings) and move it to right after `anchor`. (python-docx's add_table
    always appends at end of body, so we relocate it.) All cells get BODY_FONT.
    """
    n_rows = len(rows_data)
    n_cols = len(rows_data[0]) if rows_data else 0
    doc = anchor.part.document
    tbl = doc.add_table(rows=n_rows, cols=n_cols)
    try:
        tbl.style = doc.styles[style]
    except KeyError:
        pass
    for r_idx, row_data in enumerate(rows_data):
        for c_idx, cell_text in enumerate(row_data):
            set_cell_text(tbl.rows[r_idx].cells[c_idx], cell_text,
                          ensure_body_font=True)
    tbl_element = tbl._element
    tbl_element.getparent().remove(tbl_element)
    anchor._element.addnext(tbl_element)
    return tbl


# --- Location helpers -----------------------------------------------------
def find_paragraph_by_text(doc, predicate) -> Paragraph | None:
    """First paragraph where predicate(p) is True, else None.
    e.g. find_paragraph_by_text(doc,
            lambda p: p.style.name == "Heading 3" and p.text.startswith("3.7 "))
    """
    for p in doc.paragraphs:
        if predicate(p):
            return p
    return None


def find_table_by_first_cell(doc, predicate):
    """First table whose row[0].cells[0].text (stripped) matches predicate."""
    for t in doc.tables:
        if t.rows and t.rows[0].cells:
            if predicate(t.rows[0].cells[0].text.strip()):
                return t
    return None


def iter_paragraphs_between(start: Paragraph, end: Paragraph):
    """Yield paragraphs strictly between `start` and `end` in document order.
    Stops at the first non-paragraph element (e.g. a table)."""
    p = start
    parent = start._parent
    while True:
        sib = p._element.getnext()
        if sib is None or sib is end._element:
            return
        if sib.tag == qn("w:p"):
            wrapped = Paragraph(sib, parent)
            yield wrapped
            p = wrapped
        else:
            return


def last_content_paragraph_in_section(start_heading: Paragraph,
                                      end_heading: Paragraph) -> Paragraph:
    """Last non-empty paragraph between two headings, or start_heading if
    the section is empty. Useful as an anchor for appending to a section."""
    last = start_heading
    for p in iter_paragraphs_between(start_heading, end_heading):
        if p.text.strip():
            last = p
    return last


# --- Optional: strip em-dashes (an "AI tell") ----------------------------
def em_dash_clean(text: str, in_heading: bool = False) -> str:
    """Project convention from the origin doc: em-dashes read AI-generated, so
    replace them. Spaced em-dash -> comma in body, colon in headings; attached
    em-dash (word—word) -> 'word, word'. Drop this function if you don't want
    the convention."""
    out = text.replace(" — ", ": ") if in_heading else text.replace(" — ", ", ")
    out = re.sub(r"(\w)—(\w)", r"\1, \2", out)
    return re.sub(r" {2,}", " ", out)
```

---

## 5. The inspect helper (`inspect_docx.py`)

Run this **before** writing an edit (to find anchor text and styles) and
**after** (to confirm structure). Pass a path as `argv[1]`.

```python
"""Inspect a .docx structure: styles, every paragraph (index/style/text),
and every table (dims + first cell). Usage: python inspect_docx.py FILE.docx"""
import sys
from docx import Document

path = sys.argv[1]
doc = Document(path)

print(f"paragraphs={len(doc.paragraphs)} tables={len(doc.tables)} "
      f"sections={len(doc.sections)}\n")

styles = {}
for p in doc.paragraphs:
    styles[p.style.name] = styles.get(p.style.name, 0) + 1
print("Paragraph styles used:")
for s, c in sorted(styles.items(), key=lambda x: -x[1]):
    print(f"  {s}: {c}")

print("\nPARAGRAPHS (index | style | first 120 chars):")
for i, p in enumerate(doc.paragraphs):
    text = p.text.replace("\n", " ").strip()
    print(f"[{i:3}] {p.style.name:28} {text[:120] or '(empty)'}")

print("\nTABLES (index | rows×cols | first cell):")
for i, t in enumerate(doc.tables):
    first = t.rows[0].cells[0].text.strip()[:60] if t.rows else ""
    print(f"[{i:2}] {len(t.rows)}×{len(t.columns)}  {first!r}")
```

A companion text-diff helper is worth having too: load two docs, flatten each to
`P[style] text` / `T#[r,c] text` lines, and run `difflib.SequenceMatcher` over
the line lists. That shows *content* changes between draft and canonical
independent of XML noise.

---

## 6. How to write one edit pass

1. **Inspect first.** `python inspect_docx.py canonical.docx`. Find the exact
   anchor text / style / table index you'll target.
2. **Confirm scope** with the human in 2–3 sentences if the edit involves
   judgment (rephrasing, restructuring, new content). Proceed directly only for
   mechanical changes (find/replace, cleanup).
3. **Write `scripts/rewrite_vN.py`** (next number). Structure:
   - Top docstring: what it does + numbered list of operations.
   - `from docx_edit_lib import (...)` — **import helpers, never re-inline them.**
   - One function per operation, or a `main()` with clearly delimited phases.
   - Locate targets with `find_paragraph_by_text` / `find_table_by_first_cell`,
     not by hardcoded indices (indices shift as the doc changes).
   - Guard insertions for idempotency (`if marker not in p.text`).
   - `print()` every action so the run is self-auditing.
   - End `main()` with `doc.save(str(DRAFT_DOCX))` + a summary print.
4. **Run it**, then `python inspect_docx.py *_draft.docx` and confirm structural
   counts (paragraph count, table count, heading sequence) match expectations.
5. **Tell the human**: output is in `_draft.docx`; review in Word's Compare
   Documents and promote by renaming. Do **not** rename for them.

---

## 7. Gotchas (the hard-won lessons)

- **Font fallback via missing `eastAsia`/`cs`.** Setting only `rFonts/ascii`
  isn't enough. Word picks the font per character script; an unset `eastAsia`
  (or `cs`) attribute makes inserted runs render in the document default font.
  Always run new runs through `normalize_run_rfonts`. This was a recurring bug
  until all four attributes + `rtl=0` were set together.
- **Document default font ≠ body font.** Inspect a real run's `rPr` to learn
  what body text actually uses; don't trust `styles['Normal'].font.name`.
- **`add_table` appends at the end of the body.** You must detach and
  `addnext` it onto your anchor to place it mid-document (`create_table_after`).
- **Rows from `table.add_row()` carry no run formatting.** Use
  `set_cell_text(..., ensure_body_font=True)` for them.
- **`replace_paragraph_text` flattens to one run.** Fine for single-style
  paragraphs; it destroys inline bold/italic spans. For mixed runs, edit the
  specific run's `.text` instead.
- **Address by content, not index.** Paragraph/table indices shift between
  edits. Find anchors by heading text + style so scripts stay valid.
- **Idempotency.** Guard every insertion so a second run is a no-op.

---

## 8. Recommended conventions for the target project

Put these in that project's `CLAUDE.md` so the behavior is durable:

- Read from canonical, write to `_draft`; the human promotes by renaming.
- Each edit is its own numbered script in `scripts/`; never mutate old ones.
- Import helpers from `docx_edit_lib`; never re-inline them.
- Inspect before and after; verify structural counts.
- Don't commit the draft or the script unless asked — they're staging artifacts
  until the human accepts.
- (Optional, origin-project conventions you may or may not want: no em-dashes in
  body text; no unsourced numbers; keep an edit log.)
```
