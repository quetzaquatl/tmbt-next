# Trader Observations

This file stores examples of how the trader reads context. These are **not fixed model criteria**, **not automatic entry filters**, **not hard vetoes**, and **not universal rules** unless the trader explicitly promotes one later.

The purpose is to preserve discretionary examples for research, annotation, and future pattern discovery without changing live/backtest logic.

## 2026-09-16/17 examples

- NQ: a weekly FVG low was filled and used as part of the discretionary bullish bias for that specific trade.
- XAU: downside failure swings into the 4250 area were part of the discretionary bullish read for that specific trade.
- Weekly narrative: a Wednesday reversal / weekly-profile idea was part of the interpretation of those examples.
- Delivery language: "stairs up, elevator down" describes the trader's expectation that a slow grind can be followed by a faster opposite delivery. It is descriptive context, not a standalone setup rule.
- Trade outcome note: one referenced trade booked about 3R. This is an example outcome, not a fixed target rule.

## Handling rule

When similar examples are provided in chat, store them as qualitative observations or trade annotations first. Do not convert them into criteria, scoring factors, filters, vetoes, or targets unless the trader explicitly says to formalize that item as a rule.

Current explicitly formalized context remains separate from these observations (for example SMT / PO3 / Asia / Midnight work already requested elsewhere).

## 2026-09-17/18 XAU / NAS notes

- XAU: earlier long opportunities during the day were missed because attention was mainly on NAS. The trader would otherwise have preferred a lower long entry.
- XAU: the actual evening long entry was taken at the **H1 iFVG high**.
- XAU: the intended draw was first the visible **failure highs**, and beyond those the larger draw around **4500**.
- The fact that a late entry used an H1 iFVG high is an example of execution after the broader read was already bullish; it is not a universal rule saying H1 iFVG highs must be bought.
- A NAS chart update was supplied alongside this note as ongoing trade context. No additional fixed criterion was declared from that update.

## Storage / usage boundary

These notes are a record of the trader's discretionary thinking only. They may be shown in the Studio for reference and later research annotation, but **must not be imported by the live engine, backtest filters, criteria lists, scoring, veto logic, targets, or automated trade management** unless the trader explicitly promotes a specific observation into a formal rule in a later instruction.

## 2026-09-22 XAU morning trade / management observation

- First trade of the week, taken Tuesday morning on **XAUUSD long**. The supplied 1H chart shows entry around **4300.2**, protective stop around **4277.0** and the planned upper objective around **4399.6 / 4400** (about **4.28R** on the TradingView position tool).
- Discretionary context supplied by the trader: **H4 iFVG low**, an **H1 reference/close in the same area**, a **daily order block**, and the stop placed **below the H1 order block**.
- Weekly/day-of-week narrative: **Tuesday low-of-week anticipation** plus a **Monday engulf** were part of the bullish read for this specific trade.
- Chart read: price sold sharply from the Monday/Tuesday intraday range into the clustered 4300-area higher-timeframe references before the long was taken. This is stored as a confluence example, not as a universal entry rule.
- Separate XAU OTE management example from the same research discussion: the trade was roughly **+1.5R** in open profit and reached/raided the **next sell-side-liquidity (SSL) low**, then later reversed and hit the original stop. This is an observation motivating research into partial-profit and break-even/progressive-stop rules at logical liquidity objectives.
- Research boundary: do **not** turn the H4/H1 iFVG, daily OB, Tuesday-low narrative, Monday engulf, +1.5R threshold, SSL touch, partial amount, or break-even move into fixed model criteria/management rules until they are explicitly parameterized and validated model-by-model.
