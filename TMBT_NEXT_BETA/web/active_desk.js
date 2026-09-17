// TMBT Next v0.9.14 — Active Desk
// Removes duplicated operational model lists. The Active tab is the only live
// queue; Monitor contains background/non-actionable models only.
(function(){
  const ACTIVE_STAGE_RE=/^(SIGNAL|ARMED|WATCH|FORMING|STRONG|READY|TRIGGERED)$/i;
  const DEAD_STAGE_RE=/^(IDLE|WAIT_SESSION|EXPIRED|CLOSED|BLOCKED|NO_SETUP)$/i;

  function adProxy(m){
    if(m?.proxy===true)return true;
    const z=String(m?.name||m?.label||m?.id||"");
    return /QQQ\s*proxy|SPY\s*proxy/i.test(z);
  }
  function adFresh(m){
    try{return typeof marketFresh==="function"?!!marketFresh(m?.market):true}catch{return true}
  }
  function adStage(m){return String(m?.status||m?.stage||"").trim().toUpperCase()}
  function adActive(m){
    const s=adStage(m);
    if(!s||DEAD_STAGE_RE.test(s)||adProxy(m)||!adFresh(m))return false;
    return ACTIVE_STAGE_RE.test(s);
  }
  function adBlocked(m){return adProxy(m)||!adFresh(m)||adStage(m)==="BLOCKED"}
  function adBackgroundReason(m){
    if(adProxy(m))return "Proxy / delayed · live execution blocked";
    if(!adFresh(m))return "Data stale · alerts blocked";
    const s=adStage(m);
    if(s==="WAIT_SESSION")return "Außerhalb Session / wartet auf Zeitfenster";
    if(s==="EXPIRED"||s==="CLOSED")return "Nicht mehr aktiv";
    if(s==="IDLE")return "Kein aktuelles Setup";
    return m?.message||"Background monitor";
  }
  function adMs(v){
    if(v===null||v===undefined||v==="")return null;
    const n=Number(v);if(Number.isFinite(n))return n>1e12?n:n*1000;
    const p=Date.parse(String(v));return Number.isFinite(p)?p:null;
  }
  function adEventMs(m){
    const e=m?.event||{};
    const signal=/^SIGNAL$/i.test(adStage(m));
    return adMs(signal?(e.touch_ms??e.trigger_ms??e.event_ms??e.event_time_utc):(e.event_ms??e.event_time_utc??e.touch_ms));
  }
  function adTimeParts(ms){
    if(!ms)return {local:"—",ny:"—",date:"—"};
    const d=new Date(ms);
    const local=d.toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"});
    const date=d.toLocaleDateString([], {day:"2-digit",month:"2-digit"});
    let ny="—";
    try{ny=new Intl.DateTimeFormat("de-DE",{timeZone:"America/New_York",hour:"2-digit",minute:"2-digit",hour12:false}).format(d)}catch{}
    return {local,ny,date};
  }
  function adTimeCell(m){
    const ms=adEventMs(m),t=adTimeParts(ms);
    if(!ms)return '<span class="muted">—</span>';
    return `<span class="event-time"><b>${esc(t.local)}</b><small>NY ${esc(t.ny)} · ${esc(t.date)}</small></span>`;
  }
  function adInfo(m){
    try{return typeof formationInfo==="function"?formationInfo(m):{pct:null,stats:{},next:null,label:adStage(m)}}catch{return {pct:null,stats:{},next:null,label:adStage(m)}}
  }

  // Left rail is markets only. There is intentionally no second live-model list.
  renderModels=function(){
    const box=document.querySelector("#modelList");if(box)box.innerHTML="";
  };

  // Operational queue: only models that can matter right now.
  renderSignals=function(){
    const host=document.querySelector("#signalsTable");if(!host)return;
    const all=state.models||[];
    const active=all.filter(adActive).sort((a,b)=>{
      const order={SIGNAL:4,ARMED:3,READY:2,WATCH:1,FORMING:1,STRONG:2,TRIGGERED:4};
      return (order[adStage(b)]||0)-(order[adStage(a)]||0);
    });
    const blocked=all.filter(adBlocked).length;
    const background=all.length-active.length;
    let html=`<div class="active-desk-head"><div><b>Active Now</b><small>nur zeitlich relevante, frische und ausführbare Modelle</small></div><div class="active-counts"><span class="hot">${active.length} active</span><span>${background} background</span><span class="blocked">${blocked} blocked</span></div></div>`;
    if(!active.length){
      html+='<div class="active-empty"><b>Aktuell kein scharfes Modell.</b>WAIT_SESSION, IDLE, EXPIRED, Proxy und stale Feeds bleiben im Monitor.</div>';
      host.innerHTML=html;return;
    }
    const rows=active.map(m=>{
      const info=adInfo(m),pct=info.pct==null?"—":`${info.pct}%`,next=info.next?.label||m.message||"—";
      const cls=`active-${adStage(m).toLowerCase()}`;
      return `<tr class="clickable ${cls}" data-id="${esc(m.id)}"><td><b>${esc(m.name)}</b><small style="display:block;color:#70849c">${esc(m.market)} · ${esc(m.tf)}</small></td><td><span class="pill ${adStage(m).toLowerCase()}">${esc(adStage(m))}</span></td><td>${esc(m.side||"—")}</td><td>${adTimeCell(m)}</td><td>${fmt(m.entry,4)}</td><td>${fmt(m.sl,4)}</td><td>${fmt(m.tp,4)}</td><td><b>${pct}</b></td><td class="muted">${esc(next)}</td></tr>`;
    }).join("");
    html+=`<table class="table active-table"><thead><tr><th>Model</th><th>Stage</th><th>Side</th><th>Signal / Setup</th><th>Entry</th><th>SL</th><th>TP</th><th>Formation</th><th>Nächster Punkt</th></tr></thead><tbody>${rows}</tbody></table>`;
    host.innerHTML=html;
    host.querySelectorAll("tr[data-id]").forEach(r=>r.onclick=()=>selectModel(r.dataset.id));
  };

  // Background monitor: deliberately excludes Active Now to avoid duplication.
  renderRadar=function(){
    const host=document.querySelector("#radarView");if(!host)return;
    const bg=(state.models||[]).filter(m=>!adActive(m));
    let html=`<div class="background-head"><div><b>Background Monitor</b><small>außerhalb Session · idle · expired · proxy · stale</small></div><span class="muted">${bg.length} Modelle</span></div>`;
    const rows=bg.map(m=>{
      const info=adInfo(m),blocked=adBlocked(m),wait=adStage(m)==="WAIT_SESSION"||adStage(m)==="IDLE";
      const stateLabel=blocked?"BLOCKED":wait?"WAIT":"BACKGROUND";
      const stateClass=blocked?"blocked":wait?"wait":"ok";
      const pct=info.pct==null?"—":`${info.pct}%`;
      return `<tr class="clickable" data-radar-id="${esc(m.id)}"><td><b>${esc(m.name)}</b></td><td>${esc(m.market)}</td><td>${esc(m.tf)}</td><td><span class="pill ${adStage(m).toLowerCase()}">${esc(adStage(m)||"—")}</span></td><td><span class="monitor-state ${stateClass}">${stateLabel}</span></td><td>${pct}</td><td class="muted">${esc(adBackgroundReason(m))}</td></tr>`;
    }).join("");
    html+=`<table class="table monitor-table"><thead><tr><th>Model</th><th>Market</th><th>TF</th><th>Engine Stage</th><th>Desk</th><th>Formation</th><th>Warum nicht aktiv?</th></tr></thead><tbody>${rows||'<tr><td colspan="7" class="muted">Kein Background-Modell.</td></tr>'}</tbody></table>`;
    host.innerHTML=html;
    host.querySelectorAll("tr[data-radar-id]").forEach(r=>r.onclick=()=>selectModel(r.dataset.radarId));
  };

  // Add explicit signal/setup timestamp to the inspector.
  const adBaseInspector=renderInspector;
  renderInspector=function(m,snap=null){
    adBaseInspector(m,snap);
    if(!m)return;
    const host=document.querySelector("#inspector");if(!host)return;
    host.querySelector(".signal-time-row")?.remove();
    const ms=adEventMs(m),t=adTimeParts(ms),kind=/^SIGNAL$/i.test(adStage(m))?"Signalzeit":"Setup-Zeit";
    if(ms){
      const row=document.createElement("div");row.className="signal-time-row";
      row.innerHTML=`<span>${kind}</span><b>${esc(t.local)} lokal</b><small>NY ${esc(t.ny)} · ${esc(t.date)}</small>`;
      host.appendChild(row);
    }
  };

  // Focus the event candle once when a model is selected.
  const adBaseLoadBars=loadBars;
  loadBars=async function(){
    await adBaseLoadBars.apply(this,arguments);
    if(!state._activeDeskFocusEvent)return;
    state._activeDeskFocusEvent=false;
    const ms=adEventMs(state.selectedModel);if(!ms||!state.bars?.length)return;
    let idx=0,best=Infinity;
    state.bars.forEach((b,i)=>{const d=Math.abs((adMs(b.t)||0)-ms);if(d<best){best=d;idx=i}});
    const n=state.bars.length,slots=Math.max(40,Math.round(state.viewCount||140));
    const back=n-1-idx;
    if(back>Math.round(slots*.75))state.offset=Math.max(0,back-Math.round(slots*.25));
    draw();
  };
  const adBaseSelect=selectModel;
  selectModel=function(id){
    state._activeDeskFocusEvent=true;
    adBaseSelect(id);
    setTimeout(()=>{
      const m=state.selectedModel,ms=adEventMs(m);if(!m||!ms)return;
      const t=adTimeParts(ms),kind=/^SIGNAL$/i.test(adStage(m))?"SIGNAL":"SETUP";
      const s=document.querySelector("#selectedState");if(s)s.textContent=`${adStage(m)} · ${m.side||"—"} · ${kind} ${t.local} / NY ${t.ny}`;
    },0);
  };

  // Chart annotation: mark the candle that created/triggered the selected model.
  const adBaseDraw=draw;
  draw=function(){
    adBaseDraw();
    const m=state.selectedModel,ms=adEventMs(m);if(!m||!ms||!state.bars?.length)return;
    const b=visibleBars();if(!b.length)return;
    let idx=-1,best=Infinity;
    b.forEach((z,i)=>{
      const t=adMs(z.t);if(t===null)return;
      const close=adMs(z.close_t);
      if(t<=ms&&(close===null||ms<close)){idx=i;best=0;return}
      const d=Math.abs(t-ms);if(d<best){best=d;idx=i}
    });
    if(idx<0)return;
    const tfSec=(typeof TF_SECONDS!=="undefined"?TF_SECONDS[normTf(state.tf)]:null)||3600;
    if(best>tfSec*2500)return;
    const cv=document.querySelector("#chart"),g=chartGeom(),ctx=cv.getContext("2d");
    const slots=Math.max(20,Math.round(state.viewCount)),step=g.right/slots,cx=idx*step+step/2;
    const signal=/^SIGNAL$/i.test(adStage(m)),label=signal?"SIGNAL":"SETUP",t=adTimeParts(ms);
    ctx.save();
    ctx.setLineDash([4,4]);ctx.lineWidth=1.2;ctx.strokeStyle=signal?"rgba(52,211,153,.95)":"rgba(96,165,250,.92)";
    ctx.beginPath();ctx.moveTo(cx,g.top);ctx.lineTo(cx,g.bottom);ctx.stroke();
    ctx.setLineDash([]);ctx.fillStyle=signal?"rgba(52,211,153,.10)":"rgba(96,165,250,.09)";
    ctx.fillRect(Math.max(0,cx-step*.48),g.top,Math.max(3,step*.96),g.bottom-g.top);
    const txt=`${label} · ${t.local} · NY ${t.ny}`;
    ctx.font="600 10px Segoe UI";const tw=ctx.measureText(txt).width+12;
    const lx=Math.max(4,Math.min(g.right-tw-4,cx+6)),ly=g.top+7;
    ctx.fillStyle="rgba(7,15,24,.92)";ctx.fillRect(lx,ly,tw,20);
    ctx.strokeStyle=signal?"rgba(52,211,153,.8)":"rgba(96,165,250,.75)";ctx.strokeRect(lx+.5,ly+.5,tw-1,19);
    ctx.fillStyle=signal?"#6ee7b7":"#93c5fd";ctx.fillText(txt,lx+6,ly+13);
    ctx.restore();
  };

  function refreshActiveDesk(){
    try{renderSignals();renderRadar();if(state.selectedModel)draw()}catch(e){console.warn("active desk refresh",e)}
  }
  document.querySelector('[data-tab="signals"]')?.addEventListener("click",renderSignals);
  document.querySelector('[data-tab="radar"]')?.addEventListener("click",renderRadar);
  setTimeout(refreshActiveDesk,120);
  setInterval(refreshActiveDesk,1500);
})();
