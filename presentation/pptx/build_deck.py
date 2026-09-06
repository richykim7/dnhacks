"""Build the DNHacks 2026 judge deck.

Run:  uv run python presentation/pptx/build_deck.py
Out:  presentation/pptx/dnhacks-deck.pptx

Every slide carries a provenance tag (MEASURED / IMPLEMENTED / PLANNED / ILLUSTRATIVE) and a
speaker script in its notes. Fields the team still has to fill are written as [TODO ...] in
both the slide and the notes so nothing illustrative can be mistaken for a result on stage.

Visual system follows frontend/DESIGN.md and frontend/src/styles.css (dark theme tokens):
IBM Plex Sans / Mono, mineral charcoal surfaces, warm text, sea-green selection, amber
uncertainty, rose failure, thin dividers, no gradients.
"""

from __future__ import annotations

import json
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_MARKER_STYLE
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "dnhacks-deck.pptx"

# ---------------------------------------------------------------- tokens (frontend/src/styles.css)
BG = RGBColor(0x15, 0x1A, 0x1B)
SURFACE = RGBColor(0x1B, 0x21, 0x22)
RAISED = RGBColor(0x25, 0x2D, 0x2E)
BORDER = RGBColor(0x34, 0x41, 0x3E)
EDGE = RGBColor(0x66, 0x80, 0x78)
GRID = RGBColor(0x48, 0x5B, 0x53)
FG = RGBColor(0xED, 0xF0, 0xEA)
MUTED = RGBColor(0xAB, 0xB7, 0xB3)
SUBTLE = RGBColor(0x7D, 0x91, 0x8A)
ACCENT = RGBColor(0xA6, 0xCA, 0xBB)
ACCENT_INK = RGBColor(0x18, 0x2C, 0x24)
SELECTED = RGBColor(0x26, 0x3B, 0x33)
ATTENTION = RGBColor(0xE4, 0xBB, 0x7F)
NEGATIVE = RGBColor(0xE5, 0xA6, 0xA0)

SANS = "IBM Plex Sans"
MONO = "IBM Plex Mono"

W, H = Inches(13.333), Inches(7.5)
MARGIN = Inches(0.7)
CONTENT_W = W - 2 * MARGIN

TAGS = {
    "MEASURED": (ACCENT, ACCENT_INK, "computed from committed artifacts; numbers may be said aloud"),
    "IMPLEMENTED": (FG, BG, "behaviour that exists in main and is covered by tests"),
    "PLANNED": (ATTENTION, BG, "proposed in plans/; not built, not authorised until asked for"),
    "ILLUSTRATIVE": (SUBTLE, BG, "shape of the thing; values are placeholders until recorded"),
}

prs = Presentation()
prs.slide_width, prs.slide_height = W, H
BLANK = prs.slide_layouts[6]
SLIDE_NO = 0


# ---------------------------------------------------------------- primitives
def _font(run, size, color=FG, bold=False, font=SANS, italic=False):
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    # east-asian / complex-script fallbacks so PowerPoint does not substitute Calibri
    rpr = run._r.get_or_add_rPr()
    for tag in ("a:latin", "a:ea", "a:cs"):
        el = rpr.find(qn(tag))
        if el is None:
            el = etree.SubElement(rpr, qn(tag))
        el.set("typeface", font)


def text(slide, x, y, w, h, content, size=16, color=FG, bold=False, font=SANS, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, spacing=1.15, italic=False, margin=0):
    """content: str, or list of paragraphs; a paragraph is str or list of (text, overrides) runs."""
    box = slide.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = Emu(margin)
    paragraphs = content if isinstance(content, list) else [content]
    for i, para in enumerate(paragraphs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = spacing
        runs = para if isinstance(para, list) else [(para, {})]
        for run_text, over in runs:
            r = p.add_run()
            r.text = run_text
            _font(r, over.get("size", size), over.get("color", color), over.get("bold", bold),
                  over.get("font", font), over.get("italic", italic))
        if i:
            p.space_before = Pt(6)
    return box


def rect(slide, x, y, w, h, fill=SURFACE, line=None, radius=False, line_w=0.75):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE, x, y, w, h)
    if radius:
        shape.adjustments[0] = 0.06
    shape.shadow.inherit = False
    if fill is None:
        shape.fill.background()
    else:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill
    if line is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = line
        shape.line.width = Pt(line_w)
    shape.text_frame.text = ""
    return shape


def hline(slide, x, y, w, color=BORDER, weight=0.75):
    ln = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, x, y, x + w, y)
    ln.line.color.rgb = color
    ln.line.width = Pt(weight)
    return ln


def arrow(slide, x1, y1, x2, y2, color=EDGE, weight=1.25, dashed=False):
    ln = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, x1, y1, x2, y2)
    ln.line.color.rgb = color
    ln.line.width = Pt(weight)
    ln_el = ln.line._get_or_add_ln()
    if dashed:
        dash = etree.SubElement(ln_el, qn("a:prstDash"))
        dash.set("val", "dash")
    tail = etree.SubElement(ln_el, qn("a:tailEnd"))
    tail.set("type", "triangle")
    tail.set("w", "med")
    tail.set("len", "med")
    return ln


def pill(slide, x, y, label, fill, ink, w=None, size=9):
    w = w or Inches(0.16 + 0.085 * len(label))
    shape = rect(slide, x, y, w, Inches(0.26), fill=fill, radius=True)
    shape.adjustments[0] = 0.5
    tf = shape.text_frame
    tf.margin_left = tf.margin_right = Inches(0.06)
    tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = label
    _font(r, size, ink, True, MONO)
    return shape


def notes(slide, script):
    slide.notes_slide.notes_text_frame.text = script.strip()


def new_slide(section, title, tag=None, subtitle=None):
    """Chrome shared by every content slide: section label, provenance tag, title, footer."""
    global SLIDE_NO
    SLIDE_NO += 1
    slide = prs.slides.add_slide(BLANK)
    bg = slide.background.fill
    bg.solid()
    bg.fore_color.rgb = BG
    text(slide, MARGIN, Inches(0.42), Inches(6), Inches(0.3), section.upper(), size=10, color=SUBTLE, font=MONO)
    if tag:
        fill, ink, _ = TAGS[tag]
        pill(slide, W - MARGIN - Inches(1.45), Inches(0.42), tag, fill, ink, w=Inches(1.45))
    hline(slide, MARGIN, Inches(0.78), CONTENT_W)
    title_size = 30 if len(title) <= 58 else (26 if len(title) <= 66 else 23)
    text(slide, MARGIN, Inches(0.92), CONTENT_W, Inches(0.9), title, size=title_size, bold=True, spacing=1.05)
    if subtitle:
        sub_size = 15 if len(subtitle) <= 105 else 13.5
        text(slide, MARGIN, Inches(1.62), CONTENT_W, Inches(0.5), subtitle, size=sub_size, color=MUTED)
    hline(slide, MARGIN, H - Inches(0.55), CONTENT_W)
    text(slide, MARGIN, H - Inches(0.47), Inches(6), Inches(0.3),
         "DN Research (working name)  ·  DNHacks 2026", size=9, color=SUBTLE, font=MONO)
    text(slide, W - MARGIN - Inches(1), H - Inches(0.47), Inches(1), Inches(0.3), f"{SLIDE_NO:02d}",
         size=9, color=SUBTLE, font=MONO, align=PP_ALIGN.RIGHT)
    return slide


def card(slide, x, y, w, h, heading, body, accent=ACCENT, heading_size=13, body_size=12.5, mono_heading=True,
         fill=SURFACE):
    rect(slide, x, y, w, h, fill=fill, line=BORDER, radius=True)
    rect(slide, x, y + Inches(0.18), Inches(0.05), h - Inches(0.36), fill=accent)
    text(slide, x + Inches(0.22), y + Inches(0.14), w - Inches(0.35), Inches(0.35), heading,
         size=heading_size, bold=True, color=accent if mono_heading else FG, font=MONO if mono_heading else SANS)
    text(slide, x + Inches(0.22), y + Inches(0.52), w - Inches(0.35), h - Inches(0.6), body,
         size=body_size, color=MUTED, spacing=1.2)


def bullets(slide, x, y, w, h, items, size=15, color=FG, gap=8, marker="—", marker_color=ACCENT):
    box = slide.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.line_spacing = 1.18
        if i:
            p.space_before = Pt(gap)
        runs = item if isinstance(item, list) else [(item, {})]
        m = p.add_run()
        m.text = f"{marker}  "
        _font(m, size, marker_color, True, MONO)
        for run_text, over in runs:
            r = p.add_run()
            r.text = run_text
            _font(r, over.get("size", size), over.get("color", color), over.get("bold", False),
                  over.get("font", SANS), over.get("italic", False))
    return box


def table(slide, x, y, w, rows, col_w, header=True, size=11.5, row_h=Inches(0.34), mono_cols=()):
    n_rows, n_cols = len(rows), len(rows[0])
    shape = slide.shapes.add_table(n_rows, n_cols, x, y, w, row_h * n_rows)
    tbl = shape.table
    tbl_pr = tbl._tbl.tblPr
    tbl_pr.set("bandRow", "0")
    tbl_pr.set("firstRow", "0")
    style = tbl_pr.find(qn("a:tableStyleId"))
    if style is not None:
        tbl_pr.remove(style)
    for j, cw in enumerate(col_w):
        tbl.columns[j].width = cw
    for i, row in enumerate(rows):
        tbl.rows[i].height = row_h
        for j, val in enumerate(row):
            cell = tbl.cell(i, j)
            cell.fill.solid()
            cell.fill.fore_color.rgb = SURFACE if (i and i % 2) else BG
            cell.margin_left = cell.margin_right = Inches(0.08)
            cell.margin_top = cell.margin_bottom = Inches(0.03)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf = cell.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            r = p.add_run()
            r.text = str(val)
            is_head = header and i == 0
            _font(r, size, SUBTLE if is_head else (FG if j == 0 else MUTED), is_head,
                  MONO if (is_head or j in mono_cols) else SANS)
            # thin borders
            tc_pr = cell._tc.get_or_add_tcPr()
            for edge in ("a:lnL", "a:lnR", "a:lnT", "a:lnB"):
                ln = etree.SubElement(tc_pr, qn(edge))
                ln.set("w", "6350")
                sf = etree.SubElement(ln, qn("a:solidFill"))
                clr = etree.SubElement(sf, qn("a:srgbClr"))
                clr.set("val", "34413E" if edge in ("a:lnT", "a:lnB") else "151A1B")
    return shape


def node(slide, x, y, w, h, label, sub=None, fill=SURFACE, line=BORDER, label_color=FG, mono=False, size=None):
    shape = rect(slide, x, y, w, h, fill=fill, line=line, radius=True)
    tf = shape.text_frame
    tf.margin_left = tf.margin_right = Inches(0.08)
    tf.margin_top = tf.margin_bottom = Inches(0.04)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = label
    _font(r, size or (12.5 if not sub else 12), label_color, True, MONO if mono else SANS)
    if sub:
        p2 = tf.add_paragraph()
        p2.alignment = PP_ALIGN.CENTER
        r2 = p2.add_run()
        r2.text = sub
        _font(r2, 9.5, MUTED, False, MONO)
    return shape


