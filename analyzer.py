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

TREND_ARROW = {"up": "↑", "down": "↓"}


def build_prompt(stocks: list[dict], market_context: dict) -> str:
    stock_block = "\n".join(_format_stock_line(s) for s in stocks)
    market_block = format_for_prompt(market_context)

    return f"""{market_block}

You are a professional stock market analyst. Analyze these stocks and identify strong BUY opportunities.

STOCKS (all $1B+ revenue, {MIN_WOW_PCT}%+ WoW move, news catalyst present):
{stock_block}

ANALYSIS RULES:
- Weight market context: if VIX >25 or SPY WoW <-2%, be more selective
- Positive sentiment score + volume >1.5x = strong conviction signal
- All 3 trend arrows up = strong momentum
- Relative strength vs SPY >+2% means outperforming the market
- Earnings within 7 days = high risk/reward flag (mention explicitly)
- HIGH confidence: positive news + volume >1.5x + at least 2 trend arrows up
- MEDIUM confidence: good setup but missing one key confirming factor
- Do NOT include LOW confidence

For each BUY, provide a structured 10-point analysis:
- ticker, name, sector, confidence (HIGH or MEDIUM only)
- wow_change_pct, current_price (copy from data)
- price_target: +10-20% realistic target
- stop_loss: -5 to -8% below current price
- analysis object with these fields:
  - business_model: 1 sentence describing what the company does
  - financial_health: 1 sentence on revenue/earnings quality (reference specific numbers from news if available)
  - competitive_position: 1 sentence on moat or market position
  - catalyst: the specific news event or data point driving this signal
  - headwinds: key risk factor or headwind to watch
  - valuation: 1 sentence on whether stock looks cheap/fair/expensive vs peers or historical
  - technical_summary: 1 sentence summarizing the technical setup (trends, volume, relative strength)
  - bull_case: 2 sentences — best-case scenario from here
  - bear_case: 2 sentences — worst-case scenario from here
  - recommendation: 1 sentence — clear action statement with entry, target, stop

Respond ONLY with valid JSON array:
[
  {{
    "ticker": "MS",
    "name": "Morgan Stanley",
    "sector": "Financials",
    "confidence": "HIGH",
    "wow_change_pct": 9.06,
    "current_price": 191.96,
    "price_target": 210.00,
    "stop_loss": 177.00,
    "analysis": {{
      "business_model": "Global investment bank with leading positions in institutional securities, wealth management, and investment management.",
      "financial_health": "Q1 trading revenue beat estimates by $1B, indicating strong institutional activity and market share gains.",
      "competitive_position": "Top-3 global investment bank with a dominant wealth management franchise (>$6T AUM).",
      "catalyst": "Q1 earnings beat with trading revenue $1B above estimates, signaling broad-based strength.",
      "headwinds": "Trading revenue is inherently volatile and may not sustain at elevated levels.",
      "valuation": "Trading at 12x forward P/E, below 5-year average of 14x, suggesting upside re-rating potential.",
      "technical_summary": "All 3 trend arrows up with 2.1x average volume and +6% relative strength vs SPY — strong momentum.",
      "bull_case": "Sustained trading activity and wealth management inflows could drive earnings upgrades. Multiple expansion to historical average implies 15-20% upside.",
      "bear_case": "A market downturn could compress trading volumes and AUM-based fees simultaneously. Regulatory changes in capital markets remain an overhang.",
      "recommendation": "BUY at $191.96 with target $210.00 (+9.4%) and stop at $177.00 (-7.8%). Risk/reward favors longs."
    }}
  }}
]

If no strong buys, return: []
"""


def apply_sector_cap(signals: list[dict]) -> list[dict]:
    sector_counts: dict[str, int] = {}
    result = []
    sorted_signals = sorted(
        signals,
        key=lambda x: (0 if x.get("confidence") == "HIGH" else 1, -x.get("wow_change_pct", 0))
    )
    for s in sorted_signals:
        sector = s.get("sector", "Other")
        if sector_counts.get(sector, 0) < MAX_PER_SECTOR:
            result.append(s)
            sector_counts[sector] = sector_counts.get(sector, 0) + 1
    return result


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
        earn_text = f" ⚠️ EARNINGS {s['earnings_date']}" if s.get("earnings_within_7d") else ""
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
        model="claude-opus-4-6",
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
    earn_text = f"⚠️ EARNINGS {s['earnings_date']}" if s.get("earnings_within_7d") else ""
    sentiment = f"sentiment:{s.get('sentiment_score', 0):+.1f}"

    # Congress trade info (if available)
    cong_text = ""
    cong_trades = s.get("congress_trades", [])
    if cong_trades:
        cong_parts = [f"{t['filer']}({t['party']}) bought on {t['tx_date']}" for t in cong_trades[:3]]
        cong_text = f" | Congress: {'; '.join(cong_parts)}"

    return (
        f"- {s['ticker']} ({s['sector']}): "
        f"${s['current_price']} WoW {s['wow_change_pct']:+.2f}% | "
        f"{trends} | {rs_text} | {vol_text} | {sentiment} "
        f"{earn_text}{news_text}{cong_text}"
    )


