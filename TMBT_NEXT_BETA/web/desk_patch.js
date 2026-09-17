// Small post-compat safety patch.
// Keep feed health tied to the timeframe actually shown, not only the 5m quote.
const _compatSetMarket=setMarket;
setMarket=function(m){originalFeedMeta=null;originalFeedFresh=null;return _compatSetMarket(m)};
const _compatSetTF=setTF;
setTF=function(tf){originalFeedMeta=null;originalFeedFresh=null;return _compatSetTF(tf)};

enforceOriginalFeedHealth=function(){
  const meta=originalFeedMeta||feedStatus[state.market];
  if(meta)originalFeedFresh=meta.stale===true?false:!!(meta.ok??state.bars.length);
  if(originalFeedFresh===null)return;
  const ld=document.querySelector("#liveDot");if(ld)ld.className=originalFeedFresh?"ok":"bad";
  const btn=document.querySelector("#liveModeBtn");if(btn){btn.textContent=originalFeedFresh?"● LIVE":"⚠ STALE";btn.classList.toggle("active",originalFeedFresh);btn.classList.toggle("stale",!originalFeedFresh)}
  const badge=document.querySelector("#feedBadge");if(badge){badge.textContent=originalFeedFresh?`LIVE ${ageText(meta?.age_seconds)}`:`STALE ${ageText(meta?.age_seconds)}`;badge.className=`feed-badge ${originalFeedFresh?"ok":"bad"}`}
};

// app.js still contains a purely visual placeholder session rectangle. A wrong
// session marker is worse than no marker on a trading desk, so disable it until
// timestamp-based NY/London session shading is implemented.
state.sessions=false;
const sessionBtn=document.querySelector("#sessionsBtn");
if(sessionBtn){
  sessionBtn.classList.remove("active");
  sessionBtn.textContent="Sessions off";
  sessionBtn.title="Temporär deaktiviert: alte Preview-Markierung war nicht zeitbasiert.";
  sessionBtn.onclick=()=>toast("Session-Shading ist vorübergehend deaktiviert, bis NY/London-Zeiten exakt aus den Bar-Timestamps gezeichnet werden.");
}
draw();
