# Reddit Data Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Reddit sample for the AI-disclosure project: find text subreddits with an AI post flair, date when each one's AI label started and when it became mandatory, pull all their posts and comments for 2022–2025, and produce one cleaned post file tagged by labeling period.

**Architecture:** Three small library modules in `code/` (`arctic.py` for the Arctic Shift API, `wayback.py` for the Wayback Machine, `reddit_text.py` for text rules), each with pytest tests in `tests/`. Thin scripts in `code/` call them. Every network response is cached under `data/raw/`, so any script can be killed and rerun without re-downloading. Two judgment calls are made by hand and saved as tracked CSVs in `data/hand_coded/`: which flairs count as AI labels, and the rule dates.

**Tech Stack:** Python 3.13, standard library `urllib`, BeautifulSoup 4, pandas, pyarrow, pytest. All are already installed.

**Spec:** Step 1 ("Reddit") of the project procedure. The analysis is a difference-in-differences across subreddits (decided in GitHub issue #2, replacing the post-level regression on H_i). One row per subreddit-month:

Y_st = α_s + λ_t + β·(Mandatory_s × Post_st) + ε_st

Treated subreddits switch from a voluntary to a mandatory AI label (`mandatory_start`). Controls keep the label voluntary. The same equation runs twice:
- **Creator side:** Y = share of AI-flagged posts with the AI label. β is how much labeling was missing while it was voluntary.
- **Reader side:** Y = engagement on AI-flagged posts (`score`, `num_comments`, share with "is this AI?" call-out comments). The reader β divided by the creator β is the effect of a label on engagement for posts labeled only because the rule required it.

Subreddit and month fixed effects (α_s, λ_t) absorb fixed community differences and shocks common to all subreddits, including the Arctic Shift capture change around 2023-07. Switch dates are staggered, so the estimate is an event study (Callaway–Sant'Anna or Sun–Abraham), with flat pre-switch months as the parallel-trends check. A second outcome, AI share of all posts, checks whether the rule pushed AI posters out. If too few subreddits switch, the fallback uses `label_start` as the treatment, with reader-side outcomes only.

The sample is all text posts in every period (`pre`, `voluntary`, `mandatory`), not only voluntary-period posts. This plan stops before Pangram scoring and building the subreddit-month panel. Its output is the post file those steps consume.

## Global Constraints

- Every Arctic Shift request sends `User-Agent: fa26-1433 research project` (requests without one are rejected) and waits at least 3 seconds after each success.
- Arctic Shift sometimes returns HTTP 200 with `{"data": null, "error": "Timeout. Maybe slow down a bit"}`. Treat that as a retry, never as an empty result.
- Study window: months `2022-01` through `2025-12`, inclusive, in UTC.
- Original downloads go in `data/raw/` and built files in `data/derived/`. Both are gitignored, so never force-add them. Hand-coded inputs go in `data/hand_coded/`, which is tracked.
- Never commit API keys or tokens.
- Scripts run from the repo root as `python3 code/<script>.py`. Tests run as `python3 -m pytest tests -v`.
- Work on a branch named `reddit-pipeline`, not on `main`.

## Review Focus

1. **Flair added after posting.** Arctic Shift often stores a post only as it looked on first retrieval (`_meta.note == "no_2nd_retrieval"`), seconds after posting. A flair the author or a moderator added later would be missed, which undercounts disclosure. Task 6 keeps `meta_note` and `flair_lag_hours` on every row, and its summary reports the share of first-retrieval-only posts. Task 6 Step 8 checks 50 posts by hand against live Reddit.
2. **Moderator-removed posts.** In the mandatory period, moderators remove unlabeled AI posts. Dropping removed posts would make labeling look more complete than it was. `keep_post` keeps removed posts whose text survives and drops only posts whose text is `[removed]`, `[deleted]` or empty. Tests cover each case.
3. **Rate-limit replies.** The 200-status "Timeout" body is handled as a retry (`test_get_retries_on_rate_limit_body`).
4. **Posts sharing a timestamp at a page edge.** These are neither skipped nor duplicated (`test_iter_window_handles_shared_timestamps_at_page_edge`).
5. **Posts on the exact rule-change day, and subreddits that never went mandatory.** `period` tests cover the boundary day, a missing mandatory date and a missing label date.

---

## File Structure

| File | Responsibility |
|---|---|
| `code/arctic.py` | Arctic Shift client: retrying GET, paging through a time window, caching one subreddit-month per file |
| `code/reddit_text.py` | Text rules: AI-keyword match, flair tallies, word count, which posts to keep, labeling period |
| `code/wayback.py` | Wayback CDX queries, snapshot URLs, extracting rule text and AI-related lines from saved HTML |
| `code/reddit_subreddits.py` | Seed subreddit list, plus the study list read from `data/hand_coded/ai_flairs.csv` |
| `code/find_ai_flair_subreddits.py` | Samples posts from seed subreddits and writes the flair inventory and a draft approval list |
| `code/fetch_rule_snapshots.py` | Downloads monthly Wayback snapshots of each study subreddit's sidebar and rules pages |
| `code/extract_rule_snippets.py` | Turns saved snapshots into a table of AI-related rule lines, marking when they change |
| `code/fetch_reddit_dumps.py` | Checks volume, then pulls all posts or comments month by month |
| `code/list_mod_ai_posts.py` | Lists moderator posts that mention AI, as evidence for the rule dates |
| `code/check_rule_dates.py` | Checks the hand-coded rule-date file for errors |
| `code/build_reddit_posts.py` | Builds `data/derived/reddit_posts.parquet` |
| `data/hand_coded/README.md` | Coding guide for the two hand-coded files |
| `data/hand_coded/ai_flairs.csv` | Approved AI flairs: `subreddit,flair_text,notes` |
| `data/hand_coded/reddit_rule_dates.csv` | `subreddit,label_start,mandatory_start,label_source,mandatory_source,notes` |
| `tests/conftest.py` | Puts `code/` on the import path |
| `tests/test_*.py` | One test file per library module, plus one for the rule-date checker |

---

### Task 1: Arctic Shift client

**Files:**
- Create: `code/arctic.py`
- Create: `tests/conftest.py`
- Create: `tests/test_arctic.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `arctic.get(endpoint: str, params: dict, fetch=http_get_json, sleep=time.sleep, tries: int = 6) -> list[dict]`
  - `arctic.iter_window(endpoint: str, subreddit: str, after: int, before: int, **kw) -> Iterator[dict]` (epoch seconds, oldest first, no duplicates)
  - `arctic.months(first: str, last: str) -> list[str]` (inclusive `"YYYY-MM"` list)
  - `arctic.month_bounds(month: str) -> tuple[int, int]` (epoch of the month's first second, epoch of next month's first second)
  - `arctic.fetch_month(endpoint: str, subreddit: str, month: str, out_dir: Path, **kw) -> Path` (writes `out_dir/subreddit/month.jsonl`, skips if it exists)

- [ ] **Step 1: Create the branch**

```bash
git checkout -b reddit-pipeline
```

- [ ] **Step 2: Write the failing tests**

`tests/conftest.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "code"))
```

`tests/test_arctic.py`:

```python
import json
import urllib.parse

import pytest

import arctic


def no_sleep(_):
    pass


