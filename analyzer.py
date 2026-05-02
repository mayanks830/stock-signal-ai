import json
import httpx
import anthropic
from config import ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL, MAX_PER_SECTOR, MIN_WOW_PCT
from market_context import format_for_prompt

_http_client = httpx.Client(verify=False)

client_kwargs = {"api_key": ANTHROPIC_API_KEY, "http_client": _http_client}
if ANTHROPIC_BASE_URL:
    client_kwargs["base_url"] = ANTHROPIC_BASE_URL

client = anthropic.Anthropic(**client_kwargs)

TREND_ARROW = {"up": "\u2191", "down": "\u2193"}

# Models for each call stage
SCREEN_MODEL = "claude-haiku-4-5-20250514"
ANALYSIS_MODEL = "claude-sonnet-4-20250514"


def _strip_json(raw: str) -> str:
    """Strip markdown code fences from JSON response."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    return raw


# ── Call 1: Screening ──────────────────────────────────────────────────────────

def build_screening_prompt(candidates: list[dict], market_context: dict) -> str:
    """Build prompt for Call 1: bulk screening with haiku."""
    stock_block = "\n".join(_format_stock_line(s) for s in candidates)
    market_block = format_for_prompt(market_context)

    return f"""{market_block}

You are a stock screener. From the candidates below, select the 5-8 most interesting for deep analysis.

CANDIDATES ({len(candidates)} stocks from multiple pipelines):
{stock_block}

SELECTION CRITERIA:
- Prioritize stocks with MULTIPLE confirming factors (volume + news + trend alignment)
- Include a mix of signal types if available (momentum, dip buys, early accumulation, pullbacks, congress trades)
- Deprioritize stocks where the move already happened (WoW >+10% with no new catalyst)
- Favor stocks with clear, specific catalysts over vague momentum
- If VIX >25 or SPY WoW <-2%, be more selective

For each pick, tag it with the signal_type that best fits:
- MOMENTUM: strong trend + volume + catalyst
- EARLY: unusual volume but price flat (accumulation)
- DIP_BUY: quality stock dropped, looks like overreaction
- PULLBACK: uptrend stock pulling back to support
- CONGRESS: congressional trading activity

Respond ONLY with valid JSON array:
[
  {{"ticker": "NVDA", "signal_type": "MOMENTUM", "reason": "2.1x volume + earnings beat + all trends up"}}
]

If no stocks are worth deep analysis, return: []
"""


def screen_candidates(all_candidates: list[dict], market_context: dict) -> list[dict]:
    """Call 1: Screen all candidates down to 5-8 best picks using haiku."""
    if not all_candidates:
        return []

    print(f"[Screen] Sending {len(all_candidates)} candidates to haiku for screening...")

    try:
        message = client.messages.create(
            model=SCREEN_MODEL,
            max_tokens=2048,
            messages=[{"role": "user", "content": build_screening_prompt(all_candidates, market_context)}],
        )

        raw = _strip_json(message.content[0].text)
        picks = json.loads(raw)

        # Map back to full candidate data
        candidate_lookup = {s["ticker"]: s for s in all_candidates}
        screened = []
        for pick in picks:
            ticker = pick.get("ticker")
            if ticker in candidate_lookup:
                entry = candidate_lookup[ticker].copy()
                entry["signal_type"] = pick.get("signal_type", entry.get("signal_type", "MOMENTUM"))
                entry["screen_reason"] = pick.get("reason", "")
                screened.append(entry)

        print(f"[Screen] Haiku selected {len(screened)} stocks for deep analysis.")
        return screened
    except json.JSONDecodeError as e:
        print(f"[Screen] Failed to parse haiku response: {e}")
        return all_candidates[:8]  # Fallback: take first 8
    except Exception as e:
        print(f"[Screen] Screening failed: {e}")
        return all_candidates[:8]


# ── Call 2: Deep Analysis ──────────────────────────────────────────────────────

def build_deep_analysis_prompt(stock: dict, market_context: dict) -> str:
    """Build prompt for Call 2: deep per-ticker analysis."""
    stock_line = _format_stock_line(stock)
    market_block = format_for_prompt(market_context)
    signal_type = stock.get("signal_type", "MOMENTUM")
    screen_reason = stock.get("screen_reason", "")

    return f"""{market_block}

