import requests
from datetime import datetime
from config import DISCORD_WEBHOOK_URL

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
        requests.post(DISCORD_WEBHOOK_URL, json=payload)
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
    requests.post(DISCORD_WEBHOOK_URL, json=header)

    for signal in high + medium:
        resp = requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [build_embed(signal)]})
        if resp.status_code not in (200, 204):
            print(f"[!] Discord error for {signal['ticker']}: {resp.status_code}")
        else:
            print(f"  Sent: {signal['ticker']} ({signal.get('confidence')})")


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
    resp = requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]})
    if resp.status_code in (200, 204):
        print(f"Performance report sent: {len(reports)} signals reviewed.")
