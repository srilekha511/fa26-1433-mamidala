# Draft: Substack sections (data, method, results)

<!-- First draft for the November 18 revised draft. Section numbers follow paper/outline.md (3.5 data, 4.5
method, 6 results). Every number comes from python3 code/analyze_substack_sample.py on the substack-pipeline
branch (output/substack_off_shares.csv, substack_publications.csv, substack_estimates.csv,
substack_api_estimates.csv), run on data/hand_coded/substack_sample_deep.csv (draw 1 coded 2026-11-08 and
2026-11-11, draw 2 coded 2026-11-12) and data/derived/substack_off_scores.csv (Pangram API, pangram-4.1, scored
2026-11-12 by code/score_substack_off.py). Reader side (6.4): code/analyze_substack_readers.py on engagement
and comments fetched 2026-11-13 (output/substack_readers_estimates.csv, substack_readers_summary.csv); the 9
call-out pattern matches are coded in data/hand_coded/substack_callout_codes.csv (Claude, reviewed by the author 2026-11-13). The post-level "71 mostly-AI posts" counts and category figures in 6.2
were computed directly from these files and are not yet written to output/. Publications are not named next to
API scores of posts their authors withheld from scanning; see the note in 6.4. -->

## 3.5 Substack posts and their detection status

On July 21, 2026, Substack added Pangram's AI detector to its reader. A logged-in reader can scan any post of
at least 100 words published from that date on. The scan reports the share of the text that is AI-generated,
AI-assisted and human-written, and only the reader who runs it sees the result. Authors can turn detection off
for a post, and the reader then sees "An AI detection result is not available for this content." Authors can
also add a "How I make this" note, which the reader sees in the same popup whether detection is on or off.

Substack's public data do not record whether detection is on, so I coded it by hand in the logged-in reader. I
drew publications from Substack's own category listings for six categories (Technology, U.S. Politics, Finance,
Culture, Health & Wellness and Fiction), 11 per category, in a fixed random order within each listing page.
Drawing from the listings, not from searches, keeps writers who discuss the detector from being oversampled.
From each publication I drew free newsletter posts of at least 100 words in three windows: July 21 to August,
September and October. The first draw took one post per window (169 posts from 66 publications). A second draw
took the next post per window in the same random order for every publication (144 posts). The second draw gives
every publication the same number of extra chances to show a mix of posts with detection on and off. Some
publications have no second free post in a window, so the total is 313 posts rather than 396. For each post I
recorded whether it can be scanned, the three scan percentages when it can, and the text of any author's note.

Detection status is recorded on the day it was checked (November 8 to 12), not the day the post was published,
because an author can turn detection off for old posts at any time. For 6 of the 79 unavailable posts the popup
gives a reason that has nothing to do with the author: three need a paid subscription to scan, one is too
short, one was published on launch day before detection began, and for one the scan failed. I drop these 6. I
treat the other 73, for which the popup gives no reason, as posts where the author turned detection off. That
leaves 307 posts from 64 publications.

A reader cannot scan a post with detection off, so I scored the text of all 73 such posts with Pangram's API
(model pangram-4.1). To check that the API and the reader scan measure the same thing, I also scored 68 posts
that readers can scan: all 28 scannable posts of publications that switch, and 40 drawn at random from
publications that never turn detection off. On these 68 posts the two agree closely. The correlation is 0.95,
the API reads 2.3 points higher on average, and they put 97% of posts on the same side of 50% AI. I therefore
use the reader scan for scannable posts and the API for posts with detection off, and I check every comparison
with API scores on both sides.

For the reader side, I collected each post's likes, comment count and restacks (Substack's reshare) on
November 13, along with its comments. Comments were available for 215 of the 223 posts that have any, 8,914
comments in all. The rest sit behind paid comment sections.

**Table 3.** Substack sample by category.

| Category | Publications | Posts | Detection off | Publications ever off | Publications with a note | Posts ≥ 50% AI | Of those, detection off |
|---|---|---|---|---|---|---|---|
| Culture | 10 | 48 | 33% | 5 | 0 | 25% | 92% |
| Fiction | 10 | 48 | 42% | 6 | 2 | 12% | 100% |
| Finance | 11 | 47 | 11% | 2 | 1 | 43% | 20% |
| Health & Wellness | 11 | 60 | 25% | 3 | 4 | 38% | 65% |
| Technology | 11 | 51 | 12% | 1 | 1 | 12% | 0% |
| U.S. Politics | 11 | 53 | 21% | 2 | 0 | 8% | 100% |
| **All** | **64** | **307** | **24%** | **19** | **8** | **23%** | **56%** |

