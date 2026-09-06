#!/usr/bin/env python3
"""Build an editable DNHacks pitch and matching layout kit. Requires python-pptx."""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)
W, H = 13.333333, 7.5
INK, PAPER, GREEN, AMBER, ROSE = "17201F", "F1EFE7", "A6C9B8", "DEB577", "D99E99"
MUTED, LINE, PANEL, DARKGREEN = "AFB9B2", "3A4944", "222E2A", "365E4D"
FONT, MONO = "IBM Plex Sans", "IBM Plex Mono"
SNAPSHOT = "1e83cfb158dd1c9d35894e05006bd9482a566233"
SOURCES = {
    "pubmed": ("NIH / NLM · About PubMed", "https://pubmed.ncbi.nlm.nih.gov/about/"),
    "seer": ("NCI SEER · Pancreatic Cancer Stat Facts", "https://seer.cancer.gov/statfacts/html/pancreas.html"),
    "dtx": ("DTX Ventures · Vision", "https://www.dtxventures.com/vision"),
    "event": ("DNHacks · Official event and category descriptions", "https://dnhacks.org/"),
    "elicit": ("Elicit · Introducing Elicit Research Agent", "https://elicit.com/blog/introducing-elicit-research-agent"),
    "deepmind": ("Google DeepMind · Co-scientist", "https://deepmind.google/blog/co-scientist-a-multi-agent-ai-partner-to-accelerate-research/"),
}
TALK = []
BOUNDS = []


def color(v):
    return RGBColor.from_string(v)


def flat(sh):
    """Suppress the template's inherited Office drop-shadow preset."""
    for ref in sh._element.xpath('.//a:effectRef'):
        ref.set('idx', '0')
    sh._element.spPr.append(OxmlElement('a:effectLst'))
    return sh


def rect(s, x, y, w, h, fill, stroke=None, radius=False):
    sh = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE,
                            Inches(x), Inches(y), Inches(w), Inches(h))
    sh.fill.solid()
    sh.fill.fore_color.rgb = color(fill)
    if stroke:
        sh.line.color.rgb = color(stroke)
        sh.line.width = Pt(.7)
    else:
        sh.line.fill.background()
    if radius:
        sh.adjustments[0] = .08
    return flat(sh)


def text(s, txt, x, y, w, h, size=22, c=PAPER, bold=False, font=FONT,
         align=PP_ALIGN.LEFT, valign=MSO_ANCHOR.TOP, link=None):
    sh = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = sh.text_frame
    tf.clear()
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.vertical_anchor = valign
    for i, line in enumerate(txt.split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(0)
        p.space_before = Pt(0)
        p.line_spacing = 1.08
        r = p.add_run()
        r.text = line
        r.font.name = font
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.color.rgb = color(c)
        if link:
            r.hyperlink.address = link
    BOUNDS.append((txt[:60], x, y, w, h))
    return sh


def line(s, x1, y1, x2, y2, c=LINE, width=1, arrow=False, dash=False):
    sh = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    sh.line.color.rgb = color(c)
    sh.line.width = Pt(width)
    if dash:
        from pptx.enum.dml import MSO_LINE_DASH_STYLE
        sh.line.dash_style = MSO_LINE_DASH_STYLE.DASH
    if arrow:
        e = OxmlElement("a:tailEnd")
        e.set("type", "triangle")
        sh.line._get_or_add_ln().append(e)
    return flat(sh)


def dot(s, x, y, r=.045, c=GREEN, stroke=None):
    sh = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x-r), Inches(y-r), Inches(r*2), Inches(r*2))
    sh.fill.solid()
    sh.fill.fore_color.rgb = color(c)
    if stroke:
        sh.line.color.rgb = color(stroke)
    else:
        sh.line.fill.background()
    return flat(sh)


def tag(s, txt, x, y, w=2.2, c=GREEN, bg=PANEL):
    rect(s, x, y, w, .31, bg)
    text(s, txt, x+.10, y+.052, w-.18, .21, 9.4, c, True, MONO)


def new_prs():
    p = Presentation()
    p.slide_width, p.slide_height = Inches(W), Inches(H)
    p.core_properties.title = "DN Research — DNHacks 2026"
    p.core_properties.subject = "Editable working pitch: scientific discovery, AI engineering and trustworthy evidence"
    p.core_properties.author = "DNHacks team"
    p.core_properties.keywords = "DNHacks, DN Research, working draft, scientific discovery"
    # Theme fonts keep newly inserted PowerPoint objects consistent with the deck.
    for rel in p.slide_master.part.rels.values():
        if rel.reltype.endswith('/theme'):
            from lxml import etree
            root = etree.fromstring(rel.target_part.blob)
            ns = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
            for node in root.xpath('//a:majorFont/a:latin | //a:minorFont/a:latin', namespaces=ns):
                node.set('typeface', FONT)
            rel.target_part._blob = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
    return p


def slide(p, num, section, title=None, light=False, sub=None):
    s = p.slides.add_slide(p.slide_layouts[6])
    bg, fg, secondary = (PAPER, INK, DARKGREEN) if light else (INK, PAPER, MUTED)
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = color(bg)
    text(s, "DN / RESEARCH", .55, .27, 2.6, .24, 11, fg, True, MONO)
    text(s, section.upper(), 5.0, .28, 7.76, .22, 10, secondary, False, MONO, PP_ALIGN.RIGHT)
    line(s, .55, .72, 12.78, .72, "CDCFC4" if light else LINE, .7)
    line(s, .55, 7.04, 12.78, 7.04, "CDCFC4" if light else LINE, .7)
    text(s, "DNHACKS 2026  /  WORKING PRESENTATION", .55, 7.16, 8, .19, 8, secondary, False, MONO)
    text(s, f"{num:02}", 12.14, 7.11, .64, .29, 12, fg, False, MONO, PP_ALIGN.RIGHT)
    if title:
        text(s, title, .55, 1.02, 12.0, 1.32, 36, fg, True)
    if sub:
        text(s, sub, .57, 2.13, 11.8, .55, 18, secondary)
    return s


