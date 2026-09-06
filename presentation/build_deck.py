#!/usr/bin/env python3
"""Build the editable judge pitch, optional discovery reveal, and technical appendix."""
from __future__ import annotations
import json
from pathlib import Path
from lxml import etree
from pptx.util import Inches
from PIL import Image
import deck_style as ds
from deck_style import *

ASSETS=ROOT/'assets/v2'
PLOTS=ASSETS/'plots'
SOURCES.update({
 'nsceb':('NSCEB final report, April 2025, §1.3','https://www.biotech.senate.gov/final-report/chapters/chapter-1/section-3/'),
 'foresight':('NSCEB final report, April 2025, §3.3','https://www.biotech.senate.gov/final-report/chapters/chapter-3/section-3/'),
 'darpa':('DARPA · Pandemic Prevention Platform','https://www.darpa.mil/research/programs/pandemic-prevention-platform'),
})
HIDDEN=[]


def page(p,n,section,title=None,light=False,sub=None,hidden=False):
    s=slide(p,n,section,title,light,sub)
    if hidden:
        s._element.set('show','0'); HIDDEN.append(n)
    return s


def pic(s,path,x,y,w,h):
    path=Path(path)
    with Image.open(path) as im: ratio=im.width/im.height
    ww=min(w,h*ratio); hh=ww/ratio
    return s.shapes.add_picture(str(path), Inches(x+(w-ww)/2), Inches(y+(h-hh)/2),width=Inches(ww),height=Inches(hh))


def label(s,t,x=.6,y=6.51,w=12.1,c=MUTED):
    text(s,t,x,y,w,.32,10.5,c,font=MONO)


def heading(s,t,sub=None,light=False):
    text(s,t,.6,1.08,12.05,1.31,39,INK if light else PAPER,True)
    if sub: text(s,sub,.62,2.45,11.8,.7,21,DARKGREEN if light else MUTED)


def stat(s,value,title,x,y,w=3.6,c=GREEN,body=None):
    text(s,value,x,y,w,1.12,66,c,True)
    text(s,title,x,y+1.22,w,.66,22,PAPER,True)
    if body: text(s,body,x,y+2.05,w,1.14,17,MUTED)


def rows(s,items,x=.6,y=2.73,w=12.1,step=1.05,light=False):
    for i,(a,b) in enumerate(items):
        yy=y+i*step
        line(s,x,yy,x+w,yy,'C6CBBF' if light else LINE)
        text(s,a,x,yy+.15,w*.31,.71,22,DARKGREEN if light else GREEN,True)
        text(s,b,x+w*.34,yy+.16,w*.66,.78,19,INK if light else PAPER)


def fade(s,shape):
    """Native PowerPoint entrance effect; exported PDFs show the final state."""
    xml=f'''<p:timing xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:tnLst><p:par><p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot"><p:childTnLst><p:seq concurrent="1" nextAc="seek"><p:cTn id="2" dur="indefinite" nodeType="mainSeq"><p:childTnLst><p:par><p:cTn id="3" fill="hold"><p:stCondLst><p:cond delay="indefinite"/></p:stCondLst><p:childTnLst><p:par><p:cTn id="4" presetID="10" presetClass="entr" presetSubtype="0" fill="hold" nodeType="clickEffect"><p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst><p:animEffect transition="in" filter="fade"><p:cBhvr><p:cTn id="5" dur="800"/><p:tgtEl><p:spTgt spid="{shape.shape_id}"/></p:tgtEl></p:cBhvr></p:animEffect></p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn><p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst><p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst></p:seq></p:childTnLst></p:cTn></p:par></p:tnLst></p:timing>'''
    s._element.append(etree.fromstring(xml.encode()))


def custom_shows(p):
    ns='http://schemas.openxmlformats.org/presentationml/2006/main'
    relns='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    shows=etree.Element('{'+ns+'}custShowLst')
    ids=list(p.slides._sldIdLst)
    for ident,(name,numbers) in enumerate([
      ('Judge pitch · about five minutes',[1,2,3,4,5,6,7,8,9,14,15,16]),
      ('Discovery reveal · enable only after verification',list(range(1,17))),
      ('Three-minute cut',[1,2,4,6,7,9,16])]):
        show=etree.SubElement(shows,'{'+ns+'}custShow',name=name,id=str(ident))
        lst=etree.SubElement(show,'{'+ns+'}sldLst')
        for n in numbers:
            etree.SubElement(lst,'{'+ns+'}sld',{'{'+relns+'}id':ids[n-1].get('{'+relns+'}id')})
    root=p._element
    # Must precede photoAlbum, custDataLst, kinsoku/defaultTextStyle/extLst.
    successor=next((e for e in root if etree.QName(e).localname in ('photoAlbum','custDataLst','kinsoku','defaultTextStyle','extLst')),None)
    if successor is None: root.append(shows)
    else: successor.addprevious(shows)