<!-- Excludes the 6 posts unavailable for a stated reason. "Posts ≥ 50% AI" uses the reader scan for scannable
posts and the API for posts with detection off. -->

## 4.5 Who turns detection off

Substack gave every author the same option at the same time, so there is no untreated group to compare. The
analysis is descriptive and asks three questions that follow from the theory in Section 2.2.

1. **How often.** The share of posts with detection off, overall and by window and category. Confidence
   intervals resample publications, since posts within a publication share an author.
2. **Who, and which posts.** Unraveling predicts that the posts withheld from scanning are the ones that would
   scan as AI. I test this two ways, both at the publication level. First, I compare publications that turn
   detection off on every post with publications that never do: the mean AI share of their posts, with a
   permutation test. Second, for publications that switch, I compare each one's off posts with its own on posts,
   with a sign-flip test. The within-publication comparison holds the author fixed.
3. **Response to reader labels.** On October 14, 2026, Substack began showing reader labels. That makes scan
   results more visible and raises the cost of a bad one. I compare the off share of each publication's posts
   published before and after that date, averaged over the 44 publications with posts on both sides. Authors
   choose when to turn detection off, and status is read on the check date, so this comparison is descriptive.

## 6. Results: Turning Detection Off on Substack

### 6.1 Authors often turn detection off

Authors turned detection off on 24% of sampled posts (73 of 307; 95% CI 14% to 34%). Nineteen of the 64
publications turned it off on at least one sampled post: 9 on every one and 10 on some. Unraveling predicts
that withholding is rare when disclosure is the default and withholding takes an action (implication 3).
Withholding here is common. The off share differs by category, from 11% in Finance and 12% in Technology to
33% in Culture and 42% in Fiction.

Turning detection off looks like a standing choice for many authors. Each of the 9 always-off publications had
detection off on every one of its 2 to 6 sampled posts (45 posts in all). Six of the 10 switchers had it off
on at least half of theirs.

### 6.2 The posts withheld from scanning are the AI posts

Posts with detection off are mostly AI. Scored with the API, they average 53% AI, and 55% of them score at least
50%. Posts readers can scan average 15% AI, and 13% score at least 50%. Of the 71 sampled posts that score at
least 50% AI, 40 (56%) have detection off, against 14% of the other 236 posts. A reader who scans every post
they read would see fewer than half of the mostly-AI posts flagged.

The difference holds when the author is held fixed or both sides are measured the same way.

- **Always off against always on.** The 9 always-off publications average 61% AI per publication. The 45
  always-on publications average 15% by the reader scan, a difference of 45 points (permutation p < 0.001).
  Measured by the API on both sides (28 always-on publications in the calibration sample, averaging 17%), the
  difference is 43 points (p = 0.002). Five of the 9 always-off publications average more than 50% AI, against
  4 of the 45 always-on publications.
- **Within switching publications.** A switcher's off posts average 20 points more AI than its own on posts,
  both measured by the API (10 publications, sign-flip p = 0.06). In six of the 10 the off posts score higher,
  by 5 to 60 points. In three, all posts score 0% either way, and in one the off posts score lower.

**Table 4.** AI share of posts by detection status and publication pattern.

| Publications | Number | Posts | Scored by | Mean AI share per post | Posts ≥ 50% AI |
|---|---|---|---|---|---|
| Always on | 45 | 206 | reader scan | 15% | 28 (14%) |
| Switch, posts with detection on | 10 | 28 | reader scan | 12% | 3 (11%) |
| Switch, posts with detection off | 10 | 28 | API | 47% | 14 (50%) |
| Always off | 9 | 45 | API | 57% | 26 (58%) |

<!-- Calibration: always-on posts scored by the API (40 random posts) average 22%, with 22% at least 50%; the
switchers' on posts average 14% by the API. -->

The category pattern in Table 3 reverses once the withheld posts are scored. Detection is off most often in
Fiction and Culture, where few scannable posts score as AI. But nearly every mostly-AI post in those categories
has detection off: 6 of 6 in Fiction and 11 of 12 in Culture. Scanning in those categories shows little AI
because the AI is withheld. Finance is the exception. 43% of its posts are mostly AI, and most of those (16 of
20) can be scanned.

Not every author who withholds uses AI. Two of the 9 always-off publications score near 0% on every post, and so
do three switchers. The authors' notes show why some writers withhold anyway. One always-off publication argues
that "AI detection does not work," and another asks readers not to submit its posts to Pangram. Withholding is
therefore a noisy signal. It is not a clean separation of AI and human writers, but it is strongly concentrated
among AI posts.

