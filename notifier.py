from datetime import datetime
from config import DISCORD_WEBHOOK_URL
from utils import fetch_with_retry

CONFIDENCE_EMOJI = {"HIGH": "🟢", "MEDIUM": "🟡"}
CONFIDENCE_COLOR = {"HIGH": 0x00C851, "MEDIUM": 0xFFBB33}
TREND_ARROW = {"up": "↑", "down": "↓"}


def _trend(s: dict) -> str:
    return (
        f"1d{TREND_ARROW.get(s.get('trend_1d',''),'?')} "
        f"1w{TREND_ARROW.get(s.get('trend_1w',''),'?')} "
        f"1m{TREND_ARROW.get(s.get('trend_1m',''),'?')}"
    )


def build_embed(signal: dict) -> dict:
    confidence = signal.get("confidence", "MEDIUM").upper()
    wow = signal.get("wow_change_pct", 0)
    price = signal.get("current_price", 0)
    target = signal.get("price_target")
    stop = signal.get("stop_loss")
    vol = signal.get("volume_ratio")
    rs = signal.get("relative_strength_vs_spy")
    sentiment = signal.get("sentiment_score", 0)
    earnings = signal.get("earnings_within_7d")
    earnings_date = signal.get("earnings_date", "")

    upside = f"+{((target - price) / price * 100):.1f}%" if target and price else "N/A"
    downside = f"-{((price - stop) / price * 100):.1f}%" if stop and price else "N/A"

    fields = [
        {"name": "💰 Price", "value": f"${price}", "inline": True},
        {"name": "📈 WoW", "value": f"{wow:+.2f}%", "inline": True},
        {"name": "📊 Volume", "value": f"{vol}x avg" if vol else "N/A", "inline": True},
        {"name": "🎯 Target", "value": f"${target} ({upside})" if target else "N/A", "inline": True},
        {"name": "🛑 Stop Loss", "value": f"${stop} ({downside})" if stop else "N/A", "inline": True},
        {"name": "⚡ vs S&P 500", "value": f"{rs:+.1f}%" if rs is not None else "N/A", "inline": True},
        {"name": "📉 Trends", "value": _trend(signal), "inline": True},
        {"name": "🗞️ Sentiment", "value": f"{sentiment:+.2f}" if sentiment is not None else "N/A", "inline": True},
        {"name": "🏷️ Sector", "value": signal.get("sector", "N/A"), "inline": True},
        {"name": "📋 Analysis", "value": signal.get("reason", "N/A"), "inline": False},
        {"name": "⚠️ Risk", "value": signal.get("risk", "N/A"), "inline": False},
    ]

    if earnings:
        fields.append({
            "name": "📅 Earnings Alert",
            "value": f"Earnings on {earnings_date} — high risk/reward event within 7 days",
            "inline": False,
        })

    return {
        "title": f"{CONFIDENCE_EMOJI.get(confidence, '🟡')} BUY: {signal['ticker']} — {signal.get('name', signal['ticker'])}",
        "color": CONFIDENCE_COLOR.get(confidence, 0xFFBB33),
        "fields": fields,
        "footer": {
            "text": f"{confidence} confidence • {datetime.now().strftime('%Y-%m-%d %H:%M')} • $1B+ revenue filter"
        },
    }


def send_signals(signals: list[dict], market_context: dict = None) -> None:
    if not signals:
        payload = {"content": "📊 **Daily Market Scan** — No strong buy signals today. Staying patient."}
        fetch_with_retry(DISCORD_WEBHOOK_URL, method="post", timeout=15, json=payload)
        return

    high = [s for s in signals if s.get("confidence", "").upper() == "HIGH"]
    medium = [s for s in signals if s.get("confidence", "").upper() == "MEDIUM"]

    # Market context summary
    ctx_text = ""
    if market_context:
        vix = market_context.get("vix")
        spy = market_context.get("spy_wow_pct")
        ctx_text = f"\n📊 VIX: {vix} ({market_context.get('vix_label','?')}) | SPY WoW: {spy:+.2f}%" if vix and spy else ""

    header = {
        "content": (
            f"📊 **Daily Buy Signals** — {datetime.now().strftime('%B %d, %Y %H:%M')}"
            f"{ctx_text}\n"
            f"🟢 **{len(high)} HIGH** · 🟡 **{len(medium)} MEDIUM** confidence\n"
            f"Filters: $1B+ revenue · 3%+ WoW · News catalyst · Max 2/sector · No repeats within 7d"
        ),
    }
    fetch_with_retry(DISCORD_WEBHOOK_URL, method="post", timeout=15, json=header)

    for signal in high + medium:
        resp = fetch_with_retry(DISCORD_WEBHOOK_URL, method="post", timeout=15, json={"embeds": [build_embed(signal)]})
        if resp.status_code not in (200, 204):
            print(f"[!] Discord error for {signal['ticker']}: {resp.status_code}")
        else:
            print(f"  Sent: {signal['ticker']} ({signal.get('confidence')})")


