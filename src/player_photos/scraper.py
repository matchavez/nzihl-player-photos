"""Parse esportsdesk's stats_1team.cfm / personnel.cfm / standings.cfm pages.

Source contract (see memory: nzihl-roster-source, nzihl-roster-coaches-feature):
- Rosters: admin.esportsdesk.com/leagues/stats_1team.cfm?clientid=&leagueid=&teamid=
  (the no-cache admin host already returns server-rendered HTML without
  needing printPage=1 -- that param is only required on the JS-rendered
  www.nzihl.com/www.nzwihl.com front-ends).
- Coaches: admin.esportsdesk.com/leagues/personnel.cfm?clientid=&leagueid=&teamid=
- Standings (for gallery team ordering): admin.esportsdesk.com/leagues/standings.cfm
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from html import unescape
from urllib.parse import urlencode

from .http import fetch_text
from .overrides import normalize_name
from .teams import Team

STATS_URL = "https://admin.esportsdesk.com/leagues/stats_1team.cfm"
PERSONNEL_URL = "https://admin.esportsdesk.com/leagues/personnel.cfm"
STANDINGS_URL = "https://admin.esportsdesk.com/leagues/standings.cfm"
PROFILE_URL = "https://admin.esportsdesk.com/leagues/rosters_profile.cfm"

_PLAYER_LINK = re.compile(
    r'<a[^>]*href="[^"]*playerID=(\d+)[^"]*"[^>]*title="([^"]+)"[^>]*>'
)
_TR_RE = re.compile(r"<tr[^>]*>([\s\S]*?)</tr>", re.IGNORECASE)
_TD_RE = re.compile(r"<td[^>]*>([\s\S]*?)</td>", re.IGNORECASE)
_TH_RE = re.compile(r"<th[^>]*>([\s\S]*?)</th>", re.IGNORECASE)
# Quote-aware tag stripper (a naive `<[^>]+>` breaks on tooltip titles that
# embed a literal `<br />` inside a quoted attribute value).
_TAG_RE = re.compile(r'<(?:"[^"]*"|\'[^\']*\'|[^>"\'])*>')

_PLAYER_STATS_RE = re.compile(r"PLAYER STATISTICS[\s\S]*?TEAM TOTALS", re.IGNORECASE)
_GOALIE_STATS_RE = re.compile(r"GOALIE STATISTICS[\s\S]*?TEAM TOTALS", re.IGNORECASE)

_COACH_TITLES = {"head coach", "assistant coach"}
_COACH_ORDER = {"head coach": 0, "assistant coach": 1}


@dataclass
class Person:
    role: str            # "player" | "coach"
    player_id: int | None  # esportsdesk playerID (players only; None for coaches)
    first: str
    last: str
    number: str | None   # jersey # (players only)
    position: str         # position code (players) or coach title (coaches)


def _clean(td_html: str) -> str:
    return unescape(_TAG_RE.sub("", td_html)).strip()


def _header_index_map(header_row_html: str) -> dict[str, int]:
    return {_clean(th).upper(): i for i, th in enumerate(_TH_RE.findall(header_row_html))}


def fetch_team_html(team: Team) -> str:
    params = {"clientid": team.client_id, "leagueid": team.league_id, "teamid": team.team_id}
    return fetch_text(f"{STATS_URL}?{urlencode(params)}")


def fetch_personnel_html(team: Team) -> str:
    params = {"clientid": team.client_id, "leagueid": team.league_id, "teamid": team.team_id}
    return fetch_text(f"{PERSONNEL_URL}?{urlencode(params)}")


def fetch_standings_html(client_id: int, league_id: int) -> str:
    params = {"clientid": client_id, "leagueid": league_id, "printPage": 1}
    return fetch_text(f"{STANDINGS_URL}?{urlencode(params)}")


def profile_url(team: Team, player_id: int) -> str:
    params = {
        "clientID": team.client_id,
        "leagueID": team.league_id,
        "teamID": team.team_id,
        "playerID": player_id,
        "printPage": 0,
    }
    return f"{PROFILE_URL}?{urlencode(params)}"


def _parse_stat_block(html: str, block_re: re.Pattern, idx_num_default: int) -> list[tuple]:
    """Yield (player_id, full_name, jersey, position_or_none, row_cells) for
    every row in a PLAYER/GOALIE STATISTICS block."""
    block = block_re.search(html)
    if not block:
        return []
    block_html = block.group(0)
    header_match = _TR_RE.search(block_html)
    col = _header_index_map(header_match.group(1)) if header_match else {}
    idx_num = col.get("#", idx_num_default)
    idx_pos = col.get("POSITION")

    out = []
    for row_match in _TR_RE.finditer(block_html):
        row_html = row_match.group(1)
        m = _PLAYER_LINK.search(row_html)
        if not m:
            continue
        player_id = int(m.group(1))
        full_name = m.group(2)
        cells = [_clean(td) for td in _TD_RE.findall(row_html)]
        jersey = cells[idx_num] if idx_num < len(cells) else "-"
        position = cells[idx_pos] if (idx_pos is not None and idx_pos < len(cells)) else ""
        out.append((player_id, full_name, jersey or "-", position))
    return out


def parse_skaters(html: str, team: Team) -> list[Person]:
    rows = _parse_stat_block(html, _PLAYER_STATS_RE, idx_num_default=2)
    people = []
    for player_id, full_name, jersey, position in rows:
        first, last = normalize_name(full_name, team.league, team.team_id, jersey)
        people.append(Person("player", player_id, first, last, jersey, position))
    return people


def parse_goalies(html: str, team: Team) -> list[Person]:
    rows = _parse_stat_block(html, _GOALIE_STATS_RE, idx_num_default=2)
    people = []
    for player_id, full_name, jersey, _position in rows:
        first, last = normalize_name(full_name, team.league, team.team_id, jersey)
        people.append(Person("player", player_id, first, last, jersey, "G"))
    return people


def parse_coaches(html: str, team: Team) -> list[Person]:
    """personnel.cfm: simple 2-col Title/Name table. Name cell holds
    first/last on separate lines within one <td> (a literal newline, not a
    <br>) -- split on whitespace/newlines. Only Head Coach / Assistant Coach
    rows are kept (front-office roles are out of scope)."""
    people = []
    rows = []
    for row_match in _TR_RE.finditer(html):
        cells = [_clean(td) for td in _TD_RE.findall(row_match.group(1))]
        if len(cells) != 2:
            continue
        title = cells[0].strip()
        if title.lower() not in _COACH_TITLES:
            continue
        parts = [p.strip() for p in cells[1].split("\n") if p.strip()]
        if not parts:
            continue
        first_raw, last_raw = (parts[0], " ".join(parts[1:])) if len(parts) > 1 else ("", parts[0])
        first, last = normalize_name(f"{first_raw} {last_raw}".strip(), team.league, team.team_id, f"coach:{title}")
        rows.append((title, first, last))
    rows.sort(key=lambda r: _COACH_ORDER.get(r[0].lower(), 2))
    for title, first, last in rows:
        # Coaches have no esportsdesk playerID exposed on personnel.cfm, so
        # the profile-page photo fallback isn't available for them -- only
        # the naive-guess headshot URL is attempted (see photos.py).
        people.append(Person("coach", None, first, last, None, title))
    return people


def scrape_team(team: Team) -> list[Person]:
    """Players + goalies + coaches for one team. `team.team_id` must be set
    (callers should skip placeholder teams with team_id=None).

    esportsdesk occasionally returns a 200 with an unexpectedly empty/short
    stats page under sustained request volume (observed live during
    development -- not an HTTP-level failure http.py's own retry would
    catch, since the response itself is a "successful" 200). A real NZIHL/
    NZWIHL team is never rostered with zero skaters AND zero goalies, so
    that specific combination is treated as a signal to re-fetch rather
    than trusted as "this team truly has no players."
    """
    assert team.team_id is not None

    skaters: list[Person] = []
    goalies: list[Person] = []
    attempts = 3
    for attempt in range(attempts):
        stats_html = fetch_team_html(team)
        skaters = parse_skaters(stats_html, team)
        goalies = parse_goalies(stats_html, team)
        if skaters or goalies:
            break
        if attempt < attempts - 1:
            time.sleep(2.0 * (attempt + 1))

    people = skaters + goalies
    try:
        personnel_html = fetch_personnel_html(team)
        people += parse_coaches(personnel_html, team)
    except Exception:
        # Best-effort, same philosophy as the roster-PDF repos: a
        # personnel.cfm hiccup shouldn't fail the whole team scrape.
        pass
    return people


# ---- Standings-order helper ---------------------------------------------

_STANDINGS_ROW_RE = re.compile(r"^\|(.+?)\|", re.MULTILINE)


def parse_standings_order(standings_markdown_table: str, teams: list[Team]) -> list[str]:
    """Best-effort: return team short_codes in the order they appear in the
    standings table text (esportsdesk concatenates "<Display Name><CODE>"
    with no separator, e.g. "SkyCity StampedeSCS"). Falls back to the
    registry's declared order for any team that can't be matched."""
    order: list[str] = []
    for team in teams:
        needle = f"{team.display_name}{team.short_code}"
        pos = standings_markdown_table.find(needle)
        order.append((pos if pos >= 0 else 10**9, team.short_code))
    order.sort(key=lambda p: p[0])
    return [code for _pos, code in order]
