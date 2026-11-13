# Outline: Do AI Rules Change What Creators Post? Evidence from Reddit Bans and Substack's AI Detector

*Revised outline, November 13, 2026. Both settings now have results (paper/draft-reddit-sections.md and
paper/draft-substack-sections.md), so the answers found are marked. arXiv was dropped on 11/4, and the Reddit
label study is an appendix.*

## RAP

### R: Research question

When a platform or community sets a rule about AI content, do creators change what they post, or do they ignore
the rule? I answer this in two settings that differ in who enforces the rule and what the creator controls:
- **Reddit:** subreddits that banned AI content between July 2023 and November 2024. Moderators enforce the ban,
  so the question is whether AI creators leave, comply, or keep posting.
- **Substack:** since July 2026 readers can scan a post with Pangram's AI detector, and authors can turn the scan
  off for a post. Keeping it on is a verifiable "human-written" disclosure, so the question is whether authors
  withhold it, whether withholding is concentrated among AI users, and whether readers treat a withheld scan as
  bad news, as unraveling predicts.

The causal estimands are the effect of a Reddit ban on posting and on the AI share of posts. The Substack
estimands are descriptive: how often, and by whom, detection is turned off, and how readers respond within a
publication.

### A and P: Reddit (what does a ban do?)

**A1: AI creators leave.** Posting and the AI share both fall at a ban.
- **P1:** Mandatory rules are known to change what firms supply (Jin and Leslie 2003), but no study measures
  whether a community AI rule changes how much AI content gets made.

**A2: AI creators comply.** The AI share falls, but posting does not.
- **P2:** Same as P1, with compliance rather than exit as the channel.

**A3 (found): AI creators ignore the ban.** Posting does not fall at a ban, the share of text posts flagged as AI
keeps rising about as fast as in comparison subreddits (+0.4 points after adjusting for catch-up, 95% CI −0.9 to
+1.8), and the slowdown in posting after a ban is not larger where AI posting was more common. Bans are adopted
at a peak in activity, and the peak would have ended anyway.
- **P3:** Research on community AI rules catalogs what the rules say (Lloyd et al. 2025) but not whether they
  change behavior. This is the first evidence that a ban, as most communities write and enforce it, does not
  measurably reduce detectable AI text. The interval is wide, so a moderate reduction cannot be ruled out, and
  the result covers text subreddits only.

### A and P: Substack (do authors withhold a good-news disclosure?)

**B1 (found, in part): Authors who use AI withhold, but withholding is common, and readers do not penalize
it.** Detection is off on 24% of sampled posts, not "few." The withheld posts are mostly AI: scored with the
Pangram API they average 53% AI, against 15% for scannable posts, and 56% of the mostly-AI posts in the sample
cannot be scanned. Always-off publications average 61% AI against 15% for always-on ones (p < 0.001), and a
switching publication's off posts average 20 points more AI than its own on posts (10 publications, p = 0.06).
Readers do not respond: withheld and mostly-AI posts get no less engagement than the same publication's other
posts, and none of 8,914 comments calls a post AI.
- **PB1:** Unraveling theory predicts that verifiable good news is disclosed and silence is read as bad news
  (Grossman 1981; Milgrom 1981). Tests in labs and product markets find disclosure falls short (Jin, Luca and
  Martin 2021; Mathios 2000), but there is no field test for AI. This is one: authors sort as the theory
  predicts, but the readers' half fails. Silence carries information that readers do not act on, so
  withholding costs AI users nothing and stays common, the receiver-side failure that lab studies find (Jin,
  Luca and Martin 2021).

**B2 (not found): Many authors turn detection off, including human writers.** Disabling is common, but it is
concentrated among AI users. A few human writers withhold too (2 of 9 always-off publications score near 0%),
some of them in protest against the detector, which makes silence a noisy signal but not an empty one.

**B3 (not found): Disabling rises when scan results become more visible.** The off share is flat across
windows, and within publications it is 4 points lower after October 14, 2026 (95% CI −12 to +3).
- **PB3:** Had it risen, withholding would have responded to the cost of disclosure. With readers not reacting
  to scans or their absence, more visible scans raise no cost, which fits the null.

### Across settings

