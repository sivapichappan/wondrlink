#!/usr/bin/env python3
"""Browser preview of the implemented Direction-E trial results screen, using
REAL live data from the pipeline. Radius control + widen callout are interactive
(client-side filtering), exactly like the React Native screen.

Run: python3 scripts/mockup_trials.py  ->  /tmp/trials_mockup.html
"""
import json
import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, 'lib'))

from lib.clinical_trials import search_trials_for_patient, count_trials_for_radii

PATIENT = {
    "cancer_slug": "colorectal", "cancer_type": "colorectal cancer",
    "stage": "Stage IV", "zip_code": "10029", "biomarkers": "MSI-H",
    "age": 58, "gender": "female",
}

pool = search_trials_for_patient(PATIENT, max_results=12, radius_miles=None)["trials"]
counts = count_trials_for_radii(PATIENT)

trials = []
for t in pool:
    site = (t.get("locations") or [{}])[0]
    trials.append({
        "nct_id": t["nct_id"], "match": t["relevance"]["band"], "likely_eligible": t["likely_eligible"],
        "warnings": t["relevance"]["warnings"], "plain_summary": t["plain_summary"],
        "interventions": [i["name"] for i in t.get("interventions", [])],
        "eligibility": t.get("eligibility", {}), "enrollment_count": t.get("enrollment_count"),
        "nearest_site": {"facility": site.get("facility", ""), "city": site.get("city", ""), "state": site.get("state", "")},
        "distance": t.get("nearest_distance_miles"), "url": t["url"],
    })

DATA = {"trials": trials, "counts": counts}

