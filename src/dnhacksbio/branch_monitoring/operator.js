// Operator-only origin; token lives in memory, never a URL, localStorage or research API.
let token = '', episodes = [], selected = null;
const el = id => document.getElementById(id);
const text = (tag, value, parent) => {const n = document.createElement(tag); n.textContent = value; parent.append(n); return n;};
async function api(path, body) {
  const r = await fetch(path, {method: body ? 'POST' : 'GET', headers: {'Authorization':'Bearer '+token, ...(body ? {'Content-Type':'application/json'} : {})}, ...(body ? {body:JSON.stringify(body)} : {})});
  if (!r.ok) throw new Error(r.status === 401 ? 'Operator authorization required.' : 'Record unavailable.');
  return r.json();
}
const number = x => x == null ? 'Unavailable' : Number(x).toPrecision(4);
async function refresh() {
  try {
    episodes = (await api('/api/episodes')).episodes;
    el('workspace').hidden = false; el('login').hidden = true;
    el('status').textContent = episodes.length ? `${episodes.length} enrolled subtree episodes. Observation-only.` : 'No episodes enrolled. Scoring has not started.';
    el('tree').replaceChildren();
    for (const e of episodes.sort((a,b)=>a.run_id.localeCompare(b.run_id))) {
      const last = e.history.at(-1);
      const b = text('button', `${e.run_id} · ${number(last?.monitor_statistic)} · ${e.history.length} checkpoints · ${e.status}`, el('tree'));
      b.setAttribute('aria-pressed', String(selected === e.episode_id));
      b.style.marginInlineStart = Math.min(40, e.run_id.split('~').length * 8 - 8) + 'px';
      b.onclick = () => choose(e);
    }
    if (selected) {const e = episodes.find(x=>x.episode_id===selected); if(e) await choose(e);}
  } catch (err) { el('status').textContent = err.message; }
}
function svg(tag, attrs, content) {
  const n=document.createElementNS('http://www.w3.org/2000/svg',tag);
  for(const [k,v] of Object.entries(attrs)) n.setAttribute(k,String(v));
  if(content != null) n.textContent=content;
  el('chart').append(n); return n;
}
function chart(history) {
  el('chart').replaceChildren();
  const points=history.filter(h=>h.monitor_statistic!=null && h.monitor_statistic>0);
  if(!points.length){svg('text',{x:40,y:100},'Monitor statistic unavailable · no fitted reading');return;}
  const thresholds=history.filter(h=>h.threshold!=null && h.threshold>0).map(h=>Math.log10(h.threshold));
  const logs=points.map(h=>Math.log10(h.monitor_statistic));
  const lo=Math.min(...logs,...thresholds)-.25, hi=Math.max(...logs,...thresholds)+.25;
  const last=Math.max(...history.map(h=>h.checkpoint));
  const x=k=> last===1 ? 355 : 65+(k-1)/(last-1)*610;
  const y=v=>285-(v-lo)/(hi-lo)*245;
  svg('line',{x1:65,x2:675,y1:285,y2:285});svg('line',{x1:65,x2:65,y1:40,y2:285});
  svg('text',{x:285,y:325},'Checkpoint');svg('text',{x:12,y:23},'Monitor statistic (log scale)');
  for(let i=0;i<4;i++){const v=lo+(hi-lo)*i/3;svg('text',{x:6,y:y(v)},(10**v).toPrecision(2));}
  const threshold=history.at(-1)?.threshold;
  if(threshold!=null && threshold>0){svg('line',{x1:65,x2:675,y1:y(Math.log10(threshold)),y2:y(Math.log10(threshold)),class:'threshold'});svg('text',{x:70,y:y(Math.log10(threshold))-8},'Calibrated proposed-stop threshold');}
  for(const h of points){const dot=svg('circle',{cx:x(h.checkpoint),cy:y(Math.log10(h.monitor_statistic)),r:5}); const title=document.createElementNS(dot.namespaceURI,'title');title.textContent=`Checkpoint ${h.checkpoint}: ${number(h.monitor_statistic)}, cost ${h.cumulative_cost}`;dot.append(title);svg('text',{x:x(h.checkpoint)-4,y:305},h.checkpoint);}
}
async function choose(e) {
  selected=e.episode_id; el('objective').textContent=e.objective;
  el('summary').textContent=`${e.run_id} · ${e.status} · ${e.history.length} checkpoints · Fixed horizon ${e.protocol.terminal_budget} ${e.protocol.budget_unit}. ${e.history.at(-1)?.threshold == null ? 'Uncalibrated; no stopping threshold.' : 'Calibrated replay; proposed stops are not enforced.'}`;
  chart(e.history);el('history').replaceChildren();
  for(const h of e.history){const tr=document.createElement('tr'); for(const v of [h.checkpoint,h.cumulative_cost,number(h.monitor_statistic),h.error || (h.would_stop ? 'Proposed stop (observation only)' : 'Report')]) text('td',v,tr);el('history').append(tr);}
  el('reviews').replaceChildren();
  try {
    const rows=(await api('/api/reviews/'+encodeURIComponent(e.run_id))).reviews;
    if(!rows.length)text('p','No associated experimental evidence.',el('reviews'));
    for(const r of rows){const box=text('section','',el('reviews'));box.className='review';text('h4',r.association.finding_id,box);text('p',`${r.association.method_id} · ${r.decision || 'Awaiting human review'}`,box);text('pre',JSON.stringify(r.association.evidence,null,2),box);text('p',`Null: ${r.association.null}. Validity policy: ${r.association.validity_policy}`,box);text('pre',JSON.stringify(r.association.provenance,null,2),box);
      if(r.decision){text('p',r.note,box);continue;}
      const form=text('form','',box), label=text('label','Review decision',form), select=document.createElement('select');label.append(select);for(const s of ['accepted','rejected','unavailable']){const o=text('option',s,select);o.value=s;}
      const noteLabel=text('label','Written justification',form),note=document.createElement('textarea');note.required=true;noteLabel.append(note);const button=text('button','Save private review',form);button.type='submit';
      form.onsubmit=async ev=>{ev.preventDefault();try{await api('/api/review',{review_id:r.review_id,decision:select.value,note:note.value});await choose(e);}catch(err){el('status').textContent=err.message;}};
    }
  }catch(err){text('p',err.message,el('reviews'));}
}
el('login').onsubmit=ev=>{ev.preventDefault();token=el('token').value;el('token').value='';refresh();};
el('refresh').onclick=refresh;
