import csv

import pytest

import substack_deepen as sd
import substack_pilot as sp


def post(i, date, audience="everyone", words=500):
    return {"id": i, "post_date": f"{date}T12:00:00.000Z", "audience": audience, "type": "newsletter",
            "wordcount": words, "title": f"t{i}"}


def row(pid, pub="A", url="https://a.substack.com", status="scannable"):
    return {"post_id": str(pid), "reader_url": "", "category": "Fiction", "publication": pub, "pub_url": url,
            "window": "sep", "post_date": "2026-09-01", "wordcount": "500", "title": "t", "checked_on": "2026-11-11",
            "status": status, "unavailable_reason": "", "statement": "no", "notes": "", "draw": "1"}


def test_next_posts_skips_taken_and_ineligible():
    posts = [post(i, "2026-09-0%d" % (i % 9 + 1)) for i in range(1, 8)] + [post(50, "2026-10-02", "only_paid")]
    ranked = sorted((p for p in posts if p["audience"] == "everyone"), key=lambda p: sp.rank(p["id"]))
    got = sd.next_posts(posts, taken={str(ranked[0]["id"])})
    assert [p["id"] for p in got] == [ranked[1]["id"]]  # sep only; the paid October post is skipped


def test_next_posts_one_per_window():
    posts = [post(1, "2026-08-01"), post(2, "2026-08-02"), post(3, "2026-09-01"), post(4, "2026-10-01")]
    got = sd.next_posts(posts, taken={"1"})
    assert [sp.window_of(p["post_date"]) for p in got] == ["jul21_aug", "sep", "oct"]
    assert 1 not in [p["id"] for p in got]


def test_new_rows_blank_hand_columns_and_failures_reported():
    existing = [row(1), row(2), row(9, pub="B", url="https://b.substack.com")]
    archives = {"https://a.substack.com": [post(1, "2026-09-02"), post(3, "2026-09-03")]}

    def archive(url, since=None):
        if url not in archives:
            raise RuntimeError("HTTP 400")
        return iter(archives[url])

    rows, failed = sd.new_rows(existing, archive=archive)
    assert [r["post_id"] for r in rows] == ["3"]
    r = rows[0]
    assert r["draw"] == "2" and r["status"] == "" and r["checked_on"] == "" and r["unavailable_reason"] == ""
    assert r["publication"] == "A" and r["window"] == "sep" and r["reader_url"].endswith("/3")
    assert set(r) == set(existing[0])
    assert len(failed) == 1 and failed[0].startswith("B ")


def test_main_refuses_to_overwrite(tmp_path):
    out = tmp_path / "out.csv"
    out.write_text("x")
    with pytest.raises(SystemExit):
        sd.main(tmp_path / "in.csv", out)