def note(s, num, title, script, secs, proof="", update="", criteria="", sources=()):
    source_lines = []
    for source in sources:
        if source in SOURCES:
            name, url = SOURCES[source]
            source_lines.append(f"{name}: {url} (accessed 2026-09-06)")
        else:
            source_lines.append(f"Repository: {source} at {SNAPSHOT}")
    body = (f"TENTATIVE SCRIPT · {secs} seconds\n{script}\n\n"
            f"EVIDENCE / STATUS\n{proof}\n\n"
            f"BEFORE PRESENTING / NEXT EDIT\n{update or 'Recheck against the final demo build; preserve evidence labels.'}\n\n"
            f"JUDGING CRITERIA\n{criteria}\n\nSOURCES\n" + "\n".join(source_lines))
    s.notes_slide.notes_text_frame.text = body
    TALK.append({"slide": num, "title": title, "seconds": secs, "notes": body})


def source_footer(s, txt, key=None, light=False):
    # Full source URLs remain in speaker notes; footers keep the deck palette.
    text(s, txt, .57, 6.67, 12.1, .25, 9, DARKGREEN if light else MUTED)


def graph(s, x, y, w, h, seed=42, pale=False):
    rng = random.Random(seed)
    clusters = [(.20,.30),(.74,.21),(.60,.77)]
    nodes = []
    for k,(cx,cy) in enumerate(clusters):
        group=[]
        for j in range(20):
            a=rng.random()*math.tau
            rr=rng.uniform(.08,.23)
            xx=x+(cx+math.cos(a)*rr)*w
            yy=y+(cy+math.sin(a)*rr)*h
            group.append((xx,yy))
        nodes.append(group)
    for group in nodes:
        for j,a in enumerate(group):
            closest=sorted(range(len(group)),key=lambda k: math.dist(a,group[k]))[1:4]
            for k in closest:
                if k>j:
                    b=group[k]
                    line(s,*a,*b,"BFC9BE" if pale else "394D44",.65)
    for i,group in enumerate(nodes):
        for j,(xx,yy) in enumerate(group):
            dot(s,xx,yy,.025 if j%4 else .045,"698E7B" if pale else "6D9881")
    selected = [nodes[0][2],nodes[0][9],nodes[1][3],nodes[2][2],nodes[2][13]]
    for a,b in zip(selected,selected[1:]):
        line(s,*a,*b,DARKGREEN if pale else GREEN,2,dash=(a==selected[1]))
    for xx,yy in selected:
        dot(s,xx,yy,.095,PAPER if pale else INK,DARKGREEN if pale else GREEN)
        dot(s,xx,yy,.04,DARKGREEN if pale else GREEN)


def card(s,x,y,w,num,title,body,c=GREEN):
    line(s,x,y,x+w,y,c,1.6)
    text(s,num,x,y+.18,w,.4,16,c,False,MONO)
    text(s,title,x,y+.72,w,1.0,27,PAPER,True)
    text(s,body,x,y+1.88,w,1.2,19,MUTED)


