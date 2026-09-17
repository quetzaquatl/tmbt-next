// Live-desk safety and parallel-model patch.
// Evaluation remains backend-driven; this layer monitors every model state in
// parallel, gates alerts on fresh market data and surfaces early formation.

const _compatSetMarket=setMarket;
setMarket=function(m){originalFeedMeta=null;originalFeedFresh=null;return _compatSetMarket(m)};
const _compatSetTF=setTF;
setTF=function(tf){originalFeedMeta=null;originalFeedFresh=null;return _compatSetTF(tf)};

const TF_STALE_SECONDS={"5m":20*60,"15m":45*60,"30m":75*60,"1h":3*60*60,"4h":9*60*60,"1d":48*60*60};
const TF_SECONDS={"5m":5*60,"15m":15*60,"30m":30*60,"1h":60*60,"4h":4*60*60,"1d":24*60*60};

function normTf(v){return String(v||"").trim().toLowerCase()}
function parseBarMs(v){
  if(v===null||v===undefined||v==="")return null;
  const n=Number(v);
  if(Number.isFinite(n))return n>1e12?n:n*1000;
  const p=Date.parse(String(v));
  return Number.isFinite(p)?p:null;
}
function clientBarAge(bars,tf){
  if(!bars?.length)return null;
  const z=bars[bars.length-1];
  let t=parseBarMs(z.close_t);
  if(t===null){
    t=parseBarMs(z.t);
    const sec=TF_SECONDS[normTf(tf)];
    if(t!==null&&sec)t+=sec*1000;
  }
  return t===null?null:Math.max(0,(Date.now()-t)/1000);
}
function isClientStale(bars,tf){
  const age=clientBarAge(bars,tf),limit=TF_STALE_SECONDS[normTf(tf)]??3*60*60;
  return {age,stale:age===null||age>limit,limit};
}

// Keep feed health tied to the chart actually shown. In particular this catches
// a shared SQLite file whose mtime is fresh because NQ/ES update while XAU rows
// themselves are old.
enforceOriginalFeedHealth=function(){
  const meta=originalFeedMeta||feedStatus[state.market];
  if(meta)originalFeedFresh=meta.stale===true?false:!!(meta.ok??state.bars.length);
  if(originalFeedFresh===null)return;
  const ld=document.querySelector("#liveDot");if(ld)ld.className=originalFeedFresh?"ok":"bad";
  const btn=document.querySelector("#liveModeBtn");if(btn){btn.textContent=originalFeedFresh?"● LIVE":"⚠ STALE";btn.classList.toggle("active",originalFeedFresh);btn.classList.toggle("stale",!originalFeedFresh)}
  const badge=document.querySelector("#feedBadge");if(badge){badge.textContent=originalFeedFresh?`LIVE ${ageText(meta?.age_seconds)}`:`STALE ${ageText(meta?.age_seconds)}`;badge.className=`feed-badge ${originalFeedFresh?"ok":"bad"}`}
};

function auditSelectedFeed(){
  if(state.mode!=="live"||!state.bars?.length)return;
  const c=isClientStale(state.bars,state.tf);
  if(!originalFeedMeta)originalFeedMeta={};
  if(c.age!==null)originalFeedMeta.age_seconds=c.age;
  if(c.stale){
    originalFeedMeta.stale=true;
    originalFeedMeta.ok=true;
    originalFeedFresh=false;
    const src=document.querySelector("#chartSource");
    if(src&&!String(src.textContent).includes("STALE BAR"))src.textContent=`${src.textContent} · STALE BAR ${ageText(c.age)}`;
  }
  enforceOriginalFeedHealth();
}

// app.js still contains a visual placeholder session rectangle. A false session
// marker is worse than no marker on a live desk, so keep it disabled until the
// actual NY/London timestamps are implemented.
state.sessions=false;
const sessionBtn=document.querySelector("#sessionsBtn");
if(sessionBtn){
  sessionBtn.classList.remove("active");
  sessionBtn.textContent="Sessions off";
  sessionBtn.title="Temporär deaktiviert: alte Preview-Markierung war nicht zeitbasiert.";
  sessionBtn.onclick=()=>toast("Session-Shading bleibt aus, bis NY/London-Zeiten exakt aus Bar-Timestamps gezeichnet werden.");
}

