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

For each BUY:
- ticker, name, sector, confidence (HIGH or MEDIUM only)
- reason: 2-3 sentences, reference specific news catalyst and data
- risk: main downside
- price_target: +10-20% realistic target
- stop_loss: -5 to -8% below current price
- wow_change_pct, current_price (copy from data)

Respond ONLY with valid JSON array:
[
  {{
    "ticker": "MS",
    "name": "Morgan Stanley",
    "sector": "Financials",
    "confidence": "HIGH",
    "reason": "Beat Q1 earnings with trading revenue $1B above estimates. Volume at 2.1x avg confirms institutional buying. All 3 trend arrows up with +6% outperformance vs SPY.",
    "risk": "Trading revenue volatility may not sustain.",
    "price_target": 210.00,
    "stop_loss": 177.00,
    "wow_change_pct": 9.06,
    "current_price": 191.96
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


def analyze_stocks(stocks: list[dict], market_context: dict) -> list[dict]:
    if not stocks:
        return []

    print(f"Sending {len(stocks)} stocks to Claude for analysis...")
    stock_lookup = {s["ticker"]: s for s in stocks}

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4096,
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
        signals = apply_sector_cap(signals)
        print(f"Claude identified {len(signals)} buy signal(s).")
        return signals
    except json.JSONDecodeError as e:
        print(f"[!] Failed to parse Claude response: {e}")
        return []
