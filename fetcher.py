import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from config import TOP_N_STOCKS, MIN_WOW_PCT, MIN_PRICE
from utils import fetch_with_retry
from history import was_recently_signaled
from earnings import get_earnings_dates
from sentiment import label_headlines, score_headlines
from technicals import get_technicals

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://finance.yahoo.com",
}

SECTOR_MAP = {
    "AAPL": "Technology", "MSFT": "Technology", "NVDA": "Technology", "AVGO": "Technology",
    "AMD": "Technology", "ADBE": "Technology", "INTU": "Technology", "QCOM": "Technology",
    "AMAT": "Technology", "LRCX": "Technology", "KLAC": "Technology", "PANW": "Technology",
    "SNPS": "Technology", "CDNS": "Technology", "MSI": "Technology", "APH": "Technology",
    "FICO": "Technology", "ROP": "Technology", "MCHP": "Technology", "ACN": "Technology",
    "CRM": "Technology", "TXN": "Technology", "ADI": "Technology", "IBM": "Technology",
    "AMZN": "Consumer Discretionary", "TSLA": "Consumer Discretionary", "HD": "Consumer Discretionary",
    "MCD": "Consumer Discretionary", "LOW": "Consumer Discretionary", "TGT": "Consumer Discretionary",
    "BKNG": "Consumer Discretionary", "ORLY": "Consumer Discretionary", "AZO": "Consumer Discretionary",
    "DHI": "Consumer Discretionary", "LEN": "Consumer Discretionary", "F": "Consumer Discretionary",
    "GM": "Consumer Discretionary", "DIS": "Consumer Discretionary", "UBER": "Consumer Discretionary",
    "GOOGL": "Communication", "META": "Communication", "NFLX": "Communication", "CSCO": "Communication",
    "JPM": "Financials", "BAC": "Financials", "GS": "Financials", "MS": "Financials",
    "WFC": "Financials", "C": "Financials", "BK": "Financials", "SCHW": "Financials",
    "AXP": "Financials", "COF": "Financials", "USB": "Financials", "PNC": "Financials",
    "TFC": "Financials", "MCO": "Financials", "SPGI": "Financials", "CB": "Financials",
    "MMC": "Financials", "CME": "Financials", "V": "Financials", "MA": "Financials",
    "UNH": "Healthcare", "JNJ": "Healthcare", "LLY": "Healthcare", "MRK": "Healthcare",
    "ABBV": "Healthcare", "TMO": "Healthcare", "ABT": "Healthcare", "DHR": "Healthcare",
    "ISRG": "Healthcare", "SYK": "Healthcare", "GILD": "Healthcare", "ELV": "Healthcare",
    "VRTX": "Healthcare", "REGN": "Healthcare", "BDX": "Healthcare", "BSX": "Healthcare",
    "EW": "Healthcare", "ZTS": "Healthcare", "HCA": "Healthcare", "CI": "Healthcare", "AMGN": "Healthcare",
    "XOM": "Energy", "CVX": "Energy", "COP": "Energy", "EOG": "Energy", "SLB": "Energy",
    "OXY": "Energy", "PSX": "Energy", "VLO": "Energy", "MPC": "Energy", "HAL": "Energy",
    "PG": "Consumer Staples", "KO": "Consumer Staples", "PEP": "Consumer Staples",
    "WMT": "Consumer Staples", "COST": "Consumer Staples", "MDLZ": "Consumer Staples",
    "CL": "Consumer Staples", "MO": "Consumer Staples", "PM": "Consumer Staples",
    "LIN": "Materials", "NUE": "Materials", "FCX": "Materials",
    "CAT": "Industrials", "GE": "Industrials", "HON": "Industrials", "RTX": "Industrials",
    "NOC": "Industrials", "GD": "Industrials", "MMM": "Industrials", "EMR": "Industrials",
    "ETN": "Industrials", "PH": "Industrials", "ITW": "Industrials", "WM": "Industrials",
    "PAYX": "Industrials", "CTAS": "Industrials", "ODFL": "Industrials", "DE": "Industrials",
    "NEE": "Utilities", "SO": "Utilities", "DUK": "Utilities",
    "PLD": "Real Estate", "WELL": "Real Estate", "SPG": "Real Estate", "AMT": "Real Estate",
    "FAST": "Industrials",
}

