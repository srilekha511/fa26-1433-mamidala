import numpy as np
import pandas as pd

from analyze_reddit_did import did


def test_did_is_post_mean_minus_pre_mean():
    t = pd.period_range("2024-01", periods=6, freq="M")
    gap = pd.Series([1.0, 2.0, 3.0, 10.0, 12.0, 14.0], index=t)
    assert did(gap, pd.Period("2024-04", "M"), k=3) == 12.0 - 2.0


def test_did_is_nan_when_window_runs_off_the_data():
    t = pd.period_range("2024-01", periods=4, freq="M")
    assert np.isnan(did(pd.Series(1.0, index=t), pd.Period("2024-02", "M"), k=3))
