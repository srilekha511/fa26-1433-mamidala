"""Draw the posts for the pilot hand check of Substack's AI-detection button.

Usage: python3 code/substack_pilot.py

Publications: PUBS_PER_CATEGORY drawn from the first page of each category in CATEGORIES (Substack's own
listings, so the draw does not favor writers who discuss Pangram), English only. Posts: from each
publication, one free newsletter post of at least MIN_WORDS words (the scanner's minimum) in each window
after the 2026-07-21 launch. Draws use a rank fixed by the id, so rerunning gives the same sheet.

The July 21 to August posts check whether "AI detection unavailable" can mean anything other than the
author turning detection off.

Writes data/hand_coded/substack_pilot.csv (refuses to overwrite it, since it is filled in by hand). Open
each reader_url while logged in, choose "Scan for AI text" from the ... menu, and fill in the blank columns:
checked_on, status (scannable / unavailable / no_option), statement (yes / no), statement_text, ai_pct,
ai_assisted_pct, human_pct, seconds (time taken for the post) and notes.
"""

import csv
import sys
import zlib

from reddit_subreddits import ROOT
import substack

OUT = ROOT / "data" / "hand_coded" / "substack_pilot.csv"
SEED = 1433
CATEGORIES = ["Technology", "U.S. Politics", "Finance", "Culture", "Health & Wellness", "Fiction"]
PUBS_PER_CATEGORY = 2
MIN_WORDS = 100
WINDOWS = [("jul21_aug", "2026-07-21", "2026-09-01"), ("sep", "2026-09-01", "2026-10-01"),
           ("oct", "2026-10-01", "2026-11-01")]
HAND = ["checked_on", "status", "statement", "statement_text", "ai_pct", "ai_assisted_pct", "human_pct",
        "seconds", "notes"]


def rank(item_id):
    return zlib.crc32(f"{SEED}:{item_id}".encode())


def window_of(post_date):
    for name, start, end in WINDOWS:
        if start <= post_date < end:
            return name
    return None


def eligible(posts):
    return [p for p in posts if p["audience"] == "everyone" and p["type"] == "newsletter"
            and (p.get("wordcount") or 0) >= MIN_WORDS]


def pick_posts(posts):
    """The lowest-ranked eligible post in each window, oldest window first."""
    picked = []
    for name, _, _ in WINDOWS:
        inside = [p for p in eligible(posts) if window_of(p["post_date"]) == name]
        if inside:
            picked.append(min(inside, key=lambda p: rank(p["id"])))
    return picked


def main():
    if OUT.exists():
        sys.exit(f"{OUT} exists and may hold hand coding; move it aside to draw again.")
    ids = {c["name"]: c["id"] for c in substack.get_json("https://substack.com/api/v1/categories")}
    rows = []
    for cat in CATEGORIES:
        pubs = substack.get_json(f"https://substack.com/api/v1/category/public/{ids[cat]}/all?page=0")["publications"]
        pubs = sorted((p for p in pubs if (p.get("language") or "en").startswith("en")), key=lambda p: rank(p["id"]))
        taken = 0
        for pub in pubs:
            if taken == PUBS_PER_CATEGORY:
                break
            url = f"https://{pub['subdomain']}.substack.com"
            picked = pick_posts(list(substack.iter_archive(url, since=WINDOWS[0][1])))
            print(f"{cat}: {pub['name']} ({url}): {len(picked)} posts")
            if not picked:
                continue
            taken += 1
            rows += [{"post_id": p["id"], "reader_url": f"https://substack.com/inbox/post/{p['id']}",
                      "category": cat, "publication": pub["name"], "pub_url": url,
                      "window": window_of(p["post_date"]), "post_date": p["post_date"][:10],
                      "wordcount": p["wordcount"], "title": p["title"], **{h: "" for h in HAND}} for p in picked]
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} posts to {OUT}")


if __name__ == "__main__":
    main()
