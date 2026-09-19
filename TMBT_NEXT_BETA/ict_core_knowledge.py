from __future__ import annotations

"""
ICT 2016/17 Premium Mentorship Core Content knowledge base for TMBT Next.

This module is deliberately broader than ict_core_rules.py:
- all 115 Core Content lectures are indexed;
- source-aware concept/rule knowledge is stored here even when it is not safe
  to turn into a deterministic trading rule;
- executable strategy logic remains in ict_core_rules.py / ict_rule_engine.py
  only after the source statement has been reduced without inventing geometry.

No transcript text is copied into the repository. We retain compact paraphrases,
timestamps, lesson references and machine-readiness status.

Primary source family:
- The Inner Circle Trader, 2016 Premium Mentorship Core Content, Months 1-12.
- Public lecture index/transcript mirror:
  https://info.quagmyre.com/xwiki/bin/view/Forex/The-Inner-Circle-Trader/ICT-2016-Premium-Mentorship-Core-Content-Lectures/
- Public lecture outlines:
  https://info.quagmyre.com/xwiki/bin/view/Forex/The-Inner-Circle-Trader/ICT-2016-Premium-Mentorship-Core-Content-Lectures/Outlines/
"""

from typing import Any

KNOWLEDGE_VERSION = "ict-core-knowledge-v1"
INDEX_SOURCE = (
    "https://info.quagmyre.com/xwiki/bin/view/Forex/The-Inner-Circle-Trader/"
    "ICT-2016-Premium-Mentorship-Core-Content-Lectures/"
)
OUTLINE_SOURCE = INDEX_SOURCE + "Outlines/"

EVIDENCE = {
    "A": "EXPLICIT_CORE",
    "B": "DERIVED_CORE",
    "C": "VISUAL_CONFIRMATION_REQUIRED",
    "D": "TMBT_QUANTIFICATION_OR_NON_CORE",
}

MACHINE_STATUS = {
    "READY": "safe to expose as a deterministic primitive",
    "PARTIAL": "some pieces are deterministic; context/geometry remains discretionary",
    "REFERENCE": "knowledge/reference only; do not use as an automatic trade rule",
    "VISUAL": "requires chart/visual audit before exact geometry can be coded",
}