You are a senior quantitative analyst. Analyze this stock with intellectual honesty.

STOCK:
{stock_line}

Pipeline context: {signal_type} signal. Screening note: {screen_reason}

ANALYSIS RULES — you MUST follow these:

1. SIGNAL must be one of: BUY, SELL, HOLD, CONFLICTED
   - CONFLICTED is required when technicals and sentiment/fundamentals disagree
   - Do NOT force a BUY when the data is mixed — CONFLICTED is the honest answer

2. CONFIDENCE must be 1-10 (integer):
   - 1-3: Speculative, limited data, single weak signal
   - 4-6: Moderate, some confirming factors but gaps exist
   - 7-8: Strong, multiple confirming factors across different data types
   - 9-10: Very strong, requires citing 2+ independent data sources that confirm
   - You CANNOT give >7 unless you cite specific confirming data points

3. DATA GAPS — you MUST list what data you DON'T have:
   - No options flow data, no real-time order book, no institutional positioning
   - If earnings data is missing, say so
   - If news is limited or old, say so
   - This is not optional — every analysis must disclose gaps

4. CONFLICTS — explicitly surface when:
   - Technicals say buy but sentiment is negative (or vice versa)
   - Short-term bullish but long-term bearish
   - Price action strong but volume not confirming

Respond ONLY with valid JSON (no markdown, no code blocks):
{{
  "ticker": "{stock.get('ticker', '')}",
  "name": "{stock.get('name', stock.get('ticker', ''))}",
  "sector": "{stock.get('sector', 'Other')}",
  "signal": "BUY|SELL|HOLD|CONFLICTED",
  "confidence": 7,
  "timeframe": "swing|position|day",
  "current_price": {stock.get('current_price', 0)},
  "wow_change_pct": {stock.get('wow_change_pct', 0)},
  "price_target": 0.00,
  "stop_loss": 0.00,
  "technicals": {{
    "summary": "1-2 sentence technical picture",
    "indicators": ["RSI 65", "MACD bullish", "Above 50 MA"]
  }},
  "sentiment": {{
    "summary": "1-2 sentence sentiment read",
    "sources": ["News headlines", "Volume analysis"]
  }},
  "conflicts": ["List any conflicts between technicals/sentiment/fundamentals"],
  "data_gaps": ["List data you don't have"],
  "analysis": {{
    "business_model": "1 sentence",
    "catalyst": "specific event driving this setup",
    "headwinds": "key risk",
    "valuation": "cheap/fair/expensive vs peers",
    "technical_summary": "1 sentence technical setup"
  }}
}}
"""


def deep_analyze(stock: dict, market_context: dict) -> dict | None:
    """Call 2: Deep analysis for a single stock."""
    ticker = stock.get("ticker", "?")
    print(f"  [Analyze] {ticker}...")

    try:
        message = client.messages.create(
            model=ANALYSIS_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": build_deep_analysis_prompt(stock, market_context)}],
        )

        raw = _strip_json(message.content[0].text)
        result = json.loads(raw)

        # Validate required fields
        signal = result.get("signal", "HOLD")
        if signal not in ("BUY", "SELL", "HOLD", "CONFLICTED"):
            result["signal"] = "HOLD"

        conf = result.get("confidence", 5)
        if not isinstance(conf, int) or conf < 1 or conf > 10:
            result["confidence"] = 5

        # Ensure data_gaps exists
        if "data_gaps" not in result:
            result["data_gaps"] = ["No data gaps disclosed by model"]
        if "conflicts" not in result:
            result["conflicts"] = []

        return result
    except json.JSONDecodeError as e:
        print(f"  [Analyze] Failed to parse response for {ticker}: {e}")
        return None
    except Exception as e:
        print(f"  [Analyze] Analysis failed for {ticker}: {e}")
        return None


# ── Call 3: Risk Framing ───────────────────────────────────────────────────────

def build_risk_frame_prompt(analysis: dict) -> str:
    """Build prompt for Call 3: risk framing for a completed analysis."""
    ticker = analysis.get("ticker", "?")
    signal = analysis.get("signal", "HOLD")
    confidence = analysis.get("confidence", 5)
    price = analysis.get("current_price", 0)
    target = analysis.get("price_target", 0)
    stop = analysis.get("stop_loss", 0)
    technicals = analysis.get("technicals", {})
    sentiment = analysis.get("sentiment", {})
    conflicts = analysis.get("conflicts", [])
    catalyst = analysis.get("analysis", {}).get("catalyst", "")

    return f"""You are a risk analyst reviewing a trade signal. Be skeptical and thorough.

