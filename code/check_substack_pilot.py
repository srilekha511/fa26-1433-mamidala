"""Check the hand-coded Substack pilot sheet and summarize it.

Usage: python3 code/check_substack_pilot.py [path]   (default data/hand_coded/substack_pilot.csv)

Rows with checked_on blank are counted as not yet done and otherwise ignored. For the rest it reports entries
that break the coding rules, then:
  - status by window: the July 21 to August posts show whether "unavailable" ever appears without the author
    turning detection off (a statement or a pattern by window would say so),
  - statements by status: whether writers who disable detection explain themselves instead,
  - Pangram's scores for the scannable posts,
  - seconds per post, projected to the hours needed for HAND_TARGET posts.
"""

import sys

import pandas as pd

from substack_pilot import OUT

STATUSES = {"scannable", "unavailable", "no_option"}
# Why the popup says detection is unavailable: none_shown (the author's choice, as far as a reader can tell) or
# a reason the popup gives. Only sheets with an unavailable_reason column are checked for it.
REASONS = {"none_shown", "paid_only", "too_short", "before_launch"}
PCTS = ["ai_pct", "ai_assisted_pct", "human_pct"]
HAND_TARGET = 200
SUM_TOLERANCE = 2  # the popup rounds each percentage
AI_FLAG = 50  # ai_pct at or above this is shown in the publication sequences


def problems(df):
    """One message per entry that breaks the coding rules, keyed by post_id."""
    out = []
    for _, r in df.iterrows():
        pid = r["post_id"]
        if r["status"] not in STATUSES:
            out.append(f"{pid}: status {r['status']!r} is not one of {sorted(STATUSES)}")
        if r["statement"] not in ("yes", "no"):
            out.append(f"{pid}: statement {r['statement']!r} should be yes or no")
        if r["statement"] == "yes" and not r["statement_text"]:
            out.append(f"{pid}: statement is yes but statement_text is blank")
        if r["statement"] == "no" and r["statement_text"]:
            out.append(f"{pid}: statement is no but statement_text is filled in")
        if "unavailable_reason" in r:
            reason = r["unavailable_reason"]
            if r["status"] == "unavailable" and reason not in REASONS:
                out.append(f"{pid}: unavailable_reason {reason!r} is not one of {sorted(REASONS)}")
            if r["status"] != "unavailable" and reason:
                out.append(f"{pid}: {r['status']} but has unavailable_reason {reason!r}")
        pcts = [pd.to_numeric(r[c], errors="coerce") for c in PCTS]
        filled = [p for p in pcts if pd.notna(p)]
        if r["status"] == "scannable":
            if len(filled) != 3:
                out.append(f"{pid}: scannable but not all of {PCTS} are numbers")
            elif abs(sum(filled) - 100) > SUM_TOLERANCE:
                out.append(f"{pid}: percentages sum to {sum(filled):g}, not 100")
        elif filled:
            out.append(f"{pid}: {r['status']} but has percentages")
        if r["seconds"] and pd.isna(pd.to_numeric(r["seconds"], errors="coerce")):
            out.append(f"{pid}: seconds {r['seconds']!r} is not a number")
    return out


def patterns(done):
    """Per publication: always scannable, always unavailable, or switches; with the statuses in date order
    (U unavailable, S scannable, N no option; S78 means scannable with 78% AI)."""
    def code(r):
        if r["status"] == "scannable":
            ai = pd.to_numeric(r["ai_pct"], errors="coerce")
            return "S" + (f"{ai:g}" if pd.notna(ai) and ai >= AI_FLAG else "")
        return {"unavailable": "U", "no_option": "N"}.get(r["status"], "?")
    rows = []
    for pub, g in done.sort_values("post_date").groupby("publication", sort=True):
        statuses = set(g["status"])
        rows.append({"publication": pub, "sequence": " ".join(g.apply(code, axis=1)),
                     "pattern": "switches" if len(statuses) > 1 else f"always {statuses.pop()}"})
    return pd.DataFrame(rows)


def summarize(df):
    done = df[df["checked_on"] != ""]
    lines = [f"{len(done)} of {len(df)} posts checked"]
    if done.empty:
        return lines
    lines += ["", "Status by window:", pd.crosstab(done["status"], done["window"], margins=True).to_string()]
    lines += ["", "Statement by status:", pd.crosstab(done["status"], done["statement"], margins=True).to_string()]
    pats = patterns(done)
    lines += ["", "Publications by pattern (posts in date order):", pats["pattern"].value_counts().to_string()]
    switched = pats[pats["pattern"] == "switches"]
    if not switched.empty:
        lines += ["", "Publications that switch:", switched[["publication", "sequence"]].to_string(index=False)]
    scanned = done[done["status"] == "scannable"]
    if not scanned.empty:
        lines += ["", "Pangram scores on scannable posts (%):",
                  scanned[PCTS].apply(pd.to_numeric, errors="coerce").describe().round(1).to_string()]
    secs = pd.to_numeric(done["seconds"], errors="coerce").dropna()
    if not secs.empty:
        lines += ["", f"Seconds per post: median {secs.median():.0f}, mean {secs.mean():.0f}, max {secs.max():.0f}",
                  f"{HAND_TARGET} posts at the mean: {HAND_TARGET * secs.mean() / 3600:.1f} hours"]
    return lines


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else OUT
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    for c in ["status", "statement"]:
        df[c] = df[c].str.strip().str.lower()
    found = problems(df[df["checked_on"] != ""])
    print("\n".join(summarize(df)))
    print(f"\n{len(found)} problems" + (":\n  " + "\n  ".join(found) if found else ""))


if __name__ == "__main__":
    main()
