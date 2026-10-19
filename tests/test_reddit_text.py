import pytest

import reddit_text


@pytest.mark.parametrize("text", ["AI", "Made by AI", "AI-Generated", ":robot: AI Assisted",
                                  "ChatGPT", "chat gpt", "GPT-4", "A.I. content", "LLM output",
                                  "written with a language model", "ai"])
def test_is_ai_text_matches(text):
    assert reddit_text.is_ai_text(text)


@pytest.mark.parametrize("text", [None, "", "Writing Prompt", "Mail", "Said", "Thai food",
                                  "Domain", "Fairy tale", "Poem", "Critique"])
def test_is_ai_text_rejects(text):
    assert not reddit_text.is_ai_text(text)


def test_tally_flairs_counts_and_dates():
    samples = [("2022-03", "AI"), ("2022-01", "Story"), ("2023-05", "AI"), ("2022-02", None), ("2022-02", "")]
    got = reddit_text.tally_flairs(samples)
    assert got == {"AI": {"n": 2, "first_month": "2022-03", "last_month": "2023-05"},
                   "Story": {"n": 1, "first_month": "2022-01", "last_month": "2022-01"}}


from datetime import datetime, timezone


def ts(day):
    return int(datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp())


def post(**kw):
    base = {"is_self": True, "selftext": "word " * 1000, "author": "someone", "removed_by_category": None}
    return {**base, **kw}


def test_word_count():
    assert reddit_text.word_count("one two  three\nfour") == 4
    assert reddit_text.word_count("") == 0


def test_text_status():
    assert reddit_text.text_status(post()) == "ok"
    assert reddit_text.text_status(post(is_self=False)) == "not_text_post"
    assert reddit_text.text_status(post(selftext="[removed]")) == "no_text"
    assert reddit_text.text_status(post(selftext="[deleted]")) == "no_text"
    assert reddit_text.text_status(post(selftext="")) == "no_text"
    assert reddit_text.text_status(post(selftext="too short")) == "too_short"
    assert reddit_text.text_status(post(author="AutoModerator")) == "automod"


def test_removed_post_with_surviving_text_is_kept():
    assert reddit_text.keep_post(post(removed_by_category="moderator"))


def test_period():
    label, mand = "2023-03-01", "2024-01-15"
    assert reddit_text.period(ts("2023-02-28T23:59:59"), label, mand) == "pre"
    assert reddit_text.period(ts("2023-03-01T00:00:00"), label, mand) == "voluntary"
    assert reddit_text.period(ts("2024-01-14T23:59:59"), label, mand) == "voluntary"
    assert reddit_text.period(ts("2024-01-15T00:00:00"), label, mand) == "mandatory"


def test_period_never_mandatory():
    assert reddit_text.period(ts("2025-06-01T00:00:00"), "2023-03-01", "") == "voluntary"


def test_retrieval_regime_splits_live_ingest_from_late_archive():
    # From mid-2023 Arctic Shift captured posts within seconds; earlier posts were archived weeks late.
    assert reddit_text.retrieval_regime({"created_utc": 1000, "retrieved_on": 1038}) == "live_ingest"
    assert reddit_text.retrieval_regime({"created_utc": 1000, "retrieved_on": 1000 + 30 * 86400}) == "late_archive"
    assert reddit_text.retrieval_regime({"created_utc": 1000, "retrieved_on": None}) == "unknown"


def test_removal_type_counts_meta_removals():
    assert reddit_text.removal_type(post(removed_by_category="moderator")) == "moderator"
    assert reddit_text.removal_type(post(_meta={"removal_type": "deleted"})) == "deleted"
    assert reddit_text.removal_type(post()) is None


def test_period_without_label_date_is_pre():
    assert reddit_text.period(ts("2025-06-01T00:00:00"), "", "") == "pre"


@pytest.mark.parametrize("fields, expected", [
    ({"is_self": True}, "text"),
    ({"is_gallery": True}, "gallery"),
    ({"is_video": True, "domain": "v.redd.it"}, "video"),
    ({"post_hint": "rich:video", "domain": "youtu.be"}, "video"),
    ({"domain": "youtube.com"}, "video"),
    ({"post_hint": "image", "domain": "i.redd.it"}, "image"),
    ({"domain": "i.imgur.com"}, "image"),
    ({"domain": "example.com", "url": "https://example.com/art.PNG"}, "image"),
    ({"domain": "example.com", "url": "https://example.com/story"}, "link"),
    ({}, "link"),
])
def test_post_type(fields, expected):
    base = {"is_self": False, "is_video": False, "is_gallery": None, "post_hint": None,
            "domain": "", "url": ""}
    assert reddit_text.post_type({**base, **fields}) == expected
