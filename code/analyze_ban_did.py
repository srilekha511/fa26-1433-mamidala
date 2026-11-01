"""Event study of posts per month around an AI ban: banned subreddits against never-treated subreddits in the
same AIRules topic.

Usage: python3 code/analyze_ban_did.py   (after build_ban_sample.py)
Writes output/ban_event_study.png, output/ban_event_study.csv (one coefficient per month),
output/ban_matched_estimates.csv (the growth-matched checks),
output/ban_did_estimates.csv (the pooled estimate and its robustness checks) and output/ban_trend_break.csv
(banned subreddits' own pre-ban trend and its break at the ban, for when the pre-trend test fails).

Stacked difference-in-differences (Cengiz et al. 2019): one stack per banned subreddit, holding it and the
comparison subreddits of its topic for the PLOT_K months either side of its ban month, with stack-by-subreddit
and stack-by-month fixed effects. One treated unit per stack means each ban gets equal weight, and a comparison
subreddit never has its own ban inside a stack, so the staggered-timing problem of two-way fixed effects
does not arise. Standard errors are clustered by subreddit, since a comparison subreddit sits in many stacks.
The outcome is log(1 + posts); estimates are reported as percent changes.

A subreddit enters a stack only with a median of at least MIN_MEDIAN_POSTS posts a month over the 12 months
before that stack's ban month.

Banned subreddits grow faster than their topic's comparison subreddits before the ban, so a second comparison
group is matched on growth (growth_matches): for each ban, the MATCH_K comparison subreddits, from any topic,
nearest in mean log posts and the trend in log posts over a pre-ban window. Matching on the whole year before
the ban flattens the pre-ban coefficients by construction, so a check matches on months -12..-7 only and
leaves -6..-1 to show whether the paths still agree. Writes output/ban_matched_event_study.png and .csv.
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import chi2, norm

from analyze_reddit_did import CONTROL, GRID, INK, MUTED, SURFACE, SWITCHER
from reddit_subreddits import FIRST_MONTH, LAST_MONTH, ROOT

DERIVED = ROOT / "data" / "derived"
OUTPUT = ROOT / "output"
PLOT_K, EST_K, PRE_MONTHS = 12, 6, 12
MIN_MEDIAN_POSTS = 30  # same floor as the label study
MATCH_K = 3  # growth-matched comparison subreddits per ban, as for the switchers
MATCH_WINDOWS = {"matched on growth, months -12..-1": (-12, -1), "matched on growth, months -12..-7 only": (-12, -7)}


def load():
    sample = pd.read_csv(DERIVED / "ban_sample.csv")
    treated = sample[sample["drop"].isna()].set_index("subreddit")
    controls = pd.read_csv(DERIVED / "ban_controls.csv")
    counts = pd.read_csv(DERIVED / "ban_monthly_posts.csv")
    # Months missing from a successful count are months with no posts.
    wide = counts.pivot_table(index="month", columns="subreddit", values="posts", aggfunc="sum")
    wide = wide.reindex([str(p) for p in pd.period_range(FIRST_MONTH, LAST_MONTH, freq="M")]).fillna(0)
    wide.index = pd.PeriodIndex(wide.index, freq="M")
    return treated, controls, np.log1p(wide), wide


def active(posts, subs, event):
    """The subreddits with a median of at least MIN_MEDIAN_POSTS posts a month in the year before event."""
    pre = posts.loc[[event - i for i in range(1, PRE_MONTHS + 1)], subs]
    return [s for s in subs if pre[s].median() >= MIN_MEDIAN_POSTS]


def stacks(treated, controls, logs, posts, k=PLOT_K, matched_only=False):
    """Long table: one row per stack, subreddit and month from event-k to event+k-1."""
    out = []
    for sub, t in treated.iterrows():
        if sub not in posts:
            continue
        event = pd.Period(t["ban_date"][:7], "M")
        if event - max(k, PRE_MONTHS) < logs.index[0] or event + (k - 1) > logs.index[-1]:
            continue
        pool = controls[controls["matched_to"] == sub] if matched_only else controls[controls["topic_label"] == t["topic_label"]]
        units = active(posts, [sub] + [c for c in pool["subreddit"].unique() if c in posts], event)
        if sub not in units or len(units) < 2:
            continue
        months = [event + r for r in range(-k, k)]
        y = logs.loc[months, units]
        y.index = range(-k, k)
        long = y.reset_index(names="rel").melt(id_vars="rel", var_name="subreddit", value_name="y")
        out.append(long.assign(stack=sub, treated=long["subreddit"] == sub))
    return pd.concat(out, ignore_index=True)


def growth_features(logs, sub, months):
    """Mean and per-month trend of log(1 + posts) over the given months."""
    y = logs.loc[months, sub].to_numpy()
    return y.mean(), np.polyfit(np.arange(len(y)), y, 1)[0]


def growth_matches(treated, controls, logs, posts, window, k=MATCH_K):
    """For each ban, the k comparison subreddits (any topic, active in the year before the ban) nearest in mean
    log posts and trend over months window[0]..window[1] relative to the ban, on standardized distance. A
    comparison subreddit can match several bans, since each ban has its own stack."""
    pool = [c for c in controls["subreddit"].unique() if c in posts]
    out = []
    for sub, t in treated.iterrows():
        event = pd.Period(t["ban_date"][:7], "M")
        months = [event + r for r in range(window[0], window[1] + 1)]
        if sub not in posts or months[0] < logs.index[0]:
            continue
        cands = active(posts, pool, event)
        f = pd.DataFrame({c: growth_features(logs, c, months) for c in cands}, index=["mean", "trend"]).T
        dist = np.sqrt((((f - growth_features(logs, sub, months)) / f.std()) ** 2).sum(axis=1))
        out += [{"subreddit": c, "matched_to": sub} for c in dist.nsmallest(k).index]
    return pd.DataFrame(out)


def demean(df, cols):
    """Remove stack-by-subreddit and stack-by-month means (exact for a balanced stack)."""
    unit = df.groupby(["stack", "subreddit"])[cols].transform("mean")
    month = df.groupby(["stack", "rel"])[cols].transform("mean")
    whole = df.groupby("stack")[cols].transform("mean")
    return df[cols] - unit - month + whole


def fit(df, regressors):
    """OLS on the demeaned data with standard errors clustered by subreddit: (coefficients, covariance)."""
    x = demean(df, regressors).to_numpy()
    y = demean(df, ["y"])["y"].to_numpy()
    bread = np.linalg.inv(x.T @ x)
    b = bread @ x.T @ y
    groups = df["subreddit"].astype("category").cat.codes.to_numpy()
    scores = np.zeros((groups.max() + 1, x.shape[1]))
    np.add.at(scores, groups, x * (y - x @ b)[:, None])
    g, n = len(scores), len(y)
    v = bread @ scores.T @ scores @ bread * g / (g - 1) * (n - 1) / (n - x.shape[1])
    return b, v


def event_study(df, k=PLOT_K):
    rels = [r for r in range(-k, k) if r != -1]
    names = [f"rel_{r}" for r in rels]
    d = df.assign(**{n: (df["treated"] & (df["rel"] == r)).astype(float) for n, r in zip(names, rels)})
    b, v = fit(d, names)
    leads = [i for i, r in enumerate(rels) if r < -1]
    wald = b[leads] @ np.linalg.solve(v[np.ix_(leads, leads)], b[leads])
    table = pd.DataFrame({"rel": rels, "coef": b, "se": np.sqrt(np.diag(v))})
    table = pd.concat([table, pd.DataFrame({"rel": [-1], "coef": [0.0], "se": [0.0]})]).sort_values("rel")
    return table, float(chi2.sf(wald, len(leads)))


def pooled(df, k=EST_K):
    """treated x post within event-k..event+k-1: close to the mean across stacks of each ban's 2x2
    difference-in-differences."""
    d = df[(df["rel"] >= -k) & (df["rel"] < k)]
    d = d.assign(did=(d["treated"] & (d["rel"] >= 0)).astype(float))
    b, v = fit(d, ["did"])
    b, se = b[0], np.sqrt(v[0, 0])
    return {"did_log": b, "se": se, "did_pct": 100 * np.expm1(b), "ci_low_pct": 100 * np.expm1(b - 1.96 * se),
            "ci_high_pct": 100 * np.expm1(b + 1.96 * se), "p": 2 * norm.sf(abs(b / se)),
            "n_bans": int(d.loc[d["treated"], "stack"].nunique()),
            "n_comparison": int(d.loc[~d["treated"], "subreddit"].nunique())}


def trend_break(df):
    """Banned subreddits' own linear trend over the whole window, and its break at the ban: the change in level at
    month 0 and the change in monthly slope after it, against the comparison subreddits."""
    t = df["treated"].astype(float)
    post = (df["rel"] >= 0).astype(float)
    d = df.assign(trend=t * df["rel"], jump=t * post, slope_change=t * post * df["rel"])
    b, v = fit(d, ["trend", "jump", "slope_change"])
    se = np.sqrt(np.diag(v))
    return {name: (b[i], se[i], 2 * norm.sf(abs(b[i] / se[i]))) for i, name in enumerate(["trend", "jump", "slope_change"])}


def placebo_shift(treated, months=12):
    """The same bans moved months earlier, so the whole estimation window lies before the real ban."""
    shifted = treated.copy()
    shifted["ban_date"] = [str(pd.Period(d[:7], "M") - months) for d in treated["ban_date"]]
    return shifted


def main():
    treated, controls, logs, posts = load()
    OUTPUT.mkdir(exist_ok=True)
    df = stacks(treated, controls, logs, posts)
    print(f"{df['stack'].nunique()} bans with an active comparison group; "
          f"{df.loc[~df['treated'], 'subreddit'].nunique()} comparison subreddits")

    table, pre_p = event_study(df)
    table.round(4).to_csv(OUTPUT / "ban_event_study.csv", index=False)
    in_df = treated.loc[df["stack"].unique()]
    content = in_df.index[in_df["is_content_generation_ca_label"] == True]
    checks = [
        ("main: topic comparison group, +/-6 months", df, EST_K),
        ("+/-12 months", df, PLOT_K),
        ("own 2 matched comparison subreddits only", stacks(treated, controls, logs, posts, matched_only=True), EST_K),
        ("Content Generation communities", df[df["stack"].isin(content)], EST_K),
        ("other communities", df[~df["stack"].isin(content)], EST_K),
        ("drop bans dated by a full rule rewrite",
         df[~df["stack"].isin(in_df.index[in_df["rules_rewritten"] == True])], EST_K),
        ("placebo: ban moved 12 months earlier", stacks(placebo_shift(treated), controls, logs, posts), EST_K),
    ]
    est = pd.DataFrame([{"spec": name, **pooled(d, k)} for name, d, k in checks])
    est["pre_trend_p"] = [pre_p] + [np.nan] * (len(est) - 1)
    est.round(4).to_csv(OUTPUT / "ban_did_estimates.csv", index=False)
    pd.set_option("display.width", 200)
    print(est.round(3).to_string(index=False))
    print(f"joint test that the 11 leads are zero: p = {pre_p:.3f}")
    tb = trend_break(df)
    pd.DataFrame([{"term": k, "coef_log": b, "se": se, "pct": 100 * np.expm1(b), "p": p} for k, (b, se, p) in tb.items()]
                 ).round(4).to_csv(OUTPUT / "ban_trend_break.csv", index=False)
    print("trend break (±12 months): " + "; ".join(f"{k} {100 * np.expm1(b):+.2f}% (p = {p:.3f})"
                                                  for k, (b, se, p) in tb.items()))
    plot(table, est.iloc[0], pre_p, OUTPUT / "ban_event_study.png")

    matched_rows, paths = [], {}
    for name, window in MATCH_WINDOWS.items():
        d = stacks(treated, growth_matches(treated, controls, logs, posts, window), logs, posts, matched_only=True)
        paths[name], p = event_study(d)
        tb = trend_break(d)
        matched_rows.append({"spec": name, **pooled(d, EST_K), "pre_trend_p": p,
                             **{f"{k}_pct": 100 * np.expm1(b) for k, (b, se, _) in tb.items()},
                             **{f"{k}_p": q for k, (b, se, q) in tb.items()}})
    matched = pd.DataFrame(matched_rows)
    matched.round(4).to_csv(OUTPUT / "ban_matched_estimates.csv", index=False)
    pd.concat([t.assign(spec=n) for n, t in paths.items()]).round(4).to_csv(OUTPUT / "ban_matched_event_study.csv",
                                                                           index=False)
    print(matched.round(3).to_string(index=False))
    plot_matched(paths, OUTPUT / "ban_matched_event_study.png")


def plot_matched(paths, path):
    fig, ax = plt.subplots(figsize=(8, 4.6), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    pct = lambda x: 100 * np.expm1(x)
    ax.axhline(0, color=MUTED, lw=1, zorder=1)
    ax.axvline(-0.5, color=MUTED, lw=1, ls=(0, (3, 3)), zorder=1)
    for (name, t), color, (lo, hi) in zip(paths.items(), [SWITCHER, CONTROL], MATCH_WINDOWS.values()):
        ax.axvspan(lo - 0.5, hi + 0.5, ymin=0, ymax=0.025, color=color, lw=0, zorder=1)
        ax.fill_between(t["rel"], pct(t["coef"] - 1.96 * t["se"]), pct(t["coef"] + 1.96 * t["se"]),
                        color=color, alpha=0.12, lw=0, zorder=1)
        ax.plot(t["rel"], pct(t["coef"]), color=color, lw=2, marker="o", ms=4, zorder=3,
                label=f"Comparison subreddits {name} (marked on the axis)".replace("..", " to "))
    fig.suptitle("Posts per month around an AI ban, against subreddits matched on pre-ban growth",
                 x=0.01, ha="left", fontsize=12, color=INK)
    ax.legend(loc="upper left", frameon=False, fontsize=8.5, labelcolor=INK)
    ax.set_xlabel("Months relative to the ban", color=MUTED, fontsize=9)
    ax.set_ylabel("Change in posts vs matched subreddits (%)", color=MUTED, fontsize=9)
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.tick_params(colors=MUTED, labelsize=8)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)


def plot(table, main, pre_p, path):
    fig, ax = plt.subplots(figsize=(8, 4.6), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    pct = lambda x: 100 * np.expm1(x)
    ax.fill_between(table["rel"], pct(table["coef"] - 1.96 * table["se"]), pct(table["coef"] + 1.96 * table["se"]),
                    color=SWITCHER, alpha=0.15, lw=0, zorder=1)
    ax.axhline(0, color=MUTED, lw=1, zorder=1)
    ax.axvline(-0.5, color=MUTED, lw=1, ls=(0, (3, 3)), zorder=1)
    ax.plot(table["rel"], pct(table["coef"]), color=SWITCHER, lw=2, marker="o", ms=4, zorder=3)
    ax.set_title(f"{main['n_bans']} bans, {main['n_comparison']} comparison subreddits · "
                 f"DiD ±{EST_K} months {main['did_pct']:+.1f}% (95% CI {main['ci_low_pct']:+.1f} to "
                 f"{main['ci_high_pct']:+.1f}) · pre-trend p = {pre_p:.2f}", loc="left", fontsize=9, color=MUTED)
    fig.suptitle("Posts per month around a subreddit's AI ban, relative to the month before",
                 x=0.01, ha="left", fontsize=12, color=INK)
    ax.set_xlabel("Months relative to the ban", color=MUTED, fontsize=9)
    ax.set_ylabel("Change in posts vs comparison subreddits (%)", color=MUTED, fontsize=9)
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.tick_params(colors=MUTED, labelsize=8)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)


if __name__ == "__main__":
    main()
