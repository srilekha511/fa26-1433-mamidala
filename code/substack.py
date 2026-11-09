"""Client for Substack's public JSON endpoints (unofficial and undocumented; they can change without notice).

The archive lists a publication's posts newest first, 15 at a time, with dates, word counts, audience and
engagement but an empty body_html. Since about November 2026 it pages by cursor: each reply is
{"posts": [...], "nextCursor": ...} and any `offset` parameter is answered with 400, which breaks the
substack-api package (1.3.1). Post text comes from the by-id endpoint, one request per post.
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request

HEADERS = {"User-Agent": "fa26-1433 research project"}
PAUSE = 3  # seconds to wait after every successful request
PAGE = 15


def http_get_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def get_json(url, fetch=http_get_json, sleep=time.sleep, tries=6):
    """Return the JSON reply for one request, retrying rate limits, server errors and network errors."""
    for attempt in range(tries):
        try:
            body = fetch(url)
            sleep(PAUSE)
            return body
        except urllib.error.HTTPError as e:
            if e.code != 429 and e.code < 500:
                raise
            print(f"  retry {attempt + 1}: HTTP {e.code}")
        except Exception as e:
            print(f"  retry {attempt + 1}: {e}")
        sleep(15 * (attempt + 1))
    raise RuntimeError(f"failed after {tries} tries: {url}")


def iter_archive(pub_url, since=None, **kw):
    """Yield a publication's posts newest first, down to the first post dated before `since` (ISO date)."""
    seen = set()
    cursor = None
    while True:
        params = {"sort": "new", "limit": PAGE} | ({"cursor": cursor} if cursor else {})
        reply = get_json(f"{pub_url.rstrip('/')}/api/v1/archive?" + urllib.parse.urlencode(params), **kw)
        for p in reply["posts"]:
            if since and p["post_date"] < since:
                return
            if p["id"] not in seen:
                seen.add(p["id"])
                yield p
        cursor = reply.get("nextCursor")
        if not cursor or not reply["posts"]:
            return


def post_by_id(post_id, **kw):
    """Full JSON for one post: {"post": {... body_html ...}, "publication": ..., "publicationSettings": ...}."""
    return get_json(f"https://substack.com/api/v1/posts/by-id/{post_id}", **kw)
