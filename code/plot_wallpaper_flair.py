"""Draw the share of r/wallpaper posts carrying the voluntary AI flair, by month.

Usage: python3 code/plot_wallpaper_flair.py  (after code/fetch_flair_counts.py)
Writes output/wallpaper_ai_flair.svg, which the lightning slide embeds.
"""

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
rows = [r for r in csv.DictReader(open(ROOT / "data/raw/flair_counts.csv")) if r["subreddit"] == "wallpaper"]
months = [r["month"] for r in rows]
share = [100 * int(r["ai_flair_posts"]) / int(r["all_posts"]) for r in rows]

W, H = 520, 172
L, R, T, B = 34, 62, 14, 26
YMAX = 34
x = lambda i: L + i * (W - L - R) / (len(months) - 1)
y = lambda v: T + (1 - v / YMAX) * (H - T - B)

ink, muted, grid, accent = "#1a1d23", "#5b6270", "#e3e6eb", "#c2410c"
out = [f'<svg viewBox="0 0 {W} {H}" width="100%" xmlns="http://www.w3.org/2000/svg" '
       'font-family="Inter, Helvetica, Arial, sans-serif" role="img" '
       'aria-label="Monthly share of r/wallpaper posts flaired as AI, 2022 to 2025">']
for v in (0, 10, 20, 30):
    out.append(f'<line x1="{L}" x2="{W - R}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="{grid}" stroke-width="1"/>')
    out.append(f'<text x="{L - 6}" y="{y(v) + 4:.1f}" text-anchor="end" font-size="11" fill="{muted}">{v}%</text>')
for i, m in enumerate(months):
    if m.endswith("-01"):
        out.append(f'<text x="{x(i):.1f}" y="{H - 8}" text-anchor="middle" font-size="11" fill="{muted}">{m[:4]}</text>')
# Moderators introduce the optional flair on 2022-09-22.
i0 = months.index("2022-09") + 21 / 30
out.append(f'<line x1="{x(i0):.1f}" x2="{x(i0):.1f}" y1="{T}" y2="{y(0):.1f}" stroke="{ink}" stroke-width="1.2" stroke-dasharray="3 3"/>')
out.append(f'<text x="{x(i0) + 6:.1f}" y="{T + 10}" font-size="11.5" font-weight="700" fill="{ink}">Sep 2022: mods add “Made by AI” flair</text>')
out.append(f'<text x="{x(i0) + 6:.1f}" y="{T + 25}" font-size="11.5" font-style="italic" fill="{muted}">“Flairing is not required”</text>')
pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(share))
out.append(f'<polyline points="{pts}" fill="none" stroke="{accent}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>')
xe, ye = x(len(share) - 1), y(share[-1])
out.append(f'<circle cx="{xe:.1f}" cy="{ye:.1f}" r="4" fill="{accent}" stroke="#fff" stroke-width="2"/>')
out.append(f'<text x="{xe + 9:.1f}" y="{ye + 4:.1f}" font-size="13" font-weight="700" fill="{ink}">{share[-1]:.0f}%</text>')
out.append(f'<text x="{xe + 9:.1f}" y="{ye + 18:.1f}" font-size="10.5" fill="{muted}">Sep 2025</text>')
out.append("</svg>")
(ROOT / "output").mkdir(exist_ok=True)
(ROOT / "output/wallpaper_ai_flair.svg").write_text("\n".join(out))
print("months", months[0], "to", months[-1], "| last share %.1f%%" % share[-1], "| max %.1f%% in %s" % (max(share), months[share.index(max(share))]))
print("total posts", sum(int(r["all_posts"]) for r in rows), "AI-flaired", sum(int(r["ai_flair_posts"]) for r in rows))
