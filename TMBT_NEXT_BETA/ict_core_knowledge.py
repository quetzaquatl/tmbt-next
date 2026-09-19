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

import re
from typing import Any

KNOWLEDGE_VERSION = "ict-core-knowledge-v2"
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


# Lesson-level knowledge notes. These are compact paraphrases of the teaching,
# designed for retrieval and implementation review rather than transcript
# reproduction. "mechanization" describes how safely the lesson can become
# deterministic software without importing discretion that the source does not
# define.
LESSON_KNOWLEDGE: dict[int, dict[str, Any]] = {
    1: {"summary": "Introduces the four price-delivery states—expansion, retracement, reversal and consolidation—and frames setups as context plus an objective rather than isolated patterns.", "mechanization": "PARTIAL", "visual_dependency": "MEDIUM"},
    2: {"summary": "Explains how repeated delivery/conditioning can make traders expect continuation just before a different range objective is delivered; emphasizes reading the daily-range narrative.", "mechanization": "REFERENCE", "visual_dependency": "MEDIUM"},
    3: {"summary": "Directs study toward clean highs/lows, inefficient delivery and disciplined chart journaling instead of collecting more indicators.", "mechanization": "REFERENCE", "visual_dependency": "LOW"},
    4: {"summary": "Defines equilibrium and discount inside a relevant impulse swing and introduces the OTE retracement area for bullish framing.", "mechanization": "READY", "visual_dependency": "MEDIUM"},
    5: {"summary": "Mirrors the valuation framework for premium, links OTE to bearish framing, and stresses logical objectives rather than arbitrary exits.", "mechanization": "READY", "visual_dependency": "MEDIUM"},
    6: {"summary": "Frames fair valuation as balanced versus inefficient delivery and explains why price can revisit one-sided ranges before the next expansion.", "mechanization": "PARTIAL", "visual_dependency": "MEDIUM"},
    7: {"summary": "Treats old highs/lows as liquidity and distinguishes easier versus harder liquidity runs using directional context and intervening structure.", "mechanization": "PARTIAL", "visual_dependency": "MEDIUM"},
    8: {"summary": "Explains impulse swings and market protraction: expected movement is time-sensitive, so a valid price idea can lose quality when delivery takes too long.", "mechanization": "PARTIAL", "visual_dependency": "LOW"},
    9: {"summary": "Focuses on survival and sample-building for small accounts: selectivity, controlled exposure and statistical learning matter more than aggressive compounding.", "mechanization": "REFERENCE", "visual_dependency": "LOW"},
    10: {"summary": "Frames lower-risk setups by refining entry around institutional price references while keeping invalidation tied to the underlying idea.", "mechanization": "PARTIAL", "visual_dependency": "HIGH"},
    11: {"summary": "Uses liquidity pools and institutional sponsorship to discuss selective participation and taking partial profits rather than relying on a fixed monthly-return promise.", "mechanization": "REFERENCE", "visual_dependency": "MEDIUM"},
    12: {"summary": "Treats losses as part of a distribution of outcomes and stresses reward-to-risk, sample size and emotional neutrality.", "mechanization": "REFERENCE", "visual_dependency": "LOW"},
    13: {"summary": "Covers mitigating losing trades through risk reduction, valid re-entry logic and disciplined stop management rather than averaging blindly.", "mechanization": "PARTIAL", "visual_dependency": "MEDIUM"},
    14: {"summary": "Builds a high-reward setup-selection process from top-down context, sentiment, liquidity and a repeatable decision flow.", "mechanization": "PARTIAL", "visual_dependency": "MEDIUM"},
    15: {"summary": "Describes false-flag conditions in which apparent direction can be used to draw traders toward the wrong objective before institutional delivery resumes.", "mechanization": "REFERENCE", "visual_dependency": "HIGH"},
    16: {"summary": "Explains false breakouts and stop runs: trading beyond an obvious boundary is not sufficient for continuation if liquidity is being absorbed and price rejects.", "mechanization": "PARTIAL", "visual_dependency": "MEDIUM"},
    17: {"summary": "Defines a top-down timeframe workflow in which monthly/weekly/daily context identifies the setup and lower timeframes refine it; the model is modular rather than one universal timeframe.", "mechanization": "READY", "visual_dependency": "MEDIUM"},
    18: {"summary": "Presents institutional order flow as directional price delivery toward liquidity and institutional references, not as a single candle signal.", "mechanization": "REFERENCE", "visual_dependency": "MEDIUM"},
    19: {"summary": "Connects institutional sponsorship, market structure and accumulation/manipulation/distribution concepts to the use of order-block references.", "mechanization": "PARTIAL", "visual_dependency": "HIGH"},
    20: {"summary": "Develops anticipation by reading monthly/weekly/daily context and recent opposing candles so the next likely setup is planned before entry time.", "mechanization": "REFERENCE", "visual_dependency": "MEDIUM"},
    21: {"summary": "Extends market structure beyond one chart by using institutional swing behavior, liquidity and non-confirmation across related markets.", "mechanization": "PARTIAL", "visual_dependency": "HIGH"},
    22: {"summary": "Builds a macro-to-micro workflow using rates/bonds, the dollar and intermarket divergence before refining a technical setup.", "mechanization": "REFERENCE", "visual_dependency": "MEDIUM"},
    23: {"summary": "Warns that conventional trendlines can create false certainty; structural liquidity and institutional references take precedence over diagonal-line breaks.", "mechanization": "REFERENCE", "visual_dependency": "HIGH"},
    24: {"summary": "Uses head-and-shoulders expectations as another retail trap example and redirects attention to institutional order flow and liquidity objectives.", "mechanization": "REFERENCE", "visual_dependency": "HIGH"},
    25: {"summary": "Uses interest-rate relationships/triads to qualify currency direction and stresses cross-market confirmation before acting on a technical premise.", "mechanization": "REFERENCE", "visual_dependency": "MEDIUM"},
    26: {"summary": "Reinforces liquidity-seeking price delivery across timeframes and the role of institutional price references inside that narrative.", "mechanization": "PARTIAL", "visual_dependency": "MEDIUM"},
    27: {"summary": "Defines bullish and bearish order-block concepts, refinement/midpoint ideas and location context; exact candle selection is chart-dependent.", "mechanization": "VISUAL", "visual_dependency": "HIGH"},
    28: {"summary": "Introduces mitigation blocks around structural shifts and the return to prior institutional references for mitigation.", "mechanization": "VISUAL", "visual_dependency": "HIGH"},
    29: {"summary": "Defines breaker blocks as failed/violated prior institutional references that can become opposite-side support/resistance after structural change.", "mechanization": "VISUAL", "visual_dependency": "HIGH"},
    30: {"summary": "Defines rejection-block logic around false breaks/wicks at important extremes and connects it to accumulation/distribution and entry technique.", "mechanization": "VISUAL", "visual_dependency": "HIGH"},
    31: {"summary": "Explains reclaimed order blocks: a prior reference can be re-used after price changes delivery and reclaims the area.", "mechanization": "VISUAL", "visual_dependency": "HIGH"},
    32: {"summary": "Introduces propulsion blocks and the requirement for follow-through relative to a prior institutional candle/reference.", "mechanization": "VISUAL", "visual_dependency": "HIGH"},
    33: {"summary": "Describes vacuum blocks/breakaway gaps as time-sensitive references created when price rapidly leaves an area with little two-sided trade.", "mechanization": "PARTIAL", "visual_dependency": "HIGH"},
    34: {"summary": "Defines liquidity voids as one-sided inefficient delivery that can later be traversed as price seeks more balanced delivery.", "mechanization": "PARTIAL", "visual_dependency": "MEDIUM"},
    35: {"summary": "Organizes liquidity into pools around obvious highs/lows and explains why stop raids must be interpreted with directional bias rather than traded automatically.", "mechanization": "PARTIAL", "visual_dependency": "MEDIUM"},
    36: {"summary": "Defines Fair Value Gaps as three-candle inefficient delivery and relates them to liquidity voids and runs on old highs/lows; timeframe changes the visible granularity, not the underlying imbalance idea.", "mechanization": "READY", "visual_dependency": "MEDIUM"},
    37: {"summary": "Shows why apparent chart divergence can be misleading without trend/context confirmation and institutional reference points.", "mechanization": "REFERENCE", "visual_dependency": "HIGH"},
    38: {"summary": "Reframes double tops/bottoms and clean equal extremes as liquidity rather than guaranteed support/resistance.", "mechanization": "PARTIAL", "visual_dependency": "MEDIUM"},
    39: {"summary": "Introduces quarterly shifts and IPDA data-range thinking for intermediate-term changes in institutional price delivery.", "mechanization": "PARTIAL", "visual_dependency": "MEDIUM"},
    40: {"summary": "Defines open-float analysis using longer-term extremes, structural breaks and shorter institutional references to frame directional opportunity.", "mechanization": "REFERENCE", "visual_dependency": "HIGH"},
    41: {"summary": "Applies IPDA inventory over rolling 20/40/60-trading-day windows to highs/lows, gaps, open interest and other institutional references.", "mechanization": "READY", "visual_dependency": "MEDIUM"},
    42: {"summary": "Uses 20/40/60-day context to define open-float liquidity pools and relate them to institutional order flow.", "mechanization": "PARTIAL", "visual_dependency": "HIGH"},
    43: {"summary": "Defines institutional swing-point/failure-swing concepts and links them to breaker-style structural transitions and entry refinement.", "mechanization": "VISUAL", "visual_dependency": "HIGH"},
    44: {"summary": "Uses 10-year Treasury notes together with the dollar and seasonal context as a higher-timeframe macro filter.", "mechanization": "REFERENCE", "visual_dependency": "LOW"},
    45: {"summary": "Uses 10-year yields and correlation symmetry/non-confirmation to qualify whether a currency trend premise is supported.", "mechanization": "REFERENCE", "visual_dependency": "MEDIUM"},
    46: {"summary": "Uses interest-rate differentials to compare currencies and select the side/market that best fits the higher-timeframe premise.", "mechanization": "REFERENCE", "visual_dependency": "LOW"},
    47: {"summary": "Builds intermarket analysis across dollar, bonds, commodities and equities, focusing on lead/lag and confirmation rather than isolated signals.", "mechanization": "REFERENCE", "visual_dependency": "MEDIUM"},
    48: {"summary": "Uses bullish seasonal tendencies as a higher-timeframe roadmap only when they agree with price and cross-asset context.", "mechanization": "REFERENCE", "visual_dependency": "LOW"},
    49: {"summary": "Uses bearish seasonal tendencies as conditional context and explicitly avoids treating seasonality as a guaranteed outcome.", "mechanization": "REFERENCE", "visual_dependency": "LOW"},
    50: {"summary": "Shows how ideal seasonal windows can help build a higher-timeframe roadmap for currency pairs without becoming standalone entries.", "mechanization": "REFERENCE", "visual_dependency": "LOW"},
    51: {"summary": "Covers money management, exposure, partials and the principle that stop/risk expectations must scale with the timeframe and model.", "mechanization": "REFERENCE", "visual_dependency": "LOW"},
    52: {"summary": "Defines a higher-timeframe PD-array matrix and the ordering/location of institutional price references in premium versus discount.", "mechanization": "PARTIAL", "visual_dependency": "HIGH"},
    53: {"summary": "Explains setup progression as price moves between PD arrays and can first rebalance inefficient delivery before the next directional leg.", "mechanization": "PARTIAL", "visual_dependency": "HIGH"},
    54: {"summary": "Explains stop-entry techniques for long-term trades, using confirmation through an opening/price threshold rather than pre-emptive limit filling.", "mechanization": "PARTIAL", "visual_dependency": "MEDIUM"},
    55: {"summary": "Explains long-term limit entries at institutional PD-array references with premium/discount context and the trade-off between price improvement and fill probability.", "mechanization": "PARTIAL", "visual_dependency": "MEDIUM"},
    56: {"summary": "Covers position-trade management using intermarket alignment, major data-range extremes, realistic fills and staged management.", "mechanization": "REFERENCE", "visual_dependency": "MEDIUM"},
    57: {"summary": "Defines ideal swing-trading conditions from monthly/weekly directional bias and clear institutional objectives.", "mechanization": "PARTIAL", "visual_dependency": "MEDIUM"},
    58: {"summary": "Combines relative strength, clear liquidity levels and disciplined money management to select swing opportunities.", "mechanization": "REFERENCE", "visual_dependency": "MEDIUM"},
    59: {"summary": "Presents a classic monthly/weekly swing workflow with retracement timing, PD-array objectives and an emphasis on asymmetric reward relative to risk.", "mechanization": "PARTIAL", "visual_dependency": "HIGH"},
    60: {"summary": "Builds bullish swing setups from aligned monthly/weekly context and discount-side institutional references.", "mechanization": "PARTIAL", "visual_dependency": "HIGH"},
    61: {"summary": "Builds bearish swing setups from aligned higher-timeframe bearish context and premium-side institutional references.", "mechanization": "PARTIAL", "visual_dependency": "HIGH"},
    62: {"summary": "Shows how to reduce swing-trade risk while preserving asymmetric potential reward and uses roughly 3-to-1 reward/risk as a planning reference.", "mechanization": "PARTIAL", "visual_dependency": "MEDIUM"},
    63: {"summary": "Selects markets likely to expand using COT/open-interest, volatility, news and higher-timeframe context instead of price pattern alone.", "mechanization": "REFERENCE", "visual_dependency": "LOW"},
    64: {"summary": "Combines seasonality, macro/top-down context, entry selection and progressive stop management into a large-swing template.", "mechanization": "REFERENCE", "visual_dependency": "HIGH"},
    65: {"summary": "Frames short-term trading from monthly/weekly ranges, kill-zone timing, PD arrays and realistic reward/risk objectives.", "mechanization": "PARTIAL", "visual_dependency": "MEDIUM"},
    66: {"summary": "Introduces conditional weekly range profiles—such as early-week low/high formation, midweek continuation/reversal and neutral profiles—rather than deterministic weekday rules.", "mechanization": "REFERENCE", "visual_dependency": "MEDIUM"},
    67: {"summary": "Shows recurring market-maker manipulation templates across the week, emphasizing staged delivery and reflection rather than a fixed weekday formula.", "mechanization": "REFERENCE", "visual_dependency": "HIGH"},
    68: {"summary": "Blends the 20-day IPDA context with PD arrays and time-of-day to refine short-term institutional references.", "mechanization": "PARTIAL", "visual_dependency": "HIGH"},
    69: {"summary": "Defines low-resistance liquidity runs through premium/discount context, nearby PD arrays and the absence of opposing structural obstacles.", "mechanization": "PARTIAL", "visual_dependency": "HIGH"},
    70: {"summary": "Extends low-resistance liquidity-run analysis with 4H/trading-range structure and institutional reference points.", "mechanization": "PARTIAL", "visual_dependency": "HIGH"},
    71: {"summary": "Explains intraweek reversals and model overlap: multiple valid narratives can coexist, so the higher-timeframe context determines which model is active.", "mechanization": "REFERENCE", "visual_dependency": "HIGH"},
    72: {"summary": "Presents the One Shot One Kill workflow as a selective weekly opportunity built from macro/COT context and a higher-timeframe institutional reference.", "mechanization": "REFERENCE", "visual_dependency": "HIGH"},
    73: {"summary": "Defines daytrading essentials: directional bias, higher-timeframe PD inventory, weekly-range context and session timing precede the lower-timeframe setup.", "mechanization": "PARTIAL", "visual_dependency": "MEDIUM"},
    74: {"summary": "Defines the daily range using New York/CME session conventions and key session boundaries, separating the trading day from simple calendar-midnight candles.", "mechanization": "PARTIAL", "visual_dependency": "LOW"},
    75: {"summary": "Defines the Central Bank Dealers Range from 14:00 to 20:00 New York and uses its body range with directional context for intraday projection.", "mechanization": "READY", "visual_dependency": "MEDIUM"},
    76: {"summary": "Projects daily highs/lows using CBDR structure, London timing and standard-deviation-style range projections rather than arbitrary fixed targets.", "mechanization": "PARTIAL", "visual_dependency": "HIGH"},
    77: {"summary": "Classifies intraday profiles using CBDR width, midnight/opening references and London delivery to anticipate different day structures.", "mechanization": "PARTIAL", "visual_dependency": "HIGH"},
    78: {"summary": "Defines conditions for avoiding London trades, including already-expanded range, important news and adverse ADR/range characteristics.", "mechanization": "PARTIAL", "visual_dependency": "LOW"},
    79: {"summary": "Builds higher-probability day trades from London/session extremes, day-of-week context, logical stops and planned profit-taking.", "mechanization": "PARTIAL", "visual_dependency": "HIGH"},
    80: {"summary": "Integrates intraday entries with an existing higher-timeframe trade idea so timing refines—not replaces—the HTF premise and protective stop logic.", "mechanization": "PARTIAL", "visual_dependency": "MEDIUM"},
    81: {"summary": "Uses sentiment and opening-price context as qualifiers for daytrade conditions and premium/discount reference selection.", "mechanization": "REFERENCE", "visual_dependency": "MEDIUM"},
    82: {"summary": "Uses zero-GMT pivots, Asian-range information and daily-range projection to frame intraday directional expectations.", "mechanization": "PARTIAL", "visual_dependency": "HIGH"},
    83: {"summary": "Presents a short FX scalp framework around the Asian session and short-term extremes; the pip objective is market/model specific and not portable to futures.", "mechanization": "PARTIAL", "visual_dependency": "MEDIUM"},
    84: {"summary": "Explains how to trade consolidation differently from trend: use HTF order flow/equilibrium and be cautious with breakout expectations while price remains balanced.", "mechanization": "PARTIAL", "visual_dependency": "MEDIUM"},
    85: {"summary": "Builds intraday reversal logic around previous-day extremes, New York timing and broader directional context rather than fading every prior high/low.", "mechanization": "PARTIAL", "visual_dependency": "HIGH"},
    86: {"summary": "Presents a recurring bullish daytrade template using repricing, London timing/Judas behavior and a pre-existing directional draw.", "mechanization": "PARTIAL", "visual_dependency": "HIGH"},
    87: {"summary": "Presents the bearish counterpart using London Judas/offset distribution, time-and-price alignment and ADR-aware exits.", "mechanization": "PARTIAL", "visual_dependency": "HIGH"},
    88: {"summary": "Summarizes the daytrade routine: maintain a rolling higher-timeframe inventory, establish order flow, then refine with breaker/OTE and session timing.", "mechanization": "PARTIAL", "visual_dependency": "HIGH"},
    89: {"summary": "Uses Commitment of Traders/commercial hedging as a higher-timeframe contextual input, not as a direct timing trigger.", "mechanization": "REFERENCE", "visual_dependency": "LOW"},
    90: {"summary": "Uses relative strength and cross-market failure swings to infer accumulation/distribution and leadership among related markets.", "mechanization": "PARTIAL", "visual_dependency": "HIGH"},
    91: {"summary": "Applies commodity seasonal tendencies as conditional context and reiterates that seasonal averages are not deterministic forecasts.", "mechanization": "REFERENCE", "visual_dependency": "LOW"},
    92: {"summary": "Explains premium versus carrying-charge conditions in commodities and how spread relationships can indicate a commercially bullish or bearish backdrop.", "mechanization": "REFERENCE", "visual_dependency": "MEDIUM"},
    93: {"summary": "Combines open-interest behavior, trend and seasonal context to infer smart-money participation and higher-timeframe opportunity.", "mechanization": "REFERENCE", "visual_dependency": "MEDIUM"},
    94: {"summary": "Introduces bond-market opening-range analysis and uses volume/relative behavior to distinguish trending from consolidating conditions.", "mechanization": "PARTIAL", "visual_dependency": "HIGH"},
    95: {"summary": "Splits the bond session into AM/PM structures and demonstrates reversal/profile logic with institutional references including FVGs.", "mechanization": "PARTIAL", "visual_dependency": "HIGH"},
    96: {"summary": "Defines bond consolidation-day conditions from calendar/news context and overnight/reference highs/lows, stressing rule-based recognition.", "mechanization": "PARTIAL", "visual_dependency": "MEDIUM"},
    97: {"summary": "Defines bond trend-day conditions from volatility/catalyst context and premium/discount delivery.", "mechanization": "PARTIAL", "visual_dependency": "MEDIUM"},
    98: {"summary": "Introduces index-futures opening-range logic around the 09:30 New York equities open and the early RTH window.", "mechanization": "READY", "visual_dependency": "MEDIUM"},
    99: {"summary": "Builds the index AM model from relative highs/lows, institutional order flow and divergence among correlated equity indices.", "mechanization": "PARTIAL", "visual_dependency": "HIGH"},
    100: {"summary": "Frames the index PM session from roughly 13:00 to 16:00 New York, considering whether post-lunch delivery confirms or reverses the AM narrative.", "mechanization": "READY", "visual_dependency": "MEDIUM"},
    101: {"summary": "Projects index objectives from the AM/PM relationship, premium/discount and whether price is trending or consolidating.", "mechanization": "PARTIAL", "visual_dependency": "HIGH"},
    102: {"summary": "Compares S&P, Nasdaq and Dow relative highs/lows inside PM time-of-day context to identify index trade setups and divergence.", "mechanization": "PARTIAL", "visual_dependency": "HIGH"},
    103: {"summary": "Uses stock seasonality and monthly swings to narrow the directional universe before individual-stock analysis.", "mechanization": "REFERENCE", "visual_dependency": "LOW"},
    104: {"summary": "Builds stock buy watchlists by combining broad-index direction with relative strength and weekly directional context.", "mechanization": "PARTIAL", "visual_dependency": "MEDIUM"},
    105: {"summary": "Builds stock sell watchlists by combining a bearish market backdrop with relative weakness versus the index.", "mechanization": "PARTIAL", "visual_dependency": "MEDIUM"},
    106: {"summary": "Discusses using options for stock ideas only after directional, fundamental/institutional and seasonal conditions are established.", "mechanization": "REFERENCE", "visual_dependency": "LOW"},
    107: {"summary": "Reinforces multi-asset analysis: bonds, dollar, commodities and equities should be viewed as an interacting macro system rather than independent charts.", "mechanization": "REFERENCE", "visual_dependency": "MEDIUM"},
    108: {"summary": "Frames commodity mega-trades through sector/relative-strength and macro context while maintaining diversification and selectivity.", "mechanization": "REFERENCE", "visual_dependency": "MEDIUM"},
    109: {"summary": "Frames large FX opportunities through seasonality, dollar direction and relative strength rather than a single pair pattern.", "mechanization": "REFERENCE", "visual_dependency": "MEDIUM"},
    110: {"summary": "Frames large stock opportunities by first establishing market direction, then selecting fundamentally/institutionally stronger or weaker names.", "mechanization": "REFERENCE", "visual_dependency": "MEDIUM"},
    111: {"summary": "Frames large bond opportunities using seasonality, the Treasury curve and divergence/relative behavior across bond markets.", "mechanization": "REFERENCE", "visual_dependency": "MEDIUM"},
    112: {"summary": "Long-term top-down analysis integrates seasonality, rates/intermarket context, quarterly shifts, market state and the higher-timeframe PD matrix.", "mechanization": "REFERENCE", "visual_dependency": "HIGH"},
    113: {"summary": "Intermediate top-down analysis translates long-term context into weekly bias, sentiment and institutional focus using weekly/daily references.", "mechanization": "REFERENCE", "visual_dependency": "HIGH"},
    114: {"summary": "Short-term top-down analysis refines established bias/order flow using weekly open, midnight open and shorter-term institutional references.", "mechanization": "PARTIAL", "visual_dependency": "HIGH"},
    115: {"summary": "Intraday top-down analysis combines HTF bias with CBDR/range projections, session timing and lower-timeframe OTE/breaker/FVG references while keeping execution model-specific.", "mechanization": "PARTIAL", "visual_dependency": "HIGH"},
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
        "summary": "Optimal Trade Entry is explicitly taught inside a relevant impulse swing as the deep retracement area using the 62%, 70.5% and 79% Fibonacci references; 70.5% is called the OTE sweet spot and 50% is equilibrium.",
        "lessons": [4, 5, 88, 115],
        "evidence_class": "A",
        "machine_status": "READY",
        "source_detail": "M1 L4 00:24:09-00:24:22 and 00:29:19-00:29:45 explicitly name 62%, 70.5% and 79%; M1 L5 00:11:25-00:11:47 calls 70.5% the OTE sweet spot.",
        "note": "The percentages are source-certified. Selecting the active impulse/dealing range remains contextual and is not implied by the percentages themselves.",
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
        "summary": "Lesson 27 explicitly defines the bullish order-block candidate as the lowest down-close bar with the greatest open-to-close body range near support; it is validated when a later bar trades through that candidate's high. The bearish case is taught as the reverse.",
        "lessons": [10, 17, 18, 19, 20, 26, 27, 52, 53, 60, 61, 70, 79],
        "evidence_class": "A",
        "machine_status": "PARTIAL",
        "source_detail": "M4 L27 00:00:56-00:03:42; entry/risk/mean-threshold detail 00:01:27-00:02:19 and 00:10:08-00:10:50.",
        "note": "Candidate/validation text is explicit, but 'near support/resistance', the search window and HTF reference selection remain contextual. Do not replace this with generic 'last opposite candle before displacement'.",
    },
    "CORE_MITIGATION_BLOCK": {
        "concept": "mitigation_block",
        "summary": "Lesson 28 ties a mitigation block to a directional context plus a confirmed market-structure shift; in the bearish example the focus moves to the last down-close candle inside the short-term low that was later violated, and a retrace into that reference can be used for selling.",
        "lessons": [28, 68],
        "evidence_class": "A",
        "machine_status": "PARTIAL",
        "source_detail": "M4 L28 00:02:38-00:07:53; explicit last-down-candle reference 00:04:07-00:05:24.",
        "note": "The source requires prior directional context and a structure shift. Exact swing segmentation/reference-window quantification remains TMBT research unless separately specified.",
    },
    "CORE_BREAKER_BLOCK": {
        "concept": "breaker",
        "summary": "Lesson 29 explicitly frames a bullish breaker after sell-side liquidity is raided below an old low and the intervening short-term high is subsequently broken; that former high becomes a support reference on retrace. The bearish case is the reverse around an old high and intervening swing low.",
        "lessons": [29, 43, 52, 88, 115],
        "evidence_class": "A",
        "machine_status": "PARTIAL",
        "source_detail": "M4 L29 00:02:07-00:07:24; bearish definition 00:02:45-00:05:11; bullish definition 00:05:11-00:07:24.",
        "note": "The structural sequence is explicit. Exact old-high/old-low and short-term-swing quantification remains a separate detector choice.",
    },
    "CORE_REJECTION_BLOCK": {
        "concept": "rejection_block",
        "summary": "Lesson 30 explicitly frames a bearish rejection block from the highest wick high down to the highest open/close in the swing high after a false break; the bullish case uses the lowest wick low up to the lowest open/close in the swing low.",
        "lessons": [30, 73],
        "evidence_class": "A",
        "machine_status": "PARTIAL",
        "source_detail": "M4 L30 00:09:30-00:13:29; bearish geometry 00:09:30-00:11:39; bullish geometry 00:12:07-00:13:29.",
        "note": "Block geometry is textually explicit; selecting the qualifying major/intermediate swing and broader accumulation/distribution context remains contextual.",
    },
    "CORE_RECLAIMED_ORDER_BLOCK": {
        "concept": "reclaimed_order_block",
        "summary": "Lesson 31 explicitly describes reclaimed blocks as earlier order-block candles created on one side of a market-maker curve that are re-used on the opposite side after the major swing turns. Bullish reclaimed blocks re-use prior down-close/bullish-order-block candles for new longs; bearish reclaimed blocks re-use prior up-close/bearish-order-block candles for new shorts.",
        "lessons": [31],
        "evidence_class": "A",
        "machine_status": "PARTIAL",
        "source_detail": "M4 L31 00:03:24-00:05:23 bullish; 00:06:39-00:08:59 bearish.",
        "note": "The reuse relationship is text-certified, but detecting the market-maker curve/climax and the qualifying prior block remains contextual.",
    },
    "CORE_PROPULSION_BLOCK": {
        "concept": "propulsion_block",
        "summary": "Lesson 32 defines a bullish propulsion block as a new down-close candle that trades back into an already-established bullish order block and then assumes a higher support role; its mean-threshold/body sensitivity is explicitly discussed. The bearish case is the reverse.",
        "lessons": [32],
        "evidence_class": "A",
        "machine_status": "PARTIAL",
        "source_detail": "M4 L32 00:00:29-00:01:58; later examples/confirmation through approximately 00:06:53.",
        "note": "The propulsion relationship is explicit, but it depends on a correctly identified parent order block, so it should not auto-execute independently.",
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
        "summary": "Lesson 36 explicitly defines the three-candle one-sided delivery pocket by the untraded range between the low/high of the candle before the displacement candle and the high/low of the candle after it; bullish geometry is the mirrored case.",
        "lessons": [36, 41, 95, 115],
        "evidence_class": "A",
        "machine_status": "READY",
        "source_detail": "M4 L36 00:01:44-00:06:24, especially 00:03:29-00:04:54 and 00:05:48-00:06:24.",
        "note": "The gap geometry is source-certified. Touch/full traversal can be measured, but model-specific mitigation, inversion and expiry rules remain separate.",
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
        "summary": "Lesson 40 explicitly defines open float as current open interest above and below market price, including resting buy stops and sell stops for entries and position protection; it is then used to reason about buy-side and sell-side liquidity.",
        "lessons": [40, 42],
        "evidence_class": "A",
        "machine_status": "REFERENCE",
        "source_detail": "M5 L40 00:01:00-00:02:42 definition and liquidity framing.",
        "note": "This is source-certified knowledge/reference. TMBT cannot infer actual resting order quantities from OHLC alone.",
    },
    "CORE_INSTITUTIONAL_SWING_POINTS": {
        "concept": "institutional_swings",
        "summary": "Lesson 43 explicitly defines the ordinary three-bar swing high/low geometry and then narrows institutional turning points to two conceptual families: breaker/stop-run swing points and failure swings.",
        "lessons": [40, 42, 43],
        "evidence_class": "A",
        "machine_status": "PARTIAL",
        "source_detail": "M5 L43 00:00:24-00:02:13 three-bar swing and two-family framing; 00:18:59-00:20:42 failure-swing definition.",
        "note": "Base swing geometry is deterministic; deciding which swing is institutionally relevant still depends on the surrounding liquidity/PD-array context.",
    },
    "CORE_PD_ARRAY_MATRIX": {
        "concept": "PD_arrays",
        "summary": "Lesson 52 explicitly orders the higher-timeframe premium/discount array search from equilibrium outward. On the premium side the sequence discussed includes mitigation block, bearish breaker, liquidity void, FVG, bearish order block, rejection block and old high/low; the discount side is mirrored.",
        "lessons": [52, 53, 59, 65, 68, 73, 79, 88, 101, 112],
        "evidence_class": "A",
        "machine_status": "PARTIAL",
        "source_detail": "M5 L52 approximately 00:18:51-00:31:07, especially 00:24:05-00:29:05.",
        "note": "The hierarchy is text-certified. Detecting each component and deciding the active dealing range/context remain separate subproblems.",
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
        "summary": "Lesson 66 explicitly presents conditional weekly profiles such as classic Tuesday low/high, Wednesday high/low variants, consolidation-Thursday reversal, midweek expansion and neutral/low-probability conditions, always conditioned on prior higher-timeframe bias and PD-array location.",
        "lessons": [65, 66, 67, 71, 72, 73, 88],
        "evidence_class": "A",
        "machine_status": "REFERENCE",
        "source_detail": "M7 L66 00:00:25-00:09:00+; Tuesday-low example begins 00:00:57, Thursday-reversal examples approximately 00:04:33-00:06:05.",
        "note": "Source-certified as conditional profiles. Never encode them as guaranteed weekday outcomes.",
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


# Additional recurring logic families needed for complete lesson coverage. They are
# kept separate from the small executable primitive registry on purpose.
RULE_CATALOG.update({
    "CORE_MARKET_MAKER_CONDITIONING": {
        "concept": "market_maker_conditioning",
        "summary": "Repeated price behavior can condition traders to expect the wrong continuation; the lesson uses daily-range narrative and objective selection to counter that bias.",
        "lessons": [2],
        "evidence_class": "B",
        "machine_status": "REFERENCE",
    },
    "CORE_DIVERGENCE_PHANTOM": {
        "concept": "divergence_phantom",
        "summary": "Apparent divergence is not sufficient by itself; trend, institutional reference points and broader context determine whether the non-confirmation is meaningful.",
        "lessons": [37],
        "evidence_class": "B",
        "machine_status": "REFERENCE",
    },
    "CORE_MARKET_PROTRACTION": {
        "concept": "market_protraction",
        "summary": "Expected delivery is time-sensitive; when price fails to progress within the expected session/time context, the original premise loses quality.",
        "lessons": [8, 77, 115],
        "evidence_class": "B",
        "machine_status": "PARTIAL",
    },
    "CORE_LOW_RISK_SETUP_FRAMING": {
        "concept": "setup_framing",
        "summary": "A lower-risk setup combines directional/contextual premise, a precise institutional reference and a nearby invalidation rather than reducing risk by arbitrary stop compression.",
        "lessons": [10, 14, 53, 79],
        "evidence_class": "B",
        "machine_status": "REFERENCE",
    },
    "CORE_OUTCOME_DISTRIBUTION_DISCIPLINE": {
        "concept": "performance_psychology",
        "summary": "Judge a model over a sample of trades and accept normal losses; return targets are not guaranteed by a single setup.",
        "lessons": [9, 11, 12, 13],
        "evidence_class": "A",
        "machine_status": "REFERENCE",
    },
    "CORE_LOSS_MITIGATION_REENTRY": {
        "concept": "loss_mitigation",
        "summary": "Reduce or exit invalidated exposure and only re-enter when the underlying premise and a fresh valid setup still exist.",
        "lessons": [13, 51, 56],
        "evidence_class": "B",
        "machine_status": "REFERENCE",
    },
    "CORE_HIGH_REWARD_SELECTION": {
        "concept": "setup_selection",
        "summary": "Higher-reward opportunities are selected by aligning top-down directional context, clear liquidity objectives and an efficient entry location.",
        "lessons": [14, 57, 58, 59, 62, 64],
        "evidence_class": "B",
        "machine_status": "REFERENCE",
    },
    "CORE_MARKET_MAKER_TRAP_CONTEXT": {
        "concept": "market_maker_traps",
        "summary": "Conventional chart expectations such as false flags, breakouts, trendline breaks and head-and-shoulders can be liquidity narratives; institutional context decides whether they matter.",
        "lessons": [15, 16, 23, 24],
        "evidence_class": "B",
        "machine_status": "REFERENCE",
    },
    "CORE_INSTITUTIONAL_SPONSORSHIP": {
        "concept": "institutional_sponsorship",
        "summary": "A setup is stronger when directional price delivery shows institutional sponsorship toward a clear liquidity/PD-array objective.",
        "lessons": [11, 19, 58, 106],
        "evidence_class": "B",
        "machine_status": "REFERENCE",
    },
    "CORE_POWER_OF_THREE": {
        "concept": "power_of_three",
        "summary": "Accumulation, manipulation and distribution are used as a delivery framework; the sequence is contextual and should not be reduced to one fixed candle count.",
        "lessons": [19, 67, 73, 88],
        "evidence_class": "B",
        "machine_status": "PARTIAL",
    },
    "CORE_MACRO_TO_MICRO": {
        "concept": "macro_to_micro",
        "summary": "Establish macro directional context from rates/bonds, dollar and related assets before moving down to technical execution.",
        "lessons": [22, 25, 44, 45, 46, 47, 107, 112],
        "evidence_class": "B",
        "machine_status": "REFERENCE",
    },
    "CORE_QUARTERLY_SHIFT": {
        "concept": "quarterly_shift",
        "summary": "Quarterly shifts describe changes in intermediate-term institutional delivery and are used with IPDA ranges to update the higher-timeframe narrative.",
        "lessons": [39, 112],
        "evidence_class": "B",
        "machine_status": "REFERENCE",
    },
    "CORE_TEN_YEAR_RATE_FILTER": {
        "concept": "rates_10y",
        "summary": "10-year notes/yields can qualify currency and macro directional premises through rate and correlation behavior.",
        "lessons": [44, 45],
        "evidence_class": "B",
        "machine_status": "REFERENCE",
    },
    "CORE_INTEREST_RATE_DIFFERENTIAL": {
        "concept": "rate_differential",
        "summary": "Compare interest-rate relationships/differentials to help select which currency/side has the stronger macro premise.",
        "lessons": [25, 46],
        "evidence_class": "B",
        "machine_status": "REFERENCE",
    },
    "CORE_STOP_ENTRY_TECHNIQUE": {
        "concept": "entry_stop_order",
        "summary": "A stop-entry can require price confirmation through a predefined level before participation, trading worse price for confirmation.",
        "lessons": [30, 54, 64],
        "evidence_class": "B",
        "machine_status": "PARTIAL",
    },
    "CORE_LIMIT_ENTRY_TECHNIQUE": {
        "concept": "entry_limit_order",
        "summary": "A limit entry seeks improved price at a predefined institutional reference but introduces non-fill and touch-versus-fill risk.",
        "lessons": [55, 56, 64],
        "evidence_class": "B",
        "machine_status": "PARTIAL",
    },
    "CORE_POSITION_TRADE_MANAGEMENT": {
        "concept": "position_management",
        "summary": "Manage longer-duration positions from structural objectives and evolving invalidation, including partials and progressive stop decisions rather than bar-by-bar noise.",
        "lessons": [51, 56, 64],
        "evidence_class": "B",
        "machine_status": "REFERENCE",
    },
    "CORE_SWING_TRADING_MODEL": {
        "concept": "swing_trading",
        "summary": "Swing trading begins with monthly/weekly direction and clear institutional objectives, then uses lower-timeframe retracement/entry references.",
        "lessons": [57, 58, 59, 60, 61, 62, 63, 64],
        "evidence_class": "B",
        "machine_status": "PARTIAL",
    },
    "CORE_SWING_3R_PLANNING": {
        "concept": "swing_reward_risk",
        "summary": "The swing-trading teaching uses approximately three units of potential reward for one unit of initial risk as a planning/filter reference when structure allows.",
        "lessons": [59, 62],
        "evidence_class": "A",
        "machine_status": "READY",
        "scope": "swing-model planning reference; not a universal exit rule",
    },
    "CORE_MONTHLY_WEEKLY_RANGE_SHORT_TERM": {
        "concept": "monthly_weekly_ranges",
        "summary": "Short-term trades are nested inside monthly/weekly range location so intraday entries serve the larger draw rather than contradict it.",
        "lessons": [65, 66, 67, 71, 72, 73],
        "evidence_class": "B",
        "machine_status": "PARTIAL",
    },
    "CORE_WEEKLY_MANIPULATION_TEMPLATES": {
        "concept": "weekly_manipulation",
        "summary": "Lesson 67 expands the weekly profiles into market-maker manipulation templates, including classic Tuesday-low/high scenarios, reflection patterns and consolidation-reversal structures, with time-and-price/PD-array context.",
        "lessons": [66, 67, 71],
        "evidence_class": "A",
        "machine_status": "REFERENCE",
        "source_detail": "M7 L67: Tuesday-low 00:02:06+, Tuesday-high 00:07:28+, reflection 00:13:48+, four-stage discussion 00:16:24+.",
        "note": "These are scenario templates, not deterministic weekday triggers and not a standalone automatic trade rule.",
    },
    "CORE_INTRAWEEK_REVERSAL": {
        "concept": "intraweek_reversal",
        "summary": "An intraweek reversal is evaluated from overlapping higher-timeframe models and weekly range position rather than from day-of-week alone.",
        "lessons": [66, 67, 71],
        "evidence_class": "B",
        "machine_status": "REFERENCE",
    },
    "CORE_ONE_SHOT_ONE_KILL": {
        "concept": "one_shot_one_kill",
        "summary": "Lesson 72 presents One Shot One Kill as a selective top-down procedure requiring macro conditions, 20/40/60-day IPDA context, PD arrays, position/swing/short-term concepts, weekly Power-of-Three, time-of-day, seasonality, COT/commercial hedging, volatility and intermarket confirmation.",
        "lessons": [72],
        "evidence_class": "A",
        "machine_status": "REFERENCE",
        "source_detail": "M7 L72 00:00:27-00:10:06 prerequisites/procedure; worked examples continue through the lesson.",
        "note": "The lesson explicitly depends on prior mentorship and free-tutorial material plus trader experience, so OSOK remains reference/context knowledge rather than a single deterministic Core function.",
    },
    "CORE_DAILY_RANGE_SESSION": {
        "concept": "daily_range",
        "summary": "Define the trading day using the relevant New York/CME session boundaries rather than assuming midnight-to-midnight calendar bars.",
        "lessons": [74, 88, 115],
        "evidence_class": "B",
        "machine_status": "PARTIAL",
    },
    "CORE_DAILY_RANGE_PROJECTION": {
        "concept": "daily_range_projection",
        "summary": "Project plausible daily extremes from session range statistics/CBDR and directional context; projections are objectives, not guaranteed destinations.",
        "lessons": [76, 77, 82, 115],
        "evidence_class": "B",
        "machine_status": "PARTIAL",
    },
    "CORE_INTRADAY_PROFILE": {
        "concept": "intraday_profile",
        "summary": "Lesson 77 explicitly defines conditional London intraday profiles from higher-timeframe bias, CBDR/Asian-range characteristics, midnight-to-2am protraction and 2am delayed-protraction alternatives. The profiles are similarity templates with stated deviations, not exact deterministic copies.",
        "lessons": [77, 84, 85, 95, 96, 97, 99, 100, 101],
        "evidence_class": "A",
        "machine_status": "REFERENCE",
        "source_detail": "M8 L77 00:00:33-00:20:11; normal sell profile criteria 00:01:27-00:07:25, delayed sell 00:08:09-00:10:59, mirrored buy profiles 00:11:21-00:20:11.",
        "note": "The numeric CBDR/Asian ranges are FX-specific. Do not transplant pip thresholds to futures.",
    },
    "CORE_DAYTRADE_HTF_ALIGNMENT": {
        "concept": "daytrade_alignment",
        "summary": "A daytrade should refine an existing higher-timeframe directional premise; lower-timeframe timing does not replace the HTF draw on liquidity.",
        "lessons": [73, 79, 80, 88, 114, 115],
        "evidence_class": "B",
        "machine_status": "PARTIAL",
    },
    "CORE_SENTIMENT_CONTEXT": {
        "concept": "sentiment",
        "summary": "Sentiment is a contextual qualifier used alongside opening price, higher-timeframe direction and institutional references, not as a standalone trigger.",
        "lessons": [14, 81, 113],
        "evidence_class": "B",
        "machine_status": "REFERENCE",
    },
    "CORE_ZERO_GMT_PIVOT_CONTEXT": {
        "concept": "zero_gmt",
        "summary": "Lesson 82 explicitly uses zero-GMT floor-trader pivots as liquidity/number-filling references: central pivot, R/S levels and their 50% midpoint levels are interpreted in the direction of institutional order flow and the PD-array bias rather than as standalone retail buy/sell signals.",
        "lessons": [82],
        "evidence_class": "A",
        "machine_status": "REFERENCE",
        "source_detail": "M9 L82 00:01:46-00:05:38 defines zero-GMT central/R/S pivots and midpoint levels; later examples combine them with Asian range and PD-array bias.",
        "note": "This is a contextual reference framework. Exact platform pivot calculation must match the source's zero-GMT convention before software use.",
    },
    "CORE_ASIAN_SCALP_MODEL": {
        "concept": "asian_scalp",
        "summary": "Lesson 83 explicitly gives an FX Asian-session scalp: through midnight New York, use a 5-minute chart, probe a prior New-York short-term low for a long or short-term high for a short, fade the liquidity run, and use a fixed 20-pip target/stop in the lesson's model.",
        "lessons": [83],
        "evidence_class": "A",
        "machine_status": "REFERENCE",
        "source_detail": "M9 L83 00:04:13-00:06:25 core long/short setup; 00:08:23-00:09:23 short example; 00:10:56-00:11:27 long example.",
        "note": "This is explicitly an FX/pip model and must not be ported to NQ/ES/GC by replacing pips with arbitrary ticks.",
    },
    "CORE_BREAD_AND_BUTTER_DAYTRADE": {
        "concept": "bread_and_butter",
        "summary": "Lessons 86-87 explicitly define mirrored bread-and-butter buy/sell families: higher-timeframe institutional order flow first, then offset accumulation/distribution or fair-value retracement at discount/premium arrays, with session/kill-zone timing and Judas-style repricing used to refine intraday entries.",
        "lessons": [86, 87],
        "evidence_class": "A",
        "machine_status": "REFERENCE",
        "source_detail": "M9 L86 00:00:31-00:08:42 and later session examples; M9 L87 00:00:24-00:03:59 states the sell-side mirror and confirms parameters are reversed from the buy lesson.",
        "note": "This is a family of contextual intraday templates, not one universal deterministic setup. FX-specific timing/targets remain scoped to the lesson.",
    },
    "CORE_DAYTRADE_ROUTINE": {
        "concept": "daytrade_routine",
        "summary": "Maintain the higher-timeframe inventory and directional order flow first, then use session timing plus breaker/OTE/other references for execution planning.",
        "lessons": [88, 114, 115],
        "evidence_class": "B",
        "machine_status": "PARTIAL",
    },
    "CORE_COMMODITY_CARRY_STRUCTURE": {
        "concept": "commodity_carry",
        "summary": "Commodity premium/carrying-charge and spread relationships can reveal commercial conditions and qualify higher-timeframe opportunity.",
        "lessons": [92, 93, 108],
        "evidence_class": "B",
        "machine_status": "REFERENCE",
    },
    "CORE_BOND_OPENING_RANGE": {
        "concept": "bond_opening_range",
        "summary": "Lesson 94 explicitly defines the 30-year Treasury-bond futures true day as 08:00-15:00 New York and its opening range as 08:00-09:00; the opening range frequently frames a day high/low, stop run or fair-value/PD-array setup.",
        "lessons": [94],
        "evidence_class": "A",
        "machine_status": "REFERENCE",
        "source_detail": "M10 L94 00:03:05-00:04:09.",
        "note": "Bond-specific ZB framework. Do not transfer its opening-range clock to equity index futures.",
    },
    "CORE_BOND_SPLIT_SESSION": {
        "concept": "bond_split_session",
        "summary": "Lesson 95 explicitly splits the Treasury-bond day into an AM session/morning trend from 08:00-noon New York and a PM session from noon-15:00, with the completed AM range used to judge whether the PM session is likely to continue, reverse, abbreviate or be skipped.",
        "lessons": [95],
        "evidence_class": "A",
        "machine_status": "REFERENCE",
        "source_detail": "M10 L95 00:05:05-00:07:31 session definitions; 00:08:36-00:09:30 PM-abbreviation rule; 00:10:24-00:11:12 worked PM example.",
        "note": "Bond-specific session logic; not interchangeable with the Month-10 equity-index AM/PM clocks.",
    },
    "CORE_BOND_DAY_TYPE": {
        "concept": "bond_day_type",
        "summary": "Economic-calendar, overnight-range and volatility context help distinguish bond consolidation days from trend days before execution.",
        "lessons": [96, 97],
        "evidence_class": "B",
        "machine_status": "REFERENCE",
    },
    "CORE_STOCK_RELATIVE_WATCHLIST": {
        "concept": "stock_watchlist",
        "summary": "Stock selection starts with broad-index/seasonal direction, then ranks individual names by relative strength or weakness before any options/execution decision.",
        "lessons": [103, 104, 105, 106],
        "evidence_class": "B",
        "machine_status": "REFERENCE",
    },
    "CORE_MULTI_ASSET_SYSTEM": {
        "concept": "multi_asset_system",
        "summary": "Treat bonds, rates, dollar, commodities and equities as an interacting system and seek confirmation/divergence across assets for higher-timeframe analysis.",
        "lessons": [47, 107, 112],
        "evidence_class": "B",
        "machine_status": "REFERENCE",
    },
    "CORE_MEGA_TRADE_SELECTION": {
        "concept": "mega_trades",
        "summary": "Large commodity, FX, stock and bond opportunities are selected from macro/seasonal/relative-strength alignment; the asset-specific implementation differs by market.",
        "lessons": [108, 109, 110, 111],
        "evidence_class": "B",
        "machine_status": "REFERENCE",
    },
})


VISUAL_AUDIT_GAPS: dict[str, dict[str, Any]] = {
    "CORE_OTE": {"lessons": [4, 5, 88, 115], "status": "TEXT_CERTIFIED_NUMERIC", "gap": "No unresolved numeric source gap; active impulse/dealing-range selection remains contextual."},
    "CORE_FAIR_VALUE_GAP": {"lessons": [36, 41, 95, 115], "status": "TEXT_CERTIFIED_GEOMETRY", "gap": "No unresolved FVG boundary gap; inversion/expiry/mitigation rules remain model-specific."},
    "CORE_ORDER_BLOCK": {"lessons": [27], "status": "TEXT_CERTIFIED_CONTEXTUAL", "gap": "Candidate and validation are text-certified; contextual support/resistance and search-window selection remain non-canonical."},
    "CORE_MITIGATION_BLOCK": {"lessons": [28, 68], "status": "TEXT_CERTIFIED_CONTEXTUAL", "gap": "Structure-shift sequence is text-certified; swing segmentation remains contextual."},
    "CORE_BREAKER_BLOCK": {"lessons": [29, 43, 52, 88, 115], "status": "TEXT_CERTIFIED_CONTEXTUAL", "gap": "Breaker sequence is text-certified; swing/reference quantification remains contextual."},
    "CORE_REJECTION_BLOCK": {"lessons": [30, 73], "status": "TEXT_CERTIFIED_CONTEXTUAL", "gap": "Wick-to-body geometry is text-certified; qualifying swing/context selection remains contextual."},
    "CORE_RECLAIMED_ORDER_BLOCK": {"lessons": [31], "status": "TEXT_CERTIFIED_CONTEXTUAL", "gap": "Re-use relationship is text-certified; market-maker curve/climax and qualifying prior-block selection remain contextual."},
    "CORE_PROPULSION_BLOCK": {"lessons": [32], "status": "TEXT_CERTIFIED_CONTEXTUAL", "gap": "Propulsion relationship is text-certified but depends on the parent order-block context."},
    "CORE_OPEN_FLOAT": {"lessons": [40, 42], "status": "TEXT_CERTIFIED_REFERENCE", "gap": "Open-float definition is text-certified; actual resting order quantity is not inferable from OHLC."},
    "CORE_INSTITUTIONAL_SWING_POINTS": {"lessons": [40, 42, 43], "status": "TEXT_CERTIFIED_CONTEXTUAL", "gap": "Base swing and failure-swing concepts are text-certified; institutional relevance remains contextual."},
    "CORE_PD_ARRAY_MATRIX": {"lessons": [52, 53, 59, 65, 68, 73, 79, 88, 101, 112], "status": "TEXT_CERTIFIED_CONTEXTUAL", "gap": "Array hierarchy is text-certified; active-array/dealing-range selection remains contextual."},
    "CORE_WEEKLY_PROFILE_CONTEXT": {"lessons": [65, 66, 67, 71, 72, 73, 88], "status": "TEXT_CERTIFIED_CONTEXTUAL", "gap": "Conditional weekly profiles are text-certified; deterministic weekday conversion remains prohibited."},
    "CORE_WEEKLY_MANIPULATION_TEMPLATES": {"lessons": [66, 67, 71], "status": "TEXT_CERTIFIED_CONTEXTUAL", "gap": "Template families and prerequisites are text-certified; activation remains context-dependent."},
    "CORE_ONE_SHOT_ONE_KILL": {"lessons": [72], "status": "TEXT_CERTIFIED_REFERENCE", "gap": "Procedure prerequisites are text-certified; the complete setup depends on broader mentorship/free-tutorial knowledge and discretion."},
    "CORE_INTRADAY_PROFILE": {"lessons": [77, 84, 85, 95, 96, 97, 99, 100, 101], "status": "TEXT_CERTIFIED_CONTEXTUAL", "gap": "Profile families and stated criteria are text-certified; activation remains context-dependent."},
    "CORE_ZERO_GMT_PIVOT_CONTEXT": {"lessons": [82], "status": "TEXT_CERTIFIED_REFERENCE", "gap": "Pivot hierarchy and zero-GMT convention are text-certified; exact platform calculation must match that convention."},
    "CORE_ASIAN_SCALP_MODEL": {"lessons": [83], "status": "TEXT_CERTIFIED_FX_MODEL", "gap": "FX model is text-certified; portability to futures is explicitly prohibited."},
    "CORE_BREAD_AND_BUTTER_DAYTRADE": {"lessons": [86, 87], "status": "TEXT_CERTIFIED_CONTEXTUAL", "gap": "Buy/sell template families are text-certified; model activation remains context-dependent."},
    "CORE_BOND_OPENING_RANGE": {"lessons": [94], "status": "TEXT_CERTIFIED_BOND_RULE", "gap": "Bond opening-range clock and role are text-certified; remains ZB-specific."},
    "CORE_BOND_SPLIT_SESSION": {"lessons": [95], "status": "TEXT_CERTIFIED_BOND_RULE", "gap": "Bond AM/PM clocks and conditional use are text-certified; remains bond-specific."},
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
    row["knowledge"] = dict(LESSON_KNOWLEDGE.get(n) or {})
    row["rules"] = [
        rid for rid, rule in RULE_CATALOG.items() if n in (rule.get("lessons") or [])
    ]
    return row


def search(query: str) -> dict[str, Any]:
    q = str(query or "").strip().lower()
    if not q:
        return {"lectures": [], "rules": []}

    lesson_match = re.fullmatch(r"(?:lesson|lektion)?\s*#?\s*(\d{1,3})", q)
    if lesson_match:
        n = int(lesson_match.group(1))
        if 1 <= n <= 115:
            return {"lectures": [lecture(n)], "rules": [
                {"rule_id": rid, **RULE_CATALOG[rid]}
                for rid in lecture(n)["rules"]
            ]}

    month_match = re.fullmatch(r"(?:month|monat)\s*(\d{1,2})", q)
    if month_match:
        month = int(month_match.group(1))
        selected = [lecture(int(x["global_lesson"])) for x in LECTURES if int(x["month"]) == month]
        rule_ids = []
        for item in selected:
            for rid in item["rules"]:
                if rid not in rule_ids:
                    rule_ids.append(rid)
        return {
            "lectures": selected,
            "rules": [{"rule_id": rid, **RULE_CATALOG[rid]} for rid in rule_ids],
        }

    lectures = []
    for row in LECTURES:
        n = int(row["global_lesson"])
        knowledge = LESSON_KNOWLEDGE.get(n) or {}
        hay = " ".join(
            [
                str(row["title"]),
                str(knowledge.get("summary") or ""),
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
    mapped_lessons = {
        int(n)
        for rule in RULE_CATALOG.values()
        for n in (rule.get("lessons") or [])
    }
    unmapped_lessons = [n for n in range(1, 116) if n not in mapped_lessons]
    machine_counts = {}
    evidence_counts = {}
    for rule in RULE_CATALOG.values():
        machine_counts[rule["machine_status"]] = machine_counts.get(rule["machine_status"], 0) + 1
        evidence_counts[rule["evidence_class"]] = evidence_counts.get(rule["evidence_class"], 0) + 1
    structured_complete = (
        len(LECTURES) == 115
        and len(LESSON_FOCUS) == 115
        and len(LESSON_KNOWLEDGE) == 115
        and not unmapped_lessons
    )
    visual_locked = sorted(
        rid for rid, item in VISUAL_AUDIT_GAPS.items()
        if str(item.get("status") or "").upper() == "LOCKED"
    )
    source_rule_audit_complete = not visual_locked
    return {
        "knowledge_version": KNOWLEDGE_VERSION,
        "structured_knowledge_complete": structured_complete,
        "source_rule_audit_complete": source_rule_audit_complete,
        "fully_rule_audited": bool(structured_complete and source_rule_audit_complete),
        "frame_by_frame_visual_audit_complete": False,
        "visual_locked_rule_count": len(visual_locked),
        "visual_locked_rules": visual_locked,
        "lecture_count": len(LECTURES),
        "expected_lecture_count": 115,
        "months": 12,
        "all_lectures_indexed": len(LECTURES) == 115,
        "transcript_sources_available": sum(1 for x in LECTURES if x["transcript_available"]),
        "outline_sources_available": sum(1 for x in LECTURES if x["outline_available"]),
        "focus_indexed": sum(1 for x in LECTURES if x["global_lesson"] in LESSON_FOCUS),
        "lesson_knowledge_count": len(LESSON_KNOWLEDGE),
        "lesson_knowledge_complete": len(LESSON_KNOWLEDGE) == 115,
        "rule_catalog_count": len(RULE_CATALOG),
        "rule_mapped_lecture_count": len(mapped_lessons),
        "unmapped_lessons": unmapped_lessons,
        "machine_status_counts": machine_counts,
        "evidence_counts": evidence_counts,
        "by_month": by_month,
        "completion": {
            "corpus_index": "COMPLETE",
            "outline_focus_index": "COMPLETE" if len(LESSON_FOCUS) == 115 else "PARTIAL",
            "lesson_level_paraphrase": "COMPLETE" if len(LESSON_KNOWLEDGE) == 115 else "PARTIAL",
            "knowledge_rule_catalog": "COMPLETE" if not unmapped_lessons else "PARTIAL",
            "structured_knowledge_base": "COMPLETE" if structured_complete else "PARTIAL",
            "transcript_rule_promotion": "PARTIAL_BY_DESIGN",
            "source_rule_audit": "COMPLETE" if source_rule_audit_complete else "IN_PROGRESS_LOCKED",
            "frame_by_frame_visual_audit": "NOT_CLAIMED",
            "full_rule_audit": "COMPLETE" if structured_complete and source_rule_audit_complete else "IN_PROGRESS",
            "profitability_validation": "SEPARATE_TMBT_RESEARCH",
        },
        "important_limit": (
            "Structured knowledge and rule-source coverage are complete at the audited concept/rule level. "
            "This does not claim sentence-by-sentence transcript reproduction or a manual frame-by-frame viewing "
            "of all 53+ hours. Contextual/reference rules stay non-executable unless a separate deterministic "
            "READY rule and execution contract exist."
        ),
    }
