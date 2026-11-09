"""Score the sampled text posts with the Pangram API (model MODEL, pinned so scores are reproducible).

Usage: python3 code/score_pangram_api.py test     score TEST_N posts drawn at random from the sample, then stop
       python3 code/score_pangram_api.py select   choose the posts to score (below)
       python3 code/score_pangram_api.py project  posts and words left to score, to project the cost
       python3 code/score_pangram_api.py run N    score the next N chosen posts, then report
       python3 code/score_pangram_api.py report   flagged share and billing units so far
       (after sample_ban_text.py sample; the key is read from ~/.pangram_key and never printed)

Pangram's docs do not say what a credit buys, so the cost is measured: note the balance on the API dashboard
before and after a batch, and compare it with the posts, words and segments that `report` gives.

select keeps the bans with at least one text comparison subreddit, and in each stack at most CAP posts per subreddit
in the pre and post windows and BASELINE_CAP in the baseline window, using a random rank fixed by the post id, so the
choice cannot depend on any score. Writes data/derived/ban_text_scoring_sample.parquet; `cap_weight` is the sampling
weight scaled up for the posts capped away. Batches follow the same rank, so a part-finished run is a random
subsample of the chosen posts.

Posts go to the bulk endpoint in jobs of JOB_SIZE, each with an Idempotency-Key fixed by its contents, so
resubmitting a job after a crash returns the first job instead of paying for it again. Every job id is written to
data/raw/pangram/jobs.csv before polling, and each raw result to data/raw/pangram/results.jsonl.
Writes data/derived/pangram_api_scores.csv: one row per post id with prediction_short (AI, Mixed, Human) and the
AI, AI-assisted and human fractions of its text.
"""

import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
import zlib
from pathlib import Path

import numpy as np
import pandas as pd

from reddit_subreddits import ROOT

DERIVED = ROOT / "data" / "derived"
RAW = ROOT / "data" / "raw" / "pangram"
SCORES = DERIVED / "pangram_api_scores.csv"
CHOSEN = DERIVED / "ban_text_scoring_sample.parquet"
BASE = "https://text.external-api.pangram.com"
MODEL = "pangram-4.1"
TEST_N, JOB_SIZE, POLL = 50, 500, 10
CAP, BASELINE_CAP, SEED = 60, 15, 1433
FIELDS = ["fraction_ai", "fraction_ai_assisted", "fraction_human", "num_ai_segments", "num_human_segments"]


def key():
    return (Path.home() / ".pangram_key").read_text().strip()


def call(method, path, body=None, headers=None):
    req = urllib.request.Request(BASE + path, method=method, data=None if body is None else json.dumps(body).encode(),
                                 headers={"x-api-key": key(), "Content-Type": "application/json", **(headers or {})})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 402:
                sys.exit("Pangram: out of credits (402). Nothing more was submitted.")
            if e.code not in (429, 500, 502, 503, 504):
                raise
            print(f"  retry {attempt + 1}: HTTP {e.code}")
        except urllib.error.URLError as e:
            print(f"  retry {attempt + 1}: {e}")
        time.sleep(15 * (attempt + 1))
    raise RuntimeError(f"failed after 6 tries: {method} {path}")


def idempotency_key(body):
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def row(item):
    """One score row from a bulk result item, or None if it failed."""
    res = item.get("result")
    if not res or res.get("stage") != "STAGE_SUCCESS":
        return None
    return {"id": item["id"], "prediction_short": res["prediction_short"], **{f: res[f] for f in FIELDS},
            "version": res.get("version")}


def score_job(posts):
    """Submit one bulk job, wait for it, and append its scores. Returns the number scored."""
    body = {"items": [{"id": i, "text": t} for i, t in zip(posts["id"], posts["selftext"])], "model": MODEL}
    job = call("POST", "/bulk", body, {"Idempotency-Key": idempotency_key(body)})
    RAW.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"bulk_id": job["bulk_id"], "n": len(posts), "submitted": time.time()}]).to_csv(
        RAW / "jobs.csv", mode="a", header=not (RAW / "jobs.csv").exists(), index=False)
    print(f"  job {job['bulk_id']}: {len(job['accepted_items'])} accepted, {len(job['failed_items'])} rejected")
    while (status := call("GET", f"/bulk/{job['bulk_id']}"))["status"] in ("queued", "running"):
        time.sleep(POLL)
    items = []
    for offset in range(0, status["total_items"], 1000):
        items += call("GET", f"/bulk/{job['bulk_id']}/results?offset={offset}&limit=1000")["items"]
    with open(RAW / "results.jsonl", "a") as f:
        for it in items:
            f.write(json.dumps(it) + "\n")
    rows = [r for r in map(row, items) if r]
    if rows:
        pd.DataFrame(rows).to_csv(SCORES, mode="a", header=not SCORES.exists(), index=False)
    print(f"  {status['status']}: {len(rows)} scored, {len(items) - len(rows)} failed")
    return len(rows)


def rank(post_id):
    return zlib.crc32(f"{SEED}|{post_id}".encode())


