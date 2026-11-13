"""Fetch reader engagement, and the comments, for every post in the Substack sample.

Usage: python3 code/fetch_substack_engagement.py            engagement for every post, then comments
       python3 code/fetch_substack_engagement.py comments   comments only (posts already fetched)

Engagement: substack.com/api/v1/posts/by-id/ID gives likes (reaction_count), comment_count, restacks and the
post's current audience (a post can go paid after it was sampled). One row per post goes to
data/derived/substack_engagement.csv with fetched_at, so engagement can be put against post age. Rerunning
skips posts already in the file.

Comments: for posts with comment_count > 0, PUB/api/v1/post/ID/comments?all_comments=true returns the comment
tree. Each reply is saved as data/raw/substack_comments/ID.json (git-ignored: the text is the commenters'), and
skipped on a rerun. Paid-only comment sections come back empty without a subscription.
"""

import json
import sys
import time
import urllib.error

import pandas as pd

import substack
from reddit_subreddits import ROOT

SAMPLE = ROOT / "data" / "hand_coded" / "substack_sample_deep.csv"
OUT = ROOT / "data" / "derived" / "substack_engagement.csv"
COMMENTS = ROOT / "data" / "raw" / "substack_comments"
FIELDS = ["reaction_count", "comment_count", "child_comment_count", "restacks", "audience",
          "write_comment_permissions"]
SAVE_EVERY = 25


def engagement_row(post_id, reply, now):
    p = reply["post"]
    return {"post_id": str(post_id), **{f: p.get(f) for f in FIELDS}, "fetched_at": now}


def fetch_engagement(sample, out=OUT, get=substack.post_by_id, clock=time.time):
    have = pd.read_csv(out, dtype={"post_id": str}) if out.exists() else pd.DataFrame(columns=["post_id"])
    rows, done = have.to_dict("records"), set(have["post_id"])
    todo = [pid for pid in sample["post_id"].astype(str) if pid not in done]
    for n, pid in enumerate(todo, 1):
        try:
            rows.append(engagement_row(pid, get(pid), pd.Timestamp(clock(), unit="s").isoformat()))
        except urllib.error.HTTPError as e:
            print(f"  {pid}: HTTP {e.code}, skipped")
        if n % SAVE_EVERY == 0 or n == len(todo):
            out.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(rows).to_csv(out, index=False)
            print(f"  engagement {n}/{len(todo)}", flush=True)
    return pd.DataFrame(rows)


def fetch_comments(sample, eng, folder=COMMENTS, get=substack.get_json):
    folder.mkdir(parents=True, exist_ok=True)
    urls = dict(zip(sample["post_id"].astype(str), sample["pub_url"]))
    want = eng[eng["comment_count"].fillna(0) > 0]["post_id"].astype(str)
    todo = [pid for pid in want if not (folder / f"{pid}.json").exists()]
    for n, pid in enumerate(todo, 1):
        url = f"{urls[pid].rstrip('/')}/api/v1/post/{pid}/comments?all_comments=true&sort=oldest_first"
        try:
            (folder / f"{pid}.json").write_text(json.dumps(get(url)))
        except urllib.error.HTTPError as e:
            print(f"  {pid}: HTTP {e.code}, skipped")
        if n % SAVE_EVERY == 0 or n == len(todo):
            print(f"  comments {n}/{len(todo)}", flush=True)


def main(which="all"):
    sample = pd.read_csv(SAMPLE, dtype=str, keep_default_na=False)
    eng = fetch_engagement(sample) if which == "all" else pd.read_csv(OUT, dtype={"post_id": str})
    fetch_comments(sample, eng)


if __name__ == "__main__":
    main(*sys.argv[1:])
