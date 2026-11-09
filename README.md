# Research project title

Replace this text with a one-sentence description of the research question.

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
8. Download the AIRules longitudinal and rules sets (github.com/sTechLab/AIRules, Git LFS) into `data/raw/airules/`,
   then `python3 code/select_controls.py` (matched control subreddits for posts per month)
9. `python3 code/analyze_reddit_did.py` (baseline event studies, figures in `output/`)

AI-ban event study (needs only the AIRules download from step 8; no hand coding):
`python3 code/build_ban_sample.py` (bans dated from Reddit's rule timestamps, comparison subreddits and their
monthly post counts), then `python3 code/analyze_ban_did.py` (stacked event study, figure and estimates in `output/`).
AI share of text posts around the bans: `python3 code/sample_ban_text.py screen` (which subreddits post mostly
text), `python3 code/sample_ban_text.py sample` (frozen sample of random days before and after each ban, and before
ChatGPT), then `python3 code/score_pangram.py` (open Pangram; accept the model's terms on Hugging Face first).

Substack sample (branch `substack-pipeline`). `code/substack.py` reads Substack's public JSON endpoints
(unofficial; the archive pages by cursor, which the substack-api package does not yet handle).
`python3 code/substack_pilot.py` draws the pilot posts into `data/hand_coded/substack_pilot.csv`, then *by hand*:
open each `reader_url` logged in, run "Scan for AI text" and fill in the blank columns (see the script's docstring).
`python3 code/check_substack_pilot.py` checks the filled sheet and tabulates status by window and time per post.
Full sample (not yet run; waits on the terms-of-service question): `python3 code/build_substack_frame.py list`
snapshots the category listings, `... archive` draws publications active before the launch and saves their post
lists. `python3 code/substack_text.py IDS.csv OUT.parquet` fetches post text in the format the Pangram scorers read.

Search for more study subreddits: `python3 code/find_label_rule_subreddits.py`, then
`python3 code/find_ai_flair_subreddits.py data/derived/airules_label_candidates.csv voluntary,switcher,ban`.
Then `python3 code/build_expansion_review.py` and read `data/derived/expansion_review.md`; approved subreddits
go into `ai_flairs.csv` and through steps 2-7 like the original ones.

Earlier exploratory scripts: `code/fetch_flair_counts.py`, then `code/plot_wallpaper_flair.py`.

## Repository structure

| Directory | Purpose |
|---|---|
| `code/` | Scripts used to acquire, clean, analyze, and visualize data |
| `data/raw/` | Original source data; ignored by Git unless explicitly allowed |
| `data/derived/` | Data created by the project's code; ignored by Git unless explicitly allowed |
| `output/` | Generated figures, tables, and other results |
| `paper/` | Paper source files and rendered drafts |

## Working practices

- Keep the `main` branch in a usable state.
- Use GitHub issues to record consequential tasks, questions, and decisions.
- Use short-lived branches to test important alternatives, then record the conclusion in the related issue.
- Commit small, coherent changes with descriptive messages.
- Never commit passwords, API keys, restricted data, or personally identifiable information.
- Update this README whenever the reproduction steps or directory structure change.
