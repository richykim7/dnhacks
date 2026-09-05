"""Render the research brief and its illustrative graph interaction, using installed markdown-it."""
from pathlib import Path
from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[2]
source = ROOT / "tasks/research/graph-forecasting/report-source.md"
target = ROOT / "design/graph-forecasting-plan.html"
body = MarkdownIt("commonmark", {"html": False}).enable("table").render(source.read_text())

style = """
:root{--paper:#f4f2e9;--ink:#18312e;--muted:#63766d;--line:#d8dfd3;--green:#16735b;--lime:#d6ef83;--card:#fffef8}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.7 system-ui,sans-serif}
a{color:#146953;text-underline-offset:3px}button{font:inherit;cursor:pointer}button:focus-visible,a:focus-visible{outline:3px solid #328a68;outline-offset:4px}
.mast{max-width:1160px;margin:auto;padding:30px 32px;display:flex;justify-content:space-between;gap:20px;font-size:12px;letter-spacing:.12em;text-transform:uppercase;border-bottom:1px solid var(--line)}
.mark{font-weight:750}.mark:before{content:'✳';font-size:23px;vertical-align:middle;margin-right:10px;color:var(--green)}
.intro{max-width:1100px;margin:62px auto 32px;padding:0 32px}.eyebrow{font-size:12px;letter-spacing:.15em;text-transform:uppercase;color:var(--green);font-weight:650}
.intro h1{font:normal clamp(42px,6vw,80px)/1.03 Georgia,serif;letter-spacing:-.055em;margin:18px 0 22px}.intro p{max-width:650px;font-size:18px;color:var(--muted)}
.instrument{max-width:1100px;margin:32px auto 65px;background:var(--card);border:1px solid var(--line);border-radius:18px;overflow:hidden;box-shadow:0 20px 70px #213b2610}
.instrument-top{padding:18px 25px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;gap:20px;font-size:12px;color:var(--muted)}
.mode{padding:5px 10px;border-radius:30px;border:1px solid var(--line);font-size:11px;letter-spacing:.07em;text-transform:uppercase}
.scene{display:grid;grid-template-columns:1fr 290px;min-height:350px}.graph-wrap{position:relative;border-right:1px solid var(--line);padding:10px}.graph-wrap svg{display:block;width:100%;height:350px}
.scene-text{padding:30px 25px}.scene-text h2{font:normal 29px/1.2 Georgia,serif;letter-spacing:-.025em;margin:12px 0}.scene-text p{font-size:14px;color:var(--muted)}
.legend{display:flex;gap:17px;padding:0 23px 15px;font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.07em}.legend span:before{content:'';display:inline-block;width:19px;border-top:2px solid #53846c;vertical-align:middle;margin-right:7px}.legend span:nth-child(2):before{border-top-style:dashed;border-color:#a5853a}
.controls{display:flex;align-items:center;gap:9px;border-top:1px solid var(--line);padding:16px 22px;flex-wrap:wrap}.controls button{border:1px solid var(--line);background:transparent;color:var(--muted);padding:8px 16px;border-radius:30px;font-size:12px;transition:.2s}.controls button[aria-pressed=true]{background:var(--ink);border-color:var(--ink);color:white}.controls .play{margin-left:auto;color:var(--ink);background:var(--lime);border-color:transparent}
svg .edge{fill:none;stroke:#a9c3b4;stroke-width:1.5;transition:opacity .65s,stroke .65s}svg .node circle{fill:#eef4e8;stroke:#739b80;stroke-width:1.2;transition:fill .65s,stroke .65s}svg .node text{fill:var(--ink);font:12px system-ui,sans-serif}svg .node .sub{font-size:9px;fill:#728875;letter-spacing:.07em}svg .new{opacity:0;transition:opacity .7s}svg .hypothesis{stroke:#af913f;stroke-dasharray:5 5;stroke-width:2.5;opacity:0}svg .halo{fill:#d6ef8330;stroke:#9ebf7350;opacity:0;transition:opacity .6s}
[data-stage='1'] .new,[data-stage='2'] .new,[data-stage='3'] .new{opacity:1}[data-stage='2'] .hypothesis,[data-stage='3'] .hypothesis{opacity:1}[data-stage='1'] .halo,[data-stage='2'] .halo{opacity:1}[data-stage='3'] .hypothesis{stroke:#16735b;stroke-dasharray:none}[data-stage='3'] .future circle{fill:var(--lime);stroke:var(--green)}
.research{max-width:880px;padding:0 32px 90px;margin:auto}.research>h1{font:normal 38px/1.2 Georgia,serif;letter-spacing:-.035em;border-top:1px solid var(--line);padding-top:38px}.research h2{font:normal 30px/1.25 Georgia,serif;margin:56px 0 18px;letter-spacing:-.02em}.research h3{font-size:17px;margin:30px 0 12px}.research p{margin:14px 0}.research li{margin:8px 0}.research table{border-collapse:collapse;width:100%;font-size:13px;margin:24px 0}.research td,.research th{padding:12px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}.research th{background:#e8eedf;font-size:11px;text-transform:uppercase;letter-spacing:.04em}.research code{background:#e7ece0;border-radius:4px;padding:2px 4px;font-size:.86em;overflow-wrap:anywhere}.research strong{font-weight:650}.foot{border-top:1px solid var(--line);padding:25px 32px;text-align:center;color:var(--muted);font-size:12px}
@media(max-width:760px){.mast{padding:20px;letter-spacing:.06em}.intro{margin-top:38px;padding:0 22px}.instrument{margin:25px 15px 40px}.scene{grid-template-columns:1fr}.graph-wrap{border-right:0}.graph-wrap svg{height:auto;min-height:235px}.scene-text{border-top:1px solid var(--line);padding:18px 22px}.scene-text h2{font-size:25px}.scene-text p{margin-bottom:0}.instrument-top{padding:14px 18px}.instrument-top>span:first-child{max-width:100px}.controls{gap:6px;padding:12px}.controls button{padding:7px 11px}.controls .play{margin-left:0}.research{padding:0 22px 50px}.research table{display:block;overflow-x:auto;min-width:0}.research th,.research td{min-width:135px}.research h2{font-size:27px}}
@media(prefers-reduced-motion:reduce){*{transition:none!important;scroll-behavior:auto!important}}@media print{body{background:white;font-size:11pt}.mast,.controls{display:none}.instrument{box-shadow:none;break-inside:avoid}.intro{margin-top:10px}.research h2{break-after:avoid}.research table{font-size:9pt}a{color:inherit}.research{max-width:none}.research>h1{break-before:page}}
"""

