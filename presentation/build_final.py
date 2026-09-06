#!/usr/bin/env python3
"""Final DNHacks 2026 judge deck: ten slides, synthesised from the three working drafts.

Run with the system interpreter (python-pptx lives there, not in the uv venv):
    python3 presentation/build_final.py
"""
from __future__ import annotations
import math
import random
from pathlib import Path

from PIL import Image
from pptx.util import Inches

import arch_art
from deck_style import *  # noqa: F401,F403 - shared palette and primitives

ASSETS = ROOT / 'assets/v2'
PLOTS = ASSETS / 'plots'
FLAVOR = ASSETS / 'flavorgraph'
OUTFILE = OUT / 'DNHacks_2026_DN_Research_FINAL.pptx'

SOURCES.update({
    'flavorgraph': ('Park, Kim, Kim, Spranger & Kang, FlavorGraph, Scientific Reports 11:931 (2021), CC BY 4.0',
                    'https://doi.org/10.1038/s41598-020-79422-8'),
    'nsceb': ('NSCEB final report, April 2025, §1.3', 'https://www.biotech.senate.gov/final-report/chapters/chapter-1/section-3/'),
    'nsceb_window': ('NSCEB April 2025 action plan: a three-year window to retain or regain biotechnology leadership',
                     'https://www.biotech.senate.gov/final-report/'),
    'stack': ('Adversarial attacks on LLM safeguard pipelines, arXiv:2506.24068, appendix K.1',
              'https://arxiv.org/abs/2506.24068'),
    'aisi': ('AI Security Institute, pre-deployment biology and chemistry evaluations',
             'https://www.aisi.gov.uk/'),
    'davt': ('Pandeva, Forre, Ramdas & Shekhar, Deep anytime-valid hypothesis testing, AISTATS 2024',
             'https://proceedings.mlr.press/v238/pandeva24a.html'),
})


# ----------------------------------------------------------------------------- helpers

def page(p, section, light=False):
    n = len(p.slides._sldIdLst) + 1
    return slide(p, n, section, None, light)


def pic(s, path, x, y, w, h):
    path = Path(path)
    with Image.open(path) as im:
        ratio = im.width / im.height
    ww = min(w, h * ratio)
    hh = ww / ratio
    return s.shapes.add_picture(str(path), Inches(x + (w - ww) / 2), Inches(y + (h - hh) / 2),
                                width=Inches(ww), height=Inches(hh))


def label(s, t, x=.6, y=6.62, w=12.1, c=MUTED):
    text(s, t, x, y, w, .32, 10, c, font=MONO)


def heading(s, t, y=1.04, size=36, light=False, w=12.1):
    text(s, t, .6, y, w, 1.24, size, INK if light else PAPER, True)


def kicker(s, t, y=2.14, light=False, w=11.9, size=19):
    text(s, t, .62, y, w, .6, size, DARKGREEN if light else MUTED)


def column(s, x, w, title, body, y=2.62, c=GREEN, rule=True, tsize=20, bsize=16.5, light=False):
    if rule:
        line(s, x, y, x + w, y, c, 1.5)
    text(s, title, x, y + .18, w, .46, tsize, c, True)
    text(s, body, x, y + .76, w, 1.9, bsize, INK if light else PAPER)


