import os
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak,
    KeepTogether, HRFlowable,
)
from config import PDF_OUTPUT_DIR
from database import get_performance_summary, get_open_signals

TREND_ARROW = {"up": "\u2191", "down": "\u2193"}

# Color constants
GREEN = colors.HexColor("#22c55e")
DARK_GREEN = colors.HexColor("#15803d")
RED = colors.HexColor("#ef4444")
DARK_RED = colors.HexColor("#b91c1c")
YELLOW = colors.HexColor("#eab308")
BLUE = colors.HexColor("#3b82f6")
GRAY = colors.HexColor("#6b7280")
LIGHT_GRAY = colors.HexColor("#9ca3af")
LIGHT_GREEN = colors.HexColor("#dcfce7")
LIGHT_RED = colors.HexColor("#fee2e2")
LIGHT_YELLOW = colors.HexColor("#fef9c3")
LIGHT_BLUE = colors.HexColor("#dbeafe")
HEADER_BG = colors.HexColor("#1e293b")
HEADER_FG = colors.white
ROW_ALT = colors.HexColor("#f8fafc")
ACCENT = colors.HexColor("#0f172a")


def _pct_color(val):
    if val is None:
        return GRAY
    return GREEN if val > 0 else RED if val < 0 else GRAY


def _fmt_pct(val, fallback="--"):
    if val is None:
        return fallback
    return f"{val:+.2f}%"


def _fmt_price(val, fallback="--"):
    if val is None:
        return fallback
    return f"${val:,.2f}"


def _trend_arrows(stock):
    return (
        f"{TREND_ARROW.get(stock.get('trend_1d', ''), '?')} "
        f"{TREND_ARROW.get(stock.get('trend_1w', ''), '?')} "
        f"{TREND_ARROW.get(stock.get('trend_1m', ''), '?')}"
    )


def _make_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        "ReportTitle", parent=styles["Title"], fontSize=20, spaceAfter=2,
        textColor=ACCENT,
    ))
    styles.add(ParagraphStyle(
        "ReportDate", parent=styles["Normal"], fontSize=10, textColor=LIGHT_GRAY,
        spaceAfter=16,
    ))
    styles.add(ParagraphStyle(
        "SectionHead", parent=styles["Heading2"], fontSize=13, spaceBefore=14, spaceAfter=6,
        textColor=ACCENT, borderPadding=(0, 0, 2, 0),
    ))
    styles.add(ParagraphStyle(
        "SubHead", parent=styles["Heading3"], fontSize=10, spaceBefore=10, spaceAfter=4,
        textColor=colors.HexColor("#334155"),
    ))
    styles.add(ParagraphStyle(
        "CellText", parent=styles["Normal"], fontSize=7, leading=9,
    ))
    styles.add(ParagraphStyle(
        "BodyText8", parent=styles["Normal"], fontSize=8, leading=11, spaceBefore=2,
    ))
    styles.add(ParagraphStyle(
        "SmallGray", parent=styles["Normal"], fontSize=6.5, leading=8, textColor=LIGHT_GRAY,
    ))
    styles.add(ParagraphStyle(
        "KPILabel", parent=styles["Normal"], fontSize=7, textColor=LIGHT_GRAY, alignment=1,
    ))
    styles.add(ParagraphStyle(
        "KPIValue", parent=styles["Normal"], fontSize=14, alignment=1,
        textColor=ACCENT, fontName="Helvetica-Bold",
    ))
    return styles


def _base_table_style():
    return [
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), HEADER_FG),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 7),
        ("FONTSIZE", (0, 1), (-1, -1), 7),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]


def _alt_row_colors(style_cmds, num_rows):
    for i in range(1, num_rows):
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), ROW_ALT))


def _divider():
    return HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0"),
                       spaceBefore=8, spaceAfter=8)


def _page_footer(canvas, doc):
    """Add page number and timestamp to every page."""
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#94a3b8"))
    page_num = canvas.getPageNumber()
    canvas.drawString(0.5 * inch, 0.35 * inch,
                      f"Stock Signal AI \u2014 Daily Watchlist Report")
    canvas.drawRightString(letter[0] - 0.5 * inch, 0.35 * inch,
                           f"Page {page_num}")
    canvas.restoreState()


