"""Score the Substack posts whose authors turned AI detection off, with the Pangram API.

Usage: python3 code/score_substack_off.py fetch [off|calib]   fetch the posts' text (substack_text, 3 s pause;
                                                               default off)
       python3 code/score_substack_off.py project   posts and words to score, before paying for it
       python3 code/score_substack_off.py run       score every fetched post not yet scored

Posts: every post in the deepened sample (analyze_substack_sample.SAMPLE) coded unavailable with no reason
shown, i.e. detection off: those of the always-off publications and the off posts of publications that switch.
A reader cannot scan these, so this is the only measure of their AI use.

Calibration set (calib): the off posts' scores come from the API, the other posts' from Substack's reader scan,
so some scannable posts are scored with the API too: every scannable post of the publications that switch, plus
CALIB_ON scannable posts of always-on publications drawn at random (seed SEED). These show whether the API and
the reader scan agree, and give comparisons where both sides are measured by the API.

Text goes to data/derived/substack_off_text.parquet and scores to data/derived/substack_off_scores.csv; both are
git-ignored (the text is the authors'). Scoring reuses score_pangram_api (same model, idempotent bulk jobs) with
its output paths pointed here, so the Reddit scores are untouched. Raw results go to data/raw/pangram_substack/.
"""

import sys

import pandas as pd

import analyze_substack_sample as a
import score_pangram_api as pangram
import substack_text
from reddit_subreddits import ROOT

TEXT = ROOT / "data" / "derived" / "substack_off_text.parquet"
SCORES = ROOT / "data" / "derived" / "substack_off_scores.csv"
RAW = ROOT / "data" / "raw" / "pangram_substack"
CALIB_ON = 40
SEED = 1433


def off_ids(df):
    """Post ids with detection off, as strings."""
    return df.loc[df["off"], "post_id"].astype(str).tolist()


def calib_ids(df, n_on=CALIB_ON, seed=SEED):
    """Scannable posts of switching publications, then n_on random scannable posts of always-on ones."""
    pattern = df["publication"].map(a.publications(df).set_index("publication")["pattern"])
    scannable = df[df["status"] == "scannable"]
    sw = scannable[pattern[scannable.index] == "switches"]
    on = scannable[pattern[scannable.index] == "always_on"]
    on = on.sample(min(n_on, len(on)), random_state=seed)
    return sw["post_id"].astype(str).tolist() + on["post_id"].astype(str).tolist()


def todo(texts, scores_path=SCORES):
    """Fetched posts with text that are not yet scored."""
    done = set(pd.read_csv(scores_path, dtype={"id": str})["id"]) if scores_path.exists() else set()
    texts = texts.assign(id=texts["id"].astype(str))
    return texts[(texts["n_words"] > 0) & ~texts["id"].isin(done)].sort_values("id")


def fetch(which="off"):
    df = a.load()
    ids = off_ids(df) if which == "off" else calib_ids(df)
    print(f"{len(ids)} posts in set {which}")
    TEXT.parent.mkdir(parents=True, exist_ok=True)
    texts = substack_text.fetch_texts(ids, TEXT)
    empty = texts[texts["n_words"] == 0]
    print(f"{len(texts)} fetched, {len(empty)} empty (paywalled or gone): {empty['id'].tolist()}")


def project():
    left = todo(pd.read_parquet(TEXT))
    w = left["n_words"]
    print(f"Left to score: {len(left)} posts, {w.sum():,} words (median {w.median():.0f}, max {w.max():,}).")


def run():
    pangram.SCORES, pangram.RAW = SCORES, RAW
    left = todo(pd.read_parquet(TEXT))
    print(f"{len(left)} posts to score")
    if len(left):
        pangram.score_job(left)


if __name__ == "__main__":
    {"fetch": fetch, "project": project, "run": run}[sys.argv[1]](*sys.argv[2:])
