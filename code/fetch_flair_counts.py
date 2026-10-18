"""Download monthly post counts (all posts and AI-flaired posts) for subreddits
from the Arctic Shift Reddit archive API.

Usage: python3 code/fetch_flair_counts.py
Writes data/raw/flair_counts.csv with columns subreddit, month, all_posts, ai_flair_posts.
"""

import calendar
import csv
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://arctic-shift.photon-reddit.com/api/posts/search/aggregate"
SUBREDDITS = ["wallpaper", "wallpapers"]
YEARS = [2022, 2023, 2024, 2025]
END = "2025-10-01"
OUT = Path(__file__).resolve().parent.parent / "data" / "raw" / "flair_counts.csv"


def monthly_counts(subreddit, after, before, flair=None):
    params = {"aggregate": "created_utc", "frequency": "month",
              "subreddit": subreddit, "after": after, "before": before}
    if flair:
        params["link_flair_text"] = flair
    url = API + "?" + urllib.parse.urlencode(params)
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "fa26-1433 research project"})
            with urllib.request.urlopen(req, timeout=120) as r:
                body = json.load(r)
            if body.get("data") is not None:
                # Buckets are labelled at local midnight (e.g. 2023-12-31T23:00Z for
                # January 2024), so shift by a few hours before taking the month.
                out = {}
                for row in body["data"]:
                    ts = time.strptime(row["created_utc"][:19], "%Y-%m-%dT%H:%M:%S")
                    month = time.strftime("%Y-%m", time.gmtime(calendar.timegm(ts) + 6 * 3600))
                    out[month] = int(row["count"])
                return out
            print(f"  retry {attempt + 1}: {body.get('error')}")
        except Exception as e:
            print(f"  retry {attempt + 1}: {e}")
        time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"failed: {url}")


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for sub in SUBREDDITS:
        for y in YEARS:
            after, before = f"{y}-01-01", min(f"{y + 1}-01-01", END)
            print(sub, y)
            total = monthly_counts(sub, after, before)
            time.sleep(3)
            ai = monthly_counts(sub, after, before, flair="AI")
            time.sleep(3)
            for m in sorted(total):
                rows.append([sub, m, total[m], ai.get(m, 0)])
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["subreddit", "month", "all_posts", "ai_flair_posts"])
        w.writerows(rows)
    print(f"wrote {len(rows)} rows to {OUT}")


if __name__ == "__main__":
    main()