# ================================================================ SLIDES
# ---------------------------------------------------------------- 01 title
def slide_title():
    global SLIDE_NO
    SLIDE_NO += 1
    s = prs.slides.add_slide(BLANK)
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = BG
    text(s, MARGIN, Inches(0.55), Inches(9), Inches(0.3), "DNHACKS 2026  ·  OPEN CATEGORY, PRESENTED BY DTX VENTURES  ·  [TODO confirm track on the submission form]",
         size=10, color=SUBTLE, font=MONO)
    pill(s, W - MARGIN - Inches(1.9), Inches(0.5), "WORKING NAME", SUBTLE, BG, w=Inches(1.9))
    hline(s, MARGIN, Inches(0.9), CONTENT_W)
    text(s, MARGIN, Inches(2.0), Inches(11.5), Inches(2.2),
         [[("Compute, pointed at the", {}), ("\nright experiments.", {"color": ACCENT})]],
         size=54, bold=True, spacing=1.0)
    text(s, MARGIN, Inches(4.35), Inches(11.2), Inches(1.2),
         "An autonomous discovery engine. It turns a body of scientific literature into a knowledge graph, "
         "lets an agent roam it and run its own experiments on public data, checks every result with a "
         "falsifier that has no answer key, and puts a person at the gate.",
         size=17, color=MUTED, spacing=1.25)
    # small provenance legend
    x = MARGIN
    for i, (k, (fill, ink, meaning)) in enumerate(TAGS.items()):
        pill(s, x, Inches(5.95), k, fill, ink, w=Inches(1.3))
        text(s, x, Inches(6.25), Inches(2.6), Inches(0.5), meaning, size=8.5, color=SUBTLE, font=MONO)
        x += Inches(2.85)
    hline(s, MARGIN, H - Inches(0.55), CONTENT_W)
    text(s, MARGIN, H - Inches(0.47), Inches(9), Inches(0.3),
         "Ian Tinney · Richard Kim · [TODO team]   ·   github.com/richykim7/dnhacks", size=9, color=SUBTLE, font=MONO)
    text(s, W - MARGIN - Inches(1), H - Inches(0.47), Inches(1), Inches(0.3), "01", size=9, color=SUBTLE,
         font=MONO, align=PP_ALIGN.RIGHT)
    notes(s, """
[0:00 — 20 s]  Say the title line and stop. Do not read the paragraph.

"Every model release makes it cheaper to generate a hypothesis. It has not made it cheaper to know which
hypothesis to test next, or whether the result you get back can be trusted. We built the thing that does
both: it aims compute at untested claims in the literature, runs the experiment on public data, and refuses
to believe its own numbers until a falsifier and a person have signed off."

Track: [TODO confirm the selected category on the submission form; the deck assumes Health and Public
Service. If the team submits to Open, change the footer line on this slide.]

Product name: "DN Research" is a placeholder (plans/backlog.md NAME-01). Replace it in build_deck.py
(new_slide footer) once the team agrees on a name.

Legend at the bottom: every slide carries one of four provenance tags. Point at it once, here, and never
again: "Green means we computed it and you can ask for the file. Amber means it is a plan. Grey means
the picture is illustrative." Judges scoring Reliability & Trustworthiness reward this immediately.
""")


# ---------------------------------------------------------------- 02 the gap
def slide_gap():
    s = new_slide("01 / the problem", "Published science is full of connections nobody has tested.", "ILLUSTRATIVE",
                  "The evidence to test them is already public. What is missing is something that aims at them and checks its work.")
    y = Inches(2.35)
    cw = (CONTENT_W - Inches(0.5)) / 3
    card(s, MARGIN, y, cw, Inches(2.75), "THE LITERATURE",
         "Every paper asserts relations: this gene raises that pathway, this drug lowers this readout. "
         "Across a field those assertions form a graph with millions of edges. Most edges rest on one lab, one "
         "cell line, one experiment.", accent=ACCENT)
    card(s, MARGIN + cw + Inches(0.25), y, cw, Inches(2.75), "THE PUBLIC DATA",
         "Genome-wide dependency screens across more than a thousand cancer cell lines (DepMap). Millions of "
         "expression profiles (GEO, ArrayExpress). Open-access full text of the papers themselves. All free, "
         "all downloadable, all mostly unread against each other.", accent=ATTENTION)
    card(s, MARGIN + 2 * (cw + Inches(0.25)), y, cw, Inches(2.75), "THE GAP",
         "Nobody has the hours to cross-check claim by claim. Untested bridges between two well-studied "
         "things stay untested for years. Those are the discoveries waiting to be found, and finding them is a "
         "question of where you aim compute.", accent=NEGATIVE)
    # glossary strip
    rect(s, MARGIN, Inches(5.35), CONTENT_W, Inches(1.25), fill=SURFACE, line=BORDER, radius=True)
    text(s, MARGIN + Inches(0.25), Inches(5.45), Inches(2), Inches(0.3), "TERMS WE WILL USE", size=9.5, color=SUBTLE, font=MONO)
    text(s, MARGIN + Inches(0.25), Inches(5.75), CONTENT_W - Inches(0.5), Inches(0.85), [
        [("Claim ", {"bold": True}), ("— one paper's assertion that A affects B, kept with the exact sentence that backs it.   ", {"color": MUTED}),
         ("Knowledge graph ", {"bold": True}), ("— claims drawn as edges between named biological things.   ", {"color": MUTED}),
         ("Experiment ", {"bold": True}), ("— code the agent writes and runs against public data to test one edge.", {"color": MUTED})],
    ], size=12.5)
    notes(s, """
[0:20 — 45 s]  Non-biology audience (Rich's framing note, plans/PLAN-demo-slides.md). Lead with the idea.

"Think of a field of science as a graph. Every published paper adds edges: this gene raises that pathway.
There are millions of those edges and most of them were tested once, by one lab, in one dish. Meanwhile the
data to re-test them is sitting in public: dependency screens across more than a thousand cancer cell
lines, millions of expression profiles, and the open-access papers themselves. Nobody has the hours to
cross-check claim by claim. So the untested bridges between two well-studied things just stay untested. Those
are the discoveries waiting to be found. Finding them is a question of where you point compute."

Define the three terms in the strip the moment they appear; assume nobody knows what a cell line is.

Numbers on this slide are deliberately words, not figures ("more than a thousand", "millions"). If a judge
asks: DepMap public releases screen over a thousand cancer cell lines; GEO holds millions of samples.
[TODO if you want exact figures on the slide, pull them from the DepMap release notes and GEO front page
on the day of the demo and cite the date.]
""")


# ---------------------------------------------------------------- 03 the bottleneck
def slide_bottleneck():
    s = new_slide("02 / the insight", "Model capability is not the bottleneck. Aim and trust are.", "IMPLEMENTED",
                  "An agent with no map wanders. An agent with no gate fools itself. We built the map and the gate.")
    y = Inches(2.35)
    cw = (CONTENT_W - Inches(0.3)) / 2
    card(s, MARGIN, y, cw, Inches(2.05), "FAILURE MODE 1 — NO MAP",
         "Re-tests what is already established. Calls a partial search 'novel'. Spends its budget on the "
         "hub genes everyone studies. The literature graph is the map: an edge with no path between two "
         "well-supported nodes is a candidate untested bridge.", accent=ATTENTION)
    card(s, MARGIN + cw + Inches(0.3), y, cw, Inches(2.05), "FAILURE MODE 2 — NO GATE",
         "Stops when the number looks good. Counts wells as donors. Reports p = 0. Believes its own summary. "
         "A falsifier with no answer key kills unsound numbers; a person decides truth, with a written note "
         "the agent must not forget.", accent=NEGATIVE)
    # the loop, one line
    rect(s, MARGIN, Inches(4.7), CONTENT_W, Inches(1.85), fill=SURFACE, line=BORDER, radius=True)
    text(s, MARGIN + Inches(0.3), Inches(4.82), Inches(4), Inches(0.3), "WHAT THE ENGINE DOES, IN ONE LINE", size=9.5, color=SUBTLE, font=MONO)
    text(s, MARGIN + Inches(0.3), Inches(5.15), CONTENT_W - Inches(0.6), Inches(1.3),
         [[("literature ", {"color": ACCENT, "bold": True}), ("→ graph ", {}), ("→ agent picks one untested edge ", {}),
           ("→ writes and runs the experiment on public data ", {}), ("→ falsifier ", {"color": NEGATIVE, "bold": True}),
           ("→ person at the gate ", {"color": ATTENTION, "bold": True}), ("→ master graph", {})],
          [("Survived verification means the numbers are sound. It never means the claim is true. Truth is the person's call.",
            {"color": MUTED, "size": 13, "italic": True})]],
         size=17, spacing=1.3)
    notes(s, """
[1:05 — 40 s]  Make the "compute pointed in the right direction" argument explicit.

"Everyone in this room can call a frontier model. The two ways an autonomous scientist fails have nothing to
do with model IQ. Failure one: it has no map, so it re-tests the famous genes, or calls something novel
because its search was truncated. Failure two: it has no gate, so it stops when the number looks good,
counts wells as donors, and believes its own summary. We built the map and the gate. The graph aims the
compute. The falsifier and the human gate make what comes back trustworthy."

Read the one-line loop. Then the italic sentence, slowly. It is the sentence the whole deck rests on, and
non-biologists respect it more, not less.

Source for the invariants: ARCHITECTURE.md section 1 and section 14.
""")