const formationMemory={};
const formationLastAlert={};
const EBP_MATRIX=[
  {market:"NQ",tf:"15m"},{market:"NQ",tf:"30m"},{market:"NQ",tf:"1H"},
  {market:"ES",tf:"15m"},{market:"ES",tf:"30m"},{market:"ES",tf:"1H"},
];

function criteriaStats(m){
  const rows=Array.isArray(m?.criteria)?m.criteria:[];
  let pass=0,fail=0,pending=0;
  for(const c of rows){
    if(typeof c==="string"){pass++;continue}
    const s=String(c?.status||"PENDING").toUpperCase();
    if(s==="PASS")pass++;else if(s==="FAIL")fail++;else pending++;
  }
  const total=pass+fail+pending;
  return {pass,fail,pending,total,ratio:total?pass/total:null};
}
function stageRank(stage){
  const s=String(stage||"").toUpperCase();
  if(s==="SIGNAL")return 3;
  if(s==="ARMED")return 2;
  if(s==="WATCH")return 1;
  return 0;
}
function marketFresh(market){
  const f=feedStatus[String(market||"").toUpperCase()];
  return !!(f?.ok&&!f?.stale);
}
function formationInfo(m){
  const stat=criteriaStats(m),stage=String(m?.status||"").toUpperCase();
  let rank=stageRank(stage);
  if(stat.ratio!==null&&!["CLOSED","EXPIRED"].includes(stage)){
    if(stat.ratio>=.50)rank=Math.max(rank,1);
    if(stat.ratio>=.75&&stat.fail===0)rank=Math.max(rank,2);
  }
  if(["CLOSED","EXPIRED"].includes(stage))rank=0;
  const pct=stat.ratio===null?null:Math.round(stat.ratio*100);
  let label=stage||"IDLE";
  if(rank===1&&!(["WATCH"].includes(stage)))label="FORMING";
  if(rank===2&&!(["ARMED"].includes(stage)))label="STRONG";
  if(rank===3)label="SIGNAL";
  const next=(Array.isArray(m?.criteria)?m.criteria:[]).find(c=>typeof c!=="string"&&String(c?.status||"").toUpperCase()!=="PASS");
  return {rank,label,pct,stats:stat,next};
}
function modelAlertText(m,info){
  const score=info.pct===null?"":` · ${info.pct}% (${info.stats.pass}/${info.stats.total})`;
  const side=m.side&&m.side!=="—"?` · ${m.side}`:"";
  const next=info.next?.label?` · next: ${info.next.label}`:"";
  return `${m.name} · ${info.label}${score}${side}${next}`;
}
function detectFormationAlerts(){
  for(const m of state.models||[]){
    const id=String(m.id||m.name||"");if(!id)continue;
    const info=formationInfo(m),fresh=marketFresh(m.market);
    const prev=formationMemory[id];
    if(prev===undefined){formationMemory[id]=info.rank;continue}
    formationMemory[id]=info.rank;
    if(!fresh||info.rank<=prev||info.rank<1)returnModelNoop();
    else{
      const key=`${id}:${info.rank}`;
      const now=Date.now();
      if(now-(formationLastAlert[key]||0)>10*60*1000){
        formationLastAlert[key]=now;
        const msg=modelAlertText(m,info);
        toast(msg);
        if(state.alerts&&"Notification" in window&&Notification.permission==="granted")new Notification("TMBT Model forming",{body:msg});
      }
    }
  }
}
function returnModelNoop(){return false}

function decorateModelCards(){
  for(const m of state.models||[]){
    const card=document.querySelector(`.model-card[data-id="${CSS.escape(String(m.id))}"]`);if(!card)continue;
    const info=formationInfo(m),fresh=marketFresh(m.market);
    card.classList.toggle("data-stale",!fresh);
    let chip=card.querySelector(".formation-chip");
    if(!chip){chip=document.createElement("span");chip.className="formation-chip";card.appendChild(chip)}
    if(!fresh){chip.textContent="DATA STALE";chip.className="formation-chip stale"}
    else if(info.pct!==null){chip.textContent=`${info.label} ${info.pct}%`;chip.className=`formation-chip r${info.rank}`}
    else{chip.textContent=info.label;chip.className=`formation-chip r${info.rank}`}
  }
}

