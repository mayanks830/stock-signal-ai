import re
import json
from datetime import datetime
from utils import fetch_with_retry

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "RSC": "1",
}


def fetch_congressional_trades(ticker: str | None = None, page_size: int = 50,
                               asset_type: str | None = None) -> list[dict]:
    """
    Fetch recent congressional stock trades from Capitol Trades.
    Uses the RSC (React Server Components) endpoint for structured data.
    If ticker is provided, fetches a larger set and filters locally.
    asset_type: server-side filter, e.g. 'stock', 'stock-options', 'etf', 'crypto'.
    """
    try:
        # Ticker filtering is client-side on Capitol Trades, so fetch more and filter
        fetch_size = page_size if not ticker else max(page_size, 100)
        url = f"https://www.capitoltrades.com/trades?pageSize={fetch_size}"
        if asset_type:
            url += f"&assetType={asset_type}"

        resp = fetch_with_retry(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"  [!] Capitol Trades returned {resp.status_code}")
            return []

        trades = _parse_rsc_trades(resp.text)

        if ticker:
            ticker_upper = ticker.upper()
            trades = [t for t in trades if t.get("ticker") == ticker_upper]

        return trades[:page_size]

    except Exception as e:
        print(f"  [!] Congressional trades failed: {e}")
        return []


def _parse_rsc_trades(text: str) -> list[dict]:
    """Extract trade data from RSC flight response."""
    trades = []

    # The RSC response contains "data":[{...},{...},...] with nested trade objects.
    # Find "data":[ and then use balanced-braces parsing to extract the array.
    for match in re.finditer(r'"data":\[', text):
        start = match.end() - 1  # position of the [
        arr_str = _extract_balanced_brackets(text, start)
        if arr_str:
            try:
                arr = json.loads(arr_str)
                if isinstance(arr, list):
                    for obj in arr:
                        if isinstance(obj, dict) and "txDate" in obj:
                            trade = _normalize_trade(obj)
                            if trade:
                                trades.append(trade)
            except json.JSONDecodeError:
                continue

    if trades:
        return trades

    # Fallback: find individual trade objects using balanced-braces parser
    for match in re.finditer(r'\{"_issuerId":\d+', text):
        obj_str = _extract_balanced_braces(text, match.start())
        if obj_str:
            try:
                obj = json.loads(obj_str)
                trade = _normalize_trade(obj)
                if trade:
                    trades.append(trade)
            except json.JSONDecodeError:
                continue

    return trades


def _extract_balanced_brackets(text: str, start: int) -> str | None:
    """Extract a complete JSON array with balanced brackets starting at position."""
    if start >= len(text) or text[start] != '[':
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, min(start + 100000, len(text))):
        c = text[i]
        if escape:
            escape = False
            continue
        if c == '\\' and in_string:
            escape = True
            continue
        if c == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == '[':
            depth += 1
        elif c == ']':
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def _extract_balanced_braces(text: str, start: int) -> str | None:
    """Extract a complete JSON object with balanced braces starting at position."""
    if start >= len(text) or text[start] != '{':
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, min(start + 5000, len(text))):
        c = text[i]
        if escape:
            escape = False
            continue
        if c == '\\' and in_string:
            escape = True
            continue
        if c == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def _normalize_trade(obj: dict) -> dict | None:
    """Normalize a Capitol Trades object into our standard format."""
    try:
        # Politician info (nested object with firstName, lastName, party, chamber)
        pol = obj.get("politician") or {}
        if isinstance(pol, dict):
            first = (pol.get("firstName") or "").strip()
            last = (pol.get("lastName") or "").strip()
            filer = f"{first} {last}".strip()
            party_raw = pol.get("party") or ""
            chamber_raw = pol.get("chamber") or obj.get("chamber") or ""
        else:
            filer = obj.get("politicianName") or obj.get("filer") or ""
            party_raw = obj.get("party") or ""
            chamber_raw = obj.get("chamber") or ""

        # Normalize party
        party_lower = party_raw.lower()
        if "democrat" in party_lower or party_lower.startswith("d"):
            party = "D"
        elif "republican" in party_lower or party_lower.startswith("r"):
            party = "R"
        elif "independent" in party_lower or party_lower.startswith("i"):
            party = "I"
        else:
            party = party_raw[:1].upper() if party_raw else "?"

        # Normalize chamber
        chamber_lower = chamber_raw.lower()
        if "senate" in chamber_lower:
            chamber = "Senate"
        elif "house" in chamber_lower:
            chamber = "House"
        else:
            chamber = chamber_raw.capitalize() if chamber_raw else ""

        # Issuer / ticker info (nested object)
        issuer = obj.get("issuer") or {}
        if isinstance(issuer, dict):
            raw_ticker = issuer.get("issuerTicker") or ""
            company = issuer.get("issuerName") or ""
        else:
            raw_ticker = obj.get("issuerTicker") or obj.get("ticker") or ""
            company = obj.get("issuerName") or obj.get("company") or ""

        # Clean ticker: "VZ:US" -> "VZ"
        ticker = raw_ticker.split(":")[0].upper() if raw_ticker else ""

        # Trade type
        tx_type = (obj.get("txType") or "").lower()
        if tx_type in ("buy", "purchase"):
            action = "BUY"
        elif tx_type in ("sell", "sale"):
            action = "SELL"
        elif "exchange" in tx_type:
            action = "EXCHANGE"
        elif "receive" in tx_type:
            action = "RECEIVE"
        else:
            action = tx_type.upper()[:10] if tx_type else "UNKNOWN"

        # Amount / value
        value = obj.get("value")
        value_numeric = None
        if isinstance(value, (int, float)) and value > 0:
            value_numeric = float(value)
            amount = f"${value:,.0f}"
        else:
            amount = str(obj.get("txAmount") or obj.get("amount") or "")

        # Dates
        tx_date = obj.get("txDate") or ""
        pub_date = obj.get("pubDate") or ""

        # Reporting gap (may be pre-calculated)
        reporting_gap = obj.get("reportingGap")
        if reporting_gap is None and tx_date and pub_date:
            try:
                tx_dt = datetime.fromisoformat(tx_date[:10])
                pub_dt = datetime.fromisoformat(pub_date[:10])
                reporting_gap = (pub_dt - tx_dt).days
            except (ValueError, TypeError):
                pass

        owner_raw = obj.get("owner") or ""
        owner = owner_raw.replace("-", " ").title() if owner_raw else ""

        if not filer and not ticker:
            return None

        return {
            "filer": filer,
            "party": party,
            "chamber": chamber,
            "ticker": ticker,
            "company": company,
            "action": action,
            "amount": amount,
            "tx_date": tx_date[:10] if tx_date else "",
            "pub_date": pub_date[:10] if pub_date else "",
            "reporting_gap": reporting_gap,
            "owner": owner,
            "value_numeric": value_numeric,
        }
    except Exception:
        return None