# (global_lesson, duration, title)
LECTURE_ROWS = [
    (1, "0:20:20", "Elements Of A Trade Setup"),
    (2, "0:25:22", "How Market Makers Condition The Market"),
    (3, "0:25:03", "What To Focus On Right Now"),
    (4, "0:56:29", "Equilibrium Vs. Discount"),
    (5, "0:20:59", "Equilibrium Vs. Premium"),
    (6, "0:32:34", "Fair Valuation"),
    (7, "0:24:55", "Liquidity Runs"),
    (8, "0:12:13", "Impulse Price Swings & Market Protraction"),
    (9, "0:29:08", "Growing Small Accounts"),
    (10, "0:09:56", "Framing Low Risk Trade Setups"),
    (11, "0:18:05", "How Traders Make 10% Per Month"),
    (12, "0:20:04", "No Fear Of Losing"),
    (13, "0:17:34", "How To Mitigate Losing Trades Effectively"),
    (14, "1:03:56", "The Secrets To Selecting High Reward Setups"),
    (15, "0:29:52", "Market Maker Trap False Flag"),
    (16, "0:20:52", "Market Maker Trap False Breakouts"),
    (17, "0:49:25", "Timeframe Selection & Defining Setups"),
    (18, "0:30:32", "Institutional Order Flow"),
    (19, "0:43:55", "Institutional Sponsorship"),
    (20, "0:15:15", "The Next Setup - Anticipatory Skill Development"),
    (21, "0:20:36", "Institutional Market Structure"),
    (22, "0:19:00", "Macro Economic To Micro Technical"),
    (23, "0:24:42", "Market Maker Trap Trendline Phantoms"),
    (24, "0:17:34", "Market Maker Trap Head Shoulders Pattern"),
    (25, "0:20:55", "Interest Rate Effects On Currency Trades"),
    (26, "0:43:34", "Reinforcing Liquidity Concepts & Price Delivery"),
    (27, "0:35:48", "Orderblocks"),
    (28, "0:15:06", "Mitigation Blocks"),
    (29, "0:10:01", "ICT Breaker Block"),
    (30, "0:15:15", "ICT Rejection Block"),
    (31, "0:11:09", "Reclaimed ICT Orderblock"),
    (32, "0:07:50", "ICT Propulsion Block"),
    (33, "0:14:51", "ICT Vacuum Block"),
    (34, "0:14:39", "Liquidity Voids"),
    (35, "0:22:18", "Liquidity Pools"),
    (36, "0:17:57", "ICT Fair Value Gaps FVG"),
    (37, "0:21:53", "Divergence Phantoms"),
    (38, "0:15:04", "Double Bottom Double Top"),
    (39, "0:55:09", "Quarterly Shifts & IPDA Data Ranges"),
    (40, "0:23:42", "Open Float"),
    (41, "2:02:42", "Using IPDA Data Ranges"),
    (42, "0:27:31", "Defining Open Float Liquidity Pools"),
    (43, "0:32:57", "Defining Institutional Swing Points"),
    (44, "0:17:31", "Using 10 Year Notes In HTF Analysis"),
    (45, "0:09:31", "Qualifying Trade Conditions With 10 Year Yields"),
    (46, "0:18:38", "Interest Rate Differentials"),
    (47, "0:21:27", "How To Use Intermarket Analysis"),
    (48, "0:18:45", "How To Use Bullish Seasonal Tendencies In HTF Analysis"),
    (49, "0:35:08", "How To Use Bearish Seasonal Tendencies In HTF Analysis"),
    (50, "0:13:57", "Ideal Seasonal Tendencies"),
    (51, "0:34:10", "Money Management"),
    (52, "0:32:12", "Defining HTF PD Arrays"),
    (53, "0:28:19", "Trade Conditions & Setup Progressions"),
    (54, "0:13:54", "Stop Entry Techniques For Long Term Traders"),
    (55, "0:11:14", "Limit Order Entry Techniques For Long Term Traders"),
    (56, "0:25:44", "Position Trade Management"),
    (57, "0:20:05", "Ideal Swings Conditions For Any Market"),
    (58, "0:22:23", "Elements To Successful Swing Trading"),
    (59, "0:40:03", "Classic Swing Trading Approach"),
    (60, "0:39:46", "High Probability Swing Trade Setups In Bull Markets"),
    (61, "0:31:35", "High Probability Swing Trade Setups In Bear Markets"),
    (62, "0:30:07", "Reducing Risk and Maximizing Potential Reward In Swing Setups"),
    (63, "0:27:05", "Keys To Selecting Markets That Will Move Explosively"),
    (64, "0:38:28", "The Million Dollar Swing Setup"),
    (65, "0:44:59", "Short Term Trading Using Monthly & Weekly Ranges"),
    (66, "0:11:04", "Short Term Trading Defining Weekly Range Profiles"),
    (67, "0:40:52", "Short Term Trading Market Maker Manipulation Templates"),
    (68, "0:16:29", "Short Term Trading Blending IPDA Data Ranges & PD Arrays"),
    (69, "0:25:03", "Short Term Trading Low Resistance Liquidity Runs Part 1"),
    (70, "0:25:51", "Short Term Trading Low Resistance Liquidity Runs Part 2"),
    (71, "0:28:33", "Intraweek Market Reversals & Overlapping Models"),
    (72, "0:37:39", "One Shot One Kill Model"),
    (73, "0:46:37", "Essentials To ICT Daytrading"),
    (74, "0:10:44", "Defining The Daily Range"),
    (75, "0:16:30", "Central Bank Dealers Range"),
    (76, "0:30:02", "Projecting Daily Highs & Lows"),
    (77, "0:21:56", "Intraday Profiles"),
    (78, "0:34:33", "When To Avoid The London Session"),
    (79, "0:30:55", "High Probability Daytrade Setups"),
    (80, "0:23:42", "Integrating Daytrades With HTF Trade Entries"),
    (81, "0:12:48", "The Sentiment Effect"),
    (82, "0:28:58", "Filling The Numbers"),
    (83, "0:18:55", "20 Pips Per Day"),
    (84, "0:21:14", "Trading In Consolidations"),
    (85, "0:37:02", "Trading Market Reversals"),
    (86, "0:32:06", "Bread & Butter Buy Setups"),
    (87, "0:27:54", "Bread & Butter Sell Setups"),
    (88, "0:58:08", "ICT Day Trade Routine"),
    (89, "0:34:35", "Commitment Of Traders"),
    (90, "0:40:04", "Relative Strength Analysis - Accumulation & Distribution"),
    (91, "0:42:03", "Commodity Seasonals Tendencies - My Personal Favorites"),
    (92, "0:19:23", "Premium Vs. Carrying Charge Market"),
    (93, "0:20:34", "Open Interest Secrets & Smart Money Footprints"),
    (94, "0:18:26", "Bond Trading - Basics & Opening Range Concept"),
    (95, "0:17:56", "Bond Trading - Split Session Rules"),
    (96, "0:26:59", "Bond Trading - Consolidation Days"),
    (97, "0:20:24", "Bond Trading - Trending Days"),
    (98, "0:11:58", "Index Futures - Basics & Opening Range Concept"),
    (99, "0:19:43", "Index Futures - AM Trend"),
    (100, "0:13:07", "Index Futures - PM Trend"),
    (101, "0:17:46", "Index Futures - Projected Range & Objectives"),
    (102, "0:21:11", "Index Futures - Index Trade Setups"),
    (103, "0:21:00", "Stock Trading - Seasonals & Monthly Swings"),
    (104, "0:21:06", "Stock Trading - Building Buy Watchlists"),
    (105, "0:13:50", "Stock Trading - Building Sell Watchlists"),
    (106, "0:35:59", "Stock Trading - Using Options"),
    (107, "0:27:23", "Importance Of Multi-Asset Analysis"),
    (108, "0:40:14", "Commodity Mega-Trades"),
    (109, "0:22:33", "Forex & Currency Mega-Trades"),
    (110, "0:53:29", "Stock Mega-Trades"),
    (111, "0:43:57", "Bond Mega-Trades"),
    (112, "0:54:11", "Long Term Top Down Analysis"),
    (113, "0:48:47", "Intermediate Term Top Down Analysis"),
    (114, "0:32:34", "Short Term Top Down Analysis"),
    (115, "1:05:33", "Intraday Top Down Analysis"),
]

MONTH_RANGES = {
    1: (1, 8),
    2: (9, 16),
    3: (17, 24),
    4: (25, 38),
    5: (39, 56),
    6: (57, 64),
    7: (65, 72),
    8: (73, 80),
    9: (81, 88),
    10: (89, 107),
    11: (108, 111),
    12: (112, 115),
}