# ── Page 1: Executive Summary + Market Overview ──────────────────────────────

def _build_executive_summary(styles, market_context, equities, etfs, analyses):
    elements = []

    all_stocks = [s for s in equities + etfs if not s.get("error") and s.get("daily_change_pct") is not None]

    # KPI cards
    buy_signals = len([a for a in analyses if a.get("signal") == "BUY"])
    sell_signals = len([a for a in analyses if a.get("signal") == "SELL"])
    bullish = len([a for a in analyses if a.get("outlook") == "BULLISH"])
    bearish = len([a for a in analyses if a.get("outlook") == "BEARISH"])

    gainers = len([s for s in all_stocks if s["daily_change_pct"] > 0])
    losers = len([s for s in all_stocks if s["daily_change_pct"] < 0])

    top_gainer = max(all_stocks, key=lambda x: x["daily_change_pct"]) if all_stocks else None
    top_loser = min(all_stocks, key=lambda x: x["daily_change_pct"]) if all_stocks else None

    vix = market_context.get("vix")
    spy_wow = market_context.get("spy_wow_pct")

    # Summary box
    kpi_data = [
        ["VIX", "SPY WoW", "Signals", "Outlook", "Gainers", "Top Mover"],
        [
            f"{vix:.1f}" if vix else "--",
            _fmt_pct(spy_wow),
            f"{buy_signals} BUY / {sell_signals} SELL",
            f"{bullish}B / {bearish}Be",
            f"{gainers}G / {losers}L",
            f"{top_gainer['ticker']} {top_gainer['daily_change_pct']:+.1f}%" if top_gainer else "--",
        ],
    ]
    kpi_w = [1.05*inch, 1.05*inch, 1.2*inch, 1.0*inch, 0.95*inch, 1.35*inch]
    t = Table(kpi_data, colWidths=kpi_w)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ("TEXTCOLOR", (0, 0), (-1, 0), LIGHT_GRAY),
        ("FONTSIZE", (0, 0), (-1, 0), 7),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, 1), 10),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 1), (-1, 1), ACCENT),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("BACKGROUND", (0, 1), (-1, 1), colors.white),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 12))

    return elements


