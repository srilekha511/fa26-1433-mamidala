import pandas as pd

import check_substack_pilot as c


def row(pid, status="scannable", statement="no", text="", pcts=("10", "20", "70"), seconds="30",
        checked="2026-11-08", window="sep"):
    return {"post_id": str(pid), "publication": "P", "post_date": "2026-09-01", "window": window, "checked_on": checked, "status": status, "statement": statement,
            "statement_text": text, "ai_pct": pcts[0], "ai_assisted_pct": pcts[1], "human_pct": pcts[2],
            "seconds": seconds}


def test_clean_rows_have_no_problems():
    df = pd.DataFrame([row(1), row(2, status="unavailable", statement="yes", text="I write it", pcts=("", "", "")),
                       row(3, pcts=("0", "0", "101"))])  # rounding in the popup
    assert c.problems(df) == []


def test_problems_are_caught():
    df = pd.DataFrame([
        row(1, status="disabled", pcts=("", "", "")),
        row(2, statement="yes"),
        row(3, pcts=("10", "", "70")),
        row(4, pcts=("10", "10", "10")),
        row(5, status="unavailable"),
        row(6, seconds="abt 30"),
    ])
    found = c.problems(df)
    assert [m.split(":")[0] for m in found] == ["1", "2", "3", "4", "5", "6"]


def test_summarize_counts_only_checked_rows():
    df = pd.DataFrame([row(1, seconds="20"), row(2, status="unavailable", pcts=("", "", ""), seconds="40",
                                                 window="jul21_aug"), row(3, checked="")])
    out = "\n".join(c.summarize(df))
    assert out.startswith("2 of 3 posts checked")
    assert "median 30" in out and f"{c.HAND_TARGET * 30 / 3600:.1f} hours" in out


def test_patterns_in_date_order():
    rows = [dict(row(1, pcts=("80", "0", "20")), publication="A", post_date="2026-08-01"),
            dict(row(2, status="unavailable", pcts=("", "", "")), publication="A", post_date="2026-09-01"),
            dict(row(3), publication="B", post_date="2026-10-01"),
            dict(row(4), publication="B", post_date="2026-09-01")]
    p = c.patterns(pd.DataFrame(rows)).set_index("publication")
    assert p.loc["A", "sequence"] == "S80 U" and p.loc["A", "pattern"] == "switches"
    assert p.loc["B", "sequence"] == "S S" and p.loc["B", "pattern"] == "always scannable"


def test_summarize_with_nothing_checked():
    assert c.summarize(pd.DataFrame([row(1, checked="")])) == ["0 of 1 posts checked"]


def test_statement_and_reason_rules():
    df = pd.DataFrame([
        dict(row(1, text="I write it"), unavailable_reason=""),  # statement no but text filled
        dict(row(2, status="unavailable", pcts=("", "", "")), unavailable_reason="author"),
        dict(row(3), unavailable_reason="none_shown"),
        dict(row(4, status="unavailable", pcts=("", "", ""), seconds=""), unavailable_reason="paid_only"),
        dict(row(5), unavailable_reason=""),
    ])
    found = c.problems(df)
    assert [m.split(":")[0] for m in found] == ["1", "2", "3"]
