"""Build the sample for the AI-ban event study: subreddits that banned AI content between the two AIRules
crawls, dated from Reddit's own rule timestamps, plus never-treated comparison subreddits.

Usage: python3 code/build_ban_sample.py   (needs data/raw/airules/)
Writes data/derived/ban_sample.csv (every candidate, its ban rule and why it was kept or dropped),
data/derived/ban_controls.csv and data/derived/ban_monthly_posts.csv (monthly post counts, 2022-2025, for
banned and comparison subreddits). API replies are cached in data/raw/arctic/ban_counts/, so a stopped run
can simply be restarted.

The rule, fixed before looking at any outcome:
1. Population: subreddits in both AIRules crawls (July 2023 and November 2024; Lloyd et al. 2025).
2. Treated: no AI words in the July 2023 rules, and a November 2024 rule that bans AI content (BAN wording,
   no labeling wording) created after the July 2023 crawl. The ban date is that rule's `created_utc`, which
   Reddit sets when a rule is added. On the original study subreddits it matches the hand-coded dates to
   within about a week. Reddit keeps the timestamp when a rule is edited, so a ban written into an older
   rule cannot be dated and is dropped.
3. Comparison: subreddits with no AI rule in either crawl (select_controls.load_population). For each
   treated subreddit, the CONTROLS_PER nearest by log July 2023 subscribers in its AIRules topic, without
   replacement.
4. Both need at least MIN_SUBSCRIBERS subscribers in July 2023; the activity floor is applied in
   analyze_ban_did.py, once the counts are in.
"""

import ast
import json
import re
import time
import urllib.parse
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import arctic
from reddit_subreddits import FIRST_MONTH, LAST_MONTH, ROOT
from select_controls import AIRULES, DERIVED, load_population, mentions_ai

CACHE = ROOT / "data" / "raw" / "arctic" / "ban_counts"
JUL23_CRAWL, NOV24_CRAWL = "2023-07-13", "2024-11-14"  # day after the last rule timestamp in each crawl
MIN_SUBSCRIBERS, CONTROLS_PER = 1000, 2
AI = r"(ai|a\.i\.|chat ?gpt|midjourney|stable diffusion|dall-?e|generative|generated|llms?)"
BAN = re.compile(
    rf"\bno\b[^.\n]{{0,40}}\b{AI}\b"
    rf"|\b{AI}\b[^.\n]{{0,80}}\b(not (be )?allowed|prohibited|banned|forbidden|not permitted|not accepted"
    rf"|will be removed|are removed|is removed|not welcome)"
    rf"|\b(do not|don't|never) (post|submit|share|use)\b[^.\n]{{0,40}}\b{AI}\b",
    re.IGNORECASE)
# Rules that ask for a label or limit AI posts are not bans.
NOT_BAN = re.compile(r"not (strictly |entirely |completely |outright )?(prohibited|banned|forbidden)"
                     r"|flair|tag(ged)?\b|label|disclos|credit|mark(ed)? as|only on|allowed on", re.IGNORECASE)


def parse_rules(text):
    """The rule list from a crawl: JSON in November 2024, a Python literal in July 2023."""
    if not isinstance(text, str):
        return []
    try:
        return json.loads(text)
    except ValueError:
        return ast.literal_eval(text)


def rule_text(rule):
    return f"{rule.get('short_name', '')}: {rule.get('description', '')}"


def is_ban(text):
    return bool(BAN.search(text)) and not NOT_BAN.search(text)


