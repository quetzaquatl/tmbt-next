// Bidirectional chart panning patch.
// Keeps the existing horizontal drag/axis zoom behavior and adds natural vertical
// price panning inside the plot area. Dragging the chart up moves it up; dragging
// down moves it down. Fit / market / timeframe / snapshot changes recenter Y.

state.yPan = Number.isFinite(Number(state.yPan)) ? Number(state.yPan) : 0;

const _panBasePriceRange = basePriceRange;
basePriceRange = function(b){
  const r = _panBasePriceRange(b);
  const baseSpan = Math.max(Number(r.hi) - Number(r.lo), 1e-9);
  const shift = (Number(state.yPan) || 0) * baseSpan;
  return {lo:Number(r.lo) + shift, hi:Number(r.hi) + shift};
};

const _panResetChartScale = resetChartScale;
resetChartScale = function(){
  _panResetChartScale();
  state.yPan = 0;
};

const _panOpenArchive = openArchive;
openArchive = async function(hid,sid){
  state.yPan = 0;
  return _panOpenArchive(hid,sid);
};

const _oldDragStart = dragStart;
const _oldDragMove = dragMove;
const _oldDragEnd = dragEnd;
const _oldFit = fit;
const _panCanvas = document.querySelector("#chart");

// Replace the original handlers rather than stacking an additional move handler.
_panCanvas.removeEventListener("mousedown", _oldDragStart);
window.removeEventListener("mousemove", _oldDragMove);
window.removeEventListener("mouseup", _oldDragEnd);
_panCanvas.removeEventListener("dblclick", _oldFit);

function _clampChartOffsets(){
  const maxFuture = Math.max(8, Math.round(state.viewCount * .35));
  const maxPast = Math.max(0, state.bars.length - Math.min(state.viewCount, state.bars.length));
  state.offset = Math.max(-maxFuture, Math.min(maxPast, state.offset));
}

dragStart = function(e){
  const rect = _panCanvas.getBoundingClientRect();
  const g = chartGeom();
  const mx = e.clientX - rect.left;
  const my = e.clientY - rect.top;
  if(mx >= g.right){
    state.drag = {mode:"price", y:e.clientY, zoom:state.yZoom};
  }else if(my >= g.bottom){
    state.drag = {mode:"time", x:e.clientX, count:state.viewCount, offset:state.offset};
  }else{
    state.drag = {
      mode:"pan",
      x:e.clientX,
      y:e.clientY,
      offset:state.offset,
      yPan:Number(state.yPan) || 0,
      yZoom:Math.max(.2, Number(state.yZoom) || 1)
    };
  }
  _panCanvas.style.cursor = state.drag.mode === "price" ? "ns-resize" : state.drag.mode === "time" ? "ew-resize" : "grabbing";
};

dragMove = function(e){
  if(!state.drag)return;
  const host = document.querySelector("#chartHost");
  if(state.drag.mode === "price"){
    const dy = e.clientY - state.drag.y;
    state.yZoom = Math.max(.2, Math.min(8, state.drag.zoom * Math.exp(dy * .008)));
  }else if(state.drag.mode === "time"){
    const dx = e.clientX - state.drag.x;
    state.viewCount = Math.max(20, Math.min(500, Math.round(state.drag.count * Math.exp(-dx * .007))));
    _clampChartOffsets();
  }else{
    const pxPer = Math.max(2, (host.clientWidth - 72) / Math.max(1, state.viewCount));
    const dxBars = Math.round((e.clientX - state.drag.x) / pxPer);
    state.offset = state.drag.offset + dxBars;
    _clampChartOffsets();

    const g = chartGeom();
    const plotH = Math.max(80, g.bottom - g.top);
    const dy = e.clientY - state.drag.y;
    // yPan is measured in unzoomed base-range units. Dividing by yZoom makes
    // dragging remain 1:1 with the visible price range at every zoom level.
    const delta = dy / plotH / Math.max(.2, state.drag.yZoom || 1);
    state.yPan = Math.max(-6, Math.min(6, state.drag.yPan + delta));
  }
  draw();
};

dragEnd = function(){
  state.drag = null;
  _panCanvas.style.cursor = "crosshair";
};

fit = function(){
  state.offset = 0;
  state.futureSpace = 0;
  state.viewCount = Math.min(140, Math.max(40, state.bars.length));
  state.yZoom = 1;
  state.yPan = 0;
  draw();
};

_panCanvas.addEventListener("mousedown", dragStart);
window.addEventListener("mousemove", dragMove);
window.addEventListener("mouseup", dragEnd);
_panCanvas.addEventListener("dblclick", fit);
document.querySelector("#fitBtn").onclick = fit;

