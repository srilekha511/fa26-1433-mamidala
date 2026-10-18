"""Wayback Machine helpers: list monthly snapshots of subreddit rule pages and read their rules."""

import gzip
import json
import time
import urllib.parse
import urllib.request

from bs4 import BeautifulSoup

from reddit_text import is_ai_text

CDX = "https://web.archive.org/cdx/search/cdx"
HEADERS = {"User-Agent": "fa26-1433 research project"}

# old.reddit's front page shows the sidebar, which most subreddits use for rules; the wiki and
# about/rules pages are archived less often but are checked too.
PAGES = {
    "sidebar": "old.reddit.com/r/{sub}/",
    "wiki_rules": "www.reddit.com/r/{sub}/wiki/rules",
    "about_rules": "old.reddit.com/r/{sub}/about/rules",
}
SELECTORS = ["div.side div.md", "div.wiki-page-content div.md", "div.subreddit-rules-page"]


def decode_body(raw):
    """Decode a response body, decompressing it first if it is gzipped."""
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return raw.decode("utf-8", errors="replace")


def fetch_text(url, tries=5):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=120) as r:
                return decode_body(r.read())
        except Exception as e:
            print(f"  retry {attempt + 1}: {e}")
            time.sleep(20 * (attempt + 1))
    raise RuntimeError(f"failed after {tries} tries: {url}")


def cdx_url(page_url, first_year, last_year):
    return CDX + "?" + urllib.parse.urlencode({
        "url": page_url, "output": "json", "fl": "timestamp,original,statuscode",
        "filter": "statuscode:200", "collapse": "timestamp:6", "from": first_year, "to": last_year})


def parse_cdx(body):
    if not body:
        return []
    header, *rows = body
    return [dict(zip(header, r)) for r in rows]


def list_snapshots(page_url, first_year, last_year):
    text = fetch_text(cdx_url(page_url, first_year, last_year))
    return parse_cdx(json.loads(text) if text.strip() else [])


def snapshot_url(timestamp, original):
    """URL of the archived page exactly as captured, without the Wayback toolbar."""
    return f"https://web.archive.org/web/{timestamp}id_/{original}"


def extract_rule_text(html):
    soup = BeautifulSoup(html, "html.parser")
    parts = [el.get_text("\n", strip=True) for sel in SELECTORS for el in soup.select(sel)]
    return "\n".join(p for p in parts if p)


def ai_snippets(text):
    return [line.strip() for line in text.splitlines() if is_ai_text(line)]


def mark_changes(rows):
    """Flag rows whose AI snippets differ from the previous snapshot of the same page."""
    rows = sorted(rows, key=lambda r: (r["subreddit"], r["kind"], r["timestamp"]))
    prev = {}
    for r in rows:
        key = (r["subreddit"], r["kind"])
        r["changed"] = key not in prev or prev[key] != r["snippets"]
        prev[key] = r["snippets"]
    return rows