# ---------------------------------------------------------------- 04 architecture picture
def slide_architecture():
    s = new_slide("03 / what we built", "The whole engine in one picture.", "IMPLEMENTED",
                  "Domain-agnostic code. The data sources, vocabularies and method guides wired in today are computational biology.")
    y0 = Inches(2.55)
    bw, bh = Inches(1.72), Inches(0.95)
    gap = Inches(0.33)
    xs = [MARGIN + i * (bw + gap) for i in range(6)]
    node(s, xs[0], y0, bw, bh, "Project spec", "scope · queries · seeds")
    node(s, xs[1], y0, bw, bh, "Corpus build", "Europe PMC · open access")
    node(s, xs[2], y0, bw, bh, "Knowledge graph", "DuckDB · claims + evidence", fill=SELECTED, line=EDGE)
    node(s, xs[3], y0, bw, bh, "Explorer agent", "reason → one action → observe", fill=SELECTED, line=EDGE)
    node(s, xs[4], y0, bw, bh, "Experiments", "Python · RESULT: {json}")
    node(s, xs[5], y0, bw, bh, "Falsifier", "soundness only · no answer key", fill=RGBColor(0x3A, 0x2A, 0x2B), line=NEGATIVE)
    for i in range(5):
        arrow(s, xs[i] + bw, y0 + bh / 2, xs[i + 1], y0 + bh / 2)
    # second row: gate (under the falsifier) and master graph (under experiments)
    y1 = y0 + Inches(1.75)
    node(s, xs[5], y1, bw, bh, "Human gate", "written note required", fill=RGBColor(0x3B, 0x33, 0x22), line=ATTENTION)
    node(s, xs[4], y1, bw, bh, "Master graph", "validated + provenance", fill=SELECTED, line=EDGE)
    arrow(s, xs[5] + bw / 2, y0 + bh, xs[5] + bw / 2, y1)
    arrow(s, xs[5], y1 + bh * 0.3, xs[4] + bw, y1 + bh * 0.3)

    def path(points, color):
        for (x1, y1_), (x2, y2_) in zip(points, points[1:]):
            last = (x2, y2_) == points[-1]
            if last:
                arrow(s, x1, y1_, x2, y2_, color=color, dashed=True)
            else:
                ln = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, x1, y1_, x2, y2_)
                ln.line.color.rgb = color
                ln.line.width = Pt(1.25)
                dash = etree.SubElement(ln.line._get_or_add_ln(), qn("a:prstDash"))
                dash.set("val", "dash")

    # kills: falsifier → agent, routed just below the top row
    yk = y0 + bh + Inches(0.24)
    path([(xs[5] + bw * 0.3, y0 + bh), (xs[5] + bw * 0.3, yk), (xs[3] + bw * 0.7, yk), (xs[3] + bw * 0.7, y0 + bh)], NEGATIVE)
    text(s, xs[3] + bw * 0.78, yk + Inches(0.04), Inches(2.4), Inches(0.3), "kills → retry / reframe / dead",
         size=8.5, color=NEGATIVE, font=MONO)
    # rejections: gate → agent, routed below the second row and up the empty column
    yr = y1 + bh + Inches(0.24)
    path([(xs[5] + bw * 0.2, y1 + bh), (xs[5] + bw * 0.2, yr), (xs[3] + bw * 0.35, yr), (xs[3] + bw * 0.35, y0 + bh)], ATTENTION)
    text(s, xs[3] + bw * 0.45, yr + Inches(0.04), Inches(3.4), Inches(0.3), "rejections → corrections in the agent's memory",
         size=8.5, color=ATTENTION, font=MONO)
    # caption strip
    y2 = Inches(5.85)
    cw = (CONTENT_W - Inches(0.5)) / 3
    text(s, MARGIN, y2, cw, Inches(1), [[("The graph aims. ", {"bold": True, "color": ACCENT}),
                                        ("A missing path between two supported nodes is a candidate untested bridge; the agent's own memory is the search frontier.", {"color": MUTED})]], size=12)
    text(s, MARGIN + cw + Inches(0.25), y2, cw, Inches(1), [[("The falsifier kills. ", {"bold": True, "color": NEGATIVE}),
                                                             ("Seven checks on the numbers alone. No gene identity, no effect size, no notion of importance.", {"color": MUTED})]], size=12)
    text(s, MARGIN + 2 * (cw + Inches(0.25)), y2, cw, Inches(1), [[("The person decides. ", {"bold": True, "color": ATTENTION}),
                                                                   ("Nothing reaches the master graph without a written note, and every rejection is pushed back into the agent's memory.", {"color": MUTED})]], size=12)
    notes(s, """
[1:45 — 40 s]  This is ARCHITECTURE.md section 1 drawn as boxes. Walk left to right once, then the two dashed
arrows.

"Left to right: a project is a corpus definition. We build the corpus from Europe PMC, open access only,
licence recorded per article. A model reads every paper against closed menus and code grounds every name
to an ontology identifier, so two papers asserting the same thing land on one row. That is the graph.
The agent takes one action per step: search the graph, read a paper, find a dataset, read a method guide,
write and run Python. When it wants to keep a result it submits it. The falsifier checks only whether the
numbers can be trusted. Survivors become cards; a person validates or rejects with a written note."

Then: "Two arrows go backwards. Kills go back to the agent as retry, reframe or dead. Human rejections go back
as corrections it must not repeat. Feedback that does not reach the agent's next turn is a bug in our
codebase, by invariant."

If asked what is not domain-specific: the loop, the memory, the falsifier contract and the gate. What is
biology today: Europe PMC discovery, HGNC/ChEBI/MONDO grounding, DepMap/GEO adapters and the 21 method guides.
""")


# ---------------------------------------------------------------- 05 one loop, end to end
def slide_story():
    s = new_slide("04 / one story, not a tour", "One investigation, end to end.", "ILLUSTRATIVE",
                  "[TODO replace every bracket with the recorded investigation chosen for the demo; then change this tag to MEASURED]")
    steps = [
        ("1 · A CLAIM IN THE LITERATURE", "“[TODO exact quote from the paper]”\n[TODO first author, year] · claim_id [TODO]", ACCENT),
        ("2 · AN UNTESTED BRIDGE", "path([TODO gene A], [TODO gene B]) → none.\nBoth nodes established (≥2 sources); no edge between them; nothing in engine_tests.", ACCENT),
        ("3 · THE METHOD GUIDE", "get_skill(depmap_dependency) [TODO or the guide actually used]. The rigor contract: permute at the independent unit, ≥ 8 units per group, predeclare direction.", FG),
        ("4 · CODE, RUN, RESULT", "RESULT: {\"effect\": [TODO], \"p_null\": [TODO], \"null_model\": \"[TODO]\", \"n_units\": [TODO], \"robust\": [TODO]}", FG),
        ("5 · THE FALSIFIER'S VERDICT", "[TODO CANDIDATE, or KILL:<slug>]. If killed: the agent saw the slug on its next turn and [TODO retried / reframed].", NEGATIVE),
        ("6 · THE PERSON AT THE GATE", "Card shows the edge, the quotes, the numbers. Decision: [TODO validated / rejected]. Note: “[TODO the reviewer's written note]”.", ATTENTION),
    ]
    cw = (CONTENT_W - Inches(0.5)) / 3
    ch = Inches(1.95)
    for i, (h, b, acc) in enumerate(steps):
        col, row = i % 3, i // 3
        x = MARGIN + col * (cw + Inches(0.25))
        y = Inches(2.35) + row * (ch + Inches(0.2))
        card(s, x, y, cw, ch, h, b, accent=acc, body_size=11.5)
    notes(s, """
[2:25 — 60 s]  Show one concrete loop, not a feature tour. This slide is a template: the six cards are the
six things a judge must see once, in order, for one real candidate.

[TODO — before the demo]
1. Pick the investigation: a run on the pancreatic corpus (demo/pdac, 100 frozen full-text papers) whose
   candidate actually reached the review queue (plans/PLAN-demo-slides.md open item).
2. Fill the six cards from the recorded trace (data/processed/reasoning_<run_id>.jsonl) and the
   engine_tests row. Use the exact quote, the exact RESULT line, the exact kill slug or CANDIDATE.
3. Decide live vs recorded playback in the console. Recommendation: recorded playback in the
   Investigations view (deterministic, from ordered journal events), with the terminal button as backup.
4. Change this slide's tag to MEASURED in build_deck.py only when every bracket is gone.

Script once filled: "Here is one. The paper says [quote]. The agent asked the graph for a path between
[A] and [B] and got nothing back, with both nodes well supported. It read the dependency-screen method
guide, wrote forty lines of Python against frozen DepMap tables, and printed one line: effect, p, units,
robustness. The falsifier said [verdict]. [If killed: it came back with the fix on the next turn.] A human
looked at the card, the quotes and the numbers, and wrote: [note]. That note is now in the agent's memory."
""")


# ---------------------------------------------------------------- 06 the claim atom
def slide_graph():
    s = new_slide("05 / the graph", "Identity keys never contain free text.", "IMPLEMENTED",
                  "The model picks from menus; code grounds every name. That is why two papers asserting the same thing land on one row.")
    # left: spine diagram
    y = Inches(2.4)
    node(s, MARGIN, y + Inches(0.35), Inches(1.9), Inches(0.8), "KRAS", "HGNC:6407 · mutant", fill=SELECTED, line=EDGE, mono=True)
    node(s, MARGIN + Inches(2.5), y + Inches(0.35), Inches(1.9), Inches(0.8), "increases", "closed predicate set", fill=SURFACE, line=BORDER)
    node(s, MARGIN + Inches(5.0), y + Inches(0.35), Inches(1.9), Inches(0.8), "glycolysis", "GO:0006096 · activity", fill=SELECTED, line=EDGE, mono=True)
    arrow(s, MARGIN + Inches(1.9), y + Inches(0.75), MARGIN + Inches(2.5), y + Inches(0.75))
    arrow(s, MARGIN + Inches(4.4), y + Inches(0.75), MARGIN + Inches(5.0), y + Inches(0.75))
    text(s, MARGIN, y + Inches(1.3), Inches(7), Inches(0.35), "spine = subject · predicate · object · aspect, plus entity state   →   claim_id",
         size=10, color=SUBTLE, font=MONO)
    text(s, MARGIN, y - Inches(0.02), Inches(7), Inches(0.3), "ONE CLAIM (illustrative values)", size=9.5, color=SUBTLE, font=MONO)
    # evidence block
    rect(s, MARGIN, y + Inches(1.75), Inches(6.9), Inches(2.5), fill=SURFACE, line=BORDER, radius=True)
    text(s, MARGIN + Inches(0.25), y + Inches(1.85), Inches(6.5), Inches(0.3), "EVIDENCE, ONE ROW PER SOURCE", size=9.5, color=SUBTLE, font=MONO)
    bullets(s, MARGIN + Inches(0.25), y + Inches(2.2), Inches(6.5), Inches(2.0), [
        "the exact quote, its section, the surface predicate, evidence and study type, certainty",
        "context slots (cell line, tissue, organism) each marked stated / inherited / unspecified",
        "attribution: own finding or a citation, so ten echoes of one experiment count as one",
        "contradictions computed on demand: opposite sign, same dimension → status disputed",
    ], size=11.5, color=MUTED, gap=4)
    # right: grounding table
    rows = [("category", "owner vocabulary"), ("genes, proteins", "HGNC via Gilda"), ("chemicals", "ChEBI"),
            ("diseases", "MONDO"), ("phenotypes", "HP"), ("anatomy · cell types", "UBERON · CL"),
            ("cell lines", "Cellosaurus"), ("processes", "GO"), ("gaps", "reviewed local registries, never fake IDs")]
    table(s, MARGIN + Inches(7.4), Inches(2.35), Inches(4.5), rows, [Inches(1.9), Inches(2.6)], size=10.5,
          row_h=Inches(0.33), mono_cols=(1,))
    text(s, MARGIN + Inches(7.4), Inches(5.45), Inches(4.5), Inches(0.9),
         "Four objects on disk: Paper → Experiment → Evidence → Claim, all in one DuckDB file per corpus. "
         "Writing a paper is idempotent: its old contribution is replaced, never duplicated.",
         size=11, color=MUTED)
    notes(s, """
[Backup / 30 s if used in the main run]  Technical depth for the AI-sophistication judges. The point is
the data model, not the model.

"A claim is a spine plus evidence. The spine is subject, predicate, object and aspect, and every one of
those is a closed-vocabulary term or a resolved identifier. Never free text. The model reads the paper
and picks from menus; our code resolves the names through the owner ontology for that category. So when
two papers say the same thing they land on one row, and when they say the opposite the graph marks the
claim disputed. Evidence rows keep the exact quote and whether the paper is reporting its own result or
citing someone else, so ten echoes of one experiment count as one."

The KRAS → glycolysis example is illustrative; the identifiers shown are real but the claim is not from
the demo corpus. [TODO swap in a claim from the pdac corpus if you want this slide to be MEASURED.]

Source: ARCHITECTURE.md sections 3.3–3.7.
""")