def fake_archive(items):
    """Fake Arctic Shift: items with after < created_utc < before, oldest first, at most `limit`."""
    def fetch(url):
        q = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(url).query).items()}
        after, before, limit = int(q["after"]), int(q["before"]), int(q["limit"])
        hits = sorted((x for x in items if after < x["created_utc"] < before),
                      key=lambda x: x["created_utc"])
        return {"data": hits[:limit]}
    return fetch


def test_get_retries_on_rate_limit_body():
    replies = [{"data": None, "error": "Timeout. Maybe slow down a bit"}, {"data": [{"id": "a"}]}]
    got = arctic.get("posts/search", {"subreddit": "x"}, fetch=lambda url: replies.pop(0), sleep=no_sleep)
    assert got == [{"id": "a"}]


def test_get_retries_on_exception():
    calls = []
    def fetch(url):
        calls.append(url)
        if len(calls) == 1:
            raise TimeoutError("read timed out")
        return {"data": []}
    assert arctic.get("posts/search", {}, fetch=fetch, sleep=no_sleep) == []


def test_get_gives_up_after_tries():
    with pytest.raises(RuntimeError):
        arctic.get("posts/search", {}, fetch=lambda url: {"data": None, "error": "Timeout"},
                   sleep=no_sleep, tries=3)


def test_iter_window_pages_through_everything():
    items = [{"id": str(i), "created_utc": 1000 + i} for i in range(250)]
    got = list(arctic.iter_window("posts/search", "x", 999, 2000, fetch=fake_archive(items), sleep=no_sleep))
    assert [x["id"] for x in got] == [x["id"] for x in items]


