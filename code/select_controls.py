"""Pick comparison subreddits for the switchers' post-count outcome from the AIRules population.

Usage: python3 code/select_controls.py   (after build_reddit_posts.py; needs data/raw/airules/)
Writes data/derived/control_shortlist.csv (every candidate with its features and why it was dropped),
data/derived/control_matches.csv (the chosen controls) and data/derived/control_monthly_posts.csv
(monthly post counts for switchers and their controls, 2022-2025). API replies are cached in
data/raw/arctic/control_sample/, so a stopped run can simply be restarted.

The rule, fixed before looking at any outcome:
1. Population: English subreddits in AIRules seen in both July 2023 and November 2024 (Lloyd et al. 2025).
2. Drop any subreddit with an AI rule in either snapshot, by the AIRules label or by AI words in its rules.
3. Keep Content Generation communities in the switcher's own AIRules topic.
4. Shortlist the SHORTLIST nearest by log July 2023 subscribers, per switcher.
5. Drop candidates that are mostly NSFW, have a month with no posts in the 12 months before the
   switcher's mandate, or show an AI flair in a June 2025 sample (an AI rule after November 2024).
6. Match K controls per switcher on those 12 months: mean log posts per month, the trend in log posts,
   and the image share of a 100-post sample. Nearest first, without replacement.
7. Fetch 2022-2025 counts for the matches only. A match whose counts fail or that has a month with no
   posts is dropped and replaced by the next nearest candidate.

Counting a whole year of a very large subreddit times out on Arctic Shift, so step 6 needs only the
12-month window and step 7 only the matches.
"""

import json
import re
import sys

import numpy as np
import pandas as pd

import arctic
from fetch_reddit_dumps import month_buckets, monthly_counts
from reddit_subreddits import FIRST_MONTH, LAST_MONTH, ROOT
from reddit_text import AI_PATTERN, post_type

AIRULES = ROOT / "data" / "raw" / "airules"
CACHE = ROOT / "data" / "raw" / "arctic" / "control_sample"
DERIVED = ROOT / "data" / "derived"
RULE_DATES = ROOT / "data" / "hand_coded" / "reddit_rule_dates.csv"
SHORTLIST, K, PRE_MONTHS = 15, 3, 12
LATE_MONTH = "2025-06"
IMAGE_TYPES = {"image", "gallery"}
# AI words the general pattern misses in image communities' rules.
IMAGE_AI = re.compile(r"midjourney|stable ?diffusion|dall-?e|generative|genai", re.IGNORECASE)


def mentions_ai(text):
    text = text if isinstance(text, str) else ""
    return bool(AI_PATTERN.search(text) or IMAGE_AI.search(text))


def load_population():
    """AIRules subreddits seen in July 2023 and November 2024, with topic and AI-rule flags."""
    lon = pd.read_csv(AIRULES / "longitudinal_subreddit_set.csv",
                      usecols=["id", "name_nov24", "subscribers_jul23", "cleaned_rules_jul23",
                               "cleaned_rules_nov24", "has_ai_rule_label_jul23", "has_ai_rule_label_nov24"])
    rules = pd.read_csv(AIRULES / "rules_subreddit_set.csv",
                        usecols=["id", "topic_label", "is_content_generation_ca_label", "has_ai_rule_label"])
    d = lon.merge(rules, on="id")
    labels = ["has_ai_rule_label_jul23", "has_ai_rule_label_nov24", "has_ai_rule_label"]
    d["ai_rule"] = (d[labels].fillna(False).astype(bool).any(axis=1)
                    | d["cleaned_rules_jul23"].map(mentions_ai) | d["cleaned_rules_nov24"].map(mentions_ai))
    d["subreddit"] = d["name_nov24"].str.removeprefix("r/")
    return d.drop(columns=["cleaned_rules_jul23", "cleaned_rules_nov24"])


def pre_window(mandatory_start, n=PRE_MONTHS):
    """The n months before the month of mandatory_start (YYYY-MM-DD), oldest first."""
    end = pd.Period(mandatory_start[:7], "M")
    return [str(end - i) for i in range(n, 0, -1)]


def volume_features(counts, months):
    """Mean and per-month trend of log(1 + posts) over the given months."""
    y = np.log1p([counts.get(m, 0) for m in months])
    return {"mean_log_posts": float(y.mean()), "trend_log_posts": float(np.polyfit(np.arange(len(y)), y, 1)[0])}


