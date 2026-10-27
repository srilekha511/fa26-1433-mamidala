from check_rule_dates import problems
from list_mod_ai_posts import is_mod_ai_post

GOOD = {"subreddit": "a", "group": "switcher", "label_start": "2023-02-01", "mandatory_start": "2024-01-15",
        "label_source": "https://web.archive.org/web/x", "mandatory_source": "https://web.archive.org/web/y",
        "notes": ""}


def test_good_file_has_no_problems():
    assert problems([GOOD], ["a"]) == []


def test_never_mandatory_is_allowed():
    assert problems([{**GOOD, "group": "voluntary_throughout", "mandatory_start": "", "mandatory_source": ""}],
                    ["a"]) == []


def test_catches_bad_group():
    assert any("group" in p for p in problems([{**GOOD, "group": "ban"}], ["a"]))
    assert any("switcher needs" in p for p in problems([{**GOOD, "mandatory_start": "", "mandatory_source": ""}], ["a"]))


def test_catches_each_error():
    rows = [{**GOOD, "label_start": "2023/02/01"},
            {**GOOD, "subreddit": "b", "mandatory_start": "2022-01-01"},
            {**GOOD, "subreddit": "c", "label_source": ""},
            {**GOOD, "subreddit": "zzz"}]
    got = problems(rows, ["a", "b", "c", "d"])
    assert any(p.startswith("a:") and "label_start" in p for p in got)
    assert any(p.startswith("b:") and "before" in p for p in got)
    assert any(p.startswith("c:") and "label_source" in p for p in got)
    assert any(p.startswith("zzz:") and "not a study subreddit" in p for p in got)
    assert any(p.startswith("d:") and "missing" in p for p in got)


def test_mod_ai_post():
    assert is_mod_ai_post({"distinguished": "moderator", "title": "Rule update: AI content", "selftext": ""})
    assert is_mod_ai_post({"stickied": True, "title": "Announcement", "selftext": "ChatGPT posts need a flair"})
    assert not is_mod_ai_post({"distinguished": None, "title": "AI story", "selftext": ""})
    assert not is_mod_ai_post({"distinguished": "moderator", "title": "Weekly thread", "selftext": ""})
