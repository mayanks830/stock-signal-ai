"""Thin compatibility shim — delegates to database.py."""
from database import get_recent_signal_tickers, save_signal
from config import SIGNAL_COOLDOWN_DAYS


def was_recently_signaled(ticker: str) -> bool:
    return ticker in get_recent_signal_tickers(SIGNAL_COOLDOWN_DAYS)


def record_signals(signals: list[dict], market_context: dict = None) -> None:
    for s in signals:
        save_signal(s, market_context)