def _build_market_overview(styles, market_context, equities, etfs):
    elements = []
    vix = market_context.get("vix")
    vix_label = market_context.get("vix_label", "unknown")
    spy_wow = market_context.get("spy_wow_pct")

    spy_data = next((e for e in etfs if e["ticker"] == "SPY"), None)
    qqq_data = next((e for e in etfs if e["ticker"] == "QQQ"), None)

    elements.append(Paragraph("Market Overview", styles["SectionHead"]))

    metrics = [["Metric", "Value", "Status"]]
    metrics.append(["VIX", f"{vix:.1f}" if vix else "--", vix_label])
    metrics.append(["SPY WoW", _fmt_pct(spy_wow), "Bullish" if spy_wow and spy_wow > 0 else "Bearish"])
    if spy_data and not spy_data.get("error"):
        metrics.append(["SPY Daily", _fmt_pct(spy_data.get("daily_change_pct")), ""])
    if qqq_data and not qqq_data.get("error"):
        metrics.append(["QQQ Daily", _fmt_pct(qqq_data.get("daily_change_pct")), ""])
        metrics.append(["QQQ WoW", _fmt_pct(qqq_data.get("wow_change_pct")), ""])

    t = Table(metrics, colWidths=[2 * inch, 2 * inch, 2.5 * inch])
    style_cmds = _base_table_style()
    _alt_row_colors(style_cmds, len(metrics))
    # Color the values
    for i in range(1, len(metrics)):
        val_str = metrics[i][1]
        if val_str.startswith("+"):
            style_cmds.append(("TEXTCOLOR", (1, i), (1, i), GREEN))
        elif val_str.startswith("-"):
            style_cmds.append(("TEXTCOLOR", (1, i), (1, i), RED))
    t.setStyle(TableStyle(style_cmds))
    elements.append(t)
    elements.append(Spacer(1, 10))

    # Sector rotation (inline)
    elements.append(Paragraph("Sector Rotation", styles["SubHead"]))
    rotating_into = market_context.get("rotating_into", [])
    rotating_out = market_context.get("rotating_out", [])
    rot_data = [["Sectors with Inflows", "Sectors with Outflows"]]
    max_len = max(len(rotating_into), len(rotating_out), 1)
    for i in range(max_len):
        rot_data.append([
            rotating_into[i] if i < len(rotating_into) else "",
            rotating_out[i] if i < len(rotating_out) else "",
        ])
    t = Table(rot_data, colWidths=[3.25 * inch, 3.25 * inch])
    style_cmds = _base_table_style()
    _alt_row_colors(style_cmds, len(rot_data))
    t.setStyle(TableStyle(style_cmds))
    elements.append(t)
    elements.append(Spacer(1, 10))

    # Risk alerts
    alerts = []
    if vix and vix > 25:
        alerts.append(f"VIX elevated at {vix:.1f} \u2014 increased market volatility")
    all_stocks = [s for s in equities + etfs if not s.get("error") and s.get("daily_change_pct") is not None]
    big_drops = [s for s in all_stocks if s["daily_change_pct"] < -3]
    if big_drops:
        tickers = ", ".join(s["ticker"] for s in sorted(big_drops, key=lambda x: x["daily_change_pct"])[:5])
        alerts.append(f"Major drops: {tickers}")
    big_gains = [s for s in all_stocks if s["daily_change_pct"] > 5]
    if big_gains:
        tickers = ", ".join(s["ticker"] for s in sorted(big_gains, key=lambda x: -x["daily_change_pct"])[:5])
        alerts.append(f"Notable gainers: {tickers}")

    if alerts:
        elements.append(Paragraph("Alerts", styles["SubHead"]))
        for alert in alerts:
            elements.append(Paragraph(f"\u26a0 {alert}", styles["BodyText8"]))

    return elements


# ── Equity Watchlist Table ───────────────────────────────────────────────────

