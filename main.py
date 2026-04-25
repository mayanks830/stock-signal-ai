import os
import schedule
import time
import sys
import threading
from datetime import datetime

from config import SCAN_HOUR, FASTAPI_PORT, WATCHLIST_SCAN_ENABLED
from database import init_db, get_watchlist, is_congress_alert_sent, mark_congress_alert_sent
from fetcher import get_sp500_tickers, fetch_candidates, fetch_watchlist_data
from analyzer import analyze_stocks, analyze_watchlist
from notifier import send_signals, send_watchlist_report, send_congress_alert
from history import record_signals
from market_context import build_market_context
from tracker import run_performance_check
from report import generate_watchlist_pdf


def run_scan():
    print(f"\n{'='*60}")
    print(f"  Market Scan Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    print("\n[1/5] Fetching S&P 500 tickers...")
    tickers = get_sp500_tickers()

    print("\n[2/5] Fetching market context...")
    market_context = build_market_context()
    print(f"  VIX: {market_context.get('vix')} | SPY WoW: {market_context.get('spy_wow_pct'):+.2f}%")

    print("\n[3/5] Fetching stock data...")
    candidates = fetch_candidates(tickers)
    if not candidates:
        print("No candidates found.")
        send_signals([], market_context)
        return

    print("\n[4/5] Running AI analysis...")
    signals = analyze_stocks(candidates, market_context)

    print("\n[5/5] Sending signals to Discord...")
    send_signals(signals, market_context)

    if signals:
        record_signals(signals, market_context)

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

    # Watchlist scan daily at same time as regular scan
    if WATCHLIST_SCAN_ENABLED:
        for day in ["monday", "tuesday", "wednesday", "thursday", "friday"]:
            getattr(schedule.every(), day).at(f"{SCAN_HOUR:02d}:30").do(run_watchlist_scan)
        print(f"Watchlist scan: Mon-Fri at {SCAN_HOUR:02d}:30")

    print(f"Scheduler running. Scans: Mon-Fri at {SCAN_HOUR:02d}:00 | Performance check: daily 09:00")
    print("Flags: --now (scan) | --track (performance) | --watchlist (watchlist) | --congress-alerts (check now)")

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
