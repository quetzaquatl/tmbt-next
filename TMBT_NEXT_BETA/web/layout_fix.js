// Robust bottom workspace resizing. Loaded after the legacy splitter logic.
(function(){
  const root=document.documentElement, split=document.querySelector('#splitBottom'), tabs=document.querySelector('.bottom-tabs');
  const current=()=>parseFloat(getComputedStyle(root).getPropertyValue('--bottom'))||280;
  const clamp=v=>Math.max(90,Math.min(Math.max(260,window.innerHeight-300),v));
  const setBottom=(v,persist=true)=>{
    document.body.classList.remove('bottom-collapsed');
    root.style.setProperty('--bottom',clamp(v)+'px');
    try{draw()}catch{}
    if(persist&&typeof saveLayout==='function')setTimeout(saveLayout,20);
  };

  // Migrate the old 172px saved layout once so Radar/System are actually usable.
  try{
    const saved=JSON.parse(localStorage.getItem('tmbt-next-layout')||'null');
    const savedPx=parseFloat(saved?.bottom||'0');
    if(saved&&savedPx>0&&savedPx<220){saved.bottom='280px';localStorage.setItem('tmbt-next-layout',JSON.stringify(saved));root.style.setProperty('--bottom','280px')}
    else if(current()<220)root.style.setProperty('--bottom','280px');
  }catch{if(current()<220)root.style.setProperty('--bottom','280px')}

  if(split){
    // Replace the tiny mouse-only handler with a pointer handler that works on the whole 10px grip.
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
        split.removeEventListener('pointermove',move);split.removeEventListener('pointerup',up);split.removeEventListener('pointercancel',up);
        try{split.releasePointerCapture(ev.pointerId)}catch{}
        if(typeof saveLayout==='function')saveLayout();
      };
      split.addEventListener('pointermove',move);split.addEventListener('pointerup',up);split.addEventListener('pointercancel',up);
    });
    split.addEventListener('dblclick',()=>setBottom(320));
    split.title='Ziehen: unteres Panel vergrößern/verkleinern · Doppelklick: 320px';
  }

  if(tabs&&!document.querySelector('#bottomGrow')){
    const spacer=tabs.querySelector('.spacer');
    const add=(id,label,title,fn)=>{const b=document.createElement('button');b.id=id;b.className='bottom-resize-btn';b.textContent=label;b.title=title;b.onclick=fn;tabs.insertBefore(b,spacer?.nextSibling||tabs.lastChild);return b};
    add('bottomShrink','−','Unteres Panel kleiner',()=>setBottom(current()-80));
    add('bottomGrow','+','Unteres Panel größer',()=>setBottom(current()+80));
    add('bottomMax','↕','Unteres Panel groß/normal',()=>setBottom(current()<400?Math.min(560,window.innerHeight*.55):280));
  }

  window.addEventListener('resize',()=>{if(!document.body.classList.contains('bottom-collapsed')&&current()>window.innerHeight-260)setBottom(window.innerHeight-300,false)});
  setTimeout(()=>{try{draw()}catch{}},50);
})();