HTML = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>WondrChat — Trial Results (Direction E, live data)</title>
<style>
  :root{--primary:#1F5D4F;--primaryPressed:#17463B;--tealSoft:#CFE0D9;--tint:#EDF2EF;
    --surfaceMuted:#F7F7F5;--surface:#FFFFFF;--textPrimary:#0F201C;--textSecondary:#475554;
    --textMuted:#6F7B7A;--border:#E1E4E1;--warnText:#92400E;--warnBg:#FEF3C7;}
  *{box-sizing:border-box;}
  body{margin:0;background:#ECEBE8;font-family:-apple-system,'Segoe UI',system-ui,sans-serif;color:var(--textPrimary);padding:24px 12px;}
  .phone{width:390px;max-width:100%;margin:0 auto;background:var(--surfaceMuted);border:1px solid var(--border);border-radius:28px;overflow:hidden;box-shadow:0 16px 40px rgba(15,32,28,.10);}
  .hd{padding:22px 16px 0;display:flex;flex-direction:column;gap:3px;}
  .hd h1{font-size:18px;font-weight:700;margin:0;}
  .hd p{font-size:12.5px;color:var(--textMuted);margin:0;}
  .filter{padding:14px 16px;border-bottom:1px solid var(--border);display:flex;flex-direction:column;gap:10px;}
  .flabel{font-size:12px;font-weight:600;color:var(--textSecondary);}
  .seg{display:flex;gap:2px;background:var(--tint);border-radius:12px;padding:3px;}
  .seg button{flex:1;min-height:44px;border:1px solid transparent;border-radius:10px;background:transparent;color:var(--textMuted);font-weight:500;font-size:12px;font-family:inherit;cursor:pointer;}
  .seg button.active{background:var(--surface);border-color:var(--border);color:var(--primary);font-weight:700;box-shadow:0 1px 2px rgba(15,32,28,.10);}
  .summary{font-size:13.5px;}
  .summary b{font-weight:700;color:var(--primary);}
  .subline{font-size:12px;color:var(--textMuted);margin-top:2px;}
  .list{padding:16px 16px 26px;display:flex;flex-direction:column;gap:14px;}
  .card{border:1px solid var(--border);border-radius:16px;background:var(--surface);overflow:hidden;}
  .band{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:9px 16px;}
  .band .t{font-size:11.5px;font-weight:700;letter-spacing:.5px;text-transform:uppercase;}
  .band .e{font-size:12px;font-weight:600;}
  .body{padding:14px 16px 16px;display:flex;flex-direction:column;gap:12px;}
  .plain{font-size:15.5px;font-weight:600;line-height:1.45;}
  .warn{display:flex;gap:9px;align-items:flex-start;background:var(--warnBg);border-radius:10px;padding:9px 10px;}
  .warn .ic{width:18px;height:18px;border-radius:50%;background:var(--warnText);color:var(--warnBg);font-size:11px;font-weight:700;display:flex;align-items:center;justify-content:center;flex:none;}
  .warn .tx{font-size:13px;line-height:1.45;color:var(--warnText);}
  .facts{background:var(--surfaceMuted);border-radius:12px;padding:12px 14px;display:flex;flex-direction:column;gap:8px;}
  .frow{display:flex;gap:10px;}
  .fkey{width:92px;flex:none;font-size:11.5px;font-weight:600;color:var(--textMuted);}
  .fval{flex:1;font-size:12.5px;line-height:1.4;color:var(--textPrimary);}
  .actions{display:flex;gap:8px;}
  .view{flex:1;min-height:48px;display:flex;align-items:center;justify-content:center;background:var(--primary);color:#fff;border-radius:12px;font-size:13.5px;font-weight:600;text-decoration:none;text-align:center;padding:0 10px;}
  .save{flex:none;min-width:86px;min-height:48px;border-radius:12px;border:1.5px solid var(--primary);background:var(--surface);color:var(--primary);font-size:13.5px;font-weight:600;font-family:inherit;cursor:pointer;}
  .save.saved{background:var(--tealSoft);border-color:var(--tealSoft);}
  .widen{border:1.5px dashed var(--tealSoft);background:var(--tint);border-radius:14px;padding:14px;display:flex;flex-direction:column;gap:10px;align-items:flex-start;}
  .widen .tx{font-size:13px;line-height:1.5;color:var(--textSecondary);}
  .widen button{min-height:44px;padding:0 16px;border-radius:10px;border:1.5px solid var(--primary);background:var(--surface);color:var(--primary);font-size:13px;font-weight:600;font-family:inherit;cursor:pointer;}
  .note{max-width:390px;margin:14px auto 0;color:#5a6360;font-size:12px;text-align:center;line-height:1.5;}
</style></head>
<body>
<div class="phone">
  <div class="hd"><h1>Studies that match you</h1><p>Matched to your health profile · strongest first</p></div>
  <div class="filter">
    <div class="flabel">How far can you travel?</div>
    <div class="seg" id="seg"></div>
    <div><div class="summary" id="summary"></div><div class="subline" id="subline"></div></div>
  </div>
  <div class="list" id="list"></div>
</div>
<p class="note">Direction E rendered from <b>live ClinicalTrials.gov data</b> (Stage IV colorectal, MSI-H, NYC). Tap the radius control — filtering + the widen callout are live, exactly like the app.</p>
<script>
const DATA=__DATA__;
const TIER={strong:{bg:'#CFE0D9',fg:'#1F5D4F',l:'Strong match'},moderate:{bg:'#FEF3C7',fg:'#92400E',l:'Moderate match'},general:{bg:'#EDF2EF',fg:'#475554',l:'General match'}};
const RADII=[[25,'25 mi','within 25 miles'],[50,'50 mi','within 50 miles'],[100,'100 mi','within 100 miles'],['nationwide','Nationwide','across the U.S.']];
let radius=100; const saved={};
function esc(s){return (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
function tc(s){return s?s.charAt(0).toUpperCase()+s.slice(1).toLowerCase():'';}
function who(e){if(!e)return 'See study for details';const mn=(e.min_age||'').replace(/\s*Years?/i,'').trim(),mx=(e.max_age||'').replace(/\s*Years?/i,'').trim();
  let a=''; if(mn&&mx)a='Ages '+mn+'–'+mx; else if(mn)a='Ages '+mn+'+'; else if(mx)a='Up to '+mx;
  const sx=(e.sex||'').toUpperCase(); const sl=sx==='ALL'?'All sexes':sx?tc(sx)+' only':''; return [a,sl].filter(Boolean).join(' · ')||'See study for details';}
function pwarn(w){let o=w.replace(/;\s*patient is/i,' — your profile is'); if(!/[.!?]$/.test(o))o+='.'; return o;}
function within(t){return radius==='nationwide'||t.distance==null||t.distance<=radius;}
function facts(t){
  const drugs=(t.interventions||[]).filter(Boolean);
  const treat=drugs.length?drugs.slice(0,3).join(' + ')+(drugs.length>3?' + others':''):'See study for details';
  const s=t.nearest_site||{}; let near='Location not listed';
  if(s.facility||s.city){const f=(s.facility||'').split(' / ')[0]; const cs=[s.city,s.state].filter(Boolean).join(', ');
    const d=t.distance; const dl=d==null?'':d===0?' (~0 mi)':' ('+d+' mi)'; near=[f,cs].filter(Boolean).join(' · ')+dl;}
  return [['Treatment',treat],['Who can join',who(t.eligibility)],['Study size',t.enrollment_count!=null?t.enrollment_count+' participants':'Not specified'],['Nearest site',near],['Study ID',t.nct_id]];
}
function card(t){
  const tier=TIER[t.match]||TIER.general; const elig=t.likely_eligible===false?'Check criteria first':'Likely eligible';
  const w=(t.warnings||[])[0]; const isS=!!saved[t.nct_id];
  let h='<div class="card"><div class="band" style="background:'+tier.bg+'"><span class="t" style="color:'+tier.fg+'">'+tier.l+'</span><span class="e" style="color:'+tier.fg+'">'+elig+'</span></div>';
  h+='<div class="body"><div class="plain">'+esc(t.plain_summary)+'</div>';
  if(w)h+='<div class="warn"><span class="ic">!</span><span class="tx">'+esc(pwarn(w))+'</span></div>';
  h+='<div class="facts">'+facts(t).map(([k,v])=>'<div class="frow"><span class="fkey">'+k+'</span><span class="fval">'+esc(v)+'</span></div>').join('')+'</div>';
  h+='<div class="actions"><a class="view" href="'+esc(t.url)+'" target="_blank">View on ClinicalTrials.gov</a>';
  h+='<button class="save'+(isS?' saved':'')+'" onclick="tog(\''+t.nct_id+'\')">'+(isS?'Saved ✓':'Save')+'</button></div></div></div>';
  return h;
}
function widen(hidden){
  const ds=hidden.map(t=>t.distance).filter(d=>d!=null).sort((a,b)=>a-b).map(d=>d+' mi');
  const j=ds.length===1?ds[0]:ds.length===2?ds[0]+' and '+ds[1]:ds.slice(0,2).join(', ')+', and others';
  const mx=hidden.map(t=>t.distance).filter(d=>d!=null).reduce((a,b)=>Math.max(a,b),0);
  const tgt=mx<=50?50:mx<=100?100:'nationwide'; const lbl=tgt==='nationwide'?'Search nationwide':'Widen to '+tgt+' miles'; const n=hidden.length;
  return '<div class="widen"><div class="tx">'+n+' of your top '+(n===1?'matches is':'matches are')+' outside this range ('+j+' away).</div><button onclick="setR(\''+tgt+'\')">'+lbl+'</button></div>';
}
function tog(id){saved[id]=!saved[id];render();}
function setR(r){radius=(r==='nationwide')?'nationwide':parseInt(r);render();}
function render(){
  const shown=DATA.trials.filter(within);
  const hidden=radius==='nationwide'?[]:DATA.trials.filter(t=>t.distance!=null&&t.distance>radius);
  const meta=RADII.find(r=>String(r[0])===String(radius));
  const cnt=(DATA.counts&&DATA.counts[String(radius)])!=null?DATA.counts[String(radius)]:shown.length;
  document.getElementById('summary').innerHTML='<b>'+cnt+'</b> recruiting trials '+meta[2];
  document.getElementById('subline').textContent=shown.length?('Showing your top '+shown.length+' '+(shown.length===1?'match':'matches')+' · sorted by how well they fit you'):'';
  let html=shown.map(card).join(''); if(hidden.length)html+=widen(hidden);
  if(!shown.length&&!hidden.length)html='<div style="color:#475554;font-size:13px;">No matching trials right now.</div>';
  document.getElementById('list').innerHTML=html;
  document.querySelectorAll('#seg button').forEach(b=>b.classList.toggle('active',String(b.dataset.r)===String(radius)));
}
const seg=document.getElementById('seg');
RADII.forEach(([v,l])=>{const b=document.createElement('button');b.textContent=l;b.dataset.r=v;b.onclick=()=>setR(v);seg.appendChild(b);});
render();
</script></body></html>"""

out = HTML.replace("__DATA__", json.dumps(DATA))
with open("/tmp/trials_mockup.html", "w") as f:
    f.write(out)
print("wrote /tmp/trials_mockup.html | pool:", len(trials), "| counts:", counts)
