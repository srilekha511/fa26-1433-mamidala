"""Reader side of the Substack study: do readers engage less with posts that have detection off, or that are AI?

Usage: python3 code/analyze_substack_readers.py           estimates
       python3 code/analyze_substack_readers.py callouts  list every comment the call-out pattern matches, with
                                                          the post's status and score, for a check by hand

Inputs: the coded sample and its publication patterns (analyze_substack_sample), the Pangram API scores of the
detection-off posts (score_substack_off), engagement (fetch_substack_engagement) and saved comments.

Each eligible post gets an AI score: the reader scan for scannable posts and the API for posts with detection
off (the two agree closely; see substack_api_estimates.csv). ai50 = score at or above 50.

Engagement outcomes: log(1 + likes), log(1 + comments), log(1 + restacks), counted on the fetch date. Every model
controls for log post age in days and log word count, and clusters standard errors by publication (CR1, t with
publications - 1 degrees of freedom).
  within       publication fixed effects: off is identified from the publications that switch, ai50 from
               publications whose posts differ in AI. This is the main specification.
  within_x     adds off x ai50: is a withheld AI post penalized differently from a scannable one?
  between      category fixed effects instead of publication ones: compares publications, so it mixes the
               effect of a label with differences in audience size. Descriptive only.
  labels       adds after (published on or after the reader labels, LABELS_DATE) and its interactions with off
               and ai50: did AI or withheld posts lose engagement once scan results became more visible? Few
               posts are from after the date, so this is weak.

Call-outs: a post is called out if any comment matches the Reddit call-out pattern (CALLOUT, copied from
analyze_ban_readers.py on the reddit-pipeline branch, where it was refined against hand codes), unless the
match is coded 0 in CALLOUT_CODES.

Writes output/substack_readers_estimates.csv and output/substack_readers_summary.csv.
"""

import json
import re
import sys

import numpy as np
import pandas as pd
from scipy.stats import t as t_dist

import analyze_substack_sample as a
from reddit_subreddits import ROOT

ENGAGEMENT = ROOT / "data" / "derived" / "substack_engagement.csv"
COMMENTS = ROOT / "data" / "raw" / "substack_comments"
CALLOUT_CODES = ROOT / "data" / "hand_coded" / "substack_callout_codes.csv"
OUT_DIR = ROOT / "output"
OUTCOMES = {"log_likes": "reaction_count", "log_comments": "comment_count", "log_restacks": "restacks"}

AI = r"(ai|a\.i\.|chat ?gpt|gpt|an? llm|llms?|a bot|a chatbot|chatbots?)"
CALLOUT = re.compile(
    rf"\b(you|u|op)\b[^.\n?]{{0,12}}\b(use|used|using)\s+(an? )?{AI}\b"
    rf"|\b(it|this|that|something|someone)\b[^.\n?]{{0,15}}\b(written|generated|produced|wrote|made)\s+(by|with|using)\b"
    rf"[^.\n]{{0,10}}\b{AI}\b"
    rf"|\b(is this|was this|is that|this is|this was|it is|it's|its)\s+(literally |clearly |obviously |definitely |just |"
    rf"so |totally )?(an? )?{AI}(?!\s+(art|image|images|tool|tools|model|models|assistant|generators?|is|are|can|"
    rf"will|should|content))\b"
    rf"|\b(reads|sounds|looks|feels|seems)\s+(like|as if)\s+(an? |some )?{AI}\b"
    rf"|\b{AI}[- ](slop|garbage|drivel|nonsense)\b",
    re.IGNORECASE)
SHORT_CALLOUT = re.compile(rf"\b{AI}[- ](generated|written)\b|\b(obviously|clearly|definitely)\s+{AI}\b", re.IGNORECASE)
SHORT = 60


def is_callout(text):
    if not text:
        return False
    return CALLOUT.search(text) is not None or (len(text) <= SHORT and SHORT_CALLOUT.search(text) is not None)


def flatten(comments):
    """Every comment in a reply tree, replies included."""
    out = []
    for c in comments or []:
        out.append(c)
        out += flatten(c.get("children"))
    return out


def load_comments(folder=COMMENTS):
    """{post_id: [comment dicts]} for every saved comment file."""
    return {p.stem: flatten(json.loads(p.read_text()).get("comments")) for p in folder.glob("*.json")}


def load_codes(path=CALLOUT_CODES):
    if not path.exists():
        return {}
    c = pd.read_csv(path, dtype={"comment_id": str})
    return dict(zip(c["comment_id"], c["callout"].astype(int)))


def callout_flags(comments, codes):
    """{post_id: (n comments saved, 1 if any comment is a call-out)}."""
    return {pid: (len(cs), float(any(is_callout(c.get("body")) and codes.get(str(c.get("id")), 1) for c in cs)))
            for pid, cs in comments.items()}


