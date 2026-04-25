import time
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from utils import fetch_with_retry
from congress import fetch_congressional_trades, summarize_congressional_activity

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


# ── OpenInsider: Insider Trades ──────────────────────────────────────────────

def get_insider_trades(ticker: str, days: int = 30) -> list[dict]:
    """
    Fetch recent insider trades from OpenInsider.com.
    Returns list of trades with owner, title, trade_type, shares, value, date.
    """
    try:
        url = f"http://openinsider.com/screener?s={ticker}&o=&pl=&ph=&st=0&tdlt={days}&tdr=&tdrd=&in=&ic=&idr=&ipp=20&isfr=1"
        resp = fetch_with_retry(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        table = soup.find("table", class_="tinytable")
        if not table:
            return []

        trades = []
        rows = table.find_all("tr")[1:]  # Skip header
        for row in rows[:10]:  # Max 10 recent trades
            cols = row.find_all("td")
            if len(cols) < 13:
                continue

            trade_date = cols[1].get_text(strip=True)
            owner = cols[4].get_text(strip=True)
            title = cols[5].get_text(strip=True)
            trade_type = cols[6].get_text(strip=True)  # "P - Purchase" or "S - Sale"
            shares = cols[8].get_text(strip=True)
            value = cols[10].get_text(strip=True)

            # Classify trade
            if "P" in trade_type.upper().split("-")[0]:
                action = "BUY"
            elif "S" in trade_type.upper().split("-")[0]:
                action = "SELL"
            else:
                action = "OTHER"

            trades.append({
                "date": trade_date,
                "owner": owner[:30],
                "title": title[:20],
                "action": action,
                "shares": shares,
                "value": value,
            })

        return trades
    except Exception as e:
        print(f"  [!] Insider trades failed for {ticker}: {e}")
        return []


def summarize_insider_activity(trades: list[dict]) -> dict:
    """Summarize insider trades into a signal."""
    if not trades:
        return {"insider_buys": 0, "insider_sells": 0, "insider_signal": "NONE", "insider_trades": []}

    buys = [t for t in trades if t["action"] == "BUY"]
    sells = [t for t in trades if t["action"] == "SELL"]

    if len(buys) >= 2 and len(buys) > len(sells):
        signal = "STRONG_BUY"
    elif len(buys) > 0 and len(buys) >= len(sells):
        signal = "NET_BUY"
    elif len(sells) >= 3 and len(sells) > len(buys) * 2:
        signal = "HEAVY_SELL"
    elif len(sells) > len(buys):
        signal = "NET_SELL"
    else:
        signal = "MIXED"

    return {
        "insider_buys": len(buys),
        "insider_sells": len(sells),
        "insider_signal": signal,
        "insider_trades": trades[:5],  # Keep top 5 for display
    }


# ── StockTwits: Social Sentiment ────────────────────────────────────────────

def get_stocktwits_sentiment(ticker: str) -> dict:
    """
    Fetch sentiment from StockTwits API (free, no key required).
    Returns bullish/bearish counts and overall sentiment label.
    """
    try:
        url = f"https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"
        resp = fetch_with_retry(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            print(f"  [!] StockTwits returned HTTP {resp.status_code} for {ticker}")
            return {"st_sentiment": "UNKNOWN", "st_bullish": 0, "st_bearish": 0, "st_volume": 0}

        data = resp.json()
        messages = data.get("messages", [])

        bullish = 0
        bearish = 0
        for msg in messages:
            sentiment = msg.get("entities", {}).get("sentiment")
            if sentiment:
                if sentiment.get("basic") == "Bullish":
                    bullish += 1
                elif sentiment.get("basic") == "Bearish":
                    bearish += 1

        total = bullish + bearish
        if total == 0:
            label = "UNKNOWN"
        elif bullish / total >= 0.7:
            label = "VERY_BULLISH"
        elif bullish / total >= 0.55:
            label = "BULLISH"
        elif bearish / total >= 0.7:
            label = "VERY_BEARISH"
        elif bearish / total >= 0.55:
            label = "BEARISH"
        else:
            label = "MIXED"

        return {
            "st_sentiment": label,
            "st_bullish": bullish,
            "st_bearish": bearish,
            "st_volume": len(messages),
        }
    except Exception as e:
        print(f"  [!] StockTwits failed for {ticker}: {e}")
        return {"st_sentiment": "UNKNOWN", "st_bullish": 0, "st_bearish": 0, "st_volume": 0}


# ── Combined enrichment ─────────────────────────────────────────────────────

def get_social_data(ticker: str) -> dict:
    """Get both insider trades and StockTwits sentiment for a ticker."""
    trades = get_insider_trades(ticker)
    insider = summarize_insider_activity(trades)

    time.sleep(0.3)

    st = get_stocktwits_sentiment(ticker)

    time.sleep(0.3)

    cong_trades = fetch_congressional_trades(ticker)
    cong = summarize_congressional_activity(cong_trades)

    return {**insider, **st, **cong}


def enrich_with_social_data(stocks: list[dict]) -> None:
    """Enrich a list of stock dicts in-place with social/insider data."""
    for i, stock in enumerate(stocks):
        if stock.get("error"):
            continue
        ticker = stock["ticker"]
        print(f"  [{i+1}/{len(stocks)}] {ticker} social data    ", end="\r")
        data = get_social_data(ticker)
        stock.update(data)
        time.sleep(0.5)
    print(f"\nSocial data enriched for {len([s for s in stocks if not s.get('error')])} stocks.")
