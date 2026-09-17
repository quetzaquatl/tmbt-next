// TMBT Next compatibility + live-desk hardening for the original Studio 4.6 pipeline.
// The UI stays modern, while data semantics remain the original ones:
// Twelve QQQ -> NQ context, Twelve SPY -> ES context, Twelve XAU/USD -> XAU.

let originalFeedFresh = null;
let originalFeedMeta = null;
let feedStatus = {};
let lastBarSignature = "";
let loadedChartKey = "";
let modelRenderSignature = "";
let signalRenderSignature = "";
let selectedModelSignature = "";
const modelStages = {};

function ageText(v){
  const n=Number(v);
  if(!isFinite(n))return "?";
  if(n<120)return `${Math.max(0,Math.round(n))}s`;
  if(n<7200)return `${Math.round(n/60)}m`;
  if(n<172800)return `${(n/3600).toFixed(1)}h`;
  return `${(n/86400).toFixed(1)}d`;
}

function feedClass(meta){
  if(!meta || !meta.ok)return "bad";
  return meta.stale ? "bad" : "ok";
}

function enforceOriginalFeedHealth(){
  const meta = feedStatus[state.market] || originalFeedMeta;
  if(meta){
    originalFeedFresh = meta.stale === true ? false : !!(meta.ok ?? state.bars.length);
  }
  if(originalFeedFresh === null) return;
  const ld = document.querySelector("#liveDot");
  if(ld){
    const wanted = originalFeedFresh ? "ok" : "bad";
    if(ld.className !== wanted) ld.className = wanted;
  }
  const btn = document.querySelector("#liveModeBtn");
  if(btn){
    btn.textContent = originalFeedFresh ? "● LIVE" : "⚠ STALE";
    btn.classList.toggle("active", originalFeedFresh);
    btn.classList.toggle("stale", !originalFeedFresh);
  }
  const badge=document.querySelector("#feedBadge");
  if(badge){
    const age=meta?.age_seconds;
    badge.textContent=originalFeedFresh?`LIVE ${ageText(age)}`:`STALE ${ageText(age)}`;
    badge.className=`feed-badge ${originalFeedFresh?"ok":"bad"}`;
  }
}

const liveDotNode = document.querySelector("#liveDot");
if(liveDotNode){
  new MutationObserver(enforceOriginalFeedHealth).observe(liveDotNode,{attributes:true,attributeFilter:["class"]});
}

function resetInspectorUi(){
  state.selectedModel=null;
  selectedModelSignature="";
  const i=document.querySelector("#inspector");
  if(i){i.className="inspector empty-inspector";i.innerHTML='<span class="pill idle">NO SETUP</span><h3>Kein Modell ausgewählt</h3><p>Links ein Modell anklicken.</p>'}
  for(const id of ["#iEntry","#iStop","#iTarget","#iRR"]){const e=document.querySelector(id);if(e)e.textContent="—"}
  const c=document.querySelector("#criteria");if(c)c.innerHTML="<p>—</p>";
  const l=document.querySelector("#logic");if(l)l.innerHTML="<p>—</p>";
  const ss=document.querySelector("#selectedSetup");if(ss)ss.textContent="—";
  const st=document.querySelector("#selectedState");if(st)st.textContent="—";
}

// Manual market changes must not leave setup levels from another instrument on
// the chart. This was easy to miss in the first preview and is dangerous in a
// live decision desk.
setMarket = function(m){
  if(state.selectedModel && String(state.selectedModel.market)!==String(m))resetInspectorUi();
  state.market=m;
  state.source=null;
  document.querySelectorAll(".marketbar button").forEach(b=>b.classList.toggle("active",b.dataset.market===m));
  state.viewCount=140;
  resetChartScale();
  loadedChartKey="";
  lastBarSignature="";
  loadBars(true);
  loadPD();
  enforceOriginalFeedHealth();
};

setTF = function(tf){
  state.tf=tf;
  document.querySelectorAll(".tfbar button").forEach(b=>b.classList.toggle("active",b.dataset.tf===tf));
  state.viewCount=140;
  resetChartScale();
  loadedChartKey="";
  lastBarSignature="";
  loadBars(true);
};

function barsSignature(bars){
  if(!bars?.length)return "0";
  const z=bars[bars.length-1];
  return [bars.length,z.t,z.o,z.h,z.l,z.c].join("|");
}