def build(df, scores, eng, comments=None, codes=None):
    """Eligible posts with AI score, engagement, age and call-out flag."""
    e = df[df["eligible"]].copy()
    pubs = a.publications(df).set_index("publication")
    e["pattern"] = e["publication"].map(pubs["pattern"])
    api = dict(zip(scores["id"].astype(str), 100 * scores["fraction_ai"]))
    e["score"] = np.where(e["off"], e["post_id"].map(api), e["ai_pct"])
    e["ai50"] = (e["score"] >= a.AI_FLAG).astype(float).where(e["score"].notna())
    e = e.merge(eng, on="post_id", how="left")
    age = (pd.to_datetime(e["fetched_at"]) - pd.to_datetime(e["post_date"])).dt.days
    e["log_age"] = np.log(age.clip(lower=1))
    e["log_words"] = np.log(pd.to_numeric(e["wordcount"]).clip(lower=1))
    for name, col in OUTCOMES.items():
        e[name] = np.log1p(pd.to_numeric(e[col]))
    e["off"] = e["off"].astype(float)
    flags = callout_flags(comments or {}, codes or {})
    e["n_comments_saved"] = e["post_id"].map(lambda p: flags.get(p, (0, np.nan))[0])
    e["callout"] = e["post_id"].map(lambda p: flags.get(p, (0, np.nan))[1])
    # a post with no comments cannot be called out
    e.loc[pd.to_numeric(e["comment_count"]).fillna(0).eq(0), "callout"] = 0.0
    return e


# spec: (terms, fixed effects)
SPECS = {"within": (["off", "ai50"], "publication"),
         "within_x": (["off", "ai50", "off:ai50"], "publication"),
         "between": (["off", "ai50"], "category"),
         "labels": (["off", "ai50", "after", "off:after", "ai50:after"], "publication")}
CONTROLS = ["log_age", "log_words"]


def ols_cluster(X, y, groups):
    """OLS coefficients and CR1 cluster-robust standard errors."""
    X, y = np.asarray(X, float), np.asarray(y, float)
    xtx_inv = np.linalg.pinv(X.T @ X)
    beta = xtx_inv @ X.T @ y
    resid = y - X @ beta
    meat = np.zeros((X.shape[1], X.shape[1]))
    for g in np.unique(groups):
        s = X[groups == g].T @ resid[groups == g]
        meat += np.outer(s, s)
    n, k, G = len(y), np.linalg.matrix_rank(X), len(np.unique(groups))
    cov = G / (G - 1) * (n - 1) / (n - k) * xtx_inv @ meat @ xtx_inv
    return beta, np.sqrt(np.diag(cov)), G


def fit(e, y, spec):
    terms, fe = SPECS[spec]
    d = e.dropna(subset=[y, "off", "ai50"] + CONTROLS).copy()
    d["after"] = d["after_labels"].astype(float)
    for term in terms:
        if ":" in term:
            u, v = term.split(":")
            d[term] = d[u] * d[v]
    X = pd.concat([d[terms + CONTROLS], pd.get_dummies(d[fe], dtype=float)], axis=1)  # dummies replace the intercept
    beta, se, G = ols_cluster(X, d[y], d["publication"].to_numpy())
    crit = t_dist.ppf(0.975, G - 1)
    rows = []
    for i, term in enumerate(terms):
        rows.append({"outcome": y, "spec": spec, "term": term, "coef": beta[i], "se": se[i],
                     "ci_low": beta[i] - crit * se[i], "ci_high": beta[i] + crit * se[i],
                     "p": 2 * t_dist.sf(abs(beta[i] / se[i]), G - 1), "n": len(d), "n_pubs": G})
    return rows


def estimates(e):
    return pd.DataFrame([r for y in OUTCOMES for spec in SPECS for r in fit(e, y, spec)])


def summary(e):
    """Medians and call-out shares by detection status and AI score."""
    g = e.assign(group=np.select([e["off"] == 1, e["ai50"] == 1], ["off", "on, score >= 50"], "on, score < 50"))
    return g.groupby("group").agg(posts=("post_id", "size"), median_likes=("reaction_count", "median"),
                                  median_comments=("comment_count", "median"),
                                  median_restacks=("restacks", "median"),
                                  posts_with_comments=("comment_count", lambda s: (pd.to_numeric(s) > 0).sum()),
                                  called_out=("callout", "sum")).reset_index()


def load_all():
    df = a.load()
    scores = pd.read_csv(a.API_SCORES, dtype={"id": str})
    eng = pd.read_csv(ENGAGEMENT, dtype={"post_id": str})
    return df, build(df, scores, eng, load_comments(), load_codes())


def callouts():
    df, e = load_all()
    info = e.set_index("post_id")
    rows = []
    for pid, cs in load_comments().items():
        if pid not in info.index:
            continue
        for c in cs:
            if is_callout(c.get("body")):
                rows.append({"comment_id": str(c.get("id")), "post_id": pid, "off": info.loc[pid, "off"],
                             "score": info.loc[pid, "score"], "body": c.get("body")})
    print(f"{len(rows)} matches")
    with pd.option_context("display.max_colwidth", 300, "display.width", 250):
        print(pd.DataFrame(rows).to_string(index=False) if rows else "")


def main():
    df, e = load_all()
    est, summ = estimates(e), summary(e)
    OUT_DIR.mkdir(exist_ok=True)
    est.to_csv(OUT_DIR / "substack_readers_estimates.csv", index=False)
    summ.to_csv(OUT_DIR / "substack_readers_summary.csv", index=False)
    print(f"{len(e)} posts, {e['reaction_count'].notna().sum()} with engagement, "
          f"{int(e['n_comments_saved'].gt(0).sum())} with saved comments")
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(summ.to_string(index=False))
        print(est.round(3).to_string(index=False))


if __name__ == "__main__":
    callouts() if sys.argv[1:] == ["callouts"] else main()