# ---------------------------------------------------------------- 07 extraction & model seam
def slide_extraction():
    s = new_slide("06 / where the models are", "Two pinned models, one seam, no API keys.", "IMPLEMENTED",
                  "Model calls happen in exactly one module. Everything downstream is code that can be tested without a model.")
    y = Inches(2.35)
    cw = (CONTENT_W - Inches(0.3)) / 2
    rect(s, MARGIN, y, cw, Inches(4.3), fill=SURFACE, line=BORDER, radius=True)
    text(s, MARGIN + Inches(0.25), y + Inches(0.15), cw, Inches(0.3), "CORPUS → GRAPH (bulk extraction)", size=9.5, color=SUBTLE, font=MONO)
    bullets(s, MARGIN + Inches(0.25), y + Inches(0.5), cw - Inches(0.5), Inches(3.7), [
        [("Discovery. ", {"bold": True}), ("Each query is an independent Europe PMC channel; overlap between channels gives a capture–recapture estimate of how complete the search is.", {"color": MUTED})],
        [("Triage. ", {"bold": True}), ("MiniLM embeddings rank candidates against the theme, locally, with no API.", {"color": MUTED})],
        [("Fetch. ", {"bold": True}), ("Open-access full text only; licence recorded per article; a title-overlap check stops a mis-resolved identifier from pulling the wrong paper.", {"color": MUTED})],
        [("Extract. ", {"bold": True}), ("Opus reads each paper against category, predicate, aspect and context menus and returns claims with source quotes. A separate Sonnet pass checks direction.", {"color": MUTED})],
        [("Repair, then defer. ", {"bold": True}), ("Unresolved claims go to grouped repair with the concrete validation errors; what still fails becomes a deferral row, never a guess.", {"color": MUTED})],
    ], size=11.5, gap=5)
    rect(s, MARGIN + cw + Inches(0.3), y, cw, Inches(4.3), fill=SURFACE, line=BORDER, radius=True)
    text(s, MARGIN + cw + Inches(0.55), y + Inches(0.15), cw, Inches(0.3), "THE SEAM (llm.py)", size=9.5, color=SUBTLE, font=MONO)
    bullets(s, MARGIN + cw + Inches(0.55), y + Inches(0.5), cw - Inches(0.5), Inches(3.4), [
        [("One module. ", {"bold": True}), ("Claude Agent SDK over the operator's own CLI login. There is no API key anywhere in the repo, by rule.", {"color": MUTED})],
        [("Two pinned models. ", {"bold": True}), ("One for scientific judgement (explorer, fork judge, assistant), one for bulk extraction.", {"color": MUTED})],
        [("Resumable sessions. ", {"bold": True}), ("A session is the agent's working memory; that is what makes forking and restart-safe checkpoints possible.", {"color": MUTED})],
        [("Usage ledger. ", {"bold": True}), ("Tokens and cache hits recorded per run, so cost per experiment is a measurement, not a guess.", {"color": MUTED})],
        [("Model-free downstream. ", {"bold": True}), ("Grounding, contradiction, falsifier, gate and console are plain code with deterministic tests.", {"color": MUTED})],
    ], size=12, gap=5)
    notes(s, """
[Backup]  For "Technical Sophistication" under Best Use of AI: thoughtful model selection and orchestration,
plus a real answer to "is AI fundamental or removable?"

"AI is fundamental in two places and deliberately absent everywhere else. Reading papers into structured
claims is the first; nothing but a strong model does that at this fidelity. Reasoning over the graph and
writing experiments is the second. Everything downstream, grounding, contradiction detection, the
falsifier, the gate, the console, is code with deterministic tests, and the model calls go through one
module with two pinned models and no API keys."

If asked about hallucination: the model never writes an identifier. It picks from menus; code grounds.
Quotes are span-checked against the source. Unresolvable claims become deferrals rather than guesses.

Source: ARCHITECTURE.md sections 3.2, 3.3, 8.
""")


# ---------------------------------------------------------------- 08 the agent
def slide_agent():
    s = new_slide("07 / the agent", "Reason → one action → observe. Then a report to its parent.", "IMPLEMENTED",
                  "Sixteen actions, an episodic memory that doubles as the search frontier, and a tree of workers with a parent that allocates.")
    y = Inches(2.35)
    # left: action menu table
    rows = [("action", "what it does"),
            ("search_kg · neighbors · path", "structural reads; a missing path is a candidate bridge"),
            ("search_papers · read_paper", "semantic search over stored full text, paged reads"),
            ("find_datasets", "GEO and ArrayExpress search for real data"),
            ("search_skills · get_skill", "read a method guide before writing code (21 guides)"),
            ("run_experiments", "several Python experiments in parallel"),
            ("log · recall", "ideas, dead ends, open questions with a promise score"),
            ("submit", "send a self-judged experiment to verification"),
            ("fork · checkpoint · done", "mandatory report; the parent continues, splits or prunes")]
    table(s, MARGIN, y, Inches(7.1), rows, [Inches(2.7), Inches(4.4)], size=10.5, row_h=Inches(0.36), mono_cols=(0,))
    # right: tree sketch
    rx = MARGIN + Inches(7.6)
    rect(s, rx, y, Inches(4.3), Inches(3.3), fill=SURFACE, line=BORDER, radius=True)
    text(s, rx + Inches(0.2), y + Inches(0.12), Inches(4), Inches(0.3), "INVESTIGATION TREE (run ids are paths)", size=9.5, color=SUBTLE, font=MONO)
    nw = Inches(1.1)

    def tn(x, yy, label, fill=SELECTED, line=EDGE):
        return node(s, x, yy, nw, Inches(0.42), label, fill=fill, line=line, mono=True, size=10.5)
    tn(rx + Inches(1.6), y + Inches(0.55), "root")
    tn(rx + Inches(0.35), y + Inches(1.35), "root~0")
    tn(rx + Inches(1.6), y + Inches(1.35), "root~1")
    tn(rx + Inches(2.85), y + Inches(1.35), "root~2", fill=SURFACE, line=BORDER)
    tn(rx + Inches(0.95), y + Inches(2.15), "root~1~0")
    tn(rx + Inches(2.25), y + Inches(2.15), "root~1~1")
    for x2 in (Inches(0.35), Inches(1.6), Inches(2.85)):
        arrow(s, rx + Inches(1.6) + nw / 2, y + Inches(0.97), rx + x2 + nw / 2, y + Inches(1.35), weight=1)
    for x2 in (Inches(0.95), Inches(2.25)):
        arrow(s, rx + Inches(1.6) + nw / 2, y + Inches(1.77), rx + x2 + nw / 2, y + Inches(2.15), weight=1)
    text(s, rx + Inches(0.2), y + Inches(2.7), Inches(4), Inches(0.6),
         "pruned branch keeps its findings and pending verification", size=9.5, color=SUBTLE, font=MONO)
    bullets(s, rx, y + Inches(3.5), Inches(4.3), Inches(1.4), [
        [("Absence rule: ", {"bold": True}), ("a capped or truncated search is evidence of presence only; nothing is 'novel' on a partial search.", {"color": MUTED})],
        [("Budgets: ", {"bold": True}), ("18 actions per round, depth 6, 72 descendant slots, restart-safe reports and decisions in SQLite.", {"color": MUTED})],
    ], size=11, gap=4)
    notes(s, """
[Backup / 30 s]  Agent design for the AI judges: not a chat loop, a constrained research loop with memory.

"Each step the agent gets what is new and answers with exactly one JSON action. Its memory is an
exploration log in the same database as the graph, with a promise score on every entry, so the frontier
it expands next is its own past ideas. It cannot claim novelty on a truncated search, by rule. It works in
a tree: a child must file a checkpoint report, and a parent controller decides to continue, split or prune.
Pruning never loses findings. All of this survives a restart because reports and decisions are idempotent
rows in SQLite."

Source: ARCHITECTURE.md section 4. The tree on the slide is a sketch of the id scheme, not a recorded run.
[TODO if a recorded investigation tree exists by demo day, screenshot the Investigations view instead.]
""")


# ---------------------------------------------------------------- 09 the rigor layer
def slide_falsifier():
    s = new_slide("08 / the rigor layer", "A falsifier with no answer key.", "IMPLEMENTED",
                  "It judges only whether the numbers can be trusted. Whether a result matters is decided by a person at the gate.")
    y = Inches(2.35)
    rows = [("check", "kill slug", "kind"),
            ("required RESULT fields missing or mistyped", "malformed-result", "invalid"),
            ("effect is not a finite number", "no-effect", "invalid"),
            ("fewer than 8 independent units", "too-few-units", "underpowered"),
            ("p_null outside (0, 1]", "malformed-p", "invalid"),
            ("direction disagrees with the predicted sign", "direction-wrong", "refuted"),
            ("p_null above 0.05", "not-significant", "inconclusive"),
            ("robustness check failed (leave-one-group-out)", "not-robust", "refuted")]
    table(s, MARGIN, y, Inches(7.3), rows, [Inches(3.9), Inches(1.9), Inches(1.5)], size=11, row_h=Inches(0.37), mono_cols=(1, 2))
    text(s, MARGIN, y + Inches(3.1), Inches(7.3), Inches(0.9),
         "Fixable kills come back to the agent as needs-retry, a wrong direction as reframe, a pass as promising. "
         "There is deliberately no minimum-effect gate: the effect size is filled by the agent and validated by nothing.",
         size=11.5, color=MUTED)
    rx = MARGIN + Inches(7.8)
    rect(s, rx, y, Inches(4.1), Inches(3.95), fill=SURFACE, line=BORDER, radius=True)
    text(s, rx + Inches(0.2), y + Inches(0.12), Inches(3.8), Inches(0.3), "THE RIGOR CONTRACT EVERY EXPERIMENT SIGNS", size=9.5, color=SUBTLE, font=MONO)
    bullets(s, rx + Inches(0.2), y + Inches(0.5), Inches(3.75), Inches(3.4), [
        "permute at the truly independent unit (donors, not wells)",
        "report a Phipson–Smyth permutation p that is never exactly zero",
        "predeclare the direction; match it",
        "hold up under leave-one-group-out",
        "at least 8 units per group",
        "decide the analysis before seeing the result",
        "include a negative control where possible",
    ], size=11.5, color=FG, gap=4)
    text(s, rx, y + Inches(4.1), Inches(4.1), Inches(0.5), "Survived ≠ true. Survived = the numbers are sound.",
         size=12, color=ATTENTION, bold=True)
    notes(s, """
[3:25 — 40 s]  Why the rigor layer matters, and why there is no answer key.

"Seven checks, all on the numbers. Missing fields, non-finite effect, too few units, a malformed p, the
wrong direction, not significant, not robust. Nothing about which gene it is or how big the effect is,
because the agent fills the effect and nothing validates it. The falsifier cannot be gamed by picking an
important-sounding target. Every experiment also signs a contract: permute at the independent unit, so
wells are never donors; a permutation p that is never exactly zero; direction declared before the run;
leave-one-group-out. If the agent breaks the contract the kill comes back on its next turn with the slug,
and it either fixes it or reframes."

Close on the amber line. Say it twice if you have to.

Source: ARCHITECTURE.md section 5 (table) and section 4.1 (contract). falsifier.py is ~100 lines; invite
a judge to read it.
""")


