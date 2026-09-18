# TTFM Public-Core Implementation

Status: **formalized research model**  
Engine: `TMBT_NEXT_BETA/ttfm_engine.py`  
Rule version: `ttfm-public-core-v1`

This module implements only the parts of the TTrades Fractal Model that are
described publicly enough to make point-in-time rules. It is **not** a copy of
the private TradingView indicator and does not attempt to reverse engineer
T-Spot or undocumented indicator internals.

## Public source map

### Candle 2
Source:
https://ttrades.com/understanding-candle-2-closures-within-the-fractal-model/

Formal rule:
- bullish C2: current candle trades below the previous low and closes back
  inside the previous candle range;
- bearish C2: current candle trades above the previous high and closes back
  inside the previous candle range;
- C2 is a reversal closure;
- a POI is required;
- after a C2 closure, C3 is the expected continuation candle.

### Candle 3
Source:
https://ttrades.com/candle-3-closure-a-complete-guide-to-identifying-continuations-and-reversals/

Formal rule:
- C3 is considered only if C2 did not already provide the valid reversal close;
- bullish C3 closes through the body of C2; bearish mirrors;
- the public guide says C3 should do this without sweeping the C2 extreme;
- C2 must have interacted with a POI;
- C4 is the expected expansion after a valid C3 closure.

The public material also describes a failed-C2-sweep variant. The engine accepts
both public descriptions and records the exact variant in every trade.

### CISD / protected swing
Source:
https://ttrades.com/how-change-in-the-state-of-delivery-cisd-confirms-swing-points/

Formal rule:
- the higher-timeframe C2/C3 closure comes first;
- lower timeframe CISD must occur inside that higher-timeframe candle;
- bullish CISD closes through the candle series that created the low;
- bearish CISD mirrors;
- without lower-timeframe CISD, the higher-timeframe swing is rejected;
- the confirmed swing is the protected swing.

### D1 -> H1 -> M5
Source:
https://ttrades.com/fractal-model-playbook-aligning-daily-hourly-and-5-minute-charts/

Formal alignment:
- one-sided Daily bias / Daily closure first;
- H1 CISD confirmation in the same direction;
- previous-day range EQ is respected;
- M5 CISD confirms the entry structure;
- protected swing is the invalidation;
- target is at least 2R or a higher-timeframe objective.

### D1 -> H4 -> M15
Source:
https://ttrades.com/the-best-timeframes-for-ttrades-fractal-model-simple/

Formal alignment:
- Daily bias;
- H4 swing / confirmation;
- M15 continuation execution;
- stop at protected swing;
- 2R or higher-timeframe objective.

### H1 -> M15 -> M1 Scalping
Source:
https://ttrades.com/ttrades-scalping-model-simple-day-trading-strategy/

Formal alignment:
- Daily is broader context;
- H1 C2/C3 sets scalping bias;
- M15 creates the swing forming the H1 wick;
- M1 executes using FVG interaction / CISD / protected swing;
- the trade is the body/expansion of the H1 candle.

### POI hierarchy
Source:
https://ttrades.com/the-only-points-of-interest-that-actually-matter-for-trading/

Order:
1. FVG;
2. swing high / swing low;
3. CISD retest.

The first engine version uses FVG and prior swing as pre-confirmation POIs.
CISD is used as the confirmation primitive itself; a separate CISD-retest entry
variant can be A/B tested later without changing the core model.

## TMBT execution conventions

The public education does not specify every machine-level detail needed for a
backtest. These choices are therefore explicitly **TMBT conventions**, not
claimed TTrades rules:

- CISD candle series:
  contiguous opposing-body candles delivering into a confirmed pivot;
- CISD reference:
  open/origin of that opposing series;
- pivot confirmation:
  left/right closed-bar pivots; default 2/2;
- entry:
  next 1-minute open after the lowest-timeframe CISD closes;
- stop:
  protected swing plus optional configured buffer;
- target:
  fixed minimum 2R for the base research profile;
- OHLCV execution:
  conservative; if SL and TP occur inside the same 1-minute candle, SL wins;
- no Early C2 CISD:
  only completed bars may create a historical setup.

These convention parameters may be optimized because they are implementation
choices. Public/core closure definitions are not silently changed by the
optimizer.

## Research profiles

Created for each of **NQ, ES and GC**:

- `*_TTFM_D1_H1_M5`
- `*_TTFM_D1_H4_M15`
- `*_TTFM_H1_M15_M1`

GC is Gold Futures research. It is intentionally not presented as XAU/USD spot.

## Optimizer scope

Only these implementation choices are currently optimized:

1. protected-swing pivot left/right confirmation;
2. maximum CISD confirmation bars;
3. fixed target RR, constrained to >= 2R.

The optimizer does **not** invent private T-Spot rules, hidden wick thresholds,
or undocumented indicator behavior.

## Live policy

No TTFM profile is promoted to live merely because it backtests positive.
It must pass the same strict Development/Validation/OOS review framework used by
TMBT Next. Until then, TTFM is research-only.
