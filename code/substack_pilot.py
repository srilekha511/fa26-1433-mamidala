"""Draw the posts for the pilot hand check of Substack's AI-detection button.

Usage: python3 code/substack_pilot.py                    the 30-post pilot (2 publications per category)
       python3 code/substack_pilot.py N OUT.csv           N publications per category, into OUT.csv
       (e.g. 11 data/hand_coded/substack_sample.csv for about 200 posts)

Publications: drawn from each category in CATEGORIES (Substack's own listings, so the draw does not favor
writers who discuss Pangram), English only, in rank order within the first listing page, then the next page,
and so on. A larger draw therefore starts with the pilot's publications and posts, and their hand coding is
copied over from the pilot sheet. Posts: from each
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
MAX_PAGES = 10  # 25 publications a page
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


def listed_pubs(cat_id, get=substack.get_json):
    """English publications in a category: ranked within listing page 0, then page 1, and so on."""
    for page in range(MAX_PAGES):
        reply = get(f"https://substack.com/api/v1/category/public/{cat_id}/all?page={page}")
        yield from sorted((p for p in reply.get("publications") or []
                           if (p.get("language") or "en").startswith("en")), key=lambda p: rank(p["id"]))
        if not reply.get("more"):
            return


def carry_over(rows, coded):
    """Copy the hand-coded columns from earlier sheets (dicts keyed by post_id) into matching rows."""
    for r in rows:
        if str(r["post_id"]) in coded:
            r.update({h: coded[str(r["post_id"])][h] for h in HAND})
    return rows


def main(n_pubs=PUBS_PER_CATEGORY, out=OUT):
    if out.exists():
        sys.exit(f"{out} exists and may hold hand coding; move it aside to draw again.")
    ids = {c["name"]: c["id"] for c in substack.get_json("https://substack.com/api/v1/categories")}
    rows = []
    for cat in CATEGORIES:
        taken = 0
        for pub in listed_pubs(ids[cat]):
            if taken == n_pubs:
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
        if taken < n_pubs:
            print(f"{cat}: only {taken} publications with eligible posts")
    if out != OUT and OUT.exists():
        with open(OUT, newline="") as f:
            rows = carry_over(rows, {r["post_id"]: r for r in csv.DictReader(f)})
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} posts to {out}, {sum(bool(r['checked_on']) for r in rows)} already coded")


if __name__ == "__main__":
    if len(sys.argv) == 3:
        main(int(sys.argv[1]), ROOT / sys.argv[2])
    else:
        main()
