import wayback

SIDEBAR = """<html><body><div class="content"><p>AI post title in the feed</p></div>
<div class="side"><div class="md"><p>Welcome!</p><ol><li>Be civil.</li>
<li>AI-generated posts must use the "AI" flair.</li></ol></div></div></body></html>"""

WIKI = """<html><body><div class="wiki-page-content"><div class="md wiki">
<h2>Rules</h2><p>No spam.</p><p>Posts made with ChatGPT should be flaired.</p></div></div></body></html>"""


def test_parse_cdx_skips_header():
    body = [["timestamp", "original", "statuscode"], ["20230101000000", "https://old.reddit.com/r/x/", "200"]]
    assert wayback.parse_cdx(body) == [{"timestamp": "20230101000000",
                                        "original": "https://old.reddit.com/r/x/", "statuscode": "200"}]
    assert wayback.parse_cdx([]) == []


def test_snapshot_url_uses_raw_id_mode():
    assert wayback.snapshot_url("20230101000000", "https://old.reddit.com/r/x/") == \
        "https://web.archive.org/web/20230101000000id_/https://old.reddit.com/r/x/"


def test_cdx_url_asks_for_one_200_capture_per_month():
    url = wayback.cdx_url("old.reddit.com/r/x/", 2021, 2025)
    assert "collapse=timestamp%3A6" in url and "filter=statuscode%3A200" in url and "from=2021" in url


def test_extract_rule_text_reads_sidebar_not_feed():
    text = wayback.extract_rule_text(SIDEBAR)
    assert "Be civil." in text
    assert "feed" not in text


def test_extract_rule_text_reads_wiki():
    assert "No spam." in wayback.extract_rule_text(WIKI)


def test_extract_rule_text_empty_page():
    assert wayback.extract_rule_text("<html><body></body></html>") == ""


def test_ai_snippets():
    assert wayback.ai_snippets(wayback.extract_rule_text(SIDEBAR)) == ['AI-generated posts must use the "AI" flair.']
    assert wayback.ai_snippets(wayback.extract_rule_text(WIKI)) == ["Posts made with ChatGPT should be flaired."]


def test_mark_changes_per_subreddit_and_kind():
    rows = [{"subreddit": "a", "kind": "sidebar", "timestamp": "1", "snippets": ""},
            {"subreddit": "a", "kind": "sidebar", "timestamp": "2", "snippets": "AI ok"},
            {"subreddit": "a", "kind": "sidebar", "timestamp": "3", "snippets": "AI ok"},
            {"subreddit": "a", "kind": "wiki_rules", "timestamp": "1", "snippets": "AI ok"},
            {"subreddit": "b", "kind": "sidebar", "timestamp": "1", "snippets": "AI ok"}]
    assert [r["changed"] for r in wayback.mark_changes(rows)] == [True, True, False, True, True]


def test_decode_body_handles_gzipped_raw_snapshots():
    # Wayback's id_ mode returns the body exactly as archived, often still gzip-compressed.
    import gzip
    html = "<p>AI posts must be flaired.</p>"
    assert wayback.decode_body(gzip.compress(html.encode())) == html
    assert wayback.decode_body(html.encode()) == html