def send_watchlist_report(pdf_path: str, equities: list[dict], analyses: list[dict]) -> None:
    """Send the watchlist PDF report to Discord as an attachment with a summary."""
    # Build summary text
    valid = [s for s in equities if not s.get("error") and s.get("daily_change_pct") is not None]
    signal_count = len([a for a in analyses if a.get("signal") in ("BUY", "SELL")])

    top_mover = None
    if valid:
        top = max(valid, key=lambda x: abs(x.get("daily_change_pct", 0)))
        daily = top.get("daily_change_pct", 0)
        top_mover = f"{top['ticker']} {daily:+.1f}%"

    summary = (
        f"\U0001f4ca **Daily Watchlist Report** \u2014 {datetime.now().strftime('%B %d, %Y')}"
        f" | {signal_count} signal(s)"
    )
    if top_mover:
        summary += f" | Top mover: {top_mover}"

    try:
        with open(pdf_path, "rb") as f:
            resp = fetch_with_retry(
                DISCORD_WEBHOOK_URL,
                method="post",
                timeout=15,
                data={"content": summary},
                files={"file": (pdf_path.split("/")[-1].split("\\")[-1], f, "application/pdf")},
            )
        if resp.status_code in (200, 204):
            print(f"Watchlist report sent to Discord.")
        else:
            print(f"[!] Discord upload error: {resp.status_code} — {resp.text[:200]}")
    except Exception as e:
        print(f"[!] Failed to send watchlist report to Discord: {e}")


def send_congress_alert(trade: dict) -> None:
    """Send a Discord alert for a large congressional trade."""
    if not DISCORD_WEBHOOK_URL:
        return

    action = trade.get("action", "TRADE")
    color = 0x00C851 if action == "BUY" else 0xF44336 if action == "SELL" else 0x9E9E9E
    action_emoji = "\U0001f7e2" if action == "BUY" else "\U0001f534" if action == "SELL" else "\u26aa"
    party = trade.get("party", "?")
    party_emoji = "\U0001f535" if party == "D" else "\U0001f534" if party == "R" else "\u26aa"

    ticker = trade.get("ticker") or trade.get("company", "N/A")
    amount = trade.get("amount", "N/A")
    gap = trade.get("reporting_gap")
    gap_str = f"{gap} days" if gap is not None else "N/A"

    embed = {
        "title": f"{action_emoji} Congress {action}: {trade.get('filer', 'Unknown')} ({party}-{trade.get('chamber', '?')})",
        "color": color,
        "fields": [
            {"name": "Ticker", "value": ticker, "inline": True},
            {"name": "Amount", "value": amount, "inline": True},
            {"name": "Action", "value": action, "inline": True},
            {"name": "Company", "value": trade.get("company", "N/A"), "inline": True},
            {"name": "Trade Date", "value": trade.get("tx_date", "N/A"), "inline": True},
            {"name": "Reporting Gap", "value": gap_str, "inline": True},
        ],
        "footer": {
            "text": f"Congressional Trade Alert | {party_emoji} {party} | {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        },
    }
    resp = fetch_with_retry(DISCORD_WEBHOOK_URL, method="post", timeout=15, json={"embeds": [embed]})
    if resp.status_code in (200, 204):
        print(f"  Congress alert sent: {trade.get('filer')} {action} {ticker} {amount}")
    else:
        print(f"  [!] Congress alert Discord error: {resp.status_code}")


def send_performance_report(reports: list[dict]) -> None:
    if not reports:
        return

    wins = [r for r in reports if r.get("outcome") == "WIN"]
    losses = [r for r in reports if r.get("outcome") == "LOSS"]

    fields = []
    for r in reports:
        outcome = r.get("outcome", "OPEN")
        emoji = "✅" if outcome == "WIN" else ("❌" if outcome == "LOSS" else "⏳")
        pct = r.get("pct_change", 0)
        fields.append({
            "name": f"{emoji} {r['ticker']} ({outcome})",
            "value": (
                f"Entry: ${r.get('entry_price')} → Now: ${r.get('exit_price')} | "
                f"**{pct:+.2f}%** | Signal: {r.get('signaled_at', '')[:10]}"
            ),
            "inline": False,
        })

    embed = {
        "title": f"📈 Weekly Signal Performance Report — {datetime.now().strftime('%B %d, %Y')}",
        "color": 0x5865F2,
        "fields": fields[:25],  # Discord embed field limit
        "footer": {"text": f"✅ {len(wins)} wins · ❌ {len(losses)} losses"},
    }
    resp = fetch_with_retry(DISCORD_WEBHOOK_URL, method="post", timeout=15, json={"embeds": [embed]})
    if resp.status_code in (200, 204):
        print(f"Performance report sent: {len(reports)} signals reviewed.")
