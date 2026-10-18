"""Find seed subreddits that have an AI post flair.

Samples the last 100 posts of every month, 2022-2025, for each seed subreddit, and
tallies their flairs. Raw pages are cached in data/raw/arctic/flair_sample/.

Usage: python3 code/find_ai_flair_subreddits.py
Writes data/derived/flair_inventory.csv (every flair) and data/derived/ai_flairs_draft.csv
(flairs matching AI keywords, to review by hand into data/hand_coded/ai_flairs.csv).
"""

import csv
import json
from pathlib import Path

import arctic
from reddit_subreddits import FIRST_MONTH, LAST_MONTH, ROOT, SEED_SUBREDDITS
from reddit_text import is_ai_text, tally_flairs

CACHE = ROOT / "data" / "raw" / "arctic" / "flair_sample"
DERIVED = ROOT / "data" / "derived"


def sample_month(sub, month):
    path = CACHE / sub / f"{month}.json"
    if path.exists():
        return json.loads(path.read_text())
    start, end = arctic.month_bounds(month)
    page = arctic.get("posts/search", {"subreddit": sub, "after": start - 1, "before": end,
                                       "limit": 100, "sort": "desc"})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(page))
    return page


def main():
    DERIVED.mkdir(parents=True, exist_ok=True)
    inventory = []
    for sub in SEED_SUBREDDITS:
        print(sub)
        samples = [(m, p.get("link_flair_text"))
                   for m in arctic.months(FIRST_MONTH, LAST_MONTH) for p in sample_month(sub, m)]
        for flair, t in sorted(tally_flairs(samples).items()):
            inventory.append({"subreddit": sub, "flair_text": flair, **t, "ai_match": is_ai_text(flair)})
    fields = ["subreddit", "flair_text", "n", "first_month", "last_month", "ai_match"]
    with open(DERIVED / "flair_inventory.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(inventory)
    with open(DERIVED / "ai_flairs_draft.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(r for r in inventory if r["ai_match"])
    print(f"wrote {len(inventory)} flairs; {sum(r['ai_match'] for r in inventory)} match AI keywords")


if __name__ == "__main__":
    main()