def build():
    p=new_prs()
    s=page(p,1,'DNHacks 2026 / working name')
    cover=ASSETS/'cover.jpg'
    if cover.exists():
        pic(s,cover,0,0,W,H)
        text(s,'DN / RESEARCH',.62,.37,4,.4,14,PAPER,True,MONO)
        text(s,'DNHACKS 2026',9.6,.39,3.05,.3,11,MUTED,font=MONO,align=PP_ALIGN.RIGHT)
    else: graph(s,7,1,5.5,5.6)
    text(s,'Anticipate\nbiology.',.6,1.45,7.3,2.0,66,PAPER,True)
    text(s,'Before it changes the\nbalance of power.',.65,3.91,6.75,1.4,34,GREEN)
    text(s,'An evidence-driven research engine\nfor scientists working on what comes next.',.68,5.72,6.4,.78,20,PAPER)
    label(s,'PROTOTYPE  /  OPEN CATEGORY PROPOSED',y=6.93,c=MUTED)
    note(s,1,'Anticipate biology.',
      'Biology is an underappreciated source of future strategic power. Our thesis is that scientific lead time matters: understanding an emerging capability earlier gives scientists and institutions more time to prepare. DN Research is our working name for an engine that connects published evidence, proposes experiments and keeps the results inspectable.',25,
      'Strategic thesis and intended application. Current prototype is computational biological research; it does not demonstrate bioweapon prediction or operational threat prevention. Cover art is AI-generated conceptual imagery, not measured biology.',
      'Working name and entered category need final team confirmation. Use the Judge pitch custom show. This slide and the close are conceptual art; all scientific figures are sourced separately.',
      'Problem & Real-World Impact (25); Feasibility & Deployment (25)', ['dtx','foresight','ARCHITECTURE.md','presentation/assets/v2/README.md'])

    s=page(p,2,'Why anticipation matters',light=True)
    text(s,'A warning about the way we innovate.',.61,1.04,12,1,29,DARKGREEN,True)
    text(s,'“The United States tends to play\ncatch-up after critical technologies\nhave already become mainstream.”',.6,2.35,12.1,2.36,37,INK,True)
    line(s,.65,5.26,2.17,5.26,DARKGREEN,2)
    text(s,'National Security Commission on Emerging Biotechnology',.64,5.65,11.8,.54,23,INK)
    text(s,'2025 FINAL REPORT  /  SECTION 1.3',.66,6.28,11.8,.3,12,DARKGREEN,font=MONO)
    note(s,2,'A warning about the way we innovate.',
      'The National Security Commission on Emerging Biotechnology put it directly: the United States tends to play catch-up after critical technologies have already become mainstream. That is a costly posture for biology. We need scientists and research systems that help us investigate what could become possible before it becomes obvious.',20,
      'Exact supplied quotation verified against the official NSCEB final report §1.3. The paragraph following the quote in this script is our strategic interpretation.',criteria='Problem & Real-World Impact (25)',sources=['nsceb'])

    s=page(p,3,'Strategic thesis')
    heading(s,'A biological lead can become\na unilateral advantage.')
    text(s,'Novel biological threats leave less room for catch-up.',.65,2.56,12,.45,22,MUTED)
    text(s,'Capability develops',.65,3.12,4.2,.6,25,PAPER,True)
    text(s,'Capability becomes visible',7.17,3.12,5.52,.6,25,PAPER,True)
    line(s,.8,4.22,12.55,4.22,LINE,3)
    line(s,.8,4.22,7.46,4.22,GREEN,7)
    line(s,7.46,4.22,12.55,4.22,AMBER,7)
    dot(s,.8,4.22,.105,GREEN); dot(s,7.46,4.22,.105,PAPER); dot(s,12.55,4.22,.105,AMBER)
    text(s,'ANTICIPATE',.75,4.64,5,.4,15,GREEN,True,MONO)
    text(s,'REACT',8.0,4.64,4,.4,15,AMBER,True,MONO)
    text(s,'Connect evidence. Test implications.\nPrepare defensive options earlier.',.76,5.24,6.2,.92,23,PAPER)
    text(s,'Response starts with\nless lead time.',8.0,5.24,4.5,.92,23,PAPER)
    label(s,'TEAM THESIS · Conceptual timeline, not measured intervals. Reactive measures remain necessary.')
    note(s,3,'A biological lead can become a unilateral advantage.',
      'Biology can create asymmetric power: one actor may acquire a consequential capability before others understand it or can prepare. Waiting until a novel bioweapon or other biological risk is demonstrated leaves less time to respond. Reactive measures remain essential, but they are insufficient as our only posture. Our ambition is to reduce that window of unilateral advantage through earlier scientific investigation.',30,
      'Team thesis, informed by NSCEB strategic-surprise and foresight discussion. DARPA P3 describes the delay in developing countermeasures after threat identification. The graphic is conceptual; no lead-time savings or threat forecasting accuracy has been measured.',criteria='Problem & Real-World Impact (25); DTX audience relevance',sources=['foresight','darpa','dtx'])

    s=page(p,4,'The product')
    heading(s,'Point compute at the questions\nthat matter.')
    graph(s,7.25,2.66,5.05,3.53)
    text(s,'Published evidence',.65,3.07,6.2,.62,28,GREEN,True)
    text(s,'→ testable connections',.65,3.94,6.45,.62,28,PAPER,True)
    text(s,'→ experiments worth reviewing',.65,4.81,7.03,.72,28,PAPER,True)
    label(s,'INITIAL PROVING GROUND · Computational biology, including pancreatic-cancer research.')
    note(s,4,'Point compute at the questions that matter.',
      'There are useful connections waiting between existing findings. The hard part is deciding which connections deserve compute, what experiment can test them, and whether its output can be trusted. Our literature graph links claims from papers. Agents explore those links, run analyses with specialized tools and bring the evidence back for review. Pancreatic-cancer research is our initial proving ground.',25,
      'The graph motif is conceptual. The PDAC curation contains 100 papers; a curated corpus is not a completed extraction or discovery. An absent graph edge does not establish novelty.',criteria='Problem & Real-World Impact (25); Novelty and Importance of AI (25)',sources=['ARCHITECTURE.md','demo/pdac/README.md'])

    s=page(p,5,'Understanding the user')
    heading(s,'Make the next experiment\na deliberate decision.')
    pic(s,ROOT/'assets/workspace-fixture.png',4.62,2.64,8.1,3.73)
    text(s,'Computational\nbiologist',.66,2.80,3.77,.95,25,GREEN,True)
    text(s,'Small research team',.67,3.83,3.77,.47,20,MUTED)
    text(s,'Choose a question.\nInspect its evidence.\nExplain the decision.',.67,4.61,3.77,1.16,21,PAPER)
    label(s,'USER HYPOTHESIS · Actual interface with synthetic test data; interviews and usability study remain ahead.')
    note(s,5,'Make the next experiment a deliberate decision.',
      'Our initial user is a computational biologist with limited experimental capacity. They need direction and an audit trail. That is why the workspace exposes the research tree, the evidence behind a branch and the history of the investigation. This capture is the actual interface populated with browser-test data; the persona is a design hypothesis we still need to validate with users.',25,
      'Actual React UI; synthetic fixture. Keyboard focus, reduced motion and light/dark themes implemented. Human review is a backend capability; frontend approval controls remain hidden at the audited snapshot.',criteria='Understanding of the User (30); User Experience & Usability (40); Design Quality & Craft (30)',sources=['frontend/DESIGN.md','docs/frontend.md','presentation/assets/README.md'])

    s=page(p,6,'AI engineering / the complete loop')
    heading(s,'The graph directs exploration.\nExperiments constrain it.')
    stages=[('01','Read','Source passages\nbecome linked claims.'),('02','Connect','Researchers branch\non testable questions.'),('03','Execute','Code and domain tools\nproduce artifacts.'),('04','Challenge','Screens, comparators\nand evidence checks.'),('05','Review','A scientist decides\nwhat deserves follow-up.')]
    for j,(num,title,body) in enumerate(stages):
        xx=.66+j*2.46
        dot(s,xx+.10,3.45,.078,GREEN if j<4 else AMBER)
        if j<4: line(s,xx+.25,3.45,xx+2.36,3.45,LINE,2,arrow=True)
        text(s,num,xx,2.9,2.15,.3,13,GREEN,font=MONO)
        text(s,title,xx,3.84,2.2,.58,27,PAPER,True)
        text(s,body,xx,4.67,2.19,1.17,19,MUTED)
    label(s,'AI IS FUNDAMENTAL · Question formation, branching, executable analyses and artifact interpretation.')
    note(s,6,'The graph directs exploration. Experiments constrain it.',
      'This is the full loop. Papers become source-linked claims. Research agents form questions and spawn alternative branches. They write analyses and call domain tools, then the system preserves outputs and screens reported results. A scientist can review the surviving evidence. The engineering goes beyond a chat interface: it includes recursive orchestration, budgets, durable execution, tool-specific data work and statistical components. Screen survival is not biological truth.',35,
      'Implemented architecture. Ordinary falsifier checks reported fields and flags; it does not independently rerun arbitrary code. Private evidence adapters and branch monitoring have different contracts and maturity. No qualifying end-to-end later-paper recovery is asserted.',criteria='Technical Execution (50); Novelty and Importance of AI (25); Technical Sophistication (50)',sources=['ARCHITECTURE.md','docs/runtime.md','docs/native-evidence.md','docs/branch-monitoring.md'])

    s=page(p,7,'Computational toolkit / lead with 3D')
    text(s,'Inspect the image. Check the coordinates.',.6,1.05,12.1,1.0,38,PAPER,True)
    sh=s.shapes.add_picture(str(REPO/'docs/inhibitor-review/surface-final.png'),Inches(.61),Inches(2.37),width=Inches(8.21),height=Inches(3.92))
    sh.crop_left=.035; sh.crop_right=.215; sh.crop_top=.365; sh.crop_bottom=.07
    text(s,'A real molecular scene',9.14,2.43,3.57,1.0,27,GREEN,True)
    for yy,t in [(3.76,'Image critique'),(4.35,'Request a cutaway'),(4.94,'2.714 Å coordinate check')]:
        text(s,t,9.16,yy,3.52,.62,19,PAPER)
    label(s,'ACTUAL 3D WORKBENCH · Image-to-coordinate review; the separate docking recovery benchmark did not pass.')
    note(s,7,'Inspect the image. Check the coordinates.',
      'Start with something tangible. This is our actual molecular workbench. The agent inspected a saved image, requested a cutaway to reduce occlusion, and identified a pair of atoms for a coordinate check. The measured distance was about 2.714 angstroms, a measure of proximity rather than a bonding or efficacy claim. A separate three-seed docking benchmark failed its recovery criterion. The image helps direct inspection; the numerical check constrains the interpretation.',35,
      'Actual surface-final.png capture from the scoped inhibitor workflow. The native PowerPoint crop focuses on the scene and omits surrounding controls; source image is unchanged. The recorded canonical O22 N2 / GLN670 OE1 distance is 2.7136221099760567 Å. Three-seed Vina 3VQU/O22 recovery: no pose met the frozen 2 Å RMSD criterion; best-any RMSD was about 2.675 Å. Distance and RMSD are different measurements. No affinity, hydrogen-bond assignment or therapeutic effect is claimed.',
      'Preserve the actual capture and separate the coordinate review from the benchmark. Full source receipts are in the inhibitor review. The binder visual loop and broader 3D tool status are in the appendix.',
      'Technical Execution (50); Technical Sophistication (50); Design Quality & Craft (30)', ['docs/inhibitor-review/README.md','docs/inhibitor-review/review.json','docs/inhibitor-review/benchmark.json'])

    s=page(p,8,'Model execution / measured evidence',light=True)
    heading(s,'Training is real.\nAdvantage still has to be earned.',light=True)
    data=[('PROTEIN','219 / 110 / 105','train / validation / development','PCA beats the denoiser\non hidden-value reconstruction.'),('DRUG RESPONSE','245 / 40 / 71','train / validation / test groups','PCA selected on validation.\nNo pancreatic-subset advantage.'),('CELL ECOSYSTEMS','45 / 11 / 16','train / validation / external donors','Exact PCA remains best\nfor external reconstruction.')]
    for j,(title,n,split,result) in enumerate(data):
        x=.64+j*4.17
        line(s,x,2.83,x+3.73,2.83,DARKGREEN,1.7)
        text(s,title,x,3.07,3.8,.35,13,DARKGREEN,True,MONO)
        text(s,n,x,3.64,3.85,.72,30,INK,True)
        text(s,split,x,4.48,3.8,.65,16,DARKGREEN)
        text(s,result,x,5.36,3.83,.98,22,INK)
    label(s,'MEASURED DEVELOPMENT · Different tasks and units. These counts are not pooled or a discovery score.',c=DARKGREEN)
    note(s,8,'Training is real. Advantage still has to be earned.',
      'We trained representations on real protein, drug-response and single-cell data with explicit splits and comparators. The important result is that the simplest method often won. PCA, a simple linear compression baseline, beat our protein denoiser. The expanded ecosystem study now has 72 donor records and real validation curves; exact PCA still leads external reconstruction. The drug-response model did not beat the mean baseline on the pancreatic subset. These findings tell us what to retain and what not to claim; the appendix contains the measured training histories and held-out comparisons.',35,
      'The protein study uses CPTAC data: 219 TRAIN cases, 110 LUAD validation cases and 105 PDAC development cases. The pharmacotype study contains 356 patient-origin groups, split 245 / 40 / 71. The expanded ecosystem study uses 45 training, 11 validation and 16 external donor records across five original studies. Its epithelial definition and cell-weighted metrics differ from the initial Peng/Lin pilot. These are exposed development or test characterizations, not clinical confirmation. No new training was performed for this deck.',criteria='Technical Execution (50); AI Technical Sophistication (50); Reliability, Evaluation & Trustworthiness (25)',sources=['docs/protein-training.md','docs/pharmacotype-training.md','docs/ecosystem-expansion.md'])

    s=page(p,9,'Reliability / evidence contracts')
    heading(s,'Evidence needs a budget\nfor being wrong.')
    text(s,'INTERNAL E-VALUE TOOLS',.66,2.51,11.8,.33,13,GREEN,True,MONO)
    stat(s,'1.12%','ever crossed the threshold',.65,2.97,5.5,body='112 / 10,000 synthetic null runs\n95% Wilson interval: 0.93–1.35%')
    rows(s,[('Prevent leakage','Train on past data; score fresh observations.'),('Keep receipts','Freeze inputs, consume donors once, preserve replay.'),('Respect limits','Synthetic calibration is not discovery accuracy.')],x=6.57,y=2.89,w=6.14,step=1.09)
    label(s,'SEPARATE DIAGNOSTIC · Learned encoder; 96 synthetic pairs/run. No investigation-wide guarantee.')
    note(s,9,'Evidence needs a budget for being wrong.',
      'Our internal e-value tools separate plausible output from statistical evidence. An e-value is an evidence score designed to stay small on average when the stated no-effect assumption is true. In one standalone synthetic audit, the learned method crossed its threshold at least once in 112 of 10,000 null runs—simulated data with no group difference—or 1.12 percent. That is not the false-positive rate of the whole product. The engineering also binds evidence to frozen inputs, prevents duplicate donor consumption within the shared private ledger and preserves replay. Low false-alarm rates alone do not establish useful power or biological validity.',30,
      'In expanded-null.json, the learned encoder crossed the threshold at least once in 112 runs. Only 20 runs, or 0.20%, were above the threshold at the end; this is a different metric. The synthetic encoder differs from the real-expression model. The native ledger requires an actual identity boundary: separate processes under the same Unix owner do not provide isolation. Current release gates for adequately powered real-data confirmation remain unmet.',criteria='Reliability, Evaluation & Trustworthiness (25); Technical Execution (50)',sources=['research/learned-evalue-validation/expanded-null.json','docs/native-evidence.md'])

    s=page(p,10,'Optional discovery sequence / populate from one verified run',hidden=True)
    heading(s,'Follow one question all the way\nto a reviewable result.')
    trace=[('SOURCE','Verbatim claim + passage'),('BRIDGE','Agent’s concise decision'),('EXPERIMENT','Saved code + dataset'),('RESULT','Raw output + units'),('VERIFICATION','Checks + failed controls'),('REVIEW','Recorded human decision')]
    for j,(a,b) in enumerate(trace):
        col=j%3; row=j//3; xx=.65+col*4.18; yy=2.88+row*1.71
        line(s,xx,yy,xx+3.67,yy,GREEN,1.4)
        text(s,f'{j+1:02} / {a}',xx,yy+.18,3.8,.35,13,GREEN,font=MONO)
        text(s,b,xx,yy+.71,3.65,.86,23,PAPER,True)
    label(s,'REVEAL STORYBOARD · No qualifying run attached. Hidden from the default judge pitch.',c=AMBER)
    note(s,10,'Follow one question all the way to a reviewable result.',
      '[After verification] Here is the source claim. The agent identified this specific gap and chose this test because the available data could distinguish the alternatives. This is the code it ran, the result it produced and the check it had to survive. Finally, this is the scientist’s recorded decision. [Before verification] This is the evidence we require before presenting an end-to-end discovery claim.',45,
      'This is a prepared storyboard, not a measured investigation. It contains no invented candidate, result, scientist decision or hidden chain of thought. Use concise logged explanations and exact artifacts.',
      'Populate every slot from ONE run. Record its ID, source and date, data hash, code, output, falsifier feedback and human review. Keep failures visible. Enable the sequence only after an independent audit, and save a local recording.',
      'Technical Execution (50); Reliability (25); UX (40)', ['plans/PLAN-demo-slides.md'])

    s=page(p,11,'Optional discovery sequence / survivors before the reveal',hidden=True)
    heading(s,'First, show what survived.')
    for i in range(3):
        x=.65+i*4.18
        rect(s,x,2.97,3.72,2.85,PANEL,LINE)
        text(s,f'CANDIDATE {i+1:02}',x+.23,3.27,3.25,.35,13,GREEN,font=MONO)
        text(s,'Claim in plain\nlanguage',x+.24,3.96,3.20,1.05,28,PAPER,True)
        text(s,'Result • comparator • scope',x+.24,5.18,3.23,.46,16,MUTED)
    label(s,'UNPOPULATED STORYBOARD · Card count is a layout example, not a measured survivor count.',c=AMBER)
    note(s,11,'First, show what survived.',
      '[After attaching the actual list] These are the candidates that survived the stated checks. Survival means a candidate merits review under that check’s contract; it does not establish truth or novelty. Let us focus on this one and what its result means. [Pause before advancing to the paper reveal.]',20,
      'There is no sourced survivor list yet. The three cards illustrate the layout only. Do not recite a candidate count or claim outcomes until the cards are replaced.',
      'Use the actual survivor count, rejected-branch denominator, named checks and exact run IDs. Select one candidate with a verified match to a later paper, and delete unused cards.',
      'Technical Execution (50); Reliability (25)', ['plans/PLAN-demo-slides.md'])

    s=page(p,12,'Optional discovery sequence / paper fades in on click',hidden=True)
    heading(s,'Then reveal where the\ncandidate leads.')
    text(s,'The surviving candidate',.66,3.15,5.35,.59,25,GREEN,True)
    text(s,'Connect the measured claim\nto the later published finding.',.68,4.09,5.28,1.34,29,PAPER)
    g=s.shapes.add_group_shape()
    rect(g,7.10,2.76,5.14,3.75,PAPER)
    text(g,'LATER DISCOVERY PAPER',7.49,3.14,4.38,.38,12,DARKGREEN,True,MONO)
    text(g,'Verified paper\ncover goes here',7.49,3.97,4.37,1.16,29,INK,True)
    text(g,'Title • authors • date • DOI\nExact match to the candidate',7.49,5.54,4.36,.69,17,DARKGREEN)
    fade(s,g)
    label(s,'UNVERIFIED REVEAL SLOT · A matching paper has not been selected. Do not present as a discovery.',c=AMBER)
    note(s,12,'Then reveal where the candidate leads.',
      '[After verification only] This candidate corresponds to the finding reported in this later paper. [Click; the paper fades in. Pause.] The compelling part is the route from the recorded evidence to that result. The next slide shows exactly what information the run could access, so you can judge what this recovery does—and does not—demonstrate.',20,
      'No paper has been selected, verified or presented as recovered. The paper group has a native 800 ms fade. PowerPoint playback is not available locally; the PDF shows the final state. This is not a novel-discovery claim.',
      'Insert the actual paper image while preserving the group entrance effect. Add accessible text, DOI, date and the rationale for the match. Keep the frozen-corpus slide IMMEDIATELY after the reveal. If no run qualifies, leave all four reveal slides hidden.',
      'Technical Execution (50); Originality; Reliability (25)', ['plans/PLAN-demo-slides.md','demo/pdac/README.md'])

    s=page(p,13,'Immediately after reveal / the evidence boundary',light=True,hidden=True)
    heading(s,'What could the system\nactually know?',light=True)
    rows(s,[('Accessible corpus','100 curated full-text papers; publication years 2007–2025.'),('Curation boundary','Inclusive 2026-01-25 boundary; bind the actual run manifest.'),('Excluded evidence','Prove the revealed paper was excluded from every accessible source.'),('Remaining limitation','A frozen corpus does not eliminate model prior knowledge.')],y=2.73,step=.87,light=True)
    label(s,'CURATION FACTS ≠ VERIFIED RUN BOUNDARY · Corpus, tool access and model-memory audit still required.',c=DARKGREEN)
    note(s,13,'What could the system actually know?',
      'The corpus was curated from 100 full-text papers published between 2007 and 2025, with an inclusive January 25, 2026 boundary. For this reveal, we must show the exact accessible manifest and demonstrate that the later paper was excluded from the run’s tools and data. Even then, pretrained model memory remains a limitation. Recovering a later published result from restricted evidence would be meaningful; it would not, by itself, prove an uncontaminated new discovery.',25,
      'The curation facts are committed. The actual run access boundary and the identity of the later paper remain unverified. The curation cutoff is not automatically a paper-publication-date cutoff for every task; check the manifest’s inclusive boundary.',
      'Keep this slide directly after the paper reveal. Add the actual run ID, frozen manifest hash, access logs, target paper hash and date, cutoff protocol, model version and memory control. Keep the uncertainty visible.',
      'Reliability, Evaluation & Trustworthiness (25); Technical Execution (50)', ['demo/pdac/README.md','demo/pdac/papers.json','plans/PLAN-demo-slides.md'])

    s=page(p,14,'Feasibility / a company starts with a useful workflow')
    heading(s,'Start with one research team.\nEarn the right to expand.')
    rows(s,[('Initial buyer','A research lead choosing computational experiments for a small team.'),('First product','A private research workspace, connected to approved data and tools.'),('Commercial hypothesis','Workspace subscription plus metered compute; validate willingness to pay.'),('Pilot acceptance','Useful reviewed hypotheses, independent reruns, total cost and analyst time.')],y=2.81,step=.83)
    label(s,'PROPOSED BUSINESS MODEL · No customer, pricing, revenue or cost-saving claims.')
    note(s,14,'Start with one research team. Earn the right to expand.',
      'The initial company opportunity is a research workflow people can evaluate in a small pilot. Start with one team, approved datasets and a bounded compute budget. Our pricing hypothesis is a workspace subscription plus metered compute, but willingness to pay is untested. The pilot has to measure whether researchers get useful, reproducible experiments and whether the total cost—including failed branches and review time—makes sense.',30,
      'This is a deployment and business proposal, not evidence of traction. Price the full investigation: LLM calls, GPU and CPU work, storage, egress and human review. Unit economics for a complete investigation have not been measured.',criteria='Feasibility & Deployment Potential (25)',sources=['docs/deployment.md','docs/runtime.md','plans/backlog.md'])

    s=page(p,15,'Deployment gates')
    heading(s,'The next milestone is proof\nthat survives outside the demo.')
    for j,(a,b,c) in enumerate([
      ('REPRODUCE','One bounded investigation','Freeze task and baselines.\nIndependent scientist rerun.'),
      ('HARDEN','One private pilot','Separate identities and data.\nConstrain access and spend.'),
      ('VALIDATE','One useful workflow','Measure quality and cost.\nTest the user workflow.')]):
        x=.64+j*4.18
        line(s,x,2.83,x+3.74,2.83,GREEN if j==0 else AMBER,1.8)
        text(s,a,x,3.08,3.8,.35,13,GREEN if j==0 else AMBER,True,MONO)
        text(s,b,x,3.79,3.77,1.1,28,PAPER,True)
        text(s,c,x,5.14,3.79,1.05,20,MUTED)
    label(s,'RESEARCH-USE ROADMAP · Clinical use, regulated deployment and operational threat forecasting are not validated.')
    note(s,15,'The next milestone is proof that survives outside the demo.',
      'There are three concrete deployment gates. First, independently reproduce a bounded investigation against strong alternatives. Second, harden a private pilot with real identity boundaries, restricted data access and execution, reliable logs and spend limits. Third, validate the workflow with researchers. Research use is the starting scope; clinical decisions or operational threat forecasting would need additional evidence, governance and regulatory review.',25,
      'These are proposed milestones. A separate process under the same Unix owner does not isolate private data. Data licenses, PHI and data agreements, SSO, tenancy, sandboxing and integration need review before broader deployment. No clinical regulatory clearance is implied.',criteria='Feasibility & Deployment Potential (25); Reliability (25); Understanding of User (30)',sources=['docs/deployment.md','docs/native-evidence.md','plans/backlog.md'])

    s=page(p,16,'DN Research / closing')
    close=ASSETS/'closing.jpg'
    if close.exists():
        pic(s,close,0,0,W,H)
        shade=rect(s,0,0,W,H,INK)
        alpha=OxmlElement('a:alpha'); alpha.set('val','42000')
        shade._element.xpath('.//a:srgbClr')[0].append(alpha)
    text(s,'DN / RESEARCH',.64,.36,4,.4,14,PAPER,True,MONO)
    text(s,'Give scientists\na head start.',.61,1.60,9.1,2.15,61,PAPER,True)
    text(s,'On the biology that will shape\nindustrial strength, health and security.',.67,4.28,8.9,1.25,29,GREEN)
    text(s,'Our ambition: reduce the window\nof unilateral biological advantage.',.69,6.02,9.3,.90,22,PAPER)
    note(s,16,'Give scientists a head start.',
      'Biology will help shape industrial strength, health and security. We want scientists to have more lead time to understand what comes next. We have built the beginnings of an inspectable research engine and tested substantive parts of its toolkit. The next step is a bounded research partnership that can independently judge its usefulness. Our ambition is to reduce the window of unilateral biological advantage.',25,
      'This is a strategic ambition and a request for a pilot. It does not imply guaranteed prediction, deployment outcomes or an existing customer partnership. The closing art is conceptual. Alignment with DTX is our inference from its critical-technology thesis.',criteria='Problem & Real-World Impact (25); Feasibility (25)',sources=['dtx','foresight','presentation/assets/v2/README.md'])

    s=page(p,17,'Appendix / direct rubric coverage',hidden=True)
    heading(s,'Every judging criterion has an evidence trail.')
    specs=[('MAIN PRIZES','25 Problem / impact','1–4,16','50 Technical execution','6–13,18–24,28–29','25 Feasibility / deployment','14–15,26'),('BEST USE OF AI','25 Novelty / importance','4,6,25','50 Technical sophistication','6–9,18–24,28–29','25 Reliability / evaluation','9–13,19–24,28–29'),('BEST IN DESIGN','30 Design / craft','5,7,18','40 UX / usability','5–7,18','30 Understanding the user','5,14–15')]
    for j,items in enumerate(specs):
        x=.64+j*4.18
        text(s,items[0],x,2.83,3.8,.4,14,GREEN,True,MONO)
        for k in range(3):
            yy=3.52+k*.89
            text(s,items[1+2*k],x,yy,3.86,.44,18,PAPER,True)
            text(s,'SLIDES '+items[2+2*k],x,yy+.46,3.83,.3,12,MUTED,font=MONO)
    label(s,'Weights supplied by the team · No score or award outcome predicted.')
    note(s,17,'Every judging criterion has an evidence trail.',
      'The presentation gives the largest share of technical discussion to execution and AI sophistication, matching the fifty-point weights. We connect the problem to strategic lead time, show actual artifacts and negative results, and state deployment and user-validation gaps directly. The slide references here let us answer each rubric question with evidence instead of adjectives.',25,'The rubric was supplied by the user. The weights and slide references reflect that rubric. No scores have been self-awarded.',criteria='All supplied criteria',sources=['plans/PLAN-demo-slides.md'])

    s=page(p,18,'Appendix / design follows the scientific task',hidden=True)
    heading(s,'A useful view makes a hidden problem visible.')
    pic(s,REPO/'docs/binder-review/runtime-scene-hero.png',.64,2.55,6,3.1)
    pic(s,REPO/'docs/binder-review/scene-replay-interface-close-stage.png',6.76,2.55,6,3.1)
    text(s,'Orient in the complete structure',.69,5.91,5.82,.49,23,GREEN,True)
    text(s,'Inspect the contact-only cutaway',6.8,5.91,5.85,.49,23,GREEN,True)
    label(s,'ACTUAL UI CAPTURES · Same illustrative geometry. Color is paired with labels; opposing views expose occlusion.')
    note(s,18,'A useful view makes a hidden problem visible.',
      'A binder is a protein designed to attach to a target. This is a concrete design decision driven by the user’s task. A complete structure is good for orientation, but it can hide the interface. A contact-only cutaway and opposing view expose the region the scientist needs to inspect. The visual review caught a camera-preset bug that a screenshot test initially missed. Labels, reproducible camera state and coordinate checks make the image useful rather than decorative.',25,
      'The scene uses an illustrative 1CRN fixture. The recorded raycast captured 19 / 20 contact residues in the primary view, 18 / 20 in the reverse view and 20 / 20 across both views. These counts do not measure binding affinity. The UI inspection notes record actual iterations and fit at a 390 px mobile width.',criteria='Design Quality & Craft (30); UX (40); Understanding of User (30)',sources=['docs/binder-review/README.md','docs/binder-review/scene-replay-interface-close.json'])

    s=page(p,19,'Appendix / trained components at a glance',hidden=True)
    heading(s,'What we trained—and what we did not.')
    matrix=[('Expression','Masked autoencoder + sequential neural bettor','Reconstruct expression; score fresh paired observations.'),('Protein','PCA / rank-PCA / masked denoiser','Learn protein-abundance structure and missingness.'),('Drug response','Separate encoders + ridge + bounded critic','Predict response; test association between two views.'),('Cell ecosystems','Cell encoders + lineage model + donor critics','Represent populations; predict labels; compare donor views.'),('Branch monitor','Per-prefix logistic models: implementation only','Real-trajectory fitting and calibration still pending.')]
    for i,(a,b,c) in enumerate(matrix):
        y=2.68+i*.70
        line(s,.65,y,12.69,y)
        text(s,a,.66,y+.13,2.1,.43,18,GREEN,True)
        text(s,b,2.95,y+.10,5.04,.5,17,PAPER,True)
        text(s,c,8.36,y+.10,4.3,.59,15,MUTED)
    label(s,'Pretrained LLMs / embeddings are dependencies. Renderers and fixed statistical tests are not team-trained models.')
    note(s,19,'What we trained—and what we did not.',
      'The trained components have different jobs. The expression model learns a representation, while the sequential bettor scores fresh paired observations. Protein, drug-response and ecosystem modules learn representations or prediction functions under their own split contracts. The branch monitor is different: it is intended to estimate a research branch’s future usefulness, but has not been fitted and calibrated on real trajectories. We do not count renderers or pretrained dependencies as models we trained.',30,
      'The following slides give each model’s data and splits. Training a model does not establish useful power or real biological confirmation. Biological evidence and branch-monitor statistics answer different questions and must remain distinct.',criteria='AI Technical Sophistication (50); Reliability (25)',sources=['research/learned-evalue-validation/real-expression/README.md','docs/protein-training.md','docs/pharmacotype-training.md','docs/ecosystem-training.md','docs/branch-monitoring.md'])

    s=page(p,20,'Appendix / expression representation and evidence',hidden=True)
    heading(s,'A measured training curve.\nA separate evidence trajectory.')
    pic(s,PLOTS/'expression.png',.61,2.53,8.01,3.71)
    text(s,'374 day-zero donors',8.96,2.75,3.71,.58,25,GREEN,True)
    text(s,'TRAIN 149 / DEV 74 / EVAL 151\n19,000→512→128 encoder\n15% masking · 100 epochs\nMasked reconstruction objective',8.98,3.6,3.71,1.56,18,PAPER)
    text(s,'Single-gene baseline has\ngreater final evidence\nin the primary run.',8.98,5.34,3.7,.99,20,AMBER,True)
    label(s,'GSE212041 · Observational COVID cohort; not PDAC. Training loss only; no epoch-level validation history retained.')
    note(s,20,'A measured training curve. A separate evidence trajectory.',
      'This expression diagnostic uses 374 day-zero donors: 149 for training, 74 for development and 151 for evaluation. We trained a masked autoencoder on genes selected from the training data for 100 epochs. The plotted loss is training loss; we did not retain a held-out loss at every epoch. The evidence plot measures something different: evidence from 30 selected evaluation pairs, of which 22 are scored after burn-in. The IFIT3 single-gene baseline finishes with more evidence than the learned representation.',35,
      'The source is TPM data from GSE212041. TRAIN contains 119 positive and 30 negative donors; DEV contains 59 positive and 15 negative donors; EVAL contains 121 positive and 30 negative donors. The 30 selected pairs are not clinical matches, and 91 positive evaluation donors are unused. The encoder is 19k → 512 → 128, fitted with Adam at .001 and seed 20260905. The bettor has 64 / 64 ReLU layers and maximizes log payoff using past data. It uses 4 pairs per batch, 2 burn-in batches, at most 100 epochs per update, patience 10, learning rate .0005 and weight decay .01. Final evidence is 3652.81 for the learned encoder, 85.76 for PCA and 5964.41 for IFIT3. This is not an independent estimate of clinical power.',criteria='AI Technical Sophistication (50); Reliability (25)',sources=['research/learned-evalue-validation/real-expression/README.md','research/learned-evalue-validation/real-expression/training.json','research/learned-evalue-validation/real-expression/evaluation.json'])

    s=page(p,21,'Appendix / protein model selection',hidden=True)
    heading(s,'The protein baseline won\nthe held-out reconstruction test.')
    pic(s,PLOTS/'protein.png',.63,2.56,7.35,3.63)
    text(s,'219 train / 110 validation',8.38,2.79,4.34,.61,25,GREEN,True)
    text(s,'CPTAC: breast + colon train\nLung cohort validates\n105 pancreatic tumors: development set',8.41,3.62,4.18,1.20,19,PAPER)
    text(s,'Denoiser: 4000→256→32→2000\n20% corruption · 50 epochs\nHidden-value reconstruction',8.42,5.08,4.15,1.13,18,MUTED)
    label(s,'protein-s10-20260906-v2 · Standardized hidden-entry MSE, lower is better. Epoch loss histories were not retained.')
    note(s,21,'The protein baseline won the held-out reconstruction test.',
      'The protein model trains on 219 breast and colon tumors and is selected using 110 lung tumors. Values and missingness masks feed a denoiser with a 32-dimensional bottleneck. On frozen hidden entries, PCA’s mean squared error is 1.8243, compared with 2.1067 for the denoiser and 2.9318 for mean fill. The selected denoiser checkpoint is at the 50-epoch budget boundary, so we do not claim convergence. These results support retaining strong, simple comparators.',30,
      'The study selects 2,000 features using TRAIN coverage. Values and masks form 4000 inputs. Training uses AdamW at .001, batch size 32 and seed 0. The PDAC development set contains 105 cases, of which 104 are graded. Grade AUROC is .7816 for rank-PCA and .6262 for the denoiser; this is exposed development. Complete local artifacts for curated v2 are absent from this checkout; chart values come from committed documentation. Slide 28 presents the subsequent external benchmark with its own aggregate audit.',criteria='AI Technical Sophistication (50); Reliability (25)',sources=['docs/protein-training.md','src/dnhacksbio/protein_encoder.py'])

    s=page(p,22,'Appendix / drug response',hidden=True)
    heading(s,'Two real datasets.\nTwo limits on the claim.')
    pic(s,PLOTS/'pharmacotype.png',.62,2.51,6.08,3.64)
    pic(s,PLOTS/'pdo.png',6.82,2.51,5.84,3.64)
    label(s,'PRISM: 245/40/71 groups · PDO: 21/5/12 donors. Lower RMSE is better. These endpoints and scales differ.')
    note(s,22,'Two real datasets. Two limits on the claim.',
      'The PRISM task predicts adjusted log2 fold-change versus solvent control from molecular features, using 245 training, 40 validation and 71 test patient-origin groups. PCA is selected by mean validation error across three seeds; it does not beat the mean baseline in the pancreatic test subset. A separate 38-donor patient-derived organoid dataset measures aggregate response area. Its five-donor validation split favors the training mean over every learned method. This does not establish a successful predictor of full response curves or biological confirmation.',35,
      'PRISM covers 4 drugs at 8 doses and a 120 h exposure. Feature selection uses 1000 training genes. The compared representations are identity, PCA with 32 dimensions and one-layer tanh autoencoders with 15% masking, at most 150 epochs and patience 15. The ridge penalty is 10. A bounded bilinear critic uses an MSE objective on matched versus crossed views; molecular and response encoders train separately. The PDO split is 21 TRAIN / 5 VAL / 12 TEST. Its AUC target is one normalized area-under-response-curve value per drug, not a full dose-response curve. The CUDA fits were run, but epoch histories were not retained. Subsequent training-only RBF tuning achieved validation RMSE 0.1703 versus the mean baseline 0.1562; its improvement on an already exposed test set is not independent confirmation. Adaptive synthetic critic diagnostics show 35.52% power for the simple alternative and 0% for the nonlinear alternative. Release eligibility remains false.',criteria='AI Technical Sophistication (50); Reliability (25)',sources=['docs/pharmacotype-cuda-training.json','docs/pharmacotype-pdo-auc.json','docs/pharmacotype-training.md','docs/pharmacotype-adaptive-validation.json','docs/pharmacotype-tuning.json'])

    s=page(p,23,'Appendix / initial Peng–Lin ecosystem pilot',hidden=True)
    heading(s,'Represent the cells.\nKeep the donor as the unit of evidence.')
    pic(s,PLOTS/'ecosystem.png',.62,2.50,8.09,3.78)
    text(s,'Peng → Lin transfer',9.04,2.75,3.69,.55,25,GREEN,True)
    text(s,'16 training donors\n8 held-out donor partition\n32 cells per eligible donor\n2,000 genes per compartment',9.06,3.61,3.66,1.44,18,PAPER)
    text(s,'Cell PCA retained.\nNeural gain unproven.',9.07,5.41,3.67,.89,22,AMBER,True)
    label(s,'INITIAL PILOT · 20 NB training epochs + final held-out errors. Expanded train/validation curves: slide 29.')
    note(s,23,'Represent the cells. Keep the donor as the unit of evidence.',
      'Single-cell datasets contain many cells, but cells from one person are not independent donors. We trained separate representations for malignant-enriched and fibroblast compartments, using equal samples of 32 cells per eligible training donor. The count model uses a negative-binomial reconstruction objective. A separate set model tries to preserve donor summaries and stability across subsamples. Cell PCA wins the current reconstruction comparisons on the Peng holdout and Lin external development data. Missing compartments reduce the actual donor coverage.',35,
      'Peng donors T1–T16 form TRAIN; T17–T24 form DEV. Lin contributes 10 primary donors for external development. Actual training uses 512 malignant-enriched cells from 16 donors and 416 fibroblast cells from 13 donors. Peng has 8 eligible malignant-enriched and 5 eligible fibroblast held-out donors; Lin has 7 and 9 respectively. Both compartments are available in 5 Peng and 6 Lin donors. The negative-binomial model is 2000 → 32 tanh → 2001, trained for 20 CPU epochs with a library offset and learned dispersion. The set model is 32 → 8 tanh, followed by mean pooling and a 64-dimensional summary decoder. It trains for 20 epochs with Adam at .01, using reconstruction plus .1 times the stability loss. No held-out neural advantage or private biological confirmation was established.',criteria='AI Technical Sophistication (50); Reliability (25)',sources=['docs/ecosystem-training.md','docs/ecosystem-training/metrics.json','docs/ecosystem-training/set-metrics.json'])

    s=page(p,24,'Appendix / two different evidence questions',hidden=True)
    heading(s,'Internal e-value tools and branch monitoring\nanswer different questions.')
    rows(s,[('Biological tools','Is a specified measured relationship supported under its sampling contract?'),('Fixed statistics','Permutation / calibrated tests are statistical logic, not trained encoders.'),('Branch monitor','Could this research branch produce a qualifying result under a frozen budget?'),('Current readiness','Monitor code exists. Real-trajectory training and calibration remain uncompleted.')],y=2.72,step=.87)
    label(s,'NO LIVE CALIBRATED PRUNING · Learned branch ratios are not automatically exact e-processes.',c=AMBER)
    note(s,24,'Biological evidence and branch monitoring answer different questions.',
      'The internal evidence tools test specified measured relationships. The branch monitor asks a different question: whether continuing a research branch is likely to produce a qualifying result under a fixed policy and budget. Its design uses one logistic model per prefix and root-group-disjoint training, calibration and test splits. That implementation has not yet been trained or calibrated on real trajectories. We must not present its synthetic tests as a deployed statistical stopping guarantee.',35,
      'The proposed branch labeler uses an LLM assessor rubric after a legacy CANDIDATE result; its label is a proxy, not expert truth or independent reproduction. The monitor uses class-prior-corrected odds and history ratios, with weights for roots and episodes. At alpha .045 and delta .005, the first finite order-statistic threshold requires 116 independent successful calibration episodes; 115 are insufficient. Repeated checkpoints are not independent episodes. The operational limits of 3600 summed seconds and 288 actions are not a statistical deadline.',criteria='AI Technical Sophistication (50); Reliability (25)',sources=['docs/branch-monitoring.md','docs/dependency-scoring.md','docs/drug-response-scoring.md','docs/expression-scoring.md'])

    s=page(p,25,'Appendix / originality and the competitive test',hidden=True)
    heading(s,'The differentiation has to be demonstrated.')
    rows(s,[('Existing research agents','Elicit supports research workflows; DeepMind Co-scientist generates and evaluates hypotheses.'),('Our proposed wedge','Executable investigations with specialized biological tools, receipts and an inspectable tree.'),('The comparison to run','Strong single agent, flat parallel agents and our controller under the same total budget.'),('The outcome that matters','Independent rerun success, expert usefulness, time and total cost—including failures.')],y=2.73,step=.88)
    label(s,'POSITIONING HYPOTHESIS · No first-in-category, superior-performance or defensible-moat claim yet.')
    note(s,25,'The differentiation has to be demonstrated.',
      'Existing research agents are substantive systems, so being an AI researcher is not enough of a differentiator. Our proposed wedge is executable, inspectable investigation with specialized tools and explicit evidence contracts. The right test is an equal-budget comparison against a strong single agent and flat parallel research. We should measure independently rerunnable useful work, not the number of generated hypotheses. A defensible product advantage remains to be earned.',30,
      'The primary prior-art pages were verified; no head-to-head comparison has been run. The project reuses open-source scientific tools and renderers. The novelty claim concerns engineering integration and the proposed workflow, not new foundational statistics or the first AI scientist.',criteria='Technical Execution originality (50); AI Novelty (25); Feasibility (25)',sources=['elicit','deepmind','plans/backlog.md'])

    s=page(p,26,'Appendix / deployment diligence and evidence status',hidden=True)
    heading(s,'What a pilot must settle.')
    rows(s,[('Cost + infrastructure','Meter model calls, jobs, storage and review. Benchmark a complete investigation.'),('Security + integration','Enforce service identities, approved sources, restricted execution, audit export and access controls.'),('Regulation + adoption','Start with research use; assess dataset licenses, privacy, clinical scope and user workflow.'),('Proof boundary','No verified later-paper recovery, clinical benefit, customer traction or production certification.')],y=2.73,step=.90)
    label(s,'Evidence snapshot: '+ds.SNAPSHOT[:7]+' · Appendices are for questions; check the manifest before presenting.')
    note(s,26,'What a pilot must settle.',
      'For deployment, we need the total cost of a complete investigation, not just a cheap encoder fit. We need actual security boundaries, approved data access, restricted execution and an audit path that fits the customer’s workflow. Research use is the initial scope; privacy, licensing and any later clinical application require their own review. The current evidence supports a technically substantive prototype, while discovery recovery, customer value and production readiness still need proof.',30,
      'This evidence ledger describes the audited snapshot. Update it when newly merged work supplies source artifacts. Main-build tests check code behavior; they do not establish clinical or statistical validity. No TAM, customer logos, savings or regulatory clearance have been invented.',criteria='Feasibility & Deployment Potential (25); Reliability (25)',sources=['docs/deployment.md','docs/native-evidence.md','presentation/validation.md'])

    s=page(p,27,'Appendix / 3D toolkit readiness',hidden=True)
    heading(s,'Every 3D tool keeps its own evidence boundary.')
    rows(s,[('Binder workbench','Recorded scene, image observation and reverse view. Illustrated geometry; affinity unmeasured.'),('Molecular geometry','Scoped preparation, docking, image review and coordinate checks. Recovery benchmark did not pass.'),('Spindle mechanics','Pinned Cytosim CPU worker; real pilot exports 11 three-dimensional frames. Calibration remains ahead.'),('Tumor–stroma','Native simulation and image workflow are active development beyond the audited snapshot.')],y=2.73,step=.88)
    label(s,'3D geometry, simulated mechanics and biological experiments are different evidence types.')
    note(s,27,'Every 3D tool keeps its own evidence boundary.',
      'The binder workbench demonstrates a recorded visual loop, but its current showcased geometry is illustrative. Molecular tools now run scoped preparation and docking as well as image review and coordinate checks. Their three-seed recovery benchmark did not pass; no inhibition or efficacy is established. The spindle worker runs pinned native mechanics and exports real three-dimensional frames; biological calibration is still ahead. Tumor–stroma simulation and further image integrations are active work and should be upgraded in this deck only with their actual artifacts.',30,
      'Snapshot-specific status. Binder: no BindCraft inference demonstrated. Inhibitor: scoped docking and image-review workflow is merged; the frozen recovery result is negative. Spindle pilot uses stock aster_dynamic, shortened to 100 time steps, seed 41, 11 exported frames. Tissue development is separate from the measured statistical cellular-ecosystem module.',
      'When new work lands, replace this status with scoped run IDs, native receipts, actual images and numerical controls. Do not reuse an illustrative image as evidence of a measured biological result.',
      'Technical Execution (50); AI Technical Sophistication (50); Design Quality (30)', ['docs/binder-review/README.md','docs/inhibitor-workbench.md','docs/spindle-build-pilot.json','plans/3d-experiment-tools/03-tumor-stroma.md'])

    s=page(p,28,'Appendix / external protein transfer',hidden=True)
    heading(s,'External data changed the conclusion.')
    pic(s,PLOTS/'external_protein.png',.61,2.43,8.15,3.87)
    text(s,'224 graded tumors',9.10,2.68,3.61,.69,26,GREEN,True)
    text(s,'Fudan external benchmark\n159 G3 / 65 G2 tumors\nFive prespecified views',9.12,3.63,3.55,1.17,19,PAPER)
    text(s,'Weak primary transfer.\nSecondary signal needs\nindependent evaluation.',9.13,5.13,3.55,1.05,20,AMBER,True)
    label(s,'CROSS-ASSAY EXPLORATORY BENCHMARK · Bootstrap intervals condition on the frozen model and observed cases.')
    note(s,28,'External data changed the conclusion.',
      'The larger Fudan benchmark includes 224 graded tumors. All five views were specified before scores were inspected. The primary rank-PCA model achieved an AUROC of 0.552, showing weak transfer. A prespecified secondary kernel achieved 0.694, but its source-fixed classification threshold gave only about 0.553 balanced accuracy. That is a follow-up ranking signal, not a validated grade classifier or independent sequential confirmation. The important result is that external data changed what we could responsibly claim.',35,
      'Source: protein-external-results.json. Primary rank-PCA AUROC 0.55249, 95% stratified bootstrap interval 0.47141–0.63377. Secondary RBF rank kernel 0.69376, interval 0.625–0.764; use the JSON for exact values. 224 graded tumors: 159 G3 and 65 G2, allowing 65 possible grade pairs. Reference-normalized CPTAC and label-free Fudan are different assays; cohort-wide processing prevents untouched-confirmation claims. PCA used 219 non-PDAC training cases; supervised balanced ridge heads used 104 CPTAC grades, penalty 1. RBF gamma was 1/feature-count. No external-label model tuning was performed.',
      'Keep all five prespecified views and sensitivity analyses available. Do not promote the secondary result to the primary result, select a threshold using external labels or describe this as a qualifying discovery-paper recovery.',
      'Technical Execution (50); AI Technical Sophistication (50); Reliability (25)', ['docs/protein-external.md','docs/protein-external-results.json','docs/protein-external-training.json','docs/protein-external-audit.json'])

    s=page(p,29,'Appendix / expanded ecosystem training',light=True,hidden=True)
    heading(s,'Real validation curves.\nPCA still leads externally.',light=True)
    text(s,'72 DONOR RECORDS  /  45 TRAIN  /  11 VALIDATION  /  16 EXTERNAL',.65,2.47,12,.35,13,DARKGREEN,True,MONO)
    sh=s.shapes.add_picture(str(REPO/'docs/ecosystem-expansion/training-curves.png'),Inches(.70),Inches(2.92),width=Inches(11.90),height=Inches(3.75))
    sh.crop_top=.045; sh.crop_bottom=.485
    source_footer(s,'EPITHELIAL MODELS SHOWN · Actual three-seed histories. Full fibroblast curves and source JSON are linked in Notes.',light=True)
    note(s,29,'Real validation curves. PCA still leads externally.',
      'The expanded study now covers 72 donor records across five original studies: 45 for training, 11 for validation and 16 in external studies. These are the actual training and validation histories for the epithelial models, with all three seeds shown. The full record also contains fibroblast histories. Denoising training improves substantially, but exact PCA remains the stronger external reconstruction baseline. This is measured development work, not biological confirmation.',35,
      'Source fee3165: 338,900 prepared cells; a per-donor loading cap leaves 313,518. Separate epithelial/fibroblast denoising and negative-binomial encoders use 2,625 genes, width 256, latent size 64, 15% masking, up to 200 epochs and validation patience 35, seeds 2701–2703. The three-seed L40S run took 299 seconds with 10.8 GB peak allocation, excluding preceding pilot and later exact-PCA refresh. External MSE: exact PCA .28736/.23721, denoiser seed mean .29187/.24350, NB .36698/.29949 for epithelial/fibroblast. Epithelial denoising narrowly wins validation .20177 vs PCA .20197, so do not say PCA wins every validation comparison. Two NB fits select epoch 200; no blanket convergence claim. New epithelial definitions and cell-weighted metrics differ from the initial pilot. Seed variation is not donor uncertainty.',
      'Native PowerPoint crop shows the top two panels of the unchanged original figure. Complete four-panel PNG/PDF is docs/ecosystem-expansion/training-curves.*. Also review held-out-comparison.*, lineage-curves.* and association-controls.*. Lineage accuracy drops from 97.0% validation to 77.9% external Lin; donor-matching neural AUROC .647–.683 trails bilinear .692 on only 20 held-out donors.',
      'AI Technical Sophistication (50); Reliability (25); Technical Execution (50)', ['docs/ecosystem-expansion.md','docs/ecosystem-expansion/metrics.json','docs/ecosystem-expansion/training-curves.pdf'])

    custom_shows(p)
    p.save(OUT/'DNHacks_2026_DN_Research.pptx')
    return p


