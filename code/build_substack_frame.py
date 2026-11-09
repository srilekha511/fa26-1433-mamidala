"""Build the Substack publication frame and pull each sampled publication's post list.

Usage: python3 code/build_substack_frame.py list      snapshot every category listing (dated file, never overwritten)
       python3 code/build_substack_frame.py archive   draw publications and save their archives until each
                                                      category has PER_CATEGORY active ones
       python3 code/build_substack_frame.py status    progress so far

Frame: Substack's own category listings, snapshotted once (data/raw/substack/listings_<date>.csv) so every later
step draws from the same list. A publication listed under several categories counts for the first one it
appears in, in the order of the categories reply. Only English publications are kept.

Draw: within each category, publications are taken in a fixed random order (crc32 of SEED and the id, as in
substack_pilot.py). Each is kept if it posted at least MIN_PRE eligible posts (free newsletter posts of at least
MIN_WORDS words) between PRE_START and the 2026-07-21 launch, so it was active before Pangram arrived, and
draws continue until the category has PER_CATEGORY kept or runs out. The archive of every publication checked,
kept or not, is saved to data/raw/substack/archive/<pub_id>.jsonl (one archive item per line: date, word count,
audience, reactions, comments, restacks; no text), and the decision to data/derived/substack_frame.csv, which
is appended to after every publication so a rerun resumes.

Listings are as of the snapshot date, after the launch: a publication that stopped writing because of the
scanner before the snapshot can drop off the listings. The memo should say so.
"""

import csv
import json
import sys
import zlib
from datetime import date
from pathlib import Path

import pandas as pd

from reddit_subreddits import ROOT
import substack

RAW = ROOT / "data" / "raw" / "substack"
ARCHIVE = RAW / "archive"
FRAME = ROOT / "data" / "derived" / "substack_frame.csv"
SEED = 1433
MAX_PAGES = 20  # 25 publications a page
PER_CATEGORY = 10
PRE_START, LAUNCH = "2026-01-01", "2026-07-21"
MIN_PRE, MIN_WORDS = 3, 100
FRAME_FIELDS = ["category", "draw_order", "pub_id", "name", "subdomain", "custom_domain", "kept", "n_posts",
                "n_pre", "n_post", "first_post", "checked_on"]


def rank(item_id):
    return zlib.crc32(f"{SEED}:{item_id}".encode())


def list_category(cat_id, get=substack.get_json):
    """Every publication in one category listing, in Substack's order."""
    out = []
    for page in range(MAX_PAGES):
        reply = get(f"https://substack.com/api/v1/category/public/{cat_id}/all?page={page}")
        out += reply.get("publications") or []
        if not reply.get("more"):
            break
    return out


def snapshot(get=substack.get_json, today=None):
    path = RAW / f"listings_{today or date.today().isoformat()}.csv"
    if path.exists():
        sys.exit(f"{path} exists; the frame is a single snapshot.")
    rows = []
    for cat in get("https://substack.com/api/v1/categories"):
        pubs = list_category(cat["id"], get=get)
        print(f"{cat['name']}: {len(pubs)}")
        rows += [{"category": cat["name"], "position": i, "pub_id": p["id"], "name": p.get("name"),
                  "subdomain": p.get("subdomain"), "custom_domain": p.get("custom_domain"),
                  "language": p.get("language")} for i, p in enumerate(pubs)]
    RAW.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)
    print(f"Wrote {len(rows)} listings to {path}")


def frame_order(listings):
    """English publications, each under its first category, in draw order within category."""
    df = listings[listings["language"].fillna("en").str.startswith("en")].drop_duplicates("pub_id")
    df = df.assign(draw_order=df["pub_id"].map(rank)).sort_values(["category", "draw_order"])
    return df.reset_index(drop=True)


def eligible(p):
    return p.get("audience") == "everyone" and p.get("type") == "newsletter" and (p.get("wordcount") or 0) >= MIN_WORDS


def activity(posts):
    elig = [p for p in posts if eligible(p)]
    return {"n_posts": len(posts), "n_pre": sum(PRE_START <= p["post_date"] < LAUNCH for p in elig),
            "n_post": sum(p["post_date"] >= LAUNCH for p in elig),
            "first_post": min((p["post_date"][:10] for p in posts), default="")}


def latest_listings():
    files = sorted(RAW.glob("listings_*.csv"))
    if not files:
        sys.exit("No listings snapshot yet; run `list` first.")
    return pd.read_csv(files[-1], dtype={"pub_id": str})


def done_frame():
    return pd.read_csv(FRAME, dtype={"pub_id": str}) if FRAME.exists() else pd.DataFrame(columns=FRAME_FIELDS)


def pull_archives(order, done, fetch_archive=substack.iter_archive, today=None):
    """Check publications in draw order until each category has PER_CATEGORY kept; append each to FRAME."""
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    FRAME.parent.mkdir(parents=True, exist_ok=True)
    checked = set(done["pub_id"])
    kept = done[done["kept"].astype(bool)].groupby("category").size().to_dict()
    new = not FRAME.exists()
    with open(FRAME, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FRAME_FIELDS)
        if new:
            w.writeheader()
        for _, pub in order.iterrows():
            if pub["pub_id"] in checked or kept.get(pub["category"], 0) >= PER_CATEGORY:
                continue
            url = f"https://{pub['subdomain']}.substack.com"
            posts = list(fetch_archive(url, since=PRE_START))
            with open(ARCHIVE / f"{pub['pub_id']}.jsonl", "w") as a:
                a.writelines(json.dumps(p) + "\n" for p in posts)
            act = activity(posts)
            ok = act["n_pre"] >= MIN_PRE
            kept[pub["category"]] = kept.get(pub["category"], 0) + ok
            w.writerow({**{k: pub[k] for k in ["category", "draw_order", "pub_id", "name", "subdomain",
                                                 "custom_domain"]},
                        "kept": int(ok), **act, "checked_on": today or date.today().isoformat()})
            f.flush()
            print(f"{pub['category']}: {pub['name']}: {act['n_pre']} pre, {act['n_post']} post"
                  f"{'' if ok else ' (dropped)'}  [{kept[pub['category']]}/{PER_CATEGORY}]")
    return kept


def status():
    df = done_frame()
    print(df.groupby("category").agg(checked=("pub_id", "size"), kept=("kept", "sum")).to_string())
    print(f"\n{int(df['kept'].sum())} kept of {len(df)} checked")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "list":
        snapshot()
    elif cmd == "archive":
        pull_archives(frame_order(latest_listings()), done_frame())
    elif cmd == "status":
        status()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
