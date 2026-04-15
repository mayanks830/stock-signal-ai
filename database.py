import sqlite3
import json
import os
from datetime import datetime
from config import DB_PATH


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS signals (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker                  TEXT NOT NULL,
            name                    TEXT,
            sector                  TEXT,
            confidence              TEXT,
            signaled_at             TEXT NOT NULL,
            current_price           REAL NOT NULL,
            price_target            REAL,
            stop_loss               REAL,
            wow_change_pct          REAL,
            volume_ratio            REAL,
            range_position          REAL,
            relative_strength_vs_spy REAL,
            earnings_within_7d      INTEGER DEFAULT 0,
            earnings_date           TEXT,
            sentiment_score         REAL,
            vix_at_signal           REAL,
            spy_wow_pct             REAL,
            trend_1d                TEXT,
            trend_1w                TEXT,
            trend_1m                TEXT,
            reason                  TEXT,
            risk                    TEXT,
            news_json               TEXT
        );

        CREATE TABLE IF NOT EXISTS signal_performance (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_id       INTEGER NOT NULL REFERENCES signals(id),
            checked_at      TEXT NOT NULL,
            price_at_check  REAL NOT NULL,
            pct_change      REAL NOT NULL,
            hit_target      INTEGER DEFAULT 0,
            hit_stop        INTEGER DEFAULT 0,
            outcome         TEXT DEFAULT 'OPEN'
        );
        """)
    print("Database initialized.")


def save_signal(signal: dict, market_context: dict = None) -> int:
    ctx = market_context or {}
    with get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO signals (
                ticker, name, sector, confidence, signaled_at,
                current_price, price_target, stop_loss, wow_change_pct,
                volume_ratio, range_position, relative_strength_vs_spy,
                earnings_within_7d, earnings_date, sentiment_score,
                vix_at_signal, spy_wow_pct,
                trend_1d, trend_1w, trend_1m,
                reason, risk, news_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            signal.get("ticker"),
            signal.get("name"),
            signal.get("sector"),
            signal.get("confidence"),
            datetime.now().isoformat(),
            signal.get("current_price"),
            signal.get("price_target"),
            signal.get("stop_loss"),
            signal.get("wow_change_pct"),
            signal.get("volume_ratio"),
            signal.get("range_position"),
            signal.get("relative_strength_vs_spy"),
            1 if signal.get("earnings_within_7d") else 0,
            signal.get("earnings_date"),
            signal.get("sentiment_score"),
            ctx.get("vix"),
            ctx.get("spy_wow_pct"),
            signal.get("trend_1d"),
            signal.get("trend_1w"),
            signal.get("trend_1m"),
            signal.get("reason"),
            signal.get("risk"),
            json.dumps(signal.get("news", [])),
        ))
        return cur.lastrowid


def get_recent_signal_tickers(days: int) -> set:
    cutoff = datetime.now().isoformat()[:10]
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT ticker FROM signals WHERE date(signaled_at) >= date(?, ?)",
            (cutoff, f"-{days} days")
        ).fetchall()
    return {r["ticker"] for r in rows}


def get_all_signals(limit: int = 50, offset: int = 0) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM signals ORDER BY signaled_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        ).fetchall()
    return [dict(r) for r in rows]


def get_signal_by_id(signal_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM signals WHERE id = ?", (signal_id,)).fetchone()
    return dict(row) if row else None


def get_open_signals() -> list[dict]:
    """Signals that haven't reached a final WIN/LOSS outcome."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT s.*, p.pct_change, p.outcome, p.price_at_check
            FROM signals s
            LEFT JOIN signal_performance p ON p.signal_id = s.id
              AND p.id = (SELECT MAX(id) FROM signal_performance WHERE signal_id = s.id)
            WHERE COALESCE(p.outcome, 'OPEN') = 'OPEN'
            ORDER BY s.signaled_at DESC
        """).fetchall()
    return [dict(r) for r in rows]


def save_performance(signal_id: int, price: float, pct_change: float,
                     hit_target: bool, hit_stop: bool, outcome: str) -> None:
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO signal_performance
              (signal_id, checked_at, price_at_check, pct_change, hit_target, hit_stop, outcome)
            VALUES (?,?,?,?,?,?,?)
        """, (
            signal_id,
            datetime.now().isoformat(),
            price,
            pct_change,
            1 if hit_target else 0,
            1 if hit_stop else 0,
            outcome,
        ))


def get_performance_summary() -> dict:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT sp.outcome, sp.pct_change, sp.hit_target, sp.hit_stop, s.ticker
            FROM signal_performance sp
            JOIN signals s ON s.id = sp.signal_id
            WHERE sp.outcome IN ('WIN', 'LOSS')
              AND sp.id IN (SELECT MAX(id) FROM signal_performance GROUP BY signal_id)
        """).fetchall()

    results = [dict(r) for r in rows]
    wins = [r for r in results if r["outcome"] == "WIN"]
    losses = [r for r in results if r["outcome"] == "LOSS"]
    total = len(results)

    return {
        "total_signals": total,
        "win_count": len(wins),
        "loss_count": len(losses),
        "win_rate": round(len(wins) / total * 100, 1) if total else 0,
        "avg_win_pct": round(sum(r["pct_change"] for r in wins) / len(wins), 2) if wins else 0,
        "avg_loss_pct": round(sum(r["pct_change"] for r in losses) / len(losses), 2) if losses else 0,
        "best_trade": max((r["pct_change"] for r in results), default=0),
        "worst_trade": min((r["pct_change"] for r in results), default=0),
    }


def get_all_performance() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT s.ticker, s.name, s.sector, s.confidence, s.signaled_at,
                   s.current_price AS entry_price, s.price_target, s.stop_loss,
                   p.price_at_check AS exit_price, p.pct_change, p.outcome,
                   p.hit_target, p.hit_stop, p.checked_at
            FROM signals s
            LEFT JOIN signal_performance p ON p.signal_id = s.id
              AND p.id = (SELECT MAX(id) FROM signal_performance WHERE signal_id = s.id)
            ORDER BY s.signaled_at DESC
        """).fetchall()
    return [dict(r) for r in rows]
