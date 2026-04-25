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
    has_news = []
    for i, stock in enumerate(top):
        print(f"  [{i+1}/{len(top)}] {stock['ticker']} news    ", end="\r")
        raw_news = fetch_news(stock["ticker"])
        if raw_news:
            stock["news"] = label_headlines(raw_news)
            stock["sentiment_score"] = score_headlines(raw_news)
            has_news.append(stock)
        time.sleep(0.4)

    print(f"\n{len(has_news)} stocks with news catalyst. Sending to AI.")
    return has_news


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
