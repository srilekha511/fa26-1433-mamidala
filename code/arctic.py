"""Client for the Arctic Shift Reddit archive API (https://arctic-shift.photon-reddit.com).

Retries rate-limit replies, pages through a time window newest-first, and caches each
subreddit-month as one JSONL file so long pulls can be stopped and resumed.
"""

import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://arctic-shift.photon-reddit.com/api"
HEADERS = {"User-Agent": "fa26-1433 research project"}
PAUSE = 3  # seconds to wait after every successful request
PAGE = 100


def http_get_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def get(endpoint, params, fetch=http_get_json, sleep=time.sleep, tries=6):
    """Return the `data` list for one request, retrying errors and rate-limit replies."""
    url = f"{BASE}/{endpoint}?" + urllib.parse.urlencode(params)
    for attempt in range(tries):
        try:
            body = fetch(url)
            if body.get("data") is not None and not body.get("error"):
                sleep(PAUSE)
                return body["data"]
            print(f"  retry {attempt + 1}: {body.get('error')}")
        except Exception as e:
            print(f"  retry {attempt + 1}: {e}")
        sleep(15 * (attempt + 1))
    raise RuntimeError(f"failed after {tries} tries: {url}")


def iter_window(endpoint, subreddit, after, before, **kw):
    """Yield every item with after < created_utc < before (epoch seconds), newest first.

    Pages run backwards in time because Arctic Shift times out on oldest-first queries over
    large subreddit-months. The next page ends one second after the oldest timestamp seen,
    so posts sharing a timestamp across a page edge are not skipped; ids already yielded
    are dropped.
    """
    seen = set()
    cursor = before
    while True:
        page = get(endpoint, {"subreddit": subreddit, "after": after, "before": cursor,
                              "limit": PAGE, "sort": "desc"}, **kw)
        new = [x for x in page if x["id"] not in seen]
        for x in new:
            seen.add(x["id"])
            yield x
        if len(page) < PAGE:
            return
        oldest = int(page[-1]["created_utc"])
        cursor = oldest + 1 if new and oldest + 1 < cursor else oldest


def months(first, last):
    """Inclusive list of "YYYY-MM" strings from first to last."""
    y, m = map(int, first.split("-"))
    out = []
    while f"{y:04d}-{m:02d}" <= last:
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def month_bounds(month):
    """(epoch of the month's first second, epoch of the next month's first second), UTC."""
    y, m = map(int, month.split("-"))
    start = datetime(y, m, 1, tzinfo=timezone.utc)
    end = datetime(y + (m == 12), m % 12 + 1, 1, tzinfo=timezone.utc)
    return int(start.timestamp()), int(end.timestamp())


def fetch_month(endpoint, subreddit, month, out_dir, **kw):
    """Save every item from one subreddit-month to out_dir/subreddit/month.jsonl.

    Skips months already saved. Writes to a .partial file first, so an interrupted
    month is redone on the next run instead of being left half-saved.
    """
    path = Path(out_dir) / subreddit / f"{month}.jsonl"
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    start, end = month_bounds(month)
    tmp = path.with_suffix(".partial")
    with open(tmp, "w") as f:
        for x in iter_window(endpoint, subreddit, start - 1, end, **kw):
            if start <= int(x["created_utc"]) < end:
                f.write(json.dumps(x) + "\n")
    tmp.rename(path)
    return path


def count_gaps(local, remote, tolerance=0.05):
    """Months whose saved item count falls short of the API's own count by more than `tolerance`.

    Small shortfalls are expected: the API buckets its counts at local, not UTC, midnight.
    """
    return sorted(m for m, n in remote.items() if local.get(m, 0) < n * (1 - tolerance))