scene = """
<header class="mast"><span class="mark">Scientific frontiers</span><span>Research brief · 05 September 2026</span></header>
<section class="intro"><div class="eyebrow">A graph that learns where to look next</div><h1>Forecast the<br>next connection.</h1><p>Build a picture of what science knows. Explore the gaps. Then open the future and see which predictions held up.</p></section>
<section class="instrument" id="instrument" data-stage="0" aria-label="Illustrative graph storyboard">
<div class="instrument-top"><span>BIOLOGY · RESEARCH WORKSPACE</span><span class="mode">Illustrative scene · no measured forecasts</span></div>
<div class="scene"><div class="graph-wrap"><svg viewBox="0 0 680 350" role="img" aria-label="Conceptual biological graph with staged evidence and forecast connections">
<defs><pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r=".6" fill="#ced9c6"/></pattern></defs><rect width="680" height="350" fill="url(#grid)"/>
<ellipse class="halo" cx="264" cy="145" rx="160" ry="110"/><ellipse class="halo" cx="495" cy="215" rx="110" ry="90"/>
<path class="edge" d="M130 160 Q200 70 277 110 M130 160 Q195 265 275 264 M277 110 Q342 133 365 187 M275 264 Q316 224 365 187"/>
<path class="edge new" d="M277 110 Q391 45 486 99 M365 187 Q445 175 508 252 M508 252 Q569 206 576 146"/>
<path class="edge hypothesis" d="M130 160 Q267 348 508 252"/>
<g class="node" transform="translate(130 160)"><circle r="29"/><text y="4" text-anchor="middle">BRAF</text><text class="sub" x="0" y="49" text-anchor="middle">GENE</text></g>
<g class="node" transform="translate(277 110)"><circle r="25"/><text y="4" text-anchor="middle">V600E</text><text class="sub" y="43" text-anchor="middle">VARIANT</text></g>
<g class="node" transform="translate(275 264)"><circle r="7"/><text y="26" text-anchor="middle">Melanoma</text></g>
<g class="node" transform="translate(365 187)"><circle r="8"/><text y="28" text-anchor="middle">Treatment response</text></g>
<g class="node new" transform="translate(486 99)"><circle r="7"/><text y="-19" text-anchor="middle">Signaling pathway</text></g>
<g class="node new future" transform="translate(508 252)"><circle r="12"/><text y="30" text-anchor="middle">Follow-up target</text></g>
<g class="node new" transform="translate(576 146)"><circle r="6"/><text y="-18" text-anchor="middle">New evidence</text></g>
</svg><div class="legend"><span>Evidence</span><span>Forecast</span></div></div>
<div class="scene-text" aria-live="polite"><span class="eyebrow" id="phase">01 / Historical context</span><h2 id="scene-title">A field, as it was.</h2><p id="scene-copy">Begin with a research question and a dated body of evidence. The initial graph shows the relationships available to the investigation.</p></div></div>
<div class="controls" aria-label="Storyboard stages"><button data-step="0" aria-pressed="true">01 Read</button><button data-step="1" aria-pressed="false">02 Connect</button><button data-step="2" aria-pressed="false">03 Forecast</button><button data-step="3" aria-pressed="false">04 Reveal</button><button class="play" id="play">Play sequence ↗</button></div>
</section>
"""

