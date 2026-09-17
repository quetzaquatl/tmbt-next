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

// Expose a tiny read-only diagnostic for the System/console checks.
window.TMBT_CHART_INTERACTIONS = {
  bidirectionalPan:true,
  horizontalPan:true,
  verticalPan:true,
  priceAxisZoom:true,
  timeAxisZoom:true,
  fitResetsPan:true
};
