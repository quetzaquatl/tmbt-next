// TMBT Next compatibility layer for the original Studio 4.6 live pipeline.
// Keeps the new UI, but makes chart/feed semantics match the old Studio:
// Twelve QQQ -> NQ context, Twelve SPY -> ES context, Twelve XAU/USD -> XAU.

let originalFeedFresh = null;
let originalFeedMeta = null;

function enforceOriginalFeedHealth(){
  if(originalFeedFresh === null) return;
  const ld = document.querySelector("#liveDot");
  if(ld){
    const wanted = originalFeedFresh ? "ok" : "bad";
    if(ld.className !== wanted) ld.className = wanted;
  }
  const btn = document.querySelector("#liveModeBtn");
  if(btn){
    btn.textContent = originalFeedFresh ? "● LIVE" : "⚠ STALE";
    btn.classList.toggle("active", originalFeedFresh);
  }
}

const liveDotNode = document.querySelector("#liveDot");
if(liveDotNode){
  new MutationObserver(enforceOriginalFeedHealth).observe(liveDotNode,{attributes:true,attributeFilter:["class"]});
}

// Replace only the chart loader. Models, signals, archive, outcomes, paper and
// research remain on the existing original-workspace endpoints.
loadBars = async function(){
  if(state.mode === "snapshot") return;
  document.querySelector("#chartTitle").textContent = `${state.market} · ${state.tf}`;
  const empty = document.querySelector("#chartEmpty");
  empty.textContent = "Lade Original-Livefeed…";
  empty.style.display = "grid";
  try{
    const d = await api(`/api/bars?market=${encodeURIComponent(state.market)}&tf=${encodeURIComponent(state.tf)}&limit=1500${state.source?`&source=${encodeURIComponent(state.source)}`:""}`);
    state.bars = d.bars || [];
    // Do not pin the chart to a stale source selector. The backend resolves the
    // original Twelve mirror first and the local DB fallback second.
    state.source = null;
    originalFeedMeta = d;
    originalFeedFresh = d.stale === true ? false : (state.bars.length > 0);
    const sourceText = d.note || (d.provider ? `${d.provider} · original live pipeline` : "kein Original-Feed");
    document.querySelector("#chartSource").textContent = sourceText;
    empty.style.display = state.bars.length ? "none" : "grid";
    if(state.bars.length){
      const p = state.bars.at(-1).c;
      const q = document.querySelector("#q"+state.market);
      if(q) q.textContent = fmt(p,2);
    }else{
      empty.textContent = d.note || "Keine Bars im Original-Livefeed";
    }
    enforceOriginalFeedHealth();
    draw();
  }catch(e){
    originalFeedFresh = false;
    originalFeedMeta = {error:String(e)};
    document.querySelector("#chartSource").textContent = "Original-Livefeed nicht erreichbar";
    empty.textContent = "Bars konnten nicht geladen werden";
    enforceOriginalFeedHealth();
    log("Original-Livefeed Fehler: "+e);
  }
};

// pollModels() in the base UI reports the model monitor health. In the old
// Studio that is separate from market-data freshness, so keep the Live lamp
// tied to bars rather than allowing model polling to turn a stale feed green.
setInterval(enforceOriginalFeedHealth, 500);

// Reload once through the compatibility loader immediately after app.js.
if(state.mode === "live"){
  loadBars();
  loadPD();
}