# ---------------------------------------------------------------- 10 anytime-valid evidence
def slide_evalue():
    s = new_slide("09 / evidence that survives peeking", "Anytime-valid evidence on a real held-out cohort.", "MEASURED",
                  "An agent that runs experiments in sequence must not be able to p-hack itself by stopping when the number looks good.")
    data = json.loads((ROOT / "research/learned-evalue-validation/real-expression/evaluation.json").read_text())
    methods = data["primary"]["methods"]
    cd = CategoryChartData()
    cd.categories = [str(i) for i in range(7)]
    series = [("Learned encoder (128)", methods["autoencoder"]["log_wealth_path"], ACCENT),
              ("PCA (64)", methods["pca"]["log_wealth_path"], ATTENTION),
              ("IFIT3 scalar", methods["scalar"]["log_wealth_path"], NEGATIVE),
              ("Anytime threshold, α = 0.05 (log 20)", [2.9957] * 7, SUBTLE)]
    for name, vals, _ in series:
        cd.add_series(name, vals)
    gx, gy, gw, gh = MARGIN, Inches(2.3), Inches(7.4), Inches(4.35)
    rect(s, gx, gy, gw, gh, fill=SURFACE, line=BORDER, radius=True)
    gframe = s.shapes.add_chart(XL_CHART_TYPE.LINE_MARKERS, gx + Inches(0.15), gy + Inches(0.35), gw - Inches(0.3), gh - Inches(0.45), cd)
    chart = gframe.chart
    chart.has_legend = True
    chart.legend.position = XL_LEGEND_POSITION.BOTTOM
    chart.legend.include_in_layout = False
    chart.legend.font.size = Pt(9)
    chart.legend.font.color.rgb = MUTED
    chart.legend.font.name = SANS
    chart.font.name = SANS
    chart.font.size = Pt(9)
    chart.font.color.rgb = MUTED
    for ax in (chart.category_axis, chart.value_axis):
        ax.format.line.color.rgb = BORDER
        ax.tick_labels.font.color.rgb = MUTED
        ax.tick_labels.font.size = Pt(9)
        ax.tick_labels.font.name = MONO
    chart.value_axis.has_major_gridlines = True
    chart.value_axis.major_gridlines.format.line.color.rgb = BORDER
    chart.value_axis.major_gridlines.format.line.width = Pt(0.5)
    chart.category_axis.has_major_gridlines = False
    chart.value_axis.has_title = True
    chart.value_axis.axis_title.text_frame.text = "log wealth"
    chart.category_axis.has_title = True
    chart.category_axis.axis_title.text_frame.text = "scored batch (after two burn-in batches)"
    for ax in (chart.value_axis, chart.category_axis):
        r = ax.axis_title.text_frame.paragraphs[0].runs[0]
        _font(r, 9, SUBTLE, False, MONO)
    for i, (name, vals, color) in enumerate(series):
        ser = chart.series[i]
        ser.format.line.color.rgb = color
        ser.format.line.width = Pt(2.25 if i < 3 else 1.25)
        ser.smooth = False
        if i == 3:
            ser.marker.style = XL_MARKER_STYLE.NONE
            ln = ser.format.line._get_or_add_ln()
            dash = etree.SubElement(ln, qn("a:prstDash"))
            dash.set("val", "dash")
        else:
            ser.marker.style = XL_MARKER_STYLE.CIRCLE
            ser.marker.size = 6
            ser.marker.format.fill.solid()
            ser.marker.format.fill.fore_color.rgb = color
            ser.marker.format.line.color.rgb = color
    # transparent chart background
    cs = chart._chartSpace
    sppr = cs.find(qn("c:spPr"))
    if sppr is None:
        sppr = etree.SubElement(cs, qn("c:spPr"))
    etree.SubElement(sppr, qn("a:noFill"))
    plot_sppr = etree.SubElement(chart.plots[0]._element.getparent(), qn("c:spPr"))
    etree.SubElement(plot_sppr, qn("a:noFill"))
    text(s, gx + Inches(0.25), gy + Inches(0.1), Inches(7), Inches(0.3),
         "GSE212041 · 374 day-zero donors · COVID+ vs symptomatic COVID− · seed fixed before outcomes", size=9, color=SUBTLE, font=MONO)
    # right column
    rx = MARGIN + Inches(7.7)
    text(s, rx, Inches(2.3), Inches(4.2), Inches(0.3), "WHAT AN E-VALUE BUYS", size=9.5, color=SUBTLE, font=MONO)
    bullets(s, rx, Inches(2.62), Inches(4.2), Inches(1.6), [
        [("Peek any time. ", {"bold": True}), ("Wealth is a nonnegative martingale under the null; by Ville's inequality the chance it ever crosses 1/α is at most α.", {"color": MUTED})],
        [("Learned, but fair. ", {"bold": True}), ("A neural bettor trains only on past units and is scored on fresh ones; the encoder is frozen on a disjoint donor split.", {"color": MUTED})],
    ], size=11.5, gap=5)
    rows = [("control", "result"),
            ("artificial null, 200 sign draws", "0 of 200 final rejections"),
            ("invalid label-memorisation control", "caught: rejects 100 %"),
            ("ordinary permutation, same donors", "p = 0.0001 · e = 99"),
            ("ten predeclared re-orderings", "enc 9/10 · PCA 5/10 · scalar 8/10")]
    table(s, rx, Inches(4.3), Inches(4.25), rows, [Inches(2.2), Inches(2.05)], size=9.5, row_h=Inches(0.33), mono_cols=(1,))
    text(s, rx, Inches(6.1), Inches(4.25), Inches(0.6),
         "Standalone diagnostic, tested, deliberately not yet wired to verdicts. Encoder trained on an L40S in 3.4 s.",
         size=10, color=ATTENTION)
    notes(s, """
[Backup / 45 s; use in the main run for the Best-Use-of-AI judges]  This is the one measured research result
on main and it addresses "hallucination and reliability" head-on.

"An autonomous scientist runs experiments in sequence and looks at the numbers as it goes. With p-values
that is p-hacking by construction: keep going until it looks good, then stop. E-values fix that. Think of
it as betting against the null hypothesis: your wealth is a martingale, and the probability it ever
crosses twenty is at most one in twenty, no matter when you stop. We implemented the deep anytime-valid
construction from Pandeva et al. (AISTATS 2024): a small neural bettor that trains only on past donors and
is scored on fresh ones. On a real held-out cohort, 374 COVID-era neutrophil donors, all three
representations cross the threshold. The artificial null gave zero false rejections in 200 draws. And our
harness caught the invalid control that memorises labels: it rejects every time, which is exactly the leak
the design forbids."

Be honest about status in the amber line: it is a standalone diagnostic, tested, not yet wired into the
falsifier's verdict. That is the next step, and it is why the three learned-tool plans exist.

Numbers: research/learned-evalue-validation/real-expression/{README.md, evaluation.json, training.json}.
Final e-values: encoder 3,652.8; PCA 85.8; IFIT3 scalar 5,964.4; calibrated permutation 99.0.
Do not say the encoder "beats" the scalar: the simpler scalar has the larger final evidence in the primary run.
""")


# ---------------------------------------------------------------- 11 the human gate
def slide_gate():
    s = new_slide("10 / the person at the gate", "Nothing reaches the master graph without a written note.", "IMPLEMENTED",
                  "Every human decision is written back onto the agent's memory. Feedback that does not reach its next turn is a bug.")
    y = Inches(2.35)
    # a review card mock
    cx, cw, ch = MARGIN, Inches(6.2), Inches(4.2)
    rect(s, cx, y, cw, ch, fill=SURFACE, line=BORDER, radius=True)
    pill(s, cx + Inches(0.25), y + Inches(0.2), "CANDIDATE", ACCENT, ACCENT_INK, w=Inches(1.15))
    text(s, cx + Inches(1.55), y + Inches(0.2), Inches(4.5), Inches(0.3), "engine_tests · [TODO id]  ·  awaiting review", size=9.5, color=SUBTLE, font=MONO)
    text(s, cx + Inches(0.25), y + Inches(0.6), cw - Inches(0.5), Inches(0.5),
         [[("[TODO subject] ", {"bold": True, "font": MONO}), ("depends_on ", {"color": ACCENT, "font": MONO}), ("[TODO object]", {"bold": True, "font": MONO})]], size=14)
    hline(s, cx + Inches(0.25), y + Inches(1.1), cw - Inches(0.5))
    text(s, cx + Inches(0.25), y + Inches(1.2), cw - Inches(0.5), Inches(0.9),
         [[("Literature  ", {"color": SUBTLE, "font": MONO, "size": 9.5}),
           ("“[TODO exact quote from the source paper]” — [TODO paper], section [TODO]", {"color": MUTED, "italic": True})]], size=11.5)
    text(s, cx + Inches(0.25), y + Inches(2.05), cw - Inches(0.5), Inches(0.6),
         [[("Numbers  ", {"color": SUBTLE, "font": MONO, "size": 9.5}),
           ("effect [TODO] · p_null [TODO] · n_units [TODO] · robust [TODO] · null: [TODO]", {"font": MONO, "size": 10.5})]], size=11.5)
    text(s, cx + Inches(0.25), y + Inches(2.6), cw - Inches(0.5), Inches(0.5),
         [[("Falsifier  ", {"color": SUBTLE, "font": MONO, "size": 9.5}), ("CANDIDATE — all seven checks passed", {"color": ACCENT, "font": MONO, "size": 10.5})]], size=11.5)
    rect(s, cx + Inches(0.25), y + Inches(3.15), cw - Inches(0.5), Inches(0.8), fill=BG, line=BORDER, radius=True)
    text(s, cx + Inches(0.4), y + Inches(3.25), cw - Inches(0.8), Inches(0.6),
         "Decision note (required): [TODO the reviewer's own words — why this is, or is not, worth believing]",
         size=10.5, color=SUBTLE, italic=True)
    # right: what happens next
    rx = MARGIN + Inches(6.6)
    card(s, rx, y, Inches(5.1), Inches(1.9), "VALIDATED →",
         "The card, its literature provenance and the note are copied into a separate master graph. The working "
         "graph is untouched; the console stays read-only except for this one explicit write.", accent=ACCENT)
    card(s, rx, y + Inches(2.1), Inches(5.1), Inches(2.1), "REJECTED →",
         "Stays local. The note is pushed into the explorer's memory as a correction it must not repeat, visible "
         "on its next turn. The gate is where a lab's judgement becomes the agent's judgement.", accent=NEGATIVE)
    notes(s, """
[Backup / 30 s]  The human gate is the product's answer to "how do you know it is true?" and the design
judges' "form follows function".

"A candidate is not a discovery. It becomes a card: the edge it tests, the exact quotes, the numbers, and
the falsifier's verdict. A person validates or rejects, and both require a written note; an unexplained
verdict is skipped. Validated cards go into a separate master graph with their provenance. Rejections go
back into the agent's memory as corrections. That is how a lab's judgement becomes the agent's judgement
over time."

Status detail: the review controls are currently hidden in the frontend; the backend routes and
decision persistence exist and are tested (ARCHITECTURE.md section 6, frontend/DESIGN.md).
[TODO decide whether to re-expose the review controls for the demo, or show a recorded decision.]
The card on the slide is a layout mock; fill it from the recorded investigation or replace it with a
screenshot of the real Knowledge view claim inspector.
""")


