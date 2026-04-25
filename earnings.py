from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from utils import fetch_with_retry

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def get_earnings_dates(tickers: list[str]) -> dict[str, str]:
    """
    Returns {ticker: earnings_date_str} for tickers with earnings in the next 14 days.
    Uses StockAnalysis.com earnings calendar (free, no key).
    """
    earnings_map = {}
    try:
        url = "https://stockanalysis.com/stocks/earnings-calendar/"
        resp = fetch_with_retry(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return {}

        soup = BeautifulSoup(resp.text, "lxml")
        table = soup.find("table")
        if not table:
            return {}

        ticker_set = set(t.upper() for t in tickers)
        today = datetime.now().date()
        cutoff = today + timedelta(days=14)

        for row in table.find_all("tr")[1:]:
            cols = row.find_all("td")
            if len(cols) < 3:
                continue
            ticker = cols[0].get_text(strip=True).upper()
            date_str = cols[2].get_text(strip=True)
            if ticker not in ticker_set:
                continue
            try:
                earn_date = datetime.strptime(date_str, "%b %d, %Y").date()
                if today <= earn_date <= cutoff:
                    earnings_map[ticker] = earn_date.isoformat()
            except ValueError:
                continue

    except Exception as e:
        print(f"  [!] Earnings calendar fetch failed: {e}")

    return earnings_map
