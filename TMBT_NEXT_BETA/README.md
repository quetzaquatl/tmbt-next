# TMBT Next Beta 0.9

Parallel frontend for the existing Trading Model Backtest Studio.

## It does NOT replace the old Studio
The current Streamlit app stays untouched on port 8502.
TMBT Next runs separately on port 8510 and reads the same workspace.

## Start
Double-click:
`START_TMBT_NEXT.bat`

Then open:
`http://127.0.0.1:8510`

Default workspace:
`D:\Projekt model\Trading_Model_Backtest_Studio_WORKSPACE`

## Connected features
- Live model monitor
- Persistent live candle chart
- NQ / ES / XAU + timeframe switch
- Model overlays: Entry / SL / TP and stored setup arrays
- Previous Day / Week / Month ranges derived from 1H cache
- Zoom with mouse wheel
- Pan by dragging chart
- Crosshair + OHLC on hover
- Resizable left / right / bottom panes
- Frozen setup archive snapshots
- Outcome summary
- Research job progress
- Paper account state, open positions and closed trades
- Browser research-completion alerts
- No full-page Streamlit rerenders / no flicker

## Safety
This beta is intentionally read-only:
- no broker orders
- no strategy changes
- no starting/cancelling research jobs
- no writes into the existing TMBT workspace

Use the `Old Studio ↗` button for configuration/actions while evaluating this UI.
