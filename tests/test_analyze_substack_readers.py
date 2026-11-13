import json

import numpy as np
import pandas as pd
import pytest

import analyze_substack_readers as r


@pytest.mark.parametrize("text,hit", [
    ("Did you use ChatGPT to write this?", True),
    ("This reads like AI slop.", True),
    ("Obviously AI", True),
    ("Great piece on AI policy, thanks!", False),
    ("I use AI tools at work every day and this matches my experience.", False),
])
def test_is_callout(text, hit):
    assert r.is_callout(text) == hit


def test_flatten_and_callout_flags(tmp_path):
    tree = {"comments": [{"id": 1, "body": "Lovely", "children": [{"id": 2, "body": "Did you use ChatGPT for this?",
                                                                    "children": []}]},
                         {"id": 3, "body": "Thanks", "children": []}]}
    (tmp_path / "10.json").write_text(json.dumps(tree))
    (tmp_path / "11.json").write_text(json.dumps({"comments": [{"id": 4, "body": "Nice"}]}))
    comments = r.load_comments(tmp_path)
    assert len(comments["10"]) == 3
    assert r.callout_flags(comments, {}) == {"10": (3, 1.0), "11": (1, 0.0)}
    assert r.callout_flags(comments, {"2": 0})["10"] == (3, 0.0)  # coded not a call-out


def make_sample():
    rng = np.random.default_rng(0)
    rows, eng = [], []
    pid = 0
    for pub, pattern in [("A", "on"), ("B", "on"), ("C", "switch"), ("D", "switch"), ("E", "off")]:
        for k in range(6):
            pid += 1
            off = pattern == "off" or (pattern == "switch" and k % 2 == 0)
            ai = float(rng.integers(0, 100))
            rows.append({"post_id": str(pid), "publication": pub, "category": "C1", "post_date": "2026-09-01",
                         "wordcount": "1000", "eligible": True, "after_labels": k >= 4, "off": off, "status": "unavailable" if off else "scannable",
                         "ai_pct": np.nan if off else ai, "statement": "no"})
            eng.append({"post_id": str(pid), "reaction_count": int(rng.integers(0, 50)) + (0 if off else 20),
                        "comment_count": k % 3, "restacks": 1, "fetched_at": "2026-11-13T00:00:00"})
    scores = pd.DataFrame({"id": [r["post_id"] for r in rows if r["off"]], "fraction_ai": 0.9})
    return pd.DataFrame(rows), scores, pd.DataFrame(eng)


def test_build_scores_and_flags():
    df, scores, eng = make_sample()
    e = r.build(df, scores, eng, comments={"2": [{"id": 9, "body": "is this AI?"}]})
    assert (e.loc[e["off"] == 1, "score"] == 90).all()
    assert e.loc[e["post_id"] == "2", "callout"].item() == 1
    assert e.loc[e["comment_count"] == 0, "callout"].eq(0).all()
    assert e["log_age"].iloc[0] == pytest.approx(np.log(73))
    assert (e["restacks"] == 1).all() and e["log_restacks"].iloc[0] == pytest.approx(np.log(2))  # raw kept


def test_estimates_run_and_recover_off_penalty():
    df, scores, eng = make_sample()
    est = r.estimates(r.build(df, scores, eng))
    assert set(est["spec"]) == set(r.SPECS) and set(est["outcome"]) == set(r.OUTCOMES)
    off = est[(est["outcome"] == "log_likes") & (est["spec"] == "within") & (est["term"] == "off")]
    assert off["coef"].item() < 0  # off posts were given 20 fewer likes


def test_ols_cluster_matches_plain_ols_coefficients():
    rng = np.random.default_rng(1)
    X = np.column_stack([np.ones(200), rng.normal(size=200)])
    y = 2 + 3 * X[:, 1] + rng.normal(size=200)
    beta, se, G = r.ols_cluster(X, y, np.repeat(np.arange(20), 10))
    assert beta == pytest.approx(np.linalg.lstsq(X, y, rcond=None)[0])
    assert G == 20 and (se > 0).all() and se[1] < 0.2
