from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from database import get_watchlist, add_to_watchlist, remove_from_watchlist

router = APIRouter()


class WatchlistItem(BaseModel):
    ticker: str
    category: str = "equity"


@router.get("/watchlist")
def list_watchlist(category: str | None = Query(None)):
    return get_watchlist(category)


@router.post("/watchlist")
def add_watchlist_item(item: WatchlistItem):
    return add_to_watchlist(item.ticker, item.category)


@router.delete("/watchlist/{ticker}")
def delete_watchlist_item(ticker: str):
    removed = remove_from_watchlist(ticker)
    if not removed:
        raise HTTPException(status_code=404, detail=f"{ticker} not found in watchlist")
    return {"removed": ticker}