def select_posts(posts, cap=CAP, baseline_cap=BASELINE_CAP):
    """The posts to score, with the rank that orders batches and the weight adjusted for the cap."""
    compared = posts.loc[posts["role"] == "control", "stack"].unique()
    p = posts[posts["stack"].isin(compared)].copy()
    p["rank"] = p["id"].map(rank)
    p = p.sort_values(["rank", "id"])
    by = p.groupby(["stack", "subreddit", "window"])
    p["cap_weight"] = p["weight"] * by["id"].transform("size")
    limit = p["window"].map(lambda w: baseline_cap if w == "baseline" else cap)
    out = p[by.cumcount() < limit].copy()
    out["cap_weight"] /= out.groupby(["stack", "subreddit", "window"])["id"].transform("size")
    return out.reset_index(drop=True)


def select():
    posts = pd.read_parquet(DERIVED / "ban_text_posts.parquet")
    out = select_posts(posts)
    out.to_parquet(CHOSEN, index=False)
    print(f"{len(out):,} of {len(posts):,} posts chosen, {out['n_words'].sum():,} words, "
          f"{out['stack'].nunique()} bans, {out['subreddit'].nunique()} subreddits")
    print(out.groupby(["role", "window"]).size().to_string())


def todo():
    """Chosen posts not yet scored, in batch order; before `select`, the whole sample."""
    path = CHOSEN if CHOSEN.exists() else DERIVED / "ban_text_posts.parquet"
    posts = pd.read_parquet(path).drop_duplicates("id")
    done = set(pd.read_csv(SCORES)["id"]) if SCORES.exists() else set()
    left = posts[~posts["id"].isin(done)]
    return left.sort_values(["rank", "id"]) if "rank" in left else left.sort_values("id")


def test():
    left = todo()
    if SCORES.exists():
        sys.exit(f"{SCORES.name} already has scores; the test batch was run. Use `project`.")
    pick = left.sample(min(TEST_N, len(left)), random_state=0)
    print(f"Test batch: {len(pick)} posts, {pick['n_words'].sum():,} words. Note the dashboard balance now.")
    score_job(pick)
    project()


def project():
    left = todo()
    done = pd.read_csv(SCORES) if SCORES.exists() else pd.DataFrame()
    w = left["n_words"]
    print(f"Scored so far: {len(done)} posts. Left to score: {len(left):,} posts, {w.sum():,} words "
          f"(median {w.median():.0f}, 90th percentile {w.quantile(0.9):.0f}, max {w.max():,} words per post).")


def run(n_posts):
    left = todo().head(n_posts)
    print(f"{len(left)} posts, {left['n_words'].sum():,} words to score in jobs of {JOB_SIZE}")
    n = 0
    for start in range(0, len(left), JOB_SIZE):
        n += score_job(left.iloc[start:start + JOB_SIZE])
        print(f"{n}/{len(left)} scored", flush=True)
    report()


def wilson(k, n, z=1.96):
    """95% Wilson interval for a share of k out of n."""
    if n == 0:
        return np.nan, np.nan
    p, d = k / n, 1 + z * z / n
    mid, half = (p + z * z / (2 * n)) / d, z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, mid - half), min(1.0, mid + half)


def flag_table(df):
    """Scored posts, and the unweighted share flagged AI or Mixed, by role and window."""
    rows = []
    for (role, window), g in df.groupby(["role", "window"]):
        ai, mixed = (g["prediction_short"] == "AI").sum(), (g["prediction_short"] == "Mixed").sum()
        lo, hi = wilson(ai, len(g))
        rows.append({"role": role, "window": window, "posts": len(g), "subreddits": g["subreddit"].nunique(), "ai": ai,
                     "mixed": mixed, "ai_pct": 100 * ai / len(g), "ci_low": 100 * lo, "ci_high": 100 * hi,
                     "mean_fraction_ai_pct": 100 * g["fraction_ai"].mean()})
    return pd.DataFrame(rows)


def billing_units():
    """Posts, words and segments returned by every job so far, per job, to set against the dashboard balance."""
    jobs = pd.read_csv(RAW / "jobs.csv")
    items = [json.loads(line) for line in open(RAW / "results.jsonl")]
    done = [it["result"] for it in items if it.get("result")]
    return {"jobs": len(jobs), "posts": len(done), "words": sum(w.get("word_count", 0) for r in done for w in r["windows"]),
            "segments": sum(len(r["windows"]) for r in done)}


def report():
    chosen = pd.read_parquet(CHOSEN).drop(columns=["selftext", "title"])
    scored = pd.read_csv(SCORES).drop_duplicates("id")
    df = chosen.merge(scored, on="id")
    print(f"{len(df):,} of {len(chosen):,} chosen posts scored; {len(scored) - len(df)} test posts outside the choice")
    pd.set_option("display.width", 200)
    print(flag_table(df).round(2).to_string(index=False))
    ai = df["prediction_short"] == "AI"
    print(f"All chosen posts so far: {ai.sum()} flagged AI of {len(df)} ({100 * ai.mean():.2f}%)")
    print("Billing units across all jobs, including the test:", billing_units())


if __name__ == "__main__":
    command = sys.argv[1]
    if command == "run":
        run(int(sys.argv[2]))
    else:
        {"test": test, "select": select, "project": project, "report": report}[command]()