SIGNAL SUMMARY:
- Ticker: {ticker}
- Signal: {signal} (Confidence: {confidence}/10)
- Price: ${price} → Target: ${target} | Stop: ${stop}
- Technicals: {technicals.get('summary', 'N/A')}
- Sentiment: {sentiment.get('summary', 'N/A')}
- Catalyst: {catalyst}
- Conflicts: {', '.join(conflicts) if conflicts else 'None identified'}

Provide an honest risk assessment. Do NOT just agree with the signal — challenge it.

Respond ONLY with valid JSON (no markdown, no code blocks):
{{
  "bull_case": "2-3 sentences: what must be true for this to work. Be specific about catalysts and levels.",
  "bear_case": "2-3 sentences: the most likely way this trade fails. Not a generic disclaimer.",
  "invalidation": "The specific price level or event that kills this thesis",
  "reward_risk_ratio": 2.0,
  "upcoming_events": ["List known events: earnings, CPI, Fed, ex-div, etc."],
  "recommendation": "1-2 sentence clear action statement. If CONFLICTED, say what would resolve the conflict."
}}
"""


def risk_frame(analysis: dict) -> dict:
    """Call 3: Risk framing for a completed analysis."""
    ticker = analysis.get("ticker", "?")
    print(f"  [Risk] {ticker}...")

    try:
        message = client.messages.create(
            model=ANALYSIS_MODEL,
            max_tokens=2048,
            messages=[{"role": "user", "content": build_risk_frame_prompt(analysis)}],
        )

        raw = _strip_json(message.content[0].text)
        result = json.loads(raw)

        # Ensure all expected fields exist
        for key in ("bull_case", "bear_case", "invalidation", "recommendation"):
            if key not in result:
                result[key] = ""
        if "reward_risk_ratio" not in result:
            result["reward_risk_ratio"] = None
        if "upcoming_events" not in result:
            result["upcoming_events"] = []

        return result
    except json.JSONDecodeError as e:
        print(f"  [Risk] Failed to parse response for {ticker}: {e}")
        return {"bull_case": "", "bear_case": "", "invalidation": "",
                "reward_risk_ratio": None, "upcoming_events": [], "recommendation": ""}
    except Exception as e:
        print(f"  [Risk] Risk framing failed for {ticker}: {e}")
        return {"bull_case": "", "bear_case": "", "invalidation": "",
                "reward_risk_ratio": None, "upcoming_events": [], "recommendation": ""}


# ── Full 3-Call Pipeline ───────────────────────────────────────────────────────

def run_full_analysis(all_candidates: list[dict], market_context: dict) -> list[dict]:
    """Run the complete 3-call pipeline: screen → analyze → risk frame.

    Returns list of signal dicts ready for save_signal().
    """
    if not all_candidates:
        return []

    # Call 1: Screen
    screened = screen_candidates(all_candidates, market_context)
    if not screened:
        print("[Pipeline] No stocks passed screening.")
        return []

    # Calls 2 & 3: Deep analyze + risk frame each screened stock
    signals = []
    for stock in screened:
        # Call 2: Deep analysis
        analysis = deep_analyze(stock, market_context)
        if not analysis:
            continue

        # Skip HOLD signals with low confidence (not worth reporting)
        if analysis.get("signal") == "HOLD" and analysis.get("confidence", 0) < 4:
            print(f"  [Pipeline] Skipping {analysis['ticker']}: HOLD with confidence {analysis.get('confidence')}")
            continue

        # Call 3: Risk framing
        risk = risk_frame(analysis)

        # Merge into final signal dict
        signal = _build_signal_dict(stock, analysis, risk)
        signals.append(signal)

    print(f"[Pipeline] Complete. {len(signals)} signal(s) from {len(screened)} screened stocks.")
    return apply_sector_cap(signals)


def _build_signal_dict(stock: dict, analysis: dict, risk: dict) -> dict:
    """Merge candidate data, deep analysis, and risk framing into a signal dict."""
    # Merge analysis + risk into a single analysis_json blob
    full_analysis = {
        # From Call 2
        "technicals": analysis.get("technicals", {}),
        "sentiment": analysis.get("sentiment", {}),
        "conflicts": analysis.get("conflicts", []),
        "data_gaps": analysis.get("data_gaps", []),
        "timeframe": analysis.get("timeframe", "swing"),
        **analysis.get("analysis", {}),
        # From Call 3
        "bull_case": risk.get("bull_case", ""),
        "bear_case": risk.get("bear_case", ""),
        "invalidation": risk.get("invalidation", ""),
        "reward_risk_ratio": risk.get("reward_risk_ratio"),
        "upcoming_events": risk.get("upcoming_events", []),
        "recommendation": risk.get("recommendation", ""),
    }

    # Backward-compatible reason/risk fields
    catalyst = analysis.get("analysis", {}).get("catalyst", "")
    tech_summary = analysis.get("analysis", {}).get("technical_summary", "")
    reason = f"{catalyst} {tech_summary}".strip()
    headwinds = analysis.get("analysis", {}).get("headwinds", "")

    return {
        "ticker": analysis.get("ticker", stock.get("ticker")),
        "name": analysis.get("name", stock.get("name", "")),
        "sector": analysis.get("sector", stock.get("sector", "Other")),
        "signal": analysis.get("signal", "HOLD"),
        "confidence": str(analysis.get("confidence", 5)),
        "current_price": analysis.get("current_price", stock.get("current_price")),
        "price_target": analysis.get("price_target"),
        "stop_loss": analysis.get("stop_loss"),
        "wow_change_pct": analysis.get("wow_change_pct", stock.get("wow_change_pct")),
        "signal_type": stock.get("signal_type", "MOMENTUM"),
        # Copy raw data from candidate
        "volume_ratio": stock.get("volume_ratio"),
        "range_position": stock.get("range_position"),
        "relative_strength_vs_spy": stock.get("relative_strength_vs_spy"),
        "earnings_within_7d": stock.get("earnings_within_7d"),
        "earnings_date": stock.get("earnings_date"),
        "sentiment_score": stock.get("sentiment_score"),
        "trend_1d": stock.get("trend_1d"),
        "trend_1w": stock.get("trend_1w"),
        "trend_1m": stock.get("trend_1m"),
        "news": stock.get("news", []),
        # Structured analysis
        "analysis": full_analysis,
        # Backward compat
        "reason": reason,
        "risk": headwinds,
    }


# ── Legacy per-pipeline entry points (used by scanner.py and main.py) ──────────
# These are thin wrappers that tag candidates with signal_type for the pipeline.

def analyze_stocks(stocks: list[dict], market_context: dict) -> list[dict]:
    for s in stocks:
        s.setdefault("signal_type", "MOMENTUM")
    return run_full_analysis(stocks, market_context)


def analyze_early_signals(stocks: list[dict], market_context: dict) -> list[dict]:
    for s in stocks:
        s["signal_type"] = "EARLY"
    return run_full_analysis(stocks, market_context)


def analyze_dip_signals(stocks: list[dict], market_context: dict) -> list[dict]:
    for s in stocks:
        s["signal_type"] = "DIP_BUY"
    return run_full_analysis(stocks, market_context)


def analyze_pullback_signals(stocks: list[dict], market_context: dict) -> list[dict]:
    for s in stocks:
        s["signal_type"] = "PULLBACK"
    return run_full_analysis(stocks, market_context)


def analyze_congress_signals(stocks: list[dict], market_context: dict) -> list[dict]:
    for s in stocks:
        s["signal_type"] = "CONGRESS"
    return run_full_analysis(stocks, market_context)


# ── Helpers ────────────────────────────────────────────────────────────────────

def apply_sector_cap(signals: list[dict]) -> list[dict]:
    sector_counts: dict[str, int] = {}
    result = []
    sorted_signals = sorted(
        signals,
        key=lambda x: (-int(x.get("confidence", 5)), -x.get("wow_change_pct", 0))
    )
    for s in sorted_signals:
        sector = s.get("sector", "Other")
        if sector_counts.get(sector, 0) < MAX_PER_SECTOR:
            result.append(s)
            sector_counts[sector] = sector_counts.get(sector, 0) + 1
    return result


def _format_stock_line(s: dict) -> str:
    """Format a single stock's data into a prompt line."""
    news_parts = []
    for n in s.get("news", []):
        label = n.get("sentiment", "NEUTRAL")
        news_parts.append(f"[{label}] {n['title']}")
    news_text = " | News: " + "; ".join(news_parts) if news_parts else ""

    trends = (
        f"1d:{TREND_ARROW.get(s.get('trend_1d',''), '?')} "
        f"1w:{TREND_ARROW.get(s.get('trend_1w',''), '?')} "
        f"1m:{TREND_ARROW.get(s.get('trend_1m',''), '?')}"
    )
    rs = s.get("relative_strength_vs_spy")
    rs_text = f"vs SPY: {rs:+.1f}%" if rs is not None else ""
    vol_text = f"{s.get('volume_ratio', '?')}x vol"
    earn_text = f"EARNINGS {s['earnings_date']}" if s.get("earnings_within_7d") else ""
    sentiment = f"sentiment:{s.get('sentiment_score', 0):+.1f}"

    # Congress trade info (if available)
    cong_text = ""
    cong_trades = s.get("congress_trades", [])
    if cong_trades:
        cong_parts = [f"{t['filer']}({t['party']}) bought on {t['tx_date']}" for t in cong_trades[:3]]
        cong_text = f" | Congress: {'; '.join(cong_parts)}"

    # Signal type tag
    sig_type = s.get("signal_type", "")
    type_tag = f"[{sig_type}] " if sig_type else ""

    return (
        f"- {type_tag}{s['ticker']} ({s.get('sector', 'Other')}): "
        f"${s.get('current_price', '?')} WoW {s.get('wow_change_pct', 0):+.2f}% | "
        f"{trends} | {rs_text} | {vol_text} | {sentiment} "
        f"{earn_text}{news_text}{cong_text}"
    )