def test_iter_window_handles_shared_timestamps_at_page_edge():
    items = [{"id": str(i), "created_utc": 1000 + i // 3} for i in range(250)]  # 3 posts per second
    got = list(arctic.iter_window("posts/search", "x", 999, 2000, fetch=fake_archive(items), sleep=no_sleep))
    assert sorted(x["id"] for x in got) == sorted(x["id"] for x in items)
    assert len(got) == len(items)


def test_months_inclusive_across_year():
    assert arctic.months("2022-11", "2023-02") == ["2022-11", "2022-12", "2023-01", "2023-02"]


def test_month_bounds_december():
    start, end = arctic.month_bounds("2024-12")
    assert start == 1733011200  # 2024-12-01 00:00 UTC
    assert end == 1735689600    # 2025-01-01 00:00 UTC


def test_fetch_month_writes_only_that_month_and_skips_if_present(tmp_path):
    start, end = arctic.month_bounds("2024-01")
    items = [{"id": "before", "created_utc": start - 1}, {"id": "in1", "created_utc": start},
             {"id": "in2", "created_utc": end - 1}, {"id": "after", "created_utc": end}]
    path = arctic.fetch_month("posts/search", "x", "2024-01", tmp_path,
                              fetch=fake_archive(items), sleep=no_sleep)
    assert [json.loads(l)["id"] for l in path.read_text().splitlines()] == ["in1", "in2"]
    # A second call must not hit the network.
    def boom(url):
        raise AssertionError("should not fetch")
    assert arctic.fetch_month("posts/search", "x", "2024-01", tmp_path, fetch=boom, sleep=no_sleep) == path
```

- [ ] **Step 3: Run the tests and confirm they fail**

Run: `python3 -m pytest tests/test_arctic.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'arctic'`

- [ ] **Step 4: Write `code/arctic.py`**

```python
"""Client for the Arctic Shift Reddit archive API (https://arctic-shift.photon-reddit.com).

Retries rate-limit replies, pages through a time window oldest-first, and caches each
subreddit-month as one JSONL file so long pulls can be stopped and resumed.
"""

import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://arctic-shift.photon-reddit.com/api"
HEADERS = {"User-Agent": "fa26-1433 research project"}
PAUSE = 3  # seconds to wait after every successful request
PAGE = 100


def http_get_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def get(endpoint, params, fetch=http_get_json, sleep=time.sleep, tries=6):
    """Return the `data` list for one request, retrying errors and rate-limit replies."""
    url = f"{BASE}/{endpoint}?" + urllib.parse.urlencode(params)
    for attempt in range(tries):
        try:
            body = fetch(url)
            if body.get("data") is not None:
                sleep(PAUSE)
                return body["data"]
            print(f"  retry {attempt + 1}: {body.get('error')}")
        except Exception as e:
            print(f"  retry {attempt + 1}: {e}")
        sleep(15 * (attempt + 1))
    raise RuntimeError(f"failed after {tries} tries: {url}")


def iter_window(endpoint, subreddit, after, before, **kw):
    """Yield every item with after < created_utc < before (epoch seconds), oldest first.

    The next page starts one second before the last timestamp seen, so posts sharing a
    timestamp across a page edge are not skipped; ids already yielded are dropped.
    """
    seen = set()
    cursor = after
    while True:
        page = get(endpoint, {"subreddit": subreddit, "after": cursor, "before": before,
                              "limit": PAGE, "sort": "asc"}, **kw)
        new = [x for x in page if x["id"] not in seen]
        for x in new:
            seen.add(x["id"])
            yield x
        if len(page) < PAGE:
            return
        last = int(page[-1]["created_utc"])
        cursor = last - 1 if new and last - 1 > cursor else last


def months(first, last):
    """Inclusive list of "YYYY-MM" strings from first to last."""
    y, m = map(int, first.split("-"))
    out = []
    while f"{y:04d}-{m:02d}" <= last:
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def month_bounds(month):
    """(epoch of the month's first second, epoch of the next month's first second), UTC."""
    y, m = map(int, month.split("-"))
    start = datetime(y, m, 1, tzinfo=timezone.utc)
    end = datetime(y + (m == 12), m % 12 + 1, 1, tzinfo=timezone.utc)
    return int(start.timestamp()), int(end.timestamp())


def fetch_month(endpoint, subreddit, month, out_dir, **kw):
    """Save every item from one subreddit-month to out_dir/subreddit/month.jsonl.

    Skips months already saved. Writes to a .partial file first, so an interrupted
    month is redone on the next run instead of being left half-saved.
    """
    path = Path(out_dir) / subreddit / f"{month}.jsonl"
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    start, end = month_bounds(month)
    tmp = path.with_suffix(".partial")
    with open(tmp, "w") as f:
        for x in iter_window(endpoint, subreddit, start - 1, end, **kw):
            if start <= int(x["created_utc"]) < end:
                f.write(json.dumps(x) + "\n")
    tmp.rename(path)
    return path
```

- [ ] **Step 5: Run the tests and confirm they pass**

Run: `python3 -m pytest tests/test_arctic.py -v`
Expected: 8 passed

- [ ] **Step 6: Smoke-test against the real API**

Run:

```bash
python3 -c "
import sys; sys.path.insert(0, 'code'); import arctic
start, end = arctic.month_bounds('2024-01')
rows = list(arctic.iter_window('posts/search', 'WritingPrompts', start - 1, start + 6 * 3600))
print(len(rows), rows[0]['created_utc'] >= start, len({r['id'] for r in rows}) == len(rows))
print(rows[0].get('_meta'), rows[0]['link_flair_text'])
"
```

Expected: a count above 0, then `True True`, then a `_meta` dict and a flair string. If the API rejects epoch seconds for `after`/`before` or rejects `sort=asc`, the error message says so. In that case, change only the `params` dict in `iter_window` and rerun the unit tests.

- [ ] **Step 7: Commit**

```bash
git add code/arctic.py tests/conftest.py tests/test_arctic.py
git commit -m "Add Arctic Shift client with retries, paging, and monthly caching"
```

---

### Task 2: Find subreddits with an AI flair

**Files:**
- Create: `code/reddit_text.py`
- Create: `code/reddit_subreddits.py`
- Create: `code/find_ai_flair_subreddits.py`
- Create: `tests/test_reddit_text.py`
- Create: `data/hand_coded/README.md`
- Create: `data/hand_coded/ai_flairs.csv` (by hand, Step 7)

**Interfaces:**
- Consumes: `arctic.get`, `arctic.months`, `arctic.month_bounds` (Task 1)
- Produces:
  - `reddit_text.is_ai_text(text: str | None) -> bool`
  - `reddit_text.tally_flairs(samples: Iterable[tuple[str, str | None]]) -> dict[str, dict]` (flair → `{"n", "first_month", "last_month"}`; skips None and empty)
  - `reddit_subreddits.SEED_SUBREDDITS: list[str]`
  - `reddit_subreddits.study_subreddits() -> list[str]` (sorted unique `subreddit` values in `data/hand_coded/ai_flairs.csv`)
  - `reddit_subreddits.approved_flairs() -> dict[str, set[str]]` (subreddit → approved flair texts)
  - `reddit_subreddits.FIRST_MONTH = "2022-01"`, `LAST_MONTH = "2025-12"`

- [ ] **Step 1: Write the failing tests**

`tests/test_reddit_text.py`:

```python
import pytest

import reddit_text


@pytest.mark.parametrize("text", ["AI", "Made by AI", "AI-Generated", ":robot: AI Assisted",
                                  "ChatGPT", "chat gpt", "GPT-4", "A.I. content", "LLM output",
                                  "written with a language model", "ai"])
def test_is_ai_text_matches(text):
    assert reddit_text.is_ai_text(text)


@pytest.mark.parametrize("text", [None, "", "Writing Prompt", "Mail", "Said", "Thai food",
                                  "Domain", "Fairy tale", "Poem", "Critique"])
def test_is_ai_text_rejects(text):
    assert not reddit_text.is_ai_text(text)


def test_tally_flairs_counts_and_dates():
    samples = [("2022-03", "AI"), ("2022-01", "Story"), ("2023-05", "AI"), ("2022-02", None), ("2022-02", "")]
    got = reddit_text.tally_flairs(samples)
    assert got == {"AI": {"n": 2, "first_month": "2022-03", "last_month": "2023-05"},
                   "Story": {"n": 1, "first_month": "2022-01", "last_month": "2022-01"}}
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `python3 -m pytest tests/test_reddit_text.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'reddit_text'`

- [ ] **Step 3: Write `code/reddit_text.py`**

```python
"""Text rules for the Reddit sample: AI keywords and flair tallies."""

import re

# Used only to *find* candidate flairs, rule lines and moderator posts. The final AI-flair
# definition is the hand-approved list in data/hand_coded/ai_flairs.csv.
AI_PATTERN = re.compile(
    r"(?<![a-z])(ai|a\.i\.|artificial intelligence|chat ?gpt|gpt-?\d|llms?|language models?"
    r"|machine[- ]generated)(?![a-z])",
    re.IGNORECASE,
)


def is_ai_text(text):
    return bool(text) and AI_PATTERN.search(text) is not None


def tally_flairs(samples):
    """Map each flair to how often it appears and the first and last month seen."""
    out = {}
    for month, flair in samples:
        if not flair:
            continue
        t = out.setdefault(flair, {"n": 0, "first_month": month, "last_month": month})
        t["n"] += 1
        t["first_month"] = min(t["first_month"], month)
        t["last_month"] = max(t["last_month"], month)
    return out
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `python3 -m pytest tests/test_reddit_text.py -v`
Expected: all passed

- [ ] **Step 5: Write `code/reddit_subreddits.py` and `code/find_ai_flair_subreddits.py`**

`code/reddit_subreddits.py`:

```python
"""Subreddit lists for the Reddit sample."""

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AI_FLAIRS = ROOT / "data" / "hand_coded" / "ai_flairs.csv"
FIRST_MONTH, LAST_MONTH = "2022-01", "2025-12"

# Starting candidates: text-first communities where AI-written posts are plausible.
# Add to this list freely; find_ai_flair_subreddits.py keeps only those with an AI flair.
SEED_SUBREDDITS = [
    "WritingPrompts", "writing", "shortstories", "FanFiction", "HFY", "nosleep", "OCPoetry",
    "Poetry", "poetry_critics", "fantasywriters", "scifiwriting", "KeepWriting",
    "DestructiveReaders", "creativewriting", "Screenwriting", "selfpublish", "copywriting",
    "Blogging", "AmItheAsshole", "AITAH", "tifu", "relationship_advice", "TrueOffMyChest",
    "offmychest", "confession", "Showerthoughts", "LifeProTips", "explainlikeimfive",
    "Teachers", "Professors", "cscareerquestions", "learnprogramming",
]


def approved_flairs():
    """Subreddit -> set of flair texts approved as AI labels."""
    out = {}
    with open(AI_FLAIRS, newline="") as f:
        for row in csv.DictReader(f):
            out.setdefault(row["subreddit"], set()).add(row["flair_text"])
    return out


def study_subreddits():
    return sorted(approved_flairs())
```

`code/find_ai_flair_subreddits.py`:

```python
"""Find seed subreddits that have an AI post flair.

Samples the first 100 posts of every month, 2022-2025, for each seed subreddit, and
tallies their flairs. Raw pages are cached in data/raw/arctic/flair_sample/.

Usage: python3 code/find_ai_flair_subreddits.py
Writes data/derived/flair_inventory.csv (every flair) and data/derived/ai_flairs_draft.csv
(flairs matching AI keywords, to review by hand into data/hand_coded/ai_flairs.csv).
"""

import csv
import json
from pathlib import Path

import arctic
from reddit_subreddits import FIRST_MONTH, LAST_MONTH, ROOT, SEED_SUBREDDITS
from reddit_text import is_ai_text, tally_flairs

CACHE = ROOT / "data" / "raw" / "arctic" / "flair_sample"
DERIVED = ROOT / "data" / "derived"


def sample_month(sub, month):
    path = CACHE / sub / f"{month}.json"
    if path.exists():
        return json.loads(path.read_text())
    start, end = arctic.month_bounds(month)
    page = arctic.get("posts/search", {"subreddit": sub, "after": start - 1, "before": end,
                                       "limit": 100, "sort": "asc"})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(page))
    return page


def main():
    DERIVED.mkdir(parents=True, exist_ok=True)
    inventory = []
    for sub in SEED_SUBREDDITS:
        print(sub)
        samples = [(m, p.get("link_flair_text"))
                   for m in arctic.months(FIRST_MONTH, LAST_MONTH) for p in sample_month(sub, m)]
        for flair, t in sorted(tally_flairs(samples).items()):
            inventory.append({"subreddit": sub, "flair_text": flair, **t, "ai_match": is_ai_text(flair)})
    fields = ["subreddit", "flair_text", "n", "first_month", "last_month", "ai_match"]
    with open(DERIVED / "flair_inventory.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(inventory)
    with open(DERIVED / "ai_flairs_draft.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(r for r in inventory if r["ai_match"])
    print(f"wrote {len(inventory)} flairs; {sum(r['ai_match'] for r in inventory)} match AI keywords")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run it**

This makes about 48 requests per seed subreddit, roughly 2.5 minutes each and 80 minutes for the seed list. Run it in the background:

```bash
nohup python3 code/find_ai_flair_subreddits.py > data/derived/find_ai_flair.log 2>&1 &
```

Expected at the end: `wrote N flairs; K match AI keywords`, where K > 0.

- [ ] **Step 7: Approve flairs by hand**

Write `data/hand_coded/README.md`:

```markdown
# Hand-coded inputs

Small files coded by hand. They are tracked in Git because they cannot be rebuilt from code.

## ai_flairs.csv

Columns: `subreddit,flair_text,notes`. One row per flair that *labels a post as AI-made or
AI-assisted*. Built from `data/derived/ai_flairs_draft.csv`:

- Keep a flair only if it tells readers the post itself was made with AI ("AI", "Made by AI",
  "AI-assisted"). Drop flairs about AI as a *topic* ("AI discussion", "AI news").
- Copy `flair_text` exactly, including emoji codes and capitalization.
- Keep a subreddit only if its approved flairs appear on at least 20 sampled posts in total
  (column `n` of the draft). Fewer than that is too few labeled posts to study.
- Use `notes` for anything unusual, e.g. "flair also used for AI news before 2023-05".

## reddit_rule_dates.csv

See the coding guide added in Task 5.
```

Then build `data/hand_coded/ai_flairs.csv` from the draft using those rules, with the header `subreddit,flair_text,notes`. If no seed subreddit qualifies, add more text subreddits to `SEED_SUBREDDITS` and rerun Step 6. Cached months are not re-downloaded.

- [ ] **Step 8: Check the study list loads**

Run: `python3 -c "import sys; sys.path.insert(0,'code'); import reddit_subreddits as r; print(r.study_subreddits())"`
Expected: the subreddits you kept.

- [ ] **Step 9: Commit**

```bash
git add code/reddit_text.py code/reddit_subreddits.py code/find_ai_flair_subreddits.py \
        tests/test_reddit_text.py data/hand_coded/README.md data/hand_coded/ai_flairs.csv
git commit -m "Find subreddits with an AI post flair and record approved flairs"
```

---

### Task 3: Wayback snapshots of subreddit rules

**Files:**
- Create: `code/wayback.py`
- Create: `code/fetch_rule_snapshots.py`
- Create: `code/extract_rule_snippets.py`
- Create: `tests/test_wayback.py`

**Interfaces:**
- Consumes: `reddit_text.is_ai_text`, `reddit_subreddits.study_subreddits`, `reddit_subreddits.ROOT`, `reddit_subreddits.FIRST_MONTH`, `reddit_subreddits.LAST_MONTH` (Task 2)
- Produces:
  - `wayback.PAGES: dict[str, str]` (page kind → URL template with `{sub}`)
  - `wayback.cdx_url(page_url: str, first_year: int, last_year: int) -> str`
  - `wayback.parse_cdx(body: list) -> list[dict]`
  - `wayback.snapshot_url(timestamp: str, original: str) -> str`
  - `wayback.extract_rule_text(html: str) -> str`
  - `wayback.ai_snippets(text: str) -> list[str]`
  - `wayback.mark_changes(rows: list[dict]) -> list[dict]` (rows sorted by subreddit, kind, timestamp; adds `changed: bool`)
  - Output `data/derived/rule_snippets.csv`: `subreddit,kind,timestamp,snapshot_url,n_chars,snippets,changed`

- [ ] **Step 1: Write the failing tests**

`tests/test_wayback.py`:

```python
import wayback

SIDEBAR = """<html><body><div class="content"><p>AI post title in the feed</p></div>
<div class="side"><div class="md"><p>Welcome!</p><ol><li>Be civil.</li>
<li>AI-generated posts must use the "AI" flair.</li></ol></div></div></body></html>"""

WIKI = """<html><body><div class="wiki-page-content"><div class="md wiki">
<h2>Rules</h2><p>No spam.</p><p>Posts made with ChatGPT should be flaired.</p></div></div></body></html>"""


def test_parse_cdx_skips_header():
    body = [["timestamp", "original", "statuscode"], ["20230101000000", "https://old.reddit.com/r/x/", "200"]]
    assert wayback.parse_cdx(body) == [{"timestamp": "20230101000000",
                                        "original": "https://old.reddit.com/r/x/", "statuscode": "200"}]
    assert wayback.parse_cdx([]) == []


def test_snapshot_url_uses_raw_id_mode():
    assert wayback.snapshot_url("20230101000000", "https://old.reddit.com/r/x/") == \
        "https://web.archive.org/web/20230101000000id_/https://old.reddit.com/r/x/"


def test_cdx_url_asks_for_one_200_capture_per_month():
    url = wayback.cdx_url("old.reddit.com/r/x/", 2021, 2025)
    assert "collapse=timestamp%3A6" in url and "filter=statuscode%3A200" in url and "from=2021" in url


def test_extract_rule_text_reads_sidebar_not_feed():
    text = wayback.extract_rule_text(SIDEBAR)
    assert "Be civil." in text
    assert "feed" not in text


def test_extract_rule_text_reads_wiki():
    assert "No spam." in wayback.extract_rule_text(WIKI)


def test_extract_rule_text_empty_page():
    assert wayback.extract_rule_text("<html><body></body></html>") == ""


def test_ai_snippets():
    assert wayback.ai_snippets(wayback.extract_rule_text(SIDEBAR)) == ['AI-generated posts must use the "AI" flair.']
    assert wayback.ai_snippets(wayback.extract_rule_text(WIKI)) == ["Posts made with ChatGPT should be flaired."]


def test_mark_changes_per_subreddit_and_kind():
    rows = [{"subreddit": "a", "kind": "sidebar", "timestamp": "1", "snippets": ""},
            {"subreddit": "a", "kind": "sidebar", "timestamp": "2", "snippets": "AI ok"},
            {"subreddit": "a", "kind": "sidebar", "timestamp": "3", "snippets": "AI ok"},
            {"subreddit": "a", "kind": "wiki_rules", "timestamp": "1", "snippets": "AI ok"},
            {"subreddit": "b", "kind": "sidebar", "timestamp": "1", "snippets": "AI ok"}]
    assert [r["changed"] for r in wayback.mark_changes(rows)] == [True, True, False, True, True]
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `python3 -m pytest tests/test_wayback.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'wayback'`

- [ ] **Step 3: Write `code/wayback.py`**

```python
"""Wayback Machine helpers: list monthly snapshots of subreddit rule pages and read their rules."""

import json
import time
import urllib.parse
import urllib.request

from bs4 import BeautifulSoup

from reddit_text import is_ai_text

CDX = "https://web.archive.org/cdx/search/cdx"
HEADERS = {"User-Agent": "fa26-1433 research project"}

# old.reddit's front page shows the sidebar, which most subreddits use for rules; the wiki and
# about/rules pages are archived less often but are checked too.
PAGES = {
    "sidebar": "old.reddit.com/r/{sub}/",
    "wiki_rules": "www.reddit.com/r/{sub}/wiki/rules",
    "about_rules": "old.reddit.com/r/{sub}/about/rules",
}
SELECTORS = ["div.side div.md", "div.wiki-page-content div.md", "div.subreddit-rules-page"]


def fetch_text(url, tries=5):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:
            print(f"  retry {attempt + 1}: {e}")
            time.sleep(20 * (attempt + 1))
    raise RuntimeError(f"failed after {tries} tries: {url}")


def cdx_url(page_url, first_year, last_year):
    return CDX + "?" + urllib.parse.urlencode({
        "url": page_url, "output": "json", "fl": "timestamp,original,statuscode",
        "filter": "statuscode:200", "collapse": "timestamp:6", "from": first_year, "to": last_year})


def parse_cdx(body):
    if not body:
        return []
    header, *rows = body
    return [dict(zip(header, r)) for r in rows]


def list_snapshots(page_url, first_year, last_year):
    text = fetch_text(cdx_url(page_url, first_year, last_year))
    return parse_cdx(json.loads(text) if text.strip() else [])


def snapshot_url(timestamp, original):
    """URL of the archived page exactly as captured, without the Wayback toolbar."""
    return f"https://web.archive.org/web/{timestamp}id_/{original}"


def extract_rule_text(html):
    soup = BeautifulSoup(html, "html.parser")
    parts = [el.get_text("\n", strip=True) for sel in SELECTORS for el in soup.select(sel)]
    return "\n".join(p for p in parts if p)


def ai_snippets(text):
    return [line.strip() for line in text.splitlines() if is_ai_text(line)]


def mark_changes(rows):
    """Flag rows whose AI snippets differ from the previous snapshot of the same page."""
    rows = sorted(rows, key=lambda r: (r["subreddit"], r["kind"], r["timestamp"]))
    prev = {}
    for r in rows:
        key = (r["subreddit"], r["kind"])
        r["changed"] = key not in prev or prev[key] != r["snippets"]
        prev[key] = r["snippets"]
    return rows
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `python3 -m pytest tests/test_wayback.py -v`
Expected: 8 passed

- [ ] **Step 5: Write the two scripts**

`code/fetch_rule_snapshots.py`:

```python
"""Download one Wayback snapshot per month of each study subreddit's sidebar and rules pages.

Usage: python3 code/fetch_rule_snapshots.py
Saves raw HTML to data/raw/wayback/<subreddit>/<kind>/<timestamp>.html and an index of
snapshot URLs to data/raw/wayback/index.csv.
"""

import csv
import time

import wayback
from reddit_subreddits import FIRST_MONTH, LAST_MONTH, ROOT, study_subreddits

OUT = ROOT / "data" / "raw" / "wayback"
# Start a year early so a rule already in place in January 2022 still has a dated first appearance.
FIRST_YEAR, LAST_YEAR = int(FIRST_MONTH[:4]) - 1, int(LAST_MONTH[:4])


def main():
    index = []
    for sub in study_subreddits():
        for kind, template in wayback.PAGES.items():
            snaps = wayback.list_snapshots(template.format(sub=sub), FIRST_YEAR, LAST_YEAR)
            print(sub, kind, len(snaps), "snapshots")
            time.sleep(2)
            for s in snaps:
                url = wayback.snapshot_url(s["timestamp"], s["original"])
                path = OUT / sub / kind / f"{s['timestamp']}.html"
                if not path.exists():
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(wayback.fetch_text(url))
                    time.sleep(2)
                index.append({"subreddit": sub, "kind": kind, "timestamp": s["timestamp"], "snapshot_url": url})
    with open(OUT / "index.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["subreddit", "kind", "timestamp", "snapshot_url"])
        w.writeheader()
        w.writerows(index)
    print(f"indexed {len(index)} snapshots")


if __name__ == "__main__":
    main()
```

`code/extract_rule_snippets.py`:

```python
"""Pull AI-related rule lines out of saved Wayback snapshots.

Usage: python3 code/extract_rule_snippets.py  (after code/fetch_rule_snapshots.py)
Writes data/derived/rule_snippets.csv; rows with changed=True are where to look when dating rules.
"""

import csv

import wayback
from reddit_subreddits import ROOT

RAW = ROOT / "data" / "raw" / "wayback"
OUT = ROOT / "data" / "derived" / "rule_snippets.csv"


def main():
    rows = []
    with open(RAW / "index.csv", newline="") as f:
        for r in csv.DictReader(f):
            html = (RAW / r["subreddit"] / r["kind"] / f"{r['timestamp']}.html").read_text()
            text = wayback.extract_rule_text(html)
            rows.append({**r, "n_chars": len(text), "snippets": " || ".join(wayback.ai_snippets(text))})
    rows = wayback.mark_changes(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["subreddit", "kind", "timestamp", "snapshot_url",
                                          "n_chars", "snippets", "changed"])
        w.writeheader()
        w.writerows(rows)
    empty = sum(r["n_chars"] == 0 for r in rows)
    print(f"wrote {len(rows)} rows; {empty} snapshots had no rule text")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run both and check the extraction on real pages**

```bash
python3 code/fetch_rule_snapshots.py
python3 code/extract_rule_snippets.py
```

Expected: `indexed N snapshots`, then `wrote N rows; E snapshots had no rule text`. If E is more than about a quarter of N, open two of the empty HTML files. Find the element holding the rules, add its CSS selector to `wayback.SELECTORS`, add a fixture test in the same style as `test_extract_rule_text_reads_wiki`, and rerun `extract_rule_snippets.py`. That script works only from cached files, so it is fast.

- [ ] **Step 7: Commit**

```bash
git add code/wayback.py code/fetch_rule_snapshots.py code/extract_rule_snippets.py tests/test_wayback.py
git commit -m "Download Wayback snapshots of subreddit rules and extract AI-related lines"
```

---

### Task 4: Pull all posts and comments

**Files:**
- Create: `code/fetch_reddit_dumps.py`
- Modify: `data/raw/README.md` (append source notes)

**Interfaces:**
- Consumes: `arctic.get`, `arctic.fetch_month`, `arctic.months` (Task 1); `reddit_subreddits.study_subreddits`, `FIRST_MONTH`, `LAST_MONTH`, `ROOT` (Task 2)
- Produces:
  - `data/raw/arctic/posts/<subreddit>/<YYYY-MM>.jsonl` (one Arctic Shift post object per line, all fields)
  - `data/raw/arctic/comments/<subreddit>/<YYYY-MM>.jsonl`
  - `data/derived/reddit_volume.csv`: `subreddit,kind,count`

- [ ] **Step 1: Write `code/fetch_reddit_dumps.py`**

```python
"""Pull every post or comment in the study subreddits, one month at a time.

Usage:
  python3 code/fetch_reddit_dumps.py size        # count posts and comments first
  python3 code/fetch_reddit_dumps.py posts
  python3 code/fetch_reddit_dumps.py comments
Months already saved are skipped, so a stopped run can simply be restarted.
"""

import csv
import sys

import arctic
from reddit_subreddits import FIRST_MONTH, LAST_MONTH, ROOT, study_subreddits

RAW = ROOT / "data" / "raw" / "arctic"
ENDPOINT = {"posts": "posts/search", "comments": "comments/search"}


def size():
    rows = []
    for sub in study_subreddits():
        for kind, endpoint in ENDPOINT.items():
            data = arctic.get(endpoint + "/aggregate", {
                "aggregate": "created_utc", "frequency": "month", "subreddit": sub,
                "after": f"{FIRST_MONTH}-01", "before": f"{int(LAST_MONTH[:4]) + 1}-01-01"})
            rows.append({"subreddit": sub, "kind": kind, "count": sum(int(d["count"]) for d in data)})
            print(rows[-1])
    out = ROOT / "data" / "derived" / "reddit_volume.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["subreddit", "kind", "count"])
        w.writeheader()
        w.writerows(rows)
    for kind in ENDPOINT:
        n = sum(r["count"] for r in rows if r["kind"] == kind)
        print(f"{kind}: {n:,} items, about {n / 100 * arctic.PAUSE / 3600:.1f} hours to pull")


def pull(kind):
    for sub in study_subreddits():
        for month in arctic.months(FIRST_MONTH, LAST_MONTH):
            path = arctic.fetch_month(ENDPOINT[kind], sub, month, RAW / kind)
            print(sub, month, sum(1 for _ in open(path)))


if __name__ == "__main__":
    cmd = sys.argv[1]
    size() if cmd == "size" else pull(cmd)
```

- [ ] **Step 2: Measure the volume and decide**

Run: `python3 code/fetch_reddit_dumps.py size`
Expected: one line per subreddit and kind, then two totals with estimated hours.

**Decision gate:** Comments are needed for the reader-side call-out outcome (`score` and `num_comments` come with the posts). If the comment pull is estimated at more than 24 hours, do not pull comments through the API. Stop and plan a separate step that downloads the per-subreddit Reddit dumps from Academic Torrents (`.zst` files, which need `pip install zstandard`). Posts still come through the API. Record the choice in GitHub issue #2.

- [ ] **Step 3: Pull posts (and comments, if the gate allows) in the background**

```bash
nohup python3 code/fetch_reddit_dumps.py posts > data/derived/fetch_posts.log 2>&1 &
# after posts finish, and only if the decision gate allows:
nohup python3 code/fetch_reddit_dumps.py comments > data/derived/fetch_comments.log 2>&1 &
```

Check on progress with `tail data/derived/fetch_posts.log`. If the run dies, rerun the same command and it resumes at the first unsaved month.

- [ ] **Step 4: Check that nothing is half-saved**

Run: `find data/raw/arctic -name '*.partial' | wc -l; ls data/raw/arctic/posts/*/ | grep -c jsonl`
Expected: `0` partial files, and a jsonl count of 48 × the number of study subreddits.

- [ ] **Step 5: Document the source**

Append to `data/raw/README.md`:

```markdown
## Arctic Shift (Reddit posts and comments)

- `arctic/flair_sample/`, `arctic/posts/`, `arctic/comments/`: from the Arctic Shift API,
  https://arctic-shift.photon-reddit.com, via `code/find_ai_flair_subreddits.py` and
  `code/fetch_reddit_dumps.py`. Accessed <write the dates you ran the pulls>. Requests need a
  User-Agent header. Posts are stored as first retrieved; `_meta.note == "no_2nd_retrieval"`
  means the post was not re-fetched later, so later flair changes are missing.

## Wayback Machine (subreddit rules)

- `wayback/`: monthly captures of each study subreddit's old.reddit sidebar, wiki rules page and
  about/rules page, via `code/fetch_rule_snapshots.py` and the CDX API
  (https://web.archive.org/cdx/search/cdx). `wayback/index.csv` gives each capture's URL.
```

- [ ] **Step 6: Commit**

```bash
git add code/fetch_reddit_dumps.py data/raw/README.md
git commit -m "Pull study-subreddit posts and comments month by month"
```

---

### Task 5: Hand-code the rule dates

**Files:**
- Create: `code/list_mod_ai_posts.py`
- Create: `code/check_rule_dates.py`
- Create: `tests/test_check_rule_dates.py`
- Modify: `data/hand_coded/README.md` (replace the `reddit_rule_dates.csv` section)
- Create: `data/hand_coded/reddit_rule_dates.csv` (by hand)

**Interfaces:**
- Consumes: `reddit_text.is_ai_text`, `reddit_subreddits.study_subreddits`, `ROOT` (Task 2); `data/derived/rule_snippets.csv` (Task 3); `data/raw/arctic/posts/` (Task 4)
- Produces:
  - `list_mod_ai_posts.is_mod_ai_post(post: dict) -> bool`
  - `check_rule_dates.problems(rows: list[dict], study: list[str]) -> list[str]` (empty list = file is OK)
  - `check_rule_dates.load_rule_dates() -> dict[str, dict]` (subreddit → row with `label_start` and `mandatory_start` as `"YYYY-MM-DD"`, or `""` for never)
  - `data/derived/reddit_mod_ai_posts.csv`: `subreddit,created_utc,date,title,permalink`

- [ ] **Step 1: Write the failing tests**

`tests/test_check_rule_dates.py`:

```python
from check_rule_dates import problems
from list_mod_ai_posts import is_mod_ai_post

GOOD = {"subreddit": "a", "label_start": "2023-02-01", "mandatory_start": "2024-01-15",
        "label_source": "https://web.archive.org/web/x", "mandatory_source": "https://web.archive.org/web/y",
        "notes": ""}


def test_good_file_has_no_problems():
    assert problems([GOOD], ["a"]) == []


def test_never_mandatory_is_allowed():
    assert problems([{**GOOD, "mandatory_start": "", "mandatory_source": ""}], ["a"]) == []


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
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `python3 -m pytest tests/test_check_rule_dates.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'check_rule_dates'`

- [ ] **Step 3: Write the two scripts**

`code/list_mod_ai_posts.py`:

```python
"""List moderator posts that mention AI, as evidence for dating subreddit AI rules.

Usage: python3 code/list_mod_ai_posts.py  (after code/fetch_reddit_dumps.py posts)
Writes data/derived/reddit_mod_ai_posts.csv.
"""

import csv
import json
from datetime import datetime, timezone

from reddit_subreddits import ROOT, study_subreddits
from reddit_text import is_ai_text

POSTS = ROOT / "data" / "raw" / "arctic" / "posts"
OUT = ROOT / "data" / "derived" / "reddit_mod_ai_posts.csv"


def is_mod_ai_post(post):
    by_mod = post.get("distinguished") == "moderator" or post.get("stickied") is True
    return by_mod and is_ai_text(f"{post.get('title', '')} {post.get('selftext', '')}")


def main():
    rows = []
    for sub in study_subreddits():
        for path in sorted((POSTS / sub).glob("*.jsonl")):
            for line in open(path):
                p = json.loads(line)
                if is_mod_ai_post(p):
                    ts = int(p["created_utc"])
                    rows.append({"subreddit": sub, "created_utc": ts,
                                 "date": datetime.fromtimestamp(ts, timezone.utc).date().isoformat(),
                                 "title": p["title"], "permalink": "https://www.reddit.com" + p["permalink"]})
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["subreddit", "created_utc", "date", "title", "permalink"])
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} moderator posts mentioning AI")


if __name__ == "__main__":
    main()
```

`code/check_rule_dates.py`:

```python
"""Check data/hand_coded/reddit_rule_dates.csv for errors.

Usage: python3 code/check_rule_dates.py   (prints problems; exits 1 if there are any)
"""

import csv
import sys
from datetime import date

from reddit_subreddits import ROOT, study_subreddits

RULE_DATES = ROOT / "data" / "hand_coded" / "reddit_rule_dates.csv"


def _parse(value):
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def problems(rows, study):
    out = []
    seen = set()
    for r in rows:
        sub = r["subreddit"]
        seen.add(sub)
        if sub not in study:
            out.append(f"{sub}: not a study subreddit (not in ai_flairs.csv)")
        label = _parse(r["label_start"])
        if label is None:
            out.append(f"{sub}: label_start {r['label_start']!r} is not YYYY-MM-DD")
        if not r["label_source"]:
            out.append(f"{sub}: label_source is empty")
        if r["mandatory_start"]:
            mand = _parse(r["mandatory_start"])
            if mand is None:
                out.append(f"{sub}: mandatory_start {r['mandatory_start']!r} is not YYYY-MM-DD")
            elif label and mand < label:
                out.append(f"{sub}: mandatory_start is before label_start")
            if not r["mandatory_source"]:
                out.append(f"{sub}: mandatory_source is empty")
    out += [f"{sub}: missing from reddit_rule_dates.csv" for sub in study if sub not in seen]
    return out


def load_rule_dates():
    with open(RULE_DATES, newline="") as f:
        return {r["subreddit"]: r for r in csv.DictReader(f)}


if __name__ == "__main__":
    found = problems(list(load_rule_dates().values()), study_subreddits())
    print("\n".join(found) or "reddit_rule_dates.csv: OK")
    sys.exit(1 if found else 0)
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `python3 -m pytest tests/test_check_rule_dates.py -v`
Expected: 4 passed

- [ ] **Step 5: Write the coding guide**

Replace the `## reddit_rule_dates.csv` section of `data/hand_coded/README.md` with:

```markdown
## reddit_rule_dates.csv

Columns: `subreddit,label_start,mandatory_start,label_source,mandatory_source,notes`.
One row per subreddit in `ai_flairs.csv`. Dates are `YYYY-MM-DD` in UTC.

**label_start**: the first date posters could label a post as AI. Take the *earliest* of:
1. the first Wayback snapshot whose rules mention an AI flair or tag
   (`data/derived/rule_snippets.csv`, rows with `changed=True`);
2. a moderator post announcing the flair (`data/derived/reddit_mod_ai_posts.csv`);
3. the first month an approved AI flair appears (`first_month` in `data/derived/flair_inventory.csv`;
   use the 1st of that month).

**mandatory_start**: the first date the rules *require* the label, i.e. say "must", "required" or
"will be removed" for unlabeled AI posts. Leave it empty if labeling never became required. Wording
like "please", "should" or "encouraged" is still voluntary. A full *ban* on AI posts is not a
labeling rule: note the ban date in `notes`.

When a snapshot is the evidence, date the change to the snapshot's date, because the true change
happened between it and the previous snapshot. Write the gap in `notes`, e.g.
"changed between 2023-03-02 and 2023-04-11 snapshots". A moderator announcement gives an exact
date and takes priority.

**label_source / mandatory_source**: the snapshot URL or announcement permalink the date came from.
```

- [ ] **Step 6: Code the dates**

```bash
python3 code/list_mod_ai_posts.py
```

Then, for each study subreddit, read its rows in `rule_snippets.csv` where `changed=True`, its rows in `reddit_mod_ai_posts.csv`, and its AI flair's `first_month` in `flair_inventory.csv`. Fill in `data/hand_coded/reddit_rule_dates.csv` using the guide. Open the source URL each time to confirm the wording.

- [ ] **Step 7: Check the file**

Run: `python3 code/check_rule_dates.py`
Expected: `reddit_rule_dates.csv: OK`

- [ ] **Step 8: Count treated and control subreddits (DiD feasibility)**

Run:

```bash
python3 -c "
import sys; sys.path.insert(0, 'code')
from check_rule_dates import load_rule_dates
r = load_rule_dates()
print('switch to mandatory:', sum(1 for v in r.values() if v['mandatory_start']))
print('stay voluntary:     ', sum(1 for v in r.values() if not v['mandatory_start']))
"
```

Record both counts in GitHub issue #2. The main DiD needs several switching subreddits and at least a few that stay voluntary. With only 2–3 switchers, clustered standard errors are unreliable: use a wild cluster bootstrap, or lead with the `label_start` fallback (see Spec).

- [ ] **Step 9: Commit**

```bash
git add code/list_mod_ai_posts.py code/check_rule_dates.py tests/test_check_rule_dates.py \
        data/hand_coded/README.md data/hand_coded/reddit_rule_dates.csv
git commit -m "Hand-code when each subreddit's AI label started and became mandatory"
```

---

### Task 6: Build the cleaned post file

**Files:**
- Modify: `code/reddit_text.py` (add `word_count`, `text_status`, `keep_post`, `period`, `MIN_WORDS`)
- Modify: `tests/test_reddit_text.py` (add tests)
- Create: `code/build_reddit_posts.py`
- Modify: `README.md` (script order)

**Interfaces:**
- Consumes: `reddit_subreddits.approved_flairs`, `study_subreddits`, `ROOT` (Task 2); `check_rule_dates.load_rule_dates` (Task 5); `data/raw/arctic/posts/` (Task 4)
- Produces:
  - `reddit_text.MIN_WORDS: int`
  - `reddit_text.word_count(text: str) -> int`
  - `reddit_text.text_status(post: dict) -> str` (`"ok"`, `"no_text"`, `"too_short"`, `"not_text_post"` or `"automod"`)
  - `reddit_text.keep_post(post: dict) -> bool` (`text_status(post) == "ok"`)
  - `reddit_text.period(created_utc: int, label_start: str, mandatory_start: str) -> str` (`"pre"`, `"voluntary"` or `"mandatory"`; empty strings mean never)
  - `data/derived/reddit_posts.parquet` with columns: `id, subreddit, created_utc, month, author, title, selftext, n_words, link_flair_text, ai_flair, period, removed, score, num_comments, retrieved_on, flair_lag_hours, meta_note`
  - `data/derived/reddit_post_filter_counts.csv`: `subreddit,period,text_status,n`

- [ ] **Step 1: Check Pangram's minimum text length**

Look up Pangram's API documentation for the minimum number of words or characters it scores reliably. Set `MIN_WORDS` in Step 4 to that number, converting characters to words at about 5 characters per word. If the docs give no minimum, use 50. Record the source in a comment next to the constant.

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_reddit_text.py`:

```python
from datetime import datetime, timezone


def ts(day):
    return int(datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp())


def post(**kw):
    base = {"is_self": True, "selftext": "word " * 1000, "author": "someone", "removed_by_category": None}
    return {**base, **kw}


def test_word_count():
    assert reddit_text.word_count("one two  three\nfour") == 4
    assert reddit_text.word_count("") == 0


def test_text_status():
    assert reddit_text.text_status(post()) == "ok"
    assert reddit_text.text_status(post(is_self=False)) == "not_text_post"
    assert reddit_text.text_status(post(selftext="[removed]")) == "no_text"
    assert reddit_text.text_status(post(selftext="[deleted]")) == "no_text"
    assert reddit_text.text_status(post(selftext="")) == "no_text"
    assert reddit_text.text_status(post(selftext="too short")) == "too_short"
    assert reddit_text.text_status(post(author="AutoModerator")) == "automod"


def test_removed_post_with_surviving_text_is_kept():
    assert reddit_text.keep_post(post(removed_by_category="moderator"))


def test_period():
    label, mand = "2023-03-01", "2024-01-15"
    assert reddit_text.period(ts("2023-02-28T23:59:59"), label, mand) == "pre"
    assert reddit_text.period(ts("2023-03-01T00:00:00"), label, mand) == "voluntary"
    assert reddit_text.period(ts("2024-01-14T23:59:59"), label, mand) == "voluntary"
    assert reddit_text.period(ts("2024-01-15T00:00:00"), label, mand) == "mandatory"


def test_period_never_mandatory():
    assert reddit_text.period(ts("2025-06-01T00:00:00"), "2023-03-01", "") == "voluntary"
```

- [ ] **Step 3: Run the tests and confirm the new ones fail**

Run: `python3 -m pytest tests/test_reddit_text.py -v`
Expected: the new tests FAIL with `AttributeError: module 'reddit_text' has no attribute 'word_count'`, and the Task 2 tests still pass

- [ ] **Step 4: Add the functions to `code/reddit_text.py`**

Append:

```python
from datetime import date, datetime, timezone

MIN_WORDS = 50  # Pangram's minimum for reliable scores; source: <URL from Task 6 Step 1>
NO_TEXT = {"", "[removed]", "[deleted]"}


def word_count(text):
    return len(text.split())


def text_status(post):
    """Why a post is or is not usable for text analysis.

    Posts removed by moderators are kept when their text survives: moderators remove unlabeled
    AI posts, so dropping them would overstate how often AI posts are labeled.
    """
    if not post.get("is_self"):
        return "not_text_post"
    if post.get("author") == "AutoModerator":
        return "automod"
    text = (post.get("selftext") or "").strip()
    if text in NO_TEXT:
        return "no_text"
    if word_count(text) < MIN_WORDS:
        return "too_short"
    return "ok"


def keep_post(post):
    return text_status(post) == "ok"


def _day_start(day):
    return int(datetime.combine(date.fromisoformat(day), datetime.min.time(), timezone.utc).timestamp())


def period(created_utc, label_start, mandatory_start):
    """Labeling period of a post; a rule takes effect at 00:00 UTC on its start date."""
    if not label_start or created_utc < _day_start(label_start):
        return "pre"
    if mandatory_start and created_utc >= _day_start(mandatory_start):
        return "mandatory"
    return "voluntary"
```

Move the new `from datetime import ...` line up to sit with `import re` at the top of the file.

- [ ] **Step 5: Run the tests and confirm they pass**

Run: `python3 -m pytest tests -v`
Expected: all tests in all four files pass

- [ ] **Step 6: Write `code/build_reddit_posts.py`**

```python
"""Build the cleaned Reddit post file used for Pangram scoring and the disclosure regression.

Usage: python3 code/build_reddit_posts.py
  (after fetch_reddit_dumps.py posts and a passing check_rule_dates.py)
Writes data/derived/reddit_posts.parquet and data/derived/reddit_post_filter_counts.csv,
and prints the share of posts with an AI flair by subreddit and period.
"""

import json
from collections import Counter
from datetime import datetime, timezone

import pandas as pd

from check_rule_dates import load_rule_dates
from reddit_subreddits import ROOT, approved_flairs, study_subreddits
from reddit_text import period, text_status, word_count

POSTS = ROOT / "data" / "raw" / "arctic" / "posts"
DERIVED = ROOT / "data" / "derived"


def post_row(p, flairs, rule):
    ts = int(p["created_utc"])
    flair = (p.get("link_flair_text") or "").strip()
    return {
        "id": p["id"], "subreddit": p["subreddit"], "created_utc": ts,
        "month": datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m"),
        "author": p.get("author"), "title": p.get("title", ""), "selftext": p["selftext"],
        "n_words": word_count(p["selftext"]), "link_flair_text": flair, "ai_flair": flair in flairs,
        "period": period(ts, rule["label_start"], rule["mandatory_start"]),
        "removed": p.get("removed_by_category") is not None,
        "score": p.get("score"), "num_comments": p.get("num_comments"),
        "retrieved_on": p.get("retrieved_on"),
        "flair_lag_hours": (p["retrieved_on"] - ts) / 3600 if p.get("retrieved_on") else None,
        "meta_note": (p.get("_meta") or {}).get("note"),
    }


def main():
    flairs, rules = approved_flairs(), load_rule_dates()
    rows, filtered = [], Counter()
    for sub in study_subreddits():
        for path in sorted((POSTS / sub).glob("*.jsonl")):
            for line in open(path):
                p = json.loads(line)
                status = text_status(p)
                per = period(int(p["created_utc"]), rules[sub]["label_start"], rules[sub]["mandatory_start"])
                filtered[(sub, per, status)] += 1
                if status == "ok":
                    rows.append(post_row(p, flairs[sub], rules[sub]))
    df = pd.DataFrame(rows)
    df.to_parquet(DERIVED / "reddit_posts.parquet", index=False)
    pd.DataFrame([{"subreddit": s, "period": per, "text_status": st, "n": n}
                  for (s, per, st), n in sorted(filtered.items())]).to_csv(
        DERIVED / "reddit_post_filter_counts.csv", index=False)

    print(f"kept {len(df):,} of {sum(filtered.values()):,} posts")
    print(df.groupby(["subreddit", "period"]).agg(posts=("id", "size"), ai_flair_share=("ai_flair", "mean"),
                                                  removed_share=("removed", "mean")).round(3))
    print("share stored only as first retrieved:",
          round((df["meta_note"] == "no_2nd_retrieval").mean(), 3))


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: Run it**

Run: `python3 code/build_reddit_posts.py`
Expected: `kept N of M posts`, a table by subreddit and period, and the first-retrieval share. Sanity check: in subreddits with a `mandatory_start`, `ai_flair_share` should be higher in the mandatory period than in the voluntary one. If it isn't, re-check that subreddit's flair approvals and rule dates before going further.

- [ ] **Step 8: Check for flairs added after posting (Review Focus 1)**

Run:

```bash
python3 -c "
import pandas as pd
df = pd.read_parquet('data/derived/reddit_posts.parquet')
s = df[df.period.isin(['voluntary', 'mandatory'])].groupby('period').sample(25, random_state=1)
s[['subreddit', 'period', 'id', 'link_flair_text']].assign(url='https://www.reddit.com/comments/' + s.id).to_csv('data/derived/flair_recheck.csv', index=False)
"
```

Open each URL in `data/derived/flair_recheck.csv` and write down the post's flair today. The sample covers both periods because the DiD compares them: if late flairs are missed more often in one period, β is biased. If more than 1 of the 25 in either period now shows an AI flair that the stored data lacks, flair is often added after posting. Record that in GitHub issue #2, because the disclosure measure then needs a later re-fetch of flairs. That re-fetch would be a separate plan.

- [ ] **Step 9: Document the run order**

Replace the "Reproducing the project" section of `README.md` with:

```markdown
## Reproducing the project

Python 3.13 with pandas, pyarrow, beautifulsoup4 and pytest. Run tests with `python3 -m pytest tests`.

Reddit sample, in order. Steps marked *by hand* edit files in `data/hand_coded/`.

1. `python3 code/find_ai_flair_subreddits.py`, then *by hand*: approve flairs into `ai_flairs.csv`
2. `python3 code/fetch_rule_snapshots.py`
3. `python3 code/extract_rule_snippets.py`
4. `python3 code/fetch_reddit_dumps.py size`, then `... posts` and `... comments`
5. `python3 code/list_mod_ai_posts.py`, then *by hand*: code `reddit_rule_dates.csv`
6. `python3 code/check_rule_dates.py`
7. `python3 code/build_reddit_posts.py`

Earlier exploratory scripts: `code/fetch_flair_counts.py`, then `code/plot_wallpaper_flair.py`.
```

- [ ] **Step 10: Commit**

```bash
git add code/reddit_text.py tests/test_reddit_text.py code/build_reddit_posts.py README.md
git commit -m "Build cleaned Reddit post file tagged by labeling period"
```
