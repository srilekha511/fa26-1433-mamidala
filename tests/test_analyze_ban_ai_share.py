import numpy as np
import pandas as pd

from analyze_ban_ai_share import ban_level, did


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
