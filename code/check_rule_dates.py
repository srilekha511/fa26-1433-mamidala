"""Check data/hand_coded/reddit_rule_dates.csv for errors.

Usage: python3 code/check_rule_dates.py   (prints problems; exits 1 if there are any)
"""

import csv
import sys
from datetime import date

from reddit_subreddits import ROOT, study_subreddits

RULE_DATES = ROOT / "data" / "hand_coded" / "reddit_rule_dates.csv"


def _parse(value):
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def problems(rows, study):
    out = []
    seen = set()
    for r in rows:
        sub = r["subreddit"]
        seen.add(sub)
        if sub not in study:
            out.append(f"{sub}: not a study subreddit (not in ai_flairs.csv)")
        label = _parse(r["label_start"])
        if label is None:
            out.append(f"{sub}: label_start {r['label_start']!r} is not YYYY-MM-DD")
        if not r["label_source"]:
            out.append(f"{sub}: label_source is empty")
        if r["mandatory_start"]:
            mand = _parse(r["mandatory_start"])
            if mand is None:
                out.append(f"{sub}: mandatory_start {r['mandatory_start']!r} is not YYYY-MM-DD")
            elif label and mand < label:
                out.append(f"{sub}: mandatory_start is before label_start")
            if not r["mandatory_source"]:
                out.append(f"{sub}: mandatory_source is empty")
    out += [f"{sub}: missing from reddit_rule_dates.csv" for sub in study if sub not in seen]
    return out


def load_rule_dates():
    with open(RULE_DATES, newline="") as f:
        return {r["subreddit"]: r for r in csv.DictReader(f)}


if __name__ == "__main__":
    found = problems(list(load_rule_dates().values()), study_subreddits())
    print("\n".join(found) or "reddit_rule_dates.csv: OK")
    sys.exit(1 if found else 0)
