import json
import urllib.error

import pandas as pd

import fetch_substack_engagement as f


def reply(n_comments):
    return {"post": {"reaction_count": 5, "comment_count": n_comments, "child_comment_count": 0, "restacks": 1,
                     "audience": "everyone", "write_comment_permissions": "everyone", "body_html": "x"}}


def test_fetch_engagement_resumes_and_skips_errors(tmp_path):
    out = tmp_path / "eng.csv"
    sample = pd.DataFrame({"post_id": ["1", "2", "3"]})
    pd.DataFrame([{"post_id": "1", "reaction_count": 9}]).to_csv(out, index=False)
    calls = []

    def get(pid):
        calls.append(pid)
        if pid == "3":
            raise urllib.error.HTTPError("u", 404, "nf", {}, None)
        return reply(2)

    eng = f.fetch_engagement(sample, out, get=get, clock=lambda: 0)
    assert calls == ["2", "3"]
    assert eng["post_id"].tolist() == ["1", "2"] and "body_html" not in eng
    assert pd.read_csv(out, dtype={"post_id": str})["post_id"].tolist() == ["1", "2"]


def test_fetch_comments_only_posts_with_comments(tmp_path):
    sample = pd.DataFrame({"post_id": ["1", "2"], "pub_url": ["https://a.substack.com/", "https://b.substack.com"]})
    eng = pd.DataFrame({"post_id": ["1", "2"], "comment_count": [3, 0]})
    urls = []
    f.fetch_comments(sample, eng, tmp_path, get=lambda u: urls.append(u) or {"comments": [{"body": "hi"}]})
    assert urls == ["https://a.substack.com/api/v1/post/1/comments?all_comments=true&sort=oldest_first"]
    assert json.loads((tmp_path / "1.json").read_text())["comments"][0]["body"] == "hi"
    f.fetch_comments(sample, eng, tmp_path, get=lambda u: 1 / 0)  # already saved: not fetched again
