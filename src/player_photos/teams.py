"""Team registry for both leagues.

Team IDs, client/league IDs, and short codes are sourced from the sibling
repos matchavez/nzihl-broadcast-rosters and matchavez/nzwihl-broadcast-rosters
(same esportsdesk platform, same teamIDs) and the 2026 Style Guide TLA set.

NZIHL's client/league IDs: clientid=7131, leagueid=35499.
NZWIHL's client/league IDs: clientid=7132, leagueid=35501.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Team:
    league: str          # "nzihl" | "nzwihl"
    team_id: int | None  # esportsdesk teamID; None = not currently fielding a team
    display_name: str
    short_code: str
    client_id: int
    league_id: int

    @property
    def slug(self) -> str:
        """Full name lowercased, spaces -> underscores (matches the UP NEXT
        zip / DVD bounce loop convention used across the broadcast-assets repos)."""
        return self.display_name.lower().replace(" ", "_")


NZIHL_CID, NZIHL_LID = 7131, 35499
NZWIHL_CID, NZWIHL_LID = 7132, 35501

# ---- NZIHL (men's), 2026 ------------------------------------------------
NZIHL_TEAMS: list[Team] = [
    Team("nzihl", 675633, "Canterbury Red Devils", "CRD", NZIHL_CID, NZIHL_LID),
    Team("nzihl", 674109, "Botany Swarm", "BSW", NZIHL_CID, NZIHL_LID),
    Team("nzihl", 674110, "Pure NZ Admirals", "ADM", NZIHL_CID, NZIHL_LID),
    Team("nzihl", 675634, "Dunedin Thunder", "DUN", NZIHL_CID, NZIHL_LID),
    Team("nzihl", 675635, "SkyCity Stampede", "SCS", NZIHL_CID, NZIHL_LID),
    # Auckland Mako: not fielding a team in the 2026 NZIHL season (absent from
    # both the live TEAMS nav and standings.cfm as of 2026-07-11 — confirmed
    # live, not an oversight). Same "no teamID yet" state as the TODO markers
    # in matchavez/hockey's scorebug/summary overlays. Kept in the registry
    # (team_id=None) so the gallery still renders a "not fielding a team this
    # season" placeholder section instead of silently omitting the franchise.
    # Fill in team_id the moment Mako plays a game and a teamID surfaces.
    Team("nzihl", None, "Auckland Mako", "MKO", NZIHL_CID, NZIHL_LID),
]

# ---- NZWIHL (women's), 2026 ---------------------------------------------
NZWIHL_TEAMS: list[Team] = [
    Team("nzwihl", 675636, "Auckland Steel", "AST", NZWIHL_CID, NZWIHL_LID),
    Team("nzwihl", 675637, "Canterbury Inferno", "CIN", NZWIHL_CID, NZWIHL_LID),
    Team("nzwihl", 675638, "Dunedin Thunder Women", "DTW", NZWIHL_CID, NZWIHL_LID),
    Team("nzwihl", 675639, "Wakatipu Wild", "WLD", NZWIHL_CID, NZWIHL_LID),
]

ALL_TEAMS: list[Team] = NZIHL_TEAMS + NZWIHL_TEAMS

LEAGUES: dict[str, list[Team]] = {
    "nzihl": NZIHL_TEAMS,
    "nzwihl": NZWIHL_TEAMS,
}

LEAGUE_DISPLAY_NAMES = {"nzihl": "NZIHL", "nzwihl": "NZWIHL"}


def by_short_code(league: str, code: str) -> Team | None:
    for t in LEAGUES.get(league, []):
        if t.short_code == code.upper():
            return t
    return None