# ── Structured analysis JSON template (shared across prompts) ────────────────
_ANALYSIS_JSON_TEMPLATE = """
Respond ONLY with valid JSON array. Each object must include:
- ticker, name, sector, confidence (HIGH or MEDIUM only)
- wow_change_pct, current_price (copy from data)
- price_target: realistic target price
- stop_loss: stop loss price
- analysis object with: business_model, financial_health, competitive_position,
  catalyst, headwinds, valuation, technical_summary, bull_case, bear_case, recommendation

If no strong signals, return: []
"""


def build_early_signal_prompt(stocks: list[dict], market_context: dict) -> str:
    """Prompt for early/accumulation signals — unusual volume, price hasn't moved."""
    stock_block = "\n".join(_format_stock_line(s) for s in stocks)
    market_block = format_for_prompt(market_context)

    return f"""{market_block}

You are a professional stock analyst specializing in EARLY DETECTION of institutional accumulation.

These stocks show UNUSUAL VOLUME but the price hasn't moved significantly yet. This pattern often precedes breakouts — smart money accumulating before a catalyst becomes mainstream.

STOCKS (unusual volume, minimal price movement):
{stock_block}

ANALYSIS RULES:
- Focus on WHY volume is elevated despite flat price — this is the key signal
- SEC filings (8-K, SC 13D) are the earliest signals — prioritize these over mainstream news
- Look for: upcoming catalysts, M&A rumors, activist stakes, contract wins, insider buying
- HIGH confidence: clear catalyst in news/filings + volume >1.5x + price hasn't moved
- MEDIUM confidence: elevated volume + circumstantial evidence of upcoming catalyst
- These are EARLY signals — price targets can be more aggressive (+15-25%)
- Stop loss should be tight (-5 to -7%) since these are speculative entries

{_ANALYSIS_JSON_TEMPLATE}"""


def build_dip_prompt(stocks: list[dict], market_context: dict) -> str:
    """Prompt for buy-the-dip signals — quality stocks that dropped."""
    stock_block = "\n".join(_format_stock_line(s) for s in stocks)
    market_block = format_for_prompt(market_context)

    return f"""{market_block}

You are a professional stock analyst specializing in CONTRARIAN value opportunities.

These are large-cap stocks that have DROPPED significantly this week. Your job is to determine if this is a BUYING OPPORTUNITY (overreaction) or a justified decline (fundamental deterioration).

STOCKS (all dropped 3%+ this week):
{stock_block}

ANALYSIS RULES:
- ONLY recommend BUY if the drop appears to be an overreaction
- Overreaction signs: broad market selloff, sector rotation (not company-specific), analyst downgrade on sentiment not fundamentals
- Red flags (do NOT recommend): earnings miss, guidance cut, product failure, regulatory action, fraud
- HIGH confidence: strong company + clear overreaction + support level holding + sentiment extreme
- MEDIUM confidence: likely overreaction but needs more confirmation
- Price target: recovery to pre-drop levels (+10-15%)
- Stop loss: -5 to -8% below current (wider than usual since dip entries are volatile)
- In the analysis, explicitly state WHY the drop is temporary vs permanent

{_ANALYSIS_JSON_TEMPLATE}"""


def build_pullback_prompt(stocks: list[dict], market_context: dict) -> str:
    """Prompt for pullback entry signals — uptrend stocks at support."""
    stock_block = "\n".join(_format_stock_line(s) for s in stocks)
    market_block = format_for_prompt(market_context)

    return f"""{market_block}

You are a professional stock analyst specializing in PULLBACK ENTRIES in uptrending stocks.

These stocks have strong 1-month uptrends but pulled back this week. The question: is the pullback a healthy buying opportunity, or is the trend reversing?

STOCKS (uptrend + weekly pullback):
{stock_block}

ANALYSIS RULES:
- Healthy pullback signs: low volume on pullback (no distribution), holding above key support, positive news backdrop intact
- Trend reversal signs: high volume on pullback (distribution), breaking below support, negative news catalyst
- HIGH confidence: uptrend intact + low-volume pullback + support holding + positive sentiment
- MEDIUM confidence: uptrend likely intact but one concern (e.g., volume slightly elevated)
- Price target: retest of recent highs (+8-15%)
- Stop loss: tight, just below the pullback low (-4 to -6%)

{_ANALYSIS_JSON_TEMPLATE}"""


