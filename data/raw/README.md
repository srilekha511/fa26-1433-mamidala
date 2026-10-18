# Raw data

Store original, unmodified source data here. These files are ignored by Git by default. Document each source, access date, and any instructions needed to obtain the data.

## Arctic Shift (Reddit posts and comments)

- `arctic/flair_sample/`, `arctic/posts/`, `arctic/comments/`: from the Arctic Shift API,
  https://arctic-shift.photon-reddit.com, via `code/find_ai_flair_subreddits.py` and
  `code/fetch_reddit_dumps.py`. Flair sample pulled 2026-10-06; add the dates of the posts and comments pulls when they run. Requests need a
  User-Agent header. Capture timing changes in mid-2023: earlier posts were archived weeks or
  months after posting (after most removals and flair edits); from about July 2023 posts were
  captured within seconds and usually re-captured about a day later (`_meta.retrieved_2nd_on`).
  Posts with `_meta.note == "no_2nd_retrieval"` were never re-captured, so flair added later is
  missing. `build_reddit_posts.py` records this as the `regime` column.

## Wayback Machine (subreddit rules)

- `wayback/`: monthly captures of each study subreddit's old.reddit sidebar, wiki rules page and
  about/rules page, via `code/fetch_rule_snapshots.py` and the CDX API
  (https://web.archive.org/cdx/search/cdx). `wayback/index.csv` gives each capture's URL.
