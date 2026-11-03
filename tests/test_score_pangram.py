import numpy as np

from score_pangram import clean_text, summarize


def test_clean_text_matches_editlens_preprocessing():
    assert clean_text("Sure! Here is a story.\n\nOnce upon   a TIME 😀") == "once upon a time :grinning_face:"
    assert clean_text("Here we go") == "here we go"  # a lone paragraph is kept
    assert clean_text("<think>plan</think>Real  text") == "real text"


def test_summarize_gives_expected_bucket_score():
    logits = np.log(np.array([[0.5, 0.0001, 0.4999], [0.0001, 0.0001, 0.9998]]))
    bucket, score, p_ai = summarize(logits)
    assert list(bucket) == [0, 2]
    assert np.allclose(score, [0.5, 0.99985], atol=1e-3)
    assert np.allclose(p_ai, [0.4999, 0.9998], atol=1e-3)
