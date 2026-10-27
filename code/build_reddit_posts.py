"""Build the cleaned Reddit post file and the subreddit-month panel for the labeling DiD.

Usage: python3 code/build_reddit_posts.py
  (after fetch_reddit_dumps.py posts and a passing check_rule_dates.py)
Writes data/derived/reddit_posts.parquet (every post except AutoModerator's, of any type),
data/derived/reddit_subreddit_months.csv (one row per subreddit, month and period) and
data/derived/reddit_post_filter_counts.csv, and prints the share of posts with an AI flair by
subreddit, period and retrieval regime.

The study subreddits are image communities, so the creator outcome is the AI-labeled share of
*all* posts. `text_ok` marks the text posts long enough for Pangram, for later text work.

Arctic Shift captured posts weeks late before mid-2023 and within seconds afterwards, so flair
and removals are observed differently in the two regimes; compare periods within a regime.
"""

import json
import sys
from collections import Counter
from datetime import datetime, timezone

import pandas as pd

from check_rule_dates import load_rule_dates, problems
from reddit_subreddits import ROOT, approved_flairs, study_subreddits
from reddit_text import period, post_type, removal_type, retrieval_regime, text_status, word_count

POSTS = ROOT / "data" / "raw" / "arctic" / "posts"
DERIVED = ROOT / "data" / "derived"


def post_row(p, flairs, rule):
    ts = int(p["created_utc"])
    flair = (p.get("link_flair_text") or "").strip()
    second = (p.get("_meta") or {}).get("retrieved_2nd_on")
    last_seen = second or p.get("retrieved_on")
    removed_by = removal_type(p)
    text = p.get("selftext") or ""
    return {
        "id": p["id"], "subreddit": p["subreddit"], "created_utc": ts,
        "month": datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m"),
        "author": p.get("author"), "title": p.get("title", ""), "selftext": text,
        "post_type": post_type(p), "text_ok": text_status(p) == "ok", "n_words": word_count(text),
        "link_flair_text": flair, "ai_flair": flair in flairs,
        "period": period(ts, rule["label_start"], rule["mandatory_start"]),
        "regime": retrieval_regime(p),
        "removed": removed_by is not None, "removal_type": removed_by,
        "score": p.get("score"), "num_comments": p.get("num_comments"),
        "retrieved_on": p.get("retrieved_on"), "retrieved_2nd_on": second,
        # Hours between posting and the last time Arctic Shift saw the post (and its flair).
        "flair_lag_hours": (last_seen - ts) / 3600 if last_seen else None,
        "meta_note": (p.get("_meta") or {}).get("note"),
    }


def subreddit_months(df):
    """One row per subreddit, month and period; a month split by a rule date gets two rows."""
    df = df.assign(image=df["post_type"].isin(["image", "gallery"]),
                   ai_score=df["score"].where(df["ai_flair"]), other_score=df["score"].mask(df["ai_flair"]),
                   ai_comments=df["num_comments"].where(df["ai_flair"]),
                   other_comments=df["num_comments"].mask(df["ai_flair"]),
                   live=df["regime"] == "live_ingest")
    return df.groupby(["subreddit", "month", "period"], as_index=False).agg(
        posts=("ai_flair", "size"), ai_flair_posts=("ai_flair", "sum"), labeled_share=("ai_flair", "mean"),
        removed_share=("removed", "mean"), image_share=("image", "mean"), live_ingest_share=("live", "mean"),
        ai_mean_score=("ai_score", "mean"), other_mean_score=("other_score", "mean"),
        ai_mean_comments=("ai_comments", "mean"), other_mean_comments=("other_comments", "mean"))


def main():
    rules = load_rule_dates()
    found = problems(list(rules.values()), study_subreddits())
    if found:
        sys.exit("fix data/hand_coded/reddit_rule_dates.csv first:\n" + "\n".join(found))
    flairs = approved_flairs()
    rows, filtered = [], Counter()
    for sub in study_subreddits():
        for path in sorted((POSTS / sub).glob("*.jsonl")):
            for line in open(path):
                p = json.loads(line)
                status = text_status(p)
                per = period(int(p["created_utc"]), rules[sub]["label_start"], rules[sub]["mandatory_start"])
                filtered[(sub, per, retrieval_regime(p), status)] += 1
                if status != "automod":
                    rows.append(post_row(p, flairs[sub], rules[sub]))
    if not rows:
        sys.exit("no usable posts found; run code/fetch_reddit_dumps.py posts first")
    df = pd.DataFrame(rows)
    df.to_parquet(DERIVED / "reddit_posts.parquet", index=False)
    panel = subreddit_months(df)
    panel.insert(1, "group", panel["subreddit"].map({s: r["group"] for s, r in rules.items()}))
    panel.to_csv(DERIVED / "reddit_subreddit_months.csv", index=False)
    pd.DataFrame([{"subreddit": s, "period": per, "regime": reg, "text_status": st, "n": n}
                  for (s, per, reg, st), n in sorted(filtered.items())]).to_csv(
        DERIVED / "reddit_post_filter_counts.csv", index=False)

    print(f"kept {len(df):,} of {sum(filtered.values()):,} posts")
    print(df.groupby(["subreddit", "period", "regime"]).agg(
        posts=("id", "size"), ai_flair_share=("ai_flair", "mean"), removed_share=("removed", "mean"),
        text_ok_share=("text_ok", "mean"),
        second_retrieval_share=("retrieved_2nd_on", lambda s: s.notna().mean())).round(3))
    seen = df.groupby("subreddit")["link_flair_text"].agg(set)
    for sub, approved in flairs.items():
        for flair in sorted(approved - seen.get(sub, set())):
            print(f"warning: approved flair {flair!r} in r/{sub} matches no kept post")


if __name__ == "__main__":
    main()