def _build_equity_table(styles, equities):
    elements = []

    # Replaced "Sent" with "Sntmt", replaced absolute MA with status, added MACD
    headers = ["Ticker", "Price", "Daily%", "WoW%", "Vol", "RSI", "vs 50MA", "vs 200MA", "MACD", "Trend", "Sntmt"]
    rows = [headers]
    highlight_rows = []

    for i, s in enumerate(equities):
        if s.get("error"):
            rows.append([s["ticker"], "ERR", "", "", "", "", "", "", "", "", ""])
            continue

        rsi = s.get("rsi")
        rsi_text = f"{rsi:.0f}" if rsi is not None else "--"

        # Show above/below MA as compact status instead of absolute price
        ma50_status = "\u2191 Above" if s.get("above_50ma") else ("\u2193 Below" if s.get("above_50ma") is False else "--")
        ma200_status = "\u2191 Above" if s.get("above_200ma") else ("\u2193 Below" if s.get("above_200ma") is False else "--")

        # MACD crossover
        macd = s.get("macd")
        if macd:
            cross = macd.get("crossover", "NONE")
            if cross == "BULLISH_CROSS":
                macd_text = "\u2191 Bull"
            elif cross == "BEARISH_CROSS":
                macd_text = "\u2193 Bear"
            else:
                macd_text = "Flat" if macd.get("histogram", 0) >= 0 else "Neg"
        else:
            macd_text = "--"

        sentiment = s.get("sentiment_score", 0)

        rows.append([
            s["ticker"],
            _fmt_price(s.get("current_price")),
            _fmt_pct(s.get("daily_change_pct")),
            _fmt_pct(s.get("wow_change_pct")),
            f"{s.get('volume_ratio', '--')}x",
            rsi_text,
            ma50_status,
            ma200_status,
            macd_text,
            _trend_arrows(s),
            f"{sentiment:+.1f}" if sentiment else "0.0",
        ])

        row_idx = len(rows) - 1
        if rsi is not None and rsi >= 70:
            highlight_rows.append((row_idx, LIGHT_YELLOW))
        elif rsi is not None and rsi <= 30:
            highlight_rows.append((row_idx, LIGHT_GREEN))
        if s.get("above_200ma") is False:
            highlight_rows.append((row_idx, LIGHT_RED))

    col_widths = [0.52*inch, 0.62*inch, 0.55*inch, 0.55*inch, 0.4*inch, 0.35*inch, 0.58*inch, 0.6*inch, 0.5*inch, 0.6*inch, 0.4*inch]
    t = Table(rows, colWidths=col_widths, repeatRows=1)
    style_cmds = _base_table_style()
    style_cmds.append(("FONTSIZE", (0, 0), (-1, 0), 6.5))
    style_cmds.append(("FONTSIZE", (0, 1), (-1, -1), 6.5))
    _alt_row_colors(style_cmds, len(rows))

    for row_idx, bg_color in highlight_rows:
        style_cmds.append(("BACKGROUND", (0, row_idx), (-1, row_idx), bg_color))

    for i in range(1, len(rows)):
        stock = equities[i - 1]
        if stock.get("error"):
            continue
        daily = stock.get("daily_change_pct")
        wow = stock.get("wow_change_pct")
        if daily is not None:
            style_cmds.append(("TEXTCOLOR", (2, i), (2, i), _pct_color(daily)))
        if wow is not None:
            style_cmds.append(("TEXTCOLOR", (3, i), (3, i), _pct_color(wow)))
        # Color MA status
        if stock.get("above_50ma"):
            style_cmds.append(("TEXTCOLOR", (6, i), (6, i), GREEN))
        elif stock.get("above_50ma") is False:
            style_cmds.append(("TEXTCOLOR", (6, i), (6, i), RED))
        if stock.get("above_200ma"):
            style_cmds.append(("TEXTCOLOR", (7, i), (7, i), GREEN))
        elif stock.get("above_200ma") is False:
            style_cmds.append(("TEXTCOLOR", (7, i), (7, i), RED))
        # Color MACD
        macd = stock.get("macd")
        if macd:
            cross = macd.get("crossover", "NONE")
            if cross == "BULLISH_CROSS":
                style_cmds.append(("TEXTCOLOR", (8, i), (8, i), GREEN))
            elif cross == "BEARISH_CROSS":
                style_cmds.append(("TEXTCOLOR", (8, i), (8, i), RED))

    t.setStyle(TableStyle(style_cmds))
    elements.append(t)
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(
        "<font size='6' color='#9ca3af'>"
        "Highlights: Yellow = Overbought RSI (>70) | Green = Oversold RSI (<30) | "
        "Red = Below 200-day MA"
        "</font>",
        styles["Normal"],
    ))

    return elements


# ── ETF Portfolio Table ──────────────────────────────────────────────────────

def _build_etf_table(styles, etfs):
    elements = []

    headers = ["Ticker", "Price", "Daily%", "WoW%", "Vol Ratio", "Trend (1d/1w/1m)"]
    rows = [headers]

    for s in etfs:
        if s.get("error"):
            rows.append([s["ticker"], "ERR", "", "", "", ""])
            continue
        rows.append([
            s["ticker"],
            _fmt_price(s.get("current_price")),
            _fmt_pct(s.get("daily_change_pct")),
            _fmt_pct(s.get("wow_change_pct")),
            f"{s.get('volume_ratio', '--')}x",
            _trend_arrows(s),
        ])

    col_widths = [0.8*inch, 1.1*inch, 0.9*inch, 0.9*inch, 0.9*inch, 1.2*inch]
    t = Table(rows, colWidths=col_widths, repeatRows=1)
    style_cmds = _base_table_style()
    _alt_row_colors(style_cmds, len(rows))

    for i in range(1, len(rows)):
        stock = etfs[i - 1]
        if stock.get("error"):
            continue
        daily = stock.get("daily_change_pct")
        wow = stock.get("wow_change_pct")
        if daily is not None:
            style_cmds.append(("TEXTCOLOR", (2, i), (2, i), _pct_color(daily)))
        if wow is not None:
            style_cmds.append(("TEXTCOLOR", (3, i), (3, i), _pct_color(wow)))

    t.setStyle(TableStyle(style_cmds))
    elements.append(t)

    return elements


