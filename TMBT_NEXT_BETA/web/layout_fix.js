// Robust app-shell resizing + runtime layout guard.
(function(){
  const root=document.documentElement;
  const app=document.querySelector('#app');
  const split=document.querySelector('#splitBottom');
  const splitLeft=document.querySelector('#splitLeft');
  const splitRight=document.querySelector('#splitRight');
  const tabs=document.querySelector('.bottom-tabs');
  const workspace=document.querySelector('.workspace');
  const bottom=document.querySelector('.bottom-panel');
  const chartHost=document.querySelector('#chartHost');

  const TOPBAR=54,SPLITTER=10,MIN_WORKSPACE=290,MIN_BOTTOM=90,NORMAL_BOTTOM=300,HARD_MAX_BOTTOM=640;
  const DEFAULT_LEFT=236,DEFAULT_RIGHT=368,MIN_SIDE=150,MIN_CHART=520;
  const px=v=>parseFloat(v)||0;
  const cssVar=name=>px(getComputedStyle(root).getPropertyValue(name));
  const current=()=>cssVar('--bottom')||NORMAL_BOTTOM;
  const currentLeft=()=>cssVar('--left')||DEFAULT_LEFT;
  const currentRight=()=>cssVar('--right')||DEFAULT_RIGHT;
  const maxBottom=()=>Math.max(MIN_BOTTOM,Math.min(HARD_MAX_BOTTOM,window.innerHeight-TOPBAR-SPLITTER-MIN_WORKSPACE));
  const clampBottom=v=>Math.max(MIN_BOTTOM,Math.min(maxBottom(),Number(v)||NORMAL_BOTTOM));
  const maxLeft=()=>Math.max(MIN_SIDE,window.innerWidth-currentRight()-10-MIN_CHART);
  const maxRight=()=>Math.max(MIN_SIDE,window.innerWidth-currentLeft()-10-MIN_CHART);
  const clampLeft=v=>Math.max(MIN_SIDE,Math.min(560,maxLeft(),Number(v)||DEFAULT_LEFT));
  const clampRight=v=>Math.max(MIN_SIDE,Math.min(560,maxRight(),Number(v)||DEFAULT_RIGHT));

  let drawRaf=0;
  const redraw=()=>{
    if(drawRaf)return;
    drawRaf=requestAnimationFrame(()=>{drawRaf=0;try{draw()}catch{}});
  };

  const persist=()=>{if(typeof saveLayout==='function')setTimeout(saveLayout,20)};
  const setBottom=(v,save=true)=>{
    document.body.classList.remove('bottom-collapsed');
    const next=clampBottom(v);root.style.setProperty('--bottom',next+'px');redraw();if(save)persist();return next;
  };
  const setSide=(name,v,save=true)=>{
    if(name==='--left'){document.body.classList.remove('left-collapsed');root.style.setProperty(name,clampLeft(v)+'px')}
    else{document.body.classList.remove('right-collapsed');root.style.setProperty(name,clampRight(v)+'px')}
    redraw();if(save)persist();
  };

  // Migrate impossible/tiny saved values, while preserving reasonable user choices.
  try{
    const saved=JSON.parse(localStorage.getItem('tmbt-next-layout')||'null');
    if(saved){
      const b=px(saved.bottom),l=px(saved.left),r=px(saved.right);
      if(b>0&&b<220)saved.bottom=NORMAL_BOTTOM+'px';else if(b>maxBottom())saved.bottom=maxBottom()+'px';
      if(l>0&&!saved.lc)saved.left=clampLeft(l)+'px';
      if(r>0&&!saved.rc)saved.right=clampRight(r)+'px';
      localStorage.setItem('tmbt-next-layout',JSON.stringify(saved));
    }
    const requested=px(saved?.bottom)>=220?px(saved.bottom):current();
    root.style.setProperty('--bottom',clampBottom(requested)+'px');
  }catch{root.style.setProperty('--bottom',clampBottom(current())+'px')}

  // Replace legacy horizontal mouse splitter with pointer capture.
  if(split){
    split.onmousedown=null;
    split.addEventListener('pointerdown',e=>{
      if(e.button!==0)return;e.preventDefault();document.body.classList.remove('bottom-collapsed');document.body.classList.add('bottom-resizing');
      const startY=e.clientY,startH=current();try{split.setPointerCapture(e.pointerId)}catch{}
      const move=ev=>setBottom(startH+(startY-ev.clientY),false);
      const up=ev=>{
        document.body.classList.remove('bottom-resizing');split.removeEventListener('pointermove',move);split.removeEventListener('pointerup',up);split.removeEventListener('pointercancel',up);
        try{split.releasePointerCapture(ev.pointerId)}catch{}persist();auditLayout(true);paintAudit();
      };
      split.addEventListener('pointermove',move);split.addEventListener('pointerup',up);split.addEventListener('pointercancel',up);
    });
    split.addEventListener('dblclick',()=>{setBottom(NORMAL_BOTTOM);auditLayout(true);paintAudit()});
    split.title='Ziehen: unteres Panel vergrößern/verkleinern · Doppelklick: Normalhöhe';
  }

  function bindSideSplitter(el,name,direction){
    if(!el)return;
    el.onmousedown=null;
    el.addEventListener('pointerdown',e=>{
      if(e.button!==0)return;e.preventDefault();document.body.classList.add('side-resizing');
      const startX=e.clientX,start=name==='--left'?currentLeft():currentRight();
      try{el.setPointerCapture(e.pointerId)}catch{}
      const move=ev=>{const dx=ev.clientX-startX;setSide(name,start+(direction*dx),false)};
      const up=ev=>{
        document.body.classList.remove('side-resizing');el.removeEventListener('pointermove',move);el.removeEventListener('pointerup',up);el.removeEventListener('pointercancel',up);
        try{el.releasePointerCapture(ev.pointerId)}catch{}persist();auditLayout(true);paintAudit();
      };
      el.addEventListener('pointermove',move);el.addEventListener('pointerup',up);el.addEventListener('pointercancel',up);
    });
    el.addEventListener('dblclick',()=>setSide(name,name==='--left'?DEFAULT_LEFT:DEFAULT_RIGHT));
  }
  bindSideSplitter(splitLeft,'--left',1);
  bindSideSplitter(splitRight,'--right',-1);

  // Buttons for touchpads / quick resizing.
  if(tabs&&!document.querySelector('#bottomGrow')){
    const collapse=document.querySelector('#bottomHide');const insertBefore=collapse||null;
    const add=(id,label,title,fn)=>{const b=document.createElement('button');b.id=id;b.className='bottom-resize-btn';b.textContent=label;b.title=title;b.onclick=fn;tabs.insertBefore(b,insertBefore);return b};
    add('bottomShrink','−','Unteres Panel kleiner',()=>setBottom(current()-80));
    add('bottomGrow','+','Unteres Panel größer',()=>setBottom(current()+80));
    add('bottomMax','↕','Unteres Panel groß/normal',()=>setBottom(current()<420?Math.min(560,maxBottom()):NORMAL_BOTTOM));
  }

  function rect(el){return el?.getBoundingClientRect?.()||null}
  function auditLayout(logProblems=false){
    const a=rect(app),w=rect(workspace),s=rect(split),b=rect(bottom),c=rect(chartHost);
    const issues=[],tol=2;
    if(!a||!w)issues.push('layout nodes missing');
    else{
      // v0.9.41+ uses browser-style full-page workspace tabs; the legacy
      // horizontal drawer/splitter may intentionally not exist anymore.
      if(s&&b){
        if(w.bottom>s.top+tol)issues.push(`workspace overlaps splitter by ${Math.round(w.bottom-s.top)}px`);
        if(s.bottom>b.top+tol)issues.push(`splitter overlaps bottom panel by ${Math.round(s.bottom-b.top)}px`);
        if(b.bottom>a.bottom+tol)issues.push(`bottom panel exceeds app by ${Math.round(b.bottom-a.bottom)}px`);
      }else if(w.bottom>a.bottom+tol){
        issues.push(`workspace exceeds app by ${Math.round(w.bottom-a.bottom)}px`);
      }
      if(c&&c.bottom>w.bottom+tol)issues.push(`chart paints below workspace by ${Math.round(c.bottom-w.bottom)}px`);
      if(w.height<180)issues.push(`workspace too small (${Math.round(w.height)}px)`);
      if(c&&c.width<320)issues.push(`chart too narrow (${Math.round(c.width)}px)`);
    }
    const result={ok:issues.length===0,issues,bottom:b?Math.round(current()):0,left:Math.round(currentLeft()),right:Math.round(currentRight()),maxBottom:b?Math.round(maxBottom()):0,viewport:{w:window.innerWidth,h:window.innerHeight}};
    window.__tmbtLayoutAudit=result;
    if(logProblems&&!result.ok&&typeof log==='function')log('Layout audit: '+issues.join(' | '));
    return result;
  }
  window.tmbtLayoutAudit=auditLayout;

  function paintAudit(){
    const host=document.querySelector('#systemView');if(!host)return;
    host.querySelector('.layout-audit-card')?.remove();
    const a=auditLayout(false),card=document.createElement('div');card.className='layout-audit-card'+(a.ok?'':' bad');
    card.innerHTML=`<span class="status-dot ${a.ok?'ok':'bad'}"></span><b>Client Layout</b><span class="audit-state">${a.ok?'PASS':'FAIL'}</span><small>${a.ok?`keine Überlappung · drawer ${a.bottom}px · chart workspace bounded`:`${a.issues.join(' · ')}`}</small>`;
    host.prepend(card);
  }

  if('ResizeObserver' in window&&chartHost){const ro=new ResizeObserver(()=>redraw());ro.observe(chartHost)}
  document.querySelector('[data-tab="system"]')?.addEventListener('click',()=>setTimeout(paintAudit,450));

  window.addEventListener('resize',()=>{
    if(!document.body.classList.contains('bottom-collapsed'))setBottom(current(),false);
    if(!document.body.classList.contains('left-collapsed'))root.style.setProperty('--left',clampLeft(currentLeft())+'px');
    if(!document.body.classList.contains('right-collapsed'))root.style.setProperty('--right',clampRight(currentRight())+'px');
    redraw();setTimeout(()=>{auditLayout(true);paintAudit()},60);
  });

  setTimeout(()=>{
    const a=auditLayout(false);
    if(!a.ok){setBottom(Math.min(current(),maxBottom()),false);redraw()}
    setTimeout(()=>{auditLayout(true);paintAudit()},80);
  },120);
})();
