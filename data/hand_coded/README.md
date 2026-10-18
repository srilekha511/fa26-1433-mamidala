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
