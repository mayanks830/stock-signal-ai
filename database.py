import sqlite3
import json
import os
import hashlib
import secrets
from datetime import datetime
from config import DB_PATH


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker      TEXT NOT NULL UNIQUE,
            category    TEXT NOT NULL DEFAULT 'equity',
            added_at    TEXT NOT NULL
        );

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
            news_json               TEXT,
            analysis_json           TEXT,
            signal_type             TEXT DEFAULT 'MOMENTUM',
            signal                  TEXT DEFAULT 'BUY'
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

        CREATE TABLE IF NOT EXISTS congress_alerts (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_key       TEXT NOT NULL UNIQUE,
            alerted_at      TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS congress_trades (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            filer           TEXT NOT NULL,
            party           TEXT,
            chamber         TEXT,
            ticker          TEXT NOT NULL,
            action          TEXT NOT NULL,
            tx_date         TEXT NOT NULL,
            amount          TEXT,
            value_numeric   REAL,
            price_at_trade  REAL,
            price_current   REAL,
            return_pct      REAL,
            updated_at      TEXT,
            UNIQUE(filer, ticker, action, tx_date)
        );

        CREATE TABLE IF NOT EXISTS users (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            username        TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash   TEXT NOT NULL,
            created_at      TEXT NOT NULL,
            is_approved     INTEGER DEFAULT 0
        );
        """)
    # Migrations for existing databases
    _migrate(conn)
    seed_watchlist_from_config()
    print("Database initialized.")


def _migrate(conn: sqlite3.Connection) -> None:
    """Add columns that may be missing from older databases."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(signals)").fetchall()}
    if "analysis_json" not in cols:
        conn.execute("ALTER TABLE signals ADD COLUMN analysis_json TEXT")
    if "signal_type" not in cols:
        conn.execute("ALTER TABLE signals ADD COLUMN signal_type TEXT DEFAULT 'MOMENTUM'")
    if "signal" not in cols:
        conn.execute("ALTER TABLE signals ADD COLUMN signal TEXT DEFAULT 'BUY'")


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
                reason, risk, news_json, analysis_json, signal_type, signal
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
            json.dumps(signal.get("analysis")) if signal.get("analysis") else None,
            signal.get("signal_type", "MOMENTUM"),
            signal.get("signal", "BUY"),
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
        rows = conn.execute("""
            SELECT s.*, COALESCE(p.outcome, 'OPEN') AS outcome, p.pct_change
            FROM signals s
            LEFT JOIN signal_performance p ON p.signal_id = s.id
              AND p.id = (SELECT MAX(id) FROM signal_performance WHERE signal_id = s.id)
            ORDER BY s.signaled_at DESC LIMIT ? OFFSET ?
        """, (limit, offset)).fetchall()
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


# ── Watchlist ────────────────────────────────────────────────────────────────

def get_watchlist(category: str | None = None) -> list[dict]:
    with get_conn() as conn:
        if category:
            rows = conn.execute(
                "SELECT * FROM watchlist WHERE category = ? ORDER BY ticker", (category,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM watchlist ORDER BY category, ticker").fetchall()
    return [dict(r) for r in rows]


def add_to_watchlist(ticker: str, category: str = "equity") -> dict:
    ticker = ticker.upper().strip()
    category = category.lower().strip()
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO watchlist (ticker, category, added_at) VALUES (?, ?, ?)",
            (ticker, category, datetime.now().isoformat()),
        )
    return {"ticker": ticker, "category": category}


def remove_from_watchlist(ticker: str) -> bool:
    ticker = ticker.upper().strip()
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM watchlist WHERE ticker = ?", (ticker,))
    return cur.rowcount > 0


def seed_watchlist_from_config() -> None:
    """Seed watchlist from config.py lists if the table is empty."""
    with get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) FROM watchlist").fetchone()[0]
        if count > 0:
            return

    from config import WATCHLIST_EQUITIES, WATCHLIST_ETFS
    now = datetime.now().isoformat()
    with get_conn() as conn:
        for t in WATCHLIST_EQUITIES:
            conn.execute(
                "INSERT OR IGNORE INTO watchlist (ticker, category, added_at) VALUES (?, 'equity', ?)",
                (t.upper(), now),
            )
        for t in WATCHLIST_ETFS:
            conn.execute(
                "INSERT OR IGNORE INTO watchlist (ticker, category, added_at) VALUES (?, 'etf', ?)",
                (t.upper(), now),
            )


# ── Users ────────────────────────────────────────────────────────────────────

def _hash_password(password: str, salt: str = "") -> str:
    if not salt:
        salt = secrets.token_hex(16)
    h = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
    return f"{salt}${h}"


def _verify_password(password: str, stored: str) -> bool:
    salt = stored.split("$")[0]
    return _hash_password(password, salt) == stored


