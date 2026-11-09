import io
import urllib.error

import pandas as pd

import substack_text as st

BODY = """<div class="body markup"><h2>Heading</h2><p>First &amp; best<br>line two.</p>
<div class="captioned-image-container"><figure><img src="x.png"><figcaption>A caption</figcaption></figure></div>
<div class="subscription-widget-wrap"><div class="subscription-widget"><p>Subscribe to read more</p>
<form><input type="email"><button>Subscribe</button></form></div></div>
<p>Third<a class="footnote-anchor" href="#f1">1</a> paragraph.</p>
<p class="button-wrapper"><a class="button"><span>Share</span></a></p>
<ul><li>one</li><li>two</li></ul></div>"""


def test_html_to_text_keeps_prose_and_drops_widgets():
    assert st.html_to_text(BODY) == "Heading\n\nFirst & best\nline two.\n\nThird paragraph.\n\none\n\ntwo"


def test_html_to_text_empty():
    assert st.html_to_text(None) == "" and st.html_to_text("") == ""


def test_word_count():
    assert st.word_count("a  b\nc") == 3


def test_fetch_texts_resumes_and_keeps_failures_empty(tmp_path):
    out = tmp_path / "t.parquet"
    calls = []

    def get(pid):
        calls.append(pid)
        if pid == "3":
            raise urllib.error.HTTPError("u", 404, "nf", {}, io.BytesIO(b""))
        return {"post": {"body_html": f"<p>post {pid} text</p>"}}
    st.fetch_texts(["1", "2"], out, get=get)
    df = st.fetch_texts(["1", "2", "3"], out, get=get)
    assert calls == ["1", "2", "3"]  # 1 and 2 are not fetched again
    assert df.set_index("id")["n_words"].to_dict() == {"1": 3, "2": 3, "3": 0}
    assert pd.read_parquet(out).shape[0] == 3
