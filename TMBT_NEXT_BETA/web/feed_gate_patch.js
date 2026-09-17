// Hard safety gate for non-actionable live-model feeds.
// QQQ/SPY proxy EBP models remain visible for research, but can never present
// as actionable LIVE/SIGNAL until true NQ/ES futures feeds are connected.
(function(){
  function isProxyModel(m){
    const name=String(m?.name||m?.label||m?.id||"");
    return /QQQ\s*proxy|SPY\s*proxy/i.test(name);
  }
  function gate(m){
    const proxy=isProxyModel(m);
    const fresh=typeof marketFresh==="function"?marketFresh(m?.market):false;
    return {proxy,fresh,actionable:fresh&&!proxy,label:proxy?"PROXY DELAYED":(fresh?"LIVE":"DATA STALE")};
  }
  function setBlockedPill(pill,label="BLOCKED"){
    if(!pill)return;
    pill.textContent=label;
    pill.className="pill expired";
  }

  const baseDecorateModelCards=decorateModelCards;
  decorateModelCards=function(){
    baseDecorateModelCards();
    for(const m of state.models||[]){
      const card=document.querySelector(`.model-card[data-id="${CSS.escape(String(m.id))}"]`);if(!card)continue;
      const g=gate(m),info=formationInfo(m);
      if(!g.actionable){
        card.classList.add("data-stale");
        setBlockedPill(card.querySelector(".pill"));
        let chip=card.querySelector(".formation-chip");
        if(!chip){chip=document.createElement("span");chip.className="formation-chip stale";card.appendChild(chip)}
        chip.textContent=g.proxy?"PROXY DELAYED":"DATA STALE";
        chip.className="formation-chip stale";
        card.title=g.proxy?"QQQ/SPY proxy is monitoring-only and must not generate live trade signals.":"Feed is stale; live alerts are blocked.";
      }else{
        const pill=card.querySelector(".pill");
        if(pill){pill.textContent=m.status;pill.className=`pill ${String(m.status).toLowerCase()}`}
        const chip=card.querySelector(".formation-chip");
        if(chip){chip.textContent=info.pct!==null?`${info.label} ${info.pct}%`:info.label;chip.className=`formation-chip r${info.rank}`}
      }
    }
  };

  const baseRenderModels=renderModels;
  renderModels=function(){baseRenderModels();decorateModelCards()};

  const baseRenderSignals=renderSignals;
  renderSignals=function(){
    baseRenderSignals();
    document.querySelectorAll("#signalsTable tr[data-id]").forEach(row=>{
      const m=(state.models||[]).find(x=>String(x.id)===String(row.dataset.id));if(!m)return;
      const g=gate(m);if(g.actionable)return;
      row.classList.add("radar-stale");
      setBlockedPill(row.querySelector("td:nth-child(4) .pill"));
      const info=row.querySelector("td:last-child");
      if(info)info.textContent=`${g.label} · raw engine stage: ${m.status||"—"}`;
    });
  };

  const baseRenderInspector=renderInspector;
  renderInspector=function(m,snap=null){
    baseRenderInspector(m,snap);
    if(!m||snap)return;
    const g=gate(m);if(g.actionable)return;
    const host=document.querySelector("#inspector");
    setBlockedPill(host?.querySelector(".pill"));
    const p=host?.querySelector("p");
    if(p)p.textContent=g.proxy?"Monitoring only: QQQ/SPY proxy is delayed/non-futures. Live trading signal blocked.":"Feed stale. Live trading signal blocked.";
    const row=host?.querySelector(".formation-status b");if(row)row.textContent=g.label;
  };

  const baseSelectModel=selectModel;
  selectModel=function(id){
    baseSelectModel(id);
    const m=(state.models||[]).find(x=>String(x.id)===String(id));if(!m)return;
    const g=gate(m);
    if(!g.actionable){const s=document.querySelector("#selectedState");if(s)s.textContent=`BLOCKED · ${g.label}`}
  };

  radarRow=function(m){
    const info=formationInfo(m),g=gate(m),next=info.next?.label||info.next?.name||"—";
    const score=info.pct===null?"—":`${info.pct}%`;
    const stage=g.actionable?esc(m.status):"BLOCKED";
    const stageClass=g.actionable?String(m.status).toLowerCase():"expired";
    const data=g.proxy?'<span class="bad">PROXY</span>':(g.fresh?'<span class="good">LIVE</span>':'<span class="bad">STALE</span>');
    return `<tr class="clickable ${g.actionable?"":"radar-stale"}" data-radar-id="${esc(m.id)}"><td>${esc(m.name)}</td><td>${esc(m.market)}</td><td>${esc(m.tf)}</td><td><span class="pill ${stageClass}">${stage}</span></td><td>${data}</td><td><b>${score}</b></td><td>${info.stats.total?`${info.stats.pass}/${info.stats.total}`:"—"}</td><td class="muted">${esc(next)}</td></tr>`;
  };

  detectFormationAlerts=function(){
    for(const m of state.models||[]){
      const id=String(m.id||m.name||"");if(!id)continue;
      const info=formationInfo(m),g=gate(m),prev=formationMemory[id];
      if(prev===undefined){formationMemory[id]=info.rank;continue}
      formationMemory[id]=info.rank;
      if(!g.actionable||info.rank<=prev||info.rank<1)continue;
      const key=`${id}:${info.rank}`,now=Date.now();
      if(now-(formationLastAlert[key]||0)<=10*60*1000)continue;
      formationLastAlert[key]=now;
      const msg=modelAlertText(m,info);toast(msg);
      if(state.alerts&&"Notification" in window&&Notification.permission==="granted")new Notification("TMBT Model forming",{body:msg});
    }
  };

  setTimeout(()=>{decorateModelCards();renderSignals();if(typeof renderRadar==="function")renderRadar();if(state.selectedModel)renderInspector(state.selectedModel)},50);
})();