# ── Top Movers ───────────────────────────────────────────────────────────────

def _build_top_movers(styles, all_stocks):
    elements = []

    valid = [s for s in all_stocks if not s.get("error") and s.get("daily_change_pct") is not None]
    sorted_by_change = sorted(valid, key=lambda x: x["daily_change_pct"], reverse=True)

    gainers = sorted_by_change[:5]
    losers = sorted_by_change[-5:][::-1]

    headers = ["Ticker", "Price", "Daily%", "WoW%", "Volume", "Context"]
    col_widths = [0.7*inch, 0.9*inch, 0.8*inch, 0.8*inch, 0.7*inch, 1.2*inch]

    # Gainers
    elements.append(Paragraph("Top 5 Gainers", styles["SubHead"]))
    rows = [headers]
    for s in gainers:
        vol = s.get("volume_ratio", 1.0)
        rows.append([
            s["ticker"], _fmt_price(s.get("current_price")),
            _fmt_pct(s.get("daily_change_pct")), _fmt_pct(s.get("wow_change_pct")),
            f"{vol}x", "HIGH VOL" if vol and vol > 1.5 else "Normal",
        ])
    t = Table(rows, colWidths=col_widths, repeatRows=1)
    style_cmds = _base_table_style()
    _alt_row_colors(style_cmds, len(rows))
    for i in range(1, len(rows)):
        style_cmds.append(("TEXTCOLOR", (2, i), (2, i), GREEN))
    t.setStyle(TableStyle(style_cmds))
    elements.append(t)
    elements.append(Spacer(1, 12))

    # Losers
    elements.append(Paragraph("Top 5 Losers", styles["SubHead"]))
    rows = [headers]
    for s in losers:
        vol = s.get("volume_ratio", 1.0)
        rows.append([
            s["ticker"], _fmt_price(s.get("current_price")),
            _fmt_pct(s.get("daily_change_pct")), _fmt_pct(s.get("wow_change_pct")),
            f"{vol}x", "HIGH VOL" if vol and vol > 1.5 else "Normal",
        ])
    t = Table(rows, colWidths=col_widths, repeatRows=1)
    style_cmds = _base_table_style()
    _alt_row_colors(style_cmds, len(rows))
    for i in range(1, len(rows)):
        style_cmds.append(("TEXTCOLOR", (2, i), (2, i), RED))
    t.setStyle(TableStyle(style_cmds))
    elements.append(t)

    return elements


# ── AI Analysis & Signals ────────────────────────────────────────────────────

def _build_ai_analysis(styles, analyses):
    elements = []

    if not analyses:
        elements.append(Paragraph("No notable activity detected by AI analysis.", styles["BodyText8"]))
        return elements

    # Summary counts at top
    buys = [a for a in analyses if a.get("signal") == "BUY"]
    sells = [a for a in analyses if a.get("signal") == "SELL"]
    holds = [a for a in analyses if a.get("signal") == "HOLD"]
    elements.append(Paragraph(
        f"<b>{len(buys)}</b> BUY | <b>{len(sells)}</b> SELL | <b>{len(holds)}</b> HOLD signals from {len(analyses)} stocks analyzed",
        styles["BodyText8"],
    ))
    elements.append(Spacer(1, 8))

    outlook_colors = {"BULLISH": "#22c55e", "BEARISH": "#ef4444", "NEUTRAL": "#6b7280"}
    signal_colors = {"BUY": "#22c55e", "SELL": "#ef4444", "HOLD": "#eab308"}

    # Show BUY/SELL signals first, then HOLDs
    sorted_analyses = sorted(analyses, key=lambda a: (
        0 if a.get("signal") == "BUY" else 1 if a.get("signal") == "SELL" else 2
    ))

    for a in sorted_analyses:
        ticker = a.get("ticker", "?")
        outlook = a.get("outlook", "NEUTRAL")
        signal = a.get("signal", "HOLD")
        reasoning = a.get("reasoning", "")
        target = a.get("price_target")
        stop = a.get("stop_loss")
        price = a.get("current_price")

        o_color = outlook_colors.get(outlook, "#6b7280")
        s_color = signal_colors.get(signal, "#6b7280")

        header = (
            f"<b>{ticker}</b> \u2014 "
            f"<font color='{o_color}'>{outlook}</font> | "
            f"<font color='{s_color}'><b>{signal}</b></font>"
        )
        if price:
            header += f" | ${price:,.2f}"
        if target:
            header += f" | Target: ${target:,.2f}"
        if stop:
            header += f" | Stop: ${stop:,.2f}"

        block = [
            Paragraph(header, styles["BodyText8"]),
            Paragraph(f"<font color='#475569'>{reasoning}</font>", styles["CellText"]),
            Spacer(1, 6),
        ]
        elements.append(KeepTogether(block))

    return elements


