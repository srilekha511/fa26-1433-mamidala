import pandas as pd

import score_substack_off as s


def test_off_ids_are_strings_of_off_posts():
    df = pd.DataFrame({"post_id": [1, 2, 3], "off": [True, False, True]})
    assert s.off_ids(df) == ["1", "3"]


def test_todo_skips_scored_and_empty(tmp_path):
    texts = pd.DataFrame({"id": ["1", "2", "3"], "selftext": ["a b", "", "c d"], "n_words": [2, 0, 2]})
    scores = tmp_path / "scores.csv"
    pd.DataFrame({"id": ["3"], "fraction_ai": [0.1]}).to_csv(scores, index=False)
    assert s.todo(texts, scores)["id"].tolist() == ["1"]
    assert s.todo(texts, tmp_path / "none.csv")["id"].tolist() == ["1", "3"]


def test_calib_ids_switcher_scans_then_random_always_on():
    rows = []
    for i in range(6):  # always on
        rows.append({"post_id": 10 + i, "publication": "On", "status": "scannable", "off": False, "ai_pct": 0.0})
    rows += [{"post_id": 1, "publication": "Sw", "status": "scannable", "off": False, "ai_pct": 5.0},
             {"post_id": 2, "publication": "Sw", "status": "unavailable", "off": True, "ai_pct": float("nan")},
             {"post_id": 3, "publication": "Off", "status": "unavailable", "off": True, "ai_pct": float("nan")}]
    df = pd.DataFrame(rows).assign(eligible=True, category="C", statement="no")
    ids = s.calib_ids(df, n_on=3)
    assert ids[0] == "1" and len(ids) == 4 and set(ids[1:]) <= {str(10 + i) for i in range(6)}
    assert ids == s.calib_ids(df, n_on=3)  # fixed seed
