import numpy as np
import pandas as pd

from analyze_reddit_did import control_share, controls_for, did


def test_did_is_post_mean_minus_pre_mean():
    t = pd.period_range("2024-01", periods=6, freq="M")
    gap = pd.Series([1.0, 2.0, 3.0, 10.0, 12.0, 14.0], index=t)
    assert did(gap, pd.Period("2024-04", "M"), k=3) == 12.0 - 2.0


def test_did_is_nan_when_window_runs_off_the_data():
    t = pd.period_range("2024-01", periods=4, freq="M")
    assert np.isnan(did(pd.Series(1.0, index=t), pd.Period("2024-02", "M"), k=3))


def test_control_share_counts_controls_only_between_label_and_ban():
    t = pd.period_range("2024-01", periods=4, freq="M")
    m = pd.DataFrame({"subreddit": ["c"] * 4 + ["d"] * 4, "t": list(t) * 2,
                      "ai_flair_posts": [1, 1, 1, 1, 3, 3, 3, 3], "posts": [10] * 8})
    rules = pd.DataFrame({"L": [t[1], t[0]], "B": [pd.Period("2099-12", "M"), t[2]]}, index=["c", "d"])
    share = control_share(m, ["c", "d"], rules)
    # Jan: only d; Feb: c and d; Mar-Apr: only c (d banned AI posts from March).
    assert share.tolist() == [0.3, 0.2, 0.1, 0.1]


def test_controls_cover_the_whole_window():
    P = lambda s: pd.Period(s, "M")
    far = P("2099-12")
    rules = pd.DataFrame({
        "group": ["switcher", "voluntary_throughout", "voluntary_throughout", "voluntary_throughout", "switcher"],
        "L": [P("2023-01"), P("2023-01"), P("2024-03"), P("2023-01"), P("2023-01")],
        "E": [P("2024-06"), far, far, far, P("2024-08")],
        "B": [far, far, far, P("2024-07"), far]}, index=["s", "ok", "late_label", "banned", "early_switch"])
    assert controls_for("s", rules, k=6) == ["ok"]
