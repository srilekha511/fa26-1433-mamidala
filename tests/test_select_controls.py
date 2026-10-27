import pandas as pd
import pytest

from select_controls import match, mentions_ai, pre_window, sample_features, volume_features


def test_pre_window_is_the_months_before_the_mandate():
    assert pre_window("2024-01-05", 3) == ["2023-10", "2023-11", "2023-12"]


def test_volume_features():
    f = volume_features({"2023-01": 0, "2023-02": 9}, ["2023-01", "2023-02", "2023-03"])
    assert f["mean_log_posts"] == pytest.approx((0 + 2.302585 + 0) / 3, abs=1e-5)
    assert f["trend_log_posts"] == pytest.approx(0, abs=1e-9)


def test_mentions_ai():
    assert mentions_ai("No AI art allowed")
    assert mentions_ai("Midjourney images must be flaired")
    assert not mentions_ai("Be kind. No spam.")
    assert not mentions_ai(float("nan"))


def test_sample_features():
    posts = [{"is_self": True, "over_18": True}, {"post_hint": "image", "link_flair_text": "AI Art"}]
    assert sample_features(posts) == {"image_share": 0.5, "nsfw_share": 0.5, "ai_flair": True}


def test_match_takes_nearest_without_reuse():
    treated = pd.DataFrame({"x": [0.0, 10.0]}, index=["a", "b"])
    cands = pd.DataFrame({"switcher": ["a", "a", "a", "b", "b"], "subreddit": ["p", "q", "r", "s", "t"],
                          "x": [0.1, 5.0, 3.0, 9.0, 1.0]})
    got = match(cands, treated, ["x"], k=2)
    assert set(got[got.switcher == "a"].control) == {"p", "r"}
    assert set(got[got.switcher == "b"].control) == {"s", "t"}
