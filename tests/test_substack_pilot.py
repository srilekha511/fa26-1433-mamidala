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