// Replace the base loader: no loading overlay on every 5-second refresh, no
// needless redraw when nothing changed, and feed freshness is explicit.
loadBars = async function(force=false){
  if(state.mode === "snapshot") return;
  const key=`${state.market}|${state.tf}`;
  document.querySelector("#chartTitle").textContent = `${state.market} · ${state.tf}`;
  const empty = document.querySelector("#chartEmpty");
  const firstLoad = force || loadedChartKey!==key || !state.bars.length;
  if(firstLoad){
    empty.textContent = "Lade Original-Livefeed…";
    empty.style.display = "grid";
  }
  try{
    const d = await api(`/api/bars?market=${encodeURIComponent(state.market)}&tf=${encodeURIComponent(state.tf)}&limit=1500`);
    const nextBars=d.bars||[];
    const sig=barsSignature(nextBars);
    state.source=null;
    originalFeedMeta=d;
    originalFeedFresh=d.stale===true?false:nextBars.length>0;
    const sourceText=d.note||(d.provider?`${d.provider} · original live pipeline`:"kein Original-Feed");
    document.querySelector("#chartSource").textContent=sourceText;
    loadedChartKey=key;
    empty.style.display=nextBars.length?"none":"grid";
    if(nextBars.length){
      const p=nextBars.at(-1).c;
      const q=document.querySelector("#q"+state.market);if(q)q.textContent=fmt(p,2);
    }else{
      empty.textContent=d.note||"Keine Bars im Original-Livefeed";
    }
    if(force || sig!==lastBarSignature || !state.bars.length){
      state.bars=nextBars;
      lastBarSignature=sig;
      draw();
    }
    enforceOriginalFeedHealth();
  }catch(e){
    originalFeedFresh=false;
    originalFeedMeta={error:String(e),ok:false,stale:true};
    document.querySelector("#chartSource").textContent="Original-Livefeed nicht erreichbar";
    if(!state.bars.length){empty.style.display="grid";empty.textContent="Bars konnten nicht geladen werden"}
    enforceOriginalFeedHealth();
    log("Original-Livefeed Fehler: "+e);
  }
};

async function pollFeedStatus(){
  try{
    const d=await api("/api/feed-status");
    feedStatus=d.markets||{};
    for(const m of ["NQ","ES","XAU"]){
      const meta=feedStatus[m];
      const q=document.querySelector("#q"+m);
      if(q && meta?.price!=null)q.textContent=fmt(meta.price,2);
      const b=document.querySelector("#feed"+m);
      if(b){
        b.textContent=meta?.ok?(meta.stale?`STALE ${ageText(meta.age_seconds)}`:`LIVE ${ageText(meta.age_seconds)}`):"NO FEED";
        b.className=`feed-mini ${feedClass(meta)}`;
        b.title=meta?.note||"";
      }
    }
    enforceOriginalFeedHealth();
  }catch(e){
    log("Feed-Status Fehler: "+e);
  }
}

function compactModelSignature(models){
  return JSON.stringify((models||[]).map(m=>[m.id,m.status,m.side,m.entry,m.sl,m.tp,m.rr,m.message,m.event?.event_id]));
}

const baseRenderModels=renderModels;
renderModels=function(){
  syncSelectedModel(false);
  const sig=compactModelSignature(state.models);
  if(sig===modelRenderSignature)return;
  modelRenderSignature=sig;
  baseRenderModels();
};

const baseRenderSignals=renderSignals;
renderSignals=function(){
  const sig=compactModelSignature(state.models);
  if(sig===signalRenderSignature)return;
  signalRenderSignature=sig;
  baseRenderSignals();
};

function syncSelectedModel(redraw=true){
  if(!state.selectedModel || state.mode==="snapshot")return;
  const fresh=state.models.find(x=>String(x.id)===String(state.selectedModel.id));
  if(!fresh)return;
  const sig=JSON.stringify([fresh.status,fresh.side,fresh.entry,fresh.sl,fresh.tp,fresh.rr,fresh.message,fresh.arrays,fresh.criteria,fresh.logic]);
  state.selectedModel=fresh;
  if(sig!==selectedModelSignature){
    selectedModelSignature=sig;
    document.querySelector("#selectedSetup").textContent=fresh.name||"—";
    document.querySelector("#selectedState").textContent=`${fresh.status||"—"} · ${fresh.side||"—"}`;
    renderInspector(fresh);
    if(redraw)draw();
  }
}

function detectModelTransitions(){
  for(const m of state.models||[]){
    const id=String(m.id||m.name||"");
    const st=String(m.status||"").toUpperCase();
    const prev=modelStages[id];
    if(prev && prev!==st && ["SIGNAL","ARMED","CLOSED","EXPIRED"].includes(st)){
      const msg=`${m.name}: ${prev} → ${st}${m.side&&m.side!=="—"?` · ${m.side}`:""}`;
      toast(msg);
      if(state.alerts && "Notification" in window && Notification.permission==="granted")new Notification("TMBT Setup",{body:msg});
    }
    modelStages[id]=st;
  }
}

