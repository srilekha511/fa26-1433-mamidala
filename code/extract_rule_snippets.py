"""Pull AI-related rule lines out of saved Wayback snapshots.

Usage: python3 code/extract_rule_snippets.py  (after code/fetch_rule_snapshots.py)
Writes data/derived/rule_snippets.csv; rows with changed=True are where to look when dating rules.
"""

import csv

import wayback
from reddit_subreddits import ROOT

RAW = ROOT / "data" / "raw" / "wayback"
OUT = ROOT / "data" / "derived" / "rule_snippets.csv"


def main():
    rows = []
    with open(RAW / "index.csv", newline="") as f:
        for r in csv.DictReader(f):
            html = (RAW / r["subreddit"] / r["kind"] / f"{r['timestamp']}.html").read_text()
            text = wayback.extract_rule_text(html)
            rows.append({**r, "n_chars": len(text), "snippets": " || ".join(wayback.ai_snippets(text))})
    rows = wayback.mark_changes(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["subreddit", "kind", "timestamp", "snapshot_url",
                                          "n_chars", "snippets", "changed"])
        w.writeheader()
        w.writerows(rows)
    empty = sum(r["n_chars"] == 0 for r in rows)
    print(f"wrote {len(rows)} rows; {empty} snapshots had no rule text")


if __name__ == "__main__":
    main()
