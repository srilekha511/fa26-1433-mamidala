import pandas as pd

from sample_ban_text import draw_days, keep_on_day, screen_row, window_days


def test_window_days_covers_whole_months_around_the_ban():
    ban = pd.Period("2024-01", "M")
    assert window_days(ban, (-6, -1)) == ("2023-07-01", "2023-12-31")
    assert window_days(ban, (1, 6)) == ("2024-02-01", "2024-07-31")


def test_draw_days_is_fixed_distinct_and_inside_the_window():
    days = draw_days("x", "2023-07-01", "2023-12-31")
    assert days == draw_days("x", "2023-07-01", "2023-12-31")
    assert len(set(days)) == 10 and all("2023-07-01" <= d <= "2023-12-31" for d in days)
    assert days != draw_days("y", "2023-07-01", "2023-12-31")


def test_draw_days_takes_every_day_of_a_short_window():
    assert draw_days("x", "2023-07-01", "2023-07-03") == ["2023-07-01", "2023-07-02", "2023-07-03"]


def test_keep_on_day_caps_with_a_fixed_draw():
    ids = [str(i) for i in range(40)]
    kept = keep_on_day("x", "2023-07-01", ids, cap=25)
    assert len(kept) == 25 and kept <= set(ids)
    assert kept == keep_on_day("x", "2023-07-01", list(reversed(ids)), cap=25)
    assert keep_on_day("x", "2023-07-01", ids[:5], cap=25) == set(ids[:5])


def test_screen_row_counts_scorable_text_posts():
    long = " ".join(["word"] * 60)
    posts = [{"is_self": True, "selftext": long, "author": "a"}, {"is_self": True, "selftext": "short", "author": "a"},
             {"is_self": False, "selftext": "", "author": "a"}, {"is_self": True, "selftext": long, "author": "b"}]
    assert screen_row("x", posts) == {"subreddit": "x", "n_screened": 4, "n_text": 2, "text_share": 0.5}