def sample_features(posts):
    """Image share, NSFW share and AI flairs in a sample of posts."""
    n = max(len(posts), 1)
    return {"image_share": sum(post_type(p) in IMAGE_TYPES for p in posts) / n,
            "nsfw_share": sum(bool(p.get("over_18")) for p in posts) / n,
            "ai_flair": any(AI_PATTERN.search(p.get("link_flair_text") or "") for p in posts)}


def shortlist(pop, switchers, size=SHORTLIST):
    """The size candidates nearest each switcher in log subscribers, within its topic."""
    pool = pop[~pop["ai_rule"] & (pop["is_content_generation_ca_label"] == True)
               & ~pop["subreddit"].str.lower().isin(s.lower() for s in switchers["subreddit"])]
    out = []
    for _, s in switchers.iterrows():
        c = pool[pool["topic_label"] == s["topic_label"]].copy()
        c["size_gap"] = (np.log(c["subscribers_jul23"]) - np.log(s["subscribers_jul23"])).abs()
        out.append(c.nsmallest(size, "size_gap").assign(switcher=s["subreddit"]))
    return pd.concat(out, ignore_index=True)


def match(cands, treated, features, k=K):
    """Assign k controls per switcher, closest standardized distance first, no control used twice."""
    scale = cands[features].std().replace(0, 1)
    pairs = []
    for _, c in cands.iterrows():
        t = treated.loc[c["switcher"], features]
        pairs.append((float(np.sqrt((((c[features] - t) / scale) ** 2).sum())), c["switcher"], c["subreddit"]))
    taken, used, out = {}, set(), []
    for dist, sw, sub in sorted(pairs):
        if taken.get(sw, 0) < k and sub not in used:
            taken[sw] = taken.get(sw, 0) + 1
            used.add(sub)
            out.append({"switcher": sw, "control": sub, "distance": round(dist, 3)})
    return pd.DataFrame(out)


def aggregate_months(sub, first, last, tries=6):
    """Monthly post counts for first..last (YYYY-MM) in one aggregate request."""
    after = f"{first}-01"
    before = f"{pd.Period(last, 'M') + 1}-01"
    return month_buckets(arctic.get("posts/search/aggregate", {"aggregate": "created_utc", "frequency": "month",
                                                               "subreddit": sub, "after": after, "before": before},
                                    tries=tries))


def window_counts(sub, months):
    """Counts for a run of months: one request, or one request per month if that times out."""
    try:
        return aggregate_months(sub, months[0], months[-1], tries=2)
    except RuntimeError:
        return {m: aggregate_months(sub, m, m).get(m, 0) for m in months}


def post_counts(sub):
    """2022-2025 counts: one request, or one request per year if that times out."""
    try:
        return aggregate_months(sub, FIRST_MONTH, LAST_MONTH, tries=2)
    except RuntimeError:
        return monthly_counts("posts/search", sub)


def load_cache(sub):
    path = CACHE / f"{sub}.json"
    return json.loads(path.read_text()) if path.exists() else {}


def save_cache(sub, cached):
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / f"{sub}.json").write_text(json.dumps(cached))


def fetch_candidate(sub, window):
    """Counts for the pre-mandate window plus 100-post samples from its last month and LATE_MONTH."""
    cached = load_cache(sub)
    key = f"{window[0]}..{window[-1]}"
    if key not in cached.setdefault("windows", {}):
        full = cached.get("counts")
        cached["windows"][key] = {m: full.get(m, 0) for m in window} if full else window_counts(sub, window)
    for m in (window[-1], LATE_MONTH):
        if m not in cached.setdefault("samples", {}):
            start, end = arctic.month_bounds(m)
            cached["samples"][m] = arctic.get(
                "posts/search", {"subreddit": sub, "after": start - 1, "before": end, "limit": 100, "sort": "desc"})
    save_cache(sub, cached)
    return cached["windows"][key], cached["samples"]


def full_counts(sub):
    cached = load_cache(sub)
    if "counts" not in cached:
        cached["counts"] = post_counts(sub)
        save_cache(sub, cached)
    return cached["counts"]