# ── Insider & Social Sentiment ───────────────────────────────────────────────

def _build_social_sentiment(styles, equities):
    elements = []

    has_social = [s for s in equities if not s.get("error") and (
        s.get("insider_signal", "NONE") != "NONE" or s.get("st_sentiment", "UNKNOWN") != "UNKNOWN"
    )]

    if not has_social:
        elements.append(Paragraph("No insider or social sentiment data available.", styles["BodyText8"]))
        return elements

    # Insider activity
    insider_active = [s for s in equities if not s.get("error") and s.get("insider_signal", "NONE") != "NONE"]
    if insider_active:
        elements.append(Paragraph("Insider Trading (Last 30 Days)", styles["SubHead"]))
        headers = ["Ticker", "Buys", "Sells", "Signal", "Recent Trades"]
        rows = [headers]

        signal_order = {"STRONG_BUY": 0, "NET_BUY": 1, "MIXED": 2, "NET_SELL": 3, "HEAVY_SELL": 4}
        insider_active.sort(key=lambda x: signal_order.get(x.get("insider_signal", "MIXED"), 5))

        for s in insider_active:
            trades = s.get("insider_trades", [])
            recent = "; ".join(
                f"{t['action']} {t['shares']} ({t['owner'][:15]})"
                for t in trades[:2]
            ) if trades else "--"

            rows.append([
                s["ticker"], str(s.get("insider_buys", 0)), str(s.get("insider_sells", 0)),
                s.get("insider_signal", "NONE"), recent[:50],
            ])

        col_widths = [0.7*inch, 0.5*inch, 0.5*inch, 1*inch, 3.8*inch]
        t = Table(rows, colWidths=col_widths, repeatRows=1)
        style_cmds = _base_table_style()
        _alt_row_colors(style_cmds, len(rows))
        for i in range(1, len(rows)):
            sig = insider_active[i-1].get("insider_signal", "")
            if sig in ("STRONG_BUY", "NET_BUY"):
                style_cmds.append(("TEXTCOLOR", (3, i), (3, i), GREEN))
            elif sig in ("HEAVY_SELL", "NET_SELL"):
                style_cmds.append(("TEXTCOLOR", (3, i), (3, i), RED))
        t.setStyle(TableStyle(style_cmds))
        elements.append(t)
        elements.append(Spacer(1, 12))

    # StockTwits
    st_active = [s for s in equities if not s.get("error") and s.get("st_sentiment", "UNKNOWN") != "UNKNOWN"]
    if st_active:
        elements.append(Paragraph("StockTwits Social Sentiment", styles["SubHead"]))
        headers = ["Ticker", "Sentiment", "Bullish", "Bearish", "Messages"]
        rows = [headers]
        for s in st_active:
            rows.append([
                s["ticker"], s.get("st_sentiment", "UNKNOWN"),
                str(s.get("st_bullish", 0)), str(s.get("st_bearish", 0)),
                str(s.get("st_volume", 0)),
            ])
        col_widths = [0.8*inch, 1.2*inch, 0.8*inch, 0.8*inch, 0.8*inch]
        t = Table(rows, colWidths=col_widths, repeatRows=1)
        style_cmds = _base_table_style()
        _alt_row_colors(style_cmds, len(rows))
        for i in range(1, len(rows)):
            sent = st_active[i-1].get("st_sentiment", "")
            if "BULLISH" in sent:
                style_cmds.append(("TEXTCOLOR", (1, i), (1, i), GREEN))
            elif "BEARISH" in sent:
                style_cmds.append(("TEXTCOLOR", (1, i), (1, i), RED))
        t.setStyle(TableStyle(style_cmds))
        elements.append(t)

    return elements


