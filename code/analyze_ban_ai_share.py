"""Share of text posts the Pangram API flags as AI, before and after a subreddit's AI ban, against comparison
subreddits, and whether bans with more AI posting beforehand saw a larger slowdown in posts.

Usage: python3 code/analyze_ban_ai_share.py   (after score_pangram_api.py; runs on whatever has been scored)
Writes output/ban_ai_share_windows.csv (flagged share by group and window, and the pre-ChatGPT false-positive rate),
output/ban_ai_share_estimates.csv (the difference-in-differences and its checks),
output/ban_ai_share_leave_one_out.csv, output/ban_ai_share_heterogeneity.csv and output/ban_ai_share.png.

Outcome: 1 if Pangram's short prediction is "AI" (a "Mixed" post counts as not AI; the AI fraction of the text is a
check). Sample: the chosen posts (score_pangram_api.select) in the pre (months -6..-1) and post (+1..+6) windows.

Main estimate: a stacked difference-in-differences on posts, y = treated x post + stack-by-subreddit + stack-by-window
fixed effects, by least squares with standard errors clustered by subreddit (every subreddit sits in one stack).
Unweighted, each scored post counts once; weighted by `cap_weight`, each subreddit-window counts by its number of
text posts, so the estimate is a change in the share of all text posts. A third version weights every ban equally:
the mean across bans of each ban's own 2x2 difference.

Heterogeneity: the trend-break regression of analyze_ban_did (log posts, banned subreddit against its topic
comparison group, +/-12 months) on the text bans, with the jump and slope change interacted with the ban's pre-ban
flagged share. If AI posters leave at a ban, the slowdown should be larger where AI posting was more common.
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import norm

import analyze_ban_did as posts_did
from analyze_reddit_did import CONTROL, GRID, INK, MUTED, SURFACE, SWITCHER
from reddit_subreddits import ROOT
from score_pangram_api import CHOSEN, SCORES, wilson

OUTPUT = ROOT / "output"
WINDOWS = ["baseline", "pre", "post"]
MIN_CELL = 10  # posts per ban-group-window for the equal-weight version, so one post cannot swing a ban


def load():
    chosen = pd.read_parquet(CHOSEN).drop(columns=["selftext", "title"])
    scores = pd.read_csv(SCORES).drop_duplicates("id")
    df = chosen.merge(scores, on="id")
    df["ai"] = (df["prediction_short"] == "AI").astype(float)
    df["treated"] = df["role"] == "treated"
    return df, len(chosen)


def dummies(keys):
    """Indicator columns for each distinct value of keys, as a float array."""
    codes = pd.factorize(keys)[0]
    out = np.zeros((len(codes), codes.max() + 1))
    out[np.arange(len(codes)), codes] = 1.0
    return out


def did(df, y="ai", weight=None):
    """treated x post with stack-by-subreddit and stack-by-window fixed effects; SEs clustered by subreddit."""
    d = df[df["window"].isin(["pre", "post"])]
    if d.loc[d["treated"], "window"].nunique() < 2 or d.loc[~d["treated"], "window"].nunique() < 2:
        return None
    x = np.column_stack([(d["treated"] & (d["window"] == "post")).to_numpy(float),
                         dummies(d["stack"] + "|" + d["subreddit"]),
                         dummies(d["stack"] + "|" + d["window"])[:, 1:]])
    w = np.ones(len(d)) if weight is None else d[weight].to_numpy() / d[weight].mean()
    yv = d[y].to_numpy(float)
    xw = x * w[:, None]
    bread = np.linalg.pinv(x.T @ xw)
    b = bread @ xw.T @ yv
    groups = pd.factorize(d["subreddit"])[0]
    scores = np.zeros((groups.max() + 1, x.shape[1]))
    np.add.at(scores, groups, xw * (yv - x @ b)[:, None])
    g = len(scores)
    se = np.sqrt((bread @ scores.T @ scores @ bread)[0, 0] * g / (g - 1))
    return {"did_pp": 100 * b[0], "se_pp": 100 * se, "ci_low_pp": 100 * (b[0] - 1.96 * se),
            "ci_high_pp": 100 * (b[0] + 1.96 * se), "p": 2 * norm.sf(abs(b[0] / se)),
            "n_bans": int(d.loc[d["treated"], "stack"].nunique()), "n_subreddits": g, "n_posts": len(d)}


def ban_level(df, y="ai", min_cell=MIN_CELL):
    """Each ban's own 2x2 difference in mean y, averaged with equal weight across bans that have at least min_cell
    posts in all four cells."""
    d = df[df["window"].isin(["pre", "post"])]
    g = d.groupby(["stack", "role", "window"])[y]
    cells = g.mean().where(g.size() >= min_cell).unstack(["role", "window"])
    need = [("treated", "post"), ("treated", "pre"), ("control", "post"), ("control", "pre")]
    if not all(c in cells.columns for c in need):
        return None
    cells = cells.dropna(subset=need)
    diff = (cells[("treated", "post")] - cells[("treated", "pre")]) - (cells[("control", "post")] - cells[("control", "pre")])
    se = diff.std() / np.sqrt(len(diff))
    return {"did_pp": 100 * diff.mean(), "se_pp": 100 * se, "ci_low_pp": 100 * (diff.mean() - 1.96 * se),
            "ci_high_pp": 100 * (diff.mean() + 1.96 * se), "p": 2 * norm.sf(abs(diff.mean() / se)),
            "n_bans": len(diff), "n_subreddits": np.nan, "n_posts": int(d["stack"].isin(diff.index).sum())}


def window_table(df):
    """Flagged share by group and window: unweighted with a Wilson interval, and weighted by cap_weight."""
    rows = []
    for (role, window), g in df.groupby(["role", "window"]):
        lo, hi = wilson(g["ai"].sum(), len(g))
        rows.append({"role": role, "window": window, "posts": len(g), "subreddits": g["subreddit"].nunique(),
                     "flagged_ai": int(g["ai"].sum()), "mixed": int((g["prediction_short"] == "Mixed").sum()),
                     "ai_pct": 100 * g["ai"].mean(), "ci_low": 100 * lo, "ci_high": 100 * hi,
                     "ai_pct_weighted": 100 * np.average(g["ai"], weights=g["cap_weight"]),
                     "mean_fraction_ai_pct": 100 * g["fraction_ai"].mean()})
    base = df[df["window"] == "baseline"]
    lo, hi = wilson(base["ai"].sum(), len(base))
    rows.append({"role": "all", "window": "baseline (false-positive rate)", "posts": len(base),
                 "subreddits": base["subreddit"].nunique(), "flagged_ai": int(base["ai"].sum()),
                 "mixed": int((base["prediction_short"] == "Mixed").sum()), "ai_pct": 100 * base["ai"].mean(),
                 "ci_low": 100 * lo, "ci_high": 100 * hi})
    out = pd.DataFrame(rows)
    out["order"] = out["window"].map({w: i for i, w in enumerate(WINDOWS)}).fillna(len(WINDOWS))
    return out.sort_values(["order", "role"]).drop(columns="order")


def leave_one_out(df):
    """The unweighted estimate with each subreddit dropped in turn (a ban's stack goes with its banned subreddit)."""
    rows = []
    for sub, role, stack in df[["subreddit", "role", "stack"]].drop_duplicates().itertuples(index=False):
        keep = df["stack"] != stack if role == "treated" else df["subreddit"] != sub
        r = did(df[keep])
        if r:
            rows.append({"dropped": sub, "role": role, "stack": stack, "did_pp": r["did_pp"], "se_pp": r["se_pp"]})
    return pd.DataFrame(rows).sort_values("did_pp")


def pre_ban_share(df):
    """Each ban's flagged share in its pre window, weighted to all its text posts."""
    pre = df[df["treated"] & (df["window"] == "pre")]
    return pre.groupby("stack").apply(lambda g: np.average(g["ai"], weights=g["cap_weight"]), include_groups=False)


def heterogeneity(share):
    """Trend break in log posts at the text bans, with the jump and slope change interacted with the pre-ban share."""
    treated, controls, logs, posts = posts_did.load()
    panel = posts_did.stacks(treated.loc[treated.index.intersection(share.index)], controls, logs, posts)
    s = panel["stack"].map(share - share.mean()).fillna(0) * 100  # percentage points from the mean
    t = panel["treated"].astype(float)
    post = (panel["rel"] >= 0).astype(float)
    d = panel.assign(trend=t * panel["rel"], jump=t * post, slope_change=t * post * panel["rel"],
                     trend_x_share=t * panel["rel"] * s, jump_x_share=t * post * s,
                     slope_change_x_share=t * post * panel["rel"] * s)
    names = ["trend", "jump", "slope_change", "trend_x_share", "jump_x_share", "slope_change_x_share"]
    b, v = posts_did.fit(d, names)
    se = np.sqrt(np.diag(v))
    return pd.DataFrame({"term": names, "coef_log": b, "se": se, "pct": 100 * np.expm1(b),
                         "p": 2 * norm.sf(np.abs(b / se)), "n_bans": panel.loc[panel["treated"], "stack"].nunique(),
                         "mean_pre_share_pct": 100 * share.mean()})


def plot(table, main, path):
    fig, ax = plt.subplots(figsize=(7, 4.4), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    x = np.arange(len(WINDOWS))
    for role, color, shift, label in [("treated", SWITCHER, -0.06, "Subreddits that banned AI"),
                                      ("control", CONTROL, 0.06, "Comparison subreddits")]:
        t = table[table["role"] == role].set_index("window").reindex(WINDOWS)
        ax.errorbar(x + shift, t["ai_pct"], yerr=[t["ai_pct"] - t["ci_low"], t["ci_high"] - t["ai_pct"]],
                    color=color, marker="o", ms=6, lw=2, capsize=3, label=label, zorder=3)
    ax.set_xticks(x, ["Before ChatGPT\n(Mar-Aug 2022)", "6 months\nbefore the ban", "6 months\nafter the ban"])
    fig.suptitle("Share of text posts Pangram flags as AI, around a subreddit's AI ban", x=0.01, ha="left",
                 fontsize=12, color=INK)
    ax.set_title(f"{main['n_bans']} bans · {main['n_posts']:,} posts · difference-in-differences "
                 f"{main['did_pp']:+.1f} pp (95% CI {main['ci_low_pp']:+.1f} to {main['ci_high_pp']:+.1f})",
                 loc="left", fontsize=9, color=MUTED)
    ax.set_ylabel("Flagged as AI (%), 95% CI", color=MUTED, fontsize=9)
    ax.set_ylim(bottom=0)
    ax.legend(loc="upper left", frameon=False, fontsize=9, labelcolor=INK)
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.tick_params(colors=MUTED, labelsize=8.5)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)


def main():
    df, n_chosen = load()
    OUTPUT.mkdir(exist_ok=True)
    print(f"{len(df):,} of {n_chosen:,} chosen posts scored")
    pd.set_option("display.width", 200)

    table = window_table(df)
    table.round(3).to_csv(OUTPUT / "ban_ai_share_windows.csv", index=False)
    print(table.round(2).to_string(index=False))

    va_free = df[df["stack"] != df.loc[df["subreddit"] == "VirtualAssistant", "stack"].iloc[0]] \
        if (df["subreddit"] == "VirtualAssistant").any() else df
    specs = [("main: flagged AI, unweighted", did(df)),
             ("flagged AI, weighted to all text posts", did(df, weight="cap_weight")),
             (f"flagged AI, each ban weighted equally (mean of 2x2s, cells of {MIN_CELL}+ posts)", ban_level(df)),
             ("AI fraction of the text, unweighted", did(df, y="fraction_ai")),
             ("flagged AI or Mixed, unweighted", did(df.assign(ai=(df["prediction_short"] != "Human").astype(float)))),
             ("drop the coparenting stack (VirtualAssistant)", did(va_free))]
    est = pd.DataFrame([{"spec": name, **r} for name, r in specs if r])
    est.round(4).to_csv(OUTPUT / "ban_ai_share_estimates.csv", index=False)
    print(est.round(3).to_string(index=False))

    loo = leave_one_out(df)
    loo.round(4).to_csv(OUTPUT / "ban_ai_share_leave_one_out.csv", index=False)
    print(f"leave one subreddit out: {loo['did_pp'].min():+.2f} to {loo['did_pp'].max():+.2f} pp "
          f"(most influential: {loo.iloc[0]['dropped']}, {loo.iloc[-1]['dropped']})")

    het = heterogeneity(pre_ban_share(df))
    het.round(4).to_csv(OUTPUT / "ban_ai_share_heterogeneity.csv", index=False)
    print(het.round(4).to_string(index=False))

    plot(table, est.iloc[0], OUTPUT / "ban_ai_share.png")


if __name__ == "__main__":
    main()