function renderDiagnostics(d){
  const host=document.querySelector("#systemView");if(!host)return;
  const markets=["NQ","ES","XAU"];
  let html='<div class="diag-head"><div><b>Original Pipeline Diagnostics</b><small>Feed, Workspace und Datenalter</small></div><button id="diagRefresh">Neu prüfen</button></div>';
  html+='<div class="diag-grid">';
  for(const m of markets){
    const f=d.feeds?.[m]?.["5m"]||{};
    html+=`<div class="diag-card ${f.stale?"stale":"fresh"}"><div class="model-row"><h4>${esc(m)}</h4><span class="pill ${f.stale?"expired":"signal"}">${f.stale?"STALE":"LIVE"}</span></div><b>${f.price==null?"—":fmt(f.price,2)}</b><small>${esc(f.note||"")}</small><p>5m last: ${esc(f.last_bar_utc||"—")}</p><p>source: ${esc(f.feed||"—")}</p></div>`;
  }
  html+='</div><h4>Timeframes</h4><table class="table diag-table"><thead><tr><th>Market</th><th>TF</th><th>Status</th><th>Price</th><th>Age</th><th>Feed</th><th>Last bar UTC</th></tr></thead><tbody>';
  for(const m of markets){for(const tf of ["5m","15m","1H","4H","1D"]){const f=d.feeds?.[m]?.[tf]||{};html+=`<tr><td>${m}</td><td>${tf}</td><td class="${f.stale?"bad":"good"}">${f.stale?"STALE":"LIVE"}</td><td>${f.price==null?"—":fmt(f.price,2)}</td><td>${ageText(f.age_seconds)}</td><td>${esc(f.feed||"—")}</td><td>${esc(f.last_bar_utc||"—")}</td></tr>`}}
  html+='</tbody></table><h4>Workspace</h4><div class="component-grid">';
  for(const [k,v] of Object.entries(d.components||{})){html+=`<div><span class="status-dot ${v.exists?"ok":"bad"}"></span><b>${esc(k)}</b><small>${v.exists?"vorhanden":"fehlt"}</small></div>`}
  html+=`</div><p class="diag-hint">${esc(d.hint||"")}</p>`;
  host.innerHTML=html;
  const r=document.querySelector("#diagRefresh");if(r)r.onclick=pollDiagnostics;
}

async function pollDiagnostics(){
  const host=document.querySelector("#systemView");
  if(host && !host.dataset.loaded)host.innerHTML='<div class="empty">Systemdiagnose läuft…</div>';
  try{const d=await api("/api/diagnostics");if(host)host.dataset.loaded="1";renderDiagnostics(d)}catch(e){if(host)host.innerHTML=`<div class="empty bad">Diagnose fehlgeschlagen: ${esc(e)}</div>`}
}

// Persist panel sizing/collapse state. The old preview forgot every layout after
// a restart, which made repeated live use unnecessarily tedious.
function saveLayout(){
  try{localStorage.setItem("tmbt-next-layout",JSON.stringify({left:getComputedStyle(document.documentElement).getPropertyValue("--left"),right:getComputedStyle(document.documentElement).getPropertyValue("--right"),bottom:getComputedStyle(document.documentElement).getPropertyValue("--bottom"),lc:document.body.classList.contains("left-collapsed"),rc:document.body.classList.contains("right-collapsed"),bc:document.body.classList.contains("bottom-collapsed")}))}catch{}
}
function restoreLayout(){
  try{const x=JSON.parse(localStorage.getItem("tmbt-next-layout")||"null");if(!x)return;if(x.left)document.documentElement.style.setProperty("--left",x.left);if(x.right)document.documentElement.style.setProperty("--right",x.right);if(x.bottom)document.documentElement.style.setProperty("--bottom",x.bottom);document.body.classList.toggle("left-collapsed",!!x.lc);document.body.classList.toggle("right-collapsed",!!x.rc);document.body.classList.toggle("bottom-collapsed",!!x.bc)}catch{}
}
restoreLayout();
window.addEventListener("mouseup",()=>setTimeout(saveLayout,20));
for(const id of ["#leftHide","#rightHide","#bottomHide"]){document.querySelector(id)?.addEventListener("click",()=>setTimeout(saveLayout,50))}

// System tab was added after the original event model; its normal tab switching
// still comes from app.js, this only starts the diagnostic request.
document.querySelector('[data-tab="system"]')?.addEventListener("click",pollDiagnostics);

// Useful desk shortcuts without stealing keystrokes from filter fields.
window.addEventListener("keydown",e=>{
  if(["INPUT","SELECT","TEXTAREA"].includes(document.activeElement?.tagName))return;
  if(e.key==="Escape" && state.mode==="snapshot")backLive();
  if(e.key.toLowerCase()==="f")fit();
  if(e.key==="1")setMarket("NQ");
  if(e.key==="2")setMarket("ES");
  if(e.key==="3")setMarket("XAU");
});

// Reload immediately through the hardened loader, then keep independent health
// and model-state watches. Base polling continues to serve paper/research data.
if(state.mode === "live"){
  loadBars(true);
  loadPD();
}
pollFeedStatus();
setInterval(pollFeedStatus,4000);
setInterval(()=>{syncSelectedModel(true);detectModelTransitions()},2600);
setInterval(enforceOriginalFeedHealth,500);
