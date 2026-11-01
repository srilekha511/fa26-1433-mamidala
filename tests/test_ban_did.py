import json

import numpy as np
import pandas as pd
import pytest

from analyze_ban_did import event_study, pooled, trend_break
from build_ban_sample import ban_event, is_ban

JUL = 1690000000  # 2023-07-22
OLD = 1600000000  # 2020-09-13


def test_is_ban():
    assert is_ban("No AI art: AI generated images are not allowed.")
    assert is_ban("Human work only: posts made with ChatGPT will be removed")
    assert not is_ban("AI art must be flaired: use the AI flair")
    assert not is_ban("AI art is not strictly prohibited, but we are stricter with it")
    assert not is_ban("No spam: be kind")


def rules(*items):
    return json.dumps([{"short_name": n, "description": "", "created_utc": t} for n, t in items])


def test_ban_event_dates_a_new_ban_rule():
    e = ban_event(str([{"short_name": "Be kind", "description": ""}]), rules(("Be kind", OLD), ("No AI art", JUL)))
    assert e == {"ban_date": "2023-07-22", "ban_rule": "No AI art: ", "rules_rewritten": False}


def test_ban_event_drops_an_old_rule_edited_into_a_ban():
    e = ban_event("[]", rules(("No AI art", OLD)))
    assert e["drop"].startswith("ban rule created before July 2023")


def test_ban_event_drops_a_subreddit_with_an_ai_rule_in_july_2023():
    assert ban_event(str([{"short_name": "Flair AI art", "description": ""}]), rules(("No AI art", JUL)))["drop"] \
        == "AI rule already in July 2023"


def one_stack(effect, k=3, n_controls=4, seed=0):
    """A balanced stack: controls share a common trend; the treated unit jumps by effect from rel 0."""
    rng = np.random.default_rng(seed)
    rows = []
    trend = rng.normal(size=2 * k)
    for unit in range(n_controls + 1):
        level = rng.normal()
        for i, rel in enumerate(range(-k, k)):
            jump = effect if unit == 0 and rel >= 0 else 0.0
            rows.append({"stack": f"s{seed}", "subreddit": f"s{seed}" if unit == 0 else f"c{seed}_{unit}",
                         "rel": rel, "y": level + trend[i] + jump, "treated": unit == 0})
    return pd.DataFrame(rows)


def test_pooled_recovers_a_common_jump():
    df = pd.concat([one_stack(0.5, seed=s) for s in range(5)], ignore_index=True)
    assert pooled(df, k=3)["did_log"] == pytest.approx(0.5)


def test_event_study_is_flat_before_and_steps_after():
    df = pd.concat([one_stack(0.5, seed=s) for s in range(5)], ignore_index=True)
    table, _ = event_study(df, k=3)
    assert table.set_index("rel")["coef"].round(6).to_dict() == {-3: 0, -2: 0, -1: 0, 0: 0.5, 1: 0.5, 2: 0.5}


def test_trend_break_separates_a_pre_trend_from_a_jump():
    df = pd.concat([one_stack(0.5, seed=s) for s in range(5)], ignore_index=True)
    df["y"] += np.where(df["treated"], 0.1 * df["rel"], 0.0)  # treated already growing before the ban
    tb = trend_break(df)
    assert tb["trend"][0] == pytest.approx(0.1)
    assert tb["jump"][0] == pytest.approx(0.5)
    assert tb["slope_change"][0] == pytest.approx(0.0, abs=1e-9)