def build_congress_prompt(stocks: list[dict], market_context: dict) -> str:
    """Prompt for congress front-running signals — politicians bought, price hasn't moved."""
    stock_block = "\n".join(_format_stock_line(s) for s in stocks)
    market_block = format_for_prompt(market_context)

    return f"""{market_block}

You are a professional stock analyst evaluating CONGRESSIONAL TRADE signals.

Members of Congress recently bought these stocks (disclosed via financial filings). Due to reporting delays, these trades happened 30-45 days ago. The price hasn't moved significantly since their purchase — meaning we may still have an edge.

STOCKS (congress members bought recently, price flat since):
{stock_block}

ANALYSIS RULES:
- Congressional members may have informational advantages (upcoming legislation, contracts, regulatory decisions)
- Evaluate: What could the congress member know? Is there pending legislation or contracts in their committee jurisdiction?
- Cross-reference with news — any hints of upcoming catalysts?
- HIGH confidence: multiple congress members buying same stock + relevant committee membership + positive news backdrop
- MEDIUM confidence: single congress member buying + plausible thesis
- Price target: +10-20% (these are medium-term plays, not day trades)
- Stop loss: -6 to -8%
- In the analysis catalyst field, mention the congress member(s) and their party/chamber

{_ANALYSIS_JSON_TEMPLATE}"""


def _run_analysis(prompt: str, stocks: list[dict], signal_type: str, label: str) -> list[dict]:
    """Generic analysis runner: send prompt to Claude, parse response, merge data."""
    if not stocks:
        return []

    print(f"[{label}] Sending {len(stocks)} stocks to Claude...")
    stock_lookup = {s["ticker"]: s for s in stocks}

    try:
        message = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = message.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        signals = json.loads(raw)
        signals = [s for s in signals if s.get("confidence", "").upper() in ("HIGH", "MEDIUM")]

        for s in signals:
            orig = stock_lookup.get(s["ticker"], {})
            for key in ("volume_ratio", "range_position", "relative_strength_vs_spy",
                        "earnings_within_7d", "earnings_date", "sentiment_score",
                        "trend_1d", "trend_1w", "trend_1m", "news"):
                s[key] = orig.get(key)
            s["signal_type"] = signal_type
            # Backward-compatible reason/risk from structured analysis
            analysis = s.get("analysis", {})
            if analysis:
                s["reason"] = f"{analysis.get('catalyst', '')} {analysis.get('technical_summary', '')}".strip()
                s["risk"] = analysis.get("headwinds", s.get("risk", ""))

        print(f"[{label}] Claude identified {len(signals)} signal(s).")
        return signals
    except json.JSONDecodeError as e:
        print(f"[{label}] Failed to parse Claude response: {e}")
        return []
    except Exception as e:
        print(f"[{label}] Analysis failed: {e}")
        return []


def analyze_stocks(stocks: list[dict], market_context: dict) -> list[dict]:
    signals = _run_analysis(
        build_prompt(stocks, market_context), stocks, "MOMENTUM", "Momentum"
    )
    # Tag existing momentum signals
    for s in signals:
        s.setdefault("signal_type", "MOMENTUM")
    return apply_sector_cap(signals)


def analyze_early_signals(stocks: list[dict], market_context: dict) -> list[dict]:
    return _run_analysis(
        build_early_signal_prompt(stocks, market_context), stocks, "EARLY", "Early Signals"
    )


def analyze_dip_signals(stocks: list[dict], market_context: dict) -> list[dict]:
    return _run_analysis(
        build_dip_prompt(stocks, market_context), stocks, "DIP_BUY", "Dip Signals"
    )


def analyze_pullback_signals(stocks: list[dict], market_context: dict) -> list[dict]:
    return _run_analysis(
        build_pullback_prompt(stocks, market_context), stocks, "PULLBACK", "Pullback Signals"
    )


def analyze_congress_signals(stocks: list[dict], market_context: dict) -> list[dict]:
    return _run_analysis(
        build_congress_prompt(stocks, market_context), stocks, "CONGRESS", "Congress Signals"
    )
