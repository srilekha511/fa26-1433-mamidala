"""Build a review table for the expansion subreddits that showed an AI flair in the flair scan.

Usage: python3 code/build_expansion_review.py   (after find_ai_flair_subreddits.py on the AIRules candidates)
Writes data/derived/expansion_review.csv and data/derived/expansion_review.md (the same table, with links,
for reading). API replies are cached in data/raw/arctic/expansion_review/, so a stopped run can be restarted.

For each subreddit: its AI flairs, monthly post counts 2022-2025, an estimate of how many posts carry an
AI flair, moderator posts that mention AI (from Arctic Shift's full-text search, so no full download is
needed yet), its AIRules rule lines about AI, and a suggested decision. Approving a subreddit means
copying its label flairs into data/hand_coded/ai_flairs.csv; the suggestion is only a starting point.
"""

import json
import re
from datetime import datetime, timezone
from statistics import median

import pandas as pd

import arctic
from find_ai_flair_subreddits import CACHE as SAMPLE_CACHE
from reddit_subreddits import FIRST_MONTH, LAST_MONTH, ROOT, SEED_SUBREDDITS
from reddit_text import is_ai_text
from select_controls import AIRULES, DERIVED, mentions_ai, post_counts

CACHE = ROOT / "data" / "raw" / "arctic" / "expansion_review"
MIN_MEDIAN_POSTS = 30   # animearmor's ~17 posts a month made its flaired share swing 0-50%
MIN_FLAIRED = 20        # same floor as data/hand_coded/README.md, but on the estimated total
LAST_USABLE_MONTH = "2025-06"  # a later flair leaves no six-month window inside 2022-2025
TOPIC = re.compile(r"discussion|news|question|prompt", re.IGNORECASE)
QUERIES = ["AI", "generated"]
MAX_PAGES = 15  # 1,500 matching posts; a moderator rule post is rarely deeper in a mid-size subreddit


def load_cache(sub):
    path = CACHE / f"{sub}.json"
    return json.loads(path.read_text()) if path.exists() else {}


def save_cache(sub, cached):
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / f"{sub}.json").write_text(json.dumps(cached))


def search_all(sub, query, max_pages=MAX_PAGES):
    """Posts since FIRST_MONTH matching a full-text query, newest first (oldest-first searches time out
    on larger subreddits). Stops after max_pages pages; the cache records whether it was cut short."""
    out, before = [], int(arctic.month_bounds(LAST_MONTH)[1])
    after = int(arctic.month_bounds(FIRST_MONTH)[0]) - 1
    for _ in range(max_pages):
        page = arctic.get("posts/search", {"subreddit": sub, "query": query, "after": after, "before": before,
                                           "limit": 100, "sort": "desc"})
        out += [p for p in page if p["id"] not in {q["id"] for q in out}]
        if len(page) < 100:
            return out, True
        before = int(page[-1]["created_utc"]) + 1
    return out, False


def fetch(sub):
    cached = load_cache(sub)
    if "counts" not in cached:
        try:
            cached["counts"] = post_counts(sub)
        except RuntimeError as e:
            print(f"  counts failed for r/{sub}: {e}")
    for q in QUERIES:
        if q not in cached.setdefault("search", {}):
            try:
                posts, complete = search_all(sub, q)
            except RuntimeError as e:
                print(f"  search '{q}' failed for r/{sub}: {e}")
                continue
            cached["search"][q] = [slim(p) for p in posts]
            cached.setdefault("search_complete", {})[q] = complete
        save_cache(sub, cached)
    save_cache(sub, cached)
    return cached


def slim(p):
    keep = ["id", "created_utc", "title", "permalink", "author", "distinguished", "stickied", "selftext"]
    return {k: p.get(k) for k in keep}


def is_mod_ai_post(p):
    by_mod = p.get("distinguished") == "moderator" or p.get("stickied") is True
    return by_mod and is_ai_text(f"{p.get('title', '')} {p.get('selftext', '')}")


