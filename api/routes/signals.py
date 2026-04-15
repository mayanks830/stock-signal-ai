import json
import requests
from fastapi import APIRouter, HTTPException
from database import get_all_signals, get_signal_by_id, get_open_signals

router = APIRouter()

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Referer": "https://finance.yahoo.com",
}


@router.get("/signals")
def list_signals(limit: int = 50, offset: int = 0):
    signals = get_all_signals(limit, offset)
    for s in signals:
        if s.get("news_json"):
            try:
                s["news"] = json.loads(s["news_json"])
            except Exception:
                s["news"] = []
        del s["news_json"]
    return signals


@router.get("/signals/open")
def open_signals():
    signals = get_open_signals()
    for s in signals:
        if s.get("news_json"):
            try:
                s["news"] = json.loads(s["news_json"])
            except Exception:
                s["news"] = []
        s.pop("news_json", None)
    return signals


@router.get("/signals/{signal_id}")
def get_signal(signal_id: int):
    signal = get_signal_by_id(signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    if signal.get("news_json"):
        try:
            signal["news"] = json.loads(signal["news_json"])
        except Exception:
            signal["news"] = []
    del signal["news_json"]
    return signal


@router.get("/signals/{signal_id}/prices")
def signal_prices(signal_id: int):
    """Return 30-day price history for a signal's ticker (for sparkline charts)."""
    signal = get_signal_by_id(signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")

    ticker = signal["ticker"]
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=30d&interval=1d"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        result = resp.json().get("chart", {}).get("result", [])
        if not result:
            return {"prices": []}
        timestamps = result[0].get("timestamp", [])
        closes = result[0]["indicators"]["quote"][0].get("close", [])
        prices = [
            {"date": str(t)[:10] if t else "", "price": round(c, 2)}
            for t, c in zip(timestamps, closes)
            if c is not None
        ]
        return {"ticker": ticker, "prices": prices, "entry_price": signal["current_price"]}
    except Exception as e:
        return {"prices": [], "error": str(e)}
