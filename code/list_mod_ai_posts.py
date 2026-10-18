"""List moderator posts that mention AI, as evidence for dating subreddit AI rules.

Usage: python3 code/list_mod_ai_posts.py  (after code/fetch_reddit_dumps.py posts)
Writes data/derived/reddit_mod_ai_posts.csv.
"""

import csv
import json
from datetime import datetime, timezone

from reddit_subreddits import ROOT, study_subreddits
from reddit_text import is_ai_text

POSTS = ROOT / "data" / "raw" / "arctic" / "posts"
OUT = ROOT / "data" / "derived" / "reddit_mod_ai_posts.csv"


def is_mod_ai_post(post):
    by_mod = post.get("distinguished") == "moderator" or post.get("stickied") is True
    return by_mod and is_ai_text(f"{post.get('title', '')} {post.get('selftext', '')}")


def main():
    rows = []
    for sub in study_subreddits():
        for path in sorted((POSTS / sub).glob("*.jsonl")):
            for line in open(path):
                p = json.loads(line)
                if is_mod_ai_post(p):
                    ts = int(p["created_utc"])
                    rows.append({"subreddit": sub, "created_utc": ts,
                                 "date": datetime.fromtimestamp(ts, timezone.utc).date().isoformat(),
                                 "title": p["title"], "permalink": "https://www.reddit.com" + p["permalink"]})
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["subreddit", "created_utc", "date", "title", "permalink"])
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} moderator posts mentioning AI")


if __name__ == "__main__":
    main()
