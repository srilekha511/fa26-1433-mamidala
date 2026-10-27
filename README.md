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

Search for more study subreddits: `python3 code/find_label_rule_subreddits.py`, then
`python3 code/find_ai_flair_subreddits.py data/derived/airules_label_candidates.csv voluntary,switcher,ban`.

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
