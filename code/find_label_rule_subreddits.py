"""List more image communities with AI labeling rules, from the full AIRules data.

Usage: python3 code/find_label_rule_subreddits.py   (needs data/raw/airules/)
Writes data/derived/airules_label_candidates.csv: Content Generation subreddits whose July 2023 or
November 2024 rules mention labeling AI posts, with each snapshot's rule classified as
  none        no AI wording
  label_soft  asks for an AI flair or tag without must/required/removal wording
  label_must  requires the flair or tag
  ban         bans AI content
  other_ai    mentions AI some other way
and the study group each candidate could fill. The classification is a keyword screen to choose
which subreddits to scan for AI flairs; group membership is still decided by hand from mod posts.
"""

import re

import pandas as pd

from reddit_subreddits import ROOT
from select_controls import AIRULES, DERIVED, mentions_ai

LABEL = re.compile(r"\b(flair|flaired|tag|tagged|label|labell?ed|mark|marked|\[ai\])\b", re.IGNORECASE)
MUST = re.compile(r"\b(must|required?|will be removed|removed|mandatory|ban(ned)?)\b", re.IGNORECASE)
BAN = re.compile(r"(no|not allowed|banned|prohibited|forbidden)[^.]{0,40}\b(ai|midjourney|generated)\b"
                 r"|\b(ai|generated)[^.]{0,40}(not allowed|banned|prohibited|forbidden)", re.IGNORECASE)
# (July 2023 rule, November 2024 rule) -> group the subreddit could fill.
ROLE = {("label_soft", "label_soft"): "voluntary", ("none", "label_soft"): "voluntary",
        ("none", "label_must"): "switcher", ("label_soft", "label_must"): "switcher",
        ("label_soft", "ban"): "ban", ("label_must", "ban"): "ban",
        ("label_must", "label_must"): "mandatory"}


def classify(rules):
    lines = [s for s in re.split(r"(?<=[.!?])\s+|\n+| - ", rules if isinstance(rules, str) else "")
             if mentions_ai(s)]
    if not lines:
        return "none"
    labeling = [s for s in lines if LABEL.search(s)]
    if labeling:
        return "label_must" if any(MUST.search(s) for s in labeling) else "label_soft"
    return "ban" if any(BAN.search(s) for s in lines) else "other_ai"


def main():
    lon = pd.read_csv(AIRULES / "longitudinal_subreddit_set.csv",
                      usecols=["id", "name_nov24", "subscribers_jul23", "cleaned_rules_jul23", "cleaned_rules_nov24"])
    rules = pd.read_csv(AIRULES / "rules_subreddit_set.csv", usecols=["id", "topic_label", "is_content_generation_ca_label"])
    d = lon.merge(rules, on="id")
    d = d[d["is_content_generation_ca_label"] == True].copy()
    d["rule_jul23"] = d["cleaned_rules_jul23"].map(classify)
    d["rule_nov24"] = d["cleaned_rules_nov24"].map(classify)
    d["candidate_for"] = [ROLE.get(k, "") for k in zip(d["rule_jul23"], d["rule_nov24"])]
    d["subreddit"] = d["name_nov24"].str.removeprefix("r/")
    study = set(pd.read_csv(ROOT / "data" / "hand_coded" / "reddit_rule_dates.csv")["subreddit"].str.lower())
    d = d[(d["candidate_for"] != "") & ~d["subreddit"].str.lower().isin(study)]
    d = d.sort_values(["candidate_for", "subscribers_jul23"], ascending=[True, False])
    cols = ["subreddit", "candidate_for", "rule_jul23", "rule_nov24", "subscribers_jul23", "topic_label"]
    d[cols].to_csv(DERIVED / "airules_label_candidates.csv", index=False)
    print(d["candidate_for"].value_counts().to_string())


if __name__ == "__main__":
    main()