def build():
    p = new_prs()
    s=slide(p,1,"Scientific discovery / working name")
    graph(s,6.9,1.25,5.5,4.9)
    text(s,"Point compute at\nthe next scientific\ndiscovery.",.55,1.45,7.1,2.85,46,PAPER,True)
    text(s,"Published evidence → testable hypotheses →\nexperiments a scientist can inspect.",.59,4.68,7,1.0,23,GREEN)
    tag(s,"PROTOTYPE IN PROGRESS",.59,6.15,2.9)
    tag(s,"OPEN CATEGORY / PROPOSED",3.69,6.15,3.32)
    text(s,"Conceptual research map",9.2,6.29,3.3,.22,9,MUTED,font=MONO,align=PP_ALIGN.RIGHT)
    note(s,1,"Point compute at the next scientific discovery.",
         "A useful discovery can start with a connection between papers that nobody has tested together. DN Research is our working name for an engine that finds research directions, writes analyses against public data, and keeps the evidence inspectable. Our ambition is to turn more of the science we already have into experiments worth running.",25,
         "Working name; prototype. No confirmed new biological discovery or performance improvement is claimed.",
         "Replace DN Research after the team selects a product name. Open Category is proposed because the official event describes it as the DTX-sponsored home for cross-cutting technology; this is not a submitted category claim. Confirm the team's entered track. Keep the visual system. Core slides 1–11 target about five minutes, including the demo.",
         "Problem & Real-World Impact; Novelty and Importance of AI",["ARCHITECTURE.md","frontend/DESIGN.md"])

    s=slide(p,2,"01 / Problem & real-world impact",light=True)
    text(s,"Science is abundant.\nThe next experiment is scarce.",.55,1.13,11.9,1.5,39,INK,True)
    text(s,"40M+",.55,3.03,5.2,1.23,82,DARKGREEN,True)
    text(s,"biomedical citations and abstracts\nin PubMed",.60,4.38,5.25,.95,25,INK)
    line(s,6.05,2.95,6.05,5.82,"B5C0B5",1)
    for yy,n,t in [(3.05,"01","Evidence is spread across papers."),(4.05,"02","Plausible connections multiply."),(5.05,"03","Laboratory time is limited.")]:
        text(s,n,6.55,yy,.65,.35,13,DARKGREEN,font=MONO)
        text(s,t,7.28,yy-.02,5.25,.80,25,INK)
    source_footer(s,"Source: NIH / NLM, About PubMed. Citations and abstracts; not our ingested corpus.","pubmed",True)
    note(s,2,"Science is abundant. The next experiment is scarce.",
         "PubMed contains more than forty million citations and abstracts. Finding documents is only the beginning. A researcher still has to connect their claims, choose a tractable question, find the right data and check the result. We are building for that decision: what deserves the next unit of scientific effort?",25,
         "PubMed scale is an external fact. Workflow bottleneck is our product hypothesis, not a measured user-study finding.",criteria="Problem & Real-World Impact (25)",sources=["pubmed"])

    s=slide(p,3,"02 / User & design",title="Built around a scientist’s next decision.")
    tag(s,"WORKING USER HYPOTHESIS",.59,2.48,3.13)
    text(s,"A computational biologist\nin a small oncology team.",.58,3.12,5.15,1.3,30,GREEN,True)
    text(s,"“Which mechanism deserves\nour next experiment?”",.58,4.68,5.3,1.05,25,PAPER)
    for yy,a,b in [(2.72,"See the research direction","A tree of questions and alternatives"),(3.92,"Audit the evidence","Source passages, code and results"),(5.12,"Make a deliberate decision","Uncertainty and failures stay visible")]:
        line(s,6.2,yy-.08,12.72,yy-.08)
        text(s,a,6.35,yy+.13,6.2,.52,24,PAPER,True)
        text(s,b,6.35,yy+.70,6.2,.40,17,MUTED)
    source_footer(s,"Design implements keyboard focus, reduced motion and dark/light themes; persona interviews remain to be done.")
    note(s,3,"Built around a scientist’s next decision.",
         "Our initial user is a computational biologist on a small oncology team. They need to decide where scarce experimental time should go. That drives the interface: a research tree for direction, source passages and code for scrutiny, and visible uncertainty. This is a working persona; interviews and usability measurements are still ahead.",25,
         "Persona is proposed, not based on completed interviews. UI design choices and accessibility features exist. Human approval controls are currently hidden in the frontend.",criteria="Understanding of the User (30); User Experience & Usability (40); Design Quality & Craft (30)",sources=["frontend/DESIGN.md","docs/frontend.md"])

    s=slide(p,4,"03 / Technical execution",title="A research loop with evidence at every step.")
    stages=[("01","Read","Papers become\nlinked claims."),("02","Connect","Agents explore\npossible bridges."),("03","Test","Python analyses\nuse public data."),("04","Challenge","A statistical screen\nreturns feedback."),("05","Review","A scientist records\na decision.")]
    for i,(n,t,b) in enumerate(stages):
        x=.58+i*2.49
        line(s,x,2.65,x+2.08,2.65,GREEN if i<4 else AMBER,1.7)
        text(s,n,x,2.88,2,.38,15,GREEN if i<4 else AMBER,font=MONO)
        text(s,t,x,3.63,2.36,.69,29,PAPER,True)
        text(s,b,x,4.54,2.26,.95,19,MUTED)
        if i<4:
            line(s,x+2.13,3.95,x+2.39,3.95,GREEN,1.3,True)
    line(s,9.08,5.82,3.45,5.82,GREEN,1,True)
    text(s,"Retry, reframe or pursue another branch",3.48,6.0,6.5,.4,16,GREEN)
    source_footer(s,"Knowledge graph = claims connected to entities, sources and context. Human review exists in the backend.")
    note(s,4,"A research loop with evidence at every step.",
         "Here is the system. A knowledge graph connects scientific claims to their sources and context. The agent explores those relationships, writes and runs Python analyses, and submits the result. A deterministic screen can send it back to retry or reframe. A human decision, with a written note, is required before promotion into the accepted graph.",30,
         "Integrated architecture exists. The current screen validates reported statistics; it does not independently reproduce the analysis. Backend human-review API exists; frontend review controls are hidden.",criteria="Technical Execution (50); AI Technical Sophistication (50); Reliability, Evaluation & Trustworthiness (25)",sources=["ARCHITECTURE.md","src/dnhacksbio/litmap/promote.py","src/dnhacksbio/explorer/verifyqueue.py"])

    s=slide(p,5,"04 / AI engineering",title="The engineering is in how the loop behaves.")
    # A conceptual, entirely editable branch-control diagram.
    for a,b in [((2.1,3.25),(4.05,2.91)),((2.1,3.25),(4.05,4.09)),((2.1,3.25),(4.05,5.27)),((5.35,2.91),(6.63,3.45)),((5.35,4.09),(6.63,3.45)),((5.35,5.27),(6.63,3.45))]:
        line(s,*a,*b,GREEN,1.4)
    for x,y,w,h,t,small in [(0.6,2.75,1.55,1.0,"Question","root"),(3.0,2.5,2.38,.8,"Hypothesis A","research"),(3.0,3.68,2.38,.8,"Hypothesis B","research"),(3.0,4.86,2.38,.8,"Challenge","counter-evidence"),(6.02,2.82,1.9,1.3,"Report →\ndecide","parent control")]:
        rect(s,x,y,w,h,PANEL,LINE,True)
        text(s,t,x+.12,y+.11,w-.22,h-.19,16,PAPER,True)
        text(s,small,x,y+h+.10,w,.26,9,MUTED,font=MONO)
    line(s,7.00,4.47,7.00,5.84,AMBER,1.2,True)
    text(s,"continue / fork\nfinish / prune",5.74,6.02,2.8,.55,12,AMBER,font=MONO,align=PP_ALIGN.CENTER)
    for yy,a,b in [(2.52,"Claims tied to sources","Exact quotes, identifiers and disagreements."),(3.85,"Explicit research actions","Method guidance, executable code and feedback."),(5.18,"Research that resumes","Saved reports, decisions, events and artifacts.")]:
        text(s,a,8.45,yy,4.24,.72,24,GREEN,True)
        text(s,b,8.45,yy+.60,4.24,.70,16,MUTED)
    source_footer(s,"Conceptual control diagram. Model judgment allocates research; calibrated statistical pruning is not active.")
    note(s,5,"The engineering is in how the loop behaves.",
         "AI is fundamental to interpreting papers, proposing connections and writing task-specific analyses. Our engineering makes that work inspectable: grounded claim identities, explicit actions, and durable branch control. Children report their findings; a parent chooses what continues. A restart preserves the decisions and artifacts. This is the behavior we can demonstrate and evaluate.",30,
         "Existing implementation: multi-pass extraction and identifier grounding, explicit actions, child reporting/parent decisions, immutable artifacts and ordered runtime events. Fork means split into research branches. Model roles: Opus reads papers, Sonnet checks direction and repairs extraction, MiniLM supports retrieval; no claim that this selection beats alternatives. No first-of-kind or measured superior allocation claim.",criteria="Novelty and Importance of AI (25); AI Technical Sophistication (50); Technical Execution (50)",sources=["src/dnhacksbio/litmap/extract.py","src/dnhacksbio/litmap/grounding.py","src/dnhacksbio/explorer/control.py","src/dnhacksbio/explorer/runtime.py","src/dnhacksbio/llm.py"])

    s=slide(p,6,"05 / Demo",title="One question. An inspectable trail.")
    screenshot=ROOT/'assets'/'workspace-fixture.png'
    if screenshot.exists():
        # Full, undistorted 1600×1000 screenshot; explicit fixture label above.
        s.shapes.add_picture(str(screenshot),Inches(.56),Inches(2.19),width=Inches(7.18),height=Inches(4.4875))
    else:
        rect(s,.56,2.35,8.16,4.25,PANEL,LINE)
        text(s,"Recorded investigation",1.0,3.5,7.3,.8,35,GREEN,True)
    tag(s,"INTERFACE DEMO / SYNTHETIC DATA",.59,1.78,5.08,AMBER)
    rect(s,9.05,2.30,3.68,.50,DARKGREEN)
    text(s,"PREPARED CORPUS",9.2,2.43,3.34,.24,12,PAPER,True,MONO)
    text(s,"100",9.1,3.07,3.5,1.0,63,GREEN,True)
    text(s,"curated full-text\npancreatic cancer papers",9.12,4.10,3.52,.95,22,PAPER)
    text(s,"Show source → hypothesis →\ncode → result → feedback",9.12,5.38,3.5,.92,18,MUTED)
    text(s,"Replace this interface fixture with the final scientific run.",.73,6.73,7.78,.25,11,AMBER)
    note(s,6,"One question. An inspectable trail.",
         "For the final demo, follow one pancreatic-cancer question through its source, hypothesis, code, result and feedback. We have a curated set of one hundred full-text papers with provenance. This current capture demonstrates the working interface using a synthetic test fixture; it is not a discovery result. Replace it with the recorded scientific investigation as soon as that run is ready.",55,
         "Screenshot: actual React app rendered by frontend/e2e tests with synthetic data, not a PDAC run. 100-paper corpus is real curation metadata; indexing does not imply completed claim extraction. Pancreatic cancer overall has 13.7% five-year relative survival in SEER 2016–2022; reserve that statistic for Q&A if useful and never imply prototype benefit.",
         "CRITICAL REPLACEMENT: choose a real run and record 45–60 seconds. Open exact source; select branch; show code and structured result; show rejection/candidate feedback. Do not promise visible human-review buttons. Keep local video or screenshots as fallback; never label a fixture as real.",
         "Technical Execution (prototype works and polish); UX & Usability; Real-World Impact",["demo/pdac/README.md","frontend/e2e/workspace.spec.ts","docs/frontend.md","seer"])

    s=slide(p,7,"06 / Trustworthiness",title="A plausible result must survive scrutiny.")
    card(s,.59,2.60,3.65,"01 / SOURCE","Did the paper\nsay that?","Quoted spans, grounded IDs,\nbiological context and\nexplicit disagreements.")
    card(s,4.77,2.60,3.65,"02 / SCREEN","Does the result\npass the checks?","Typed result, reported sample\nsize, direction, p-value\nand robustness.")
    card(s,8.95,2.60,3.78,"03 / SCIENTIST","Is it worth\npursuing?","Code and evidence remain\nreviewable. Human acceptance\nrequires a written note.",AMBER)
    source_footer(s,"Screened candidate ≠ independently reproduced result ≠ confirmed biological discovery.")
    note(s,7,"A plausible result must survive scrutiny.",
         "Trust has three layers: what the source actually said, what the implemented numerical checks accept, and what a scientist concludes. The screen can reject a malformed result or one that contradicts its predicted direction. It still reads reported statistics. Independent reruns and confirmation remain necessary; a candidate is not a confirmed discovery.",25,
         "Ordinary falsifier checks fields, finite effect, n_units ≥ 8, p in (0,1], expected direction, p ≤ .05 and reported robust flag. This is not proof of independence, correct analysis or family-wide error control.",criteria="Reliability, Evaluation & Trustworthiness (25); Technical Execution (50)",sources=["src/dnhacksbio/falsifier.py","src/dnhacksbio/methods.py","src/dnhacksbio/litmap/promote.py"])

    s=slide(p,8,"07 / Evaluation evidence",light=True)
    text(s,"We test the trust layer, too.",.55,1.05,12,1.0,38,INK,True)
    tag(s,"MEASURED / STANDALONE DIAGNOSTIC",.60,2.09,4.43,DARKGREEN,"DFE5DB")
    text(s,"10,000",.56,2.83,5.30,1.15,76,DARKGREEN,True)
    text(s,"synthetic no-difference runs",.62,4.06,5.18,.75,25,INK)
    text(s,"Separate training data. Frozen configuration.\nFresh pairs scored sequentially.",.62,5.11,5.28,.85,19,DARKGREEN)
    data=json.loads((REPO/'research/learned-evalue-validation/expanded-null.json').read_text())
    obs=data['scenarios']['null']['autoencoder']
    text(s,f"{obs['crossing_rate']*100:.2f}%",6.65,2.85,5.7,1.17,76,INK,True)
    text(s,"false alarms in this simulation",6.72,4.06,5.87,.70,23,INK)
    text(s,"112 / 10,000 ever crossed the threshold\n95% interval 0.93–1.35% · nominal level 5%",6.73,5.02,5.94,.82,17,DARKGREEN)
    source_footer(s,"Synthetic null audit of learned-encoder diagnostic. Not end-to-end discovery accuracy or a deployed stopping guarantee.",light=True)
    note(s,8,"We test the trust layer, too.",
         "We also built a separate learned statistical diagnostic and evaluated its failure behavior. In ten thousand synthetic runs with no group difference, the learned-encoder version crossed its evidence threshold in one point one two percent of runs. Training data and scoring units are separated. This is a concrete component test, not end-to-end discovery accuracy or a deployed guarantee.",30,
         "Read directly from expanded-null.json: 112/10,000 ever crossings, Wilson 95% CI .93–1.35%; final rejections 20/10,000=.20%. Each repetition 96 independent synthetic pairs, 16 burn-in pairs; frozen synthetic encoder from separate 256-row training set. Ordinary fixed-horizon permutation rejects 513/10,000=5.13%; this is compatible with nominal 5%, not evidence it is unreliable. Invalid label-memorizing control rejects 10,000/10,000. All methods in appendix. Statistical diagnostic is separate from live falsifier.",
         "Keep synthetic, standalone and ever-crossing labels. Earlier paragraph in validation README says 10,000 runs not yet run; its later expanded section and JSON supersede that historical pilot statement. Do not imply broad 1.12% product false-positive rate.",
         "AI Technical Sophistication (50); Reliability, Evaluation & Trustworthiness (25)",["research/learned-evalue-validation/expanded-null.json","research/learned-evalue-validation/README.md","src/dnhacksbio/learned_evalue.py"])

    s=slide(p,9,"08 / Feasibility & deployment",title="Start with one team and one research decision.")
    tag(s,"PROPOSED FIRST PILOT",.59,2.4,2.93)
    text(s,"Oncology research teams",.59,3.02,5.3,.7,32,GREEN,True)
    text(s,"User: computational biologist\nBuyer: research lead / lab director\nWorkflow: target or mechanism prioritization",.61,4.0,5.5,1.52,20,PAPER)
    text(s,"Commercial hypothesis\nPrivate research workspace + metered compute",.61,5.78,5.7,.66,16,MUTED)
    for yy,n,tt,bb in [(2.65,"01","Reproducible","Can another analyst rerun the result?"),(3.89,"02","Useful","Would the expert act on the candidate?"),(5.13,"03","Economical","What is the cost per reviewed candidate?")]:
        line(s,6.76,yy,12.73,yy)
        text(s,n,6.77,yy+.22,.58,.4,13,GREEN,font=MONO)
        text(s,tt,7.50,yy+.12,5.22,.50,25,PAPER,True)
        text(s,bb,7.5,yy+.72,5.2,.47,17,MUTED)
    source_footer(s,"Pilot, buyer and pricing model are hypotheses. No customer adoption, revenue or savings claimed.")
    note(s,9,"Start with one team and one research decision.",
         "Our first commercial hypothesis is a private research workspace for an oncology team, with compute metered by use. The buyer is the research lead who owns prioritization. A pilot should answer three questions: can another analyst reproduce the output, does the scientist find it useful, and what does each reviewed candidate cost? We have not measured those outcomes yet.",25,
         "Proposed buyer and commercial model, no customer validation. Existing localhost research service is not production hardened. Cost formula and deployment blockers appear in appendix.",criteria="Feasibility & Deployment Potential (25); Understanding of the User (30)",sources=["docs/frontend.md","docs/runtime.md","plans/backlog.md"])

    s=slide(p,10,"09 / Roadmap",title="A focused prototype. A credible path forward.")
    card(s,.59,2.57,3.69,"NOW / IMPLEMENTED","Inspectable\nresearch engine","Grounded claim graph\nRecursive research control\nCode, results and replay")
    card(s,4.77,2.57,3.69,"NEXT / PROPOSED","Evidence of\nuseful discovery","Finish the real PDAC demo\nIndependent reruns\nMatched-budget pilot",AMBER)
    card(s,8.96,2.57,3.78,"LATER / PLANNING","Deeper biological\ntools","Learned biological tests\nCellular ecosystems\n3D experiment workbenches",AMBER)
    source_footer(s,"PDAC = pancreatic ductal adenocarcinoma. Learned-tool plans and calibrated branch stopping remain separate future work.")
    note(s,10,"A focused prototype. A credible path forward.",
         "Today we have the inspectable research engine and separate statistical tooling. Next comes the evidence that matters: a real recorded pancreatic-cancer investigation, independent reruns and a matched-budget pilot. The plans extend into learned biological tests and three-dimensional experiment workbenches. We will add those capabilities against explicit validation milestones.",25,
         "Three learned tool plans are planning-only: protein/phosphosignaling, pharmacotype association and donor-level cellular ecosystems. Existing private expression/dependency/drug-response scoring is distinct from these future learned tools. New 3D plans cover inhibitor workbench, binder design, tumor-stroma and spindle simulation, with explicit reference/prediction/simulation/illustration provenance. They are not implemented tools or existing biological results. Real trajectory training and calibrated stopping are deferred.",criteria="Feasibility & Deployment Potential (25); Technical Execution (50)",sources=["plans/evalue-tool-council/README.md","plans/evalue-tool-council/native-evidence-contract.md","docs/branch-monitoring.md","plans/3d-experiment-tools/README.md"])

    s=slide(p,11,"10 / The ambition")
    graph(s,7.27,1.24,5.16,4.8,73)
    text(s,"More useful science\nfrom every dollar\nof compute.",.55,1.55,8.0,2.82,46,PAPER,True)
    text(s,"Our ambition: strengthen the infrastructure\nbehind American scientific discovery.",.6,4.78,7.95,.98,24,GREEN)
    text(s,"NEXT MILESTONE",.6,6.14,2.6,.3,11,AMBER,True,MONO)
    text(s,"One independently reproduced, expert-reviewed candidate.",3.06,6.08,9.60,.53,20,PAPER)
    note(s,11,"More useful science from every dollar of compute.",
         "Scientific advantage depends on turning knowledge into evidence we can act on. We want to build infrastructure that helps American research teams do more useful science with their compute. Our next milestone is concrete: one independently reproduced, expert-reviewed candidate, with the full path from its source to the result.",20,
         "Ambition, not measured dollar efficiency. DTX vision emphasizes U.S. leadership across critical technologies including health. This is our audience-fit inference, not DTX endorsement.",
         "End the short pitch here and take questions. If a verified result lands, replace next milestone with that result and its precise scope. Add agreed team names/contact only after supplied.",
         "Problem & Real-World Impact; Feasibility & Deployment Potential",["dtx","event"])

    # Appendix: intentionally modular, so presenters can answer the judges directly.
    s=slide(p,12,"Appendix / Rubric map",title="Every judging criterion has a place in the story.")
    groups=[("MAIN PRIZES",[("25","Problem & Real-World Impact","02 · 06 · 11"),("50","Technical Execution","04–08"),("25","Feasibility & Deployment","09–10 · 15")]),("BEST USE OF AI",[("25","Novelty & Importance of AI","04–05 · 16"),("50","Technical Sophistication","05 · 08 · 14"),("25","Reliability, Evaluation & Trust","07–08 · 13–14")]),("BEST IN DESIGN",[("30","Design Quality & Craft","03 · 06"),("40","User Experience & Usability","03 · 06"),("30","Understanding of the User","03 · 09")])]
    for i,(heading,rows) in enumerate(groups):
        x=.59+4.17*i
        text(s,heading,x,2.54,3.84,.35,14,GREEN,True,MONO)
        for j,(pts,t,refs) in enumerate(rows):
            y=3.14+j*1.03
            line(s,x,y,x+3.78,y)
            text(s,pts,x,y+.15,.61,.5,24,AMBER,True)
            text(s,t,x+.80,y+.12,2.93,.52,16,PAPER,True)
            text(s,"SLIDES "+refs,x+.80,y+.68,2.93,.25,10,MUTED,font=MONO)
    source_footer(s,"Weights transcribed from the user-provided judging rubric. This is a coverage map, not a claimed score.")
    note(s,12,"Judging criterion map.","The core story is deliberately weighted toward engineering, which accounts for half the main score and half the AI award. The supporting slides make the evidence, deployment assumptions and user decisions easy to inspect.",20,"All nine rubric items and weights match the user-provided rubric.",criteria="All criteria",sources=["event"])

    s=slide(p,13,"Appendix / Current state",title="What is built, prepared and still to be proven.")
    rows=[("BUILT","Claims, quotes and context","Grounding failures are deferred; source count is not proof."),("BUILT","Research actions and branch control","Model judgment; no calibrated scientific stopping."),("BUILT","Statistical screen + backend review","Reported statistics; human-review controls hidden in UI."),("PREPARED","100-paper pancreatic cancer corpus","Frozen curation is not a prospective discovery benchmark."),("MEASURED","Standalone learned diagnostic","Synthetic null audit and one observational expression cohort."),("TO PROVE","Useful discovery per dollar","No independent discovery, savings or customer result yet.")]
    for i,(status,claim,limit) in enumerate(rows):
        y=2.50+i*.60
        line(s,.6,y,12.73,y)
        text(s,status,.61,y+.16,1.64,.27,10,AMBER if status=="TO PROVE" else GREEN,True,MONO)
        text(s,claim,2.30,y+.13,4.9,.40,18,PAPER,True)
        text(s,limit,7.31,y+.15,5.38,.40,14,MUTED)
    source_footer(s,"Source snapshot: main 1e83cfb, 6 September 2026. Recheck this ledger when new work lands.")
    note(s,13,"Current-state ledger.","These status labels separate implementation from data preparation and scientific validation. A frozen corpus is useful infrastructure, but it does not exclude model memory or prove a blind discovery. A working statistical module also does not establish that the full research loop finds better hypotheses.",25,"Claim ledger reconciles current code with plans. Older forecasting materials and historical validation-pilot statements were not reused as current proof.",criteria="Technical Execution; Reliability & Trustworthiness",sources=["ARCHITECTURE.md","demo/pdac/README.md","research/learned-evalue-validation/README.md"])

    s=slide(p,14,"Appendix / Evaluation details",title="Statistical evidence has a declared scope.")
    text(s,"SYNTHETIC NULL · 10,000 RUNS / METHOD",.6,2.44,7.6,.35,12,GREEN,True,MONO)
    text(s,"Method",.62,3.01,3.95,.38,15,MUTED)
    text(s,"Ever crossed",4.07,3.01,1.83,.38,15,MUTED)
    text(s,"Final reject",6.0,3.01,1.85,.38,15,MUTED)
    labels=[('identity','Identity'),('pca','PCA'),('autoencoder','Learned encoder'),('scalar','Single feature'),('fixed_projection','Fixed projection'),('permutation_p','Permutation p*'),('permutation_calibrated_e','Calibrated permutation e*'),('INVALID_label_memorization','Invalid memorization control')]
    for i,(key,label) in enumerate(labels):
        y=3.49+i*.32
        rr=data['scenarios']['null'][key]
        text(s,label,.62,y,3.72,.29,13,GREEN if key=='autoencoder' else PAPER)
        text(s,f"{100*rr['crossing_rate']:.2f}%",4.10,y,1.77,.29,13,PAPER,font=MONO)
        text(s,f"{100*rr['final_rate']:.2f}%",6.00,y,1.77,.29,13,PAPER,font=MONO)
    line(s,8.3,2.45,8.3,6.1)
    text(s,"REAL-COHORT DIAGNOSTIC",8.69,2.48,4.0,.40,11,AMBER,True,MONO)
    text(s,"19,000 → 512 → 128",8.67,3.16,4.05,.5,23,GREEN,True)
    text(s,"Masked expression encoder\ntrained on separate donors",8.68,3.84,4.04,.84,20,PAPER)
    text(s,"30 held-out pairs · observational cohort\nLearned final e-value 3,652.81\nPCA 85.76 · single gene 5,964.41",8.68,5.0,4.02,.94,15,MUTED)
    source_footer(s,"* Fixed-horizon comparators. No universal winner; lower null crossing does not establish greater power. Real cohort is COVID, not PDAC.")
    note(s,14,"Statistical evidence has a declared scope.","The full comparison matters. A simpler single-feature method can outperform learned features on a particular task. Our real-data example uses a separate observational COVID expression cohort and the same thirty evaluation pairs for each method. It is a diagnostic engineering result, not cancer validation, causality or universal model superiority.",35,
         "Synthetic table read directly from expanded-null.json. Threshold 20; alpha .05. Permutation comparators have one fixed-horizon decision. Real final e-values: learned3652.81, PCA85.76, IFIT3 scalar5964.41, calibrated permutation99.00. 374 unique day-zero donors split 40/20/40; the same 30 selected evaluation pairs with 91 positive evaluation donors unused. Different representation widths; not an equal-width architecture ablation. Clinical labels not randomized. E-values must not be multiplied across dependent/reused data.",criteria="AI Technical Sophistication (50); Reliability, Evaluation & Trustworthiness (25)",sources=["research/learned-evalue-validation/expanded-null.json","research/learned-evalue-validation/real-expression/README.md"])

    s=slide(p,15,"Appendix / Deployment & economics",title="The pilot has explicit deployment gates.")
    items=[("COST","Meter model calls, compute, storage and scientist review.\nCost per reviewed candidate = total pilot cost / reviewed candidates."),("SECURITY","Authenticate research access; isolate experiment workers; scope credentials.\nCurrent localhost API and execution migration are not production-ready."),("INTEGRATION","Keep corpus, source links, code and artifacts portable.\nSeparate persistent workers and data from application releases."),("ADOPTION & USE","Begin with nonclinical research decisions and public/licensed data.\nPrivate datasets and clinical use require separate data, legal and regulatory review.")]
    for i,(a,b) in enumerate(items):
        y=2.47+i*.88
        line(s,.61,y,12.72,y)
        text(s,a,.61,y+.22,2.47,.36,12,GREEN,True,MONO)
        text(s,b,3.07,y+.15,9.59,.65,18,PAPER)
    source_footer(s,"Proposed gates. Price, gross margin and production compliance have not been measured or established.")
    note(s,15,"Deployment and economics.","We would start with a narrowly scoped research pilot. We need authenticated access, isolated execution and persistent workers that survive application deployment. The economics must include scientist review as well as model and compute spend. The intended first use is research prioritization; patient-facing decisions would require a separate validation and regulatory path.",30,
         "Research server is localhost-only in docs. Docker currently implemented; removal is a product decision but replacement environment/permissions unspecified. Security controls in this slide are requirements, not completed implementation or certification. No legal conclusion about device status.",criteria="Feasibility & Deployment Potential (25)",sources=["ARCHITECTURE.md","docs/frontend.md","docs/runtime.md"])

    s=slide(p,16,"Appendix / Originality & prior art",title="The bar is a useful, inspectable research system.")
    rows=[("Google DeepMind\nCo-scientist","Multi-agent hypothesis generation,\ntools and scientist-led validation.","Strong evidence that multi-agent\nresearch is already a serious field."),("Elicit\nResearch Agent","Research workflows, bioinformatics\nanalysis and source-linked outputs.","Paper summarization alone\nis not a credible distinction."),("Our focus","Grounded claim relationships →\nrecursive executable investigations.","Show exact provenance, decisions,\nresults and failure feedback.")]
    for i,(a,b,c) in enumerate(rows):
        y=2.53+i*1.13
        line(s,.6,y,12.73,y,GREEN if i==2 else LINE)
        text(s,a,.6,y+.18,3.27,.87,22,GREEN if i==2 else PAPER,True)
        text(s,b,4.11,y+.20,4.32,.86,19,PAPER)
        text(s,c,8.9,y+.21,3.84,.90,17,MUTED)
    source_footer(s,"Official product descriptions, accessed 6 September 2026. Differentiation is a design focus; comparative superiority is unproven.")
    note(s,16,"Originality and prior art.","We should be compared with serious research agents, not a strawman chatbot. Co-scientist and Elicit already perform substantive research workflows. Our claim is the specific composition we built: grounded relationships, recursive executed investigations and an inspectable decision trail. We still need matched-budget comparisons to establish an advantage.",25,
         "Primary official descriptions reviewed. Do not claim first autonomous scientist, first multi-agent research system or unique experimental validation. Current Elicit research agent post is August 2026; DeepMind source May 2026.",criteria="Technical Execution (originality); Novelty and Importance of AI (25)",sources=["deepmind","elicit"])

    s=slide(p,17,"Appendix / Next evaluation",title="The next result should be hard to fool.")
    card(s,.59,2.51,3.71,"01 / FIX THE TASK","Freeze the\nstarting point","Version the corpus and data.\nChoose tasks before runs.\nKeep outcomes out of inputs.")
    card(s,4.77,2.51,3.71,"02 / MATCH THE BUDGET","Compare real\nalternatives","Single-agent baseline.\nFlat parallel research.\nOur recursive controller.")
    card(s,8.96,2.51,3.78,"03 / AUDIT THE OUTPUT","Count useful,\nreproduced work","Expert usefulness ratings.\nIndependent rerun success.\nTime and total cost.",AMBER)
    source_footer(s,"Proposed protocol; not run. Include failures and rejected branches. Model memory remains a concern in retrospective tasks.")
    note(s,17,"The next result should be hard to fool.","The next evaluation should compare the research loop with a strong single agent and flat parallel research under the same total budget. Freeze tasks and starting evidence, account for failed branches, and have independent analysts rerun results. Measure expert usefulness and cost. Retrospective dates alone do not remove model-memory contamination.",25,
         "Evaluation proposal only; no new model runs or training authorized by creation of this deck. Predeclare dataset/task splits, evaluator rubric, budgets, stopping rules, output definitions and exclusions; report exact denominators and uncertainty when justified.",criteria="Reliability, Evaluation & Trustworthiness (25); Technical Execution (50); Feasibility (25)",sources=["plans/backlog.md","plans/PLAN-demo-slides.md"])
    p.save(OUT/'DNHacks_2026_DN_Research.pptx')
    return p


