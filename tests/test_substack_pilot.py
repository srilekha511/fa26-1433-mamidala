import substack_pilot as sp


def post(i, date, audience="everyone", type_="newsletter", words=500):
    return {"id": i, "post_date": f"{date}T12:00:00.000Z", "audience": audience, "type": type_,
            "wordcount": words, "title": f"t{i}", "canonical_url": f"https://a/p/{i}"}


def test_window_of():
    assert sp.window_of("2026-07-20T23:59:59Z") is None  # before launch
    assert sp.window_of("2026-07-21T00:00:00Z") == "jul21_aug"
    assert sp.window_of("2026-09-30T12:00:00Z") == "sep"
    assert sp.window_of("2026-10-31T12:00:00Z") == "oct"
    assert sp.window_of("2026-11-01T00:00:00Z") is None


def test_eligible_keeps_only_free_text_posts_long_enough_to_scan():
    posts = [post(1, "2026-08-01"), post(2, "2026-08-01", audience="only_paid"),
             post(3, "2026-08-01", type_="podcast"), post(4, "2026-08-01", words=99)]
    assert [p["id"] for p in sp.eligible(posts)] == [1]


def test_pick_posts_one_per_window_and_reproducible():
    posts = [post(i, d) for i, d in enumerate(["2026-07-25", "2026-08-10", "2026-09-05", "2026-10-02",
                                                "2026-10-20", "2026-06-01"])]
    picked = sp.pick_posts(posts)
    assert sorted(sp.window_of(p["post_date"]) for p in picked) == ["jul21_aug", "oct", "sep"]
    assert picked == sp.pick_posts(list(reversed(posts)))  # order of the archive does not matter


def test_pick_posts_skips_empty_windows():
    assert [sp.window_of(p["post_date"]) for p in sp.pick_posts([post(1, "2026-09-05")])] == ["sep"]


def test_rank_is_fixed_by_id():
    assert sp.rank(123) == sp.rank(123) and sp.rank(123) != sp.rank(124)


def test_listed_pubs_keeps_page_order_so_pilot_pubs_come_first():
    pages = {0: {"publications": [{"id": i, "language": "en"} for i in range(5)] + [{"id": 99, "language": "es"}],
                 "more": True},
             1: {"publications": [{"id": i} for i in range(5, 10)], "more": False}}
    got = [p["id"] for p in sp.listed_pubs(1, get=lambda url: pages[int(url.rsplit("=", 1)[1])])]
    assert sorted(got[:5]) == [0, 1, 2, 3, 4] and sorted(got[5:]) == [5, 6, 7, 8, 9]  # page 0 before page 1
    assert got[:5] == sorted(range(5), key=sp.rank)  # ranked within page, as the pilot was
    assert 99 not in got


def test_carry_over_copies_hand_columns_by_post_id():
    rows = [{"post_id": 1, **{h: "" for h in sp.HAND}}, {"post_id": 2, **{h: "" for h in sp.HAND}}]
    coded = {"1": {**{h: "" for h in sp.HAND}, "status": "unavailable", "checked_on": "2026-11-08"}}
    out = sp.carry_over(rows, coded)
    assert out[0]["status"] == "unavailable" and out[0]["checked_on"] == "2026-11-08"
    assert out[1]["status"] == ""