# ---------------------------------------------------------------- 12 persona
def slide_persona():
    s = new_slide("11 / who it is for", "Built for the person who has to decide what is true.", "IMPLEMENTED",
                  "A guiding persona, and the design decisions that fall out of her.")
    y = Inches(2.35)
    rect(s, MARGIN, y, Inches(4.4), Inches(4.25), fill=SURFACE, line=BORDER, radius=True)
    text(s, MARGIN + Inches(0.25), y + Inches(0.15), Inches(4), Inches(0.3), "GUIDING PERSONA", size=9.5, color=SUBTLE, font=MONO)
    text(s, MARGIN + Inches(0.25), y + Inches(0.45), Inches(4), Inches(0.7), "The computational biologist in a small lab", size=14, bold=True)
    bullets(s, MARGIN + Inches(0.25), y + Inches(1.2), Inches(3.9), Inches(3.0), [
        "owns one corpus and one question at a time; a run is hours, a follow-up wet-lab test is months",
        "trusts quotes and denominators, not summaries; has been burned by a p-hacked collaborator",
        "works long sessions in a dark room; keyboard first; needs to leave and come back",
        "will not accept a black box in a paper's methods section",
        "is the only person allowed to say 'true'",
    ], size=11.5, color=MUTED, gap=5)
    rows = [("she needs", "so the design does"),
            ("to check the source herself", "every claim opens to its exact quotation and paper; developer ids in disclosures"),
            ("never to mistake a lead for a result", "'candidate' is never styled as a discovery; missing measurements are never zero"),
            ("to know what the machine is doing now", "intent, runtime execution and worker liveness are separate signals"),
            ("her decision to teach the agent", "a written note is required; rejections reach the agent's next turn"),
            ("calm, not telemetry", "no gradients, glass, neon, fake counters; motion only describes change"),
            ("to work her way", "dark and light themes, reduced motion respected, keyboard focus, narrow screens")]
    table(s, MARGIN + Inches(4.7), y, Inches(7.2), rows, [Inches(2.6), Inches(4.6)], size=10.5, row_h=Inches(0.55))
    notes(s, """
[Backup / 30 s]  For "Understanding of the User" (30 pts, Best in Design). The persona is deliberately
narrow. If judges ask "what about pharma?", the answer is on the deployment slide: the lab user is the
wedge; the persona does not change.

"We designed for one person: the computational biologist in a small lab who owns the corpus and is the
only one allowed to say 'true'. She trusts quotes and denominators, not summaries. So every claim opens to
its exact quotation. A candidate is never styled as a discovery. A missing measurement is never drawn as
zero. Her decision requires a note because the note is how the agent learns. And the whole workspace is a
quiet instrument: no counters, no glow, motion only when something actually changed."

Source: frontend/DESIGN.md. The persona text on this slide is written for the deck; [TODO have the team
confirm or sharpen it, ideally with one real user conversation before the demo].
""")


# ---------------------------------------------------------------- 13 the workspace
def slide_design():
    s = new_slide("12 / the workspace", "A quiet, precise scientific instrument.", "IMPLEMENTED",
                  "Three surfaces: Investigations, Library, Knowledge. The tree owns the visual emphasis.")
    y = Inches(2.35)
    # screenshot placeholders
    for i, (label, sub) in enumerate([("INVESTIGATIONS", "search tree of agents · live activity feed · each experiment with code, result, provenance"),
                                      ("KNOWLEDGE", "claim graph with entity shapes and signed edges · claim inspector with quotes and sources")]):
        x = MARGIN + i * Inches(4.05)
        rect(s, x, y, Inches(3.85), Inches(2.6), fill=SURFACE, line=BORDER, radius=True)
        text(s, x, y + Inches(0.9), Inches(3.85), Inches(0.5), f"[TODO screenshot: {label} view]", size=11, color=SUBTLE,
             font=MONO, align=PP_ALIGN.CENTER)
        text(s, x + Inches(0.2), y + Inches(2.65), Inches(3.6), Inches(0.7), sub, size=9.5, color=SUBTLE, font=MONO)
    # palette swatches
    px = MARGIN + Inches(8.3)
    text(s, px, y, Inches(3.6), Inches(0.3), "TOKENS (frontend/src/styles.css)", size=9.5, color=SUBTLE, font=MONO)
    sw = [("#151a1b", BG, "background"), ("#1b2122", SURFACE, "surface"), ("#edf0ea", FG, "text"),
          ("#a6cabb", ACCENT, "selection · sea-green"), ("#e4bb7f", ATTENTION, "uncertainty · amber"), ("#e5a6a0", NEGATIVE, "failure · rose")]
    for i, (hexv, colr, name) in enumerate(sw):
        yy = y + Inches(0.4) + i * Inches(0.42)
        rect(s, px, yy, Inches(0.55), Inches(0.32), fill=colr, line=BORDER)
        text(s, px + Inches(0.7), yy + Inches(0.02), Inches(3), Inches(0.3), [[(hexv + "  ", {"font": MONO, "color": SUBTLE}), (name, {"color": MUTED})]], size=10.5)
    text(s, px, y + Inches(3.0), Inches(3.6), Inches(0.6), "IBM Plex Sans · IBM Plex Mono", size=12, bold=True)
    # principles strip
    bullets(s, MARGIN, Inches(5.85), Inches(8), Inches(0.9), [
        [("Decorative colour never implies confidence. ", {"bold": True}), ("Provenance distinguishes reference, prediction, derived geometry and illustration.", {"color": MUTED})],
        [("Same tokens on stage. ", {"bold": True}), ("This deck uses the product's palette and type so the demo and the slides read as one instrument.", {"color": MUTED})],
    ], size=11, gap=3)
    text(s, px, Inches(5.85), Inches(3.6), Inches(0.9), "React Flow · Dagre · d3-force · Motion · Radix · 3Dmol (only inside its owning experiment)",
         size=9.5, color=SUBTLE, font=MONO)
    notes(s, """
[Backup / 30 s]  Design Quality & Craft (30) and UX (40). Show the real thing; this slide exists so the
principles are stated even when the live demo is what they see.

[TODO capture two real screenshots (dark theme, populated state) and drop them in:
 frontend e2e can produce them; or run `uv run python scripts/serve_ui.py --port 8765` and screenshot.
 Replace the placeholders in slide_design() with slide.shapes.add_picture(path, x, y, width=Inches(3.85)).]

"The workspace is a quiet instrument. Three surfaces named for what the scientist does: Investigations,
Library, Knowledge. The investigation tree owns the visual emphasis; select an agent and its recorded
activity and experiments appear. Sea-green means selected, amber means uncertain, rose means failed, and
no colour ever implies confidence. IBM Plex throughout. Dark and light, reduced motion respected, keyboard
navigable. And the deck you are looking at uses the same tokens, so the slides and the product read as one
thing."

Novelty claim for judges who ask "is this copied?": the layout was built independently of prior DNHacks UI
and of the usual dashboard idiom; the closest published patterns (claim-to-source in one click, bounded
focused graph, stable layout) come from research tools like Elicit and Connected Papers, and we cite them.
""")


# ---------------------------------------------------------------- 14 reliability
def slide_reliability():
    s = new_slide("13 / reliability", "Where it can fail, and what catches it.", "IMPLEMENTED",
                  "Failure modes are named, tested, and shown honestly in the interface.")
    y = Inches(2.35)
    cw = (CONTENT_W - Inches(0.5)) / 3
    card(s, MARGIN, y, cw, Inches(3.6), "HALLUCINATION",
         "The model never writes an identifier: it picks from menus and code grounds. Quotes are span-checked. "
         "Unresolvable claims become deferrals. The absence rule forbids 'novel' on a truncated search. "
         "Results must be one typed RESULT line or they do not exist.", accent=ACCENT)
    card(s, MARGIN + cw + Inches(0.25), y, cw, Inches(3.6), "SECURITY & ISOLATION",
         "Console bound to localhost; inspection is read-only; DuckDB opened read-only with a snapshot when a run "
         "holds the lock. No API keys in the repo. Experiment code runs in a sandbox (Docker today; a lighter "
         "runtime is a pending decision). Private scoring is kept out of agent feedback by construction.", accent=ATTENTION)
    card(s, MARGIN + 2 * (cw + Inches(0.25)), y, cw, Inches(3.6), "TESTING REGIMEN",
         "Tracked Python suite: 270 passed, 18 skipped from a clean checkout of main (2026-09-06); the wider "
         "local suite with unversioned vocabulary data reports 648 passed. Browser suite in Playwright against an "
         "empty-data server. The architecture endpoint reads action names, thresholds and budgets from source "
         "by AST, so the docs fail loudly if the code drifts.", accent=FG)
    rect(s, MARGIN, y + Inches(3.8), CONTENT_W, Inches(0.85), fill=SURFACE, line=BORDER, radius=True)
    text(s, MARGIN + Inches(0.25), y + Inches(3.9), CONTENT_W - Inches(0.5), Inches(0.7), [
        [("Planned, not built: ", {"bold": True, "color": ATTENTION}),
         ("EVAL-01, a rerunnable safety fixture matrix (untrusted instruction in retrieved text, path escape, timeout, restart) with exact denominators; "
          "EVAL-02, paired runs measuring whether human feedback changes later behaviour. Both wait for explicit approval.", {"color": MUTED})]], size=11)
    notes(s, """
[4:05 — 35 s]  Reliability, Evaluation & Trustworthiness (25) and the security part of Feasibility.

"Three places it can fail. Hallucination: the model never writes an identifier, quotes are checked
against the source, and a result is one typed line or it does not exist. Isolation: local-only console,
read-only inspection, no API keys, sandboxed experiment code, and private scoring that cannot leak back into
the agent's feedback. Testing: about six hundred and fifty Python tests plus a browser suite, and an
architecture endpoint that reads thresholds out of the source by AST, so the documentation fails loudly if
the code drifts."

Then the amber line: "What we have not built yet is the adversarial fixture matrix and a paired-run
measurement of whether feedback actually changes behaviour. Both are specified; neither is claimed."

Test count sources: `uv run --extra dev pytest tests` in a clean worktree of main on 2026-09-06 gave
270 passed, 18 skipped (the tracked suite; tests/ is gitignored except force-added files). The board
post for PR #41 reports 648 passed, 19 skipped, 12 pre-existing failures with the wider unversioned
local suite. Say the 270 figure unless you have rerun the wider suite yourself.
[TODO rerun on the demo commit and update the card.]
Docker status: ARCHITECTURE.md section 4.5 (product decision to remove; migration not done). Say it as
written; do not promise the replacement runtime.
""")


