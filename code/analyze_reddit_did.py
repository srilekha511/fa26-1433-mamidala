"""Baseline event studies around each switcher's mandate: the flaired share of posts, and posts per month.

Usage: python3 code/analyze_reddit_did.py   (after build_reddit_posts.py and select_controls.py)
Writes output/flair_event_study.png, output/flair_did_estimates.csv, output/posts_event_study.png and
output/posts_did_estimates.csv.

Flaired share: each switcher is compared with subreddits whose label stays voluntary for its whole
event window, the voluntary_throughout group and switchers that mandate only after the window ends.
Posts per month: each switcher is compared with its matched controls from select_controls.py.

The estimate is a 2x2 difference-in-differences on the switcher-minus-control gap, six months either
side of the mandate. With four treated subreddits, inference is by placebo dates: the same estimate at
every earlier date whose whole window falls before the mandate (for the flaired share, also after the
label existed) (Roth et al. 2023, section 5.1, on few treated units).
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from reddit_subreddits import FIRST_MONTH, ROOT

DERIVED = ROOT / "data" / "derived"
OUTPUT = ROOT / "output"
RULE_DATES = ROOT / "data" / "hand_coded" / "reddit_rule_dates.csv"
PLOT_K, EST_K = 12, 6  # months either side shown in the plot / used in the estimate
SWITCHER, CONTROL = "#2a78d6", "#eb6834"  # categorical slots 1 and 2
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e6e5e0", "#fcfcfb"


def monthly(panel):
    """One row per subreddit and month (a month split by a rule date is summed back together)."""
    live = panel.assign(live_posts=panel["live_ingest_share"] * panel["posts"])
    m = live.groupby(["subreddit", "month"], as_index=False)[["posts", "ai_flair_posts", "live_posts"]].sum()
    m["share"] = m["ai_flair_posts"] / m["posts"]
    m["live"] = m["live_posts"] / m["posts"]
    m["t"] = pd.PeriodIndex(m["month"], freq="M")
    return m


def controls_for(sub, rules, k=PLOT_K):
    """Subreddits whose label stays voluntary through sub's event window."""
    end = rules.loc[sub, "E"] + (k - 1)
    ok = rules.index[(rules["group"] == "voluntary_throughout")
                     | ((rules["group"] == "switcher") & (rules["E"] > end))]
    return [s for s in ok if s != sub]


def control_share(m, controls, rules):
    """Pooled flaired share of the controls by month, counting each only after its label exists."""
    c = m[m["subreddit"].isin(controls)]
    c = c[c["t"] >= c["subreddit"].map(rules["L"])]
    g = c.groupby("t")[["ai_flair_posts", "posts"]].sum()
    return g["ai_flair_posts"] / g["posts"]


def did(gap, event, k=EST_K):
    """Mean gap in months event..event+k-1 minus mean gap in months event-k..event-1."""
    post = [event + i for i in range(k)]
    pre = [event - i for i in range(1, k + 1)]
    if not all(t in gap.index for t in pre + post):
        return np.nan
    return gap[post].mean() - gap[pre].mean()


def placebo(gap, event, first, k=EST_K):
    """Estimates at earlier dates whose whole window lies between first and the month before event,
    and the two-sided placebo p-value of the estimate at event."""
    dates = pd.period_range(first + k, event - k, freq="M")
    est = [x for x in (did(gap, t, k) for t in dates) if not np.isnan(x)]
    actual = did(gap, event, k)
    p = (1 + sum(abs(x) >= abs(actual) for x in est)) / (1 + len(est)) if est else np.nan
    return len(est), p


def window_means(series, event, k=EST_K):
    return (series.reindex([event - i for i in range(1, k + 1)]).mean(),
            series.reindex([event + i for i in range(k)]).mean())


def flair_study(rules, m, switchers):
    rows, panels = [], []
    for sub in switchers:
        event, controls = rules.loc[sub, "E"], controls_for(sub, rules)
        own = m[m["subreddit"] == sub].set_index("t")
        ctrl = control_share(m, controls, rules)
        gap = (own["share"] - ctrl).dropna()
        n, p = placebo(gap, event, rules.loc[sub, "L"])
        (s0, s1), (c0, c1) = window_means(own["share"], event), window_means(ctrl, event)
        rows.append({"switcher": sub, "mandate_month": str(event), "controls": "; ".join(controls),
                     "share_pre": s0, "share_post": s1, "control_pre": c0, "control_post": c1,
                     "did": did(gap, event), "did_12m": did(gap, event, PLOT_K), "n_placebo_dates": n,
                     "placebo_p": p, "live_share_pre": window_means(own["live"], event)[0]})
        r = rows[-1]
        title = (f"r/{sub}, mandate {event}\nown change {100 * (s1 - s0):+.1f} pp · DiD {100 * r['did']:+.1f} pp "
                 f"(placebo p = {p:.2f})")
        panels.append((title, event, 100 * own["share"], 100 * ctrl, own["live"] < 0.5, controls))
    est = pd.DataFrame(rows)
    est.round(4).to_csv(OUTPUT / "flair_did_estimates.csv", index=False)
    plot(panels, OUTPUT / "flair_event_study.png", "Flaired share of posts around the switch to mandatory AI labels",
         "Posts with an AI flair (%)", "Controls (label still voluntary)", zero_floor=True)
    return est


