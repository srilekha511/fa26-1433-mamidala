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


def test_post_row_keeps_image_posts_without_text():
    p = raw_post(is_self=False, post_hint="image", domain="i.redd.it", selftext=None)
    row = build_reddit_posts.post_row(p, {"AI"}, RULE)
    assert row["post_type"] == "image"
    assert row["text_ok"] is False and row["n_words"] == 0 and row["selftext"] == ""


def test_post_row_marks_long_text_posts_as_usable_for_text_analysis():
    row = build_reddit_posts.post_row(raw_post(is_self=True), {"AI"}, RULE)
    assert row["post_type"] == "text" and row["text_ok"] is True


def test_subreddit_months_labeled_share_of_all_posts():
    import pandas as pd
    df = pd.DataFrame({
        "subreddit": ["x", "x", "x", "x", "y"], "month": ["2023-01"] * 3 + ["2023-02", "2023-01"],
        "period": ["voluntary"] * 4 + ["pre"], "regime": ["late_archive"] * 5,
        "ai_flair": [True, False, False, True, False], "removed": [False, True, False, False, False],
        "post_type": ["image", "image", "text", "image", "link"],
        "score": [10, 2, 6, 4, 1], "num_comments": [3, 1, 2, 0, 5],
    })
    out = build_reddit_posts.subreddit_months(df).set_index(["subreddit", "month"])
    jan = out.loc[("x", "2023-01")]
    assert jan["posts"] == 3 and jan["ai_flair_posts"] == 1
    assert jan["labeled_share"] == pytest.approx(1 / 3)
    assert jan["removed_share"] == pytest.approx(1 / 3)
    assert jan["image_share"] == pytest.approx(2 / 3)
    assert jan["ai_mean_score"] == 10 and jan["other_mean_score"] == 4
    assert out.loc[("x", "2023-02"), "labeled_share"] == 1
    assert out.loc[("y", "2023-01"), "ai_flair_posts"] == 0
