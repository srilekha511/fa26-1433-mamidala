import pandas as pd

from score_pangram_api import idempotency_key, row, select_posts, wilson

RESULT = {"stage": "STAGE_SUCCESS", "prediction_short": "AI", "fraction_ai": 0.9, "fraction_ai_assisted": 0.1,
          "fraction_human": 0.0, "num_ai_segments": 2, "num_human_segments": 0, "version": "4.1"}


def test_row_reads_a_successful_item():
    assert row({"id": "abc", "result": RESULT}) == {"id": "abc", "prediction_short": "AI", "fraction_ai": 0.9,
                                                    "fraction_ai_assisted": 0.1, "fraction_human": 0.0,
                                                    "num_ai_segments": 2, "num_human_segments": 0, "version": "4.1"}


def test_row_skips_failed_and_unfinished_items():
    assert row({"id": "abc", "result": None, "stage": "STAGE_FAILED"}) is None
    assert row({"id": "abc", "result": {**RESULT, "stage": "STAGE_FAILED"}}) is None


def test_idempotency_key_is_fixed_by_the_body():
    a = {"items": [{"id": "1", "text": "x"}], "model": "pangram-4.1"}
    assert idempotency_key(a) == idempotency_key({"model": "pangram-4.1", "items": [{"id": "1", "text": "x"}]})
    assert idempotency_key(a) != idempotency_key({**a, "items": [{"id": "2", "text": "x"}]})


def posts_frame():
    rows = []
    for i in range(100):
        rows.append({"id": f"t{i}", "stack": "a", "subreddit": "a", "role": "treated", "window": "pre", "weight": 2.0})
    for i in range(30):
        rows.append({"id": f"b{i}", "stack": "a", "subreddit": "a", "role": "treated", "window": "baseline", "weight": 1.0})
    for i in range(5):
        rows.append({"id": f"c{i}", "stack": "a", "subreddit": "c", "role": "control", "window": "pre", "weight": 3.0})
    rows.append({"id": "n0", "stack": "alone", "subreddit": "alone", "role": "treated", "window": "pre", "weight": 1.0})
    return pd.DataFrame(rows)


def test_select_posts_caps_each_window_and_drops_bans_without_a_comparison():
    out = select_posts(posts_frame())
    counts = out.groupby(["subreddit", "window"]).size().to_dict()
    assert counts == {("a", "baseline"): 15, ("a", "pre"): 60, ("c", "pre"): 5}
    assert "alone" not in set(out["stack"])


def test_select_posts_keeps_each_windows_total_weight():
    out = select_posts(posts_frame())
    totals = out.groupby(["subreddit", "window"])["cap_weight"].sum().round(6).to_dict()
    assert totals == {("a", "baseline"): 30.0, ("a", "pre"): 200.0, ("c", "pre"): 15.0}


def test_select_posts_does_not_depend_on_row_order():
    frame = posts_frame()
    a = select_posts(frame)
    b = select_posts(frame.sample(frac=1, random_state=1))
    assert list(a["id"]) == list(b["id"])


def test_wilson_interval_contains_the_share():
    lo, hi = wilson(1, 50)
    assert 0 < lo < 0.02 < hi < 0.11
    assert wilson(0, 100)[0] == 0
