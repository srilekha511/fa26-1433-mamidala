import pytest

import build_reddit_posts
import reddit_subreddits

RULE = {"label_start": "2023-03-01", "mandatory_start": ""}


def raw_post(**kw):
    base = {"id": "p1", "subreddit": "x", "created_utc": 1700000000, "retrieved_on": 1700000030,
            "author": "a", "title": "t", "selftext": "word " * 100, "link_flair_text": "AI ",
            "score": 1, "num_comments": 0, "removed_by_category": None,
            "_meta": {"retrieved_2nd_on": 1700130000, "removal_type": "moderator"}}
    return {**base, **kw}


def test_post_row_records_second_retrieval_regime_and_meta_removal():
    row = build_reddit_posts.post_row(raw_post(), {"AI"}, RULE)
    assert row["ai_flair"] is True
    assert row["retrieved_2nd_on"] == 1700130000
    assert row["flair_lag_hours"] == pytest.approx(130000 / 3600)
    assert row["regime"] == "live_ingest"
    assert row["removed"] is True and row["removal_type"] == "moderator"


def test_post_row_without_second_retrieval_uses_first():
    row = build_reddit_posts.post_row(raw_post(_meta={"note": "no_2nd_retrieval"}), {"AI"}, RULE)
    assert row["retrieved_2nd_on"] is None
    assert row["flair_lag_hours"] == pytest.approx(30 / 3600)
    assert row["removed"] is False


def test_approved_flairs_strips_hand_typed_spaces(tmp_path):
    f = tmp_path / "ai_flairs.csv"
    f.write_text("subreddit,flair_text,notes\nx, AI ,typo\n")
    assert reddit_subreddits.approved_flairs(f) == {"x": {"AI"}}
