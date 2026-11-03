from score_pangram_api import idempotency_key, row

RESULT = {"stage": "STAGE_SUCCESS", "prediction_short": "AI", "fraction_ai": 0.9, "fraction_ai_assisted": 0.1,
          "fraction_human": 0.0, "num_ai_segments": 2, "num_human_segments": 0, "version": "4.1"}


def test_row_reads_a_successful_item():
    assert row({"id": "abc", "result": RESULT}) == {"id": "abc", "prediction_short": "AI", "fraction_ai": 0.9,
                                                    "fraction_ai_assisted": 0.1, "fraction_human": 0.0,
                                                    "num_ai_segments": 2, "num_human_segments": 0, "version": "4.1"}


def test_row_skips_failed_and_unfinished_items():
    assert row({"id": "abc", "result": None, "stage": "STAGE_FAILED"}) is None
    assert row({"id": "abc", "result": {**RESULT, "stage": "STAGE_FAILED"}}) is None


def test_idempotency_key_is_fixed_by_the_body():
    a = {"items": [{"id": "1", "text": "x"}], "model": "pangram-4.1"}
    assert idempotency_key(a) == idempotency_key({"model": "pangram-4.1", "items": [{"id": "1", "text": "x"}]})
    assert idempotency_key(a) != idempotency_key({**a, "items": [{"id": "2", "text": "x"}]})
