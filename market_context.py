import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://finance.yahoo.com",
}

SECTOR_ETFS = {
    "Technology": "XLK",
    "Financials": "XLF",
    "Healthcare": "XLV",
    "Energy": "XLE",
    "Consumer Discretionary": "XLY",
    "Communication": "XLC",
    "Industrials": "XLI",
    "Consumer Staples": "XLP",
    "Real Estate": "XLRE",
    "Utilities": "XLU",
    "Materials": "XLB",
}


def _fetch_wow(symbol: str) -> float | None:
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=14d&interval=1d"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return None
        result = resp.json().get("chart", {}).get("result", [])
        if not result:
            return None
        closes = [c for c in result[0]["indicators"]["quote"][0].get("close", []) if c]
        if len(closes) < 6:
            return None
        current = closes[-1]
        week_ago = closes[max(0, len(closes) - 6)]
        return round((current - week_ago) / week_ago * 100, 2)
    except Exception:
        return None


def get_vix() -> float | None:
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX?range=1d&interval=1d"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        result = resp.json().get("chart", {}).get("result", [])
        if not result:
            return None
        closes = [c for c in result[0]["indicators"]["quote"][0].get("close", []) if c]
        return round(closes[-1], 2) if closes else None
    except Exception:
        return None


def get_sector_rotation() -> dict:
    rotation = {}
    for sector, etf in SECTOR_ETFS.items():
        wow = _fetch_wow(etf)
        if wow is not None:
            rotation[sector] = wow
    return rotation


def build_market_context() -> dict:
    print("  Fetching market context (VIX, SPY, sectors)...")
    vix = get_vix()
    spy_wow = _fetch_wow("SPY")
    sectors = get_sector_rotation()

    # Interpret VIX
    if vix is None:
        vix_label = "unknown"
    elif vix < 15:
        vix_label = "low (complacent market)"
    elif vix < 20:
        vix_label = "normal"
    elif vix < 30:
        vix_label = "elevated (caution)"
    else:
        vix_label = "high (fear/volatility)"

    # Top gaining and losing sectors
    sorted_sectors = sorted(sectors.items(), key=lambda x: x[1], reverse=True)
    rotating_into = [f"{s} ({v:+.1f}%)" for s, v in sorted_sectors[:3]]
    rotating_out = [f"{s} ({v:+.1f}%)" for s, v in sorted_sectors[-3:]]

    return {
        "vix": vix,
        "vix_label": vix_label,
        "spy_wow_pct": spy_wow,
        "sector_rotation": sectors,
        "rotating_into": rotating_into,
        "rotating_out": rotating_out,
    }


def format_for_prompt(ctx: dict) -> str:
    sectors_in = ", ".join(ctx.get("rotating_into", []))
    sectors_out = ", ".join(ctx.get("rotating_out", []))
    spy = ctx.get("spy_wow_pct")
    vix = ctx.get("vix")

    return (
        f"MARKET CONTEXT:\n"
        f"- VIX: {vix} ({ctx.get('vix_label', '?')})\n"
        f"- S&P 500 WoW: {spy:+.2f}%\n" if spy else f"- S&P 500 WoW: N/A\n"
        f"- Sectors with inflows: {sectors_in}\n"
        f"- Sectors with outflows: {sectors_out}\n"
    )
