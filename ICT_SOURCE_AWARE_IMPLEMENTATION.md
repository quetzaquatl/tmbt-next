# ICT Source-Aware Implementation Status

This document describes what TMBT Next may claim as sourced ICT Core logic versus what remains a TMBT/later-model research convention.

## Pipeline contract

All source-aware research is separated into five layers:

1. **CONTEXT** — session/range/location state.
2. **EVENT** — objective events observed on closed candles.
3. **SETUP** — a named model decides whether context + events form a trade setup.
4. **EXECUTION** — entry, stop, target, expiry and fill assumptions.
5. **RISK** — sizing and trade-management policy.

Core primitives are never allowed to jump directly from EVENT to EXECUTION. A Fair Value Gap or liquidity raid by itself is not a trade.

Implementation: TMBT_NEXT_BETA/ict_rule_engine.py

## Evidence classes

- **A / EXPLICIT_CORE** — explicit Core rule/definition.
- **B / DERIVED_CORE** — deterministic software interpretation built from A-rules.
- **C / VISUAL_CONFIRMATION_REQUIRED** — exact chart geometry still needs visual-source confirmation.
- **D / TMBT_RESEARCH_OR_LATER_ICT** — TMBT research convention or later ICT model; not a 2016/17 Core rule.

Registry: TMBT_NEXT_BETA/ict_core_rules.py

## Implemented Core primitives

### OTE / Premium-Discount
- 50% equilibrium.
- OTE zone 62%-79%.
- 70.5% reference.
- Selecting the active swing/dealing range remains a TMBT quantification unless a profile defines it more specifically.

### Fair Value Gap
- Three-candle imbalance primitive is implemented.
- The engine reports zone, CE, later touch and full traversal.
- The primitive intentionally does **not** call touch/traversal mitigation, invalidation or an entry signal without a model-specific rule.

### Liquidity
- Old highs/lows are treated as structural liquidity references.
- TMBT left/right pivot integers are explicitly research geometry, not canonical ICT constants.
- A raid and a close back through the reference are recorded as separate observations.

### Index futures context
- 09:30-10:30 New York Opening Range.
- 09:30-12:00 AM context.
- NQ/ES SMT remains available.
- YM historical/live-mirror plumbing is prepared. Target-vs-YM SMT is advisory research metadata only until separately validated.

## Canonical research matrix

Default scheduler mode is now **SOURCE-AUDITED** instead of the old automatically generated 49-profile matrix.

Default canonical queue (15 profiles):

- NQ_EBP_H1
- ES_EBP_H1
- XAU_OTE_BOS_M15
- XAU_SWEEP_IFVG_M5
- NQ_SILVER_BULLET_M1
- ES_SILVER_BULLET_M1
- NQ_TTFM_D1_H1_M5
- NQ_TTFM_D1_H4_M15
- NQ_TTFM_H1_M15_M1
- ES_TTFM_D1_H1_M5
- ES_TTFM_D1_H4_M15
- ES_TTFM_H1_M15_M1
- GC_TTFM_D1_H1_M5
- GC_TTFM_D1_H4_M15
- GC_TTFM_H1_M15_M1

Generated M1/M3/M5/M15/M30/H1/H4 clones remain available only when experimental_timeframe_matrix_enabled=true (or legacy full_model_matrix_enabled=true).

This prevents a generated timeframe clone from being presented as if it were a separately sourced/canonical model.

## Model-family boundaries

### OTE BOS
Core-sourced:
- OTE zone/premium-discount concepts.
- old high/low liquidity concepts.

TMBT-specific:
- exact BOS boolean.
- pivot integers.
- ATR impulse threshold.
- execution/expiry conventions.

### Sweep iFVG
Core-sourced components:
- FVG primitive.
- liquidity references.

Not a complete 2016/17 Core model:
- inversion FVG state machine.
- CE-on-iFVG entry.
- fixed lookback/inversion/retest bar counts such as 18/12/12.

### Silver Bullet
The concrete Silver Bullet model is treated as later ICT/TMBT, not retroactively labelled as 2016/17 Core.

### EBP
Formalized TMBT model, not a named ICT 2016/17 Core model.

### TTFM
Top-down/fractal hierarchy is compatible with the public TTrades material used by the implementation. Exact state-machine thresholds remain TMBT conventions and are not claimed as proprietary indicator rules.

## Research-only source snapshot

Read-only historical diagnostic:

~~~powershell
py -3 .\TMBT_NEXT_BETA\ict_research_snapshot.py --market NQ --tf 5m
~~~

The output contains only CONTEXT/EVENT primitives. SETUP, EXECUTION and RISK remain locked.

## Verification

~~~powershell
py -3 .\TMBT_NEXT_BETA\verify_ict_core_patch.py
~~~

or:

~~~powershell
.\TMBT_NEXT_BETA\VERIFY_ICT_CORE_AUDIT.bat
~~~

The verification checks:
- provenance separation;
- canonical vs generated variants;
- three-candle FVG detection;
- confirmed old-high liquidity raid;
- locked SETUP/EXECUTION/RISK layers;
- Month-10 Opening Range context;
- syntax of the source-aware integration modules.

## Safety / research discipline

- Core source claims and profitability claims are separate.
- No Core rule automatically promotes a model to live.
- Holdout/OOS remains locked until the existing manual review gate.
- Generated timeframe variants are discovery experiments only.
- If a rule depends on chart geometry that cannot be supported textually, it remains evidence class C until visually audited.
