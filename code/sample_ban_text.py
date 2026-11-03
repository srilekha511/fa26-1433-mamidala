"""Frozen random sample of text posts around each AI ban, for measuring the AI share of posts with a detector.

Usage: python3 code/sample_ban_text.py screen   (then)   python3 code/sample_ban_text.py sample
       (after build_ban_sample.py)

screen: one request per banned subreddit, and per comparison subreddit of a banned subreddit that passes: the
SCREEN_N posts before SCREEN_BEFORE (before any ban in the sample). Writes data/derived/ban_text_screen.csv with
the share of them that are scorable text posts (reddit_text.keep_post: a self post with at least MIN_WORDS words).
A subreddit is a text subreddit if that share is at least MIN_TEXT_SHARE. The screen uses only pre-ban posts, so it
does not select on the outcome.

sample: for each text subreddit that banned AI, and its comparison subreddits (build_ban_sample.pick_controls) that
are also text subreddits, DAYS random days in each of three windows, and every post on those days:
  baseline  2022-03..2022-08, before ChatGPT: the detector's false-positive rate in that subreddit
  pre       months -6..-1 relative to the ban month
  post      months +1..+6 (the ban month itself is left out)
Days are drawn with a seed fixed by the subreddit and the window, so the sample is the same on every run and does
not depend on what the detector says. Within a sampled day at most CAP_PER_DAY scorable posts are kept, at random.
Every post on a sampled day had the same chance of being drawn, so `weight` (days in the window / days drawn x
scorable posts that day / scorable posts kept) makes weighted means unbiased for the window.

Writes data/derived/ban_text_posts.parquet: one row per kept scorable post, one copy per stack it belongs to.
API replies are cached in data/raw/arctic/ban_text/ (one file per subreddit-day), so a stopped run can be restarted.
"""

import json
import sys
import zlib
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd

import arctic
from reddit_subreddits import ROOT
from reddit_text import keep_post, word_count

DERIVED = ROOT / "data" / "derived"
CACHE = ROOT / "data" / "raw" / "arctic" / "ban_text"
SCREEN_BEFORE, SCREEN_N = "2023-07-01", 100
MIN_TEXT_SHARE = 0.25
DAYS, CAP_PER_DAY = 10, 25
BASELINE = ("2022-03-01", "2022-08-31")
WINDOWS = {"pre": (-6, -1), "post": (1, 6)}


def epoch(day):
    return int(datetime.combine(date.fromisoformat(day), datetime.min.time(), timezone.utc).timestamp())


def window_days(period, k):
    """(first day, last day) of the months k[0]..k[1] relative to a ban month."""
    first, last = period + k[0], period + k[1]
    return first.start_time.date().isoformat(), last.end_time.date().isoformat()


def draw_days(sub, first, last, n=DAYS):
    """n distinct days between first and last inclusive, seeded by the subreddit and the window."""
    start = date.fromisoformat(first)
    span = (date.fromisoformat(last) - start).days + 1
    rng = np.random.default_rng(zlib.crc32(f"{sub}|{first}|{last}".encode()))
    return sorted((start + timedelta(days=int(d))).isoformat() for d in rng.choice(span, min(n, span), replace=False))


def keep_on_day(sub, day, ids, cap=CAP_PER_DAY):
    """The ids kept from one day's scorable posts: all of them up to cap, otherwise a seeded random cap."""
    ids = sorted(ids)
    if len(ids) <= cap:
        return set(ids)
    rng = np.random.default_rng(zlib.crc32(f"{sub}|{day}".encode()))
    return set(rng.choice(ids, cap, replace=False))


def cached_json(path, fetch):
    if path.exists():
        return json.loads(path.read_text())
    data = fetch()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    return data


def day_posts(sub, day):
    """Every post in a subreddit on one UTC day."""
    start = epoch(day)
    return cached_json(CACHE / sub / f"{day}.json",
                       lambda: [x for x in arctic.iter_window("posts/search", sub, start - 1, start + 86400)
                                if start <= int(x["created_utc"]) < start + 86400])


def screen_posts(sub):
    return cached_json(CACHE / "_screen" / f"{sub}.json",
                       lambda: arctic.get("posts/search", {"subreddit": sub, "before": epoch(SCREEN_BEFORE),
                                                           "limit": SCREEN_N, "sort": "desc"}))


def screen_row(sub, posts):
    n = len(posts)
    ok = sum(keep_post(p) for p in posts)
    return {"subreddit": sub, "n_screened": n, "n_text": ok, "text_share": ok / n if n else np.nan}


