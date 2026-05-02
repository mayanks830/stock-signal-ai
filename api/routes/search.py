import json
import time
from fastapi import APIRouter, HTTPException, Query

from fetcher import _fetch_price_data_no_filter, fetch_news, SECTOR_MAP
from sentiment import label_headlines
from technicals import get_technicals
from social import get_social_data
from market_context import build_market_context, format_for_prompt
from analyzer import client

router = APIRouter()

# ── Ticker ↔ Company Name mapping ────────────────────────────────────────────
TICKER_TO_NAME: dict[str, str] = {
    "AAPL": "Apple", "MSFT": "Microsoft", "NVDA": "NVIDIA", "AVGO": "Broadcom",
    "AMD": "AMD", "ADBE": "Adobe", "INTU": "Intuit", "QCOM": "Qualcomm",
    "AMAT": "Applied Materials", "LRCX": "Lam Research", "KLAC": "KLA Corp",
    "PANW": "Palo Alto Networks", "SNPS": "Synopsys", "CDNS": "Cadence",
    "MSI": "Motorola Solutions", "APH": "Amphenol", "FICO": "Fair Isaac",
    "ROP": "Roper Technologies", "MCHP": "Microchip Technology", "ACN": "Accenture",
    "CRM": "Salesforce", "TXN": "Texas Instruments", "ADI": "Analog Devices",
    "IBM": "IBM", "AMZN": "Amazon", "TSLA": "Tesla", "HD": "Home Depot",
    "MCD": "McDonald's", "LOW": "Lowe's", "TGT": "Target",
    "BKNG": "Booking Holdings", "ORLY": "O'Reilly Auto", "AZO": "AutoZone",
    "DHI": "D.R. Horton", "LEN": "Lennar", "F": "Ford", "GM": "General Motors",
    "DIS": "Disney", "UBER": "Uber", "GOOGL": "Alphabet/Google",
    "META": "Meta/Facebook", "NFLX": "Netflix", "CSCO": "Cisco",
    "JPM": "JPMorgan Chase", "BAC": "Bank of America", "GS": "Goldman Sachs",
    "MS": "Morgan Stanley", "WFC": "Wells Fargo", "C": "Citigroup",
    "BK": "Bank of New York Mellon", "SCHW": "Charles Schwab", "AXP": "American Express",
    "COF": "Capital One", "USB": "U.S. Bancorp", "PNC": "PNC Financial",
    "TFC": "Truist Financial", "MCO": "Moody's", "SPGI": "S&P Global",
    "CB": "Chubb", "MMC": "Marsh McLennan", "CME": "CME Group",
    "V": "Visa", "MA": "Mastercard",
    "UNH": "UnitedHealth", "JNJ": "Johnson & Johnson", "LLY": "Eli Lilly",
    "MRK": "Merck", "ABBV": "AbbVie", "TMO": "Thermo Fisher", "ABT": "Abbott",
    "DHR": "Danaher", "ISRG": "Intuitive Surgical", "SYK": "Stryker",
    "GILD": "Gilead Sciences", "ELV": "Elevance Health", "VRTX": "Vertex Pharma",
    "REGN": "Regeneron", "BDX": "Becton Dickinson", "BSX": "Boston Scientific",
    "EW": "Edwards Lifesciences", "ZTS": "Zoetis", "HCA": "HCA Healthcare",
    "CI": "Cigna", "AMGN": "Amgen",
    "XOM": "ExxonMobil", "CVX": "Chevron", "COP": "ConocoPhillips",
    "EOG": "EOG Resources", "SLB": "Schlumberger", "OXY": "Occidental Petroleum",
    "PSX": "Phillips 66", "VLO": "Valero Energy", "MPC": "Marathon Petroleum",
    "HAL": "Halliburton",
    "PG": "Procter & Gamble", "KO": "Coca-Cola", "PEP": "PepsiCo",
    "WMT": "Walmart", "COST": "Costco", "MDLZ": "Mondelez",
    "CL": "Colgate-Palmolive", "MO": "Altria", "PM": "Philip Morris",
    "LIN": "Linde", "NUE": "Nucor", "FCX": "Freeport-McMoRan",
    "CAT": "Caterpillar", "GE": "GE Aerospace", "HON": "Honeywell",
    "RTX": "RTX/Raytheon", "NOC": "Northrop Grumman", "GD": "General Dynamics",
    "MMM": "3M", "EMR": "Emerson Electric", "ETN": "Eaton",
    "PH": "Parker Hannifin", "ITW": "Illinois Tool Works", "WM": "Waste Management",
    "PAYX": "Paychex", "CTAS": "Cintas", "ODFL": "Old Dominion Freight",
    "DE": "John Deere", "FAST": "Fastenal",
    "NEE": "NextEra Energy", "SO": "Southern Company", "DUK": "Duke Energy",
    "PLD": "Prologis", "WELL": "Welltower", "SPG": "Simon Property",
    "AMT": "American Tower",
}