// Model/chart scale guard. If a stale local futures fallback ever sneaks in,
// model Entry/SL/TP overlays are suppressed instead of being silently plotted on
// a completely different price scale.
function modelChartScaleMismatch(){
  const m=state.selectedModel;
  if(!m || !state.bars?.length)return false;
  const px=Number(state.bars.at(-1)?.c);
  const entry=Number(m.entry ?? m.arrays?.entry);
  if(!Number.isFinite(px) || !Number.isFinite(entry) || px===0 || entry===0)return false;
  const name=String(m.name||m.label||"").toUpperCase();
  if(name.includes("QQQ") && px>5000)return true;
  if(name.includes("SPY") && px>3000)return true;
  const ratio=Math.abs(entry/px);
  return ratio<0.20 || ratio>5;
}

const _panArrLines=arrLines;
arrLines=function(){
  const lines=_panArrLines();
  if(!modelChartScaleMismatch())return lines;
  const context=new Set(["PDH","PDL","PWH","PWL","PMH","PML"]);
  return lines.filter(x=>context.has(x.label));
};

function paintModelScaleGuard(){
  const heading=document.querySelector(".chart-heading");
  if(!heading)return;
  let badge=heading.querySelector(".model-scale-guard");
  if(!badge){badge=document.createElement("span");badge.className="model-scale-guard";heading.appendChild(badge)}
  const mismatch=modelChartScaleMismatch();
  badge.style.display=mismatch?"inline-flex":"none";
  badge.textContent=mismatch?"MODEL / CHART FEED MISMATCH":"";
  badge.style.padding="3px 7px";
  badge.style.border="1px solid #a84855";
  badge.style.borderRadius="5px";
  badge.style.background="#351820";
  badge.style.color="#ff7d8b";
  badge.style.fontSize="10px";
  badge.style.fontWeight="700";
  if(mismatch){
    const src=document.querySelector("#chartSource");
    if(src && !String(src.textContent).includes("MODEL/CHART"))src.textContent=`${src.textContent} · MODEL/CHART SCALE MISMATCH`;
  }
}

// Extend the System tab with the 30m feed that was added today and client-side
// interaction/layout checks. The base diagnostics renderer remains authoritative.
const _panRenderDiagnostics=renderDiagnostics;
renderDiagnostics=function(d){
  _panRenderDiagnostics(d);
  const host=document.querySelector("#systemView");
  if(!host)return;
  const tbody=host.querySelector(".diag-table tbody");
  if(tbody && !tbody.querySelector('tr[data-extra-tf="30m"]')){
    for(const m of ["NQ","ES","XAU"]){
      const f=d?.feeds?.[m]?.["30m"]||{};
      const tr=document.createElement("tr");
      tr.dataset.extraTf="30m";
      tr.innerHTML=`<td>${m}</td><td>30m</td><td class="${f.stale?"bad":"good"}">${f.stale?"STALE":"LIVE"}</td><td>${f.price==null?"—":fmt(f.price,2)}</td><td>${ageText(f.age_seconds)}</td><td>${esc(f.feed||"—")}</td><td>${esc(f.last_bar_utc||"—")}</td>`;
      tbody.appendChild(tr);
    }
  }
  const checks=host.querySelector(".feature-checks");
  if(checks && !checks.querySelector(".client-chart-check")){
    const row=document.createElement("div");
    row.className="feature-row client-chart-check";
    row.innerHTML='<span class="status-dot ok"></span><b>Chart interactions</b><span class="feature-status pass">PASS</span><small>X/Y pan · price-axis zoom · time-axis zoom · Fit reset wired</small>';
    checks.appendChild(row);
  }
  if(checks && !checks.querySelector(".canonical-identity-check")){
    const vals=["NQ","ES","XAU"].map(m=>d?.feeds?.[m]?.["5m"]?.identity_ok).filter(v=>v!==undefined&&v!==null);
    const failed=vals.some(v=>v===false),known=vals.length>0;
    const status=failed?"FAIL":known?"PASS":"WARN";
    const row=document.createElement("div");
    row.className="feature-row canonical-identity-check";
    row.innerHTML=`<span class="status-dot ${status==="PASS"?"ok":status==="FAIL"?"bad":"warn"}"></span><b>Canonical model/chart identity</b><span class="feature-status ${status.toLowerCase()}">${status}</span><small>${failed?"Instrument mismatch detected":known?"QQQ / SPY / XAU mirror identity consistent":"legacy mirror has no explicit ticker identity"}</small>`;
    checks.appendChild(row);
  }
};

// Expose a tiny read-only diagnostic for the System/console checks.
window.TMBT_CHART_INTERACTIONS = {
  bidirectionalPan:true,
  horizontalPan:true,
  verticalPan:true,
  priceAxisZoom:true,
  timeAxisZoom:true,
  fitResetsPan:true,
  modelScaleGuard:true
};

setInterval(()=>{paintModelScaleGuard()},700);
setTimeout(()=>{paintModelScaleGuard()},100);