SP500_TICKERS = list(SECTOR_MAP.keys())

# Cache SPY WoW so we only fetch it once per scan
_spy_wow_cache: float | None = None


def get_spy_wow() -> float | None:
    global _spy_wow_cache
    if _spy_wow_cache is not None:
        return _spy_wow_cache
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/SPY?range=14d&interval=1d"
        resp = fetch_with_retry(url, headers=HEADERS, timeout=10)
        result = resp.json().get("chart", {}).get("result", [])
        closes = [c for c in result[0]["indicators"]["quote"][0].get("close", []) if c]
        if len(closes) >= 6:
            _spy_wow_cache = round((closes[-1] - closes[max(0, len(closes)-6)]) / closes[max(0, len(closes)-6)] * 100, 2)
    except Exception:
        pass
    return _spy_wow_cache


def get_sp500_tickers() -> list[str]:
    return SP500_TICKERS


def fetch_price_data(ticker: str) -> dict | None:
    """Fetch multi-timeframe price data from Yahoo Finance chart API."""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=30d&interval=1d"
        resp = fetch_with_retry(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return None

        result = resp.json().get("chart", {}).get("result", [])
        if not result:
            return None

        quote = result[0]["indicators"]["quote"][0]
        closes = [c for c in quote.get("close", []) if c is not None]
        volumes = [v for v in quote.get("volume", []) if v is not None]

        if len(closes) < 6:
            return None

        current = closes[-1]
        if current < MIN_PRICE:
            return None

        # WoW (~5 trading days)
        week_ago = closes[max(0, len(closes) - 6)]
        wow = ((current - week_ago) / week_ago) * 100

        # Multi-timeframe trends
        trend_1d = "up" if len(closes) >= 2 and closes[-1] > closes[-2] else "down"
        trend_1w = "up" if wow > 0 else "down"
        trend_1m = "up" if current > closes[0] else "down"

        # Volume ratio
        avg_vol = sum(volumes) / len(volumes) if volumes else 0
        vol_ratio = round(volumes[-1] / avg_vol, 2) if avg_vol > 0 and volumes else 1.0

        # Position within 30d range
        high_30, low_30 = max(closes), min(closes)
        range_pos = round((current - low_30) / (high_30 - low_30) * 100, 1) if high_30 != low_30 else 50.0

        return {
            "current_price": round(current, 2),
            "wow_change_pct": round(wow, 2),
            "volume_ratio": vol_ratio,
            "range_position": range_pos,
            "trend_1d": trend_1d,
            "trend_1w": trend_1w,
            "trend_1m": trend_1m,
        }
    except Exception as e:
        print(f"  [!] {ticker}: {e}")
        return None


def fetch_news(ticker: str) -> list[dict]:
    try:
        url = f"https://news.google.com/rss/search?q={ticker}+stock&hl=en-US&gl=US&ceid=US:en"
        resp = fetch_with_retry(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            return []

        root = ET.fromstring(resp.content)
        cutoff = datetime.now() - timedelta(days=7)
        items = []

        for item in root.findall(".//item")[:5]:
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            pub_date_str = item.findtext("pubDate", "")
            try:
                pub_dt = datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S %Z")
                if pub_dt >= cutoff:
                    items.append({"title": title, "link": link, "date": pub_dt.strftime("%Y-%m-%d")})
            except Exception:
                items.append({"title": title, "link": link, "date": "recent"})

        return items
    except Exception:
        return []


def fetch_candidates(tickers: list[str]) -> list[dict]:
    global _spy_wow_cache
    _spy_wow_cache = None  # reset cache each scan

    print(f"Fetching price data for {len(tickers)} tickers...")
    spy_wow = get_spy_wow()

    # Fetch earnings calendar once for all tickers
    print("  Fetching earnings calendar...")
    earnings_map = get_earnings_dates(tickers)
    print(f"  Found {len(earnings_map)} upcoming earnings in next 14 days.")

    candidates = []
    for i, ticker in enumerate(tickers):
        print(f"  [{i+1}/{len(tickers)}] {ticker}        ", end="\r")

        if was_recently_signaled(ticker):
            time.sleep(0.1)
            continue

        price_data = fetch_price_data(ticker)
        if not price_data:
            time.sleep(0.3)
            continue

        if abs(price_data["wow_change_pct"]) < MIN_WOW_PCT:
            time.sleep(0.3)
            continue

        # Relative strength vs SPY
        rs = round(price_data["wow_change_pct"] - spy_wow, 2) if spy_wow is not None else None

        earnings_date = earnings_map.get(ticker)

        candidates.append({
            "ticker": ticker,
            "sector": SECTOR_MAP.get(ticker, "Other"),
            "revenue": ">$1B",
            "current_price": price_data["current_price"],
            "wow_change_pct": price_data["wow_change_pct"],
            "volume_ratio": price_data["volume_ratio"],
            "range_position": price_data["range_position"],
            "trend_1d": price_data["trend_1d"],
            "trend_1w": price_data["trend_1w"],
            "trend_1m": price_data["trend_1m"],
            "relative_strength_vs_spy": rs,
            "earnings_within_7d": earnings_date is not None and (
                datetime.fromisoformat(earnings_date).date() - datetime.now().date()
            ).days <= 7,
            "earnings_date": earnings_date,
            "news": [],
        })
        time.sleep(0.3)

    print(f"\nFiltered to {len(candidates)} qualifying stocks.")
    candidates.sort(key=lambda x: x["wow_change_pct"], reverse=True)
    top = candidates[:TOP_N_STOCKS]

    # Fetch and score news
    print(f"Fetching news for {len(top)} stocks...")
    _enrich_news(top)

    news_count = sum(1 for s in top if s.get("news"))
    print(f"{news_count}/{len(top)} stocks with news. Sending all {len(top)} to AI.")
    return top


def _fetch_price_data_no_filter(ticker: str, range: str = "30d", interval: str = "1d") -> dict | None:
    """Fetch price data without MIN_PRICE or WoW filters."""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range={range}&interval={interval}"
        resp = fetch_with_retry(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return None

        result = resp.json().get("chart", {}).get("result", [])
        if not result:
            return None

        quote = result[0]["indicators"]["quote"][0]
        timestamps = result[0].get("timestamp", [])
        closes = [c for c in quote.get("close", []) if c is not None]
        volumes = [v for v in quote.get("volume", []) if v is not None]

        if len(closes) < 2:
            return None

        current = closes[-1]

        # Daily change
        daily_change = round((closes[-1] - closes[-2]) / closes[-2] * 100, 2) if len(closes) >= 2 else 0.0

        # WoW (~5 trading days)
        week_ago = closes[max(0, len(closes) - 6)] if len(closes) >= 6 else closes[0]
        wow = round((current - week_ago) / week_ago * 100, 2)

        # Multi-timeframe trends
        trend_1d = "up" if len(closes) >= 2 and closes[-1] > closes[-2] else "down"
        trend_1w = "up" if wow > 0 else "down"
        trend_1m = "up" if current > closes[0] else "down"

        # Volume ratio
        avg_vol = sum(volumes) / len(volumes) if volumes else 0
        vol_ratio = round(volumes[-1] / avg_vol, 2) if avg_vol > 0 and volumes else 1.0

        # Position within 30d range
        high_30, low_30 = max(closes), min(closes)
        range_pos = round((current - low_30) / (high_30 - low_30) * 100, 1) if high_30 != low_30 else 50.0

        # Build price history from timestamps + closes
        price_history = []
        # Filter aligned: only include entries where close is not None
        raw_closes = quote.get("close", [])
        for i, ts in enumerate(timestamps):
            if i < len(raw_closes) and raw_closes[i] is not None:
                from datetime import datetime as dt
                price_history.append({
                    "date": dt.utcfromtimestamp(ts).strftime("%Y-%m-%d"),
                    "close": round(raw_closes[i], 2),
                })

        return {
            "current_price": round(current, 2),
            "daily_change_pct": daily_change,
            "wow_change_pct": wow,
            "volume_ratio": vol_ratio,
            "range_position": range_pos,
            "trend_1d": trend_1d,
            "trend_1w": trend_1w,
            "trend_1m": trend_1m,
            "price_history": price_history,
        }
    except Exception as e:
        print(f"  [!] {ticker}: {e}")
        return None


def _build_candidate(ticker: str, price_data: dict, spy_wow: float | None,
                     earnings_map: dict) -> dict:
    """Build a standard candidate dict from price data."""
    rs = round(price_data["wow_change_pct"] - spy_wow, 2) if spy_wow is not None else None
    earnings_date = earnings_map.get(ticker)
    return {
        "ticker": ticker,
        "sector": SECTOR_MAP.get(ticker, "Other"),
        "revenue": ">$1B",
        "current_price": price_data["current_price"],
        "wow_change_pct": price_data["wow_change_pct"],
        "volume_ratio": price_data["volume_ratio"],
        "range_position": price_data["range_position"],
        "trend_1d": price_data["trend_1d"],
        "trend_1w": price_data["trend_1w"],
        "trend_1m": price_data["trend_1m"],
        "relative_strength_vs_spy": rs,
        "earnings_within_7d": earnings_date is not None and (
            datetime.fromisoformat(earnings_date).date() - datetime.now().date()
        ).days <= 7,
        "earnings_date": earnings_date,
        "news": [],
        "sentiment_score": 0.0,
    }


def _enrich_news(candidates: list[dict]) -> None:
    """Fetch and score news for a list of candidates in-place."""
    for i, stock in enumerate(candidates):
        print(f"  [{i+1}/{len(candidates)}] {stock['ticker']} news    ", end="\r")
        raw_news = fetch_news(stock["ticker"])
        alt_news = fetch_alt_news(stock["ticker"])
        combined = (raw_news or []) + (alt_news or [])
        if combined:
            stock["news"] = label_headlines(combined)
            stock["sentiment_score"] = score_headlines(combined)
        time.sleep(0.3)
    print()


def fetch_alt_news(ticker: str) -> list[dict]:
    """Fetch SEC EDGAR filings (8-K, SC 13D) for early/non-mainstream signals."""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        url = (
            f"https://efts.sec.gov/LATEST/search-index?"
            f"q=%22{ticker}%22&dateRange=custom&startdt={week_ago}&enddt={today}"
            f"&forms=8-K,SC%2013D,SC%2013G"
        )
        resp = fetch_with_retry(
            url, timeout=10,
            headers={"User-Agent": "StockSignalAI/1.0 contact@example.com", "Accept": "application/json"},
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        hits = data.get("hits", {}).get("hits", [])
        items = []
        for hit in hits[:3]:
            src = hit.get("_source", {})
            form_type = src.get("form") or src.get("file_type") or ""
            entity = src.get("display_names", [""])[0].split("(")[0].strip() if src.get("display_names") else ticker
            desc = src.get("file_description", "Filing")
            title = f"[SEC {form_type}] {entity}: {desc}"
            filed = src.get("file_date", "recent")
            items.append({"title": title, "link": "", "date": filed})
        return items
    except Exception:
        return []


def fetch_early_candidates(tickers: list[str], spy_wow: float | None,
                           earnings_map: dict) -> list[dict]:
    """
    Early signal pipeline: stocks with unusual volume but price hasn't moved yet.
    Catches accumulation before a breakout.
    """
    print("\n[Early Signals] Scanning for accumulation patterns...")
    candidates = []
    for ticker in tickers:
        if was_recently_signaled(ticker):
            continue
        price_data = fetch_price_data(ticker)
        if not price_data:
            time.sleep(0.3)
            continue
        wow = price_data["wow_change_pct"]
        vol = price_data["volume_ratio"]
        # Hasn't moved much but volume is elevated
        if -1.0 <= wow <= 1.5 and vol >= 1.1:
            candidates.append(_build_candidate(ticker, price_data, spy_wow, earnings_map))
        time.sleep(0.3)

    print(f"[Early Signals] {len(candidates)} stocks with unusual volume + flat price.")
    if candidates:
        candidates.sort(key=lambda x: x["volume_ratio"], reverse=True)
        top = candidates[:15]
        print(f"[Early Signals] Fetching news for top {len(top)}...")
        _enrich_news(top)
        # Only keep candidates that have news (something is brewing)
        top = [c for c in top if c.get("news")]
        print(f"[Early Signals] {len(top)} with news catalyst.")
        return top
    return []


def fetch_dip_candidates(tickers: list[str], spy_wow: float | None,
                         earnings_map: dict) -> list[dict]:
    """
    Buy-the-dip pipeline: strong stocks that dropped significantly.
    Catches overreactions and capitulation.
    """
    print("\n[Dip Signals] Scanning for oversold quality stocks...")
    candidates = []
    for ticker in tickers:
        if was_recently_signaled(ticker):
            continue
        price_data = fetch_price_data(ticker)
        if not price_data:
            time.sleep(0.3)
            continue
        wow = price_data["wow_change_pct"]
        range_pos = price_data["range_position"]
        vol = price_data["volume_ratio"]
        # Meaningful drop, near bottom of range
        if wow <= -2.0 and range_pos <= 40:
            candidates.append(_build_candidate(ticker, price_data, spy_wow, earnings_map))
        time.sleep(0.3)

    print(f"[Dip Signals] {len(candidates)} stocks with significant pullback.")
    if candidates:
        candidates.sort(key=lambda x: x["wow_change_pct"])  # most beaten down first
        top = candidates[:15]
        print(f"[Dip Signals] Fetching news for top {len(top)}...")
        _enrich_news(top)
        return top
    return []


def fetch_pullback_candidates(tickers: list[str], spy_wow: float | None,
                              earnings_map: dict) -> list[dict]:
    """
    Pullback entry pipeline: stocks in uptrend that pulled back to support.
    Better entry than chasing breakouts.
    """
    print("\n[Pullback Signals] Scanning for pullbacks in uptrends...")
    candidates = []
    for ticker in tickers:
        if was_recently_signaled(ticker):
            continue
        price_data = fetch_price_data(ticker)
        if not price_data:
            time.sleep(0.3)
            continue
        wow = price_data["wow_change_pct"]
        range_pos = price_data["range_position"]
        trend_1m = price_data["trend_1m"]
        # Uptrend (1m) but pulling back this week
        if trend_1m == "up" and -5.0 <= wow <= -1.0 and 20 <= range_pos <= 70:
            candidates.append(_build_candidate(ticker, price_data, spy_wow, earnings_map))
        time.sleep(0.3)

    print(f"[Pullback Signals] {len(candidates)} stocks pulling back in uptrends.")
    if candidates:
        candidates.sort(key=lambda x: x["wow_change_pct"])
        top = candidates[:15]
        print(f"[Pullback Signals] Fetching news for top {len(top)}...")
        _enrich_news(top)
        return top
    return []


def fetch_congress_frontrun_candidates(spy_wow: float | None,
                                       earnings_map: dict) -> list[dict]:
    """
    Congress front-running pipeline: politicians bought recently but price hasn't moved.
    Uses existing congress_trades DB data.
    """
    from database import get_conn
    print("\n[Congress Signals] Scanning for front-running opportunities...")

    # Get recent congress BUY trades from DB
    cutoff = (datetime.now() - timedelta(days=45)).strftime("%Y-%m-%d")
    try:
        with get_conn() as conn:
            rows = conn.execute("""
                SELECT DISTINCT ticker, filer, party, tx_date, value_numeric
                FROM congress_trades
                WHERE action = 'BUY' AND tx_date >= ?
                  AND (value_numeric IS NULL OR value_numeric >= 5000)
                ORDER BY tx_date DESC
            """, (cutoff,)).fetchall()
        trades = [dict(r) for r in rows]
    except Exception:
        trades = []

    if not trades:
        print("[Congress Signals] No recent congress BUY trades found.")
        return []

    # Group by ticker, get unique tickers
    ticker_trades: dict[str, list[dict]] = {}
    for t in trades:
        ticker_trades.setdefault(t["ticker"], []).append(t)

    print(f"[Congress Signals] {len(ticker_trades)} tickers with congress buys in last 45 days.")

    candidates = []
    for ticker, ctrades in ticker_trades.items():
        if was_recently_signaled(ticker):
            continue
        price_data = fetch_price_data(ticker)
        if not price_data:
            time.sleep(0.3)
            continue
        # Only signal if price hasn't run away yet (< +5% WoW)
        if price_data["wow_change_pct"] <= 5.0:
            cand = _build_candidate(ticker, price_data, spy_wow, earnings_map)
            # Attach congress trade info for the AI prompt
            cand["congress_trades"] = ctrades[:3]
            candidates.append(cand)
        time.sleep(0.3)

    print(f"[Congress Signals] {len(candidates)} tickers haven't run yet.")
    if candidates:
        top = candidates[:15]
        print(f"[Congress Signals] Fetching news for top {len(top)}...")
        _enrich_news(top)
        return top
    return []


def fetch_watchlist_data(tickers: list[str], include_technicals: bool = True) -> list[dict]:
    """
    Fetch data for watchlist tickers — NO filters applied.
    Every ticker is included regardless of price, WoW change, or news.
    """
    global _spy_wow_cache
    _spy_wow_cache = None
    spy_wow = get_spy_wow()

    print(f"Fetching watchlist data for {len(tickers)} tickers...")
    earnings_map = get_earnings_dates(tickers)
    print(f"  Found {len(earnings_map)} upcoming earnings in next 14 days.")

    results = []
    for i, ticker in enumerate(tickers):
        print(f"  [{i+1}/{len(tickers)}] {ticker}        ", end="\r")

        price_data = _fetch_price_data_no_filter(ticker)
        if not price_data:
            results.append({
                "ticker": ticker,
                "sector": SECTOR_MAP.get(ticker, "Other"),
                "current_price": None,
                "error": True,
            })
            time.sleep(0.3)
            continue

        rs = round(price_data["wow_change_pct"] - spy_wow, 2) if spy_wow is not None else None
        earnings_date = earnings_map.get(ticker)

        stock = {
            "ticker": ticker,
            "sector": SECTOR_MAP.get(ticker, "Other"),
            "current_price": price_data["current_price"],
            "daily_change_pct": price_data["daily_change_pct"],
            "wow_change_pct": price_data["wow_change_pct"],
            "volume_ratio": price_data["volume_ratio"],
            "range_position": price_data["range_position"],
            "trend_1d": price_data["trend_1d"],
            "trend_1w": price_data["trend_1w"],
            "trend_1m": price_data["trend_1m"],
            "relative_strength_vs_spy": rs,
            "earnings_within_7d": earnings_date is not None and (
                datetime.fromisoformat(earnings_date).date() - datetime.now().date()
            ).days <= 7,
            "earnings_date": earnings_date,
            "news": [],
            "sentiment_score": 0.0,
            "error": False,
        }

        # Technicals (RSI, MA, MACD)
        if include_technicals:
            tech = get_technicals(ticker)
            if tech:
                stock["rsi"] = tech["rsi"]
                stock["rsi_status"] = tech["rsi_status"]
                stock["ma50"] = tech["ma50"]
                stock["ma200"] = tech["ma200"]
                stock["above_50ma"] = tech["above_50ma"]
                stock["above_200ma"] = tech["above_200ma"]
                stock["ma_cross"] = tech["ma_cross"]
                stock["macd"] = tech["macd"]
                stock["trailing_returns"] = tech["trailing_returns"]

        results.append(stock)
        time.sleep(0.3)

    # Fetch news for all (best effort, no filtering)
    print(f"\nFetching news for {len(results)} watchlist stocks...")
    for i, stock in enumerate(results):
        if stock.get("error"):
            continue
        print(f"  [{i+1}/{len(results)}] {stock['ticker']} news    ", end="\r")
        raw_news = fetch_news(stock["ticker"])
        if raw_news:
            stock["news"] = label_headlines(raw_news)
            stock["sentiment_score"] = score_headlines(raw_news)
        time.sleep(0.4)

    valid = [s for s in results if not s.get("error")]
    print(f"\nWatchlist data fetched: {len(valid)}/{len(tickers)} tickers successful.")
    return results
