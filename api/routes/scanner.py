from fastapi import APIRouter, BackgroundTasks
from fetcher import get_sp500_tickers, fetch_candidates
from analyzer import analyze_stocks
from notifier import send_signals
from history import record_signals
from market_context import build_market_context
from database import get_all_signals

router = APIRouter()
_scan_running = False
_scan_status = {"step": "", "error": "", "signals_found": 0}


def _do_scan():
    global _scan_running, _scan_status
    try:
        _scan_status = {"step": "Fetching S&P 500 tickers...", "error": "", "signals_found": 0}
        tickers = get_sp500_tickers()

        _scan_status["step"] = "Building market context..."
        market_context = build_market_context()

        _scan_status["step"] = f"Fetching price data for {len(tickers)} stocks..."
        candidates = fetch_candidates(tickers)
        if not candidates:
            _scan_status["step"] = "No candidates found. Scan complete."
            return

        _scan_status["step"] = f"Running AI analysis on {len(candidates)} candidates..."
        signals = analyze_stocks(candidates, market_context)

        _scan_status["step"] = "Sending signals to Discord..."
        send_signals(signals, market_context)

        if signals:
            record_signals(signals, market_context)

        _scan_status["step"] = f"Done! {len(signals)} signal(s) generated."
        _scan_status["signals_found"] = len(signals)
        print(f"[Scan Complete] {len(signals)} signal(s) saved.", flush=True)
    except Exception as e:
        _scan_status["step"] = "Error"
        _scan_status["error"] = str(e)
        print(f"[!] Scan error: {e}", flush=True)
        import traceback
        traceback.print_exc()
    finally:
        _scan_running = False


@router.post("/scan/trigger")
def trigger_scan(background_tasks: BackgroundTasks):
    global _scan_running
    if _scan_running:
        return {"status": "already_running", **_scan_status}
    _scan_running = True
    background_tasks.add_task(_do_scan)
    return {"status": "started"}


@router.get("/scan/status")
def scan_status():
    return {"running": _scan_running, **_scan_status}


@router.get("/stats")
def stats():
    signals = get_all_signals(limit=1000)
    return {
        "total_signals": len(signals),
        "latest": signals[0]["signaled_at"] if signals else None,
    }
