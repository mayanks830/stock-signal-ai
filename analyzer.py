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
    lines = []
    for s in stocks:
        # Labeled news with sentiment
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

        lines.append(
            f"- {s['ticker']} ({s['sector']}): "
            f"${s['current_price']} WoW {s['wow_change_pct']:+.2f}% | "
            f"{trends} | {rs_text} | {vol_text} | {sentiment} "
            f"{earn_text}{news_text}"
        )

    stock_block = "\n".join(lines)
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


def analyze_stocks(stocks: list[dict], market_context: dict) -> list[dict]:
    if not stocks:
        return []

    print(f"Sending {len(stocks)} stocks to Claude for analysis...")
    stock_lookup = {s["ticker"]: s for s in stocks}

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=8192,
        messages=[{"role": "user", "content": build_prompt(stocks, market_context)}],
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        signals = json.loads(raw)
        signals = [s for s in signals if s.get("confidence", "").upper() in ("HIGH", "MEDIUM")]
        # Merge enrichment fields back from original stock data
        for s in signals:
            orig = stock_lookup.get(s["ticker"], {})
            for key in ("volume_ratio", "range_position", "relative_strength_vs_spy",
                        "earnings_within_7d", "earnings_date", "sentiment_score",
                        "trend_1d", "trend_1w", "trend_1m", "news"):
                s[key] = orig.get(key)
            # Build backward-compatible reason/risk from structured analysis
            analysis = s.get("analysis", {})
            if analysis:
                s["reason"] = f"{analysis.get('catalyst', '')} {analysis.get('technical_summary', '')}".strip()
                s["risk"] = analysis.get("headwinds", s.get("risk", ""))
        signals = apply_sector_cap(signals)
        print(f"Claude identified {len(signals)} buy signal(s).")
        return signals
    except json.JSONDecodeError as e:
        print(f"[!] Failed to parse Claude response: {e}")
        return []