def _month_of(global_lesson: int) -> int:
    for month, (a, b) in MONTH_RANGES.items():
        if a <= global_lesson <= b:
            return month
    raise KeyError(global_lesson)


def _month_lesson(global_lesson: int) -> int:
    month = _month_of(global_lesson)
    return global_lesson - MONTH_RANGES[month][0] + 1


def _seconds(duration: str) -> int:
    parts = [int(x) for x in duration.split(":")]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


LECTURES: list[dict[str, Any]] = [
    {
        "global_lesson": n,
        "month": _month_of(n),
        "month_lesson": _month_lesson(n),
        "title": title,
        "duration": duration,
        "duration_seconds": _seconds(duration),
        "index_source": INDEX_SOURCE,
        "outline_source": OUTLINE_SOURCE,
        "transcript_available": True,
        "outline_available": True,
        # The lecture is present in the complete 115-lesson corpus. This field
        # does NOT claim that every visual frame is machine-verifiable.
        "corpus_status": "INDEXED",
    }
    for n, duration, title in LECTURE_ROWS
]

# Compact, source-aware lecture focus index. These are paraphrased topic labels,
# not copied transcript text. It lets TMBT locate the relevant lessons without
# pretending that a title or outline is itself an executable rule.
LESSON_FOCUS: dict[int, tuple[str, ...]] = {
    1: ("market states", "expansion", "consolidation", "retracement", "reversal", "liquidity voids"),
    2: ("price delivery", "market-maker perspective", "daily range reversal"),
    3: ("clean highs/lows", "liquidity voids", "journaling"),
    4: ("impulse swing", "equilibrium", "discount", "OTE"),
    5: ("impulse swing", "premium", "OTE", "profit targets", "daily bias"),
    6: ("fair valuation", "liquidity void", "consolidation", "range valuation"),
    7: ("liquidity", "old highs/lows", "high/low resistance liquidity runs"),
    8: ("impulse swing", "market protraction", "time sensitivity", "London"),
    9: ("risk", "selectivity", "small accounts", "sample statistics"),
    10: ("low-risk framing", "order block", "entry refinement"),
    11: ("liquidity pools", "institutional sponsorship", "partials"),
    12: ("reward/risk", "loss acceptance", "sample distribution"),
    13: ("loss mitigation", "re-entry", "stop management"),
    14: ("high-reward setup selection", "top-down", "sentiment", "flowchart"),
    15: ("false flags", "market-maker trap", "objectives"),
    16: ("false breakouts", "liquidity absorption", "stop runs"),
    17: ("timeframe selection", "monthly/weekly/daily", "modular setups", "order blocks"),
    18: ("institutional order flow", "liquidity seeking", "order blocks"),
    19: ("institutional sponsorship", "market structure", "Power of Three", "order blocks"),
    20: ("anticipation", "monthly/daily/weekly", "recent opposing candles"),
    21: ("institutional market structure", "cross-market divergence", "liquidity"),
    22: ("macro-to-micro", "bonds", "dollar index", "intermarket divergence"),
    23: ("trendline trap", "context over diagonal lines"),
    24: ("head-and-shoulders trap", "institutional order flow", "order blocks"),
    25: ("interest-rate triads", "cross-market validation", "action plan"),
    26: ("liquidity", "price delivery", "multi-timeframe", "order blocks"),
    27: ("bullish/bearish order blocks", "midpoint", "equal highs", "refinement"),
    28: ("mitigation blocks", "market-structure shift", "reference points"),
    29: ("breaker blocks", "bullish/bearish breaker", "mitigation"),
    30: ("rejection blocks", "false breaks", "accumulation/distribution", "stop entry"),
    31: ("reclaimed order block", "hedging", "re-use of reference levels"),
    32: ("propulsion block", "candle break condition"),
    33: ("vacuum block", "breakaway gap", "time-sensitive gap"),
    34: ("liquidity voids", "gap closure", "uniform delivery"),
    35: ("liquidity pools", "old highs/lows", "stop raids", "bias"),
    36: ("fair value gap", "liquidity void", "old-high/old-low run", "efficient delivery"),
    37: ("divergence", "trend context", "order block"),
    38: ("double top/bottom", "clean highs/lows", "liquidity beyond extremes"),
    39: ("quarterly shifts", "IPDA data ranges", "intermediate-term structure"),
    40: ("open float", "12-month highs/lows", "market-structure break", "bias"),
    41: ("IPDA data ranges", "20/40/60-day lookbacks", "FVG", "open interest"),
    42: ("open-float liquidity pools", "20/40/60-day ranges", "institutional order flow"),
    43: ("institutional swing points", "failure swing", "breaker", "entry pattern"),
    44: ("10-year notes", "dollar index", "seasonality", "HTF analysis"),
    45: ("10-year yields", "correlation symmetry", "trend qualification"),
    46: ("interest-rate differentials", "currency selection", "HTF premise"),
    47: ("intermarket analysis", "lead/lag", "dollar", "bonds", "commodities", "stocks"),
    48: ("bullish seasonality", "HTF analysis", "cross-asset confirmation"),
    49: ("bearish seasonality", "HTF analysis", "seasonality is not guaranteed"),
    50: ("seasonality", "currency pairs", "HTF roadmap"),
    51: ("money management", "timeframe-proportionate stops", "partials", "exposure"),
    52: ("HTF PD arrays", "array ordering", "breaker", "premium/discount"),
    53: ("trade-condition progression", "rebalance", "order blocks", "PD arrays"),
    54: ("stop-entry techniques", "opening-price confirmation", "long-term"),
    55: ("limit-entry techniques", "PD arrays", "premium/discount", "long-term"),
    56: ("position management", "intermarket alignment", "40-day extremes", "limit fill risk"),
    57: ("swing trading", "monthly/weekly bias", "directional setups"),
    58: ("swing selection", "relative strength", "clear levels", "money-management discipline"),
    59: ("classic swing approach", "monthly/weekly", "retracement timing", "PD matrix", "3R"),
    60: ("bull-market swing setups", "monthly/weekly bias", "order blocks"),
    61: ("bear-market swing setups", "multi-timeframe bearishness", "premium arrays", "order blocks"),
    62: ("swing risk/reward", "monthly/weekly framing", "3R"),
    63: ("explosive-market selection", "COT", "open interest", "volatility filter", "news"),
    64: ("million-dollar swing", "seasonality", "top-down", "stop progression", "entry type"),
    65: ("short-term trading", "monthly/weekly ranges", "risk/reward", "kill zones", "PD arrays"),
    66: ("weekly profiles", "Tuesday low", "Wednesday high", "Thursday reversal", "neutral profile"),
    67: ("manipulation templates", "Tuesday high/low", "reflection pattern", "four stages"),
    68: ("IPDA + PD arrays", "20-day lookback", "time+price", "mitigation blocks"),
    69: ("low-resistance liquidity run", "premium/discount", "PD arrays", "consolidation"),
    70: ("low-resistance liquidity run", "4H", "trading range", "order blocks"),
    71: ("intraweek reversals", "model overlap", "HTF context"),
    72: ("one-shot-one-kill", "COT", "macro", "weekly order block"),
    73: ("daytrading essentials", "directional bias", "40/60-day PD arrays", "London", "weekly range"),
    74: ("daily range", "true day", "New York time", "CME open", "London close"),
    75: ("Central Bank Dealers Range", "14:00-20:00 NY", "body range", "bias"),
    76: ("projected daily high/low", "CBDR", "London kill zone", "standard deviations"),
    77: ("intraday profiles", "CBDR width", "midnight", "London open"),
    78: ("London avoidance", "large-range day", "news", "ADR", "rule-based no-trade"),
    79: ("high-probability daytrade", "London extremes", "day-of-week", "stop", "profit taking"),
    80: ("daytrade + HTF entry", "premium/discount", "intraday timing", "protective stop"),
    81: ("sentiment effect", "opening price", "daytrade conditions", "premium array"),
    82: ("zero-GMT pivots", "daily range projection", "Asian range", "bias"),
    83: ("20-pip scalp", "Asian session", "short-term high/low", "fade"),
    84: ("consolidation", "HTF order flow", "equilibrium", "fading extremes"),
    85: ("market reversals", "previous-day high/low", "New York reversal", "London close"),
    86: ("bread-and-butter buy", "repricing", "London open", "Judas swing", "time of day"),
    87: ("bread-and-butter sell", "offset distribution", "London Judas", "ADR exit", "time+price"),
    88: ("day-trade routine", "60-day lookback", "breaker", "institutional order flow", "OTE"),
    89: ("COT", "commercial hedging", "net positioning"),
    90: ("relative strength", "accumulation/distribution", "failure swing", "cross-market leadership"),
    91: ("commodity seasonality", "seasonality is not deterministic"),
    92: ("carrying charge", "premium", "commercial bull market", "spread analysis"),
    93: ("open interest", "trend", "seasonal average", "discount array"),
    94: ("bond opening range", "volume divergence", "trend/consolidation"),
    95: ("bond split sessions", "AM/PM", "reversal profile", "FVG"),
    96: ("bond consolidation day", "economic calendar", "overnight highs/lows", "rule-based testing"),
    97: ("bond trend day", "volatility", "premium/discount", "economic catalyst"),
    98: ("index futures", "opening range", "09:30 equities open", "time of day"),
    99: ("index AM trend", "relative highs/lows", "institutional order flow", "divergence"),
    100: ("index PM trend", "13:00-16:00 NY", "lunch", "relative highs/lows", "index divergence"),
    101: ("index projected range", "AM/PM relationship", "premium/discount", "consolidation"),
    102: ("index trade setups", "ES/NQ/YM comparison", "PM time-of-day", "divergence"),
    103: ("stock seasonality", "monthly swings", "calendar tendency"),
    104: ("stock buy watchlist", "index-relative strength", "weekly direction"),
    105: ("stock sell watchlist", "bearish month filter", "index-relative weakness"),
    106: ("stock options", "fundamentals", "institutional participation", "seasonality"),
    107: ("multi-asset analysis", "bonds", "dollar", "commodities", "stocks"),
    108: ("commodity mega-trades", "relative strength", "sector diversification"),
    109: ("FX mega-trades", "seasonality", "dollar index", "relative strength"),
    110: ("stock mega-trades", "market direction", "fundamental strength", "watchlists"),
    111: ("bond mega-trades", "seasonality", "Treasury curve", "cross-bond divergence"),
    112: ("long-term top-down", "seasonality", "rates", "quarterly shift", "market state", "PD matrix"),
    113: ("intermediate top-down", "weekly bias", "sentiment", "institutional focus", "COT"),
    114: ("short-term top-down", "bias", "institutional order flow", "weekly open", "midnight open"),
    115: ("intraday top-down", "CBDR deviations", "daily range projection", "OTE", "breaker", "FVG"),
}