# ── Earnings Calendar ────────────────────────────────────────────────────────

def _build_earnings_calendar(styles, all_stocks):
    elements = []

    earners = [s for s in all_stocks if s.get("earnings_date") and not s.get("error")]
    earners.sort(key=lambda x: x["earnings_date"])

    if not earners:
        elements.append(Paragraph("No watchlist stocks reporting earnings in the next 14 days.", styles["BodyText8"]))
        return elements

    headers = ["Ticker", "Earnings Date", "Price", "WoW%", "Within 7d"]
    rows = [headers]
    for s in earners:
        rows.append([
            s["ticker"], s["earnings_date"], _fmt_price(s.get("current_price")),
            _fmt_pct(s.get("wow_change_pct")),
            "YES" if s.get("earnings_within_7d") else "No",
        ])

    col_widths = [1*inch, 1.3*inch, 1*inch, 0.9*inch, 0.9*inch]
    t = Table(rows, colWidths=col_widths, repeatRows=1)
    style_cmds = _base_table_style()
    _alt_row_colors(style_cmds, len(rows))
    for i in range(1, len(rows)):
        if earners[i-1].get("earnings_within_7d"):
            style_cmds.append(("BACKGROUND", (4, i), (4, i), LIGHT_YELLOW))
    t.setStyle(TableStyle(style_cmds))
    elements.append(t)

    return elements


# ── Performance Tracking ─────────────────────────────────────────────────────

def _build_performance_tracking(styles, equities):
    elements = []

    # Trailing returns
    elements.append(Paragraph("Trailing Returns", styles["SubHead"]))
    headers = ["Ticker", "Price", "1-Week", "1-Month", "3-Month"]
    rows = [headers]
    valid_equities = [s for s in equities if not s.get("error")]

    for s in valid_equities:
        tr = s.get("trailing_returns", {})
        rows.append([
            s["ticker"], _fmt_price(s.get("current_price")),
            _fmt_pct(tr.get("1w")), _fmt_pct(tr.get("1m")), _fmt_pct(tr.get("3m")),
        ])

    if len(rows) > 1:
        col_widths = [0.8*inch, 1*inch, 0.9*inch, 0.9*inch, 0.9*inch]
        t = Table(rows, colWidths=col_widths, repeatRows=1)
        style_cmds = _base_table_style()
        _alt_row_colors(style_cmds, len(rows))
        for i in range(1, len(rows)):
            tr = valid_equities[i-1].get("trailing_returns", {})
            for col_idx, key in [(2, "1w"), (3, "1m"), (4, "3m")]:
                val = tr.get(key)
                if val is not None:
                    style_cmds.append(("TEXTCOLOR", (col_idx, i), (col_idx, i), _pct_color(val)))
        t.setStyle(TableStyle(style_cmds))
        elements.append(t)
    elements.append(Spacer(1, 12))

    # Signal scorecard + Open positions side by side
    elements.append(Paragraph("Signal Scorecard", styles["SubHead"]))
    try:
        perf = get_performance_summary()
        if perf and perf.get("total_signals", 0) > 0:
            scorecard = [
                ["Metric", "Value"],
                ["Total Signals", str(perf.get("total_signals", 0))],
                ["Win Rate", f"{perf.get('win_rate', 0):.1f}%"],
                ["Avg Win", _fmt_pct(perf.get("avg_win_pct"))],
                ["Avg Loss", _fmt_pct(perf.get("avg_loss_pct"))],
                ["Best Trade", _fmt_pct(perf.get("best_trade"))],
                ["Worst Trade", _fmt_pct(perf.get("worst_trade"))],
            ]
            t = Table(scorecard, colWidths=[2*inch, 2*inch])
            style_cmds = _base_table_style()
            _alt_row_colors(style_cmds, len(scorecard))
            t.setStyle(TableStyle(style_cmds))
            elements.append(t)
        else:
            elements.append(Paragraph("No signal history available yet.", styles["BodyText8"]))
    except Exception:
        elements.append(Paragraph("Signal performance data unavailable.", styles["BodyText8"]))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("Open Positions", styles["SubHead"]))
    try:
        open_sigs = get_open_signals()
        if open_sigs:
            headers = ["Ticker", "Entry", "Target", "Stop", "Signal Date"]
            rows = [headers]
            for sig in open_sigs:
                rows.append([
                    sig.get("ticker", "?"), _fmt_price(sig.get("current_price")),
                    _fmt_price(sig.get("price_target")), _fmt_price(sig.get("stop_loss")),
                    str(sig.get("signaled_at", ""))[:10],
                ])
            col_widths = [0.8*inch, 1*inch, 1*inch, 1*inch, 1*inch]
            t = Table(rows, colWidths=col_widths, repeatRows=1)
            style_cmds = _base_table_style()
            _alt_row_colors(style_cmds, len(rows))
            t.setStyle(TableStyle(style_cmds))
            elements.append(t)
        else:
            elements.append(Paragraph("No open positions.", styles["BodyText8"]))
    except Exception:
        elements.append(Paragraph("Open positions data unavailable.", styles["BodyText8"]))

    return elements


