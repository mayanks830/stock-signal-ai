import time
from fastapi import APIRouter, Query, Path

from congress import fetch_congressional_trades
from database import get_senator_leaderboard, get_senator_trades

router = APIRouter()

# ── In-memory cache ──────────────────────────────────────────────────────────
# Keyed by asset_type so different filters get separate caches
_congress_cache: dict[str, tuple[float, list[dict]]] = {}
_CONGRESS_TTL = 600  # 10 minutes


@router.get("/congress")
def get_congress_trades(
    limit: int = Query(50, ge=1, le=200),
    asset_type: str = Query("", alias="assetType"),
):
    """Return recent congressional stock trades, optionally filtered by asset type."""
    global _congress_cache
    now = time.time()
    cache_key = asset_type or "_all"

    if cache_key in _congress_cache:
        ts, cached = _congress_cache[cache_key]
        if now - ts < _CONGRESS_TTL:
            return {"trades": cached[:limit], "total": len(cached), "cached": True}

    trades = fetch_congressional_trades(
        page_size=limit,
        asset_type=asset_type or None,
    )
    _congress_cache[cache_key] = (now, trades)

    return {"trades": trades[:limit], "total": len(trades), "cached": False}


@router.post("/congress/enrich")
def trigger_enrich():
    """Manually trigger congress trade enrichment."""
    from congress import enrich_congress_trades
    result = enrich_congress_trades()
    return result


@router.get("/congress/leaderboard")
def congress_leaderboard():
    """Return senators ranked by average return on BUY trades."""
    return get_senator_leaderboard()


@router.get("/congress/senator/{name}")
def congress_senator(name: str = Path(...)):
    """Return a senator's BUY trades with returns."""
    trades = get_senator_trades(name)
    if not trades:
        return {"filer": name, "trades": [], "avg_return_pct": None}

    returns = [t["return_pct"] for t in trades if t["return_pct"] is not None]
    avg_return = round(sum(returns) / len(returns), 2) if returns else None

    return {
        "filer": name,
        "avg_return_pct": avg_return,
        "trade_count": len(trades),
        "trades": trades,
    }
