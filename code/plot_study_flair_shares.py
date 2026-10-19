"""Draw the monthly share of posts carrying an approved AI flair in each study subreddit.

Usage: python3 code/plot_study_flair_shares.py  (after find_ai_flair_subreddits.py and ai_flairs.csv)
Uses the cached flair samples (the newest 100 posts of each month), so it is a first look; the
full panel from build_reddit_posts.py replaces it once all posts are pulled.
Writes output/study_ai_flair_shares.svg and data/derived/flair_sample_shares.csv.
"""

import csv
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from reddit_subreddits import FIRST_MONTH, LAST_MONTH, ROOT, approved_flairs
from arctic import months

CACHE = ROOT / "data" / "raw" / "arctic" / "flair_sample"
INK, MUTED, GRID, ACCENT = "#1a1d23", "#5b6270", "#e3e6eb", "#c2410c"


def sample_shares(flairs):
    """Rows of subreddit, month, sampled posts and posts with an approved AI flair."""
    rows = []
    for sub, approved in sorted(flairs.items()):
        for month in months(FIRST_MONTH, LAST_MONTH):
            path = CACHE / sub / f"{month}.json"
            posts = json.load(open(path)) if path.exists() else []
            n_ai = sum((p.get("link_flair_text") or "").strip() in approved for p in posts)
            rows.append({"subreddit": sub, "month": month, "sampled": len(posts), "ai_flair": n_ai})
    return rows


def main():
    rows = sample_shares(approved_flairs())
    with open(ROOT / "data" / "derived" / "flair_sample_shares.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    by_sub = {}
    for r in rows:
        by_sub.setdefault(r["subreddit"], []).append(r)
    # Largest overall labeled share first, so the panels read from most to least labeling.
    order = sorted(by_sub, key=lambda s: -sum(r["ai_flair"] for r in by_sub[s]) / max(1, sum(r["sampled"] for r in by_sub[s])))
    ms = months(FIRST_MONTH, LAST_MONTH)
    fig, axes = plt.subplots(4, 4, figsize=(10, 7.2), sharex=True)
    plt.rcParams["font.family"] = "Helvetica"
    for ax, sub in zip(axes.flat, order):
        share = [100 * r["ai_flair"] / r["sampled"] if r["sampled"] else None for r in by_sub[sub]]
        ax.plot(range(len(ms)), share, color=ACCENT, lw=2, solid_capstyle="round")
        ax.set_title(f"r/{sub}", fontsize=9.5, color=INK, loc="left")
        ax.set_ylim(0, max(5, max(s for s in share if s is not None) * 1.15))
        ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(decimals=0))
        ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(3))
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.tick_params(colors=MUTED, labelsize=8, length=0)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color(GRID)
        ax.set_xticks([ms.index(f"{y}-01") for y in (2022, 2023, 2024, 2025)], ["2022", "23", "24", "25"])
    for ax in list(axes.flat)[len(order):]:
        ax.axis("off")
    for ax in list(axes.flat)[len(order) - 4:len(order)]:  # lowest drawn panel in each column
        ax.xaxis.set_tick_params(labelbottom=True)
    fig.suptitle("Share of sampled posts with an AI flair, by month", x=0.01, ha="left",
                 fontsize=12, fontweight="bold", color=INK)
    fig.text(0.01, 0.005, "Newest 100 posts per month (all posts in smaller months), Arctic Shift. "
             "Each panel has its own y-axis.", fontsize=8, color=MUTED)
    fig.tight_layout(rect=(0, 0.02, 1, 0.97))
    (ROOT / "output").mkdir(exist_ok=True)
    fig.savefig(ROOT / "output" / "study_ai_flair_shares.svg")
    fig.savefig(ROOT / "output" / "study_ai_flair_shares.png", dpi=150)
    for sub in order:
        n = sum(r["sampled"] for r in by_sub[sub])
        a = sum(r["ai_flair"] for r in by_sub[sub])
        last = by_sub[sub][-1]
        print(f"{sub:22s} sampled {n:5d}  AI-flaired {a:4d} ({100 * a / max(1, n):4.1f}%)  "
              f"Dec 2025 {last['ai_flair']}/{last['sampled']}")


if __name__ == "__main__":
    main()
