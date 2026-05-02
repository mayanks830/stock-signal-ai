from fastapi import APIRouter, BackgroundTasks
from fetcher import (
    get_sp500_tickers, fetch_candidates, fetch_watchlist_data,
    fetch_early_candidates, fetch_dip_candidates, fetch_pullback_candidates,
    fetch_congress_frontrun_candidates, get_spy_wow,
)
from analyzer import run_full_analysis, analyze_watchlist
from notifier import send_signals, send_watchlist_report
from history import record_signals
from market_context import build_market_context
from database import get_all_signals, get_watchlist
from report import generate_watchlist_pdf
from earnings import get_earnings_dates

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
        spy_wow = get_spy_wow()
        earnings_map = get_earnings_dates(tickers)

        # Collect ALL candidates from all 5 pipelines
        all_candidates = []

        _scan_status["step"] = "Collecting candidates: Momentum..."
        try:
            momentum = fetch_candidates(tickers)
            for s in momentum:
                s["signal_type"] = "MOMENTUM"
            all_candidates.extend(momentum)
        except Exception as e:
            print(f"[!] Momentum fetch: {e}", flush=True)

        _scan_status["step"] = "Collecting candidates: Early signals..."
        try:
            early = fetch_early_candidates(tickers, spy_wow, earnings_map)
            for s in early:
                s["signal_type"] = "EARLY"
            all_candidates.extend(early)
        except Exception as e:
            print(f"[!] Early fetch: {e}", flush=True)

        _scan_status["step"] = "Collecting candidates: Dip signals..."
        try:
            dips = fetch_dip_candidates(tickers, spy_wow, earnings_map)
            for s in dips:
                s["signal_type"] = "DIP_BUY"
            all_candidates.extend(dips)
        except Exception as e:
            print(f"[!] Dip fetch: {e}", flush=True)

        _scan_status["step"] = "Collecting candidates: Pullback signals..."
        try:
            pullbacks = fetch_pullback_candidates(tickers, spy_wow, earnings_map)
            for s in pullbacks:
                s["signal_type"] = "PULLBACK"
            all_candidates.extend(pullbacks)
        except Exception as e:
            print(f"[!] Pullback fetch: {e}", flush=True)

        _scan_status["step"] = "Collecting candidates: Congress signals..."
        try:
            congress = fetch_congress_frontrun_candidates(spy_wow, earnings_map)
            for s in congress:
                s["signal_type"] = "CONGRESS"
            all_candidates.extend(congress)
        except Exception as e:
            print(f"[!] Congress fetch: {e}", flush=True)

        _scan_status["step"] = f"AI analysis: {len(all_candidates)} candidates → screen → analyze → risk..."
        all_signals = run_full_analysis(all_candidates, market_context)

        _scan_status["step"] = "Sending signals to Discord..."
        send_signals(all_signals, market_context)

        if all_signals:
            record_signals(all_signals, market_context)

        _scan_status["step"] = f"Done! {len(all_signals)} signal(s) from {len(all_candidates)} candidates."
        _scan_status["signals_found"] = len(all_signals)
        print(f"[Scan Complete] {len(all_signals)} signal(s) saved.", flush=True)
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
