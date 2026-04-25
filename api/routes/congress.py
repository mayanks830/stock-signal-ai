import time
from fastapi import APIRouter, Query

from congress import fetch_congressional_trades

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
