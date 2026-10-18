import json
import urllib.parse

import pytest

import arctic


def no_sleep(_):
    pass


def fake_archive(items, requests=None):
    """Fake Arctic Shift: items with after < created_utc < before, sorted by `sort`, at most `limit`."""
    def fetch(url):
        q = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(url).query).items()}
        if requests is not None:
            requests.append(q)
        after, before, limit = int(q["after"]), int(q["before"]), int(q["limit"])
        hits = sorted((x for x in items if after < x["created_utc"] < before),
                      key=lambda x: x["created_utc"], reverse=q.get("sort") == "desc")
        return {"data": hits[:limit]}
    return fetch


def test_get_retries_on_rate_limit_body():
    replies = [{"data": None, "error": "Timeout. Maybe slow down a bit"}, {"data": [{"id": "a"}]}]
    got = arctic.get("posts/search", {"subreddit": "x"}, fetch=lambda url: replies.pop(0), sleep=no_sleep)
    assert got == [{"id": "a"}]


def test_get_retries_on_exception():
    calls = []
    def fetch(url):
        calls.append(url)
        if len(calls) == 1:
            raise TimeoutError("read timed out")
        return {"data": []}
    assert arctic.get("posts/search", {}, fetch=fetch, sleep=no_sleep) == []


def test_get_gives_up_after_tries():
    with pytest.raises(RuntimeError):
        arctic.get("posts/search", {}, fetch=lambda url: {"data": None, "error": "Timeout"},
                   sleep=no_sleep, tries=3)


def test_iter_window_pages_through_everything():
    items = [{"id": str(i), "created_utc": 1000 + i} for i in range(250)]
    got = list(arctic.iter_window("posts/search", "x", 999, 2000, fetch=fake_archive(items), sleep=no_sleep))
    assert sorted(x["id"] for x in got) == sorted(x["id"] for x in items)
    assert len(got) == len(items)


def test_iter_window_asks_newest_first():
    # Arctic Shift times out on oldest-first queries over a month of a large subreddit,
    # but answers newest-first ones, so paging must run backwards in time.
    requests = []
    items = [{"id": str(i), "created_utc": 1000 + i} for i in range(250)]
    list(arctic.iter_window("posts/search", "x", 999, 2000, fetch=fake_archive(items, requests), sleep=no_sleep))
    assert all(q["sort"] == "desc" for q in requests)
    assert len(requests) == 3


def test_iter_window_handles_shared_timestamps_at_page_edge():
    items = [{"id": str(i), "created_utc": 1000 + i // 3} for i in range(250)]  # 3 posts per second
    got = list(arctic.iter_window("posts/search", "x", 999, 2000, fetch=fake_archive(items), sleep=no_sleep))
    assert sorted(x["id"] for x in got) == sorted(x["id"] for x in items)
    assert len(got) == len(items)


def test_months_inclusive_across_year():
    assert arctic.months("2022-11", "2023-02") == ["2022-11", "2022-12", "2023-01", "2023-02"]


def test_month_bounds_december():
    start, end = arctic.month_bounds("2024-12")
    assert start == 1733011200  # 2024-12-01 00:00 UTC
    assert end == 1735689600    # 2025-01-01 00:00 UTC


def test_fetch_month_writes_only_that_month_and_skips_if_present(tmp_path):
    start, end = arctic.month_bounds("2024-01")
    items = [{"id": "before", "created_utc": start - 1}, {"id": "in1", "created_utc": start},
             {"id": "in2", "created_utc": end - 1}, {"id": "after", "created_utc": end}]
    path = arctic.fetch_month("posts/search", "x", "2024-01", tmp_path,
                              fetch=fake_archive(items), sleep=no_sleep)
    assert sorted(json.loads(l)["id"] for l in path.read_text().splitlines()) == ["in1", "in2"]
    # A second call must not hit the network.
    def boom(url):
        raise AssertionError("should not fetch")
    assert arctic.fetch_month("posts/search", "x", "2024-01", tmp_path, fetch=boom, sleep=no_sleep) == path


def test_get_retries_when_error_accompanies_data():
    # A reply carrying an error must never end a month early as if it were the last page.
    replies = [{"data": [], "error": "Timeout. Maybe slow down a bit"}, {"data": [{"id": "a"}]}]
    got = arctic.get("posts/search", {}, fetch=lambda url: replies.pop(0), sleep=no_sleep)
    assert got == [{"id": "a"}]


def test_count_gaps_flags_months_missing_posts():
    local = {"2024-01": 100, "2024-02": 50, "2024-03": 0}
    remote = {"2024-01": 101, "2024-02": 80, "2024-03": 10}
    assert arctic.count_gaps(local, remote, tolerance=0.05) == ["2024-02", "2024-03"]
