// Robust bottom workspace resizing + runtime layout guard.
(function(){
  const root=document.documentElement;
  const app=document.querySelector('#app');
  const split=document.querySelector('#splitBottom');
  const tabs=document.querySelector('.bottom-tabs');
  const workspace=document.querySelector('.workspace');
  const bottom=document.querySelector('.bottom-panel');
  const chartHost=document.querySelector('#chartHost');

  const TOPBAR=54, SPLITTER=10, MIN_WORKSPACE=290, MIN_BOTTOM=90, NORMAL_BOTTOM=300, HARD_MAX_BOTTOM=640;
  const current=()=>parseFloat(getComputedStyle(root).getPropertyValue('--bottom'))||NORMAL_BOTTOM;
  const maxBottom=()=>Math.max(MIN_BOTTOM,Math.min(HARD_MAX_BOTTOM,window.innerHeight-TOPBAR-SPLITTER-MIN_WORKSPACE));
  const clamp=v=>Math.max(MIN_BOTTOM,Math.min(maxBottom(),Number(v)||NORMAL_BOTTOM));

  let drawRaf=0;
  const redraw=()=>{
    if(drawRaf)return;
    drawRaf=requestAnimationFrame(()=>{drawRaf=0;try{draw()}catch{}});
  };

  const setBottom=(v,persist=true)=>{
    document.body.classList.remove('bottom-collapsed');
    const next=clamp(v);
    root.style.setProperty('--bottom',next+'px');
    redraw();
    if(persist&&typeof saveLayout==='function')setTimeout(saveLayout,30);
    return next;
  };

  // Migrate old tiny drawer sizes. Keep a user's larger valid choice.
  try{
    const saved=JSON.parse(localStorage.getItem('tmbt-next-layout')||'null');
    const savedPx=parseFloat(saved?.bottom||'0');
    if(saved){
      if(savedPx>0&&savedPx<220)saved.bottom=NORMAL_BOTTOM+'px';
      else if(savedPx>maxBottom())saved.bottom=maxBottom()+'px';
      localStorage.setItem('tmbt-next-layout',JSON.stringify(saved));
    }
    const requested=savedPx>=220?savedPx:current();
    root.style.setProperty('--bottom',clamp(requested)+'px');
  }catch{root.style.setProperty('--bottom',clamp(current())+'px')}

  // Disable the legacy mousedown splitter for this handle. Pointer capture is
  // much more reliable and works even if the cursor moves quickly while dragging.
  if(split){
    split.onmousedown=null;
    split.addEventListener('pointerdown',e=>{
      if(e.button!==0)return;
      e.preventDefault();
      document.body.classList.remove('bottom-collapsed');
      document.body.classList.add('bottom-resizing');
      const startY=e.clientY,startH=current();
      try{split.setPointerCapture(e.pointerId)}catch{}
      const move=ev=>setBottom(startH+(startY-ev.clientY),false);
      const up=ev=>{
        document.body.classList.remove('bottom-resizing');
        split.removeEventListener('pointermove',move);
        split.removeEventListener('pointerup',up);
        split.removeEventListener('pointercancel',up);
        try{split.releasePointerCapture(ev.pointerId)}catch{}
        if(typeof saveLayout==='function')saveLayout();
        auditLayout(true);
      };
      split.addEventListener('pointermove',move);
      split.addEventListener('pointerup',up);
      split.addEventListener('pointercancel',up);
    });
    split.addEventListener('dblclick',()=>{setBottom(NORMAL_BOTTOM);auditLayout(true)});
    split.title='Ziehen: unteres Panel vergrößern/verkleinern · Doppelklick: Normalhöhe';
  }

  // Explicit controls are useful on touchpads and when the splitter is hard to hit.
  if(tabs&&!document.querySelector('#bottomGrow')){
    const collapse=document.querySelector('#bottomHide');
    const insertBefore=collapse||null;
    const add=(id,label,title,fn)=>{
      const b=document.createElement('button');
      b.id=id;b.className='bottom-resize-btn';b.textContent=label;b.title=title;b.onclick=fn;
      tabs.insertBefore(b,insertBefore);return b;
    };
    add('bottomShrink','−','Unteres Panel kleiner',()=>setBottom(current()-80));
    add('bottomGrow','+','Unteres Panel größer',()=>setBottom(current()+80));
    add('bottomMax','↕','Unteres Panel groß/normal',()=>setBottom(current()<420?Math.min(560,maxBottom()):NORMAL_BOTTOM));
  }

  function rect(el){return el?.getBoundingClientRect?.()||null}
  function auditLayout(logProblems=false){
    const a=rect(app),w=rect(workspace),s=rect(split),b=rect(bottom),c=rect(chartHost);
    const issues=[];
    const tol=2;
    if(!a||!w||!s||!b)issues.push('layout nodes missing');
    else{
      if(w.bottom>s.top+tol)issues.push(`workspace overlaps splitter by ${Math.round(w.bottom-s.top)}px`);
      if(s.bottom>b.top+tol)issues.push(`splitter overlaps bottom panel by ${Math.round(s.bottom-b.top)}px`);
      if(b.bottom>a.bottom+tol)issues.push(`bottom panel exceeds app by ${Math.round(b.bottom-a.bottom)}px`);
      if(c&&c.bottom>w.bottom+tol)issues.push(`chart paints below workspace by ${Math.round(c.bottom-w.bottom)}px`);
      if(w.height<180)issues.push(`workspace too small (${Math.round(w.height)}px)`);
    }
    const result={ok:issues.length===0,issues,bottom:Math.round(current()),maxBottom:Math.round(maxBottom()),viewport:{w:window.innerWidth,h:window.innerHeight}};
    window.__tmbtLayoutAudit=result;
    if(logProblems&&!result.ok&&typeof log==='function')log('Layout audit: '+issues.join(' | '));
    return result;
  }
  window.tmbtLayoutAudit=auditLayout;

  // ResizeObserver catches drawer/side-panel geometry changes that do not emit a
  // window resize event. This keeps the canvas pixel size in sync with its box.
  if('ResizeObserver' in window&&chartHost){
    const ro=new ResizeObserver(()=>redraw());
    ro.observe(chartHost);
  }

  window.addEventListener('resize',()=>{
    if(!document.body.classList.contains('bottom-collapsed'))setBottom(current(),false);
    redraw();
    setTimeout(()=>auditLayout(true),60);
  });

  // If old CSS/localStorage left an impossible geometry, self-heal once.
  setTimeout(()=>{
    const a=auditLayout(false);
    if(!a.ok){setBottom(Math.min(current(),maxBottom()),false);redraw()}
    setTimeout(()=>auditLayout(true),80);
  },120);
})();
