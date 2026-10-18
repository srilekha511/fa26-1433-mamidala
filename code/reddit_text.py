"""Text rules for the Reddit sample: AI keywords, flair tallies, post filters and labeling periods."""

import re
from datetime import date, datetime, timezone

# Used only to *find* candidate flairs, rule lines and moderator posts. The final AI-flair
# definition is the hand-approved list in data/hand_coded/ai_flairs.csv.
AI_PATTERN = re.compile(
    r"(?<![a-z])(ai|a\.i\.|artificial intelligence|chat ?gpt|gpt-?\d|llms?|language models?"
    r"|machine[- ]generated)(?![a-z])",
    re.IGNORECASE,
)


def is_ai_text(text):
    return bool(text) and AI_PATTERN.search(text) is not None


def tally_flairs(samples):
    """Map each flair to how often it appears and the first and last month seen."""
    out = {}
    for month, flair in samples:
        if not flair:
            continue
        t = out.setdefault(flair, {"n": 0, "first_month": month, "last_month": month})
        t["n"] += 1
        t["first_month"] = min(t["first_month"], month)
        t["last_month"] = max(t["last_month"], month)
    return out


# Pangram's minimum for a prediction (https://www.pangram.com/blog/why-does-pangram-have-a-minimum-word-count).
# Independent tests find it unreliable below ~200-250 words; restrict on n_words for robustness.
MIN_WORDS = 50
NO_TEXT = {"", "[removed]", "[deleted]"}


def word_count(text):
    return len(text.split())


def text_status(post):
    """Why a post is or is not usable for text analysis.

    Posts removed by moderators are kept when their text survives: moderators remove unlabeled
    AI posts, so dropping them would overstate how often AI posts are labeled.
    """
    if not post.get("is_self"):
        return "not_text_post"
    if post.get("author") == "AutoModerator":
        return "automod"
    text = (post.get("selftext") or "").strip()
    if text in NO_TEXT:
        return "no_text"
    if word_count(text) < MIN_WORDS:
        return "too_short"
    return "ok"


def keep_post(post):
    return text_status(post) == "ok"


def _day_start(day):
    return int(datetime.combine(date.fromisoformat(day), datetime.min.time(), timezone.utc).timestamp())


def period(created_utc, label_start, mandatory_start):
    """Labeling period of a post; a rule takes effect at 00:00 UTC on its start date."""
    if not label_start or created_utc < _day_start(label_start):
        return "pre"
    if mandatory_start and created_utc >= _day_start(mandatory_start):
        return "mandatory"
    return "voluntary"


def retrieval_regime(post):
    """How Arctic Shift captured the post.

    From mid-2023 posts were captured within seconds of posting ("live_ingest"), usually with a
    second capture about a day later; earlier posts were archived weeks or months late
    ("late_archive"), after most removals and flair edits had already happened.
    """
    if post.get("retrieved_on") is None:
        return "unknown"
    return "live_ingest" if post["retrieved_on"] - int(post["created_utc"]) < 3600 else "late_archive"


def removal_type(post):
    """Who removed the post, if anyone, from either Reddit's field or Arctic Shift's _meta."""
    return post.get("removed_by_category") or (post.get("_meta") or {}).get("removal_type")