def day(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")


def ban_event(rules_jul23, rules_nov24):
    """(ban date, ban rule text, whether every rule was re-created that day) or a reason it is not a dated ban."""
    if any(mentions_ai(rule_text(r)) for r in parse_rules(rules_jul23)):
        return {"drop": "AI rule already in July 2023"}
    rules = parse_rules(rules_nov24)
    bans = [r for r in rules if is_ban(rule_text(r))]
    if not bans:
        return {"drop": "no ban wording"}
    first = min(bans, key=lambda r: r["created_utc"])
    date = day(first["created_utc"])
    if not JUL23_CRAWL <= date <= NOV24_CRAWL:
        return {"drop": "ban rule created before July 2023 and edited later: undated", "ban_rule": rule_text(first)}
    return {"ban_date": date, "ban_rule": rule_text(first),
            "rules_rewritten": all(day(r["created_utc"]) == date for r in rules)}


def candidates():
    lon = pd.read_csv(AIRULES / "longitudinal_subreddit_set.csv",
                      usecols=["id", "name_nov24", "subscribers_jul23", "rules_jul23", "rules_nov24"])
    lon = lon[lon["rules_jul23"].notna() & lon["rules_nov24"].notna()
              & (lon["subscribers_jul23"] >= MIN_SUBSCRIBERS)]
    # Cheap screen before parsing every rule list: some rule mentions AI in November 2024.
    lon = lon[lon["rules_nov24"].map(mentions_ai)]
    events = pd.DataFrame([ban_event(a, b) for a, b in zip(lon["rules_jul23"], lon["rules_nov24"])],
                          index=lon.index)
    out = lon[["id", "name_nov24", "subscribers_jul23"]].join(events)
    out["subreddit"] = out.pop("name_nov24").str.removeprefix("r/")
    return out[out["drop"] != "no ban wording"]


def pick_controls(treated, pop, k=CONTROLS_PER):
    """The k nearest never-treated subreddits by log subscribers within each treated subreddit's topic."""
    pool = pop[~pop["ai_rule"] & (pop["subscribers_jul23"] >= MIN_SUBSCRIBERS)
               & ~pop["subreddit"].isin(treated["subreddit"])].copy()
    pool["log_subs"] = np.log(pool["subscribers_jul23"])
    used, out = set(), []
    for _, t in treated.sort_values("subscribers_jul23", ascending=False).iterrows():
        c = pool[(pool["topic_label"] == t["topic_label"]) & ~pool["subreddit"].isin(used)]
        near = c.assign(gap=(c["log_subs"] - np.log(t["subscribers_jul23"])).abs()).nsmallest(k, "gap")
        used.update(near["subreddit"])
        out += [{"subreddit": s, "topic_label": t["topic_label"], "subscribers_jul23": n, "matched_to": t["subreddit"]}
                for s, n in zip(near["subreddit"], near["subscribers_jul23"])]
    return pd.DataFrame(out)


def fetch_counts(sub, tries=6):
    """2022-2025 monthly post counts from Arctic Shift's precomputed time series. They match the aggregate
    endpoint's counts to within a post, and unlike it they do not time out on busy subreddits."""
    url = f"{arctic.BASE}/time_series?" + urllib.parse.urlencode(
        {"key": f"r/{sub}/posts/count", "precision": "month",
         "after": f"{FIRST_MONTH}-01", "before": f"{pd.Period(LAST_MONTH, 'M') + 1}-01"})
    for attempt in range(tries):
        try:
            body = arctic.http_get_json(url)
            if body.get("data") is not None and not body.get("error"):
                time.sleep(1)
                return {day(x["date"])[:7]: int(x["value"]) for x in body["data"]}
            print(f"  r/{sub}: {body.get('error')}")
        except Exception as e:
            print(f"  r/{sub}: {e}")
        time.sleep(20 * (attempt + 1))
    raise RuntimeError(f"failed after {tries} tries: {url}")


def counts(sub):
    """Cached counts, or None if they could not be fetched (also cached, so a restart does not retry)."""
    path = CACHE / f"{sub}.json"
    if path.exists():
        return json.loads(path.read_text())
    try:
        c = fetch_counts(sub)
    except RuntimeError as e:
        print(f"  counts failed for r/{sub}: {e}")
        c = None
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(c))
    return c


def main():
    pop = load_population()
    cands = candidates().merge(pop[["id", "topic_label", "is_content_generation_ca_label"]], on="id", how="left")
    cands["drop"] = cands["drop"].fillna("")
    treated = cands[cands["drop"] == ""]
    print(f"{len(cands)} candidates with ban wording; {len(treated)} dated bans")
    print(cands["drop"].replace("", "kept").value_counts().to_string())
    controls = pick_controls(treated, pop)
    print(f"{len(controls)} comparison subreddits")

    rows = []
    subs = [("treated", s) for s in treated["subreddit"]] + [("control", s) for s in controls["subreddit"]]
    for i, (role, sub) in enumerate(subs, 1):
        c = counts(sub)
        print(f"[{i}/{len(subs)}] r/{sub} {role}: {'failed' if c is None else sum(c.values())}", flush=True)
        rows += [{"subreddit": sub, "role": role, "month": m, "posts": n} for m, n in (c or {}).items()]

    cands.to_csv(DERIVED / "ban_sample.csv", index=False)
    controls.to_csv(DERIVED / "ban_controls.csv", index=False)
    pd.DataFrame(rows).to_csv(DERIVED / "ban_monthly_posts.csv", index=False)


if __name__ == "__main__":
    main()
