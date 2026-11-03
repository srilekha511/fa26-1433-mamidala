"""Score the sampled text posts with the Pangram API (model MODEL, pinned so scores are reproducible).

Usage: python3 code/score_pangram_api.py test     score TEST_N posts drawn at random from the sample, then stop
       python3 code/score_pangram_api.py project  posts and words left to score, to project the cost
       python3 code/score_pangram_api.py run      score everything not yet scored
       (after sample_ban_text.py sample; the key is read from ~/.pangram_key and never printed)

Pangram's docs do not say what a credit buys, so the cost is measured: note the balance on the API dashboard
before and after `test`, then `project` gives the posts and words left to price.

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
from pathlib import Path

import pandas as pd

from reddit_subreddits import ROOT

DERIVED = ROOT / "data" / "derived"
RAW = ROOT / "data" / "raw" / "pangram"
SCORES = DERIVED / "pangram_api_scores.csv"
BASE = "https://text.external-api.pangram.com"
MODEL = "pangram-4.1"
TEST_N, JOB_SIZE, POLL = 50, 500, 10
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


def todo():
    posts = pd.read_parquet(DERIVED / "ban_text_posts.parquet", columns=["id", "selftext", "n_words"])
    posts = posts.drop_duplicates("id")
    done = set(pd.read_csv(SCORES)["id"]) if SCORES.exists() else set()
    return posts[~posts["id"].isin(done)].sort_values("id")


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


def run():
    left = todo()
    print(f"{len(left)} posts to score in jobs of {JOB_SIZE}")
    n = 0
    for start in range(0, len(left), JOB_SIZE):
        n += score_job(left.iloc[start:start + JOB_SIZE])
        print(f"{n}/{len(left)} scored", flush=True)


if __name__ == "__main__":
    {"test": test, "project": project, "run": run}[sys.argv[1]]()
