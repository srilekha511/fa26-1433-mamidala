"""Subreddit lists for the Reddit sample."""

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AI_FLAIRS = ROOT / "data" / "hand_coded" / "ai_flairs.csv"
FIRST_MONTH, LAST_MONTH = "2022-01", "2025-12"

# Starting candidates: text-first communities where AI-written posts are plausible.
# Add to this list freely; find_ai_flair_subreddits.py keeps only those with an AI flair.
SEED_SUBREDDITS = [
    "WritingPrompts", "writing", "shortstories", "FanFiction", "HFY", "nosleep", "OCPoetry",
    "Poetry", "poetry_critics", "fantasywriters", "scifiwriting", "KeepWriting",
    "DestructiveReaders", "creativewriting", "Screenwriting", "selfpublish", "copywriting",
    "Blogging", "AmItheAsshole", "AITAH", "tifu", "relationship_advice", "TrueOffMyChest",
    "offmychest", "confession", "Showerthoughts", "LifeProTips", "explainlikeimfive",
    "Teachers", "Professors", "cscareerquestions", "learnprogramming",
    # None of the text communities above had an AI disclosure flair (2026-10-11 inventory).
    # These are image, art, music and fan communities whose Nov 2024 rules ask for AI posts to
    # be flaired or tagged, from the AIRules dataset (Lloyd et al., CHI 2025,
    # github.com/sTechLab/AIRules), plus r/wallpaper's optional "Made by AI" flair.
    "wallpaper", "MobileWallpaper", "BeAmazed", "overlord", "Gintama", "TheNightFeeling",
    "Drizzy", "NikkeMobile", "HybridAnimals", "Shrek", "moths", "redrising",
    "TheEminenceInShadow", "sticker", "FantasyMaps", "Simpsons", "industrialmusic", "oneshot",
    "TarotDecks", "atrioc", "Frozen", "MartialMemes", "Disgaea", "GloriousTomBombadil",
    "MoriCalliope", "JingLiu", "PRYudiposting", "animearmor", "PeacefulSolitude",
    "houkai3rd", "RimWorld", "Avatarthelastairbende", "Dolls",
]


def approved_flairs(path=AI_FLAIRS):
    """Subreddit -> set of flair texts approved as AI labels."""
    out = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            out.setdefault(row["subreddit"].strip(), set()).add(row["flair_text"].strip())
    return out


def study_subreddits():
    return sorted(approved_flairs())