def search_status(cached):
    """complete, partial (a search hit the page cap) or failed (a search could not run)."""
    done = cached.get("search_complete", {})
    if len(done) < len(QUERIES):
        return "failed"
    return "complete" if all(done.values()) else "partial"


def mod_ai_posts(cached):
    seen, out = set(), []
    for posts in cached.get("search", {}).values():
        for p in posts:
            if p["id"] not in seen and is_mod_ai_post(p):
                seen.add(p["id"])
                out.append(p)
    return sorted(out, key=lambda p: int(p["created_utc"]))


def sample(sub):
    """Month -> the cached 100-post sample from the flair scan."""
    return {m: json.loads((SAMPLE_CACHE / sub / f"{m}.json").read_text())
            for m in arctic.months(FIRST_MONTH, LAST_MONTH) if (SAMPLE_CACHE / sub / f"{m}.json").exists()}


def estimate_flaired(samples, counts, flairs):
    """Flaired posts scaled up from each month's sample to the month's full post count."""
    total = 0.0
    for m, posts in samples.items():
        hits = sum(p.get("link_flair_text") in flairs for p in posts)
        if posts and hits:
            total += hits / len(posts) * max(len(posts), (counts or {}).get(m, len(posts)))
    return round(total)


def rule_lines(text):
    parts = re.split(r"(?<=[.!?])\s+|\n+| - ", text if isinstance(text, str) else "")
    return " | ".join(s.strip() for s in parts if mentions_ai(s))[:400]


def suggest(row):
    reasons = []
    if row["screen_role"] == "ban":
        reasons.append("rules moved to a ban: only useful if treatment widens to bans")
    if row["topic_flair_only"]:
        reasons.append("flair looks like a topic, not a label")
    if row["median_monthly_posts"] is not None and row["median_monthly_posts"] < MIN_MEDIAN_POSTS:
        reasons.append(f"small: median {row['median_monthly_posts']:.0f} posts a month")
    if row["est_flaired_posts"] < MIN_FLAIRED:
        reasons.append(f"about {row['est_flaired_posts']} AI-flaired posts")
    if row["first_flair_month"] > LAST_USABLE_MONTH:
        reasons.append("flair appears after mid-2025")
    if row["median_monthly_posts"] is None:
        reasons.append("post counts unavailable")
    if not reasons:
        return "keep", "date the rule from the moderator posts"
    hard = [r for r in reasons if not r.startswith("post counts")]
    return ("drop" if hard else "check"), "; ".join(reasons)