### 6.3 No rise when reader labels began

The off share is about the same across windows: 25% for posts from July 21 to August, 25% in September and 22% in
October. Within publications, the off share of posts published after October 14 is 4 points lower than before
(95% CI −12 to +3, 44 publications). Making scan results more visible did not raise withholding, so there is no
support for answer B3. The interval cannot rule out a small rise.

### 6.4 Readers do not visibly react

If readers took a missing scan as a sign of AI, posts with detection off would get less engagement. They don't,
measurably. I regress log likes, comments and restacks on detection off and on scoring at least 50% AI. The
models include publication fixed effects, so each publication is compared with itself, and control for post age
and length. Standard errors are clustered by publication.

**Table 5.** Engagement on posts with detection off and on mostly-AI posts, within publications (log points).

| Outcome | Detection off | 95% CI | Score ≥ 50% AI | 95% CI |
|---|---|---|---|---|
| Likes | −0.13 | −0.57 to +0.30 | +0.11 | −0.15 to +0.37 |
| Comments | −0.17 | −0.59 to +0.24 | −0.35 | −0.88 to +0.17 |
| Restacks | +0.06 | −0.56 to +0.68 | +0.22 | −0.21 to +0.65 |

<!-- 307 posts, 64 publications; output/substack_readers_estimates.csv, spec "within". The "off" coefficient is
identified from the 10 switchers. -->

None of the estimates is distinguishable from zero. The intervals are wide: posts with detection off could get
up to about 43% fewer likes or up to 35% more. Across publications, the raw gap is large. The median post with
detection off has 33 likes, a scannable human post 87 and a scannable mostly-AI post 55. But this gap reflects
which publications withhold, not how readers respond to a given post. Comparing publications within categories,
mostly-AI posts get about 43% fewer likes (−0.56 log points, p = 0.12), but this comparison mixes the effect of AI
with differences in audience size. Allowing the effects to change after the reader labels began on October 14
changes nothing (all interactions p > 0.4), though only 69 posts fall after that date.

Readers also do not call posts out. Across 8,914 comments, no comment says the post it is under was written with
AI. That holds for the 71 mostly-AI posts too. The 9 comments the Reddit call-out pattern matches all use "AI
slop" for something else, such as the news. The one comment that names Pangram uses it against another
commenter. On Reddit, by contrast, 2.6% of posts Pangram flags as AI drew a call-out (6 of 232; Section
5.5). Substack readers either
do not notice AI text, do not scan, or do not say so in public. Scan results are private, so the data cannot
tell these apart.

### 6.5 Summary and limits

About one in four sampled Substack posts has AI detection turned off, and the posts with detection off are
mostly AI. More than half of the mostly-AI posts in the sample cannot be scanned by readers. Withholding is
concentrated among AI posts, across publications and within them, as unraveling predicts (answer B1). But it is
far from rare, so the theory's other prediction fails. Readers who treated a missing scan as a sign of AI would
be right more often than not. The second half of unraveling is that readers act on silence, and there is no sign
of it: withheld posts and mostly-AI posts get no less engagement than the same publication's other posts, and
no reader calls a post out. With readers not penalizing silence, authors who use AI lose nothing by
withholding. That is consistent with withholding staying common.

The results have seven limits.

- The sample is small: 64 publications, 9 always off and 10 switchers. The within-publication comparison
  (p = 0.06) rests on 10 publications, and so does the engagement effect of detection off.
- Engagement is counted on one day, two weeks to four months after posting, and cannot show whether readers
  scanned.
  It measures what readers do, not what they believe.
- Scores of posts with detection off come from the API, and the rest from the reader scan. The two agree closely
  on 68 posts scored both ways, and the main comparisons hold with the API on both sides.
- Pangram can misclassify. Its false-positive rate on pre-2022 Reddit text was 0 of 1,592 posts (Section 3.3),
  but newsletter prose may differ.
- "Off" assumes that an unavailable post with no stated reason was turned off by its author. The popup does not
  say so.
- Status is read on the check date. Within publications, second-draw posts (checked November 12) are off 5
  points more often than first-draw posts (checked November 8 to 11; 95% CI 0 to 11). Authors may still be
  turning detection off on older posts. Rechecking the first-draw posts would tell.
- Publications come from Substack's category listings, which favor established newsletters.

**Note on scoring withheld posts.** These authors chose to turn detection off, and one asked readers not to
submit their posts to Pangram. Scoring their posts overrides that choice, so the paper reports these scores
only in aggregate and does not name publications next to them. The text was used only for scoring and is not
kept in the replication files.