def flow(s, x, y, w, blocks, gap=.15):
    """Stack paragraphs with heights computed from the wrapped line count."""
    for content, size, colour in blocks:
        per_line = max(12, int(w * 72 / (.505 * size)))
        lines = 0
        for para in content.split('\n'):
            lines += max(1, -(-len(para) // per_line))
        h = lines * size * 1.10 / 72
        text(s, content, x, y, w, h + .04, size, colour)
        y += h + gap
    return y


def items(s, x, y, w, entries, tsize=18.5, bsize=14.5, gap=.30, colour=GREEN):
    """Ruled list whose rows grow with their own wrapped text."""
    for a, bd in entries:
        line(s, x, y, x + w, y, LINE)
        text(s, a, x, y + .12, w, tsize * 1.2 / 72 + .04, tsize, colour, True)
        yy = y + .14 + tsize * 1.18 / 72
        per = max(12, int(w * 72 / (.505 * bsize)))
        lines = max(1, -(-len(bd) // per))
        h = lines * bsize * 1.12 / 72
        text(s, bd, x, yy, w, h + .04, bsize, PAPER)
        y = yy + h + gap
    return y


def chaos_graph(s, x, y, w, h, seed=11, n=150):
    """A denser, messier literature cloud than the cover diagram's default."""
    rng = random.Random(seed)
    pts = []
    for _ in range(n):
        a = rng.random() * math.tau
        r = rng.uniform(.02, 1.0) ** .48
        pts.append((x + w * .5 + math.cos(a) * r * w * .48, y + h * .5 + math.sin(a) * r * h * .48))
    for i, a in enumerate(pts):
        for k in sorted(range(len(pts)), key=lambda k: math.dist(a, pts[k]))[1:4]:
            if k > i:
                line(s, *a, *pts[k], "33453E", .55)
    for _ in range(16):  # long-range cross links: the field is not tidy
        a, b = rng.choice(pts), rng.choice(pts)
        line(s, *a, *b, "2C3B36", .5)
    for i, (px, py) in enumerate(pts):
        dot(s, px, py, .016 if i % 4 else .029, "5E8571")


# ----------------------------------------------------------------------------- slides

def slide_01(p):
    s = page(p, 'DN Research / biological foresight')
    arch_art.architecture_art(s, 6.16, 1.34, 6.64, 4.62, chaos=True)
    text(s, 'Autonomous research\nfor biological\nforesight', .6, 1.40, 5.7, 2.1, 34, PAPER, True)
    text(s, 'Biological breakthroughs can create\nunilateral power before defenses adapt.',
         .63, 4.02, 5.3, .9, 19, GREEN)
    text(s, 'We connect the literature to executable\nexperiments and inspectable evidence.',
         .63, 5.30, 5.4, .9, 18, PAPER)
    label(s, 'PROTOTYPE  ·  DNHACKS 2026  ·  OPEN CATEGORY', y=6.86)
    note(s, 'Autonomous research for biological foresight.',
         'Biology is an underappreciated source of future unilateral power: a discovery can hand one actor a '
         'capability others have not anticipated, and reactive measures are weakest exactly when the capability is new. '
         'DN Research connects published evidence to executable experiments and keeps every step inspectable. '
         'A literature graph aims the compute, recursive agent sessions spend it, and a statistics floor and then a '
         'person decide what counts.', 30,
         'Strategic thesis and intended application. The prototype does computational biological research; it does not '
         'demonstrate bioweapon prediction or operational threat prevention. The cover diagram is drawn from the real '
         'architecture: claim graph, recursive sessions, human gate.',
         'Confirm the working name and entered category before presenting.',
         'Problem & Real-World Impact (25); Feasibility & Deployment (25)',
         ['dtx', 'nsceb', 'ARCHITECTURE.md'])


def slide_02(p):
    s = page(p, 'Why now / national security framing')
    heading(s, 'AI is accelerating biology.\nDefense needs a head start.', size=34)
    stats = [
        (GREEN, 'CAPABILITY', 'Up to 60%', 'above PhD-level baselines on selected biology and chemistry questions.',
         'AISI · pre-deployment evaluations'),
        (AMBER, 'SAFEGUARDS', '79% → 100%', 'attack success of one published jailbreak template on a 100-item bioweapons query set, against a classifier-guarded frontier model.',
         'arXiv:2506.24068 · appendix K.1'),
        (ROSE, 'THE WINDOW', '3 years', 'the window Congress’s biotechnology commission gives the United States to hold, or regain, the lead.',
         'NSCEB action plan · April 2025'),
    ]
    for j, (c, kind, value, body, src) in enumerate(stats):
        x = .62 + j * 4.13
        line(s, x, 2.66, x + 3.76, 2.66, c, 1.6)
        text(s, kind, x, 2.84, 3.7, .28, 11, c, True, MONO)
        text(s, value, x, 3.20, 3.9, .92, 42, PAPER, True)
        text(s, body, x, 4.22, 3.72, 1.5, 15.5, MUTED)
        text(s, src, x, 5.62, 3.74, .3, 10, c, font=MONO)
    line(s, .6, 5.98, 12.73, 5.98, LINE)
    text(s, '“The United States tends to play catch-up after critical\ntechnologies have already become mainstream.”',
         .63, 6.12, 8.3, .76, 17, PAPER, True)
    text(s, 'NSCEB\n2025 FINAL REPORT · §1.3', 9.5, 6.16, 3.2, .66, 11, GREEN, font=MONO)
    label(s, 'PUBLIC SOURCES · The jailbreak template reached 100% once the queries were rephrased. Quoted from cited '
             'public evaluations; our engine has not been used for threat assessment.', y=6.86, w=12.1)
    note(s, 'AI is accelerating biology. Defense needs a head start.',
         'Three public facts frame the problem. Frontier models now score well above expert baselines on selected '
         'biology and chemistry questions. Safeguards are real but not sufficient: a published universal jailbreak '
         'template reached seventy-nine percent attack success on a hundred-item bioweapons query set against a '
         'classifier-guarded model, and one hundred percent once the queries were rephrased. And the national '
         'biotechnology commission gives the United States a three-year window to hold or regain the lead, exactly '
         'as AI compresses the discovery cycle. Defense follows publication, so the dangerous region is the part of '
         'biology nobody has written on yet.', 35,
         'All three figures are quoted from public sources; we measured none of them. The jailbreak result is '
         'appendix K.1 of arXiv:2506.24068. The three-year window is the NSCEB April 2025 action plan. Do not present '
         'any of these as evidence about our own system.',
         'Confirm the AISI capability figure against the exact published evaluation before presenting.',
         'Problem & Real-World Impact (25); Novelty and Importance of AI (25)',
         ['aisi', 'stack', 'nsceb_window', 'nsceb'])


def slide_03(p):
    s = page(p, 'The system / high-level')
    heading(s, 'A claim graph aims the compute.\nA floor, then a person, decides.', size=34)
    stages = [('01', 'Read', 'Open-access full text becomes typed claim rows.'),
              ('02', 'Connect', 'Missing edges between hubs become questions.'),
              ('03', 'Execute', 'Agents write and run code against real data.'),
              ('04', 'Challenge', 'Typed checks, comparators and recorded artifacts.'),
              ('05', 'Review', 'A named person accepts, with a written note.')]
    for j, (num, title, body) in enumerate(stages):
        xx = .66 + j * 2.46
        dot(s, xx + .10, 3.42, .078, GREEN if j < 4 else AMBER)
        if j < 4:
            line(s, xx + .25, 3.42, xx + 2.36, 3.42, LINE, 2, arrow=True)
        text(s, num, xx, 2.88, 2.15, .3, 13, GREEN if j < 4 else AMBER, font=MONO)
        text(s, title, xx, 3.80, 2.2, .58, 26, PAPER, True)
        text(s, body, xx, 4.60, 2.24, 1.2, 17, MUTED)
    line(s, .6, 5.94, 12.73, 5.94, LINE)
    facts = [('PAPERS → IDENTIFIERS', 'no free text in an identity'),
             ('18 ACTIONS / CHECKPOINT', 'the parent allocates the next round'),
             ('2,880 ACTIONS / TREE', 'one frozen budget, counted in actions'),
             ('MASTER GRAPH', 'never entered without a person')]
    for j, (a, b) in enumerate(facts):
        x = .62 + j * 3.09
        text(s, a, x, 6.08, 3.0, .26, 10.5, GREEN, True, MONO)
        text(s, b, x, 6.38, 3.0, .32, 13.5, MUTED)
    label(s, 'IMPLEMENTED · Source-linked claims, recursive sessions, soundness floor and human gate all run today.',
          y=6.86)
    note(s, 'A claim graph aims the compute. A floor, then a person, decides.',
         'This is the whole loop in one view. Papers become source-linked claim rows whose identity is four resolved '
         'identifiers. Missing edges between well-studied hubs become questions. Agent sessions write and execute code '
         'against real data, one action at a time. Typed checks in code screen every reported result, and a scientist '
         'reviews what survives. The engineering is the orchestration around that: recursive sessions, action budgets, '
         'durable execution and recorded artifacts. Surviving the screens is not biological truth, which is why a '
         'person sits at the end.', 35,
         'Implemented architecture. The falsifier checks reported fields; it does not rerun arbitrary code. Nothing '
         'reaches the master graph without a human decision and a written note.',
         criteria='Technical Execution (50); AI Technical Sophistication (50)',
         sources=['ARCHITECTURE.md', 'docs/runtime.md'])


def slide_04(p):
    s = page(p, 'Knowledge graph / two-view structure')
    heading(s, 'Papers become rows a computer can argue with.', y=1.02, size=32)
    parts = [('SUBJECT', 'SMAD4', 'HGNC:6770'), ('PREDICATE', 'increases', 'closed set'),
             ('OBJECT', 'metastasis', 'GO:0033627'), ('ASPECT', 'burden', 'quantity')]
    for j, (k, v, ident) in enumerate(parts):
        x = .62 + j * 2.16
        rect(s, x, 1.86, 1.98, .88, PANEL, LINE)
        text(s, k, x + .14, 1.97, 1.8, .22, 9.5, GREEN, True, MONO)
        text(s, v, x + .14, 2.21, 1.8, .34, 17, PAPER, True)
        text(s, ident, x + .14, 2.50, 1.84, .22, 10, MUTED, font=MONO)
    text(s, 'The model picks from closed menus and quotes the passage. Code grounds every name against fifteen owner '
            'vocabularies; anything ungroundable becomes a counted deferral row.',
         9.34, 1.90, 3.4, .84, 12, MUTED)
    line(s, .6, 2.96, 12.73, 2.96, LINE)

    text(s, 'FLAVORGRAPH · SCI REP 11:931 (2021)', .62, 3.10, 4.0, .24, 10, MUTED, True, MONO)
    text(s, 'Two views, one embedding', .62, 3.40, 3.7, .38, 19, GREEN, True)
    flow(s, .62, 3.88, 3.66, [
        ('Usage: metapath2vec walks over a graph of 1M recipes — what cooks put together.', 14.5, PAPER),
        ('Meaning: an 881-bit PubChem fingerprint — what an ingredient is.', 14.5, PAPER),
        ('The move: chemistry is not a second score. An auxiliary loss makes the embedding reconstruct the '
         'fingerprint, so it shapes the 94% with none.', 14.5, MUTED)])

    text(s, 'OUR ANALOGUE · litmap/pairing.py', 4.66, 3.10, 4.0, .24, 10, MUTED, True, MONO)
    text(s, 'Co-occurrence + meaning', 4.66, 3.40, 3.8, .38, 19, AMBER, True)
    flow(s, 4.66, 3.88, 3.66, [
        ('Usage: PPMI over entity co-occurrence in claims — what the field has studied together.', 14.5, PAPER),
        ('Meaning: pooled MiniLM vectors of an entity’s claims — what is said about it.', 14.5, PAPER),
        ('One truncated SVD over both, meaning rescaled to the usage norm. High on both, no claim between them = '
         'an untested bridge. It ranks; it never asserts.', 14.5, MUTED)])

    pic(s, PLOTS / 'pairing_ours.png', 8.74, 3.06, 4.0, 3.24)
    label(s, 'MEASURED · Synthetic graph with a known answer, 5 seeds, 25% of edges held out and ranked back against '
             'chance. Not yet measured on the PDAC corpus.', y=6.84)
    note(s, 'Papers become rows a computer can argue with — and two views say where to look.',
         'Ingestion first: a claim is subject, predicate, object and aspect, all resolved identifiers, never free text. '
         'The model picks from closed menus and quotes the passage; code grounds the names against fifteen owner '
         'vocabularies, and anything that will not ground becomes a counted deferral rather than a guess. That is what '
         'lets two labs asserting the same thing merge onto one row and ten citations of one experiment collapse to '
         'one experiment. Then the part we are proudest of, which we did not invent. FlavorGraph built one graph from '
         'a million recipes and a second from shared chemical compounds, and the clever move was to make the embedding '
         'reconstruct the chemistry rather than average it in, so chemistry shapes the ninety-four percent of '
         'ingredients that have none recorded. A literature graph has the same two views: which entities the field '
         'studies together, and what the claims about an entity actually say. We take positive pointwise mutual '
         'information over claim co-occurrence, append a rescaled MiniLM meaning block and factor both at once. A pair '
         'high on both with no claim between them is an untested bridge. The chart is the check: hide a quarter of the '
         'edges and rank them back. The joint view beats usage alone everywhere except the sparsest graph, where '
         'meaning alone wins — and we show that failure rather than hide it.', 45,
         'Implemented in litmap/pairing.py with tests in tests/test_pairing.py. This is the closed-form analogue of '
         'FlavorGraph’s chemical-structure-prediction loss, not a reimplementation: they train skip-gram over '
         'metapath2vec walks with an auxiliary binary cross-entropy on an 881-bit PubChem fingerprint. The measured '
         'panel is a synthetic two-factor graph of 180 entities, five seeds, 25% holdout, rank 24, meaning share 0.25. '
         'Ranking a pair is not evidence about it.',
         'Replace the panel with the PDAC corpus measurement once the built database is reachable '
         '(scripts/untested_bridges.py --evaluate).',
         'AI Technical Sophistication (50); Novelty and Importance of AI (25)',
         ['flavorgraph', 'src/dnhacksbio/litmap/pairing.py', 'presentation/assets/v2/plots/pairing.json'])


def slide_05(p):
    s = page(p, 'Recursive sessions / agent architecture')
    heading(s, 'One action per turn, and instruments\nit has to check itself against.', size=32)
    entries = [('One action, then an observation',
              'The session emits one JSON action. Code executes it and returns the result. No hidden tool loop.'),
             ('Children inherit real instruments',
              'Graph and paper search, dataset lookup, parallel Python, and scoped 3D molecular, binder, tissue and spindle tools.'),
             ('Structure enters as an embedding',
              'Geometry is consumed as vectors beside the claim graph. The render exists so the agent, and a person, can look.'),
             ('Nothing is trusted on sight',
              'Every experiment prints one typed RESULT line. Code screens it; the kill lands on the agent’s memory row.')]
    items(s, .62, 2.38, 5.8, entries, tsize=17, bsize=13.5, gap=.24)
    arch_art.session_tree(s, 6.98, 2.34, 5.74, 3.10)
    text(s, 'Every 18 actions the worker stops and files a checkpoint report. The parent reads it and continues, '
            'forks, finishes or prunes. Nothing forks itself; all descendants share one frozen budget.',
         7.0, 5.66, 5.72, .8, 14, MUTED)
    label(s, 'FROZEN SUBTREE CONTRACT · depth 6 · 72 descendant slots · 96 actions per node · 2,880 across the tree.',
          y=6.62)
    note(s, 'One action per turn, and instruments it has to check itself against.',
         'The agent is a scientist on a leash we can inspect. Each turn it emits exactly one action, our code executes '
         'it, and the observation comes back. Its ideas and dead ends are rows in the same database as the graph, so '
         'the frontier is a query rather than a growing prompt. Children get the real instruments: the graph, the '
         'papers, dataset search, parallel Python, and scoped three-dimensional tools for molecular geometry, binders, '
         'tissue simulation and spindle mechanics. Structure enters the reasoning as an embedding alongside the claim '
         'graph; we added the rendering so the agent can look at a scene and a person can check the same thing. '
         'Looking is never the evidence: the agent counterchecks what it saw against canonical coordinates in code, '
         'and every experiment has to print one strictly typed result line that our screens can judge. Every eighteen '
         'actions it stops and reports upward, and the parent decides whether that line continues at all.', 40,
         'Implemented in explorer/explorer.py, control.py, budget.py, lineage.py; instruments in binder/, tissue/, '
         'spindle/ and the inhibitor workflow. The parent controller is an LLM call; its allocation quality has not '
         'been benchmarked against random or depth-first allocation. The three-seed docking recovery benchmark did '
         'not pass, and that failure stays in the record.',
         criteria='Technical Execution (50); AI Technical Sophistication (50)',
         sources=['ARCHITECTURE.md', 'docs/binder-design.md', 'docs/inhibitor-review/README.md'])


def slide_06(p):
    s = page(p, 'Selection policy / what survives and why')
    heading(s, 'No model decides whether a result is sound.', y=1.02, size=32)
    kicker(s, 'Three gates, in this order: a floor written in code, evidence that stays valid whenever you look, '
              'and an allocator that would rather stay silent than guess.', y=1.90, size=18)

    text(s, '01 · THE FLOOR', .62, 2.70, 3.8, .26, 10.5, GREEN, True, MONO)
    line(s, .62, 3.00, 4.34, 3.00, GREEN, 1.5)
    kills = [('no-effect', 'effect not finite'), ('too-few-units', 'fewer than 8 units'),
             ('malformed-p', 'p outside (0, 1]'), ('direction-wrong', 'sign disagrees with the prediction'),
             ('not-significant', 'p above 0.05'), ('not-robust', 'leave-one-group-out failed')]
    for j, (slug, why) in enumerate(kills):
        yy = 3.14 + j * .50
        text(s, slug, .62, yy, 1.82, .24, 12, AMBER, True, MONO)
        text(s, why, 2.48, yy, 1.92, .48, 12, PAPER)
    text(s, 'No minimum-effect gate, deliberately: a constant against incommensurable quantities is not a comparison.',
         .62, 6.28, 3.8, .5, 12, MUTED)

    text(s, '02 · THE EVIDENCE', 4.78, 2.70, 3.8, .26, 10.5, GREEN, True, MONO)
    line(s, 4.78, 3.00, 8.5, 3.00, GREEN, 1.5)
    text(s, 'qₜ = 1 + tanh(dₜ)     Eₜ = Eₜ₋₁ × qₜ', 4.78, 3.14, 3.8, .28, 12.5, GREEN, True, MONO)
    flow(s, 4.78, 3.50, 3.68, [
        ('A bettor, not a classifier. The payoff is bounded and odd: swap the two groups and the score negates, so '
         'under the null the expected payoff is exactly one.', 13.5, PAPER),
        ('Ville’s inequality caps the chance wealth ever exceeds 1/α at α, so the agent may peek after every batch.',
         13.5, MUTED)], gap=.20)
    for j, (v, t2, c) in enumerate([('≤5.00%', 'Ville bound', MUTED), ('1.12%', 'measured ever-crossing', AMBER),
                                    ('100%', 'cheating critic caught', GREEN)]):
        yy = 5.72 + j * .40
        text(s, v, 4.78, yy, 1.2, .28, 14, c, True, MONO)
        text(s, t2, 6.06, yy, 2.5, .28, 13.5, PAPER)

    text(s, '03 · THE ALLOCATOR', 8.94, 2.70, 3.8, .26, 10.5, GREEN, True, MONO)
    line(s, 8.94, 3.00, 12.72, 3.00, GREEN, 1.5)
    alloc = [('Every branch is an episode',
              'A checkpoint report and its evidence trail, enrolled under a frozen policy and budget.'),
             ('Trained on observed outcomes',
              'Did continuing this line produce a verified, non-duplicate finding inside budget?'),
             ('Silence beats a guess',
              'Below 116 independent episodes it returns no threshold at all.'),
             ('Review is never a label',
              'Human accept and reject decisions are excluded, so it cannot flatter the reviewer.')]
    for j, (a, bd) in enumerate(alloc):
        yy = 3.14 + j * .98
        text(s, a, 8.94, yy, 3.8, .26, 14.5, AMBER, True)
        text(s, bd, 8.94, yy + .28, 3.78, .66, 12.5, MUTED)
    label(s, 'IMPLEMENTED · falsifier.py thresholds and slugs. The null audit is a standalone synthetic diagnostic; '
             'branch monitoring is observation-only.', y=6.92)
    note(s, 'No model decides whether a result is sound.',
         'Three gates decide what survives, and none of them is a language model. First the floor: every experiment '
         'prints one strictly typed result line, and six checks run in a fixed order in code — a finite effect, at '
         'least eight independent units, a p-value inside zero to one, the direction declared before the result, '
         'significance, and a leave-one-group-out robustness check. Each failure has a named slug and goes straight '
         'back onto the agent’s memory. Notice what is missing: no minimum effect size, because one constant compared '
         'against incommensurable quantities is not a comparison. Second, the evidence statistic is a bet, not a '
         'score: bounded and odd, so under the null the expected payoff is exactly one, and Ville’s inequality caps '
         'the chance of ever crossing the threshold at five percent no matter how often we peek. Ten thousand null '
         'runs measured one-point-one-two percent, and a critic we deliberately built to cheat was caught in all ten '
         'thousand. Third, allocation. Today a parent model decides; the branch monitor turns that into a statistic '
         'fitted on completed subtrees, calibrated prospectively on independent episodes, and below its episode floor '
         'it refuses to return a threshold at all.', 45,
         'Falsifier constants verbatim: MIN_GROUP 8, P_PERM_CLEAR_NULL 0.05, malformed-result enforced by the '
         'ToolResult schema before the floor. Two gaps to concede if pressed: the permutation p is required of the '
         'agent but not re-derived by the falsifier, and MIN_GROUP is checked against a single scalar, so an '
         'eight-total experiment passes a contract that states eight per group. Null-audit numbers are from the '
         'standalone learned e-value diagnostic, not a product-wide error rate. Branch monitoring is implemented and '
         'observation-only; no live calibrated pruning.',
         'Fix the per-group versus total n_units mismatch in falsifier.py, then update this slide.',
         'Reliability, Evaluation & Trustworthiness (25); AI Technical Sophistication (50)',
         ['davt', 'src/dnhacksbio/falsifier.py', 'research/learned-evalue-validation/expanded-null.json',
          'docs/branch-monitoring.md'])


def slide_07(p):
    s = page(p, 'Backtest / frozen corpus')
    heading(s, 'Freeze the literature, then rerun\nthe loop against the past.', size=32)
    kicker(s, 'The only honest way to ask whether the aim is real: give it what was known in 2025, and see whether it '
              'reaches what was published in 2026.', y=2.44, size=18)
    entries7 = [('Literature frozen at 31 December 2025',
                 '160 open-access papers, 3,493 claims. Every paper dated by its earliest Europe PMC or preprint record, so a late preprint cannot slip in.'),
                ('The data is frozen too',
                 'DepMap 24Q4 gene-effect matrix, 1,178 cell lines by 17,916 genes, released December 2024, before the target preprint existed.'),
                ('The answer is absent, not hidden',
                 'No pre-2026 paper links the gene to the centriole. It was verified absent, not down-ranked.')]
    items(s, .62, 3.10, 5.86, entries7, tsize=18, bsize=14, gap=.26)
    rect(s, 6.96, 3.10, 5.78, 2.88, PANEL, LINE)
    text(s, 'TWO CONTROLS ON WHAT IT COULD KNOW', 7.22, 3.28, 5.2, .26, 10.5, AMBER, True, MONO)
    text(s, 'RECALLED: NO', 7.22, 3.58, 5.3, .44, 22, PAPER, True)
    text(s, 'The bare model, no corpus and no tools, describes the gene only through PKA and NF-κB signalling and '
            'will not confirm a centriole role. The same harness recalls a pre-cutoff control finding.',
         7.22, 4.08, 5.24, .9, 14, MUTED)
    text(s, 'And the goal named a region, never a gene: find a gene annotated for an unrelated role whose partners '
            'are enriched in the inner scaffold.', 7.22, 5.14, 5.24, .7, 14, PAPER)
    text(s, 'A frozen corpus bounds the evidence, never what a pretrained model already knew. That is why the recall '
            'ablation is on this slide.', 7.06, 6.20, 5.6, .5, 13, AMBER)
    note(s, 'Freeze the literature, then rerun the loop against the past.',
         'Here is how we test whether the aim is real rather than plausible. We froze a literature corpus at the end '
         'of 2025, dating every paper by its earliest record so that no late preprint slips in, and we froze the '
         'dependency data at a December 2024 release. The finding we were hunting for was verified absent from the '
         'corpus: no pre-2026 paper connects that gene to the centriole. Then two controls on what the model itself '
         'could know. The bare model, with no corpus and no tools, will not confirm the role, while the same harness '
         'recalls a pre-cutoff control finding perfectly. And the goal we gave the agent named a structural region, '
         'never a gene. A frozen corpus bounds the evidence and never the pretraining, which is exactly why the '
         'ablation is on the slide rather than in a footnote.', 35,
         'Corpus and freeze from MANIFEST.json: target AKIP1 to centriole inner scaffold, freeze 2025-12-31, 160 '
         'papers, 3,493 claims, 45 reference seeds; the write-up quotes 3,478 claims for the same build, so cite the '
         'manifest. DepMap 24Q4, 1,178 lines by 17,916 genes. Recall ablations: ablation_akip1_recall.py returns '
         'recalled: no; ablation_gametolog_recall.py returns recalled: yes on a pre-cutoff finding. The tier-2 '
         'external novelty and date check was OFF in this pass.',
         'Rerun the tier-2 novelty check and record it beside the ablations before presenting to a technical judge.',
         'Reliability, Evaluation & Trustworthiness (25); Technical Execution (50)',
         ['ARCHITECTURE.md', 'demo/pdac/README.md'])


def slide_08(p, run=None):
    s = page(p, 'Backtest / the result')
    heading(s, 'It proposed a centriole component the corpus did not contain.', y=1.02, size=30)
    counts = [('83', 'experiments run'), ('2', 'submitted to verification'),
              ('2', 'passed the soundness floor'), ('1', 'survived the rigor audit')]
    for j, (v, t2) in enumerate(counts):
        x = .62 + j * 3.09
        text(s, v, x, 1.94, 2.9, .8, 36, GREEN if j < 3 else AMBER, True)
        text(s, t2, x, 2.78, 2.94, .46, 14.5, MUTED)
    line(s, .6, 3.34, 12.73, 3.34, LINE)
    text(s, 'THE SURVIVING CANDIDATE', .62, 3.48, 5.9, .26, 10.5, GREEN, True, MONO)
    text(s, 'AKIP1 is a component of the centriole inner scaffold', .62, 3.76, 5.9, .8, 21, PAPER, True)
    text(s, '3 of 6 inner-scaffold seed genes sit in its top-25 co-essential partners. Empirical p = 6.7e-4 against '
            '3,000 random genes, 1,178 cell lines, and it held across wider seed sets and a stricter top-15 cutoff.',
         .62, 4.66, 5.86, .8, 14, PAPER)
    text(s, 'DETERMINISTIC CROSS-CHECK, OUTSIDE THE ENGINE', .62, 5.72, 5.9, .26, 10.5, MUTED, True, MONO)
    text(s, 'Rank #1 of ~17,900 non-module genes · p = 6.2e-10', .62, 6.00, 5.9, .34, 16, GREEN, True)
    text(s, 'ENTRY 61 · RUN akip1main · NO GENE NAMED IN THE GOAL', .62, 6.36, 5.9, .28, 10.5, MUTED, font=MONO)
    rect(s, 6.96, 3.48, 5.78, 2.52, PANEL, LINE)
    text(s, 'bioRxiv · PUBLISHED 7 JUNE 2026', 7.22, 3.64, 5.24, .26, 10.5, AMBER, True, MONO)
    text(s, 'AKIP1 is an inner scaffold component required for centriole integrity', 7.22, 3.94, 5.24, .8, 17, PAPER, True)
    text(s, 'doi:10.64898/2026.06.03.729831', 7.22, 4.86, 5.24, .3, 12, MUTED, font=MONO)
    text(s, 'Corpus frozen 2025-12-31  →  model cutoff January 2026  →  preprint 2026-06-07. The paper was published '
            'after both, by a group that never saw the engine.', 7.22, 5.22, 5.24, .7, 13.5, PAPER)
    text(s, 'The other submission was wrong, and the floor did not catch it. FNTB passed the falsifier and a manual '
            'rank-based audit killed it at 0 of 25 (p = 1.0). The floor validates the statistic the agent reports; it '
            'does not re-derive the enrichment. The human gate did not run in this pass.',
         .62, 6.56, 12.1, .46, 12.5, AMBER)
    note(s, 'It proposed a centriole component the corpus did not contain.',
         'From that frozen evidence the engine ran eighty-three experiments and submitted two. Both passed the '
         'soundness floor. One of them was wrong, and I want to give you that one first: FNTB scored on mean '
         'correlation against a loose centrosome set, passed the falsifier, and was killed by a manual rank-based '
         'audit at zero of twenty-five partners. That is a real gap, and it is the one we are fixing next: the floor '
         'validates the statistic the agent reports, it does not re-derive the enrichment. The surviving candidate is '
         'AKIP1, a gene the literature annotates for signalling, proposed as a structural component of the centriole '
         'inner scaffold. Three of six seed genes sit in its top twenty-five co-essential partners at an empirical p '
         'of six-point-seven times ten to the minus four, and it held when we widened the seed set and tightened the '
         'cutoff. A deterministic cross-check outside the engine puts it first of roughly seventeen thousand nine '
         'hundred genes. The preprint on the right was published in June 2026, after our corpus freeze and after the '
         'reasoning model’s own cutoff. Sound numbers are not truth, and no person has reviewed this at the gate yet. '
         'What it shows is aim.', 45,
         'All figures from AKIP1_rediscovery_result.json, MANIFEST.json and WRITEUP.md in the akip1 corpus directory: '
         'effect 3 of 6 seeds, effect_size 358.32, p_null 6.664e-4, n_units 1178, robust true, explore_entry 61, run '
         'akip1main. Target DOI 10.64898/2026.06.03.729831, preprint 2026-06-07. Deterministic check against a '
         '10-gene inner-scaffold set: rank 1 of ~17,900, 4 of 25, p 6.2e-10. Known gaps, all stated on the slide or '
         'in the write-up: the falsifier does not re-derive rank-based enrichment, the tier-2 novelty check was off, '
         'the promotion gate and human review did not run, and the exclusion list of known centriole genes was leaky, '
         'so the engine repeatedly resurfaced genuine centriole genes before the final phase.',
         'Run the human gate on this candidate and record the reviewer note, then update the fourth count.',
         'Reliability, Evaluation & Trustworthiness (25); Technical Execution (50); Novelty and Importance of AI (25)',
         ['ARCHITECTURE.md', 'skills/co_essentiality/SKILL.md'])


def slide_09(p):
    s = page(p, 'Prepared answers / the objections we expect')
    heading(s, 'The questions we would ask us.', y=1.02, size=32)
    qa = [('“This is retrieval with extra steps.”',
           'Retrieval finds text. The graph computes identity, echo and contradiction — none of those is a lookup.'),
          ('“The model will invent identifiers.”',
           'It cannot write one. It picks from closed menus and code grounds the choice; failures become counted deferral rows.'),
          ('“Sound numbers are not true biology.”',
           'Agreed, and designed in. Nothing enters the master graph without a named person and a written note.'),
          ('“A frozen corpus is not a clean test.”',
           'Correct, so we ablate: the bare model with no corpus will not confirm the finding, and recalls a pre-cutoff control.'),
          ('“Your e-value is a fancy p-value.”',
           'It stays valid at any stopping time, so the agent may peek after every batch. A p-value does not.'),
          ('“Then the learned bettor must win.”',
           'It does not. Permutation beats it on mean shifts and a single feature beats it on variance. We show that.'),
          ('“The branch monitor trains on itself.”',
           'Prospectively, on independent episodes, with human review decisions excluded from labels — and it is observation-only today.'),
          ('“Better models make this obsolete.”',
           'Every guarantee sits outside the model: grounding, one action per turn, the floor, anytime validity, the gate.')]
    for j, (q, a) in enumerate(qa):
        x = .62 + (j % 2) * 6.24
        y = 1.96 + (j // 2) * 1.12
        line(s, x, y, x + 5.9, y, LINE)
        text(s, q, x, y + .12, 5.88, .32, 16.5, GREEN, True)
        text(s, a, x, y + .46, 5.86, .58, 13.5, PAPER)
    text(s, 'Ask us the one on your mind. Every answer has a number behind it, and four of them are places where our '
            'own result is negative: PCA beat our denoiser, the docking benchmark failed, a permutation test beats '
            'our bettor on mean shifts, and the allocator has no live calibration.', .62, 6.30, 12.1, .5, 14, AMBER)
    label(s, 'COVERAGE · Open-access full text only, with a Chao2 capture-recapture completeness estimate and '
             'deferrals counted, not hidden.', y=6.86)
    note(s, 'The questions we would ask us.',
         'We would rather spend the remaining time on whichever of these is bothering you most. Each has a real answer '
         'with numbers behind it, and several are places where our own result is negative: PCA beat our protein '
         'denoiser, the docking recovery benchmark failed, the learned bettor loses to a permutation test on mean '
         'shifts, and the branch monitor has no live calibration yet. We show all four rather than hide them.', 25,
         'Every answer on this slide restates a position defended elsewhere in the deck and verified against the '
         'implementation: grounding in litmap/grounding.py, the floor in falsifier.py, anytime validity in '
         'learned_evalue.py, and observation-only branch monitoring in branch_monitoring/.',
         'Hold this slide in reserve during a timed run; jump to it when a judge raises one of these.',
         'Reliability, Evaluation & Trustworthiness (25); Technical Execution (50)',
         ['ARCHITECTURE.md', 'docs/learned-evalue-process.md', 'docs/branch-monitoring.md'])


def slide_10(p):
    s = page(p, 'Direction / why this compounds')
    heading(s, 'Every guarantee sits outside the model.\nThat makes better models an input, not a threat.', size=30)
    text(s, 'NEXT 90 DAYS', .62, 2.44, 3.8, .26, 10.5, GREEN, True, MONO)
    line(s, .62, 2.74, 4.36, 2.74, GREEN, 1.5)
    plan = [('Corpus at scale', 'from 100 papers to a field-sized collection, with a Chao2 completeness estimate'),
            ('First calibrated threshold', 'enrol the 116 independent episodes calibration needs, then publish one'),
            ('Prospective, not retrospective', 'register candidates now; score them against literature not yet written'),
            ('One bench partner', 'take a single accepted candidate to an actual wet-lab experiment')]
    yy = 2.92
    for a, bd in plan:
        text(s, a, .62, yy, 3.8, .28, 15, PAPER, True)
        text(s, bd, .62, yy + .28, 3.76, .48, 12.5, MUTED)
        yy += .92
    text(s, 'THE ONLY METRIC WE ASK TO BE JUDGED ON', 4.78, 2.44, 7.9, .26, 10.5, AMBER, True, MONO)
    line(s, 4.78, 2.74, 12.72, 2.74, AMBER, 1.5)
    text(s, 'Cost and reviewer-minutes per rerunnable accepted finding.', 4.78, 2.88, 7.9, .38, 20, PAPER, True)
    text(s, 'Not tokens, not papers read, not candidates generated. The denominator counts every branch that failed. '
            'The runtime records action time and SDK usage today; the ratio itself is unmeasured, and it is the first '
            'number a pilot has to produce.', 4.78, 3.36, 7.9, .7, 13.5, MUTED)
    rowdata = [('WHAT IMPROVES', 'WHAT IT BUYS HERE', 'WHAT DOES NOT MOVE'),
               ('Extractor', 'graph fills faster, coverage rises', 'grounding + deferrals'),
               ('Explorer', 'better trajectories to learn from', 'one action per turn'),
               ('Inference cost', 'more actions per dollar', 'the soundness floor'),
               ('Instruments', 'more of biology becomes executable', 'the human gate')]
    for j, (a, b, c) in enumerate(rowdata):
        y = 4.20 + j * .48
        head = j == 0
        line(s, 4.78, y, 12.72, y, LINE, .8)
        text(s, a, 4.82, y + .13, 2.0, .3, 10 if head else 13.5, GREEN if head else PAPER, head, MONO if head else FONT)
        text(s, b, 6.96, y + .13, 3.3, .3, 10 if head else 13, GREEN if head else MUTED, head, MONO if head else FONT)
        text(s, c, 10.42, y + .13, 2.34, .3, 10 if head else 13, GREEN if head else MUTED, head, MONO if head else FONT)
    text(s, 'Three years out the bottleneck is not reading the literature. It is choosing which machine-proposed '
            'experiment deserves a bench, and that is the allocator.', .62, 6.50, 12.1, .32, 12.5, AMBER)
    label(s, 'PROPOSED · No customer, revenue or pricing claim. First deployment is one private workspace inside a '
             'computational research team.', y=6.94)
    note(s, 'Every guarantee sits outside the model.',
         'Three things to close on. In the next ninety days: a corpus at field scale with a completeness estimate '
         'rather than a hand wave, enough independent episodes to publish a calibrated branch-monitor threshold, a '
         'prospective run where we register candidates now and score them against literature that does not exist yet, '
         'and one bench partner to take a single accepted candidate to a real experiment. The metric we ask to be '
         'judged on is cost and reviewer-minutes per independently rerunnable accepted finding, with every failed '
         'branch in the denominator. And on why it compounds: a better extractor fills the graph faster, a better '
         'explorer produces better trajectories for the allocator to learn from, cheaper inference buys more actions '
         'because our budgets are counted in actions rather than hours, and better instruments make more of biology '
         'executable. None of those touches grounding, the action contract, the soundness floor, anytime validity or '
         'the person at the gate. A better model makes a chat assistant better and a research record no more '
         'trustworthy; here capability compounds into throughput instead of confident noise.', 40,
         'Budget contract is action-only: 18 actions per checkpoint, 2,880 research actions shared across a subtree, '
         'depth 6, 72 descendant slots. The cost-per-finding ratio is not yet measured; the runtime records action '
         'time and SDK token usage. No customer, revenue, pricing or cost-saving claim.',
         'Fill the measured cost-per-accepted-finding as soon as one complete investigation has been metered.',
         'Feasibility & Deployment (25); Technical Execution (50)',
         ['ARCHITECTURE.md', 'docs/runtime.md', 'src/dnhacksbio/explorer/budget.py'])


# ----------------------------------------------------------------------------- build

PLACEHOLDER_RUN = {
    'proposed': '[ X ]', 'passed': '[ X ]', 'gate': '[ X ]', 'matched': '1',
    'candidate': '[ subject → predicate → object · aspect ]',
    'provenance': 'PROPOSED AT ACTION [ X ] OF [ X ] · BRANCH [ X ] · ACCEPTED BY [ NAME ]',
    'journal': '[ JOURNAL ] · PUBLISHED AFTER OUR CUTOFF',
    'paper': '[ Paper title — the independently published finding ]',
    'authors': '[ AUTHORS ] · [ INSTITUTION ] · doi:[ DOI ]',
    'match': '[ The one sentence in this paper that matches our candidate ]',
    'status': 'RUN PENDING AUDIT · Bracketed values are placeholders. Do not present this slide until the run and the '
              'paper match are audited.',
}


def build(run=None):
    run = run or PLACEHOLDER_RUN
    p = new_prs()
    slide_01(p)
    slide_02(p)
    slide_03(p)
    slide_04(p)
    slide_05(p)
    slide_06(p)
    slide_07(p)
    slide_08(p, run)
    slide_09(p)
    slide_10(p)
    p.save(OUTFILE)
    print(f'wrote {OUTFILE} · {len(p.slides._sldIdLst)} slides')


if __name__ == '__main__':
    build()