# ---------------------------------------------------------------- 15 feasibility
def slide_feasibility():
    s = new_slide("14 / beyond the hackathon", "Local-first, public data, open-access text. It runs on a laptop.", "IMPLEMENTED",
                  "Cost, security, infrastructure, regulation, integration and adoption, in that order.")
    y = Inches(2.35)
    rows = [("", "today", "what changes at scale"),
            ("cost", "one machine; DuckDB; local MiniLM; tokens per run recorded in a ledger", "per-experiment cost is a measured number [TODO fill from UsageLedger]; GPU only for encoder training"),
            ("security", "localhost console; no keys; sandboxed code; private scoring separated", "per-lab deployment behind the lab's own login; no shared tenant needed"),
            ("infrastructure", "Python 3.12, Node 22, one DuckDB file per corpus", "corpora are files; scale is more machines, not a new architecture"),
            ("data & regulation", "public open-access text, licence per article; public cohorts; no patient-identifiable data", "copyrighted full text never leaves the machine; publisher deals only if a lab wants them"),
            ("integration", "Europe PMC, PMC, Unpaywall, GEO, ArrayExpress, DepMap; HGNC, ChEBI, MONDO, GO and the other owner ontologies", "new domain = new source adapters and method guides; the loop, memory, falsifier and gate do not change"),
            ("adoption", "the lab that owns the corpus; its decisions become its master graph", "core facilities → pharma target triage → government horizon scanning")]
    table(s, MARGIN, y, CONTENT_W, rows, [Inches(1.6), Inches(5.1), Inches(5.23)], size=10.5, row_h=Inches(0.56), mono_cols=(0,))
    text(s, MARGIN, Inches(6.45), CONTENT_W, Inches(0.4),
         "Mission to market share: every corpus a lab builds is a proprietary, provenance-complete graph of what it knows. The asset compounds with use.",
         size=11.5, color=ACCENT, bold=True)
    notes(s, """
[4:40 — 30 s]  Feasibility & Deployment Potential (25). DTX scores "is there a buyer" and "converting mission
into market share"; answer both in one breath.

"It runs on a laptop today: one DuckDB file per corpus, local embeddings, open-access text with the licence
recorded, public cohorts, no patient data, no API keys. Scale is more machines, not a new architecture. The
first buyer is the lab that owns the corpus, because its decisions become its master graph and that graph
compounds. From there: core facilities, pharma target triage, where 'which of these candidates gets
confirmed' is literally the job, and government horizon scanning."

[TODO fill the per-experiment cost from the UsageLedger of the demo run; until then say "measured per run"
without a number.]
Do not claim revenue, customers or LOIs that do not exist. If asked about a company: "the wedge is the lab;
the moat is the provenance graph each lab accumulates."
""")


# ---------------------------------------------------------------- 16 why it matters (DTX)
def slide_mission(dtx):
    s = new_slide("15 / why it matters", "Compute pointed at the frontier is national infrastructure.", "ILLUSTRATIVE",
                  "Biology is bottlenecked on the ordering of experiments, not on materials. That is an information problem.")
    y = Inches(2.35)
    cw = (CONTENT_W - Inches(0.3)) / 2
    bullets(s, MARGIN, y, cw, Inches(3.6), [
        [("Export controls work on atoms and chips. ", {"bold": True}), ("They do not work on knowing which of the next thousand experiments to run. Lead time is the only durable advantage in biology.", {"color": MUTED})],
        [("Synthesis was never the bottleneck. ", {"bold": True}), ("In the COVID vaccine timeline the sequence-to-candidate step took days; the evidence took most of a year. This engine is an evidence-ordering engine.", {"color": MUTED})],
        [("Sovereign scientific memory. ", {"bold": True}), ("A time-indexed, provenance-complete graph of what a country's science knew, and when, is infrastructure the way a fab is infrastructure.", {"color": MUTED})],
        [("The defender needs to see the frontier first. ", {"bold": True}), ("We rank and test published associations from public, curated data. No sequences, no pathogens, no wet lab.", {"color": MUTED})],
    ], size=12.5, gap=8)
    rect(s, MARGIN + cw + Inches(0.3), y, cw, Inches(3.6), fill=SURFACE, line=BORDER, radius=True)
    text(s, MARGIN + cw + Inches(0.55), y + Inches(0.2), cw - Inches(0.5), Inches(0.3), "A CONGRESSIONALLY CHARTERED BODY ALREADY SAYS IT", size=9.5, color=SUBTLE, font=MONO)
    text(s, MARGIN + cw + Inches(0.55), y + Inches(0.6), cw - Inches(0.5), Inches(1.6), dtx["quote"], size=15, italic=True, spacing=1.3)
    text(s, MARGIN + cw + Inches(0.55), y + Inches(2.3), cw - Inches(0.5), Inches(1.25), dtx["attribution"], size=9.5, color=SUBTLE, font=MONO)
    text(s, MARGIN, Inches(6.1), CONTENT_W, Inches(0.7), dtx["dtx_line"], size=11, color=MUTED)
    notes(s, f"""
[Optional / 30 s]  Use this slide only if the room is DTX-heavy; skip it for a general audience. It maps to
DTX's stated thesis (American leadership in AI, energy, defense, semiconductors, space, health) without
changing the product.

"Nuclear power is bottlenecked on material: you can count centrifuges. Biological power is bottlenecked on
knowing which of the next thousand experiments to run. That is an information problem, and export
controls do not work on it; only lead time does. The COVID vaccine timeline shows synthesis was never the
bottleneck, the evidence was. An engine that tests claims at scale on public data is an evidence-ordering
engine. And the graph it leaves behind, a provenance-complete record of what was known and when, is
infrastructure."

Quote provenance: {dtx['quote_source']}
[TODO verify the exact wording against the primary source before saying it aloud; if unverifiable, drop
the quotation marks and paraphrase.]

Do not say: "predicts discoveries", "AI scientist", "first in the world", "novel algorithm". Say:
"ranks and tests later-confirmed associations from earlier evidence", "evidence-ordering engine with a
verifier stack".
""")


# ---------------------------------------------------------------- 17 what compute buys
def slide_scale():
    s = new_slide("16 / what more compute buys", "Every experiment here costs compute, not bench time.", "PLANNED",
                  "The frozen demo corpus is small on purpose. The loop does not change when the corpus is a field.")
    y = Inches(2.35)
    stats = [("100", "frozen full-text papers in the pancreatic demo corpus, hash-verified", "MEASURED"),
             ("7.2 M", "readable characters, 856 figure files, all checksummed", "MEASURED"),
             ("21", "method guides the agent must read before it writes code", "MEASURED"),
             ("72", "descendant worker slots per investigation; depth 6; 96 actions per node", "IMPLEMENTED"),
             ("[TODO]", "tokens and wall-clock per experiment from the demo run's UsageLedger", "PLANNED"),
             ("[TODO]", "candidates reaching the review queue per 100 experiments", "PLANNED")]
    cw = (CONTENT_W - Inches(0.5)) / 3
    for i, (num, label, tag) in enumerate(stats):
        col, row = i % 3, i // 3
        x = MARGIN + col * (cw + Inches(0.25))
        yy = y + row * Inches(1.75)
        rect(s, x, yy, cw, Inches(1.55), fill=SURFACE, line=BORDER, radius=True)
        text(s, x + Inches(0.25), yy + Inches(0.12), cw - Inches(0.5), Inches(0.7), num, size=30, bold=True,
             color=ACCENT if tag == "MEASURED" else (FG if tag == "IMPLEMENTED" else ATTENTION), font=MONO)
        text(s, x + Inches(0.25), yy + Inches(0.85), cw - Inches(0.5), Inches(0.65), label, size=10.5, color=MUTED)
        fill, ink, _ = TAGS[tag]
        pill(s, x + cw - Inches(1.35), yy + Inches(0.2), tag, fill, ink, w=Inches(1.15), size=8)
    text(s, MARGIN, Inches(6.0), CONTENT_W, Inches(0.6),
         "The lever is throughput: more papers read, more edges scored, more experiments run against public data per dollar. "
         "The falsifier and the gate are what let throughput rise without trust falling.", size=12, color=MUTED)
    notes(s, """
[Optional / 25 s]  Rich's "what is waiting to be found" slide. It is honest about which numbers exist.

"The demo corpus is one hundred frozen papers on pancreatic cancer, hash-verified, seven million readable
characters. That is small on purpose. The loop is the same when the corpus is a field. Every experiment
costs compute, not bench time, and the reason we can turn throughput up without trust going down is the
falsifier and the gate."

[TODO before the demo: run the chosen investigation, read tokens and wall-clock from the UsageLedger and
the runtime journal, and fill the two amber cards. Change their tags to MEASURED. If you cannot, leave
them amber and say "we measure this per run" rather than inventing a number.]

Sources: demo/pdac/README.md (corpus), ARCHITECTURE.md 4.4 (budgets), skills/ (21 guides).
""")


# ---------------------------------------------------------------- 18 roadmap & ask
def slide_roadmap():
    s = new_slide("17 / next, and the ask", "Wire learned evidence into the loop. Then measure whether feedback works.", "PLANNED",
                  "Everything here is specified in plans/ and waits for explicit approval. Nothing here is claimed as built.")
    y = Inches(2.35)
    cw = (CONTENT_W - Inches(0.5)) / 3
    card(s, MARGIN, y, cw, Inches(2.5), "NEXT 30 DAYS",
         "Docker-free experiment runtime with explicit permissions. Re-expose the review gate in the console. "
         "EVAL-01 safety fixtures. Measure cost per experiment and candidates per 100 experiments on the pancreatic corpus.", accent=ACCENT)
    card(s, MARGIN + cw + Inches(0.25), y, cw, Inches(2.5), "NEXT 90 DAYS",
         "Three learned biological tools with native anytime-valid evidence, chosen by five independent reviews: "
         "protein / phospho-signalling, learned pharmacotype association, donor-level cellular ecosystems. "
         "Shared receipt-only confirmation surface; frozen encoders on the L40S.", accent=ATTENTION)
    card(s, MARGIN + 2 * (cw + Inches(0.25)), y, cw, Inches(2.5), "THEN",
         "Branch monitoring under a frozen policy: which subtrees pay off, as a private monitor statistic. "
         "EVAL-02: paired runs proving human feedback changes later behaviour. A second domain (materials or "
         "semiconductors) as new source adapters, not a rewrite.", accent=FG)
    rect(s, MARGIN, y + Inches(2.75), CONTENT_W, Inches(1.5), fill=SELECTED, line=EDGE, radius=True)
    text(s, MARGIN + Inches(0.3), y + Inches(2.85), Inches(3), Inches(0.3), "THE ASK", size=9.5, color=ACCENT, font=MONO)
    text(s, MARGIN + Inches(0.3), y + Inches(3.15), CONTENT_W - Inches(0.6), Inches(1.1),
         [[("One wet-lab partner ", {"bold": True}), ("to take the first validated cards prospectively.  ", {"color": MUTED}),
           ("Two design-partner labs ", {"bold": True}), ("to build their own corpora.  ", {"color": MUTED}),
           ("Compute ", {"bold": True}), ("for the encoder training and the paired feedback experiment.", {"color": MUTED})]], size=13.5)
    notes(s, """
[5:10 — 25 s]  The roadmap is what is in plans/, in the order the team wrote it. The ask is concrete.

"Next thirty days: the lighter experiment runtime, the review gate back in the console, the safety
fixtures, and measured cost per experiment. Ninety days: three learned biological tools with native
anytime-valid evidence, chosen by five independent reviews, on a shared receipt-only confirmation surface.
Then branch monitoring and the paired feedback experiment. The ask is one wet-lab partner to take the first
validated cards prospectively, two design-partner labs, and compute."

Sources: plans/evalue-tool-council/README.md (three tools, reviewer table), plans/backlog.md (EVAL-01/02),
ARCHITECTURE.md 4.5 (runtime), 7.1 (branch monitoring). AGENTS.md rule 6: backlog items are not
autonomous assignments; say "specified", never "underway".
""")


