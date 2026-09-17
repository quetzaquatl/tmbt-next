// TMBT Next v0.9.16 — HTF direction visibility.
(function(){
  const seen={};
  const escH=s=>String(s??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m]));
  function modelBias(m){return String(m?.htf_bias||m?.htf_filter?.bias||"").toUpperCase()}
  function gate(m){return String(m?.execution_gate||"").toUpperCase()}
  function chip(m){
    const b=modelBias(m);if(!b)return "";
    const cls=b==="LONG"?"long":b==="SHORT"?"short":"neutral";
    return `<span class="htf-chip ${cls}">HTF 1H ${escH(b)}</span>`;
  }
  function decorateTable(hostSelector,rowAttr){
    const host=document.querySelector(hostSelector);if(!host)return;
    for(const m of state.models||[]){
      const id=String(m.id||"");if(!id)continue;
      const row=host.querySelector(`[${rowAttr}="${CSS.escape(id)}"]`);if(!row)continue;
      const first=row.querySelector("td");if(!first)continue;
      let c=first.querySelector(".htf-chip");
      const b=modelBias(m);if(!b){c?.remove();continue}
      const tmp=document.createElement("span");tmp.innerHTML=chip(m);const fresh=tmp.firstElementChild;
      if(c)c.replaceWith(fresh);else first.appendChild(fresh);
    }
  }
  function decorateInspector(){
    const m=state.selectedModel;if(!m)return;
    const host=document.querySelector("#inspector");if(!host)return;
    let row=host.querySelector(".htf-status-row");
    const b=modelBias(m),f=m.htf_filter||{};
    if(!b){row?.remove();return}
    if(!row){row=document.createElement("div");row.className="htf-status-row";host.appendChild(row)}
    const pass=m.htf_filter_pass===true;
    const cls=b==="LONG"?"long":b==="SHORT"?"short":"neutral";
    const reason=f.reason||"—";
    row.className=`htf-status-row ${cls} ${pass?"pass":"blocked"}`;
    row.innerHTML=`<div><span>HTF Filter</span><b>1H ${escH(b)}</b><em>${pass?"PASS":"BLOCK"}</em></div><small>${escH(reason)}${gate(m)?` · ${escH(gate(m))}`:""}</small>`;
  }
  function decorateHeading(){
    const heading=document.querySelector(".chart-heading");if(!heading)return;
    let badge=heading.querySelector("#htfBiasBadge");
    const m=(state.models||[]).find(x=>String(x.market||"").toUpperCase()===String(state.market||"").toUpperCase()&&modelBias(x));
    if(!m){badge?.remove();return}
    if(!badge){badge=document.createElement("span");badge.id="htfBiasBadge";heading.appendChild(badge)}
    const b=modelBias(m),cls=b==="LONG"?"long":b==="SHORT"?"short":"neutral";
    badge.className=`htf-bias-badge ${cls}`;badge.textContent=`HTF 1H ${b}`;
    badge.title=m.htf_filter?.reason||"Higher-timeframe direction filter";
  }
  function notifyGates(){
    if(typeof window.tmbtNotify!=="function")return;
    for(const m of state.models||[]){
      const g=gate(m);if(!g.startsWith("HTF_"))continue;
      const key=String(m.id||m.name||"")+":"+g+":"+modelBias(m)+":"+String(m.side||"");
      if(seen[key])continue;seen[key]=true;
      if(["HTF_CONFLICT","HTF_NEUTRAL","HTF_UNAVAILABLE"].includes(g)){
        window.tmbtNotify(`${m.name} · ${g.replaceAll("_"," ")} · HTF 1H ${modelBias(m)||"—"} · ${m.side||"—"} blockiert`,"model");
      }
    }
  }
  function refresh(){
    try{decorateTable("#signalsTable","data-id");decorateTable("#radarView","data-radar-id");decorateInspector();decorateHeading();notifyGates()}catch(e){console.warn("HTF UI",e)}
  }
  const baseSelect=window.selectModel;
  if(typeof baseSelect==="function")window.selectModel=selectModel=function(id){const r=baseSelect(id);setTimeout(refresh,0);return r};
  setTimeout(refresh,180);setInterval(refresh,900);
})();