Reddit tests a rule enforced by moderators against content creators; Substack tests a disclosure that creators
control. Together they ask whether AI rules work through enforcement or through the creator's own choice. The
answer is the same in both: a rule changes behavior only if someone acts on it. Reddit bans are not enforced
(1 of 57 flagged posts removed), and AI posting continues (A3). Substack's detector does sort authors, since AI
users withhold the scan (B1), but readers do not act on a withheld scan, so withholding is free and common.
Readers on both platforms impose little cost on AI text: on Reddit, flagged posts get somewhat fewer comments and
2.6% are called out; on Substack, neither.

---

## 1. Background: AI Rules on Reddit and Substack

### 1.1 Platform and government AI rules

**Takeaway.** AI rules are spreading, from labeling mandates (EU AI Act Art. 50, California SB 942) to platform
detectors and community bans, but there is little evidence on whether they change what creators post. The two
settings below each give one answer.

### 1.2 AI bans on Reddit

**Takeaway.** Subreddit moderators write their own rules, and hundreds banned AI content between 2023 and 2024.
Reddit timestamps each rule when it is created, so each ban can be dated to the day. That gives a large set of
staggered bans in comparable communities, which is the variation the Reddit design uses.

- Of the subreddits in both AIRules crawls (July 2023 and November 2024; Lloyd et al. 2025), 416 adopted a
  datable ban between the crawls; 351 are active enough to study.
- Most bans target AI images ("No AI art"); about a fifth of banned subreddits post mostly text, where the AI
  share can be measured with a text detector.
- A few subreddits instead added an optional AI flair and later made it mandatory. Only four such switches can
  be dated, so this is an appendix (Appendix A).

### 1.3 Substack's reader-run AI detector

**Takeaway.** Substack launched Pangram's AI detector for readers on July 21, 2026 (press coverage). A reader
can scan a post of 100 words or more, the result is private to that reader, and the scan covers posts from the
launch date on. According to press coverage, authors can turn detection off for a post, and readers then see
"AI detection unavailable." Keeping the scan on lets readers verify a post is human-written, so turning it off
is the author's choice to withhold that.

- Confirmed in the logged-in reader on 11/6: some posts show "AI detection unavailable," and the status can
  differ between posts of the same publication. Authors can also add an optional "How I make this" note, which
  shows even when detection is off.
- The popup gives a reason for some unavailable posts (paid only, too short, before launch, scan failed); for
  the rest it gives none. Not confirmed from a primary source: that "no reason" means the author turned
  detection off.