YAHOO_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://finance.yahoo.com",
}


def _yahoo_ticker(ticker: str) -> str:
    """Convert ticker to Yahoo Finance format (BRK/B → BRK-B)."""
    return ticker.replace("/", "-")


def _fetch_historical_price(ticker: str, date_str: str) -> float | None:
    """Fetch the closing price of a ticker on a specific date from Yahoo Finance."""
    try:
        yt = _yahoo_ticker(ticker)
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        # period1 = start of that day, period2 = next day (to get the close)
        p1 = int(dt.timestamp())
        p2 = p1 + 86400 * 3  # add 3 days buffer for weekends/holidays
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yt}?period1={p1}&period2={p2}&interval=1d"
        resp = fetch_with_retry(url, headers=YAHOO_HEADERS, timeout=10)
        if resp.status_code != 200:
            return None
        result = resp.json().get("chart", {}).get("result", [])
        if not result:
            return None
        closes = [c for c in result[0]["indicators"]["quote"][0].get("close", []) if c is not None]
        return round(closes[0], 2) if closes else None
    except Exception as e:
        print(f"  [!] Historical price fetch failed for {ticker} on {date_str}: {e}")
        return None


def _fetch_current_price(ticker: str) -> float | None:
    """Fetch the current price of a ticker from Yahoo Finance."""
    try:
        yt = _yahoo_ticker(ticker)
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yt}?range=1d&interval=1d"
        resp = fetch_with_retry(url, headers=YAHOO_HEADERS, timeout=10)
        if resp.status_code != 200:
            return None
        result = resp.json().get("chart", {}).get("result", [])
        if not result:
            return None
        closes = [c for c in result[0]["indicators"]["quote"][0].get("close", []) if c is not None]
        return round(closes[-1], 2) if closes else None
    except Exception:
        return None


def enrich_congress_trades() -> dict:
    """
    Scrape trades, store BUYs in DB, fetch prices, calculate returns.
    Returns summary stats.
    """
    import time as _time
    from database import (
        upsert_congress_trade, get_congress_trades_needing_prices,
        get_congress_tickers, update_congress_trade_entry_price,
        update_congress_current_prices,
    )

    print("[Congress Enrich] Fetching trades from Capitol Trades...")
    trades = fetch_congressional_trades(page_size=200, asset_type="stock")

    # Store BUY trades
    stored = 0
    for trade in trades:
        if trade.get("action") != "BUY":
            continue
        if not trade.get("ticker") or not trade.get("tx_date"):
            continue
        if upsert_congress_trade(trade):
            stored += 1

    print(f"[Congress Enrich] {stored} new BUY trades stored from {len(trades)} total.")

    # Fetch historical prices for trades missing them
    needs_price = get_congress_trades_needing_prices()
    print(f"[Congress Enrich] {len(needs_price)} trades need historical prices.")
    priced = 0
    for t in needs_price:
        price = _fetch_historical_price(t["ticker"], t["tx_date"])
        if price:
            update_congress_trade_entry_price(t["id"], price)
            priced += 1
        _time.sleep(0.3)  # Rate limit Yahoo

    print(f"[Congress Enrich] Fetched {priced}/{len(needs_price)} historical prices.")

    # Update current prices for all tickers
    tickers = get_congress_tickers()
    print(f"[Congress Enrich] Updating current prices for {len(tickers)} tickers...")
    updated = 0
    for ticker in tickers:
        price = _fetch_current_price(ticker)
        if price:
            update_congress_current_prices(ticker, price)
            updated += 1
        _time.sleep(0.3)

    print(f"[Congress Enrich] Updated {updated}/{len(tickers)} current prices.")

    return {"stored": stored, "priced": priced, "updated": updated}


def summarize_congressional_activity(trades: list[dict]) -> dict:
    """Summarize congressional trades into a signal (same pattern as insider activity)."""
    if not trades:
        return {"cong_buys": 0, "cong_sells": 0, "cong_signal": "NONE", "cong_trades": []}

    buys = [t for t in trades if t.get("action") == "BUY"]
    sells = [t for t in trades if t.get("action") == "SELL"]

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
        "cong_buys": len(buys),
        "cong_sells": len(sells),
        "cong_signal": signal,
        "cong_trades": trades[:5],
    }