@router.get("/search/autocomplete")
def autocomplete(query: str = Query(..., min_length=1, max_length=50)):
    """Return matching tickers for a search query (by ticker or company name)."""
    q = query.strip().lower()
    results = []

    for ticker, name in TICKER_TO_NAME.items():
        ticker_lower = ticker.lower()
        name_lower = name.lower()

        # Exact ticker match = highest priority
        if ticker_lower == q:
            results.insert(0, {"ticker": ticker, "name": name, "sector": SECTOR_MAP.get(ticker, "Other")})
        # Ticker starts with query
        elif ticker_lower.startswith(q):
            results.append({"ticker": ticker, "name": name, "sector": SECTOR_MAP.get(ticker, "Other")})
        # Name contains query
        elif q in name_lower:
            results.append({"ticker": ticker, "name": name, "sector": SECTOR_MAP.get(ticker, "Other")})

    return results[:10]

# ── In-memory caches ─────────────────────────────────────────────────────────
_search_cache: dict[str, tuple[float, dict]] = {}  # ticker → (timestamp, result)
_SEARCH_TTL = 300  # 5 minutes

_market_ctx_cache: tuple[float, dict] | None = None
_MARKET_CTX_TTL = 600  # 10 minutes


def _get_cached_market_ctx() -> dict:
    global _market_ctx_cache
    now = time.time()
    if _market_ctx_cache and now - _market_ctx_cache[0] < _MARKET_CTX_TTL:
        return _market_ctx_cache[1]
    ctx = build_market_context()
    _market_ctx_cache = (now, ctx)
    return ctx


def _resolve_ticker(query: str) -> str | None:
    """Resolve a company name or ticker input to a valid ticker symbol."""
    q = query.upper().strip()
    # Already a known ticker
    if q in TICKER_TO_NAME:
        return q

    # Try matching by company name (case-insensitive)
    q_lower = query.lower().strip()
    best = None
    for ticker, name in TICKER_TO_NAME.items():
        if name.lower() == q_lower:
            return ticker  # Exact name match
        if q_lower in name.lower() and best is None:
            best = ticker  # First partial match
    return best


def _evict_stale():
    now = time.time()
    stale = [k for k, (ts, _) in _search_cache.items() if now - ts >= _SEARCH_TTL]
    for k in stale:
        del _search_cache[k]