if __name__=='__main__':
    build(); templates()
    invalid=[b for b in BOUNDS if b[1]<0 or b[2]<0 or b[1]+b[3]>W+.01 or b[2]+b[4]>H+.01]
    if invalid: raise ValueError(f'Text outside slide: {invalid}')
    core=[1,2,3,4,5,6,7,8,9,14,15,16]
    total=sum(x['seconds'] for x in TALK if x['slide'] in core)
    (ROOT/'speaker-notes.md').write_text('# Tentative speaking script\n\nDefault judge pitch: slides '+', '.join(map(str,core))+f' ({total} seconds). Slides 10–13 are hidden discovery storyboards; 17–29 are hidden Q&A. Every slide has editable PowerPoint Notes.\n\n'+'\n\n'.join(f"## {a['slide']:02} — {a['title']}\n\n{a['notes']}" for a in TALK)+'\n')
    (OUT/'deck-manifest.json').write_text(json.dumps({'source_snapshot':ds.SNAPSHOT,'built_on':'2026-09-06','main_slides':29,'core_slides':core,'core_seconds':total,'hidden_slides':HIDDEN,'reveal_sequence':[10,11,12,13],'paper_reveal_slide':12,'frozen_corpus_slide':13,'layout_kit_slides':4,'fonts':[FONT,MONO],'sources':SOURCES},indent=2)+'\n')
    print(f'Built 29 slides; default pitch {total}s; 4 reusable layouts.')
