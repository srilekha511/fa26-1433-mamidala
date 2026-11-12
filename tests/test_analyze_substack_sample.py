import numpy as np
import pandas as pd
import pytest

import analyze_substack_sample as a


def write(tmp_path, rows):
    cols = ["post_id", "category", "publication", "window", "post_date", "status", "unavailable_reason",
            "statement", "statement_text", "ai_pct", "ai_assisted_pct", "human_pct"]
    path = tmp_path / "s.csv"
    pd.DataFrame(rows, columns=cols).to_csv(path, index=False)
    return path


def post(pid, pub, date, status="scannable", reason="", ai="0", statement="no", cat="Fiction"):
    pcts = (ai, "0", str(100 - int(ai))) if status == "scannable" else ("", "", "")
    return [pid, cat, pub, "sep", date, status, reason, statement, "", *pcts]


@pytest.fixture
def df(tmp_path):
    rows = [
        post(1, "On", "2026-09-01", ai="0"), post(2, "On", "2026-10-20", ai="80"),
        post(3, "Off", "2026-09-01", "unavailable", "none_shown"),
        post(4, "Off", "2026-10-20", " Unavailable", "none_shown", statement="yes"),
        post(5, "Sw", "2026-09-01", ai="10"), post(6, "Sw", "2026-10-20", "unavailable", "none_shown"),
        post(7, "Sw", "2026-10-21", "unavailable", "paid_only"),  # dropped
    ]
    return a.load(write(tmp_path, rows))


def test_load_flags(df):
    assert df["off"].tolist() == [False, False, True, True, False, True, False]
    assert df["eligible"].sum() == 6
    assert df["after_labels"].tolist() == [False, True, False, True, False, True, True]


def test_shares_drop_stated_reasons(df):
    s = a.shares(df, "category").iloc[0]
    assert (s["n_off"], s["n_posts"], s["n_pubs"]) == (3, 6, 3)
    assert s["off_share"] == 0.5


def test_publications(df):
    p = a.publications(df).set_index("publication")
    assert p.loc["On", "pattern"] == "always_on" and p.loc["On", "ai_flagged"] == True
    assert p.loc["Off", "pattern"] == "always_off" and np.isnan(p.loc["Off", "ai_flagged"])
    assert p.loc["Off", "statement"] == True
    assert p.loc["Sw", "pattern"] == "switches" and p.loc["Sw", "n_posts"] == 2  # paid_only post dropped
    assert p.loc["Sw", "ai_flagged"] == False


def test_labels_change_is_within_publication(df):
    e = df[df["eligible"]]
    # On 0->0, Off 1->1, Sw 0->1: mean change 1/3
    assert a.labels_change(e) == pytest.approx(1 / 3)


def test_flag_test(df):
    table, p = a.flag_test(a.publications(df))
    assert table == [[0, 1], [1, 0]] and 0 <= p <= 1


def test_estimates_and_bootstrap(df):
    est = a.estimates(df, a.publications(df), boot=50).set_index("estimate")
    assert est.loc["off_share", "value"] == 0.5
    assert est.loc["off_share", "ci_low"] <= 0.5 <= est.loc["off_share", "ci_high"]
    assert est.loc["labels_change", "n"] == 3
    assert "switchers 0/1, always on 1/1" in est.loc["ai_flagged_switchers_minus_always_on", "note"]


def test_mean_ai_test():
    pubs = pd.DataFrame({"pattern": ["switches"] * 2 + ["always_on"] * 3 + ["always_off"],
                         "mean_ai": [50.0, 70.0, 0.0, 10.0, 20.0, np.nan]})
    diff, p, na, nb = a.mean_ai_test(pubs, perms=200)
    assert diff == pytest.approx(50) and (na, nb) == (2, 3) and 0 < p <= 1


def test_uncoded_rows_are_ignored(tmp_path):
    rows = [post(1, "On", "2026-09-01"), [2, "Fiction", "On", "sep", "2026-09-02", "", "", "", "", "", "", ""]]
    d = a.load(write(tmp_path, rows))
    assert d["eligible"].tolist() == [True, False]
