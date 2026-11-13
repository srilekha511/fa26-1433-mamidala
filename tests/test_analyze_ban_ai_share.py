import numpy as np
import pandas as pd

from analyze_ban_ai_share import ban_level, catch_up, did, live_capture, removals


def panel(effect, n=400, stacks=30, seed=0):
    """Stacks of one banned and one comparison subreddit; AI rises 3 points everywhere and `effect` more at bans."""
    rng = np.random.default_rng(seed)
    parts = []
    for s in range(stacks):
        for sub, role in [(f"s{s}", "treated"), (f"s{s}c", "control")]:
            level = rng.uniform(0, 0.1)
            for window in ["pre", "post"]:
                p = level + (0.03 if window == "post" else 0) + (effect if role == "treated" and window == "post" else 0)
                parts.append(pd.DataFrame({"stack": f"s{s}", "subreddit": sub, "role": role, "window": window,
                                           "ai": (rng.random(n) < p).astype(float), "cap_weight": rng.uniform(1, 9, n)}))
    df = pd.concat(parts, ignore_index=True)
    df["treated"] = df["role"] == "treated"
    return df


def test_did_recovers_a_known_effect_despite_different_levels():
    r = did(panel(-0.02))
    assert abs(r["did_pp"] + 2) < 2 * r["se_pp"]
    assert r["n_bans"] == 30 and r["n_subreddits"] == 60


def test_did_needs_both_windows_in_both_groups():
    df = panel(0.0)
    assert did(df[~(df["treated"] & (df["window"] == "post"))]) is None


def test_ban_level_drops_bans_with_thin_cells():
    df = panel(0.0, n=20)
    thin = df[~((df["stack"] == "s0") & (df["role"] == "control") & (df.groupby(
        ["stack", "role", "window"]).cumcount() >= 3))]
    assert ban_level(thin, min_cell=10)["n_bans"] == 29
    assert ban_level(df, min_cell=10)["n_bans"] == 30


def test_catch_up_removes_a_convergence_that_looks_like_a_ban_effect():
    # No ban effect, but low-AI subreddits rise more after the ban date, and banned subreddits start lower.
    rng = np.random.default_rng(2)
    parts = []
    for s in range(60):
        for sub, role, level in [(f"s{s}", "treated", rng.uniform(0, 0.05)), (f"s{s}c", "control", rng.uniform(0.02, 0.08))]:
            for window in ["pre", "post"]:
                p = level + (0.6 * (0.1 - level) if window == "post" else 0)
                n = 1500
                parts.append(pd.DataFrame({"stack": f"s{s}", "subreddit": sub, "role": role, "window": window,
                                           "ai": (rng.random(n) < p).astype(float), "rank": rng.integers(0, 10**6, n)}))
    df = pd.concat(parts, ignore_index=True)
    df["treated"] = df["role"] == "treated"
    naive, adjusted = did(df), catch_up(df)
    assert naive["did_pp"] > 1 and naive["p"] < 0.01
    assert abs(adjusted["did_pp"]) < 0.5 * naive["did_pp"]
    assert -0.8 < adjusted["pre_share_x_post_coef"] < -0.4  # true slope -0.6


def test_live_capture_keeps_stacks_whose_pre_window_starts_late_enough():
    df = pd.DataFrame({"stack": ["a", "a", "b", "b"], "window": ["pre", "post", "pre", "post"],
                       "day": ["2023-03-05", "2023-12-01", "2023-08-02", "2024-03-01"]})
    assert set(live_capture(df)["stack"]) == {"b"}


def test_removals_rates_and_change():
    df = panel(0.0, n=200, stacks=20)
    rng = np.random.default_rng(3)
    df["removed_any"] = (rng.random(len(df)) < np.where(df["treated"] & (df["window"] == "post"), 0.2, 0.05)).astype(float)
    rates, tests = removals(df)
    assert set(rates["ai"]) <= {"flagged AI", "not flagged"}
    change = tests.set_index("spec").loc["change at a ban, all posts", "did_pp"]
    assert 12 < change < 18