def main():
    draft = pd.read_csv(DERIVED / "ai_flairs_draft_expansion.csv")
    cands = pd.read_csv(DERIVED / "airules_label_candidates.csv").set_index("subreddit")
    lon = pd.read_csv(AIRULES / "longitudinal_subreddit_set.csv",
                      usecols=["name_nov24", "cleaned_rules_jul23", "cleaned_rules_nov24"])
    lon["subreddit"] = lon["name_nov24"].str.removeprefix("r/")
    lon = lon.drop_duplicates("subreddit").set_index("subreddit")
    seeds = set(SEED_SUBREDDITS)
    rows, details = [], {}
    for sub, flairs in draft.groupby("subreddit", sort=False):
        print(sub)
        cached = fetch(sub)
        counts = cached.get("counts")
        samples = sample(sub)
        names = set(flairs["flair_text"])
        mods = mod_ai_posts(cached)
        recent = [n for m, n in (counts or {}).items() if m >= "2023-01"]
        examples = [p for m in sorted(samples) for p in samples[m] if p.get("link_flair_text") in names][:3]
        row = {
            "subreddit": sub,
            "screen_role": cands.loc[sub, "candidate_for"],
            "subscribers_jul23": int(cands.loc[sub, "subscribers_jul23"]),
            "median_monthly_posts": median(recent) if recent else None,
            "posts_2022_2025": sum(counts.values()) if counts else None,
            "ai_flairs": "; ".join(f"{r.flair_text.strip()} ({r.n})" for r in flairs.itertuples()),
            "topic_flair_only": all(TOPIC.search(f) for f in names),
            "first_flair_month": flairs["first_month"].min(),
            "est_flaired_posts": estimate_flaired(samples, counts, names),
            "n_mod_ai_posts": len(mods),
            "first_mod_ai_post": day(mods[0]) if mods else "",
            "mod_search": search_status(cached),
            "rules_jul23": rule_lines(lon["cleaned_rules_jul23"].get(sub)),
            "rules_nov24": rule_lines(lon["cleaned_rules_nov24"].get(sub)),
            "in_original_seed_scan": sub in seeds,
        }
        row["suggestion"], row["reason"] = suggest(row)
        row["decision"] = ""
        rows.append(row)
        details[sub] = (mods, examples)
    out = pd.DataFrame(rows)
    order = {"keep": 0, "check": 1, "drop": 2}
    out = out.sort_values(["suggestion", "screen_role", "est_flaired_posts"],
                          key=lambda s: s.map(order) if s.name == "suggestion" else s,
                          ascending=[True, True, False])
    out.to_csv(DERIVED / "expansion_review.csv", index=False)
    write_markdown(out, details)
    print(out.groupby(["suggestion", "screen_role"]).size().to_string())


def day(p):
    return datetime.fromtimestamp(int(p["created_utc"]), timezone.utc).date().isoformat()


def link(p):
    return "https://www.reddit.com" + p["permalink"]


def write_markdown(out, details):
    lines = ["# Expansion subreddits: review", "",
             "Generated by `code/build_expansion_review.py`. To approve a subreddit, copy its label flairs into",
             "`data/hand_coded/ai_flairs.csv` (or write `keep` in the `decision` column of `expansion_review.csv`).",
             f"Suggested `keep` needs: median ≥ {MIN_MEDIAN_POSTS} posts a month since 2023, about ≥ {MIN_FLAIRED} "
             f"AI-flaired posts, a flair before {LAST_USABLE_MONTH}, a label flair (not a topic) and a labeling rule "
             "(not a ban). The screen role is a keyword guess from the AIRules rules text.", "",
             "| Suggestion | Subreddit | Screen role | Subscribers (Jul 2023) | Median posts/month | Est. AI-flaired posts | First flair | Mod AI posts | Reason |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in out.itertuples():
        med = "?" if r.median_monthly_posts is None or pd.isna(r.median_monthly_posts) else f"{r.median_monthly_posts:.0f}"
        lines.append(f"| {r.suggestion} | [r/{r.subreddit}](#r{r.subreddit.lower()}) | {r.screen_role} | "
                     f"{r.subscribers_jul23:,} | {med} | {r.est_flaired_posts} | {r.first_flair_month} | "
                     f"{r.n_mod_ai_posts}{'' if r.mod_search == 'complete' else ' (' + r.mod_search + ' search)'} | {r.reason} |")
    for r in out[out["suggestion"] != "drop"].itertuples():
        mods, examples = details[r.subreddit]
        lines += ["", f"## r/{r.subreddit}", "",
                  f"**{r.suggestion}** ({r.screen_role}). Flairs: {r.ai_flairs}.", ""]
        lines.append(f"- Rules, July 2023: {r.rules_jul23 or '(no AI line)'}")
        lines.append(f"- Rules, November 2024: {r.rules_nov24 or '(no AI line)'}")
        lines.append("- Moderator posts mentioning AI:" + ("" if mods else " none found"))
        lines += [f"  - {day(p)} [{p['title'].strip()}]({link(p)})" for p in mods[:8]]
        lines.append("- Example flaired posts: " + ", ".join(f"[{day(p)}]({link(p)})" for p in examples))
    (DERIVED / "expansion_review.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
