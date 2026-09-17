// TMBT Next v0.9.19 — visual desk refresh.
(function(){
  const ACTIVE=/^(SIGNAL|ARMED|WATCH|FORMING|STRONG|READY|TRIGGERED)$/i;
  const DEAD=/^(IDLE|WAIT_SESSION|EXPIRED|CLOSED|BLOCKED|NO_SETUP)$/i;
  const stage=m=>String(m?.status||m?.stage||"").trim().toUpperCase();
  const isProxy=m=>m?.proxy===true||/QQQ\s*proxy|SPY\s*proxy/i.test(String(m?.name||m?.label||m?.id||""));
  const fresh=m=>{try{return typeof marketFresh==="function"?!!marketFresh(m?.market):true}catch{return true}};
  const active=m=>{const s=stage(m);return !!s&&!DEAD.test(s)&&!isProxy(m)&&fresh(m)&&ACTIVE.test(s)};
  const side=m=>{const s=String(m?.side||"").toUpperCase();return /LONG|BUY|BULL/.test(s)?"LONG":/SHORT|SELL|BEAR/.test(s)?"SHORT":"—"};
  const sideClass=s=>s==="LONG"?"side-long":s==="SHORT"?"side-short":"side-neutral";
  function ms(v){if(v==null||v==="")return null;const n=Number(v);if(Number.isFinite(n))return n>1e12?n:n*1000;const p=Date.parse(String(v));return Number.isFinite(p)?p:null}
  function eventMs(m){const e=m?.event||{};return ms(e.touch_ms??e.trigger_ms??e.event_ms??e.event_time_utc??m?.event_time_utc??m?.signal_time_utc)}
  function timeText(m){const x=eventMs(m);if(!x)return "—";const d=new Date(x);const local=d.toLocaleTimeString([],{hour:"2-digit",minute:"2-digit"});let ny="—";try{ny=new Intl.DateTimeFormat("de-DE",{timeZone:"America/New_York",hour:"2-digit",minute:"2-digit",hour12:false}).format(d)}catch{}return `${local} · NY ${ny}`}
  function info(m){try{return typeof formationInfo==="function"?formationInfo(m):{pct:null,next:null}}catch{return {pct:null,next:null}}}
  function number(v,n=2){try{return v==null||v===""?"—":Number(v).toFixed(n)}catch{return "—"}}
  function criterionStatus(c){const s=String(c?.status||"PENDING").toUpperCase();return s==="PASS"?"pass":s==="WARN"?"warn":/FAIL|BLOCK|INVALID/.test(s)?"fail":"pending"}
  function shortCriterionLabel(label){
    const z=String(label||"");
    if(/SMT Profit Taking/i.test(z))return "SMT TP";
    if(/SMT/i.test(z))return "SMT";
    if(/^PO3$/i.test(z))return "PO3";
    if(/Asia Range/i.test(z))return "Asia";
    if(/Midnight Open/i.test(z))return "Midnight";
    if(/Liquidity Sweep/i.test(z))return "Sweep";
    if(/Opposite FVG/i.test(z))return "iFVG";
    if(/CE \/ 50%-Retest/i.test(z))return "CE Retest";
    if(/Mindest-RR/i.test(z))return "RR";
    if(/Entry-Retest/i.test(z))return "Retest";
    if(/BOS/i.test(z))return "BOS";
    if(/OTE/i.test(z))return "OTE";
    return z.length>15?z.slice(0,14)+"…":z;
  }
  function criteriaSummary(m){
    const all=Array.isArray(m?.criteria)?m.criteria:[];
    if(!all.length)return '<div class="active-card-criteria empty"><span>Keine Kriterien im Payload</span></div>';
    const priority=/SMT Profit Taking|SMT NQ\/ES|^PO3$|Asia Range|Midnight Open|Liquidity Sweep|Opposite FVG|CE \/ 50%-Retest|Mindest-RR|Entry-Retest|BOS|OTE/i;
    const ranked=all.map((c,i)=>({c,i,p:priority.test(String(c?.label||c?.name||""))?1:0})).sort((a,b)=>b.p-a.p||a.i-b.i);
    const chosen=ranked.slice(0,5).map(x=>x.c);
    const chips=chosen.map(c=>{
      const label=c?.label||c?.name||"Kriterium",st=criterionStatus(c),detail=c?.detail||"";
      return `<span class="criterion-chip ${st}" title="${esc(label)}${detail?` — ${esc(detail)}`:""}">${esc(shortCriterionLabel(label))}</span>`;
    }).join("");
    const more=all.length>chosen.length?`<span class="criterion-more">+${all.length-chosen.length}</span>`:"";
    return `<div class="active-card-criteria">${chips}${more}</div>`;
  }

  // Override the dense table with scan-friendly setup cards.
  window.renderSignals=renderSignals=function(){
    const host=document.querySelector("#signalsTable");if(!host)return;
    const all=state.models||[];
    const list=all.filter(active).sort((a,b)=>{
      const rank={SIGNAL:6,TRIGGERED:6,ARMED:5,READY:4,STRONG:3,FORMING:2,WATCH:1};
      return (rank[stage(b)]||0)-(rank[stage(a)]||0);
    });
    const blocked=all.filter(m=>isProxy(m)||!fresh(m)||stage(m)==="BLOCKED").length;
    const background=all.length-list.length;
    let html=`<div class="active-desk-head"><div><b>Active Setups</b><small>nur was jetzt beobachtet oder ausgeführt werden kann</small></div><div class="active-counts"><span class="hot">${list.length} active</span><span>${background} background</span><span class="blocked">${blocked} blocked</span></div></div>`;
    if(!list.length){host.innerHTML=html+'<div class="active-empty"><b>Keine aktiven Setups.</b>Wartende, blockierte und abgelaufene Modelle findest du im Monitor.</div>';return}
    html+='<div class="active-card-grid">'+list.map(m=>{
      const st=stage(m),sd=side(m),fi=info(m),pct=fi?.pct==null?"—":`${fi.pct}%`,next=fi?.next?.label||m?.message||"—";
      const entry=m.entry??m.arrays?.entry,sl=m.sl??m.stop??m.arrays?.stop,tp=m.tp??m.target??m.arrays?.target;
      return `<article class="active-setup-card ${st.toLowerCase()}" data-id="${esc(m.id)}">
        <div class="active-card-top">
          <div class="active-card-title"><b>${esc(m.name||m.label||"Setup")}</b><small>${esc(m.market||"—")} · ${esc(m.tf||"—")} · <span class="active-card-time">${esc(timeText(m))}</span></small></div>
          <div class="active-card-side ${sideClass(sd)}">${esc(sd)}</div>
        </div>
        <span class="pill ${st.toLowerCase()}">${esc(st)}</span>
        <div class="active-card-middle">
          <div class="active-card-metric"><small>Entry</small><b>${number(entry,4)}</b></div>
          <div class="active-card-metric"><small>Stop</small><b style="color:#ff8290">${number(sl,4)}</b></div>
          <div class="active-card-metric"><small>Target</small><b style="color:#5ee0aa">${number(tp,4)}</b></div>
        </div>
        ${criteriaSummary(m)}
        <div class="active-card-bottom"><span class="formation">${esc(pct)}</span><span class="next">${esc(next)}</span></div>
      </article>`;
    }).join("")+'</div>';
    host.innerHTML=html;
    host.querySelectorAll("[data-id]").forEach(el=>el.onclick=()=>selectModel(el.dataset.id));
  };

  function installMoreTabs(){
    const bar=document.querySelector(".bottom-tabs");if(!bar||bar.querySelector(".more-tabs-wrap"))return;
    const spacer=bar.querySelector(":scope > .spacer");
    const wrap=document.createElement("div");wrap.className="more-tabs-wrap";
    wrap.innerHTML=`<button class="more-tabs-btn" type="button">More ▾</button><div class="more-tabs-menu">
      <button type="button" data-target="outcomes">Outcomes</button>
      <button type="button" data-target="paper">Paper</button>
      <button type="button" data-target="system">System</button>
      <button type="button" data-target="logs">Logs</button>
    </div>`;
    bar.insertBefore(wrap,spacer||null);
    const btn=wrap.querySelector(".more-tabs-btn");
    btn.onclick=e=>{e.stopPropagation();wrap.classList.toggle("open")};
    wrap.querySelectorAll("[data-target]").forEach(b=>b.onclick=e=>{
      e.stopPropagation();
      const target=b.dataset.target;
      const original=bar.querySelector(`button[data-tab="${target}"]`);
      if(original){original.click();btn.textContent=`${b.textContent} ▾`}
      wrap.classList.remove("open");
    });
    document.addEventListener("click",()=>wrap.classList.remove("open"));
    bar.querySelectorAll('button[data-tab="signals"],button[data-tab="radar"],button[data-tab="archive"],button[data-tab="research"]').forEach(b=>b.addEventListener("click",()=>{btn.textContent="More ▾"}));
  }

  function decorateInspector(){
    const m=state.selectedModel,host=document.querySelector("#inspector");if(!m||!host)return;
    const sd=side(m);host.dataset.side=sd.toLowerCase();
    let sideBadge=host.querySelector(".inspector-side-badge");
    if(!sideBadge){sideBadge=document.createElement("b");sideBadge.className="inspector-side-badge";host.insertBefore(sideBadge,host.querySelector("h3"))}
    sideBadge.className=`inspector-side-badge ${sideClass(sd)}`;sideBadge.textContent=sd;
  }

  const extraStyle=document.createElement("style");
  extraStyle.textContent=`
    .inspector-side-badge{float:right;margin-top:-21px;font-size:15px;letter-spacing:.05em}
    .inspector[data-side="long"]{box-shadow:inset 3px 0 0 #35d59a}
    .inspector[data-side="short"]{box-shadow:inset 3px 0 0 #ff6678}
    .active-card-criteria{display:flex;flex-wrap:wrap;gap:5px;margin:9px 0 5px;padding-top:8px;border-top:1px solid rgba(120,150,180,.12)}
    .active-card-criteria.empty{color:#64748b;font-size:10px}
    .criterion-chip,.criterion-more{display:inline-flex;align-items:center;min-height:19px;padding:2px 6px;border-radius:999px;font-size:9px;font-weight:700;letter-spacing:.02em;border:1px solid rgba(120,150,180,.22);background:rgba(70,90,115,.12);color:#9fb2c8}
    .criterion-chip.pass{border-color:rgba(52,211,153,.28);background:rgba(52,211,153,.08);color:#6ee7b7}
    .criterion-chip.warn{border-color:rgba(251,191,36,.32);background:rgba(251,191,36,.09);color:#fcd34d}
    .criterion-chip.fail{border-color:rgba(248,113,113,.32);background:rgba(248,113,113,.09);color:#fda4af}
    .criterion-chip.pending{border-color:rgba(96,165,250,.26);background:rgba(96,165,250,.07);color:#93c5fd}
    .criterion-more{color:#71859c}
  `;
  document.head.appendChild(extraStyle);

  const baseSelect=window.selectModel;
  if(typeof baseSelect==="function")window.selectModel=selectModel=function(id){const r=baseSelect(id);setTimeout(decorateInspector,0);return r};
  installMoreTabs();
  setTimeout(()=>{try{renderSignals();decorateInspector()}catch(e){console.warn("visual refresh",e)}},120);
  setInterval(()=>{try{installMoreTabs();decorateInspector()}catch{}},1500);
})();
