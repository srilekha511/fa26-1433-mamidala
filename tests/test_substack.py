import io
import urllib.error
import urllib.parse

import pytest

import substack


def no_sleep(_):
    pass


def http_error(code):
    return urllib.error.HTTPError("https://x", code, "err", {}, io.BytesIO(b"{}"))


def fake_archive(posts, page=3, requests=None):
    """Fake /api/v1/archive: newest first, `page` posts per reply, cursor = post_date of the last one."""
    posts = sorted(posts, key=lambda p: p["post_date"], reverse=True)

    def fetch(url):
        q = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(url).query).items()}
        if requests is not None:
            requests.append(q)
        if "offset" in q:
            raise http_error(400)
        left = [p for p in posts if "cursor" not in q or p["post_date"] < q["cursor"]]
        out = left[:page]
        return {"posts": out, "nextCursor": out[-1]["post_date"] if len(left) > page else None}
    return fetch


def post(i, day):
    return {"id": i, "post_date": f"2026-{day}T12:00:00.000Z"}


POSTS = [post(i, d) for i, d in enumerate(["10-01", "09-01", "08-01", "07-01", "06-01", "05-01", "04-01"])]


def test_get_json_retries_rate_limit_and_errors():
    replies = [http_error(429), TimeoutError("slow"), {"ok": 1}]

    def fetch(url):
        r = replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r
    assert substack.get_json("https://x", fetch=fetch, sleep=no_sleep) == {"ok": 1}


def test_get_json_does_not_retry_client_errors():
    # A 400 or 404 is a wrong request or a missing page; asking again cannot fix it.
    calls = []

    def fetch(url):
        calls.append(url)
        raise http_error(404)
    with pytest.raises(urllib.error.HTTPError):
        substack.get_json("https://x", fetch=fetch, sleep=no_sleep)
    assert len(calls) == 1


def test_get_json_gives_up_after_tries():
    def fetch(url):
        raise http_error(503)
    with pytest.raises(RuntimeError):
        substack.get_json("https://x", fetch=fetch, sleep=no_sleep, tries=3)


def test_iter_archive_follows_cursor_through_everything():
    got = list(substack.iter_archive("https://a.substack.com", fetch=fake_archive(POSTS), sleep=no_sleep))
    assert [p["id"] for p in got] == [p["id"] for p in POSTS]


def test_iter_archive_never_sends_offset():
    # Substack answers any offset with 400 since about November 2026; paging is by cursor.
    requests = []
    list(substack.iter_archive("https://a.substack.com", fetch=fake_archive(POSTS, requests=requests),
                               sleep=no_sleep))
    assert all("offset" not in q for q in requests)
    assert "cursor" not in requests[0] and all("cursor" in q for q in requests[1:])


def test_iter_archive_stops_before_since():
    requests = []
    got = list(substack.iter_archive("https://a.substack.com", since="2026-07-01",
                                     fetch=fake_archive(POSTS, requests=requests), sleep=no_sleep))
    assert [p["post_date"][:10] for p in got] == ["2026-10-01", "2026-09-01", "2026-08-01", "2026-07-01"]
    assert len(requests) == 2  # the page reaching back past `since` is the last one asked for


def test_iter_archive_drops_repeated_ids():
    def fetch(url):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        if "cursor" not in q:
            return {"posts": POSTS[:2], "nextCursor": POSTS[1]["post_date"]}
        return {"posts": POSTS[1:3], "nextCursor": None}
    got = list(substack.iter_archive("https://a.substack.com", fetch=fetch, sleep=no_sleep))
    assert [p["id"] for p in got] == [0, 1, 2]


def test_iter_archive_handles_empty_publication():
    got = list(substack.iter_archive("https://a.substack.com", fetch=lambda url: {"posts": [], "nextCursor": None},
                                     sleep=no_sleep))
    assert got == []


def test_post_by_id_url():
    seen = []
    substack.post_by_id(42, fetch=lambda url: seen.append(url) or {"post": {}}, sleep=no_sleep)
    assert seen == ["https://substack.com/api/v1/posts/by-id/42"]
