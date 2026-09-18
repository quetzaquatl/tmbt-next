const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const state={market:"NQ",tf:"1H",source:null,bars:[],models:[],archive:[],outcomes:[],outcomeGroups:[],research:[],researchAutopilot:null,researchSync:null,researchScheduler:null,paper:null,traderNotes:"",selectedModel:null,snapshot:null,tradeReplay:null,mode:"live",pd:{},viewCount:140,offset:0,hover:null,drag:null,lastResearchStates:{},alerts:false,pdOn:true,sessions:true,yZoom:1,futureSpace:0};
const RESEARCH_ALERT_KEY="tmbt_next_research_alerts_v1";
const researchAlertSeen=(()=>{try{const x=JSON.parse(localStorage.getItem(RESEARCH_ALERT_KEY)||"[]");return new Set(Array.isArray(x)?x.slice(-500):[])}catch{return new Set()}})();
let researchAlertsPrimed=false;
function saveResearchAlertSeen(){try{localStorage.setItem(RESEARCH_ALERT_KEY,JSON.stringify([...researchAlertSeen].slice(-500)))}catch{}}
function researchJobKey(j){return String(j?.job_id||j?.id||[j?.created_at_utc,j?.kind,j?.request?.preset].filter(Boolean).join("|")||"")}
const fmt=(v,n=2)=>v===null||v===undefined||v===""?"—":Number(v).toFixed(n);
const esc=s=>String(s??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m]));
const iso=t=>{try{return new Date(typeof t==="number"&&t>1e12?t:Number(t)||t).toLocaleString("de-DE",{day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"})}catch{return"—"}};
function log(s){$("#logs").textContent=`[${new Date().toLocaleTimeString()}] ${s}\n`+$("#logs").textContent.slice(0,5000)}
function toast(s){const e=$("#toast");e.textContent=s;e.classList.add("show");setTimeout(()=>e.classList.remove("show"),2800)}
function dot(id,cl){const el=$(id);if(el)el.className=cl}
function setWorkspaceView(view){
 const v=String(view||"desk");
 document.body.classList.toggle("workspace-page-open",v!=="desk");
 document.body.dataset.workspaceView=v;
 document.querySelectorAll(".workspace-nav [data-workspace-view]").forEach(b=>b.classList.toggle("active",b.dataset.workspaceView===v));
 document.querySelectorAll(".workspace-page").forEach(p=>p.classList.toggle("active",p.dataset.workspacePage===v));
 if(v==="research"||v==="review")pollResearch();
 if(v==="paper")pollPaper();
 if(v==="archive")refreshArchive();
 if(v==="outcomes")refreshOutcomes();
 if(v==="system")setTimeout(()=>{try{window.tmbtLayoutAudit?.();window.dispatchEvent(new Event("resize"))}catch{}},80);
 if(v==="desk")setTimeout(draw,40);
}
async function api(path){const r=await fetch(path,{cache:"no-store"});if(!r.ok)throw Error(`${r.status} ${path}`);return r.json()}
function resetChartScale(){state.yZoom=1;state.offset=0;state.futureSpace=0;state.hover=null}
function setMarket(m){state.market=m;$$(".marketbar button").forEach(b=>b.classList.toggle("active",b.dataset.market===m));state.viewCount=140;resetChartScale();loadBars();loadPD()}
function setTF(tf){state.tf=tf;$$(".tfbar button").forEach(b=>b.classList.toggle("active",b.dataset.tf===tf));state.viewCount=140;resetChartScale();loadBars()}
function healthFromBoot(d){const ss=d.signal_status||{};dot("#liveDot",ss.running===false?"warn":"ok");const ps=(d.paper||{}).status||{};dot("#paperDot",ps.running?"ok":"warn");const j=(d.research||[])[0];dot("#researchDot",j&&String(j.state).toUpperCase()==="RUNNING"?"ok":"warn")}
async function bootstrap(){
 try{
  const d=await api("/api/bootstrap");$("#version").textContent=d.version+" · parallel UI";state.models=d.models||[];state.archive=d.archive||[];state.outcomes=d.outcome_summary||[];state.outcomeGroups=d.outcome_groups||[];state.research=d.research||[];state.paper=d.paper||null;healthFromBoot(d);
  renderModels();renderSignals();renderArchive();renderOutcomes();renderResearch();renderPaperSummary(d.paper);checkResearchAlerts(state.research);
 }catch(e){log("Bootstrap Fehler: "+e);dot("#liveDot","bad")}
}
async function pollModels(){
 try{const d=await api("/api/models");state.models=d.models||[];renderModels();renderSignals();dot("#liveDot",d.status?.running===false?"warn":"ok")}catch(e){dot("#liveDot","bad")}
}
async function pollResearch(){
 try{
  const [d,n,a,s,rs]=await Promise.all([
   api("/api/research?limit=12"),
   api("/api/trader-observations").catch(()=>({text:""})),
   api("/api/research-autopilot/status").catch(()=>null),
   api("/api/research-sync/status").catch(()=>null),
   api("/api/research-scheduler/status").catch(()=>null)
  ]);
  state.research=d.jobs||[];state.traderNotes=n.text||"";state.researchAutopilot=a;state.researchSync=s;state.researchScheduler=rs;renderResearch();renderReview();checkResearchAlerts(state.research);
  const j=state.research[0];dot("#researchDot",rs?.running||s?.running||a?.running||j&&String(j.state).toUpperCase()==="RUNNING"?"ok":"warn")
 }catch(e){}
}

async function researchAutopilotAction(action){
 try{
  const profile=$("#researchAutopilotProfile")?.value||"NQ_EBP_H1";
  const r=await fetch("/api/research-autopilot/"+action,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(action==="start"?{profile,test_news:true,tick_audit:false}:{})});
  const d=await r.json();
  if(!r.ok)throw Error(d.error||String(r.status));
  toast(action==="start"?(d.started===false&&d.reason==="already_running"?"Research Autopilot läuft bereits.":"Research Autopilot gestartet: "+profile):"Research Autopilot Abbruch angefordert.");
  setTimeout(pollResearch,500);
 }catch(e){toast("Research Autopilot: "+String(e))}
}
async function pollPaper(){
 try{const d=await api("/api/paper");state.paper=d;renderPaper(d);const s=d.status||{};dot("#paperDot",s.running?"ok":"warn")}catch(e){}
}
async function refreshArchive(){
 try{const d=await api("/api/archive?limit=500");state.archive=d.rows||[];renderArchive()}catch(e){}
}
async function refreshOutcomes(){
 try{const d=await api("/api/outcomes");state.outcomes=d.summary||[];state.outcomeGroups=d.groups||[];renderOutcomes()}catch(e){}
}
function researchAlertLabel(j){
 const req=j?.request||{},kind=String(j?.kind||"research").toLowerCase(),preset=req.preset||j?.job_id||"Research";
 const notes=String(req.notes||"");
 let stage="";
 if(/development baseline/i.test(notes))stage="Baseline";
 else if(/optimized development candidate/i.test(notes))stage="Optimized Candidate";
 else if(/locked validation/i.test(notes))stage="Validation";
 else if(/tick-exact validation audit/i.test(notes))stage="Tick Audit";
 else if(/news variant/i.test(notes))stage="News Variant";
 else if(/optimizer:/i.test(notes))stage=notes.replace(/^.*optimizer:\s*/i,"").trim();
 else if(kind==="optimizer")stage="Optimizer";
 else stage=kind==="backtest"?"Backtest":kind;
 return `${preset} · ${stage}`;
}
function checkResearchAlerts(jobs){
 let dirty=false;
 for(const j of jobs||[]){
  const id=researchJobKey(j);if(!id)continue;
  const st=String(j.state||"").toUpperCase(),prev=state.lastResearchStates[id],terminal=["COMPLETED","FAILED","CANCELLED"].includes(st),alertKey=`${id}|${st}`;
  if(terminal&&!researchAlertSeen.has(alertKey)){
   const shouldNotify=researchAlertsPrimed&&(prev===undefined||prev!==st);
   researchAlertSeen.add(alertKey);dirty=true;
   if(shouldNotify){const msg=`Research ${st}: ${researchAlertLabel(j)}`;toast(msg);if(state.alerts&&"Notification" in window&&Notification.permission==="granted")new Notification("TMBT Research",{body:msg})}
  }
  state.lastResearchStates[id]=st;
 }
 if(dirty)saveResearchAlertSeen();
 researchAlertsPrimed=true;
}
async function loadBars(){
 if(state.mode==="snapshot")return;
 $("#chartTitle").textContent=`${state.market} · ${state.tf}`;$("#chartEmpty").textContent="Lade Bars…";$("#chartEmpty").style.display="grid";
 try{const d=await api(`/api/bars?market=${encodeURIComponent(state.market)}&tf=${encodeURIComponent(state.tf)}&limit=1500${state.source?`&source=${encodeURIComponent(state.source)}`:""}`);state.bars=d.bars||[];state.source=d.source||null;$("#chartSource").textContent=state.source?`${state.source} · lokaler Cache`:(d.note||"kein Feed");$("#chartEmpty").style.display=state.bars.length?"none":"grid";if(state.bars.length){const p=state.bars.at(-1).c;$("#q"+state.market).textContent=fmt(p,2)}draw()}catch(e){$("#chartEmpty").textContent="Bars konnten nicht geladen werden";log(String(e))}
}
async function loadPD(){
 try{const d=await api(`/api/pd?market=${encodeURIComponent(state.market)}${state.source?`&source=${encodeURIComponent(state.source)}`:""}`);state.pd=d.levels||{};renderPD();draw()}catch(e){state.pd={};renderPD()}
}
function rangeText(h,l){return h==null||l==null?"—":`${fmt(h,2)} / ${fmt(l,2)}`}
function posText(eq){if(eq==null||!state.bars.length)return"—";const p=Number(state.bars.at(-1).c);return p>eq?"Premium":p<eq?"Discount":"EQ"}
function renderPD(){const p=state.pd||{};$("#pm").textContent=rangeText(p.PMH,p.PML);$("#pw").textContent=rangeText(p.PWH,p.PWL);$("#pd").textContent=rangeText(p.PDH,p.PDL);$("#pmPos").textContent=posText(p.month_eq);$("#pwPos").textContent=posText(p.week_eq);$("#pdPos").textContent=posText(p.day_eq)}
function renderModels(){const box=$("#modelList");if(!state.models.length){box.innerHTML='<div class="empty">Keine Live-Modelle gefunden.</div>';return}box.innerHTML=state.models.map(m=>`<div class="model-card ${state.selectedModel?.id===m.id?"selected":""}" data-id="${esc(m.id)}"><div class="model-row"><b>${esc(m.name)}</b><span class="pill ${String(m.status).toLowerCase()}">${esc(m.status)}</span></div><div class="model-row"><small>${esc(m.market)} · ${esc(m.tf)} · ${esc(m.source||"")}</small><small>${esc(m.side)}</small></div></div>`).join("");box.querySelectorAll(".model-card").forEach(el=>el.onclick=()=>selectModel(el.dataset.id))}
function selectModel(id){const m=state.models.find(x=>String(x.id)===String(id));if(!m)return;state.selectedModel=m;state.snapshot=null;state.mode="live";$("#snapshotBanner").classList.remove("show");if(["NQ","ES","XAU"].includes(String(m.market)))state.market=String(m.market);if(m.tf)state.tf=String(m.tf);state.source=m.source||state.source;state.viewCount=140;resetChartScale();$$(".marketbar button").forEach(b=>b.classList.toggle("active",b.dataset.market===state.market));$$(".tfbar button").forEach(b=>b.classList.toggle("active",b.dataset.tf===state.tf));$("#selectedSetup").textContent=m.name;$("#selectedState").textContent=`${m.status} · ${m.side}`;renderInspector(m);renderModels();loadBars();loadPD()}
function renderInspector(m, snap=null){if(!m){return}const validity=m.validity||{};$("#inspector").className="inspector";$("#inspector").innerHTML=`<span class="pill ${String(m.status||m.stage).toLowerCase()}">${esc(m.status||m.stage||"—")}</span><h3>${esc(m.name||m.label||m.model||"Setup")}</h3><p>${esc(m.message||validity.reason||"")}</p>`;$("#iEntry").textContent=fmt(m.entry??m.arrays?.entry,4);$("#iStop").textContent=fmt(m.sl??m.stop??m.arrays?.stop,4);$("#iTarget").textContent=fmt(m.tp??m.target??m.arrays?.target,4);$("#iRR").textContent=fmt(m.rr??m.planned_rr??m.arrays?.planned_rr,2);const crit=m.criteria||snap?.criteria||[];$("#criteria").innerHTML=crit.length?crit.slice(0,12).map(c=>{if(typeof c==="string")return`<p class="pass">${esc(c)}</p>`;const s=String(c.status||"PENDING").toLowerCase();return`<p class="${s}"><b>${esc(c.label||c.name||"")}</b>${c.detail?` — ${esc(c.detail)}`:""}</p>`}).join(""):"<p>Keine Kriterien verfügbar.</p>";const logic=m.logic||snap?.logic||{};const entries=Object.entries(logic);$("#logic").innerHTML=entries.length?entries.slice(0,12).map(([k,v])=>`<p><b>${esc(k)}:</b> ${esc(typeof v==="object"?JSON.stringify(v):v)}</p>`).join(""):"<p>Keine Logikdetails verfügbar.</p>"}
function renderSignals(){const rows=state.models.map(m=>`<tr class="clickable" data-id="${esc(m.id)}"><td>${esc(m.name)}</td><td>${esc(m.market)}</td><td>${esc(m.tf)}</td><td><span class="pill ${String(m.status).toLowerCase()}">${esc(m.status)}</span></td><td>${esc(m.side)}</td><td>${fmt(m.entry,4)}</td><td>${fmt(m.sl,4)}</td><td>${fmt(m.tp,4)}</td><td>${fmt(m.rr,2)}</td><td class="muted">${esc(m.message)}</td></tr>`).join("");$("#signalsTable").innerHTML=`<table class="table"><thead><tr><th>Model</th><th>Market</th><th>TF</th><th>Status</th><th>Side</th><th>Entry</th><th>SL</th><th>TP</th><th>RR</th><th>Info</th></tr></thead><tbody>${rows}</tbody></table>`;$("#signalsTable").querySelectorAll("tr[data-id]").forEach(r=>r.onclick=()=>selectModel(r.dataset.id))}
function archiveFiltered(){const q=$("#archiveSearch")?.value.toLowerCase()||"",st=$("#archiveStage")?.value||"";return state.archive.filter(r=>(!st||String(r.stage)===st)&&(!q||[r.model,r.market,r.stage,r.side,r.reason].some(x=>String(x||"").toLowerCase().includes(q))))}
function renderArchive(){if(!$("#archiveTable"))return;const arr=archiveFiltered();$("#archiveCount").textContent=`${arr.length} Einträge`;const rows=arr.map(r=>`<tr class="clickable" data-hid="${esc(r.history_id)}" data-sid="${esc(r.snapshot_id||"")}"><td>${r.snapshot_id?"📸":"—"}</td><td>${iso(r.event_time_utc)}</td><td>${esc(r.model)}</td><td>${esc(r.market)}</td><td>${esc(r.tf)}</td><td><span class="pill ${String(r.stage).toLowerCase()}">${esc(r.stage)}</span></td><td>${esc(r.side||"—")}</td><td>${fmt(r.entry,4)}</td><td>${fmt(r.sl,4)}</td><td>${fmt(r.tp,4)}</td><td>${r.outcome?esc(r.outcome):"—"}</td><td class="${Number(r.outcome_r)>0?"good":Number(r.outcome_r)<0?"bad":""}">${r.outcome_r==null?"—":fmt(r.outcome_r,2)+"R"}</td><td class="muted">${esc(r.reason||"")}</td></tr>`).join("");$("#archiveTable").innerHTML=`<table class="table"><thead><tr><th>Snap</th><th>Zeit</th><th>Model</th><th>Mkt</th><th>TF</th><th>Status</th><th>Side</th><th>Entry</th><th>SL</th><th>TP</th><th>Outcome</th><th>R</th><th>Grund</th></tr></thead><tbody>${rows}</tbody></table>`;$("#archiveTable").querySelectorAll("tr[data-hid]").forEach(r=>r.onclick=()=>openArchive(r.dataset.hid,r.dataset.sid))}
async function openArchive(hid,sid){const row=state.archive.find(x=>x.history_id===hid);if(!row)return;if(!sid){toast("Für diesen Legacy-Eintrag existiert kein eingefrorener Snapshot.");return}try{const snap=await api(`/api/snapshot?id=${encodeURIComponent(sid)}`);state.snapshot=snap;state.mode="snapshot";state.bars=(snap.bars||[]).map(b=>({t:b.bar_open_ms??b.t,o:Number(b.open??b.o),h:Number(b.high??b.h),l:Number(b.low??b.l),c:Number(b.close??b.c)}));state.offset=0;state.viewCount=Math.min(140,Math.max(40,state.bars.length));state.yZoom=1;state.futureSpace=0;const sm=snap.model||{};state.market=sm.market||row.market||state.market;state.tf=sm.timeframe||row.tf||state.tf;state.selectedModel={id:row.model_id||hid,name:sm.label||row.model,status:sm.stage||row.stage,side:sm.side||row.side,entry:snap.arrays?.entry??row.entry,sl:snap.arrays?.stop??row.sl,tp:snap.arrays?.target??row.tp,rr:snap.arrays?.planned_rr??row.rr,message:sm.message||row.reason,criteria:snap.criteria||row.criteria,logic:snap.logic||row.logic,arrays:snap.arrays||{},validity:snap.validity||{}};$("#snapshotBanner").classList.add("show");$("#snapshotName").textContent=`${state.selectedModel.name} · ${iso(snap.event_time_utc)}`;$("#chartTitle").textContent=`${state.market} · ${state.tf} · Snapshot`;$("#chartSource").textContent=`eingefroren · ${sm.source||row.source||"—"}`;$("#selectedSetup").textContent=state.selectedModel.name;$("#selectedState").textContent=`${state.selectedModel.status} · ${state.selectedModel.side}`;renderInspector(state.selectedModel,snap);$("#chartEmpty").style.display=state.bars.length?"none":"grid";draw();toast("Snapshot geladen")}catch(e){toast("Snapshot konnte nicht geladen werden.");log(String(e))}}
async function openTradeReplay(hid,phase="entry"){
 try{
  const d=await api("/api/trade-replay?history_id="+encodeURIComponent(hid)+"&phase="+encodeURIComponent(phase));
  state.snapshot=null;state.tradeReplay=d;state.mode="trade_replay";
  state.market=d.market||state.market;state.tf=d.tf||state.tf;state.source=null;
  state.bars=(d.bars||[]).map(b=>({t:b.bar_open_ms??b.t,o:Number(b.open??b.o),h:Number(b.high??b.h),l:Number(b.low??b.l),c:Number(b.close??b.c),v:b.volume??b.v}));
  state.pd=d.pd||{};
  state.selectedModel=Object.assign({},d.setup||{},{market:state.market,tf:state.tf});
  state.offset=0;state.viewCount=Math.min(150,Math.max(45,state.bars.length));state.yZoom=1;state.futureSpace=0;
  document.querySelectorAll(".marketbar button").forEach(b=>b.classList.toggle("active",b.dataset.market===state.market));
  document.querySelectorAll(".tfbar button").forEach(b=>b.classList.toggle("active",b.dataset.tf===state.tf));
  setWorkspaceView("desk");
  $("#snapshotBanner").classList.add("show");
  $("#snapshotModeLabel").textContent=phase==="result"?"TRADE REPLAY · RESULT":"TRADE REPLAY · ENTRY";
  $("#snapshotName").textContent=(state.selectedModel.name||"Trade")+" · "+(d.quality||"REPLAY")+(d.outcome_r==null?"":" · "+fmt(d.outcome_r,2)+"R");
  $("#backOutcome").style.display="";
  $("#chartTitle").textContent=state.market+" · "+state.tf+" · "+(phase==="result"?"Result Replay":"Entry Snapshot");
  $("#chartSource").textContent=(d.quality_note||"")+(d.cached?" · cached":"");
  $("#selectedSetup").textContent=state.selectedModel.name||"Historical Trade";
  $("#selectedState").textContent=(state.selectedModel.status||"REPLAY")+" · "+(state.selectedModel.side||"—");
  renderInspector(state.selectedModel,{criteria:state.selectedModel.criteria||[],logic:state.selectedModel.logic||{}});
  $("#chartEmpty").style.display=state.bars.length?"none":"grid";
  draw();
  toast(phase==="result"?"Result Snapshot geladen":"Entry Snapshot geladen");
 }catch(e){toast("Trade-Snapshot konnte nicht geladen werden.");log(String(e))}
}
function backOutcomes(){state.tradeReplay=null;state.mode="live";$("#snapshotBanner").classList.remove("show");$("#backOutcome").style.display="none";$("#snapshotModeLabel").textContent="FROZEN SNAPSHOT";setWorkspaceView("outcomes");refreshOutcomes()}
function backLive(){state.mode="live";state.snapshot=null;state.tradeReplay=null;$("#snapshotBanner").classList.remove("show");$("#backOutcome").style.display="none";$("#snapshotModeLabel").textContent="FROZEN SNAPSHOT";resetChartScale();loadBars();loadPD();if(state.selectedModel)renderInspector(state.selectedModel)}
function outcomeStatsHtml(s){
 const x=s||{};
 return `<div class="outcome-stat-grid">
  <div><small>Signals</small><b>${x.signals??0}</b></div>
  <div><small>Winrate</small><b>${x.winrate==null?"—":fmt(x.winrate,1)+"%"}</b></div>
  <div><small>Net R</small><b class="${Number(x.net_r)>0?"good":Number(x.net_r)<0?"bad":""}">${fmt(x.net_r??0,2)}R</b></div>
  <div><small>Expectancy</small><b>${x.expectancy==null?"—":fmt(x.expectancy,2)+"R"}</b></div>
  <div><small>Ø MFE</small><b>${x.avg_mfe==null?"—":fmt(x.avg_mfe,2)+"R"}</b></div>
  <div><small>Ø MAE</small><b>${x.avg_mae==null?"—":fmt(x.avg_mae,2)+"R"}</b></div>
 </div>`;
}
function outcomeInstanceTable(items){
 const arr=items||[];
 if(!arr.length)return'<div class="empty">Keine Modellinstanzen.</div>';
 return `<table class="table compact outcome-instance-table"><thead><tr><th>Market</th><th>TF</th><th>Model</th><th>Signals</th><th>WR</th><th>Net R</th><th>Exp</th></tr></thead><tbody>${arr.map(i=>{
  const s=i.stats||{};
  return `<tr><td><b>${esc(i.market)}</b></td><td><span class="tf-chip">${esc(i.tf)}</span></td><td>${esc(i.model)}</td><td>${s.signals??0}</td><td>${s.winrate==null?"—":fmt(s.winrate,1)+"%"}</td><td class="${Number(s.net_r)>0?"good":Number(s.net_r)<0?"bad":""}">${fmt(s.net_r??0,2)}R</td><td>${s.expectancy==null?"—":fmt(s.expectancy,2)+"R"}</td></tr>`
 }).join("")}</tbody></table>`;
}
function outcomeTradeHtml(t){
 const l=t.logic_summary||{},criteria=l.criteria||[],logic=l.logic||[];
 return `<details class="outcome-trade">
  <summary>
   <span class="outcome-trade-main"><b>${esc(t.market)} · ${esc(t.tf)}</b><span>${esc(t.model)}</span><small>${iso(t.event_time_utc)} · ${esc(t.side||"—")}</small></span>
   <span class="outcome-trade-result ${Number(t.outcome_r)>0?"good":Number(t.outcome_r)<0?"bad":""}"><b>${t.outcome_r==null?"—":fmt(t.outcome_r,2)+"R"}</b><small>${esc(t.outcome||"—")}</small></span>
  </summary>
  <div class="outcome-trade-body">
   <div class="outcome-trade-metrics">
    <div><small>Entry</small><b>${fmt(t.entry,4)}</b></div>
    <div><small>Stop</small><b>${fmt(t.sl,4)}</b></div>
    <div><small>Target</small><b>${fmt(t.tp,4)}</b></div>
    <div><small>Planned RR</small><b>${t.planned_rr==null?"—":fmt(t.planned_rr,2)+"R"}</b></div>
    <div><small>MFE</small><b>${t.mfe_r==null?"—":fmt(t.mfe_r,2)+"R"}</b></div>
    <div><small>MAE</small><b>${t.mae_r==null?"—":fmt(t.mae_r,2)+"R"}</b></div>
   </div>
   <div class="outcome-chart-actions"><button class="trade-chart-btn" data-history-id="${esc(t.history_id)}" data-phase="entry">📸 Entry Snapshot</button><button class="trade-chart-btn" data-history-id="${esc(t.history_id)}" data-phase="result">🏁 Result Snapshot</button></div>
   ${l.reason?`<p class="outcome-trade-reason"><b>Setup/Outcome:</b> ${esc(l.reason)}</p>`:""}
   <div class="outcome-logic-grid">
    <section><h5>Kriterien beim Trade</h5>${criteria.length?`<ul>${criteria.map(x=>`<li>${esc(x)}</li>`).join("")}</ul>`:'<p class="muted">Keine eingefrorenen Kriterien verfügbar.</p>'}</section>
    <section><h5>Gespeicherte Modell-Logik</h5>${logic.length?`<dl>${logic.map(x=>`<div><dt>${esc(x.key)}</dt><dd>${esc(x.value)}</dd></div>`).join("")}</dl>`:'<p class="muted">Keine Logikdetails für diesen historischen Trade gespeichert.</p>'}</section>
   </div>
  </div>
 </details>`;
}
function renderOutcomes(){
 const groups=state.outcomeGroups||[];
 const host=$("#outcomeCards");if(!host)return;
 host.className="outcome-groups";
 if(!groups.length){
  const arr=state.outcomes||[];
  host.innerHTML=arr.length?arr.map(o=>`<div class="outcome-card"><h4>${esc(o.model)}</h4>${outcomeStatsHtml(o)}</div>`).join(""):'<div class="empty">Noch keine Outcome-Daten.</div>';
  return;
 }
 host.innerHTML=groups.map(g=>`<article class="outcome-group-card">
   <div class="outcome-group-head"><div><small>${esc(g.scope||"")}</small><h3>${esc(g.family||g.label)}</h3></div><span class="pill idle">${(g.instances||[]).length} INSTANCES</span></div>
   ${outcomeStatsHtml(g.stats)}
   <details class="outcome-section" open><summary><b>Modelle & Timeframes</b><span>alle konfigurierten Instanzen, auch ohne Trades</span></summary>${outcomeInstanceTable(g.instances)}</details>
   <details class="outcome-section"><summary><b>Vergangene Trades</b><span>${(g.trades||[]).length} Trades · aufklappbar inkl. Logik</span></summary><div class="outcome-trades">${(g.trades||[]).length?(g.trades||[]).map(outcomeTradeHtml).join(""):'<div class="empty">Noch keine abgeschlossenen Trades für diese Gruppe.</div>'}</div></details>
  </article>`).join("");
 host.querySelectorAll(".trade-chart-btn").forEach(btn=>btn.onclick=e=>{e.preventDefault();e.stopPropagation();openTradeReplay(btn.dataset.historyId,btn.dataset.phase)});
}
function perfMoney(v){
 if(v===null||v===undefined||v==="")return"—";const n=Number(v);if(!Number.isFinite(n))return"—";
 try{return new Intl.NumberFormat("de-DE",{style:"currency",currency:"EUR",maximumFractionDigits:2}).format(n)}catch{return n.toFixed(2)+" €"}
}
function perfPct(v,d=2){if(v===null||v===undefined||v==="")return"—";const n=Number(v);return Number.isFinite(n)?n.toFixed(d)+"%":"—"}
function perfNum(v,d=2){if(v===null||v===undefined||v==="")return"—";const n=Number(v);return Number.isFinite(n)?n.toFixed(d):"—"}
function perfEquitySvg(perf){
 const curve=perf?.equity_curve||[];if(curve.length<2)return'<div class="perf-chart-empty">Keine Equity-Daten verfügbar.</div>';
 const w=1000,h=230,p=30,vals=curve.map(x=>Number(x.balance_eur)).filter(Number.isFinite);
 let lo=Math.min(...vals),hi=Math.max(...vals);if(!(hi>lo)){hi=lo+1}
 const pad=(hi-lo)*.08;lo-=pad;hi+=pad;
 const sx=i=>p+(w-2*p)*(i/Math.max(1,curve.length-1)),sy=v=>p+(h-2*p)*(1-(v-lo)/(hi-lo));
 const pts=curve.map((x,i)=>`${sx(i).toFixed(1)},${sy(Number(x.balance_eur)).toFixed(1)}`).join(" ");
 const start=Number(curve[0].balance_eur),end=Number(curve.at(-1).balance_eur),startY=sy(start);
 const ticks=[0,.25,.5,.75,1].map(f=>{const v=lo+(hi-lo)*(1-f),y=p+(h-2*p)*f;return`<line x1="${p}" y1="${y}" x2="${w-p}" y2="${y}" class="perf-gridline"/><text x="4" y="${y+4}" class="perf-axis">${esc(perfMoney(v))}</text>`}).join("");
 return`<div class="perf-chart"><div class="perf-chart-head"><div><b>Equity Curve</b><small>${esc(perfMoney(start))} → ${esc(perfMoney(end))}</small></div><span>${curve.length-1} Trades</span></div><svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" role="img" aria-label="Equity curve">${ticks}<line x1="${p}" y1="${startY}" x2="${w-p}" y2="${startY}" class="perf-startline"/><polyline points="${pts}" class="perf-equity-line"/></svg></div>`;
}
function perfDrawdownSvg(perf){
 const curve=perf?.equity_curve||[];if(curve.length<2)return"";
 const w=1000,h=130,p=26,vals=curve.map(x=>Number(x.drawdown_pct)||0),max=Math.max(1,...vals);
 const sx=i=>p+(w-2*p)*(i/Math.max(1,curve.length-1)),sy=v=>p+(h-2*p)*(v/max);
 const pts=curve.map((x,i)=>`${sx(i).toFixed(1)},${sy(Number(x.drawdown_pct)||0).toFixed(1)}`).join(" ");
 return`<div class="perf-chart drawdown"><div class="perf-chart-head"><div><b>Drawdown</b><small>max ${perfPct(perf?.metrics?.max_drawdown_pct,2)}</small></div></div><svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><line x1="${p}" y1="${p}" x2="${w-p}" y2="${p}" class="perf-gridline"/><polyline points="${pts}" class="perf-dd-line"/></svg></div>`;
}
function perfTableRows(rows,kind){
 if(!Array.isArray(rows)||!rows.length)return'<tr><td colspan="4" class="muted">—</td></tr>';
 if(kind==="side")return rows.map(x=>`<tr><td>${esc(x.side)}</td><td>${x.trades??0}</td><td>${perfPct(x.winrate_pct,1)}</td><td>${perfNum(x.net_r,2)}R</td><td>${perfNum(x.expectancy_r,3)}R</td></tr>`).join("");
 if(kind==="exit")return rows.map(x=>`<tr><td>${esc(x.reason)}</td><td>${x.trades??0}</td><td>${perfPct(x.winrate_pct,1)}</td><td>${perfNum(x.net_r,2)}R</td></tr>`).join("");
 return rows.slice(-24).map(x=>`<tr><td>${esc(x.month)}</td><td>${x.trades??0}</td><td>${perfNum(x.net_r,2)}R</td><td>${perfPct(x.winrate_pct,1)}</td><td>${perfNum(x.expectancy_r,3)}R</td></tr>`).join("");
}
function performanceDetail(perf,label="Validation",open=true){
 if(!perf?.available)return`<details class="performance-report" ${open?"open":""}><summary>${esc(label)} · Performance</summary><div class="empty">Detaildaten nicht verfügbar${perf?.reason?" · "+esc(perf.reason):""}.</div></details>`;
 const m=perf.metrics||{},best=perf.best_trade||{},worst=perf.worst_trade||{},acc=perf.accounting||{};
 return`<details class="performance-report" ${open?"open":""}>
  <summary><b>${esc(label)} · MetaTrader-Style Auswertung</b><span>${m.trades??0} Trades · ${perfMoney(m.start_balance_eur)} Start</span></summary>
  <div class="perf-account-note">Kontosimulation: <b>${perfMoney(acc.start_balance_eur)}</b> Start · <b>${perfPct(acc.risk_pct_per_r,2)}</b> Risiko je 1R, auf aktuelle Equity gerechnet. Nur Reporting – verändert keine Entry-/Model-Logik.</div>
  <div class="perf-metric-grid">
   <div><small>End Balance</small><b>${perfMoney(m.end_balance_eur)}</b></div>
   <div><small>Net Profit</small><b class="${Number(m.net_profit_eur)>=0?"good":"bad"}">${perfMoney(m.net_profit_eur)}</b></div>
   <div><small>Return</small><b>${perfPct(m.return_pct,2)}</b></div>
   <div><small>Profit Factor</small><b>${perfNum(m.profit_factor,2)}</b></div>
   <div><small>Expectancy</small><b>${perfNum(m.expectancy_r,3)}R</b></div>
   <div><small>Win Rate</small><b>${perfPct(m.winrate_pct,1)}</b></div>
   <div><small>Net R</small><b>${perfNum(m.net_r,2)}R</b></div>
   <div><small>Max DD</small><b>${perfMoney(m.max_drawdown_eur)} · ${perfPct(m.max_drawdown_pct,2)}</b></div>
   <div><small>Avg Win</small><b>${perfNum(m.avg_win_r,3)}R</b></div>
   <div><small>Avg Loss</small><b>${perfNum(m.avg_loss_r,3)}R</b></div>
   <div><small>Median Trade</small><b>${perfNum(m.median_r,3)}R</b></div>
   <div><small>Recovery Factor</small><b>${perfNum(m.recovery_factor,2)}</b></div>
   <div><small>Max Win Streak</small><b>${m.max_consecutive_wins??"—"}</b></div>
   <div><small>Max Loss Streak</small><b>${m.max_consecutive_losses??"—"}</b></div>
   <div><small>Avg Planned RR</small><b>${perfNum(m.avg_planned_rr,2)}R</b></div>
   <div><small>Avg Hold</small><b>${perfNum(m.avg_hold_minutes,0)} min</b></div>
  </div>
  <div class="perf-chart-grid">${perfEquitySvg(perf)}${perfDrawdownSvg(perf)}</div>
  <div class="perf-best-worst">
   <div><small>Highest Win</small><b class="good">${perfNum(best.r,3)}R · ${perfMoney(best.pnl_eur)}</b><span>${esc(best.side||"")} · ${esc(best.exit_reason||"")} · ${esc(best.exit_time||"")}</span></div>
   <div><small>Highest Loss</small><b class="bad">${perfNum(worst.r,3)}R · ${perfMoney(worst.pnl_eur)}</b><span>${esc(worst.side||"")} · ${esc(worst.exit_reason||"")} · ${esc(worst.exit_time||"")}</span></div>
   <div><small>Avg MFE / MAE</small><b>${perfNum(m.avg_mfe_r,2)}R / ${perfNum(m.avg_mae_r,2)}R</b><span>Trade excursion</span></div>
   <div><small>Gross Profit / Loss</small><b>${perfMoney(m.gross_profit_eur)} / ${perfMoney(m.gross_loss_eur)}</b><span>${perfNum(m.gross_profit_r,1)}R / ${perfNum(m.gross_loss_r,1)}R</span></div>
  </div>
  <div class="perf-tables">
   <section><h4>Long / Short</h4><table class="table compact"><thead><tr><th>Side</th><th>Trades</th><th>WR</th><th>Net</th><th>Exp</th></tr></thead><tbody>${perfTableRows(perf.sides,"side")}</tbody></table></section>
   <section><h4>Exit Reasons</h4><table class="table compact"><thead><tr><th>Exit</th><th>Trades</th><th>WR</th><th>Net</th></tr></thead><tbody>${perfTableRows(perf.exit_reasons,"exit")}</tbody></table></section>
  </div>
  <details class="perf-monthly"><summary>Monatliche Performance</summary><table class="table compact"><thead><tr><th>Monat</th><th>Trades</th><th>Net</th><th>WR</th><th>Exp</th></tr></thead><tbody>${perfTableRows(perf.monthly,"month")}</tbody></table></details>
 </details>`;
}
function optimizationHistory(a){
 const steps=a?.optimization_steps||[];
 if(!steps.length)return'<div class="empty">Noch kein Optimierungsverlauf gespeichert.</div>';
 return`<div class="optimization-history">${steps.map((s,i)=>{
  const d=s.deltas||{},before=s.before||{},after=s.after||{},changes=s.changes||[];
  const ch=changes.length?changes.map(x=>`<span class="opt-change"><b>${esc(x.parameter)}</b> ${esc(x.before==null?"—":x.before)} → ${esc(x.after)}</span>`).join(""):'<span class="muted">keine Parameteränderung</span>';
  const effectClass=(Number(d.expectancy_r)>=0&&Number(d.profit_factor_r)>=0)?"good":((Number(d.expectancy_r)<0&&Number(d.profit_factor_r)<0)?"bad":"");
  return`<article class="optimization-step">
    <div class="optimization-step-head"><div><small>Lauf ${i+1}</small><b>${esc(s.name||s.stage||"Optimizer")}</b></div><span>${s.tested_combinations??0} Kombinationen</span></div>
    <div class="opt-changes">${ch}</div>
    <div class="opt-effect ${effectClass}">
      <span>Expectancy <b>${perfNum(before.expectancy_r,3)} → ${perfNum(after.expectancy_r,3)}R</b> <em>${Number(d.expectancy_r)>=0?"+":""}${perfNum(d.expectancy_r,3)}</em></span>
      <span>PF <b>${perfNum(before.profit_factor_r,2)} → ${perfNum(after.profit_factor_r,2)}</b> <em>${Number(d.profit_factor_r)>=0?"+":""}${perfNum(d.profit_factor_r,3)}</em></span>
      <span>DD <b>${perfNum(before.max_drawdown_r,1)} → ${perfNum(after.max_drawdown_r,1)}R</b> <em>${Number(d.max_drawdown_r)>=0?"+":""}${perfNum(d.max_drawdown_r,1)}R</em></span>
      <span>Net <b>${perfNum(before.net_r,1)} → ${perfNum(after.net_r,1)}R</b> <em>${Number(d.net_r)>=0?"+":""}${perfNum(d.net_r,1)}R</em></span>
    </div>
    <p class="opt-reason"><b>Warum:</b> ${esc(s.reason||"—")}</p>
  </article>`
 }).join("")}</div>`;
}
function validationGateHtml(a){
 const v=a?.validation||{},g=v.gates||{},keys=Object.keys(g);
 if(!keys.length)return"";
 const label=k=>({
  development_expectancy_ge_0_10R:"Development Expectancy ≥ 0.10R",
  development_profit_factor_ge_1_20:"Development PF ≥ 1.20",
  validation_expectancy_ge_0_08R:"Validation Expectancy ≥ 0.08R",
  validation_profit_factor_ge_1_20:"Validation PF ≥ 1.20",
  validation_min_trades:`Validation Trades ≥ ${v.min_val_trades??"—"}`,
  validation_net_r_ge_10:"Validation Net ≥ 10R",
  expectancy_retention_ge_50pct:"Expectancy Retention ≥ 50%",
  validation_recovery_factor_ge_1_50:"Recovery Factor ≥ 1.50",
  validation_max_drawdown_le_25R:"Validation DD ≤ 25R"
 }[k]||k);
 return`<div class="validation-gates"><div class="model-row"><h4>Live-Review Gate</h4><span class="pill ${String(v.verdict||"fail").toLowerCase()}">${esc(v.verdict||"—")} · ${v.passed_gates??0}/${v.total_gates??keys.length}</span></div><div class="gate-grid">${keys.map(k=>`<div class="${g[k]?"pass":"fail"}"><b>${g[k]?"✓":"✕"}</b><span>${esc(label(k))}</span></div>`).join("")}</div><small>Positiver Net Profit allein reicht ausdrücklich nicht. Alle Gates müssen für PASS erfüllt sein.</small></div>`;
}
function renderReview(){
 const host=$("#reviewView");if(!host)return;
 const rs=state.researchScheduler||{},profiles=Object.values(rs.profiles||{});
 const ready=profiles.filter(p=>String(p.candidate_state||"").toUpperCase()==="READY_FOR_LIVE_REVIEW");
 if(!ready.length){host.innerHTML='<div class="empty">Noch kein Modell hat die Validation für den Review-Gate bestanden.</div>';return}
 host.innerHTML='<div class="review-grid">'+ready.map(p=>{
  const a=p.last_analysis||{},dev=a.development_summary||{},val=a.validation_summary||{},good=a.good||[],bad=a.bad||[],next=a.next_steps||[],ov=a.selected_overrides||{},perf=a.performance||{};
  return `<article class="review-card">
   <div class="review-head"><div><small>${esc(p.profile||"")}</small><h3>${esc(a.label||p.label||p.profile||"Model")}</h3></div><span class="pill signal">READY FOR REVIEW</span></div>
   <div class="review-metrics">
    <div><small>Validation Trades</small><b>${val.trades??"—"}</b></div>
    <div><small>Expectancy</small><b>${val.expectancy_r==null?"—":fmt(val.expectancy_r,3)+"R"}</b></div>
    <div><small>Profit Factor</small><b>${fmt(val.profit_factor_r,2)}</b></div>
    <div><small>Max DD</small><b>${val.max_drawdown_r==null?"—":fmt(val.max_drawdown_r,1)+"R"}</b></div>
   </div>
   ${validationGateHtml(a)}
   ${performanceDetail(perf.validation,"Validation",true)}
   <details class="optimization-report" open><summary><b>Optimierungsverlauf</b><span>${(a.optimization_steps||[]).length} Schritte</span></summary>${optimizationHistory(a)}</details>
   ${performanceDetail(perf.development,"Optimiertes Development",false)}
   ${performanceDetail(perf.baseline,"Development Baseline",false)}
   <div class="review-columns">
    <section><h4>Was funktioniert</h4><ul>${good.map(x=>`<li class="good">${esc(x)}</li>`).join("")||"<li>—</li>"}</ul></section>
    <section><h4>Risiken / Schwächen</h4><ul>${bad.map(x=>`<li class="bad">${esc(x)}</li>`).join("")||"<li>—</li>"}</ul></section>
   </div>
   <section class="review-next"><h4>Nächster Schritt</h4><ul>${next.map(x=>`<li>${esc(x)}</li>`).join("")||"<li>—</li>"}</ul></section>
   <details><summary>Development vs Validation</summary><div class="model-row"><small>Development: ${dev.trades??"—"} Trades · Exp ${fmt(dev.expectancy_r,3)}R · PF ${fmt(dev.profit_factor_r,2)} · DD ${fmt(dev.max_drawdown_r,1)}R</small><small>Validation: ${val.trades??"—"} Trades · Exp ${fmt(val.expectancy_r,3)}R · PF ${fmt(val.profit_factor_r,2)} · DD ${fmt(val.max_drawdown_r,1)}R</small></div></details>
   <details><summary>Gewählte Parameter</summary><pre>${esc(JSON.stringify(ov,null,2))}</pre></details>
   <div class="review-gate-note">Holdout/OOS bleibt gesperrt. Keine automatische Live-Freigabe.</div>
  </article>`
 }).join("")+'</div>';
}

function renderResearch(){
 const arr=state.research||[],a=state.researchAutopilot||{},profiles=a.available_profiles||{},rs=state.researchScheduler||{};
 const opts=Object.entries(profiles).filter(([k])=>k!=="_error").map(([k,v])=>`<option value="${esc(k)}" ${String(a.profile||"")==k?"selected":""}>${esc(v.label||k)}</option>`).join("");

 const cp=rs.cycle_progress||{},cpPct=Math.max(0,Math.min(100,Number(cp.pct||0)));
 const cycle=cp.profile?`<div class="research-card"><div class="model-row"><div><h4>${esc(cp.label||cp.profile)}</h4><small>Automatischer Research-Zyklus</small></div><span class="pill ${cp.running?"signal":"idle"}">${cp.running?"RUNNING":"IDLE"}</span></div><div class="progress"><i style="width:${cpPct}%"></i></div><div class="model-row"><small><b>${cp.step||0}/${cp.total||0}</b> · ${esc(cp.stage_label||cp.stage||"Wartet")} · ${cpPct.toFixed(1)}%</small><small>${cp.news_tests_enabled?"inkl. historische News-Tests":"ohne News-Tests"}</small></div></div>`:"";

 const rawJobs=arr.length?arr.map(j=>{const p=j.progress||{},pct=Number(p.pct||0);return`<div class="research-card"><div class="model-row"><h4>${esc(researchAlertLabel(j))}</h4><span class="pill ${String(j.state).toLowerCase()}">${esc(j.state)}</span></div><div class="progress"><i style="width:${Math.max(0,Math.min(100,pct))}%"></i></div><div class="model-row"><small>${pct.toFixed(1)}% · ${esc(p.date||"")} · Trades ${p.trades??"—"}</small><small>${esc(j.job_id||"")}</small></div>${j.error?`<p class="bad">${esc(j.error)}</p>`:""}</div>`}).join(""):'<div class="empty">Keine technischen Teiljobs.</div>';
 const jobs=`<details class="research-card"><summary><b>Technische Teiljobs</b> <small>${arr.length} · normalerweise eingeklappt</small></summary>${rawJobs}</details>`;

 const news=rs.news||{};
 const newsText=news.ready
  ?`Historische News: AKTIV · ${Number(news.rows||0).toLocaleString("de-DE")} Events · ${esc(news.first_utc||"")} → ${esc(news.last_utc||"")}`
  :`Historische News: NICHT GELADEN · News-Varianten werden übersprungen`;

 const reportHtml=p=>{
  const x=p?.last_analysis||{},dev=x.development_summary||{},val=x.validation_summary||{},good=x.good||[],bad=x.bad||[],next=x.next_steps||[],ov=x.selected_overrides||{},perf=x.performance||{};
  if(!x.profile)return"";
  return`<details class="research-card"><summary><b>Bericht · ${esc(x.label||x.profile)}</b> <span class="pill ${String(x.verdict||"idle").toLowerCase()}">${esc(x.verdict||"—")}</span></summary><div class="model-row"><small>Development: Trades ${dev.trades??"—"} · Exp ${fmt(dev.expectancy_r,3)}R · PF ${fmt(dev.profit_factor_r,2)} · DD ${fmt(dev.max_drawdown_r,1)}R</small><small>Validation: Trades ${val.trades??"—"} · Exp ${fmt(val.expectancy_r,3)}R · PF ${fmt(val.profit_factor_r,2)} · DD ${fmt(val.max_drawdown_r,1)}R</small></div>${validationGateHtml(x)}${performanceDetail(perf.validation,"Validation",false)}<details class="optimization-report"><summary><b>Optimierungsverlauf</b><span>${(x.optimization_steps||[]).length} Schritte</span></summary>${optimizationHistory(x)}</details><h4>Gut</h4><ul>${good.map(v=>`<li class="good">${esc(v)}</li>`).join("")||"<li>—</li>"}</ul><h4>Schlecht / Risiken</h4><ul>${bad.map(v=>`<li class="bad">${esc(v)}</li>`).join("")||"<li>—</li>"}</ul><h4>Nächster Schritt</h4><ul>${next.map(v=>`<li>${esc(v)}</li>`).join("")||"<li>—</li>"}</ul><details><summary>Gewählte Parameter</summary><pre>${esc(JSON.stringify(ov,null,2))}</pre></details></details>`;
 };
 const rp=rs.profiles||{};
 const reports=Object.values(rp).filter(p=>p?.last_analysis?.profile).map(reportHtml).join("");
 const reportsBox=`<div class="research-card research-autopilot"><div class="model-row"><div><h4>Backtest-Berichte</h4><small>direkt im Studio · pro Modell</small></div><span class="pill idle">${Object.values(rp).filter(p=>p?.last_analysis?.profile).length} REPORTS</span></div>${reports||'<div class="empty">Noch keine abgeschlossenen Modellberichte.</div>'}</div>`;

 const pRows=Object.values(rp).map(p=>`<div class="model-row"><small>${esc(p.label||p.profile||"")}</small><span class="pill ${String(p.candidate_state||"idle").toLowerCase()}">${esc(p.candidate_state||"PENDING")}</span></div>`).join("");
 const lab=`<div class="research-card research-autopilot"><div class="model-row"><div><h4>Auto Research Lab</h4><small>Backtest → Optimierung → Validation → nächstes Modell</small></div><span class="pill ${rs.running?"signal":"idle"}">${rs.running?esc(rs.state||"RUNNING"):"STOPPED"}</span></div><div class="model-row"><small>Databento: ${(rs.databento||{}).import_complete?"COMPLETE":esc((rs.databento||{}).state||"WAITING")}</small><small>Auto-Live: AUS · Review erforderlich</small></div><p class="${news.ready?"good":"bad"}">${newsText}</p>${pRows}</div>`;

 const auto=`<div class="research-card research-autopilot"><div class="model-row"><div><h4>Research Autopilot</h4><small>manueller Einzelstart · Observations ausgeschlossen</small></div><span class="pill ${a.running?"signal":"idle"}">${a.running?"RUNNING":"STOPPED"}</span></div><div class="model-row"><select id="researchAutopilotProfile" ${a.running?"disabled":""}>${opts}</select><span><button id="researchAutopilotStart" ${a.running||!opts?"disabled":""}>Start</button> <button id="researchAutopilotStop" class="ghost" ${a.running?"":"disabled"}>Stop</button></span></div></div>`;

 const sync=state.researchSync||{},syncOk=!!sync.healthy;
 const remote=`<div class="research-card research-autopilot"><div class="model-row"><div><h4>Remote Research Sync</h4><small>ChatGPT ↔ TMBT Next</small></div><span class="pill ${syncOk?"signal":"idle"}">${syncOk?"ONLINE":(sync.running?"STALE":"OFFLINE")}</span></div>${sync.last_error?`<p class="bad">${esc(sync.last_error)}</p>`:""}</div>`;
 const notes=state.traderNotes?`<details class="research-card trader-notes"><summary><b>Trader Thinking / Observations</b> <small>nur Notizen · keine Regeln</small></summary><pre>${esc(state.traderNotes)}</pre></details>`:"";

 $("#researchList").innerHTML=remote+lab+cycle+reportsBox+auto+notes+jobs;
 $("#researchAutopilotStart")?.addEventListener("click",()=>researchAutopilotAction("start"));
 $("#researchAutopilotStop")?.addEventListener("click",()=>researchAutopilotAction("stop"));
}
function renderPaperSummary(p){state.paper=p;renderPaper(p)}
function renderPaper(d){if(!d)return;const status=d.status||{},s=d.state||{},cfg=d.config||{},opens=Array.isArray(s.open_positions)?s.open_positions:[],trades=d.trades||[];const top=`<div class="paper-top"><div><small>Agent</small><b>${esc(status.state||"—")}</b></div><div><small>Balance</small><b>${fmt(s.balance??status.balance,2)}</b></div><div><small>Equity</small><b>${fmt(s.equity??status.equity,2)}</b></div><div><small>Open</small><b>${opens.length}</b></div><div><small>Net R</small><b>${fmt(s.net_r,2)}R</b></div></div>`;const openRows=opens.map(p=>`<tr><td>${esc(p.model||p.model_id)}</td><td>${esc(p.side)}</td><td>${fmt(p.entry,4)}</td><td>${fmt(p.current_price,4)}</td><td>${fmt(p.stop,4)}</td><td>${fmt(p.target,4)}</td><td>${p.unrealized_r==null?"—":fmt(p.unrealized_r,2)+"R"}</td></tr>`).join("");const closedRows=trades.slice(0,20).map(t=>`<tr><td>${esc(t.model||t.model_id)}</td><td>${esc(t.side)}</td><td>${esc(t.exit_reason||t.status||"")}</td><td>${t.r==null?"—":fmt(t.r,2)+"R"}</td><td>${iso(t.exit_time_utc||t.closed_at_utc)}</td></tr>`).join("");$("#paperView").innerHTML=top+`<h4>Offene Demo-Trades</h4><table class="table"><thead><tr><th>Model</th><th>Side</th><th>Entry</th><th>Current</th><th>SL</th><th>TP</th><th>uR</th></tr></thead><tbody>${openRows||'<tr><td colspan="7" class="muted">Keine offenen Positionen</td></tr>'}</tbody></table><h4>Letzte geschlossene Trades</h4><table class="table"><thead><tr><th>Model</th><th>Side</th><th>Exit</th><th>R</th><th>Zeit</th></tr></thead><tbody>${closedRows||'<tr><td colspan="5" class="muted">Noch keine geschlossenen Trades</td></tr>'}</tbody></table>`}
function arrLines(){const m=state.selectedModel,a=state.snapshot?.arrays||m?.arrays||{};const lines=[];const push=(label,v,col,dash=true)=>{if(v!=null&&isFinite(Number(v)))lines.push({label,v:Number(v),col,dash})};push("ENTRY",a.entry??m?.entry,"#5fa9ff");push("SL",a.stop??m?.sl,"#ff6575");push("TP",a.target??m?.tp,"#2fcf8b");if(state.pdOn){push("PDH",state.pd.PDH,"#657790");push("PDL",state.pd.PDL,"#657790");push("PWH",state.pd.PWH,"#7e6ac7");push("PWL",state.pd.PWL,"#7e6ac7");push("PMH",state.pd.PMH,"#9a6c9b");push("PML",state.pd.PML,"#9a6c9b");push("Ref H",a.reference_high,"#8c78d8");push("Ref L",a.reference_low,"#8c78d8");push("OTE H",a.zone_high,"#6d7fd1");push("OTE L",a.zone_low,"#6d7fd1");push("iFVG H",a.ifvg_high,"#bb7f4b");push("iFVG L",a.ifvg_low,"#bb7f4b");push("Prev H",a.prev_high,"#6f8198");push("Prev L",a.prev_low,"#6f8198")}return lines}
function visibleBars(){const n=state.bars.length;if(!n){state.futureSpace=0;return[]}const slots=Math.max(20,Math.round(state.viewCount)),future=Math.max(0,Math.min(Math.round(slots*.45),-Math.round(state.offset))),past=Math.max(0,Math.round(state.offset)),end=Math.max(0,Math.min(n,n-past)),count=Math.max(0,Math.min(slots-future,end)),start=Math.max(0,end-count);state.futureSpace=future;return state.bars.slice(start,end)}
function chartGeom(){const host=$("#chartHost"),w=Math.max(300,host.clientWidth),h=Math.max(160,host.clientHeight),axisW=72,axisH=30;return{w,h,axisW,axisH,left:0,right:Math.max(160,w-axisW),top:18,bottom:Math.max(80,h-axisH)}}
function basePriceRange(b){let lo=Math.min(...b.map(z=>Number(z.l))),hi=Math.max(...b.map(z=>Number(z.h)));const center=(lo+hi)/2,span=Math.max(hi-lo,Math.abs(center)*.001,1e-6),guard=Math.max(span*6,Math.abs(center)*.06,1);for(const l of arrLines()){if(Math.abs(l.v-center)<=guard){lo=Math.min(lo,l.v);hi=Math.max(hi,l.v)}}const pad=Math.max((hi-lo)*.08,span*.08,1e-6);return{lo:lo-pad,hi:hi+pad}}
function draw(){
 const cv=$("#chart"),g=chartGeom(),{w,h,right,top,bottom}=g,dpr=devicePixelRatio||1;cv.width=w*dpr;cv.height=h*dpr;cv.style.width=w+"px";cv.style.height=h+"px";const x=cv.getContext("2d");x.scale(dpr,dpr);x.clearRect(0,0,w,h);const b=visibleBars();if(!b.length){$("#chartEmpty").style.display="grid";return}$("#chartEmpty").style.display="none";
 const base=basePriceRange(b),baseCenter=(base.lo+base.hi)/2,baseSpan=Math.max(base.hi-base.lo,1e-9),span=baseSpan/Math.max(.2,state.yZoom),lo=baseCenter-span/2,hi=baseCenter+span/2,sy=v=>top+(hi-v)/(hi-lo)*(bottom-top),plotW=right,slots=Math.max(20,Math.round(state.viewCount)),step=plotW/slots,bw=Math.max(2,Math.min(9,step*.66));
 x.strokeStyle="#182435";x.lineWidth=1;x.font="10px Segoe UI";for(let i=0;i<=6;i++){const y=top+(bottom-top)*i/6;x.beginPath();x.moveTo(0,y);x.lineTo(right,y);x.stroke();const pv=hi-(hi-lo)*i/6;x.fillStyle="#8292a7";x.fillText(fmt(pv,2),right+8,y+3)}for(let i=1;i<10;i++){const xx=i*right/10;x.beginPath();x.moveTo(xx,top);x.lineTo(xx,bottom);x.stroke()}x.strokeStyle="#2a3a4d";x.beginPath();x.moveTo(right,0);x.lineTo(right,h);x.moveTo(0,bottom);x.lineTo(w,bottom);x.stroke();
 if(state.sessions&&state.mode==="live"){x.fillStyle="rgba(70,145,220,.035)";x.fillRect(right*.58,top,right*.10,bottom-top)}
 b.forEach((z,i)=>{const cx=i*step+step/2,up=z.c>=z.o,col=up?"#2bc889":"#ff6171";x.strokeStyle=col;x.fillStyle=col;x.setLineDash([]);x.beginPath();x.moveTo(cx,sy(z.h));x.lineTo(cx,sy(z.l));x.stroke();const y1=sy(Math.max(z.o,z.c)),y2=sy(Math.min(z.o,z.c));if(y2>=top&&y1<=bottom)x.fillRect(cx-bw/2,Math.max(top,y1),bw,Math.max(1,Math.min(bottom,y2)-Math.max(top,y1)))});
 for(const l of arrLines()){const y=sy(l.v);if(y<top-1||y>bottom+1)continue;x.strokeStyle=l.col;x.fillStyle=l.col;x.setLineDash(l.dash?[5,5]:[]);x.beginPath();x.moveTo(0,y);x.lineTo(right,y);x.stroke();x.setLineDash([]);x.fillText(`${l.label} ${fmt(l.v,2)}`,Math.max(5,right-108),y-3)}
 const ticks=5;x.fillStyle="#77889e";for(let i=0;i<ticks;i++){const idx=Math.round(i*(b.length-1)/(ticks-1)),z=b[idx],xx=idx*step+step/2;x.fillText(iso(z.t),Math.max(2,Math.min(right-60,xx-28)),h-9)}
 const last=Number(b.at(-1).c),ly=sy(last);if(ly>=top&&ly<=bottom){x.strokeStyle="#6aa9df";x.setLineDash([2,3]);x.beginPath();x.moveTo(0,ly);x.lineTo(right,ly);x.stroke();x.setLineDash([]);x.fillStyle="#173a57";x.fillRect(right+3,ly-9,g.axisW-6,18);x.fillStyle="#b9ddff";x.fillText(fmt(last,2),right+8,ly+4)}
  if(state.mode==="trade_replay"&&state.tradeReplay?.markers){
   const replayMs=v=>{if(v==null)return null;const n=Number(v);if(Number.isFinite(n)&&n>0)return n>1e12?n:n*1000;const d=Date.parse(v);return Number.isFinite(d)?d:null};
   const replayBarMs=z=>replayMs(z?.t);
   const replayMarkers=[["ENTRY",replayMs(state.tradeReplay.markers.entry_ms),"#5fa9ff"],["EXIT",replayMs(state.tradeReplay.markers.exit_ms),Number(state.tradeReplay.outcome_r)>=0?"#2fcf8b":"#ff6575"]];
   for(const [label,t,col] of replayMarkers){
    if(!t)continue;let idx=-1,best=Infinity;b.forEach((z,i)=>{const zt=replayBarMs(z);if(zt==null)return;const d=Math.abs(zt-t);if(d<best){best=d;idx=i}});
    if(idx<0)continue;const xx=idx*step+step/2;x.strokeStyle=col;x.fillStyle=col;x.setLineDash([4,4]);x.beginPath();x.moveTo(xx,top);x.lineTo(xx,bottom);x.stroke();x.setLineDash([]);x.fillRect(Math.max(2,xx-22),top+4,44,16);x.fillStyle="#08111a";x.fillText(label,Math.max(5,xx-16),top+15);
   }
  }
 if(state.hover!=null&&state.hover>=0&&state.hover<b.length){const i=state.hover,z=b[i],cx=i*step+step/2,cy=sy(z.c);x.strokeStyle="#607188";x.setLineDash([3,4]);x.beginPath();x.moveTo(cx,top);x.lineTo(cx,bottom);if(cy>=top&&cy<=bottom){x.moveTo(0,cy);x.lineTo(right,cy)}x.stroke();x.setLineDash([]);$("#ohlcText").textContent=`O ${fmt(z.o,2)}  H ${fmt(z.h,2)}  L ${fmt(z.l,2)}  C ${fmt(z.c,2)}`;$("#cursorTime").textContent=iso(z.t)}
}
function chartMouse(e){const rect=$("#chart").getBoundingClientRect(),b=visibleBars(),g=chartGeom(),mx=e.clientX-rect.left,my=e.clientY-rect.top,step=g.right/Math.max(20,Math.round(state.viewCount));$("#chart").style.cursor=mx>=g.right?"ns-resize":my>=g.bottom?"ew-resize":state.drag?"grabbing":"crosshair";if(!b.length||mx>=g.right||my>=g.bottom){state.hover=null;draw();return}const idx=Math.floor(mx/step);state.hover=idx>=0&&idx<b.length?idx:null;draw()}
function wheel(e){e.preventDefault();const rect=$("#chart").getBoundingClientRect(),g=chartGeom(),mx=e.clientX-rect.left;if(mx>=g.right){state.yZoom=Math.max(.2,Math.min(8,state.yZoom*(e.deltaY>0?.9:1.1)))}else{const dir=e.deltaY>0?1:-1;state.viewCount=Math.max(20,Math.min(500,state.viewCount+dir*Math.max(5,Math.round(state.viewCount*.1))));const maxFuture=Math.max(8,Math.round(state.viewCount*.35)),maxPast=Math.max(0,state.bars.length-Math.min(state.viewCount,state.bars.length));state.offset=Math.max(-maxFuture,Math.min(maxPast,state.offset))}draw()}
function dragStart(e){const rect=$("#chart").getBoundingClientRect(),g=chartGeom(),mx=e.clientX-rect.left,my=e.clientY-rect.top;if(mx>=g.right)state.drag={mode:"price",y:e.clientY,zoom:state.yZoom};else if(my>=g.bottom)state.drag={mode:"time",x:e.clientX,count:state.viewCount,offset:state.offset};else state.drag={mode:"pan",x:e.clientX,offset:state.offset};$("#chart").style.cursor=state.drag.mode==="price"?"ns-resize":state.drag.mode==="time"?"ew-resize":"grabbing"}
function dragMove(e){if(!state.drag)return;const host=$("#chartHost");if(state.drag.mode==="price"){const dy=e.clientY-state.drag.y;state.yZoom=Math.max(.2,Math.min(8,state.drag.zoom*Math.exp(dy*.008)))}else if(state.drag.mode==="time"){const dx=e.clientX-state.drag.x;state.viewCount=Math.max(20,Math.min(500,Math.round(state.drag.count*Math.exp(-dx*.007))));const maxFuture=Math.max(8,Math.round(state.viewCount*.35)),maxPast=Math.max(0,state.bars.length-Math.min(state.viewCount,state.bars.length));state.offset=Math.max(-maxFuture,Math.min(maxPast,state.drag.offset))}else{const pxPer=Math.max(2,(host.clientWidth-72)/Math.max(1,state.viewCount)),delta=Math.round((e.clientX-state.drag.x)/pxPer),maxFuture=Math.max(8,Math.round(state.viewCount*.35)),maxPast=Math.max(0,state.bars.length-Math.min(state.viewCount,state.bars.length));state.offset=Math.max(-maxFuture,Math.min(maxPast,state.drag.offset+delta))}draw()}
function dragEnd(){state.drag=null;$("#chart").style.cursor="crosshair"}
function fit(){state.offset=0;state.futureSpace=0;state.viewCount=Math.min(140,Math.max(40,state.bars.length));state.yZoom=1;draw()}
function setupSplit(id,varName,type){const el=$(id);if(!el)return;let start,initial;el.onmousedown=e=>{e.preventDefault();start=type==="h"?e.clientY:e.clientX;initial=parseFloat(getComputedStyle(document.documentElement).getPropertyValue(varName));const move=ev=>{let v=initial;if(varName==="--left")v+=ev.clientX-start;if(varName==="--right")v-=ev.clientX-start;if(varName==="--bottom")v-=ev.clientY-start;v=Math.max(varName==="--bottom"?40:0,Math.min(varName==="--bottom"?520:560,v));document.documentElement.style.setProperty(varName,v+"px");draw()};const up=()=>{document.removeEventListener("mousemove",move);document.removeEventListener("mouseup",up)};document.addEventListener("mousemove",move);document.addEventListener("mouseup",up)}}
document.querySelectorAll(".marketbar button").forEach(b=>b.onclick=()=>setMarket(b.dataset.market));document.querySelectorAll(".tfbar button").forEach(b=>b.onclick=()=>setTF(b.dataset.tf));document.querySelectorAll(".quotes>div").forEach(d=>d.onclick=()=>setMarket(d.dataset.goto));document.querySelectorAll(".workspace-nav [data-workspace-view]").forEach(b=>b.onclick=()=>setWorkspaceView(b.dataset.workspaceView));
$("#archiveSearch").oninput=renderArchive;$("#archiveStage").onchange=renderArchive;$("#backLive").onclick=backLive;$("#backOutcome").onclick=backOutcomes;$("#liveModeBtn").onclick=backLive;$("#fitBtn").onclick=fit;$("#pdBtn").onclick=()=>{state.pdOn=!state.pdOn;$("#pdBtn").classList.toggle("active",state.pdOn);draw()};$("#sessionsBtn").onclick=()=>{state.sessions=!state.sessions;$("#sessionsBtn").classList.toggle("active",state.sessions);draw()};$("#leftHide").onclick=()=>{document.body.classList.toggle("left-collapsed");setTimeout(draw,30)};$("#rightHide").onclick=()=>{document.body.classList.toggle("right-collapsed");setTimeout(draw,30)};if($("#bottomHide"))$("#bottomHide").onclick=()=>{document.body.classList.toggle("bottom-collapsed");setTimeout(draw,30)};
$("#alertsBtn").onclick=async()=>{if(!("Notification" in window)){toast("Browser unterstützt keine Notifications.");return}const p=await Notification.requestPermission();state.alerts=p==="granted";$("#alertsBtn").classList.toggle("active",state.alerts);toast(state.alerts?"Alerts aktiviert":"Alerts nicht erlaubt")};
const cv=$("#chart");cv.addEventListener("mousemove",chartMouse);cv.addEventListener("mouseleave",()=>{if(!state.drag){state.hover=null;cv.style.cursor="crosshair";draw()}});cv.addEventListener("wheel",wheel,{passive:false});cv.addEventListener("mousedown",dragStart);cv.addEventListener("dblclick",fit);window.addEventListener("mousemove",dragMove);window.addEventListener("mouseup",dragEnd);window.addEventListener("resize",draw);
setupSplit("#splitLeft","--left","v");setupSplit("#splitRight","--right","v");
setWorkspaceView("desk");bootstrap();loadBars();loadPD();setInterval(pollModels,2500);setInterval(()=>{if(state.mode==="live")loadBars()},5000);setInterval(pollResearch,5000);setInterval(pollPaper,5000);setInterval(()=>{refreshArchive();refreshOutcomes()},15000);