const _deskBaseRenderInspector=renderInspector;
renderInspector=function(m,snap=null){
  _deskBaseRenderInspector(m,snap);
  if(!m)return;
  const info=formationInfo(m),fresh=marketFresh(m.market);
  const host=document.querySelector("#inspector");if(!host)return;
  let row=host.querySelector(".formation-status");if(!row){row=document.createElement("div");row.className="formation-status";host.appendChild(row)}
  const pct=info.pct===null?"—":`${info.pct}%`;
  row.innerHTML=`<div><span>Formation</span><b>${fresh?esc(info.label):"DATA STALE"}</b></div><div class="formation-track"><i style="width:${info.pct??0}%"></i></div><small>${pct}${info.stats.total?` · ${info.stats.pass}/${info.stats.total} Kriterien erfüllt`:""}</small>`;
  row.classList.toggle("stale",!fresh);
};

function normModelTf(v){const z=normTf(v);return z==="1h"?"1H":z}
function isEbp(m){return /\bEBP\b/i.test(String(m?.name||m?.label||m?.id||""))}
function ebpFound(market,tf){
  const want=normModelTf(tf);
  return (state.models||[]).find(m=>String(m.market).toUpperCase()===market&&isEbp(m)&&normModelTf(m.tf)===want);
}
function radarRow(m){
  const info=formationInfo(m),fresh=marketFresh(m.market),next=info.next?.label||info.next?.name||"—";
  const score=info.pct===null?"—":`${info.pct}%`;
  return `<tr class="clickable ${fresh?"":"radar-stale"}" data-radar-id="${esc(m.id)}"><td>${esc(m.name)}</td><td>${esc(m.market)}</td><td>${esc(m.tf)}</td><td><span class="pill ${String(m.status).toLowerCase()}">${esc(m.status)}</span></td><td>${fresh?'<span class="good">LIVE</span>':'<span class="bad">STALE</span>'}</td><td><b>${score}</b></td><td>${info.stats.total?`${info.stats.pass}/${info.stats.total}`:"—"}</td><td class="muted">${esc(next)}</td></tr>`;
}
function renderRadar(){
  const host=document.querySelector("#radarView");if(!host)return;
  const models=[...(state.models||[])].sort((a,b)=>formationInfo(b).rank-formationInfo(a).rank);
  const active=models.filter(m=>formationInfo(m).rank>0&&marketFresh(m.market)).length;
  const stale=models.filter(m=>!marketFresh(m.market)).length;
  let html=`<div class="radar-head"><div><b>Parallel Model Radar</b><small>${models.length} Backend-Modelle · ${active} forming/active · ${stale} data-gated</small></div><div class="radar-legend"><span class="good">fresh feed</span><span class="bad">stale = alerts blocked</span></div></div>`;
  html+='<table class="table radar-table"><thead><tr><th>Model</th><th>Market</th><th>TF</th><th>Stage</th><th>Data</th><th>Formation</th><th>Pass</th><th>Nächster Punkt</th></tr></thead><tbody>';
  html+=models.map(radarRow).join("")||'<tr><td colspan="8" class="muted">Keine Modelle vom Live-Monitor geliefert.</td></tr>';
  html+='</tbody></table><h4 class="matrix-title">EBP Intraday Matrix · gewünschte Instanzen</h4><div class="ebp-matrix">';
  for(const x of EBP_MATRIX){const m=ebpFound(x.market,x.tf),fresh=marketFresh(x.market);html+=`<div class="matrix-cell ${m?"present":"missing"}"><b>${x.market} · ${x.tf}</b><span>${m?esc(m.status||"RUNNING"):"ENGINE MISSING"}</span><small>${m?(fresh?"feed live":"feed stale"):"noch nicht vom Backend-Monitor geliefert"}</small></div>`}
  html+='</div>';
  host.innerHTML=html;
  host.querySelectorAll("tr[data-radar-id]").forEach(r=>r.onclick=()=>selectModel(r.dataset.radarId));
}

document.querySelector('[data-tab="radar"]')?.addEventListener("click",renderRadar);

// Safety: do not let an old XAU candle continue to display a green LIVE state.
setInterval(auditSelectedFeed,750);
setInterval(()=>{detectFormationAlerts();decorateModelCards();renderRadar()},1200);
setTimeout(()=>{auditSelectedFeed();decorateModelCards();renderRadar();draw()},150);
