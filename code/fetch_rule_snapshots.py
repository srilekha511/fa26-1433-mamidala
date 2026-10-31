"""Download one Wayback snapshot per month of each study subreddit's sidebar and rules pages.

Usage: python3 code/fetch_rule_snapshots.py [subreddit ...]
With subreddits, fetches only those and replaces their rows in the existing index.
Saves raw HTML to data/raw/wayback/<subreddit>/<kind>/<timestamp>.html and an index of
snapshot URLs to data/raw/wayback/index.csv.
"""

import csv
import sys
import time

import wayback
from reddit_subreddits import FIRST_MONTH, LAST_MONTH, ROOT, study_subreddits

OUT = ROOT / "data" / "raw" / "wayback"
# Start a year early so a rule already in place in January 2022 still has a dated first appearance.
FIRST_YEAR, LAST_YEAR = int(FIRST_MONTH[:4]) - 1, int(LAST_MONTH[:4])


def main(subs=None):
    index = []
    if subs and (OUT / "index.csv").exists():
        with open(OUT / "index.csv", newline="") as f:
            index = [r for r in csv.DictReader(f) if r["subreddit"] not in subs]
    for sub in subs or study_subreddits():
        for kind, template in wayback.PAGES.items():
            snaps = wayback.list_snapshots(template.format(sub=sub), FIRST_YEAR, LAST_YEAR)
            print(sub, kind, len(snaps), "snapshots")
            time.sleep(2)
            for s in snaps:
                url = wayback.snapshot_url(s["timestamp"], s["original"])
                path = OUT / sub / kind / f"{s['timestamp']}.html"
                if not path.exists():
                    try:
                        text = wayback.fetch_text(url)
                    except RuntimeError as e:  # e.g. a snapshot the archive now blocks (HTTP 403)
                        print(f"  skipped: {e}")
                        continue
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(text)
                    time.sleep(2)
                index.append({"subreddit": sub, "kind": kind, "timestamp": s["timestamp"], "snapshot_url": url})
    with open(OUT / "index.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["subreddit", "kind", "timestamp", "snapshot_url"])
        w.writeheader()
        w.writerows(index)
    print(f"indexed {len(index)} snapshots")


if __name__ == "__main__":
    main(sys.argv[1:])
