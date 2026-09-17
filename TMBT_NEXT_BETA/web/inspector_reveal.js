// TMBT Next — keep the Setup Inspector reachable from Active/Monitor cards.
(function(){
  const root=document.documentElement;
  const panel=document.querySelector('#rightPanel');
  if(!panel)return;

  function px(v){const n=parseFloat(v);return Number.isFinite(n)?n:0}
  function revealInspector(){
    document.body.classList.remove('right-collapsed');
    const current=px(getComputedStyle(root).getPropertyValue('--right'));
    if(current<260)root.style.setProperty('--right','368px');
    panel.scrollTop=0;
    panel.classList.remove('inspector-attention');
    void panel.offsetWidth;
    panel.classList.add('inspector-attention');
    setTimeout(()=>panel.classList.remove('inspector-attention'),700);
    try{if(typeof saveLayout==='function')saveLayout()}catch{}
    try{if(typeof draw==='function')draw()}catch{}
  }

  // Wrap the final selectModel implementation (all earlier UI patches are loaded first).
  const baseSelect=window.selectModel;
  if(typeof baseSelect==='function'){
    window.selectModel=selectModel=function(id){
      revealInspector();
      const result=baseSelect(id);
      requestAnimationFrame(()=>{
        revealInspector();
        const selected=window.state?.selectedModel;
        if(selected){
          const title=document.querySelector('#selectedSetup');
          if(title)title.textContent=selected.name||selected.label||'Setup';
        }
      });
      return result;
    };
  }

  // Delegated fallback: survives the Active/Monitor lists being re-rendered every few seconds.
  document.addEventListener('click',e=>{
    const item=e.target.closest?.('.active-setup-card[data-id], #signalsTable [data-id], #radarView [data-radar-id], .model-card[data-id]');
    if(!item)return;
    const id=item.dataset.id||item.dataset.radarId;
    if(!id)return;
    setTimeout(()=>{
      revealInspector();
      const selected=window.state?.selectedModel;
      if(!selected||String(selected.id)!==String(id)){
        try{window.selectModel?.(id)}catch(err){console.warn('inspector select fallback',err)}
      }
    },0);
  },true);

  // If the panel was saved as collapsed, selecting a setup must always win over that old layout state.
  const style=document.createElement('style');
  style.textContent=`
    #rightPanel.inspector-attention{box-shadow:inset 3px 0 0 rgba(85,168,255,.9),-10px 0 28px rgba(0,0,0,.18)}
    #rightPanel{transition:box-shadow .18s ease}
  `;
  document.head.appendChild(style);
})();
