import fetch_reddit_dumps


def test_monthly_counts_asks_one_year_at_a_time_and_shifts_bucket_labels():
    calls = []

    def fake_get(endpoint, params):
        calls.append((params["after"], params["before"]))
        # Buckets come labelled at local midnight the evening before the month starts.
        return [{"created_utc": f"{int(params['after'][:4]) - 1}-12-31T23:00:00.000Z", "count": "7"}]

    out = fetch_reddit_dumps.monthly_counts("posts/search", "x", get=fake_get)
    assert calls == [("2022-01-01", "2023-01-01"), ("2023-01-01", "2024-01-01"),
                     ("2024-01-01", "2025-01-01"), ("2025-01-01", "2026-01-01")]
    assert out == {"2022-01": 7, "2023-01": 7, "2024-01": 7, "2025-01": 7}