# ── Main Generator ───────────────────────────────────────────────────────────

def generate_watchlist_pdf(
    equities: list[dict],
    etfs: list[dict],
    market_context: dict,
    analyses: list[dict],
) -> str:
    """Generate the full watchlist PDF report. Returns the file path."""
    os.makedirs(PDF_OUTPUT_DIR, exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"watchlist_{date_str}.pdf"
    filepath = os.path.join(PDF_OUTPUT_DIR, filename)

    doc = SimpleDocTemplate(
        filepath,
        pagesize=letter,
        topMargin=0.5 * inch,
        bottomMargin=0.6 * inch,
        leftMargin=0.5 * inch,
        rightMargin=0.5 * inch,
    )

    styles = _make_styles()
    elements = []
    all_stocks = equities + etfs

    # ── Page 1: Title + Executive Summary + Market Overview
    elements.append(Paragraph("Daily Watchlist Report", styles["ReportTitle"]))
    elements.append(Paragraph(datetime.now().strftime("%B %d, %Y \u2014 %I:%M %p"), styles["ReportDate"]))
    elements.extend(_build_executive_summary(styles, market_context, equities, etfs, analyses))
    elements.extend(_build_market_overview(styles, market_context, equities, etfs))
    elements.append(PageBreak())

    # ── Pages 2-3: Equity Table
    elements.append(Paragraph("Equity Watchlist", styles["SectionHead"]))
    elements.extend(_build_equity_table(styles, equities))
    elements.append(PageBreak())

    # ── Page 4: ETF Table + Top Movers (combined to avoid sparse pages)
    elements.append(Paragraph("ETF Portfolio", styles["SectionHead"]))
    elements.extend(_build_etf_table(styles, etfs))
    elements.append(_divider())
    elements.append(Paragraph("Top Movers", styles["SectionHead"]))
    elements.extend(_build_top_movers(styles, all_stocks))
    elements.append(PageBreak())

    # ── Pages 5-6: AI Analysis
    elements.append(Paragraph("AI Analysis & Signals", styles["SectionHead"]))
    elements.extend(_build_ai_analysis(styles, analyses))
    elements.append(PageBreak())

    # ── Page 7: Insider & Social + Earnings (combined)
    elements.append(Paragraph("Insider & Social Sentiment", styles["SectionHead"]))
    elements.extend(_build_social_sentiment(styles, equities))
    elements.append(_divider())
    elements.append(Paragraph("Earnings Calendar", styles["SectionHead"]))
    elements.extend(_build_earnings_calendar(styles, all_stocks))
    elements.append(PageBreak())

    # ── Page 8: Performance Tracking
    elements.append(Paragraph("Performance Tracking", styles["SectionHead"]))
    elements.extend(_build_performance_tracking(styles, equities))

    doc.build(elements, onFirstPage=_page_footer, onLaterPages=_page_footer)
    print(f"PDF report generated: {filepath}")
    return filepath