# Source-aware rules/concepts that recur across the corpus. The purpose here is
# to preserve what the Core teaches, including material that is not suitable for
# mechanical trading. machine_status=READY is intentionally rare.
RULE_CATALOG: dict[str, dict[str, Any]] = {
    "CORE_MARKET_STATES": {
        "concept": "market_states",
        "summary": "Classify price delivery as expansion, retracement, reversal or consolidation before selecting a setup.",
        "lessons": [1, 6, 84, 112],
        "evidence_class": "B",
        "machine_status": "PARTIAL",
        "note": "The taxonomy is explicit; exact state thresholds are not universal Core constants.",
    },
    "CORE_IMPULSE_SWING_CONTEXT": {
        "concept": "impulse_price_swing",
        "summary": "An impulse swing is the range used to reason about retracement, valuation and potential continuation/reversal.",
        "lessons": [4, 5, 8],
        "evidence_class": "B",
        "machine_status": "PARTIAL",
    },
    "CORE_EQUILIBRIUM_PREMIUM_DISCOUNT": {
        "concept": "premium_discount",
        "summary": "Use the relevant dealing/impulse range around equilibrium; seek longs in discount and shorts in premium when directional context supports it.",
        "lessons": [4, 5, 52, 53, 59, 65, 69, 70, 101, 112],
        "evidence_class": "B",
        "machine_status": "PARTIAL",
        "note": "50% equilibrium is deterministic; selecting the active range is contextual.",
    },
    "CORE_OTE": {
        "concept": "OTE",
        "summary": "Optimal Trade Entry is a deep retracement area inside a relevant price swing, with 70.5% used as a reference inside the 62%-79% zone.",
        "lessons": [4, 5, 88, 115],
        "evidence_class": "A",
        "machine_status": "READY",
    },
    "CORE_LIQUIDITY_OLD_HIGHS_LOWS": {
        "concept": "liquidity",
        "summary": "Old/clean highs and lows are structural liquidity references; price commonly raids liquidity resting beyond them.",
        "lessons": [3, 7, 16, 18, 21, 26, 35, 36, 38, 42, 69, 70, 85],
        "evidence_class": "A",
        "machine_status": "PARTIAL",
        "note": "The reference idea is explicit; a universal pivot-left/right algorithm is not.",
    },
    "CORE_HIGH_LOW_RESISTANCE_LIQUIDITY": {
        "concept": "liquidity_resistance",
        "summary": "Distinguish low-resistance from high-resistance liquidity runs using directional/order-flow context rather than treating every old extreme equally.",
        "lessons": [7, 69, 70, 96],
        "evidence_class": "B",
        "machine_status": "REFERENCE",
    },
    "CORE_FALSE_BREAK_LIQUIDITY_REVERSAL": {
        "concept": "false_break",
        "summary": "A raid beyond an old extreme can be a reversal setup when higher-order context favors rejection rather than continuation.",
        "lessons": [16, 30, 35, 36, 43, 85],
        "evidence_class": "B",
        "machine_status": "PARTIAL",
    },
    "CORE_TIMEFRAME_HIERARCHY": {
        "concept": "top_down",
        "summary": "Higher timeframes establish directional/contextual reference; lower timeframes refine execution. Structural ideas recur across timeframes without implying identical bar-count parameters.",
        "lessons": [17, 20, 26, 52, 57, 59, 65, 73, 80, 112, 113, 114, 115],
        "evidence_class": "B",
        "machine_status": "READY",
    },
    "CORE_INSTITUTIONAL_ORDER_FLOW": {
        "concept": "institutional_order_flow",
        "summary": "Read price as delivery toward institutional liquidity/PD arrays; order flow is a directional context, not a single-candle trigger.",
        "lessons": [18, 19, 21, 26, 42, 52, 53, 57, 88, 99, 114],
        "evidence_class": "B",
        "machine_status": "REFERENCE",
    },
    "CORE_ORDER_BLOCK": {
        "concept": "order_block",
        "summary": "Bullish/bearish order blocks are contextual institutional price references; candle selection, validation and location matter.",
        "lessons": [10, 17, 18, 19, 20, 26, 27, 52, 53, 60, 61, 70, 79],
        "evidence_class": "C",
        "machine_status": "VISUAL",
        "note": "Do not reduce to 'last opposite candle before displacement' without a separately audited rule.",
    },
    "CORE_MITIGATION_BLOCK": {
        "concept": "mitigation_block",
        "summary": "Mitigation blocks arise around a market-structure shift and re-use prior price references for mitigation.",
        "lessons": [28, 68],
        "evidence_class": "C",
        "machine_status": "VISUAL",
    },
    "CORE_BREAKER_BLOCK": {
        "concept": "breaker",
        "summary": "Breaker blocks are failed/violated prior blocks used as opposite-side references after structural change.",
        "lessons": [29, 43, 52, 88, 115],
        "evidence_class": "C",
        "machine_status": "VISUAL",
    },
    "CORE_REJECTION_BLOCK": {
        "concept": "rejection_block",
        "summary": "Rejection blocks are framed around false breaks/wicks at important highs or lows and the underlying accumulation/distribution context.",
        "lessons": [30, 73],
        "evidence_class": "C",
        "machine_status": "VISUAL",
    },
    "CORE_RECLAIMED_ORDER_BLOCK": {
        "concept": "reclaimed_order_block",
        "summary": "A previously used order-block reference can be reclaimed/re-used after price changes delivery.",
        "lessons": [31],
        "evidence_class": "C",
        "machine_status": "VISUAL",
    },
    "CORE_PROPULSION_BLOCK": {
        "concept": "propulsion_block",
        "summary": "Propulsion-block logic uses a prior institutional candle/reference and requires follow-through through a relevant candle extreme.",
        "lessons": [32],
        "evidence_class": "C",
        "machine_status": "VISUAL",
    },
    "CORE_VACUUM_BLOCK": {
        "concept": "vacuum_block",
        "summary": "Vacuum block is taught as a breakaway-gap reference created by a price vacuum.",
        "lessons": [33],
        "evidence_class": "B",
        "machine_status": "PARTIAL",
    },
    "CORE_LIQUIDITY_VOID": {
        "concept": "liquidity_void",
        "summary": "A liquidity void is one-sided/inefficient price delivery that may later be revisited to rebalance delivery.",
        "lessons": [1, 3, 6, 34, 36],
        "evidence_class": "B",
        "machine_status": "PARTIAL",
    },
    "CORE_FAIR_VALUE_GAP": {
        "concept": "FVG",
        "summary": "A Fair Value Gap is a three-candle one-sided delivery pocket between candle one and candle three around the displacement candle.",
        "lessons": [36, 41, 95, 115],
        "evidence_class": "B",
        "machine_status": "READY",
        "note": "Touch/traversal can be measured; model-specific mitigation/invalidation is separate.",
    },
    "CORE_EQUAL_HIGHS_LOWS_LIQUIDITY": {
        "concept": "equal_highs_lows",
        "summary": "Equal/clean highs and lows are notable liquidity pools; price can trade through them to access stops.",
        "lessons": [27, 35, 38, 53],
        "evidence_class": "B",
        "machine_status": "PARTIAL",
    },
    "CORE_IPDA_20_40_60": {
        "concept": "IPDA_data_ranges",
        "summary": "Use rolling 20/40/60-trading-day context to inventory relevant highs/lows, gaps and PD arrays for higher-timeframe analysis.",
        "lessons": [41, 42, 56, 73, 88],
        "evidence_class": "B",
        "machine_status": "READY",
        "scope": "higher-timeframe research context",
    },
    "CORE_OPEN_FLOAT": {
        "concept": "open_float",
        "summary": "Open-float work combines longer-term extremes and shorter institutional swing/liquidity references to frame directional opportunity.",
        "lessons": [40, 42],
        "evidence_class": "C",
        "machine_status": "REFERENCE",
    },
    "CORE_INSTITUTIONAL_SWING_POINTS": {
        "concept": "institutional_swings",
        "summary": "Short/intermediate/long-term swing points are context-dependent institutional references, including failure swings near support/resistance arrays.",
        "lessons": [40, 42, 43],
        "evidence_class": "C",
        "machine_status": "VISUAL",
    },
    "CORE_PD_ARRAY_MATRIX": {
        "concept": "PD_arrays",
        "summary": "Inventory premium/discount arrays in an ordered matrix and expect price to move between relevant arrays under directional context.",
        "lessons": [52, 53, 59, 65, 68, 73, 79, 88, 101, 112],
        "evidence_class": "C",
        "machine_status": "PARTIAL",
        "note": "The exact active-array selection/order requires contextual and visual audit.",
    },
    "CORE_REBALANCE_FROM_PREMIUM_DISCOUNT": {
        "concept": "rebalance",
        "summary": "When price is materially premium/discount, an initial draw can be toward rebalance/efficient delivery before the next expansion.",
        "lessons": [6, 34, 36, 53],
        "evidence_class": "B",
        "machine_status": "PARTIAL",
    },
    "CORE_SEASONALITY_CONTEXT_ONLY": {
        "concept": "seasonality",
        "summary": "Seasonal tendencies are a roadmap/context input, not a guarantee or standalone signal.",
        "lessons": [48, 49, 50, 63, 64, 89, 91, 103, 108, 109, 111, 112],
        "evidence_class": "A",
        "machine_status": "REFERENCE",
    },
    "CORE_INTERMARKET_ANALYSIS": {
        "concept": "intermarket",
        "summary": "Use relationships among dollar, bonds/rates, commodities and equities as confirmation/qualification rather than isolated price action.",
        "lessons": [21, 22, 25, 44, 45, 46, 47, 56, 63, 89, 90, 92, 93, 107, 108, 109, 111, 112, 113],
        "evidence_class": "B",
        "machine_status": "REFERENCE",
    },
    "CORE_RELATIVE_STRENGTH_DIVERGENCE": {
        "concept": "relative_strength",
        "summary": "Compare related markets: non-confirmation of corresponding highs/lows can reveal accumulation/distribution or leadership.",
        "lessons": [21, 22, 45, 47, 58, 63, 90, 99, 100, 102, 104, 105, 108, 109, 111],
        "evidence_class": "B",
        "machine_status": "PARTIAL",
    },
    "CORE_RISK_TIMEFRAME_PROPORTIONAL": {
        "concept": "risk_management",
        "summary": "Risk, stop distance and exposure must be proportional to the timeframe/model; higher-timeframe trades require different stop/risk expectations than intraday setups.",
        "lessons": [9, 10, 12, 13, 51, 58, 62, 64, 79, 80],
        "evidence_class": "A",
        "machine_status": "REFERENCE",
    },
    "CORE_PARTIALS_LOGICAL_TARGETS": {
        "concept": "trade_management",
        "summary": "Take/scale profits at logical liquidity/PD-array objectives rather than assuming the maximum projected move will always complete.",
        "lessons": [5, 11, 13, 51, 56, 64, 79, 87, 115],
        "evidence_class": "B",
        "machine_status": "PARTIAL",
    },
    "CORE_WEEKLY_PROFILE_CONTEXT": {
        "concept": "weekly_profiles",
        "summary": "Weekly range profiles include recurring scenarios such as early-week high/low formation, midweek continuation/reversal and neutral profiles.",
        "lessons": [65, 66, 67, 71, 72, 73, 88],
        "evidence_class": "C",
        "machine_status": "REFERENCE",
        "note": "Treat as conditional profiles, not deterministic weekday rules.",
    },
    "CORE_TIME_OF_DAY": {
        "concept": "time_of_day",
        "summary": "Intraday setup quality depends on session/time-of-day and the higher-timeframe draw; London, New York AM, lunch/PM and London Close have different roles.",
        "lessons": [8, 65, 73, 74, 77, 78, 79, 80, 85, 86, 87, 88, 94, 95, 98, 99, 100, 101, 102, 114, 115],
        "evidence_class": "B",
        "machine_status": "PARTIAL",
    },
    "CORE_CBDR": {
        "concept": "CBDR",
        "summary": "Central Bank Dealers Range is framed from 14:00 to 20:00 New York and used with directional bias for intraday range projections.",
        "lessons": [75, 76, 77, 115],
        "evidence_class": "A",
        "machine_status": "READY",
        "scope": "FX/daytrading teaching; do not silently transplant pip thresholds to futures",
    },
    "CORE_CBDR_WIDTH_40_PIPS": {
        "concept": "CBDR",
        "summary": "The teaching treats an extended CBDR beyond roughly 40 pips as a different/less ideal condition.",
        "lessons": [75, 77],
        "evidence_class": "A",
        "machine_status": "READY",
        "scope": "FX only",
    },
    "CORE_LONDON_AVOIDANCE": {
        "concept": "London_session",
        "summary": "Avoid/discount London entries under adverse conditions such as prior large range, important upcoming news, or already-exhausted range characteristics.",
        "lessons": [78, 80],
        "evidence_class": "B",
        "machine_status": "PARTIAL",
    },
    "CORE_PREVIOUS_DAY_EXTREME_REVERSALS": {
        "concept": "previous_day_high_low",
        "summary": "Previous-day highs/lows are intraday liquidity references that can support reversal models when broader context is not strongly one-sided.",
        "lessons": [85],
        "evidence_class": "B",
        "machine_status": "PARTIAL",
    },
    "CORE_OPENING_PRICE_CONTEXT": {
        "concept": "opening_price",
        "summary": "Opening prices, including weekly and midnight opens, are contextual reference points for bias and intraday positioning.",
        "lessons": [81, 88, 114],
        "evidence_class": "B",
        "machine_status": "READY",
    },
    "CORE_ASIAN_RANGE_CONTEXT": {
        "concept": "Asian_range",
        "summary": "Asian-session highs/lows and range structure can frame intraday liquidity, range projection and scalp/reversal opportunities.",
        "lessons": [82, 83],
        "evidence_class": "B",
        "machine_status": "PARTIAL",
    },
    "CORE_ADR_TARGET_DISCIPLINE": {
        "concept": "ADR",
        "summary": "Average Daily Range is a projection/exit constraint; the teaching uses it to avoid demanding unrealistic intraday extension.",
        "lessons": [78, 87],
        "evidence_class": "B",
        "machine_status": "PARTIAL",
    },
    "CORE_COT_CONTEXT": {
        "concept": "COT",
        "summary": "Commercial hedging/net-positioning data is a higher-timeframe contextual filter for major directional/seasonal opportunities.",
        "lessons": [63, 64, 72, 89, 113],
        "evidence_class": "B",
        "machine_status": "REFERENCE",
    },
    "CORE_OPEN_INTEREST_CONTEXT": {
        "concept": "open_interest",
        "summary": "Open interest and its trend/seasonal relationship can qualify accumulation/distribution and higher-timeframe market conditions.",
        "lessons": [41, 42, 63, 93],
        "evidence_class": "B",
        "machine_status": "REFERENCE",
    },
    "CORE_INDEX_OPENING_RANGE": {
        "concept": "index_opening_range",
        "summary": "Index-futures teaching frames the equities open and the early New York session as a distinct opening-range context.",
        "lessons": [98, 99],
        "evidence_class": "A",
        "machine_status": "READY",
        "note": "TMBT currently implements 09:30-10:30 New York from the audited lesson.",
    },
    "CORE_INDEX_AM_RELATIVE_HILO": {
        "concept": "index_AM",
        "summary": "AM index analysis compares relative highs/lows among correlated equity indices under institutional-order-flow context.",
        "lessons": [99, 102],
        "evidence_class": "B",
        "machine_status": "PARTIAL",
    },
    "CORE_INDEX_PM_SESSION": {
        "concept": "index_PM",
        "summary": "The PM index session is framed around the post-lunch 13:00-16:00 New York window and may continue or reverse the AM move.",
        "lessons": [100, 101, 102],
        "evidence_class": "B",
        "machine_status": "READY",
    },
    "CORE_INDEX_SMT_BASKET": {
        "concept": "index_SMT",
        "summary": "Compare S&P, Nasdaq and Dow relative highs/lows; a failure of one index to confirm another can signal relative accumulation/distribution.",
        "lessons": [99, 100, 102],
        "evidence_class": "B",
        "machine_status": "PARTIAL",
    },
    "CORE_CONSOLIDATION_BEHAVIOR": {
        "concept": "consolidation",
        "summary": "When price is in consolidation, do not apply trending expectations mechanically; liquidity raids/fades and rebalancing become more relevant.",
        "lessons": [1, 6, 84, 96, 101, 112],
        "evidence_class": "B",
        "machine_status": "PARTIAL",
    },
    "CORE_TOP_DOWN_LONG_TERM": {
        "concept": "top_down_long",
        "summary": "Long-term analysis blends seasonality, rates/intermarket context, quarterly structure, market state and the HTF PD matrix.",
        "lessons": [112],
        "evidence_class": "B",
        "machine_status": "REFERENCE",
    },
    "CORE_TOP_DOWN_INTERMEDIATE": {
        "concept": "top_down_intermediate",
        "summary": "Intermediate analysis moves weekly-to-daily, establishing weekly bias, sentiment and institutional focus from higher-timeframe references.",
        "lessons": [113],
        "evidence_class": "B",
        "machine_status": "REFERENCE",
    },
    "CORE_TOP_DOWN_SHORT": {
        "concept": "top_down_short",
        "summary": "Short-term analysis uses established bias/order flow together with weekly and midnight opening-price references.",
        "lessons": [114],
        "evidence_class": "B",
        "machine_status": "PARTIAL",
    },
    "CORE_TOP_DOWN_INTRADAY": {
        "concept": "top_down_intraday",
        "summary": "Intraday analysis refines HTF context with CBDR/range projections, model-specific entry patterns, profit discipline, breaker/FVG/OTE references.",
        "lessons": [115],
        "evidence_class": "B",
        "machine_status": "PARTIAL",
    },
}