def posts_study(rules, m, switchers):
    counts = pd.read_csv(DERIVED / "control_monthly_posts.csv")
    counts["t"] = pd.PeriodIndex(counts["month"], freq="M")
    counts["log_posts"] = np.log1p(counts["posts"])
    rows, panels = [], []
    for sub in switchers:
        event = rules.loc[sub, "E"]
        mine = counts[counts["switcher"] == sub]
        own = mine[mine["role"] == "switcher"].set_index("t")["log_posts"]
        ctrl = mine[mine["role"] == "control"].groupby("t")["log_posts"].mean()
        controls = sorted(mine.loc[mine["role"] == "control", "subreddit"].unique())
        gap = (own - ctrl).dropna()
        n, p = placebo(gap, event, pd.Period(FIRST_MONTH, "M"))
        (s0, s1), (c0, c1) = window_means(own, event), window_means(ctrl, event)
        est = did(gap, event)
        rows.append({"switcher": sub, "mandate_month": str(event), "controls": "; ".join(controls),
                     "log_posts_pre": s0, "log_posts_post": s1, "control_pre": c0, "control_post": c1,
                     "did": est, "did_pct": 100 * (np.exp(est) - 1), "did_12m": did(gap, event, PLOT_K),
                     "n_placebo_dates": n, "placebo_p": p})
        title = (f"r/{sub}, mandate {event}\nown change {100 * (np.exp(s1 - s0) - 1):+.0f}% · "
                 f"DiD {rows[-1]['did_pct']:+.0f}% (placebo p = {p:.2f})")
        # Index each line to its own mean over the six months before the mandate, so the plot shows
        # changes on one scale; the estimate uses the raw log gap.
        panels.append((title, event, own - s0, ctrl - c0, None, controls))
    est = pd.DataFrame(rows)
    est.round(4).to_csv(OUTPUT / "posts_did_estimates.csv", index=False)
    plot(panels, OUTPUT / "posts_event_study.png", "Posts per month around the switch to mandatory AI labels",
         "Log posts, relative to pre-mandate mean", "Matched controls (mean, no AI rule)")
    return est


def main():
    rules = pd.read_csv(RULE_DATES).set_index("subreddit")
    rules["L"] = pd.PeriodIndex(rules["label_start"].str[:7], freq="M")
    rules["E"] = pd.PeriodIndex(rules["mandatory_start"].str[:7].fillna("2099-12"), freq="M")
    m = monthly(pd.read_csv(DERIVED / "reddit_subreddit_months.csv"))
    switchers = rules.index[rules["group"] == "switcher"].sort_values(key=lambda s: rules.loc[s, "E"])
    OUTPUT.mkdir(exist_ok=True)
    pd.set_option("display.width", 200)
    for name, study in [("flaired share", flair_study), ("posts per month", posts_study)]:
        if study is posts_study and not (DERIVED / "control_monthly_posts.csv").exists():
            print("\nskipping posts per month: run select_controls.py first")
            continue
        est = study(rules, m, switchers)
        print(f"\n{name}:\n" + est.drop(columns="controls").round(3).to_string(index=False))
        print(f"mean DiD across switchers: {est['did'].mean():+.3f}")


def plot(panels, path, title, ylabel, control_label, zero_floor=False):
    fig, axes = plt.subplots(2, 2, figsize=(10, 7.2), sharex=True, facecolor=SURFACE)
    ks = np.arange(-PLOT_K, PLOT_K)
    for ax, (head, event, own, ctrl, late, controls) in zip(axes.flat, panels):
        ax.set_facecolor(SURFACE)
        months = [event + int(k) for k in ks]
        if late is not None:
            for k in ks[late.reindex(months, fill_value=False).to_numpy()]:
                ax.axvspan(k - 0.5, k + 0.5, color=GRID, lw=0, zorder=0)
        ax.axvline(-0.5, color=MUTED, lw=1, ls=(0, (3, 3)), zorder=1)
        ax.plot(ks, ctrl.reindex(months).to_numpy(), color=CONTROL, lw=2, marker="o", ms=4, zorder=2)
        ax.plot(ks, own.reindex(months).to_numpy(), color=SWITCHER, lw=2, marker="o", ms=4, zorder=3)
        ax.set_title(head, loc="left", fontsize=9.5, color=INK)
        ax.text(0.99, 0.95, "controls: " + ", ".join(controls), transform=ax.transAxes, ha="right", va="top",
                fontsize=7.5, color=MUTED, wrap=True)
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.tick_params(colors=MUTED, labelsize=8)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(GRID)
        if zero_floor:
            ax.set_ylim(bottom=0)
    for ax in axes[1]:
        ax.set_xlabel("Months relative to the mandate", color=MUTED, fontsize=9)
    for ax in axes[:, 0]:
        ax.set_ylabel(ylabel, color=MUTED, fontsize=9)
    handles = [plt.Line2D([], [], color=SWITCHER, lw=2, marker="o", ms=4, label="Switcher"),
               plt.Line2D([], [], color=CONTROL, lw=2, marker="o", ms=4, label=control_label)]
    if any(p[4] is not None for p in panels):
        handles.append(plt.Rectangle((0, 0), 1, 1, color=GRID, label="Captured weeks late (before mid-2023)"))
    fig.suptitle(title, x=0.01, ha="left", y=0.995, fontsize=12, color=INK)
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.005, 0.955), ncol=3, frameon=False,
               fontsize=9, labelcolor=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.91))
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)


if __name__ == "__main__":
    main()