# ---------------------------------------------------------------- 19 close
def slide_close():
    global SLIDE_NO
    SLIDE_NO += 1
    s = prs.slides.add_slide(BLANK)
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = BG
    hline(s, MARGIN, Inches(0.9), CONTENT_W)
    text(s, MARGIN, Inches(2.1), CONTENT_W, Inches(3.0),
         [[("Survived verification means the numbers are sound.", {}),
           ("\nTruth is a person's call.", {"color": ACCENT}),
           ("\nWe built the machine that gets you to that call faster.", {"color": MUTED})]],
         size=30, bold=True, spacing=1.2)
    text(s, MARGIN, Inches(5.7), Inches(11), Inches(0.5), "github.com/richykim7/dnhacks   ·   [TODO demo URL]   ·   [TODO contact]",
         size=12, color=SUBTLE, font=MONO)
    hline(s, MARGIN, H - Inches(0.55), CONTENT_W)
    text(s, MARGIN, H - Inches(0.47), Inches(6), Inches(0.3), "DN Research (working name)  ·  DNHacks 2026", size=9, color=SUBTLE, font=MONO)
    text(s, W - MARGIN - Inches(1), H - Inches(0.47), Inches(1), Inches(0.3), f"{SLIDE_NO:02d}", size=9, color=SUBTLE, font=MONO, align=PP_ALIGN.RIGHT)
    notes(s, """
[5:35 — 10 s]  Say the three lines. Stop. Take questions.

Leave this slide up during Q&A; the repo link is on it.
""")


# ---------------------------------------------------------------- appendix A: criteria map
def slide_criteria():
    s = new_slide("appendix A / judging criteria", "Where each criterion is answered.", None,
                  "Five-minute cut: slides 01 · 02 · 03 · 04 · 05 · 09 · 13 · 14 · 17 · 18. Everything else is backup for questions.")
    rows = [("prize · criterion", "pts", "slides", "the evidence we point at"),
            ("Main · Problem & Real-World Impact", "25", "02, 03, 15", "untested edges + public data; compute aimed and trusted; health track"),
            ("Main · Technical Execution", "50", "04–09, 11", "claim atom, grounding, agent tree, falsifier, e-values; working console"),
            ("Main · Feasibility & Deployment", "25", "13, 14, 17", "local-first, licences, no keys, adoption path, concrete ask"),
            ("AI · Novelty & Importance of AI", "25", "06, 07", "AI fundamental in extraction and exploration; removable nowhere else by design"),
            ("AI · Technical Sophistication", "50", "06–09", "two pinned models, one seam, menus + grounding, memory frontier, anytime-valid bettor"),
            ("AI · Reliability, Evaluation, Trust", "25", "08, 09, 13", "seven kills, rigor contract, null + invalid controls, 648 tests, AST-checked docs"),
            ("Design · Quality & Craft", "30", "12", "Plex, charcoal, sea-green/amber/rose semantics, no decoration, accessibility"),
            ("Design · UX & Usability", "40", "05, 10, 12", "one-click claim-to-quote, candidate ≠ discovery, missing ≠ zero, gate needs a note"),
            ("Design · Understanding of the User", "30", "11", "named persona; six decisions derived from her")]
    table(s, MARGIN, Inches(2.3), CONTENT_W, rows, [Inches(3.4), Inches(0.6), Inches(1.4), Inches(6.53)], size=10.5, row_h=Inches(0.42), mono_cols=(1, 2))
    notes(s, """
Backup. Use it to check yourself before the run, not on stage.

Timing plan for a five-minute slot (adjust to the actual limit on the day):
 01 title 0:20 · 02 gap 0:45 · 03 insight 0:40 · 04 picture 0:40 · 05 one loop 1:00 · 09 rigor 0:40 ·
 13 reliability 0:35 · 14 feasibility 0:30 · 17 next 0:25 · 18 close 0:10  →  5:45; trim 05 or 13 to fit.

If the slot is three minutes: 01, 03, 04, 05, 09, 18.
""")


# ---------------------------------------------------------------- appendix B: questions
def slide_questions():
    s = new_slide("appendix B / questions a good judge will ask", "Answers we have already written down.", None)
    qa = [("“Isn't this just a wrapper around a model?”",
           "The model reads papers and proposes; everything that decides is code: grounding, contradiction, the seven kills, the gate. Remove the model and the verifier stack still rejects unsound numbers."),
          ("“How do you know it isn't hallucinating?”",
           "It never writes an identifier; it picks from menus and code grounds. Quotes are span-checked. Partial searches cannot support 'novel'. A result is one typed line or it does not exist."),
          ("“Survived the falsifier, so it's true?”",
           "No. Survived means the numbers are sound. A person says true, with a note, and that note goes back into the agent's memory."),
          ("“Why permutation tests and e-values instead of a bigger model?”",
           "Because the agent runs experiments in sequence and looks as it goes. Anytime-valid evidence is the only kind that survives that. We measured it on a real cohort; it is not yet wired to verdicts."),
          ("“What is actually novel?”",
           "The composition: a provenance-complete claim graph as the search map, an agent whose memory is its frontier, a falsifier with no answer key, and a gate whose decisions teach the agent. No new algorithm is claimed."),
          ("“Are you building the thing you warn about?”",
           "We test published associations on public, curated data. No sequences, no pathogens, no wet lab. The defender needs to see the frontier first."),
          ("“Why you?”",
           "In the hackathon window the team shipped the graph, the agent, the falsifier, the gate, a measured anytime-valid diagnostic, and two negative results about its own ideas. The instinct to falsify ourselves is the product.")]
    y = Inches(2.05)
    cw = (CONTENT_W - Inches(0.3)) / 2
    for i, (q, a) in enumerate(qa):
        col, row = i % 2, i // 2
        x = MARGIN + col * (cw + Inches(0.3))
        yy = y + row * Inches(1.2)
        text(s, x, yy, cw, Inches(0.3), q, size=11.5, bold=True, color=ACCENT)
        text(s, x, yy + Inches(0.3), cw, Inches(0.85), a, size=10, color=MUTED)
    notes(s, """
Backup. Adapted from design/judge-brief.md section 4 to the discovery-engine framing.

"Two negative results about its own ideas" refers to the archived forecasting work (appendix C): greedy
coverage did not beat uniform acquisition, and the policy lab found no novel policy advantage after 5,120
exhaustive cases. Only say it if you are prepared to show appendix C.
""")


# ---------------------------------------------------------------- appendix C: archived backtest
def slide_archive():
    s = new_slide("appendix C / an experiment we ran and then removed from main", "Sealed-cutoff backtest on CIViC 2018 → 2022 (archived).", "MEASURED",
                  "Built during the hackathon, then removed from main (880cac4). Numbers reconcile to the archived run artifacts.")
    y = Inches(2.35)
    rows = [("scorer on the frozen 2018 graph (llm_calls = 0)", "AUROC", "AP"),
            ("full historical graph, 216 evidence rows", "0.82", "0.20"),
            ("initial graph, 54 seed rows", "0.58", "0.05"),
            ("popularity (target degree) baseline", "0.58", "0.06"),
            ("greedy coverage acquisition, 32 acquisitions", "0.60", "0.05"),
            ("uniform acquisition, 32 acquisitions", "0.67", "0.08"),
            ("random expectation", "0.50", "0.035")]
    table(s, MARGIN, y, Inches(7.0), rows, [Inches(4.6), Inches(1.2), Inches(1.2)], size=10.5, row_h=Inches(0.36), mono_cols=(1, 2))
    text(s, MARGIN, y + Inches(2.7), Inches(7.0), Inches(1.5), [
        [("683 candidate variant → therapy edges, 24 later confirmed (base rate 3.5 %). ", {"color": MUTED}),
         ("Rank 1 of 683, PIK3CA mutation → cetuximab / panitumumab, was confirmed. Worst miss: FLT3 ITD → ponatinib at rank 642; the 2018 graph had no path.", {"color": MUTED})],
        [("Memory control: ", {"bold": True, "color": NEGATIVE}),
         ("a no-retrieval Sonnet 5 scored AUROC 0.854 on the same 683 rows, above the structural 0.819. Model memory contaminates any 'AI predicts science' demo; sealed cutoffs are the only defence.", {"color": MUTED})]],
        size=10.5)
    rx = MARGIN + Inches(7.4)
    card(s, rx, y, Inches(4.5), Inches(4.2), "WHY IT IS IN THE APPENDIX",
         "Greedy coverage lost to uniform acquisition. The policy lab (5,120 exhaustive cases, 2,400 certificates, 95 replays) "
         "found no novel policy advantage. Twenty-four positives give wide intervals. The team judged the discovery loop the "
         "stronger product and removed the standalone module. The lesson survived: evidence volume moved the score (0.58 → 0.82) "
         "far more than any policy did. Throughput is the lever.", accent=ATTENTION, body_size=11)
    notes(s, """
Backup only. Show it if a judge asks "can it anticipate anything?" or "have you ever measured yourselves
against a held-out future?" It is also the honest answer to "what did you try that failed?"

Provenance: design/judge-brief.md (local, untracked) reconciled by an independent read of the run JSON on
branch ian/policy-research-forecast-runner: 71 nodes / 131 claims / 216 evidence rows / 683 candidates /
24 confirmed; pooled AUROC full 0.8187, initial 0.5791, popularity 0.5820, greedy 0.6043, uniform 0.6692.
Caveats found in that read: the committed report uses k = 5 and 10 (no P@24 artifact); macro-averaged AP
for the full graph is 0.41, not 0.20; budget matching is marked "unspecified" in the artifact. Do not
quote P@24, and say "pooled" if you quote AP.
Memory-control result: board post ian/judge-brief, PR #24, main f52e2e4.

Say "later recorded", never "first discovered": CIViC additions are curation lag.
""")


# ================================================================ build
def main():
    dtx_path = Path(__file__).resolve().parent / "dtx_context.json"
    dtx = json.loads(dtx_path.read_text()) if dtx_path.exists() else {
        "quote": "[TODO verified quotation from the National Security Commission on Emerging Biotechnology, April 2025 report]",
        "attribution": "NSCEB final report, April 2025 — [TODO page / section]",
        "quote_source": "[TODO url]",
        "dtx_line": "[TODO one line mapping to DTX Ventures' published thesis, with source]",
    }
    slide_title()
    slide_gap()
    slide_bottleneck()
    slide_architecture()
    slide_story()
    slide_graph()
    slide_extraction()
    slide_agent()
    slide_falsifier()
    slide_evalue()
    slide_gate()
    slide_persona()
    slide_design()
    slide_reliability()
    slide_feasibility()
    slide_mission(dtx)
    slide_scale()
    slide_roadmap()
    slide_close()
    slide_criteria()
    slide_questions()
    slide_archive()
    prs.save(OUT)
    print(f"wrote {OUT} ({len(prs.slides)} slides)")


if __name__ == "__main__":
    main()