def templates():
    p=new_prs()
    examples=[("Evidence slide","[One finding in a complete sentence]","[Claim and scope]","[Editable visual: chart, graph or source excerpt]"),
              ("Result slide","[What changed after the experiment?]","[Method · units · comparator]","[Measured result and uncertainty]"),
              ("Demo slide","[One question. One decision.]","[Actual run · date · dataset]","[Replace this panel with the real demo capture]"),
              ("Roadmap slide","[The next milestone earns the next claim]","[Implemented]","[Next / proposed] / [Later / planning]")]
    for i,(kind,title,small,body) in enumerate(examples,1):
        s=slide(p,i,"Layout kit / "+kind,title,light=(i==2))
        if i==1:
            tag(s,small,.59,2.47,5.2)
            rect(s,.6,3.13,8.03,3.11,PANEL,LINE)
            text(s,body,1.01,4.13,7.19,1.16,29,GREEN,True)
            text(s,"[Why it matters]",9.16,3.16,3.5,.64,27,PAPER,True)
            text(s,"[One short explanation.\nPut detail in speaker notes.]",9.17,4.12,3.52,1.56,22,MUTED)
        elif i==2:
            tag(s,small,.59,2.47,5.2,DARKGREEN,"DFE5DB")
            line(s,6.46,3.18,6.46,5.96,"B5C0B5")
            for x,label in [(.60,"[Baseline]"),(7.02,"[Our method]")]:
                text(s,label,x,3.30,5.42,.52,24,DARKGREEN,True)
                text(s,"[Value]",x,4.16,5.44,1.10,62,INK,True)
                text(s,"[Units · sample size · uncertainty]",x,5.53,5.44,.63,19,DARKGREEN)
        elif i==3:
            tag(s,small,.59,2.20,5.2)
            rect(s,.6,2.93,12.12,3.29,PANEL,LINE)
            text(s,body,1.06,4.02,11.23,1.08,32,GREEN,True,align=PP_ALIGN.CENTER)
        else:
            for j,(a,b) in enumerate([("NOW / IMPLEMENTED","[What works today]"),("NEXT / PROPOSED","[The proof milestone]"),("LATER / PLANNING","[The expansion]")]):
                card(s,.59+j*4.17,2.70,3.78,a,b,"[One concrete deliverable]\n[Its evidence requirement]\n[Owner or dependency]",GREEN if j==0 else AMBER)
        source_footer(s,"[Source, measured/planned/illustrative status, scope and date]",light=(i==2))
        s.notes_slide.notes_text_frame.text=("TENTATIVE SCRIPT\n[Write 40–65 words: finding, evidence, implication, transition.]\n\n"
          "STATUS\n[Implemented / measured / planned / illustration]\n\nSOURCE\n[Exact URL or repository path, version and date]\n\n"
          "EDITING\nDuplicate this slide; replace bracketed text and the visual panel. Preserve 0.55-inch margins, 36pt headline, 19–24pt body, IBM Plex fonts and explicit status. Avoid exceeding one argument per slide.")
    p.save(OUT/'DNHacks_Layout_Kit.pptx')


if __name__=='__main__':
    build()
    templates()
    invalid=[b for b in BOUNDS if b[1]<0 or b[2]<0 or b[1]+b[3]>W+.01 or b[2]+b[4]>H+.01]
    if invalid:
        raise ValueError(f'Text boxes outside slide: {invalid}')
    (ROOT/'speaker-notes.md').write_text('# Tentative speaking script\n\nCore slides 1–11: approximately five minutes, including a 55-second demo slot. Appendices 12–17 are for Q&A.\n\n'+ '\n\n'.join(f"## {a['slide']:02} — {a['title']}\n\n{a['notes']}" for a in TALK)+'\n')
    (OUT/'deck-manifest.json').write_text(json.dumps({'source_snapshot':SNAPSHOT,'built_on':'2026-09-06','main_slides':17,'core_slides':11,'core_seconds':sum(x['seconds'] for x in TALK[:11]),'layout_kit_slides':4,'fonts':[FONT,MONO],'sources':SOURCES},indent=2)+'\n')
    print(f'Built {OUT}/DNHacks_2026_DN_Research.pptx (17 slides) and layout kit (4 slides).')
