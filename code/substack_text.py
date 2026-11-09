"""Plain text of Substack posts, for scoring with Pangram.

Usage: python3 code/substack_text.py IDS.csv OUT.parquet
       IDS.csv has a post_id column; OUT gets id, selftext and n_words, the columns the Pangram scorers read.
       Fetches one post per request through substack.post_by_id and saves after every SAVE_EVERY posts, so a
       rerun picks up where it stopped. Posts the endpoint will not return (404, paywalled) keep an empty text.

body_html carries Substack's own widgets inside the post (subscribe boxes, share and comment buttons, image
captions, footnote anchors). Those are dropped so the scored text is the writer's prose.
"""

import re
import sys
import urllib.error
from html.parser import HTMLParser
from pathlib import Path

import pandas as pd

import substack

BLOCKS = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre", "tr", "hr"}
SKIP_TAGS = {"script", "style", "figcaption", "button", "form", "svg", "iframe"}
SKIP_CLASSES = ("subscription-widget", "button-wrapper", "captioned-button", "share-dialog", "footnote-anchor",
                "footnote-number", "image-link-expand", "paywall", "embedded-post")
VOID = {"br", "hr", "img", "input", "meta", "link", "source", "wbr"}
SAVE_EVERY = 25


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip_depth = 0  # >0 while inside an element being dropped

    def handle_starttag(self, tag, attrs):
        if tag in VOID:
            if tag in BLOCKS and not self.skip_depth:
                self.parts.append("\n")
            return
        cls = dict(attrs).get("class") or ""
        if self.skip_depth or tag in SKIP_TAGS or any(s in cls for s in SKIP_CLASSES):
            self.skip_depth += 1
        elif tag in BLOCKS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if self.skip_depth:
            self.skip_depth -= 1
        elif tag in BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip_depth:
            self.parts.append(data)


def html_to_text(html):
    p = _Text()
    p.feed(html or "")
    p.close()
    lines = (re.sub(r"[ \t\xa0]+", " ", line).strip() for line in "".join(p.parts).split("\n"))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def word_count(text):
    return len(text.split())


def fetch_texts(ids, out, get=substack.post_by_id):
    """Fill `out` (parquet) with the text of every id in `ids` not already there."""
    have = pd.read_parquet(out) if Path(out).exists() else pd.DataFrame(columns=["id", "selftext", "n_words"])
    rows = have.to_dict("records")
    done = set(have["id"].astype(str))
    todo = [str(i) for i in ids if str(i) not in done]
    for n, pid in enumerate(todo, 1):
        try:
            text = html_to_text(get(pid)["post"].get("body_html"))
        except urllib.error.HTTPError as e:
            print(f"  {pid}: HTTP {e.code}, kept empty")
            text = ""
        rows.append({"id": pid, "selftext": text, "n_words": word_count(text)})
        if n % SAVE_EVERY == 0 or n == len(todo):
            pd.DataFrame(rows).to_parquet(out, index=False)
            print(f"  {n}/{len(todo)}")
    return pd.DataFrame(rows)


def main():
    ids_csv, out = sys.argv[1:3]
    fetch_texts(pd.read_csv(ids_csv, dtype=str)["post_id"], out)


if __name__ == "__main__":
    main()
