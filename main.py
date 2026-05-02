import os
import schedule
import time
import sys
import threading
from datetime import datetime

from config import SCAN_HOUR, FASTAPI_PORT, WATCHLIST_SCAN_ENABLED
from database import init_db, get_watchlist, is_congress_alert_sent, mark_congress_alert_sent
from fetcher import (
    get_sp500_tickers, fetch_candidates, fetch_watchlist_data,
    fetch_early_candidates, fetch_dip_candidates, fetch_pullback_candidates,
    fetch_congress_frontrun_candidates, get_spy_wow,
)
from analyzer import run_full_analysis, analyze_watchlist
from earnings import get_earnings_dates
from notifier import send_signals, send_watchlist_report, send_congress_alert
from history import record_signals
from market_context import build_market_context
from tracker import run_performance_check
from report import generate_watchlist_pdf


def run_scan():
    print(f"\n{'='*60}")
    print(f"  Market Scan Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    tickers = get_sp500_tickers()
    market_context = build_market_context()
    print(f"  VIX: {market_context.get('vix')} | SPY WoW: {market_context.get('spy_wow_pct'):+.2f}%")

    spy_wow = get_spy_wow()
    earnings_map = get_earnings_dates(tickers)

    # Collect ALL candidates from 5 pipelines
    all_candidates = []

    print("\n[1/6] Fetching momentum candidates...")
    try:
        momentum = fetch_candidates(tickers)
        for s in momentum:
            s["signal_type"] = "MOMENTUM"
        all_candidates.extend(momentum)
        print(f"  {len(momentum)} momentum candidates")
    except Exception as e:
        print(f"  [!] Momentum fetch failed: {e}")

    print("\n[2/6] Fetching early signal candidates...")
    try:
        early = fetch_early_candidates(tickers, spy_wow, earnings_map)
        for s in early:
            s["signal_type"] = "EARLY"
        all_candidates.extend(early)
        print(f"  {len(early)} early candidates")
    except Exception as e:
        print(f"  [!] Early signal fetch failed: {e}")

    print("\n[3/6] Fetching dip candidates...")
    try:
        dips = fetch_dip_candidates(tickers, spy_wow, earnings_map)
        for s in dips:
            s["signal_type"] = "DIP_BUY"
        all_candidates.extend(dips)
        print(f"  {len(dips)} dip candidates")
    except Exception as e:
        print(f"  [!] Dip fetch failed: {e}")

    print("\n[4/6] Fetching pullback candidates...")
    try:
        pullbacks = fetch_pullback_candidates(tickers, spy_wow, earnings_map)
        for s in pullbacks:
            s["signal_type"] = "PULLBACK"
        all_candidates.extend(pullbacks)
        print(f"  {len(pullbacks)} pullback candidates")
    except Exception as e:
        print(f"  [!] Pullback fetch failed: {e}")

    print("\n[5/6] Fetching congress candidates...")
    try:
        congress = fetch_congress_frontrun_candidates(spy_wow, earnings_map)
        for s in congress:
            s["signal_type"] = "CONGRESS"
        all_candidates.extend(congress)
        print(f"  {len(congress)} congress candidates")
    except Exception as e:
        print(f"  [!] Congress fetch failed: {e}")

    # 3-call AI pipeline: screen → analyze → risk frame
    print(f"\n[6/6] AI pipeline: {len(all_candidates)} candidates → screen → analyze → risk...")
    all_signals = run_full_analysis(all_candidates, market_context)

    print(f"\nTotal signals: {len(all_signals)}")
    send_signals(all_signals, market_context)

    if all_signals:
        record_signals(all_signals, market_context)

    print(f"\nScan complete at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def run_watchlist_scan():
    print(f"\n{'='*60}")
    print(f"  Watchlist Scan Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    print("\n[1/6] Fetching market context...")
    market_context = build_market_context()
    print(f"  VIX: {market_context.get('vix')} | SPY WoW: {market_context.get('spy_wow_pct'):+.2f}%")

    equity_tickers = [w["ticker"] for w in get_watchlist("equity")]
    etf_tickers = [w["ticker"] for w in get_watchlist("etf")]

    print(f"\n[2/6] Fetching equity watchlist data ({len(equity_tickers)} tickers)...")
    equities = fetch_watchlist_data(equity_tickers, include_technicals=True)

    print(f"\n[3/6] Fetching ETF watchlist data ({len(etf_tickers)} tickers)...")
    etfs = fetch_watchlist_data(etf_tickers, include_technicals=False)

    print("\n[4/7] Running AI analysis on watchlist...")
    try:
        analyses = analyze_watchlist(equities, market_context)
    except Exception as e:
        print(f"  [!] AI analysis failed ({type(e).__name__}): {e}")
        print("  Continuing with PDF generation without AI analysis...")
        analyses = []

    print("\n[5/7] Fetching insider trades & social sentiment...")
    try:
        from social import enrich_with_social_data
        enrich_with_social_data(equities)
    except Exception as e:
        print(f"  [!] Social data fetch failed: {e}")

    print("\n[6/7] Generating PDF report...")
    pdf_path = generate_watchlist_pdf(equities, etfs, market_context, analyses)

    print("\n[7/8] Sending report to Discord...")
    send_watchlist_report(pdf_path, equities, analyses)

    print("\n[8/8] Sending report via email...")
    try:
        from emailer import send_report_email
        send_report_email(pdf_path, equities, analyses)
    except Exception as e:
        print(f"  [!] Email delivery failed: {e}")

    print(f"\nWatchlist scan complete at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


CONGRESS_ALERT_MIN = float(os.getenv("CONGRESS_ALERT_MIN", 500_000))


def check_congress_alerts():
    """Check for congressional trades >= $500k and send Discord alerts."""
    from congress import fetch_congressional_trades

    print(f"\n[Congress Alert] Checking for trades >= ${CONGRESS_ALERT_MIN:,.0f}...")
    trades = fetch_congressional_trades(page_size=100)

    alerted = 0
    for trade in trades:
        val = trade.get("value_numeric")
        if val is None or val < CONGRESS_ALERT_MIN:
            continue

        # Unique key: filer + ticker + date + action + amount
        key = f"{trade.get('filer')}|{trade.get('ticker')}|{trade.get('tx_date')}|{trade.get('action')}|{val}"

        if is_congress_alert_sent(key):
            continue

        send_congress_alert(trade)
        mark_congress_alert_sent(key)
        alerted += 1

    print(f"[Congress Alert] Done. {alerted} new alert(s) sent, {len(trades)} trades checked.")


def start_api():
    try:
        import uvicorn
        from api.app import app
        print(f"Starting dashboard at http://localhost:{FASTAPI_PORT}")
        uvicorn.run(app, host="0.0.0.0", port=FASTAPI_PORT, log_level="warning")
    except ImportError:
        print("[!] FastAPI not installed — run 'pip install fastapi uvicorn' to enable the dashboard.")


def main():
    init_db()

    if "--watchlist" in sys.argv:
        run_watchlist_scan()
        return

    if "--now" in sys.argv:
        run_scan()
        return

    if "--track" in sys.argv:
        run_performance_check()
        return

    if "--congress-alerts" in sys.argv:
        check_congress_alerts()
        return

    if "--congress-enrich" in sys.argv:
        from congress import enrich_congress_trades
        enrich_congress_trades()
        return

    # Start API server in background thread
    api_thread = threading.Thread(target=start_api, daemon=True)
    api_thread.start()

    # Schedule daily scans at market close (Mon–Fri)
    for day in ["monday", "tuesday", "wednesday", "thursday", "friday"]:
        getattr(schedule.every(), day).at(f"{SCAN_HOUR:02d}:00").do(run_scan)

    # Performance check daily at 9 AM
    schedule.every().day.at("09:00").do(run_performance_check)

    # Congress trade alerts — check every 2 hours during market days
    for day in ["monday", "tuesday", "wednesday", "thursday", "friday"]:
        for hour in ["08:00", "10:00", "12:00", "14:00", "16:00", "18:00"]:
            getattr(schedule.every(), day).at(hour).do(check_congress_alerts)
    print(f"Congress alerts: Mon-Fri every 2h (min ${CONGRESS_ALERT_MIN:,.0f})")

    # Congress trade enrichment — daily at 17:00 (after market close)
    from congress import enrich_congress_trades
    for day in ["monday", "tuesday", "wednesday", "thursday", "friday"]:
        getattr(schedule.every(), day).at("17:00").do(enrich_congress_trades)
    print("Congress enrichment: Mon-Fri at 17:00")

    # Seed congress trades on startup (background thread so it doesn't block)
    def _initial_enrich():
        import time as _t
        _t.sleep(10)  # Wait for API to be ready
        try:
            enrich_congress_trades()
        except Exception as e:
            print(f"[Congress Enrich] Startup enrichment failed: {e}")
    threading.Thread(target=_initial_enrich, daemon=True).start()

    # Watchlist scan daily at same time as regular scan
    if WATCHLIST_SCAN_ENABLED:
        for day in ["monday", "tuesday", "wednesday", "thursday", "friday"]:
            getattr(schedule.every(), day).at(f"{SCAN_HOUR:02d}:30").do(run_watchlist_scan)
        print(f"Watchlist scan: Mon-Fri at {SCAN_HOUR:02d}:30")

    print(f"Scheduler running. Scans: Mon-Fri at {SCAN_HOUR:02d}:00 | Performance check: daily 09:00")
    print("Flags: --now (scan) | --track (performance) | --watchlist (watchlist) | --congress-alerts | --congress-enrich")

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
