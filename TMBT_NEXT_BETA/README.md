# TMBT Next Beta 0.9.4

Parallel frontend for the existing Trading Model Backtest Studio.

## It does NOT replace the old Studio yet
The current Streamlit app stays untouched on port 8502.
TMBT Next runs separately on port 8510 and reads the same workspace.

## Start
Double-click:
`START_TMBT_NEXT.bat`

Then open:
`http://127.0.0.1:8510`

Default workspace:
`D:\Projekt model\Trading_Model_Backtest_Studio_WORKSPACE`

## Data pipeline
TMBT Next now follows the original Studio 4.6 data path again:
- original Twelve live mirror when available
- newer local SQLite live cache on the workstation takes priority
- no Yahoo / GC proxy fallback
- explicit LIVE / STALE state and data age
- System tab shows every market/timeframe plus workspace health

## Connected features
- Live model monitor
- Persistent NQ / ES / XAU candle chart
- 5m / 15m / 1H / 4H / 1D switching
- Model overlays: Entry / SL / TP and stored setup arrays
- Previous Day / Week / Month ranges derived from the original feed
- Price/time zoom, pan, crosshair and OHLC hover
- Resizable panes with saved layout
- Frozen setup archive snapshots
- Outcome summary
- Research job progress
- Paper account state, open positions and closed trades
- Browser alerts for research completion and model-stage changes
- System diagnostics / read-only feature self-checks
- Live updates avoid full chart/list rerenders when nothing changed

## Keyboard
- `1` NQ
- `2` ES
- `3` XAU
- `F` fit chart
- `Esc` leave frozen snapshot

## Safety
This beta is intentionally read-only:
- no broker orders
- no strategy changes
- no starting/cancelling research jobs
- no writes into the existing TMBT workspace

Use the `Old Studio ↗` button for configuration/actions while evaluating this UI. Research controls and eventual execution controls should be added only after the read-only desk is stable and fully auditable.