# ── Watchlist (unchanged) ─────────────────────────────────────────────────────

def build_watchlist_prompt(stocks: list[dict], market_context: dict) -> str:
    lines = []
    for s in stocks:
        if s.get("error"):
            continue

        news_parts = []
        for n in s.get("news", []):
            label = n.get("sentiment", "NEUTRAL")
            news_parts.append(f"[{label}] {n['title']}")
        news_text = " | News: " + "; ".join(news_parts) if news_parts else ""

        trends = (
            f"1d:{TREND_ARROW.get(s.get('trend_1d',''), '?')} "
            f"1w:{TREND_ARROW.get(s.get('trend_1w',''), '?')} "
            f"1m:{TREND_ARROW.get(s.get('trend_1m',''), '?')}"
        )
        rs = s.get("relative_strength_vs_spy")
        rs_text = f"vs SPY: {rs:+.1f}%" if rs is not None else ""
        vol_text = f"{s.get('volume_ratio', '?')}x vol"
        earn_text = f" EARNINGS {s['earnings_date']}" if s.get("earnings_within_7d") else ""
        sentiment = f"sentiment:{s.get('sentiment_score', 0):+.1f}"

        # Technical indicators
        tech_parts = []
        if s.get("rsi") is not None:
            tech_parts.append(f"RSI:{s['rsi']:.0f}({s.get('rsi_status','')})")
        if s.get("ma50") is not None:
            tech_parts.append(f"50MA:${s['ma50']}")
        if s.get("ma200") is not None:
            tech_parts.append(f"200MA:${s['ma200']}")
        macd = s.get("macd")
        if macd:
            tech_parts.append(f"MACD:{macd['crossover']}")
        tech_text = " | " + " ".join(tech_parts) if tech_parts else ""

        # Insider & social data
        social_parts = []
        insider_sig = s.get("insider_signal")
        if insider_sig and insider_sig != "NONE":
            social_parts.append(f"Insider:{insider_sig}(B:{s.get('insider_buys',0)}/S:{s.get('insider_sells',0)})")
        st_sent = s.get("st_sentiment")
        if st_sent and st_sent != "UNKNOWN":
            social_parts.append(f"StockTwits:{st_sent}")
        social_text = " | " + " ".join(social_parts) if social_parts else ""

        lines.append(
            f"- {s['ticker']} ({s['sector']}): "
            f"${s['current_price']} Daily {s.get('daily_change_pct', 0):+.2f}% WoW {s['wow_change_pct']:+.2f}% | "
            f"{trends} | {rs_text} | {vol_text} | {sentiment}"
            f"{tech_text}{social_text}{earn_text}{news_text}"
        )

    stock_block = "\n".join(lines)
    market_block = format_for_prompt(market_context)

    return f"""{market_block}

You are a professional stock market analyst reviewing a personal watchlist. Analyze ALL stocks below and provide outlook and actionable signals for any with notable activity.

WATCHLIST STOCKS:
{stock_block}

ANALYSIS RULES:
- Provide outlook for EVERY stock that has notable activity (significant price move, RSI extreme, MA crossover, MACD crossover, volume spike, or relevant news)
- Outlook: BULLISH, BEARISH, or NEUTRAL
- For stocks with strong setups, provide a BUY or SELL signal with price target and stop loss
- RSI >70 = overbought warning, RSI <30 = oversold opportunity
- Price below 200-day MA = bearish trend warning
- MACD bullish cross + volume confirmation = strong buy setup
- Insider STRONG_BUY or NET_BUY = bullish confirmation (executives buying their own stock)
- Insider HEAVY_SELL = bearish warning (but consider scheduled selling plans)
- StockTwits VERY_BULLISH/VERY_BEARISH = crowd sentiment extremes (can be contrarian at extremes)
- Weight market context: if VIX >25 or SPY WoW <-2%, be more cautious
- Include price_target and stop_loss ONLY for actionable signals (BUY/SELL)

For each stock with notable activity:
- ticker, outlook (BULLISH/BEARISH/NEUTRAL)
- signal: "BUY", "SELL", or "HOLD" (HOLD = no action but worth watching)
- reasoning: 2-3 sentences referencing specific data
- price_target (only for BUY/SELL), stop_loss (only for BUY/SELL)
- current_price, wow_change_pct (copy from data)

Respond ONLY with valid JSON array:
[
  {{
    "ticker": "NVDA",
    "outlook": "BULLISH",
    "signal": "BUY",
    "reasoning": "RSI at 35 showing oversold conditions with MACD bullish crossover. Volume 1.8x average confirms institutional buying. Price recovering above 50-day MA.",
    "price_target": 150.00,
    "stop_loss": 125.00,
    "current_price": 135.50,
    "wow_change_pct": 4.2
  }}
]

If no stocks have notable activity, return: []
"""


def analyze_watchlist(stocks: list[dict], market_context: dict) -> list[dict]:
    """Analyze watchlist stocks with broader outlook (not just BUY signals)."""
    valid_stocks = [s for s in stocks if not s.get("error") and s.get("current_price")]
    if not valid_stocks:
        return []

    print(f"Sending {len(valid_stocks)} watchlist stocks to Claude for analysis...")

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8192,
        messages=[{"role": "user", "content": build_watchlist_prompt(valid_stocks, market_context)}],
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        analyses = json.loads(raw)
        print(f"Claude analyzed {len(analyses)} stocks with notable activity.")
        return analyses
    except json.JSONDecodeError as e:
        print(f"[!] Failed to parse Claude watchlist response: {e}")
        return []
