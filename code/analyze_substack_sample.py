"""Summarize the hand-coded Substack sample: how often authors turn AI detection off, and who does.

Usage: python3 code/analyze_substack_sample.py [path]   (default data/hand_coded/substack_sample.csv)

A post counts as "detection off" when the reader popup says detection is unavailable and gives no reason
(unavailable_reason none_shown). Posts the popup says are unavailable for another reason (paid_only,
too_short, before_launch) are dropped from every denominator. "Off" is as of checked_on: authors can turn
detection off for old posts later.

Writes to output/:
  substack_off_shares.csv     off share by window, category and before/after the reader labels (LABELS_DATE)
  substack_publications.csv   one row per publication: pattern (always_on / always_off / switches),
                              statement, Pangram scores of its scannable posts
  substack_estimates.csv      overall off share, the within-publication change at the reader labels (both
                              with publication bootstrap CIs) and the AI-score comparison of switchers with
                              always-on publications (Fisher's exact test)
"""

import sys

import numpy as np
import pandas as pd
from scipy.stats import fisher_exact

from reddit_subreddits import ROOT

SAMPLE = ROOT / "data" / "hand_coded" / "substack_sample.csv"
OUT_DIR = ROOT / "output"
LABELS_DATE = "2026-10-14"  # Substack started showing reader labels
AI_FLAG = 50  # a publication is "AI-flagged" if any scannable post has ai_pct at or above this
PCTS = ["ai_pct", "ai_assisted_pct", "human_pct"]
BOOT = 2000
SEED = 1433


def load(path=SAMPLE):
    """The coded posts, with off / eligible flags and numeric scores."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    for c in ["status", "statement", "unavailable_reason"]:
        df[c] = df[c].str.strip().str.lower()
    df["publication"] = df["publication"].str.strip()
    for c in PCTS:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["off"] = (df["status"] == "unavailable") & (df["unavailable_reason"] == "none_shown")
    df["eligible"] = (df["status"] == "scannable") | df["off"]
    df["after_labels"] = df["post_date"] >= LABELS_DATE
    return df


def shares(df, by):
    """Off share of eligible posts for each value of `by`."""
    e = df[df["eligible"]]
    g = e.groupby(by).agg(off_share=("off", "mean"), n_off=("off", "sum"), n_posts=("off", "size"),
                          n_pubs=("publication", "nunique")).reset_index()
    return g.rename(columns={by: "group"}).assign(by=by)[["by", "group", "off_share", "n_off", "n_posts",
                                                          "n_pubs"]]


def publications(df):
    e = df[df["eligible"]]
    p = e.groupby("publication").agg(category=("category", "first"), n_posts=("off", "size"),
                                     n_off=("off", "sum"), statement=("statement", lambda s: (s == "yes").any()),
                                     n_scanned=("ai_pct", "count"), max_ai=("ai_pct", "max"),
                                     mean_ai=("ai_pct", "mean")).reset_index()
    p["pattern"] = np.select([p["n_off"] == 0, p["n_off"] == p["n_posts"]], ["always_on", "always_off"],
                             "switches")
    p["ai_flagged"] = (p["max_ai"] >= AI_FLAG).where(p["n_scanned"] > 0)
    return p


def labels_change(e):
    """Mean within-publication change in the off share, after minus before LABELS_DATE, over publications
    with posts on both sides."""
    m = e.groupby(["publication", "after_labels"])["off"].mean().unstack()
    if True not in m or False not in m:
        return np.nan
    return (m[True] - m[False]).dropna().mean()


def bootstrap(e, stat, boot=BOOT, seed=SEED):
    """Percentile 95% CI of stat(posts) resampling publications."""
    rng = np.random.default_rng(seed)
    groups = dict(tuple(e.groupby("publication")))
    names = list(groups)
    draws = []
    for _ in range(boot):
        pick = rng.choice(len(names), len(names))
        sample = pd.concat([groups[names[i]].assign(publication=f"{names[i]}#{k}") for k, i in enumerate(pick)])
        draws.append(stat(sample))
    return np.nanpercentile(draws, [2.5, 97.5])


def flag_test(pubs):
    """Switchers vs always-on publications: how many have an AI-flagged scannable post."""
    a = pubs[pubs["pattern"] == "switches"]["ai_flagged"].dropna()
    b = pubs[pubs["pattern"] == "always_on"]["ai_flagged"].dropna()
    table = [[int(a.sum()), int(len(a) - a.sum())], [int(b.sum()), int(len(b) - b.sum())]]
    return table, fisher_exact(table).pvalue


def estimates(df, pubs, boot=BOOT):
    e = df[df["eligible"]]
    overall = lambda x: x["off"].mean()
    lo, hi = bootstrap(e, overall, boot)
    rows = [{"estimate": "off_share", "value": overall(e), "ci_low": lo, "ci_high": hi,
             "n": len(e), "note": f"{e['publication'].nunique()} publications"}]
    lo, hi = bootstrap(e, labels_change, boot)
    both = e.groupby("publication")["after_labels"].nunique().eq(2).sum()
    rows.append({"estimate": "labels_change", "value": labels_change(e), "ci_low": lo, "ci_high": hi,
                 "n": both, "note": f"publications with posts before and after {LABELS_DATE}"})
    table, p = flag_test(pubs)
    rows.append({"estimate": "ai_flagged_switchers_minus_always_on",
                 "value": table[0][0] / max(sum(table[0]), 1) - table[1][0] / max(sum(table[1]), 1),
                 "ci_low": np.nan, "ci_high": np.nan, "n": sum(table[0]) + sum(table[1]),
                 "note": f"flagged/total: switchers {table[0][0]}/{sum(table[0])}, always on "
                         f"{table[1][0]}/{sum(table[1])}; Fisher p={p:.2f}"})
    return pd.DataFrame(rows)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else SAMPLE
    df = load(path)
    dropped = df[~df["eligible"]]["unavailable_reason"].value_counts()
    print(f"{len(df)} posts; dropped as unavailable for a stated reason: {dropped.to_dict()}")
    df["labels"] = np.where(df["after_labels"], f"after {LABELS_DATE}", f"before {LABELS_DATE}")
    sh = pd.concat([shares(df, b) for b in ["window", "category", "labels"]])
    pubs = publications(df)
    est = estimates(df, pubs)
    OUT_DIR.mkdir(exist_ok=True)
    sh.to_csv(OUT_DIR / "substack_off_shares.csv", index=False)
    pubs.to_csv(OUT_DIR / "substack_publications.csv", index=False)
    est.to_csv(OUT_DIR / "substack_estimates.csv", index=False)
    with pd.option_context("display.width", 160, "display.max_columns", 20):
        print("\nOff shares:\n" + sh.round(3).to_string(index=False))
        print("\nPublications by pattern:\n" + pubs["pattern"].value_counts().to_string())
        print("\nScores by pattern (publications with scans):\n"
              + pubs.groupby("pattern")[["max_ai", "mean_ai", "ai_flagged"]].mean().round(2).to_string())
        print("\nStatements:\n" + pubs[pubs["statement"]][["publication", "pattern", "max_ai"]].to_string(index=False))
        print("\nEstimates:\n" + est.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
