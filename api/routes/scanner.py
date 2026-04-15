from fastapi import APIRouter, BackgroundTasks
from fetcher import get_sp500_tickers, fetch_candidates
from analyzer import analyze_stocks
from notifier import send_signals
from history import record_signals
from market_context import build_market_context

router = APIRouter()
_scan_running = False


def _do_scan():
    global _scan_running
    try:
        print("\n[Dashboard Scan Triggered]")
        tickers = get_sp500_tickers()
        market_context = build_market_context()
        candidates = fetch_candidates(tickers)
        if not candidates:
            send_signals([], market_context)
            return
        signals = analyze_stocks(candidates, market_context)
        send_signals(signals, market_context)
        if signals:
            record_signals(signals, market_context)
        print(f"[Dashboard Scan Complete] {len(signals)} signal(s) saved.")
    except Exception as e:
        print(f"[!] Scan error: {e}")
    finally:
        _scan_running = False


@router.post("/scan/trigger")
def trigger_scan(background_tasks: BackgroundTasks):
    global _scan_running
    if _scan_running:
        return {"status": "already_running"}
    _scan_running = True
    background_tasks.add_task(_do_scan)
    return {"status": "started"}


@router.get("/scan/status")
def scan_status():
    return {"running": _scan_running}