- Substack began showing reader labels on October 14, 2026 (per a Substack writer's post, not yet confirmed),
  a second date at which the stakes of a scan change.
- Substack's terms (updated October 6, 2026) prohibit automated collection and copying significant content.
  Detection status was hand-coded in the reader; post text, engagement and comments were fetched from
  Substack's public endpoints before the advisor's decision on permission (section 3.5).

### 1.4 Previous work

**Takeaway.** Disclosure economics shows voluntary disclosure of quality often falls short; work on AI labels
measures how audiences react in experiments; work on AI rules describes what rules say. None measures, with
real creators, whether AI rules change what gets posted.

- **Voluntary and mandatory disclosure:** Grossman (1981); Milgrom (1981); Jin, Luca and Martin (2021); Mathios
  (2000); Jin and Leslie (2003); review in Dranove and Jin (2010).
- **Audience responses to AI labels:** survey experiments with hypothetical stimuli (Altay and Gilardi 2024,
  among others).
- **AI rules and AI detection:** community AI rules on Reddit (Lloyd et al. 2025); the Pangram classifier (Emi
  and Spero 2024; Glickenhaus et al. 2026).

## 2. Theory: How a Creator Responds to an AI Rule

### 2.1 A ban

**Takeaway.** A creator who uses AI can comply (post without AI, at a cost), keep posting AI content and risk
removal, or leave. Which one they choose depends on how likely a violation is to be caught. If enforcement is
weak, the cheapest response is to ignore the ban, and neither posting nor the AI share moves.

- A creator who uses AI gets value $v$ from posting AI content, $v - k$ from posting without AI ($k$ is the cost
  of doing the work), and 0 from leaving. A violating post is removed with probability $q$, and removal costs $c$.
  The creator ignores the ban if $v - q(v + c) \ge \max(v - k, 0)$, i.e. if $q \le \min(k, v)/(v + c)$.

### 2.2 Turning detection off on Substack

**Takeaway.** An author chooses whether to leave a post scannable. A human-written post gains from being
verifiable; an AI-assisted post risks a "likely AI" result. If readers read a disabled scan as a bad sign,
human authors keep detection on, and disabling is concentrated among AI users: unraveling.

- An author's post is AI-assisted with some probability. If scannable, readers learn the truth; if disabled,
  readers form a belief $\mu_d$ that the post is AI. Human authors keep the scan on whenever $\mu_d > 0$, so in
  equilibrium only AI-assisted posts are disabled, unless turning the scan off has a cost or a benefit unrelated
  to AI (for example, authors who object to the feature on principle).
- The equilibrium needs readers to act on $\mu_d$. If readers do not scan, or do not discount disabled posts,
  withholding costs an AI author nothing, and disabling can be common while still concentrated among AI users.

### 2.3 Testable implications

1. **Weak enforcement means no change at a ban** (2.1): posting and the AI share do not move. Tested in 5.1-5.2.
2. **Exit means the slowdown scales with AI posting** (2.1): if creators leave, posting falls more where the AI
   share was higher. Tested in 5.3.
3. **Unraveling on Substack** (2.2): disabled posts are rare, and disabled posts are the AI posts. Tested in
   6.1-6.2.
4. **Disabling responds to visibility** (2.2): more disabling after reader labels launched on October 14, 2026.
   Tested in 6.3.
5. **Readers discount silence** (2.2): disabled posts get less engagement than the same author's scannable posts,
   and readers call out AI posts. Tested in 6.4.

## 3. Data

### 3.1 Reddit bans and their dates

**Takeaway.** Bans come from the two AIRules crawls and are dated by Reddit's own rule timestamps, which match
hand-coded dates where both exist. 416 bans are datable; 351 are active enough to study.

- Treated: no AI rule in July 2023; a rule banning AI content (without asking for a label) created after the July
  2023 crawl. Bans written into an older, edited rule cannot be dated and are dropped (151).

### 3.2 Posts per month and comparison subreddits

**Takeaway.** Monthly post counts for 2022-2025 come from Arctic Shift (Heitmann 2026). Comparison subreddits
have no AI rule in either crawl, drawn by topic and size, and a second set matched on pre-ban growth.

- 832 topic comparison subreddits (608 active before at least one ban); 3 growth-matched comparison subreddits
  per ban, matched on the level and trend of log posts in months 12 to 7 before the ban.

### 3.3 The AI share of text posts

**Takeaway.** A random sample of text posts around 56 text bans and their comparison subreddits, scored with
the Pangram API (`pangram-4.1`). The sample is fixed before scoring, and a pre-ChatGPT window measures the
false-positive rate (0 of 1,592 posts flagged).

- Text subreddits: at least a quarter of their last 100 posts before July 2023 are text posts of 50+ words (83 of
  416 bans; 56 with a text comparison subreddit).
- 10 random days in each of March-August 2022, months −6 to −1 and months +1 to +6; at most 60 posts per
  subreddit-window scored, weighted back to all text posts. 11,857 posts scored.

### 3.4 Reading the ban rules

**Takeaway.** The 83 text-ban rules are read by hand: 48 ban all AI content, 14 ban AI text, 9 ban only images,
4 ban only comments, 4 are not bans of AI content, and 4 are partial or unclear. Results are shown for the rules
that cover text posts.

### 3.5 Substack posts and their detection status

**Takeaway.** A hand-coded sample of Substack posts records whether each post can be scanned, what the scan says
when it can, and whether the author added a "How I make this" note. Detection status is not in Substack's public
data, so it can only be read in the logged-in reader.

- Sample: 66 publications from Substack's category listings (11 in each of six categories) and free posts of
  at least 100 words in three windows from the July 21 launch to October. Two draws, one post per window each:
  313 posts, hand-coded November 8 to 12. Dropping 6 posts unavailable for a stated reason leaves 307 posts from
  64 publications; 73 have detection off.
- Status is recorded on the day it is checked, not the day the post was published, since authors can turn
  detection off for old posts.
- AI scores: the reader scan for scannable posts; the Pangram API (pangram-4.1) for the 73 posts with detection
  off. On 68 posts scored both ways the two agree closely (correlation 0.95, API 2.3 points higher, 97% on the
  same side of 50%).
- Reader side: likes, comments and restacks of every post, and 8,914 comments on 215 posts, fetched November 13.
- Scoring the withheld posts overrides the authors' choice (one asked readers not to submit posts to Pangram),
  so those scores are reported only in aggregate, without naming publications, and the text is not kept in the
  replication files.

### 3.6 Summary statistics

- **Table 1:** Reddit sample construction. **Table 2:** banned and comparison subreddits (size, posts per month).
- **Table 3:** Substack sample by category: publications, posts, share with detection off, publications with a
  note, share of posts mostly AI and how many of those have detection off.

## 4. Methodology

### 4.1 Reddit: posts per month

**Takeaway.** A stacked event study compares each ban with never-banned subreddits. Banned subreddits grow
faster before the ban, so parallel trends fail, and the main estimate is a trend break against growth-matched
comparison subreddits.

$$\log(1 + \text{posts}_{ist}) = \sum_{k \neq -1} \beta_k \, \mathbf{1}[\text{treated}_{is}] \, \mathbf{1}[t - E_s = k] + \alpha_{is} + \gamma_{st} + \varepsilon_{ist}$$

- One stack per ban (Cengiz et al. 2019), stack-by-subreddit and stack-by-month fixed effects, errors clustered by
  subreddit (Roth et al. 2023). The trend-break version replaces the $\beta_k$ with a banned-subreddit trend, a
  jump and a slope change at the ban.

### 4.2 Reddit: the AI share of text posts

**Takeaway.** The same stacked comparison on scored posts gives the change in the probability a post is flagged
as AI at a ban. Banned subreddits start with less AI text than their comparison subreddits, so the main estimate
adjusts for catch-up.

$$\text{AI}_{pisw} = \beta \, \mathbf{1}[\text{treated}_{is}] \, \mathbf{1}[w = \text{post}] + \alpha_{is} + \gamma_{sw} + \varepsilon_{pisw}$$

- Catch-up adjustment: each subreddit's pre-ban AI share × post, measured on a random half of its pre-ban posts
  and estimated on the other half, so regression to the mean is not built in.

### 4.3 Reddit: does the slowdown scale with AI posting?

**Takeaway.** Interacting the trend break with each ban's pre-ban AI share tests exit (implication 2) directly.

### 4.4 Reddit: identifying assumptions

- **Posts:** without a ban, a banned subreddit would have kept its trend against its growth-matched comparison
  subreddits. Threat: bans are written at an activity peak, which biases the slowdown toward a negative effect.
- **AI share:** without a ban, a banned subreddit's AI share would have risen like a comparison subreddit's with
  the same starting share. Threat: evasion (editing AI text until it is not flagged), which biases toward
  finding compliance.
- **Coverage:** the AI share covers text subreddits (56 of 351 bans); most bans target images.

### 4.5 Substack: who turns detection off

**Takeaway.** Substack has no rule change to exploit, so the analysis is descriptive: how often posts are
disabled, whether the disabled posts are the AI posts, and how readers respond, holding the publication fixed
where possible.

- **Share disabled** by window and category, with confidence intervals that resample publications
  (implication 3).
- **Which posts are disabled:** always-off against always-on publications (permutation test on publication
  means), and a switching publication's off posts against its own on posts (sign-flip test) (implication 3).
- **Before and after reader labels** (October 14, 2026): the within-publication change in the disabled share
  (implication 4). Descriptive, since authors choose when to disable.
- **Readers** (implication 5): log likes, comments and restacks on detection off and on scoring ≥ 50% AI, with
  publication fixed effects, controls for post age and length, and errors clustered by publication; comment
  call-outs found with the Reddit pattern and checked by hand.

## 5. Results: Reddit AI Bans

See paper/draft-reddit-sections.md for the full text, tables and figures.

### 5.1 Posting does not fall at a ban

**Takeaway.** Banned subreddits pull ahead of growth-matched subreddits in the six months before the ban, peak
in the ban month and then stop gaining (slope change −1.6% a month, p < 0.001; no jump). Read as the end of a
burst of activity, not the effect of the ban.

- **Figure 1:** posts per month around a ban against growth-matched subreddits.

### 5.2 The AI share of text posts does not fall

**Takeaway.** The share of text posts flagged as AI rises after a ban about as fast as in comparison subreddits:
+0.4 points adjusted for catch-up (95% CI −0.9 to +1.8), +0.1 on rules covering text. No sign of compliance, but
a moderate reduction cannot be ruled out.

- **Figure 2:** flagged share by window. **Table 3:** estimates and checks.

### 5.3 Moderators rarely remove AI posts

**Takeaway.** 1 of 57 posts flagged as AI after a ban was removed (1.8%), no more than other posts; bans do not
change removal rates (−0.8 points, 95% CI −3.1 to +1.5). Enforcement is close to zero, which is why ignoring the
ban pays (implication 1).

### 5.4 The slowdown is not about AI

**Takeaway.** The slowdown is not larger where AI posting was more common (interaction +0.5% a month per point,
p = 0.23), the wrong sign for exit.

### 5.5 Readers engage a little less with AI posts

**Takeaway.** Flagged AI posts get about 19% fewer comments in their first week (−0.21 log points, 95% CI −0.39
to −0.02) and about the same score; 2.6% are called out as AI (6 of 232), against 0.03% of other posts. Bans do
not make readers harsher. Readers impose little cost on AI text.

## 6. Results: Turning Detection Off on Substack

See paper/draft-substack-sections.md for the full text and tables.

### 6.1 Authors often turn detection off

**Takeaway.** Detection is off on 24% of posts (73 of 307; 95% CI 14% to 34%). 19 of 64 publications turn it
off at least once: 9 on every sampled post, 10 on some. Off shares range from 11% (Finance) to 42% (Fiction).

### 6.2 The withheld posts are the AI posts

**Takeaway.** Withheld posts average 53% AI, scannable ones 15%; 40 of the 71 mostly-AI posts (56%) are
withheld, against 14% of other posts. Always-off publications average 61% AI, always-on 15% (p < 0.001; 43
points with the API on both sides, p = 0.002). Within switching publications, off posts average 20 points more
AI (p = 0.06, 10 publications). Categories that look human when scanned (Fiction, Culture) withhold nearly
all their AI posts.

- **Table 3:** sample by category. **Table 4:** AI share by detection status and publication pattern.

### 6.3 No rise after reader labels

**Takeaway.** The off share is flat across windows, and 4 points lower after October 14 within publications
(95% CI −12 to +3). No support for B3.

### 6.4 Readers do not react

**Takeaway.** Within publications, neither withheld nor mostly-AI posts get measurably less engagement (likes
−0.13 and +0.11 log points, all p > 0.18), and no comment out of 8,914 calls a post AI. Silence is informative,
but readers do not act on it.

- **Table 5:** engagement estimates.

## 7. Discussion: Enforcement versus Creator Choice

**Takeaway.** Neither kind of AI rule changes what readers get. Reddit bans go unenforced, so AI creators ignore
them. Substack's detector lets authors signal, and AI users do withhold, but readers do not penalize the
silence, so withholding stays common and most AI text goes unscanned. Both results point to the audience: a
rule moves creators only if someone, a moderator or a reader, acts on it.

## Appendix A: The Reddit Label Study

Four subreddits switched from an optional AI flair to a mandatory one (wallpaper, Shrek, NikkeMobile, Frozen).
The flaired share rises at the mandate in the two clean cases and does not in the two with bundled rule changes;
no estimate is distinguishable from placebo dates. Figure: `output/flair_event_study.png`. Two more possible
switchers (Avatarthelastairbende, winxclub) are dated by rule timestamps but not yet added.

## 8. Next Steps, in Priority Order

1. Tell the advisor that Substack text, engagement and comments were collected and withheld posts scored
   before the terms-of-service decision, and agree how to report it.
2. Recheck the 29 Substack pilot posts (checked 11/8) to see whether authors are still turning detection off on
   old posts.
3. Write the introduction and theory sections around this outline (due with the 11/18 draft).
