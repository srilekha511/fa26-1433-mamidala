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
  For the AIRules expansion (`code/build_expansion_review.py`), the 20 applies to the estimated total
  of flaired posts, scaled up from each month's sample, and the subreddit also needs a median of at
  least 30 posts a month since 2023 and a flair that appears by 2025-06.
- Use `notes` for anything unusual, e.g. "flair also used for AI news before 2023-05".

## reddit_rule_dates.csv

Columns: `subreddit,group,label_start,mandatory_start,label_source,mandatory_source,mandatory_start_loose,ban_start,notes`.
One row per subreddit in `ai_flairs.csv`. Dates are `YYYY-MM-DD` in UTC.

**label_start**: the first date posters could label a post as AI. Take the *earliest* of:
1. the first Wayback snapshot whose rules mention an AI flair or tag
   (`data/derived/rule_snippets.csv`, rows with `changed=True`);
2. a moderator post announcing the flair (`data/derived/reddit_mod_ai_posts.csv`);
3. the date of the first post in the full post download that carries an approved AI flair
   (source: `first flaired post <id>`).

**mandatory_start**: the first date the rules *require* the label, i.e. say "must", "required" or
"will be removed" for unlabeled AI posts. Leave it empty if labeling never became required. Wording
like "please", "should" or "encouraged" is still voluntary. A full *ban* on AI posts is not a
labeling rule: note the ban date in `notes`.

When a snapshot is the evidence, date the change to the snapshot's date, because the true change
happened between it and the previous snapshot. Write the gap in `notes`, e.g.
"changed between 2023-03-02 and 2023-04-11 snapshots". A moderator announcement gives an exact
date and takes priority.

**mandatory_start_loose**: a looser reading for robustness. Also counts a plain instruction in the
subreddit's rules list ("Tag AI posts using the flair", "select the AI Generated flair") with no
"must" or removal wording. Equal to `mandatory_start` when the strict wording is present.

**ban_start**: the first date AI posts are banned outright (or confined to a megathread), from a moderator
announcement. Empty if never. A comparison subreddit stops counting from this date, since its labeled
share no longer reflects voluntary labeling.

**group**: how the rule changed, which decides each subreddit's role in the design.
- `switcher`: a voluntary period, then a mandatory rule (`mandatory_start` set). These are the treated units.
- `mandatory_at_intro`: the label arrived with a rule requiring it (or within days), so there is no voluntary
  period. Also used when the rule is a plain instruction from day one that fails the strict wording test.
- `voluntary_throughout`: never required in 2022-2025. These are the comparison units for the labeled share.
- `unclear`: the evidence cannot place the start of the requirement. Kept out of the treated and comparison groups.

Read moderator announcements (`data/derived/reddit_mod_ai_posts.csv`) in full before trusting a sidebar
snapshot: old.reddit sidebars often lag the rules by months.

**label_source / mandatory_source**: the snapshot URL or announcement permalink the date came from.
