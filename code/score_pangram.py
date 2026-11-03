"""Score the sampled text posts with open Pangram (EditLens, RoBERTa-large; Thai et al. 2026).

Usage: python3 code/score_pangram.py   (after sample_ban_text.py sample)
Needs the gated model: accept its terms at https://huggingface.co/pangram/editlens_roberta-large while logged in
with the account whose token is in ~/.cache/huggingface/token. The model is CC BY-NC-SA 4.0 (non-commercial).

Writes data/derived/pangram_scores.csv: one row per post id with
  bucket   the most likely bucket, 0 = human-written ... n_buckets-1 = AI-generated
  score    the expected bucket over the predicted distribution, scaled to [0, 1] (EditLens's score_pred)
  p_ai     the probability of the top (AI-generated) bucket
Scores already in the file are skipped, so a stopped run can be restarted. Text is cleaned as in EditLens's
preprocess.clean_text and cut at MAX_LENGTH tokens, as in its inference script.
"""

import re

import emoji
import numpy as np
import pandas as pd
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from reddit_subreddits import ROOT

DERIVED = ROOT / "data" / "derived"
SCORES = DERIVED / "pangram_scores.csv"
MODEL = "pangram/editlens_roberta-large"
MAX_LENGTH, BATCH = 512, 16
# EditLens drops a first paragraph that starts like a chatbot reply, as in its training data.
BOILERPLATE_STARTS = ("Sure", "Here", "Abstract", "Title", "I'm happy to help", "Certainly")


def remove_ai_header(text):
    paragraphs = [p for p in text.split("\n") if p.strip()]
    if not paragraphs:
        return text
    first = emoji.replace_emoji(re.sub(r"^[^a-zA-Z0-9]*", "", paragraphs[0]), "")
    if first.startswith(BOILERPLATE_STARTS) and len(paragraphs) > 1:
        return "\n".join(paragraphs[1:])
    return text


def clean_text(text):
    """EditLens's preprocess.clean_text: emoji to words, drop a chatbot header, lowercase, one space."""
    text = emoji.demojize(text)
    if "</think>" in text:
        text = text.split("</think>")[1].strip()
    text = remove_ai_header(text)
    return re.sub(r"\s+", " ", text.lower()).strip()


def summarize(logits):
    """(bucket, score, p_ai) from an (n, n_buckets) array of logits, as in EditLens's inference script."""
    p = torch.softmax(torch.as_tensor(logits, dtype=torch.float32), dim=1).numpy()
    k = p.shape[1]
    return p.argmax(1), p @ np.arange(k) / (k - 1), p[:, -1]


def device():
    return "mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu"


def main():
    posts = pd.read_parquet(DERIVED / "ban_text_posts.parquet", columns=["id", "selftext"]).drop_duplicates("id")
    done = set(pd.read_csv(SCORES)["id"]) if SCORES.exists() else set()
    todo = posts[~posts["id"].isin(done)]
    print(f"{len(posts)} posts, {len(done)} already scored, {len(todo)} to score")
    if todo.empty:
        return
    tok = AutoTokenizer.from_pretrained(MODEL)
    dev = device()
    model = AutoModelForSequenceClassification.from_pretrained(MODEL).to(dev).eval()
    print(f"{model.config.num_labels} buckets, on {dev}")
    texts = [clean_text(t) for t in todo["selftext"]]
    # Similar lengths in a batch waste less padding.
    order = np.argsort([len(t) for t in texts])
    ids = todo["id"].to_numpy()
    for start in range(0, len(order), BATCH * 25):
        chunk = order[start:start + BATCH * 25]
        logits = []
        for b in range(0, len(chunk), BATCH):
            enc = tok([texts[i] for i in chunk[b:b + BATCH]], truncation=True, max_length=MAX_LENGTH,
                      padding=True, return_tensors="pt").to(dev)
            with torch.no_grad():
                logits.append(model(**enc).logits.float().cpu())
        bucket, score, p_ai = summarize(torch.cat(logits))
        out = pd.DataFrame({"id": ids[chunk], "bucket": bucket, "score": score.round(4), "p_ai": p_ai.round(4)})
        out.to_csv(SCORES, mode="a", header=not SCORES.exists(), index=False)
        print(f"{min(start + len(chunk), len(order))}/{len(order)} scored", flush=True)


if __name__ == "__main__":
    main()
