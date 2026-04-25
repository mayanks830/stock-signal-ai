from utils import fetch_with_retry

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://finance.yahoo.com",
}


def _fetch_history(ticker: str, days: int = 200) -> list[dict] | None:
    """Fetch daily OHLCV history from Yahoo Finance."""
    try:
        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
            f"?range={days}d&interval=1d"
        )
        resp = fetch_with_retry(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return None

        result = resp.json().get("chart", {}).get("result", [])
        if not result:
            return None

        quote = result[0]["indicators"]["quote"][0]
        closes = quote.get("close", [])
        volumes = quote.get("volume", [])

        # Filter out None values while keeping alignment
        data = []
        for i, c in enumerate(closes):
            if c is not None:
                data.append({
                    "close": c,
                    "volume": volumes[i] if i < len(volumes) and volumes[i] else 0,
                })
        return data if len(data) >= 30 else None
    except Exception as e:
        print(f"  [!] Technicals fetch failed for {ticker}: {e}")
        return None


def _calc_rsi(closes: list[float], period: int = 14) -> float | None:
    """Calculate RSI (Relative Strength Index)."""
    if len(closes) < period + 1:
        return None

    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]

    # Seed with simple average of first `period` changes
    gains = [d if d > 0 else 0 for d in deltas[:period]]
    losses = [-d if d < 0 else 0 for d in deltas[:period]]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    # Smoothed (Wilder's) for remaining
    for d in deltas[period:]:
        gain = d if d > 0 else 0
        loss = -d if d < 0 else 0
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def _calc_ma(closes: list[float], period: int) -> float | None:
    """Calculate simple moving average."""
    if len(closes) < period:
        return None
    return round(sum(closes[-period:]) / period, 2)


def _calc_ema(closes: list[float], period: int) -> list[float]:
    """Calculate exponential moving average series."""
    if len(closes) < period:
        return []
    k = 2 / (period + 1)
    ema = [sum(closes[:period]) / period]
    for price in closes[period:]:
        ema.append(price * k + ema[-1] * (1 - k))
    return ema


def _calc_macd(closes: list[float]) -> dict | None:
    """Calculate MACD (12/26/9)."""
    if len(closes) < 35:
        return None

    ema12 = _calc_ema(closes, 12)
    ema26 = _calc_ema(closes, 26)

    # Align: ema12 starts at index 12, ema26 at index 26
    # MACD line = ema12 - ema26 (aligned from the end)
    offset = 26 - 12  # = 14
    macd_line = [ema12[i + offset] - ema26[i] for i in range(len(ema26))]

    if len(macd_line) < 9:
        return None

    # Signal line = 9-period EMA of MACD line
    signal_line = _calc_ema(macd_line, 9)

    macd_val = macd_line[-1]
    signal_val = signal_line[-1] if signal_line else macd_val
    histogram = macd_val - signal_val

    # Determine crossover
    if len(macd_line) >= 2 and signal_line:
        prev_macd = macd_line[-2]
        prev_signal = signal_line[-2] if len(signal_line) >= 2 else signal_val
        if prev_macd <= prev_signal and macd_val > signal_val:
            cross = "BULLISH_CROSS"
        elif prev_macd >= prev_signal and macd_val < signal_val:
            cross = "BEARISH_CROSS"
        else:
            cross = "NONE"
    else:
        cross = "NONE"

    return {
        "macd": round(macd_val, 4),
        "signal": round(signal_val, 4),
        "histogram": round(histogram, 4),
        "crossover": cross,
    }


def get_technicals(ticker: str) -> dict | None:
    """
    Fetch extended history and calculate technical indicators.
    Returns dict with RSI, MAs, MACD, and status flags.
    """
    data = _fetch_history(ticker, days=250)
    if not data:
        return None

    closes = [d["close"] for d in data]
    current = closes[-1]

    rsi = _calc_rsi(closes)
    ma50 = _calc_ma(closes, 50)
    ma200 = _calc_ma(closes, 200)
    macd = _calc_macd(closes)

    # Status flags
    above_50ma = current > ma50 if ma50 else None
    above_200ma = current > ma200 if ma200 else None

    # Golden/Death cross
    ma_cross = None
    if ma50 and ma200:
        if ma50 > ma200:
            ma_cross = "GOLDEN"
        else:
            ma_cross = "DEATH"

    # RSI status
    rsi_status = None
    if rsi is not None:
        if rsi >= 70:
            rsi_status = "OVERBOUGHT"
        elif rsi <= 30:
            rsi_status = "OVERSOLD"
        else:
            rsi_status = "NEUTRAL"

    # Trailing returns
    returns = {}
    if len(closes) >= 6:
        returns["1w"] = round((current - closes[-6]) / closes[-6] * 100, 2)
    if len(closes) >= 22:
        returns["1m"] = round((current - closes[-22]) / closes[-22] * 100, 2)
    if len(closes) >= 66:
        returns["3m"] = round((current - closes[-66]) / closes[-66] * 100, 2)

    return {
        "rsi": rsi,
        "rsi_status": rsi_status,
        "ma50": ma50,
        "ma200": ma200,
        "above_50ma": above_50ma,
        "above_200ma": above_200ma,
        "ma_cross": ma_cross,
        "macd": macd,
        "trailing_returns": returns,
    }
