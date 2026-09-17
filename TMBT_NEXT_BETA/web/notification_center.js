// TMBT Next v0.9.15 — persistent notification history.
(function(){
  const KEY="tmbt_next_notifications_v1",MAX=100;
  let items=[];
  try{items=JSON.parse(localStorage.getItem(KEY)||"[]");if(!Array.isArray(items))items=[]}catch{items=[]}
  const save=()=>{try{localStorage.setItem(KEY,JSON.stringify(items.slice(0,MAX)))}catch{}};
  const escN=s=>String(s??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m]));
  function kindFor(msg){
    const s=String(msg||"");
    if(/\bSIGNAL\b|TRIGGERED|target hit|stop hit/i.test(s))return "signal";
    if(/ARMED|FORMING|WATCH|setup/i.test(s))return "model";
    if(/research|optimizer|backtest|completed|failed/i.test(s))return /failed|error/i.test(s)?"error":"research";
    if(/error|fehler|stale|blocked|offline/i.test(s))return "error";
    if(/feed|paper|system|started|gestartet/i.test(s))return "system";
    return "info";
  }
  function add(msg,kind){
    const text=String(msg||"").trim();if(!text)return;
    const now=Date.now(),last=items[0];
    if(last&&last.text===text&&now-last.ts<4000)return;
    items.unshift({id:`${now}_${Math.random().toString(16).slice(2,7)}`,ts:now,text,kind:kind||kindFor(text),read:false});
    items=items.slice(0,MAX);save();render();
  }
  const baseToast=typeof window.toast==="function"?window.toast:null;
  if(baseToast){
    window.toast=toast=function(msg){add(msg);return baseToast(msg)};
  }

  const drawer=document.querySelector("#notificationDrawer"),shade=document.querySelector("#notificationShade"),list=document.querySelector("#notificationList"),btn=document.querySelector("#alertsBtn"),clearBtn=document.querySelector("#notificationClear"),closeBtn=document.querySelector("#notificationClose"),permBtn=document.querySelector("#notificationPermission"),permState=document.querySelector("#notificationPermissionState"),foot=document.querySelector("#notificationFoot");
  if(!drawer||!list||!btn)return;
  let badge=btn.querySelector(".notif-badge");if(!badge){badge=document.createElement("span");badge.className="notif-badge zero";btn.appendChild(badge)}
  function permissionText(){
    if(!("Notification" in window))return "Browser-Alerts nicht verfügbar";
    if(Notification.permission==="granted")return "Browser-Alerts aktiv";
    if(Notification.permission==="denied")return "Browser-Alerts blockiert";
    return "Browser-Alerts aus";
  }
  function render(){
    const unread=items.filter(x=>!x.read).length;badge.textContent=String(unread);badge.classList.toggle("zero",unread===0);
    if(permState)permState.textContent=permissionText();
    if(foot)foot.textContent=`${items.length} gespeichert · maximal ${MAX} · lokal im Browser`;
    if(!items.length){list.innerHTML='<div class="notif-empty"><b>Noch keine Notifications.</b><br>Modell-, Research- und Systemmeldungen erscheinen hier.</div>';return}
    list.innerHTML=items.slice(0,60).map(n=>{
      const d=new Date(n.ts),time=d.toLocaleTimeString([],{hour:"2-digit",minute:"2-digit",second:"2-digit"}),date=d.toLocaleDateString([],{day:"2-digit",month:"2-digit"});
      const label={signal:"Signal",model:"Model",research:"Research",system:"System",error:"Warnung",info:"Info"}[n.kind]||"Info";
      return `<div class="notif-item ${n.read?"":"unread"}"><time>${escN(time)}<br>${escN(date)}</time><div class="notif-body"><span class="notif-kind ${escN(n.kind)}">${label}</span><p>${escN(n.text)}</p></div></div>`;
    }).join("");
  }
  function open(){drawer.classList.add("open");shade?.classList.add("open");drawer.setAttribute("aria-hidden","false");items.forEach(x=>x.read=true);save();render()}
  function close(){drawer.classList.remove("open");shade?.classList.remove("open");drawer.setAttribute("aria-hidden","true")}
  btn.addEventListener("click",e=>{e.preventDefault();e.stopImmediatePropagation();drawer.classList.contains("open")?close():open()},true);
  closeBtn?.addEventListener("click",close);shade?.addEventListener("click",close);document.addEventListener("keydown",e=>{if(e.key==="Escape")close()});
  clearBtn?.addEventListener("click",()=>{items=[];save();render()});
  permBtn?.addEventListener("click",async()=>{
    if(!("Notification" in window)){add("Browser-Notifications sind hier nicht verfügbar.","error");return}
    try{const p=await Notification.requestPermission();if(typeof state!=="undefined")state.alerts=p==="granted";add(p==="granted"?"Browser-Alerts aktiviert.":"Browser-Alerts nicht aktiviert.",p==="granted"?"system":"error")}catch(e){add("Browser-Alert Berechtigung fehlgeschlagen: "+e,"error")}
  });
  window.tmbtNotify=(msg,kind)=>add(msg,kind);
  render();
})();
