from build_expansion_review import estimate_flaired, is_mod_ai_post, suggest


def base(**kw):
    row = {"screen_role": "voluntary", "topic_flair_only": False, "median_monthly_posts": 100,
           "est_flaired_posts": 50, "first_flair_month": "2023-05"}
    return {**row, **kw}


def test_estimate_scales_each_month_sample_to_its_count():
    samples = {"2023-01": [{"link_flair_text": "AI"}] + [{}] * 99, "2023-02": [{"link_flair_text": "AI"}, {}]}
    # 1% of 1,000 posts, plus a fully sampled month with one flaired post.
    assert estimate_flaired(samples, {"2023-01": 1000, "2023-02": 2}, {"AI"}) == 11


def test_estimate_without_counts_uses_the_sample():
    assert estimate_flaired({"2023-01": [{"link_flair_text": "AI"}, {}]}, None, {"AI"}) == 1


def test_suggest_keep():
    assert suggest(base())[0] == "keep"


def test_suggest_drops_small_late_ban_and_topic_flairs():
    assert suggest(base(median_monthly_posts=10)) == ("drop", "small: median 10 posts a month")
    assert suggest(base(first_flair_month="2025-08"))[0] == "drop"
    assert suggest(base(screen_role="ban"))[0] == "drop"
    assert suggest(base(topic_flair_only=True))[0] == "drop"


def test_suggest_check_when_counts_missing():
    assert suggest(base(median_monthly_posts=None)) == ("check", "post counts unavailable")


def test_is_mod_ai_post():
    assert is_mod_ai_post({"distinguished": "moderator", "title": "New rule: flair AI art"})
    assert not is_mod_ai_post({"stickied": False, "title": "AI art"})
    assert not is_mod_ai_post({"stickied": True, "title": "Weekly thread"})
