import schedule
import time
import sys
import threading
from datetime import datetime

from config import SCAN_HOUR, FASTAPI_PORT
from database import init_db
from fetcher import get_sp500_tickers, fetch_candidates
from analyzer import analyze_stocks
from notifier import send_signals
from history import record_signals
from market_context import build_market_context
from tracker import run_performance_check


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

    if "--now" in sys.argv:
        run_scan()
        return

    if "--track" in sys.argv:
        run_performance_check()
        return

    # Start API server in background thread
    api_thread = threading.Thread(target=start_api, daemon=True)
    api_thread.start()

    # Schedule daily scans at market close (Mon–Fri)
    for day in ["monday", "tuesday", "wednesday", "thursday", "friday"]:
        getattr(schedule.every(), day).at(f"{SCAN_HOUR:02d}:00").do(run_scan)

    # Performance check daily at 9 AM
    schedule.every().day.at("09:00").do(run_performance_check)

    print(f"Scheduler running. Scans: Mon–Fri at {SCAN_HOUR:02d}:00 | Performance check: daily 09:00")
    print("Flags: --now (immediate scan) | --track (performance check)")

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