def local_switcher(sub, month):
    """The same counts and newest-100 sample for a switcher, from the posts already downloaded."""
    folder = ROOT / "data" / "raw" / "arctic" / "posts" / sub
    counts = {p.stem: sum(1 for _ in open(p)) for p in folder.glob("*.jsonl")}
    posts = sorted(map(json.loads, open(folder / f"{month}.jsonl")), key=lambda p: -int(p["created_utc"]))
    return counts, posts[:100]


def main():
    rules = pd.read_csv(RULE_DATES)
    switchers = rules[rules["group"] == "switcher"][["subreddit", "mandatory_start"]]
    pop = load_population()
    switchers = switchers.merge(pop[["subreddit", "subscribers_jul23", "topic_label"]], on="subreddit")
    print(f"population {len(pop):,}; no AI rule {(~pop['ai_rule']).sum():,}")

    cands = shortlist(pop, switchers)
    windows = {s["subreddit"]: pre_window(s["mandatory_start"]) for _, s in switchers.iterrows()}
    feats = []
    for i, c in cands.iterrows():
        window = windows[c["switcher"]]
        try:
            n, samples = fetch_candidate(c["subreddit"], window)
        except RuntimeError as e:
            print(f"skip r/{c['subreddit']}: {e}")
            feats.append({"drop": "fetch failed"})
            continue
        late = sample_features(samples[LATE_MONTH])
        f = {**volume_features(n, window), **sample_features(samples[window[-1]])}
        f["drop"] = ("nsfw" if f["nsfw_share"] > 0.5 else
                     "month with no posts" if min(n.get(m, 0) for m in window) == 0 else
                     "AI flair in 2025" if late["ai_flair"] or f["ai_flair"] else "")
        feats.append(f)
        print(f"{i + 1}/{len(cands)} r/{c['subreddit']} for r/{c['switcher']}: {f['drop'] or 'ok'}")
    cands = pd.concat([cands, pd.DataFrame(feats, index=cands.index)], axis=1)

    treated, counts = {}, {}
    for _, s in switchers.iterrows():
        window = windows[s["subreddit"]]
        n, sample = local_switcher(s["subreddit"], window[-1])
        counts[s["subreddit"]] = n
        treated[s["subreddit"]] = {**volume_features(n, window), **sample_features(sample)}
    treated = pd.DataFrame(treated).T
    features = ["mean_log_posts", "trend_log_posts", "image_share"]

    all_months = arctic.months(FIRST_MONTH, LAST_MONTH)
    while True:
        matches = match(cands[cands["drop"] == ""], treated, features)
        bad = []
        for sub in matches["control"]:
            try:
                counts[sub] = full_counts(sub)
            except RuntimeError as e:
                print(f"drop match r/{sub}: {e}")
                bad.append((sub, "2022-2025 counts failed"))
                continue
            if min(counts[sub].get(m, 0) for m in all_months) == 0:
                bad.append((sub, "month with no posts in 2022-2025"))
        if not bad:
            break
        for sub, why in bad:
            print(f"replace r/{sub}: {why}")
            cands.loc[cands["subreddit"] == sub, "drop"] = why
    cands.to_csv(DERIVED / "control_shortlist.csv", index=False)
    matches = matches.merge(cands[["switcher", "subreddit", "topic_label", "subscribers_jul23"] + features],
                            left_on=["switcher", "control"], right_on=["switcher", "subreddit"]).drop(columns="subreddit")
    matches.to_csv(DERIVED / "control_matches.csv", index=False)

    rows = [{"subreddit": s, "role": "switcher", "switcher": s, "month": m, "posts": counts[s].get(m, 0)}
            for s in switchers["subreddit"] for m in all_months]
    rows += [{"subreddit": r["control"], "role": "control", "switcher": r["switcher"], "month": m,
              "posts": counts[r["control"]].get(m, 0)}
             for _, r in matches.iterrows() for m in all_months]
    pd.DataFrame(rows).to_csv(DERIVED / "control_monthly_posts.csv", index=False)

    print("\nswitchers:\n" + treated[features].round(3).to_string())
    print("\nmatches:\n" + matches.round(3).to_string(index=False))
    print("\ndropped:\n" + cands["drop"].replace("", "kept").value_counts().to_string())


if __name__ == "__main__":
    sys.exit(main())