def _build_single_stock_prompt(ticker: str, price_data: dict, technicals: dict | None,
                                news: list[dict], social: dict, market_ctx: dict) -> str:
    market_block = format_for_prompt(market_ctx)

    # Price section
    price_lines = (
        f"Price: ${price_data['current_price']} | "
        f"Daily: {price_data['daily_change_pct']:+.2f}% | "
        f"WoW: {price_data['wow_change_pct']:+.2f}% | "
        f"Volume: {price_data['volume_ratio']}x avg | "
        f"30d Range Position: {price_data['range_position']}% | "
        f"Trends: 1d:{price_data['trend_1d']} 1w:{price_data['trend_1w']} 1m:{price_data['trend_1m']}"
    )

    # Technicals
    tech_lines = "Technicals: N/A"
    if technicals:
        parts = []
        if technicals.get("rsi") is not None:
            parts.append(f"RSI: {technicals['rsi']:.1f} ({technicals.get('rsi_status', '')})")
        if technicals.get("ma50") is not None:
            parts.append(f"50-day MA: ${technicals['ma50']} ({'above' if technicals.get('above_50ma') else 'below'})")
        if technicals.get("ma200") is not None:
            parts.append(f"200-day MA: ${technicals['ma200']} ({'above' if technicals.get('above_200ma') else 'below'})")
        if technicals.get("ma_cross"):
            parts.append(f"MA Cross: {technicals['ma_cross']}")
        macd = technicals.get("macd")
        if macd:
            parts.append(f"MACD: {macd['crossover']} (hist: {macd['histogram']:+.4f})")
        if technicals.get("trailing_returns"):
            ret = technicals["trailing_returns"]
            ret_parts = [f"{k}: {v:+.2f}%" for k, v in ret.items()]
            parts.append(f"Returns: {', '.join(ret_parts)}")
        tech_lines = "Technicals: " + " | ".join(parts)

    # News
    news_lines = "News: None"
    if news:
        items = [f"[{n.get('sentiment', 'NEUTRAL')}] {n['title']}" for n in news[:5]]
        news_lines = "News:\n" + "\n".join(f"  - {item}" for item in items)

    # Social
    social_parts = []
    if social.get("insider_signal", "NONE") != "NONE":
        social_parts.append(
            f"Insider: {social['insider_signal']} "
            f"(Buys: {social.get('insider_buys', 0)}, Sells: {social.get('insider_sells', 0)})"
        )
    if social.get("st_sentiment", "UNKNOWN") != "UNKNOWN":
        social_parts.append(
            f"StockTwits: {social['st_sentiment']} "
            f"(Bull: {social.get('st_bullish', 0)}, Bear: {social.get('st_bearish', 0)})"
        )
    if social.get("cong_signal", "NONE") != "NONE":
        cong_detail = f"Congress: {social['cong_signal']} (Buys: {social.get('cong_buys', 0)}, Sells: {social.get('cong_sells', 0)})"
        recent_cong = social.get("cong_trades", [])
        if recent_cong:
            names = [f"{t.get('filer','')} ({t.get('party','')}) {t.get('action','')} on {t.get('tx_date','')}" for t in recent_cong[:3]]
            cong_detail += " — [recent: " + "; ".join(names) + "]"
        social_parts.append(cong_detail)

    social_lines = "Social: " + (" | ".join(social_parts) if social_parts else "No data")

    return f"""{market_block}

You are a senior quantitative analyst. Provide an honest, comprehensive analysis for {ticker}.

DATA:
{price_lines}
{tech_lines}
{news_lines}
{social_lines}

ANALYSIS RULES:
1. Signal must be BUY, SELL, HOLD, or CONFLICTED
   - Use CONFLICTED when technicals and sentiment/fundamentals disagree
2. Confidence must be 1-10 (integer)
   - 1-3: Speculative  |  4-6: Moderate  |  7-8: Strong  |  9-10: Very strong (cite 2+ sources)
3. You MUST list data_gaps — what information you don't have
4. Surface conflicts explicitly when data disagrees

Respond ONLY with valid JSON (no markdown, no code blocks):
{{
  "signal": "BUY|SELL|HOLD|CONFLICTED",
  "confidence": 7,
  "price_target": 0.00,
  "stop_loss": 0.00,
  "key_levels": {{"support": 0.00, "resistance": 0.00}},
  "technicals": {{
    "summary": "1-2 sentence technical picture",
    "indicators": ["RSI 65", "MACD bullish"]
  }},
  "sentiment": {{
    "summary": "1-2 sentence sentiment read",
    "sources": ["News", "Volume"]
  }},
  "conflicts": ["list any conflicts"],
  "data_gaps": ["list what data is missing"],
  "analysis": {{
    "business_model": "1-2 sentences",
    "financial_health": "1-2 sentences",
    "competitive_position": "1-2 sentences",
    "catalyst": "specific event or 'No specific catalyst'",
    "headwinds": "1-2 sentences",
    "valuation": "1-2 sentences",
    "technical_summary": "1-2 sentences",
    "bull_case": "2-3 sentences",
    "bear_case": "2-3 sentences",
    "recommendation": "2-3 sentences with price levels"
  }}
}}
"""


