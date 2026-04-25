import time
import requests


def fetch_with_retry(url, headers=None, timeout=10, max_retries=3, method="get", **kwargs):
    """
    HTTP request with exponential backoff retry.
    Retries on 429, 500, 502, 503, 504 and connection/timeout errors.
    """
    retryable_statuses = {429, 500, 502, 503, 504}
    backoff = 1

    for attempt in range(max_retries + 1):
        try:
            resp = getattr(requests, method)(url, headers=headers, timeout=timeout, **kwargs)
            if resp.status_code not in retryable_statuses or attempt == max_retries:
                return resp
            print(f"  [retry] {method.upper()} {url[:80]} → {resp.status_code}, retrying in {backoff}s...")
        except (requests.ConnectionError, requests.Timeout) as e:
            if attempt == max_retries:
                raise
            print(f"  [retry] {method.upper()} {url[:80]} → {type(e).__name__}, retrying in {backoff}s...")

        time.sleep(backoff)
        backoff *= 2

    return resp
