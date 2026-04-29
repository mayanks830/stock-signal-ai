from fastapi import APIRouter, BackgroundTasks
from fetcher import get_sp500_tickers, fetch_candidates, fetch_watchlist_data
from analyzer import analyze_stocks, analyze_watchlist
from notifier import send_signals, send_watchlist_report
from history import record_signals
from market_context import build_market_context
from database import get_all_signals, get_watchlist
from report import generate_watchlist_pdf

router = APIRouter()
_scan_running = False
_scan_status = {"step": "", "error": "", "signals_found": 0}

_watchlist_scan_running = False
_watchlist_scan_status = {"step": "", "error": ""}


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


def _do_watchlist_scan():
    global _watchlist_scan_running, _watchlist_scan_status
    try:
        _watchlist_scan_status = {"step": "Fetching market context...", "error": ""}
        market_context = build_market_context()

        equity_tickers = [w["ticker"] for w in get_watchlist("equity")]
        etf_tickers = [w["ticker"] for w in get_watchlist("etf")]

        _watchlist_scan_status["step"] = f"Fetching equity data ({len(equity_tickers)} tickers)..."
        equities = fetch_watchlist_data(equity_tickers, include_technicals=True)

        _watchlist_scan_status["step"] = f"Fetching ETF data ({len(etf_tickers)} tickers)..."
        etfs = fetch_watchlist_data(etf_tickers, include_technicals=False)

        _watchlist_scan_status["step"] = "Running AI analysis on watchlist..."
        try:
            analyses = analyze_watchlist(equities, market_context)
        except Exception as e:
            print(f"  [!] AI analysis failed: {e}")
            analyses = []

        _watchlist_scan_status["step"] = "Fetching social data..."
        try:
            from social import enrich_with_social_data
            enrich_with_social_data(equities)
        except Exception as e:
            print(f"  [!] Social data failed: {e}")

        _watchlist_scan_status["step"] = "Generating PDF report..."
        pdf_path = generate_watchlist_pdf(equities, etfs, market_context, analyses)

        _watchlist_scan_status["step"] = "Sending report to Discord..."
        send_watchlist_report(pdf_path, equities, analyses)

        _watchlist_scan_status["step"] = "Sending email..."
        try:
            from emailer import send_report_email
            send_report_email(pdf_path, equities, analyses)
        except Exception as e:
            print(f"  [!] Email failed: {e}")

        _watchlist_scan_status["step"] = "Done! Report generated."
        print(f"[Watchlist Scan Complete] Report: {pdf_path}", flush=True)
    except Exception as e:
        _watchlist_scan_status["step"] = "Error"
        _watchlist_scan_status["error"] = str(e)
        print(f"[!] Watchlist scan error: {e}", flush=True)
        import traceback
        traceback.print_exc()
    finally:
        _watchlist_scan_running = False


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


@router.post("/scan/watchlist")
def trigger_watchlist_scan(background_tasks: BackgroundTasks):
    global _watchlist_scan_running
    if _watchlist_scan_running:
        return {"status": "already_running", **_watchlist_scan_status}
    _watchlist_scan_running = True
    background_tasks.add_task(_do_watchlist_scan)
    return {"status": "started"}


@router.get("/scan/watchlist/status")
def watchlist_scan_status():
    return {"running": _watchlist_scan_running, **_watchlist_scan_status}


@router.get("/stats")
def stats():
    signals = get_all_signals(limit=1000)
    return {
        "total_signals": len(signals),
        "latest": signals[0]["signaled_at"] if signals else None,
    }
