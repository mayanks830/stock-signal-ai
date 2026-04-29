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


def _parse_signal_json(s: dict) -> None:
    """Parse news_json and analysis_json into proper objects."""
    if s.get("news_json"):
        try:
            s["news"] = json.loads(s["news_json"])
        except Exception:
            s["news"] = []
    s.pop("news_json", None)
    if s.get("analysis_json"):
        try:
            s["analysis"] = json.loads(s["analysis_json"])
        except Exception:
            s["analysis"] = None
    s.pop("analysis_json", None)


@router.get("/signals")
def list_signals(limit: int = 50, offset: int = 0):
    signals = get_all_signals(limit, offset)
    for s in signals:
        _parse_signal_json(s)
    return signals


@router.get("/signals/open")
def open_signals():
    signals = get_open_signals()
    for s in signals:
        _parse_signal_json(s)
    return signals


@router.get("/signals/{signal_id}")
def get_signal(signal_id: int):
    signal = get_signal_by_id(signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    _parse_signal_json(signal)
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