def create_user(username: str, password: str, auto_approve: bool = False) -> dict | None:
    """Create a new user. Returns user dict or None if username taken."""
    username = username.strip()
    if not username or not password:
        return None
    pw_hash = _hash_password(password)
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO users (username, password_hash, created_at, is_approved) VALUES (?, ?, ?, ?)",
                (username, pw_hash, datetime.now().isoformat(), 1 if auto_approve else 0),
            )
        return {"username": username, "is_approved": auto_approve}
    except sqlite3.IntegrityError:
        return None


def authenticate_user(username: str, password: str) -> dict | None:
    """Verify credentials. Returns user dict or None."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username.strip(),)
        ).fetchone()
    if not row:
        return None
    if not _verify_password(password, row["password_hash"]):
        return None
    return dict(row)


def get_all_users() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT id, username, created_at, is_approved FROM users ORDER BY created_at").fetchall()
    return [dict(r) for r in rows]


def approve_user(username: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute("UPDATE users SET is_approved = 1 WHERE username = ?", (username.strip(),))
    return cur.rowcount > 0


def delete_user(username: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM users WHERE username = ?", (username.strip(),))
    return cur.rowcount > 0


def get_user_count() -> int:
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]


# ── Congress Alerts ──────────────────────────────────────────────────────────

def is_congress_alert_sent(trade_key: str) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT 1 FROM congress_alerts WHERE trade_key = ?", (trade_key,)).fetchone()
    return row is not None


def mark_congress_alert_sent(trade_key: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO congress_alerts (trade_key, alerted_at) VALUES (?, ?)",
            (trade_key, datetime.now().isoformat()),
        )


# ── Congress Trades (performance tracking) ─────────────────────────────────

def upsert_congress_trade(trade: dict) -> bool:
    """Insert a congress trade if not already stored. Returns True if inserted."""
    try:
        with get_conn() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO congress_trades
                  (filer, party, chamber, ticker, action, tx_date, amount, value_numeric, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade.get("filer"),
                trade.get("party"),
                trade.get("chamber"),
                trade.get("ticker"),
                trade.get("action"),
                trade.get("tx_date"),
                trade.get("amount"),
                trade.get("value_numeric"),
                datetime.now().isoformat(),
            ))
        return True
    except Exception:
        return False


def get_congress_trades_needing_prices() -> list[dict]:
    """Get trades that don't have a price_at_trade yet."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, ticker, tx_date FROM congress_trades WHERE price_at_trade IS NULL AND ticker != ''"
        ).fetchall()
    return [dict(r) for r in rows]


def get_congress_tickers() -> list[str]:
    """Get distinct tickers from congress_trades."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT ticker FROM congress_trades WHERE ticker != ''"
        ).fetchall()
    return [r["ticker"] for r in rows]


def update_congress_trade_entry_price(trade_id: int, price: float) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE congress_trades SET price_at_trade = ?, updated_at = ? WHERE id = ?",
            (round(price, 2), datetime.now().isoformat(), trade_id),
        )


def update_congress_current_prices(ticker: str, current_price: float) -> None:
    """Update current price and return_pct for all trades of a ticker."""
    with get_conn() as conn:
        conn.execute("""
            UPDATE congress_trades
            SET price_current = ?,
                return_pct = CASE
                    WHEN price_at_trade IS NOT NULL AND price_at_trade > 0
                    THEN ROUND((? - price_at_trade) / price_at_trade * 100, 2)
                    ELSE NULL
                END,
                updated_at = ?
            WHERE ticker = ?
        """, (round(current_price, 2), current_price, datetime.now().isoformat(), ticker))


def get_senator_leaderboard() -> list[dict]:
    """Get senators ranked by average return on BUY trades."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT
                filer,
                party,
                chamber,
                COUNT(*) as trade_count,
                ROUND(AVG(return_pct), 2) as avg_return_pct,
                MAX(return_pct) as best_return_pct,
                SUM(value_numeric) as total_value
            FROM congress_trades
            WHERE action = 'BUY'
              AND return_pct IS NOT NULL
            GROUP BY filer
            HAVING trade_count >= 1
            ORDER BY avg_return_pct DESC
        """).fetchall()

        results = []
        for r in rows:
            row = dict(r)
            best = conn.execute("""
                SELECT ticker, return_pct FROM congress_trades
                WHERE filer = ? AND action = 'BUY' AND return_pct IS NOT NULL
                ORDER BY return_pct DESC LIMIT 1
            """, (row["filer"],)).fetchone()
            row["best_ticker"] = best["ticker"] if best else None
            row["best_return_pct"] = best["return_pct"] if best else None
            results.append(row)

    return results


def get_senator_trades(filer: str) -> list[dict]:
    """Get all BUY trades for a specific senator with returns."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT ticker, tx_date, amount, value_numeric,
                   price_at_trade, price_current, return_pct
            FROM congress_trades
            WHERE filer = ? AND action = 'BUY'
            ORDER BY tx_date DESC
        """, (filer,)).fetchall()
    return [dict(r) for r in rows]