@router.get("/search")
def search_stock(
    ticker: str = Query(..., min_length=1, max_length=50),
    nocache: bool = Query(False),
):
    """Run full analysis for a single ticker or company name."""
    ticker = ticker.strip()[:50]

    # Try to resolve company name → ticker if input doesn't look like a ticker
    resolved = _resolve_ticker(ticker)
    if resolved:
        ticker = resolved
    else:
        ticker = ticker.upper()

    # Evict stale cache entries
    _evict_stale()

    # Return cached result if available
    if not nocache and ticker in _search_cache:
        ts, cached_result = _search_cache[ticker]
        if time.time() - ts < _SEARCH_TTL:
            return {**cached_result, "cached": True}

    # Fetch all data
    price_data = _fetch_price_data_no_filter(ticker)
    if not price_data:
        raise HTTPException(status_code=404, detail=f"Could not fetch price data for {ticker}")

    technicals = get_technicals(ticker)

    raw_news = fetch_news(ticker)
    news = label_headlines(raw_news) if raw_news else []

    social = get_social_data(ticker)

    market_ctx = _get_cached_market_ctx()

    # AI analysis
    prompt = _build_single_stock_prompt(ticker, price_data, technicals, news, social, market_ctx)
    try:
        message = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        ai_analysis = json.loads(raw)
        # If the model put analysis fields at root level instead of nested, wrap them
        if "analysis" not in ai_analysis and "bull_case" in ai_analysis:
            nested_keys = ["business_model", "financial_health", "competitive_position",
                           "catalyst", "headwinds", "valuation", "technical_summary",
                           "bull_case", "bear_case", "recommendation"]
            ai_analysis["analysis"] = {k: ai_analysis.pop(k) for k in nested_keys if k in ai_analysis}
        print(f"[Search] AI analysis keys: {list(ai_analysis.keys())}")
    except Exception as e:
        ai_analysis = {"outlook": "UNKNOWN", "signal": "HOLD", "reasoning": f"AI analysis failed: {e}"}

    result = {
        "ticker": ticker,
        "price_data": price_data,
        "technicals": technicals,
        "news": news,
        "social": social,
        "market_context": {
            "vix": market_ctx.get("vix"),
            "vix_label": market_ctx.get("vix_label"),
            "spy_wow_pct": market_ctx.get("spy_wow_pct"),
        },
        "ai_analysis": ai_analysis,
    }

    # Cache the result
    _search_cache[ticker] = (time.time(), result)

    return {**result, "cached": False}


# Yahoo Finance range → interval mapping
_RANGE_INTERVALS = {
    "1mo": "1d",
    "3mo": "1d",
    "6mo": "1d",
    "1y": "1wk",
    "2y": "1wk",
    "5y": "1mo",
}


@router.get("/price-history")
def get_price_history(
    ticker: str = Query(..., min_length=1, max_length=50),
    range: str = Query("1mo"),
):
    """Fetch price history for a ticker at a given range (1mo, 3mo, 6mo, 1y, 2y, 5y)."""
    ticker = ticker.upper().strip()
    if range not in _RANGE_INTERVALS:
        raise HTTPException(status_code=400, detail=f"Invalid range. Use: {', '.join(_RANGE_INTERVALS)}")
    interval = _RANGE_INTERVALS[range]
    data = _fetch_price_data_no_filter(ticker, range=range, interval=interval)
    if not data:
        raise HTTPException(status_code=404, detail=f"No price data for {ticker}")
    return {"ticker": ticker, "range": range, "price_history": data.get("price_history", [])}
