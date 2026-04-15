import requests
from datetime import datetime, timedelta
from database import get_open_signals, save_performance, get_all_performance
from notifier import send_performance_report

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://finance.yahoo.com",
}


def get_current_price(ticker: str) -> float | None:
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=1d&interval=1d"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        result = resp.json().get("chart", {}).get("result", [])
        if not result:
            return None
        closes = [c for c in result[0]["indicators"]["quote"][0].get("close", []) if c]
        return round(closes[-1], 2) if closes else None
    except Exception:
        return None


def run_performance_check() -> None:
    print(f"\n[Tracker] Running performance check at {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    open_signals = get_open_signals()

    if not open_signals:
        print("[Tracker] No open signals to check.")
        return

    matured = []
    for signal in open_signals:
        signal_id = signal["id"]
        ticker = signal["ticker"]
        entry_price = signal["current_price"]
        price_target = signal.get("price_target")
        stop_loss = signal.get("stop_loss")
        signaled_at = datetime.fromisoformat(signal["signaled_at"])
        days_open = (datetime.now() - signaled_at).days

        current_price = get_current_price(ticker)
        if not current_price:
            continue

        pct_change = round((current_price - entry_price) / entry_price * 100, 2)
        hit_target = bool(price_target and current_price >= price_target)
        hit_stop = bool(stop_loss and current_price <= stop_loss)

        # Determine outcome
        if hit_target:
            outcome = "WIN"
        elif hit_stop:
            outcome = "LOSS"
        elif days_open >= 7:
            outcome = "WIN" if pct_change > 0 else "LOSS"
        else:
            outcome = "OPEN"

        save_performance(signal_id, current_price, pct_change, hit_target, hit_stop, outcome)
        print(f"  {ticker}: {pct_change:+.2f}% → {outcome}")

        if outcome in ("WIN", "LOSS"):
            matured.append({
                **signal,
                "entry_price": entry_price,
                "exit_price": current_price,
                "pct_change": pct_change,
                "outcome": outcome,
            })

    if matured:
        print(f"[Tracker] {len(matured)} signals matured. Sending report to Discord...")
        send_performance_report(matured)
    else:
        print("[Tracker] No matured signals yet.")
