"""Add one more post per window for every publication already in the Substack sample.

Usage: python3 code/substack_deepen.py [SAMPLE.csv] [OUT.csv]
       (defaults data/hand_coded/substack_sample.csv and data/hand_coded/substack_sample_deep.csv)

Why: with 2-3 posts per publication, a publication that turns detection off on some posts often looks
"always on" or "always off". A second post per window, for every publication alike, finds more of the
publications that switch and gives each one more scans. Deepening only the publications that already switch
would give them more chances to show a switch than the rest, so every publication gets the same draw.

For each publication, the new post in each window is the lowest-ranked eligible post (substack_pilot.rank,
same seed) that is not already in the sample. Eligibility is checked again now, so a post that has since gone
paid is skipped. The publication list comes from the sample, not from Substack's listings, which change.

Writes OUT with every existing row as it is (draw 1) followed by the new rows (draw 2) with the hand-coded
columns blank. Refuses to overwrite OUT, since it will be filled in by hand.
"""

import csv
import sys

import substack
import substack_pilot as sp
from reddit_subreddits import ROOT

SAMPLE = ROOT / "data" / "hand_coded" / "substack_sample.csv"
OUT = ROOT / "data" / "hand_coded" / "substack_sample_deep.csv"


def next_posts(posts, taken):
    """Per window, the lowest-ranked eligible post whose id is not in `taken`, oldest window first."""
    out = []
    for name, _, _ in sp.WINDOWS:
        inside = [p for p in sp.eligible(posts) if sp.window_of(p["post_date"]) == name
                  and str(p["id"]) not in taken]
        if inside:
            out.append(min(inside, key=lambda p: sp.rank(p["id"])))
    return out


def new_rows(existing, archive=substack.iter_archive):
    """Rows for the extra posts, one publication at a time in the sample's order."""
    taken = {r["post_id"] for r in existing}
    blank = {c: "" for c in existing[0] if c not in {"post_id", "reader_url", "category", "publication",
                                                      "pub_url", "window", "post_date", "wordcount", "title"}}
    pubs = {}
    for r in existing:
        pubs.setdefault(r["pub_url"], r)
    rows, failed = [], []
    for url, first in pubs.items():
        try:
            picked = next_posts(list(archive(url, since=sp.WINDOWS[0][1])), taken)
        except Exception as e:  # one bad archive should not stop the draw
            failed.append(f"{first['publication']} ({url}): {e}")
            continue
        print(f"{first['publication']}: {len(picked)} new posts")
        rows += [{**blank, "post_id": str(p["id"]), "reader_url": f"https://substack.com/inbox/post/{p['id']}",
                  "category": first["category"], "publication": first["publication"], "pub_url": url,
                  "window": sp.window_of(p["post_date"]), "post_date": p["post_date"][:10],
                  "wordcount": p["wordcount"], "title": p["title"], "draw": "2"} for p in picked]
    return rows, failed


def main(sample=SAMPLE, out=OUT):
    if out.exists():
        sys.exit(f"{out} exists and may hold hand coding; move it aside to draw again.")
    with open(sample, newline="") as f:
        existing = [{**r, "draw": "1"} for r in csv.DictReader(f)]
    rows, failed = new_rows(existing)
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(existing[0]))
        w.writeheader()
        w.writerows(existing + rows)
    print(f"Wrote {len(existing)} existing and {len(rows)} new posts to {out}")
    if failed:
        print(f"{len(failed)} publications failed (rerun after moving {out} aside):\n  " + "\n  ".join(failed))


if __name__ == "__main__":
    args = [ROOT / a for a in sys.argv[1:3]]
    main(*args)