script = """
const states=[
 ['01 / Historical context','A field, as it was.','Begin with a research question and a dated body of evidence. The initial graph shows the relationships available to the investigation.'],
 ['02 / Graph revision','Evidence changes the map.','New sources expand the graph. Branches cover different neighborhoods; their overlap makes the next allocation decision visible.'],
 ['03 / Committed forecast','A connection worth pursuing.','The model consumes the revised graph and commits a proposed connection. Dashed edges preserve the distinction between evidence and prediction.'],
 ['04 / Later evidence','Now open the future.','In the finished demo, later records attach to earlier predictions and every forecast is scored. This illustrative sequence asserts no biological result.']
];
let timer=null,step=0;const root=document.getElementById('instrument'),play=document.getElementById('play');
function show(n){step=n;root.dataset.stage=String(n);document.getElementById('phase').textContent=states[n][0];document.getElementById('scene-title').textContent=states[n][1];document.getElementById('scene-copy').textContent=states[n][2];document.querySelectorAll('[data-step]').forEach(b=>b.setAttribute('aria-pressed',String(Number(b.dataset.step)===n)));}
function stop(){clearInterval(timer);timer=null;play.textContent='Play sequence ↗';}
document.querySelectorAll('[data-step]').forEach(b=>b.addEventListener('click',()=>{stop();show(Number(b.dataset.step));}));
play.addEventListener('click',()=>{if(timer){stop();return;}show(0);play.textContent='Pause sequence';timer=setInterval(()=>{show(step+1);if(step===3)stop();},2400);});
document.addEventListener('visibilitychange',()=>{if(document.hidden)stop();});
const initial=Number(new URLSearchParams(location.search).get('stage'));if(Number.isInteger(initial)&&initial>=0&&initial<4)show(initial);
"""

target.write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Forecast the next edge — research and demo plan</title><style>' + style + '</style></head><body>' + scene + '<main class="research">' + body + '</main><footer class="foot">Planning artifact · public assets verified · predictive advantage remains to be measured</footer><script>' + script + '</script></body></html>')
print(target)
