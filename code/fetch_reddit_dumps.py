"""Pull every post or comment in the study subreddits, one month at a time.

Usage:
  python3 code/fetch_reddit_dumps.py size        # count posts and comments first
  python3 code/fetch_reddit_dumps.py posts
  python3 code/fetch_reddit_dumps.py comments
  python3 code/fetch_reddit_dumps.py check       # compare saved post months with the API's counts
Months already saved are skipped, so a stopped run can simply be restarted.
"""

import calendar
import csv
import sys
import time

import arctic
from reddit_subreddits import FIRST_MONTH, LAST_MONTH, ROOT, study_subreddits

RAW = ROOT / "data" / "raw" / "arctic"
DERIVED = ROOT / "data" / "derived"
ENDPOINT = {"posts": "posts/search", "comments": "comments/search"}
SECONDS_PER_PAGE = 9  # measured on a large subreddit, including rate-limit retries


def monthly_counts(endpoint, sub, get=None):
    """The API's own item count for each month (date strings: epoch seconds return zeros).

    Asks one year at a time: a four-year aggregate over a busy subreddit times out (HTTP 422).
    """
    get = get or arctic.get
    data = []
    for year in range(int(FIRST_MONTH[:4]), int(LAST_MONTH[:4]) + 1):
        data += get(endpoint + "/aggregate", {"aggregate": "created_utc", "frequency": "month",
                                              "subreddit": sub, "after": f"{year}-01-01",
                                              "before": f"{year + 1}-01-01"})
    out = {}
    for row in data:
        # Buckets are labelled at local midnight (e.g. 2023-12-31T23:00Z for January 2024),
        # so shift by a few hours before taking the month.
        ts = calendar.timegm(time.strptime(row["created_utc"][:19], "%Y-%m-%dT%H:%M:%S"))
        out[time.strftime("%Y-%m", time.gmtime(ts + 6 * 3600))] = int(row["count"])
    return out


def size():
    DERIVED.mkdir(parents=True, exist_ok=True)
    rows = []
    for sub in study_subreddits():
        for kind, endpoint in ENDPOINT.items():
            try:
                n = sum(monthly_counts(endpoint, sub).values())
            except RuntimeError as e:
                print(f"could not count {kind} for r/{sub}: {e}")
                continue
            rows.append({"subreddit": sub, "kind": kind, "count": n})
            print(rows[-1])
    with open(DERIVED / "reddit_volume.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["subreddit", "kind", "count"])
        w.writeheader()
        w.writerows(rows)
    for kind in ENDPOINT:
        n = sum(r["count"] for r in rows if r["kind"] == kind)
        print(f"{kind}: {n:,} items, about {n / 100 * SECONDS_PER_PAGE / 3600:.1f} hours to pull")


def pull(kind):
    for sub in study_subreddits():
        for month in arctic.months(FIRST_MONTH, LAST_MONTH):
            path = arctic.fetch_month(ENDPOINT[kind], sub, month, RAW / kind)
            print(sub, month, sum(1 for _ in open(path)))


def check():
    """Print saved post months that hold noticeably fewer posts than the API reports."""
    bad = 0
    for sub in study_subreddits():
        local = {p.stem: sum(1 for _ in open(p)) for p in (RAW / "posts" / sub).glob("*.jsonl")}
        for month in arctic.count_gaps(local, monthly_counts(ENDPOINT["posts"], sub)):
            bad += 1
            print(f"r/{sub} {month}: saved {local.get(month, 0)}; delete the file and rerun `posts`")
    print(f"{bad} incomplete months")


if __name__ == "__main__":
    cmd = sys.argv[1]
    {"size": size, "check": check}.get(cmd, lambda: pull(cmd))()
