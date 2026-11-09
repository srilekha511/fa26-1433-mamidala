import json

import pandas as pd
import pytest

import build_substack_frame as bf


@pytest.fixture
def paths(tmp_path, monkeypatch):
    monkeypatch.setattr(bf, "RAW", tmp_path / "raw")
    monkeypatch.setattr(bf, "ARCHIVE", tmp_path / "raw" / "archive")
    monkeypatch.setattr(bf, "FRAME", tmp_path / "frame.csv")
    return tmp_path


def post(date, audience="everyone", words=500):
    return {"id": hash(date) % 10**6, "post_date": f"{date}T12:00:00.000Z", "audience": audience,
            "type": "newsletter", "wordcount": words}


def test_list_category_pages_until_no_more():
    pages = {0: {"publications": [{"id": 1}], "more": True}, 1: {"publications": [{"id": 2}], "more": False}}
    asked = []

    def get(url):
        asked.append(url)
        return pages[int(url.rsplit("=", 1)[1])]
    assert [p["id"] for p in bf.list_category(7, get=get)] == [1, 2]
    assert len(asked) == 2


def test_snapshot_is_written_once(paths):
    def get(url):
        if url.endswith("/categories"):
            return [{"id": 1, "name": "Tech"}]
        return {"publications": [{"id": 5, "name": "A", "subdomain": "a", "language": "en"}], "more": False}
    bf.snapshot(get=get, today="2026-11-08")
    assert pd.read_csv(paths / "raw" / "listings_2026-11-08.csv")["pub_id"].tolist() == [5]
    with pytest.raises(SystemExit):
        bf.snapshot(get=get, today="2026-11-08")


def test_frame_order_english_first_category_fixed_order():
    listings = pd.DataFrame([
        {"category": "Tech", "position": 0, "pub_id": "1", "language": "en"},
        {"category": "Culture", "position": 0, "pub_id": "1", "language": "en"},  # listed twice
        {"category": "Tech", "position": 1, "pub_id": "2", "language": "es"},
        {"category": "Tech", "position": 2, "pub_id": "3", "language": None},
        {"category": "Tech", "position": 3, "pub_id": "4", "language": "en-US"},
    ])
    order = bf.frame_order(listings)
    assert set(order["pub_id"]) == {"1", "3", "4"}
    assert (order["category"] == "Tech").all()
    shuffled = pd.concat([listings.iloc[:2], listings.iloc[2:].iloc[::-1]])  # same categories first, Tech reordered
    assert order["pub_id"].tolist() == bf.frame_order(shuffled)["pub_id"].tolist()


def test_activity_counts_eligible_posts_around_launch():
    posts = [post("2025-12-30"), post("2026-03-01"), post("2026-07-20"), post("2026-05-01", audience="only_paid"),
             post("2026-06-01", words=50), post("2026-07-21"), post("2026-10-01")]
    assert bf.activity(posts) == {"n_posts": 7, "n_pre": 2, "n_post": 2, "first_post": "2025-12-30"}


def test_pull_archives_fills_quota_saves_and_resumes(paths, monkeypatch):
    monkeypatch.setattr(bf, "PER_CATEGORY", 2)
    order = pd.DataFrame([{"category": "Tech", "draw_order": i, "pub_id": str(i), "name": f"p{i}",
                           "subdomain": f"p{i}", "custom_domain": None} for i in range(5)])
    active = [post("2026-02-01"), post("2026-03-01"), post("2026-04-01"), post("2026-09-01")]
    archives = {"p0": active, "p1": [post("2026-09-01")], "p2": active, "p3": active, "p4": active}
    asked = []

    def fetch(url, since):
        asked.append(url)
        return iter(archives[url.split("//")[1].split(".")[0]])
    bf.pull_archives(order.iloc[:2], bf.done_frame(), fetch_archive=fetch, today="2026-11-08")
    kept = bf.pull_archives(order, bf.done_frame(), fetch_archive=fetch, today="2026-11-08")
    assert kept == {"Tech": 2}
    assert [u.split("//")[1].split(".")[0] for u in asked] == ["p0", "p1", "p2"]  # resumed; p3, p4 not needed
    frame = pd.read_csv(paths / "frame.csv", dtype={"pub_id": str})
    assert frame["kept"].tolist() == [1, 0, 1]
    lines = (paths / "raw" / "archive" / "0.jsonl").read_text().splitlines()
    assert [json.loads(x)["post_date"][:10] for x in lines] == ["2026-02-01", "2026-03-01", "2026-04-01",
                                                               "2026-09-01"]