CONCEPT_INDEX: dict[str, list[str]] = {}
for rule_id, rule in RULE_CATALOG.items():
    CONCEPT_INDEX.setdefault(str(rule["concept"]), []).append(rule_id)


def lecture(global_lesson: int) -> dict[str, Any]:
    n = int(global_lesson)
    if not 1 <= n <= len(LECTURES):
        raise KeyError(n)
    row = dict(LECTURES[n - 1])
    row["focus"] = list(LESSON_FOCUS.get(n) or ())
    row["rules"] = [
        rid for rid, rule in RULE_CATALOG.items() if n in (rule.get("lessons") or [])
    ]
    return row


def search(query: str) -> dict[str, Any]:
    q = str(query or "").strip().lower()
    if not q:
        return {"lectures": [], "rules": []}
    lectures = []
    for row in LECTURES:
        n = int(row["global_lesson"])
        hay = " ".join(
            [
                str(row["title"]),
                *[str(x) for x in LESSON_FOCUS.get(n) or ()],
            ]
        ).lower()
        if q in hay:
            lectures.append(lecture(n))
    rules = []
    for rid, rule in RULE_CATALOG.items():
        hay = " ".join(
            [
                rid,
                str(rule.get("concept") or ""),
                str(rule.get("summary") or ""),
                str(rule.get("note") or ""),
            ]
        ).lower()
        if q in hay:
            rules.append({"rule_id": rid, **rule})
    return {"lectures": lectures, "rules": rules}


