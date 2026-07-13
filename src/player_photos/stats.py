"""Fetch skater/goalie season stats from the two roster repos' stats.json
(matchavez/nzihl-broadcast-rosters, matchavez/nzwihl-broadcast-rosters) and
build a lookup the gallery can use to print a small stat line under each
active player's photo.

stats.json is the canonical G/A/PTS + goalie-record source (see that repo's
memory.md -- skater totals are pulled from the season-data warehouse,
goalie fields straight off the live team page). We fetch it fresh at gallery
-build time rather than folding it into manifest.json, since manifest.json's
job is the photo/hash record and stats change on a different cadence.

Joined on (league, team short_code, jersey number) -- deliberately not name,
since esportsdesk names need the override table ([[nzihl-player-name-overrides]])
and number is already the unique key stats.json itself uses.
"""
from __future__ import annotations

import sys

import requests

STATS_URLS = {
    "nzihl": "https://raw.githubusercontent.com/matchavez/nzihl-broadcast-rosters/main/stats.json",
    "nzwihl": "https://raw.githubusercontent.com/matchavez/nzwihl-broadcast-rosters/main/stats.json",
}


def _fetch_one(league: str) -> dict:
    url = STATS_URLS[league]
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  [warn] stats.json fetch failed for {league}: {e}", file=sys.stderr)
        return {}


def _skater_line(s: dict) -> str | None:
    gp = s.get("gp") or 0
    if not gp:
        return None
    g, a, pts = s.get("g", 0), s.get("a", 0), s.get("pts", 0)
    return f"{pts} PTS ({g}G {a}A)"


def _goalie_line(g: dict) -> str | None:
    gp = g.get("gp") or 0
    if not gp:
        return None
    w, l = g.get("w", 0), g.get("l", 0)
    gaa = g.get("gaa", "-")
    sv_pct = g.get("sv_pct", "-")
    return f"{w}-{l}, {gaa} GAA, {sv_pct} SV%"


def build_stats_index() -> dict[tuple[str, str, str], str]:
    """Returns {(league, short_code, number): 'small stat line'} for every
    skater/goalie with at least one game played. Silently empty (not an
    error) for a league whose fetch fails -- gallery just omits stat lines
    for that league rather than breaking the whole build."""
    index: dict[tuple[str, str, str], str] = {}
    for league in STATS_URLS:
        data = _fetch_one(league)
        teams = data.get("teams", {})
        for code, team_block in teams.items():
            for s in team_block.get("skaters", []):
                number = str(s.get("number") or "")
                if not number:
                    continue
                line = _skater_line(s)
                if line:
                    index[(league, code, number)] = line
            for g in team_block.get("goalies", []):
                number = str(g.get("number") or "")
                if not number:
                    continue
                line = _goalie_line(g)
                if line:
                    index[(league, code, number)] = line
    return index