def screen():
    sample = pd.read_csv(DERIVED / "ban_sample.csv")
    treated = sample[sample["drop"].isna()]
    controls = pd.read_csv(DERIVED / "ban_controls.csv")
    rows = []
    for i, sub in enumerate(treated["subreddit"], 1):
        rows.append({**screen_row(sub, screen_posts(sub)), "role": "treated"})
        print(f"[{i}/{len(treated)}] r/{sub}: {rows[-1]['n_text']}/{rows[-1]['n_screened']} text", flush=True)
    text = {r["subreddit"] for r in rows if r["text_share"] >= MIN_TEXT_SHARE}
    pool = controls[controls["matched_to"].isin(text)]
    for i, sub in enumerate(pool["subreddit"], 1):
        rows.append({**screen_row(sub, screen_posts(sub)), "role": "control"})
        print(f"[{i}/{len(pool)}] r/{sub} (control): {rows[-1]['n_text']}/{rows[-1]['n_screened']} text", flush=True)
    out = pd.DataFrame(rows)
    out["text_sub"] = out["text_share"] >= MIN_TEXT_SHARE
    out.to_csv(DERIVED / "ban_text_screen.csv", index=False)
    print(out.groupby("role")["text_sub"].agg(["sum", "count"]).to_string())


def plan():
    """One row per (stack, subreddit, window): the days to fetch."""
    sample = pd.read_csv(DERIVED / "ban_sample.csv")
    treated = sample[sample["drop"].isna()].set_index("subreddit")
    controls = pd.read_csv(DERIVED / "ban_controls.csv")
    scr = pd.read_csv(DERIVED / "ban_text_screen.csv")
    text = set(scr.loc[scr["text_sub"], "subreddit"])
    rows = []
    for sub in treated.index.intersection(scr.loc[scr["text_sub"] & (scr["role"] == "treated"), "subreddit"]):
        event = pd.Period(treated.loc[sub, "ban_date"][:7], "M")
        units = [(sub, "treated")] + [(c, "control") for c in controls.loc[controls["matched_to"] == sub, "subreddit"]
                                      if c in text]
        for unit, role in units:
            windows = {"baseline": BASELINE, **{w: window_days(event, k) for w, k in WINDOWS.items()}}
            for w, (first, last) in windows.items():
                span = (date.fromisoformat(last) - date.fromisoformat(first)).days + 1
                rows += [{"stack": sub, "ban_date": treated.loc[sub, "ban_date"], "subreddit": unit, "role": role,
                          "window": w, "window_days": span, "day": d} for d in draw_days(unit, first, last)]
    return pd.DataFrame(rows)


def sample():
    days = plan()
    todo = days[["subreddit", "day"]].drop_duplicates()
    print(f"{days['stack'].nunique()} stacks, {days['subreddit'].nunique()} subreddits, {len(todo)} subreddit-days")
    posts = {}
    for i, (sub, day) in enumerate(todo.itertuples(index=False), 1):
        got = day_posts(sub, day)
        ok = [p for p in got if keep_post(p)]
        kept = keep_on_day(sub, day, [p["id"] for p in ok])
        posts[sub, day] = [{"id": p["id"], "created_utc": int(p["created_utc"]), "author": p.get("author"),
                            "title": p.get("title") or "", "selftext": p["selftext"].strip(),
                            "n_words": word_count(p["selftext"]), "score": p.get("score"),
                            "num_comments": p.get("num_comments"), "removed": p.get("removed_by_category"),
                            "n_posts_day": len(got), "n_text_day": len(ok)} for p in ok if p["id"] in kept]
        if i % 50 == 0 or i == len(todo):
            print(f"[{i}/{len(todo)}] r/{sub} {day}: {len(got)} posts, {len(ok)} text", flush=True)
    rows = []
    for r in days.itertuples(index=False):
        for p in posts[r.subreddit, r.day]:
            rows.append({**r._asdict(), **p, "weight": r.window_days / DAYS * p["n_text_day"]
                         / min(p["n_text_day"], CAP_PER_DAY)})
    out = pd.DataFrame(rows)
    out.to_parquet(DERIVED / "ban_text_posts.parquet", index=False)
    print(out.groupby(["role", "window"]).agg(posts=("id", "size"), subreddits=("subreddit", "nunique")).to_string())


if __name__ == "__main__":
    {"screen": screen, "sample": sample}[sys.argv[1]]()