def coverage_report() -> dict[str, Any]:
    by_month = {}
    for month, (a, b) in MONTH_RANGES.items():
        by_month[str(month)] = {
            "first_lesson": a,
            "last_lesson": b,
            "lessons": b - a + 1,
            "indexed": sum(1 for x in LECTURES if x["month"] == month),
        }
    machine_counts = {}
    evidence_counts = {}
    for rule in RULE_CATALOG.values():
        machine_counts[rule["machine_status"]] = machine_counts.get(rule["machine_status"], 0) + 1
        evidence_counts[rule["evidence_class"]] = evidence_counts.get(rule["evidence_class"], 0) + 1
    return {
        "knowledge_version": KNOWLEDGE_VERSION,
        "lecture_count": len(LECTURES),
        "expected_lecture_count": 115,
        "months": 12,
        "all_lectures_indexed": len(LECTURES) == 115,
        "transcript_sources_available": sum(1 for x in LECTURES if x["transcript_available"]),
        "outline_sources_available": sum(1 for x in LECTURES if x["outline_available"]),
        "focus_indexed": sum(1 for x in LECTURES if x["global_lesson"] in LESSON_FOCUS),
        "rule_catalog_count": len(RULE_CATALOG),
        "machine_status_counts": machine_counts,
        "evidence_counts": evidence_counts,
        "by_month": by_month,
        "completion": {
            "corpus_index": "COMPLETE",
            "outline_focus_index": "COMPLETE" if len(LESSON_FOCUS) == 115 else "PARTIAL",
            "knowledge_rule_catalog": "ACTIVE",
            "transcript_rule_promotion": "IN_PROGRESS",
            "visual_geometry_audit": "IN_PROGRESS",
            "profitability_validation": "SEPARATE_TMBT_RESEARCH",
        },
        "important_limit": (
            "115/115 indexed does not mean every chart-dependent geometry is executable. "
            "C/VISUAL rules remain locked until source-faithful visual confirmation."
        ),
    }
