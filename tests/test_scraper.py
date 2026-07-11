from pathlib import Path

from player_photos.scraper import parse_skaters, parse_goalies, parse_coaches, parse_standings_order
from player_photos.teams import by_short_code

FIXTURES = Path(__file__).parent / "fixtures"


def _adm():
    return by_short_code("nzihl", "ADM")


def test_parse_skaters_from_fixture():
    html = (FIXTURES / "team_min.html").read_text()
    team = _adm()
    skaters = parse_skaters(html, team)
    names = {(p.first, p.last, p.number, p.position) for p in skaters}
    assert ("Benjamin", "De Jonge", "26", "F") in names
    assert ("Scott", "Henry", "4", "D") in names
    assert ("Nash", "Hayward Jones", "19", "F") in names
    # player_id captured for the profile-page photo fallback
    dj = next(p for p in skaters if p.last == "De Jonge")
    assert dj.player_id == 2479057
    assert dj.role == "player"


def test_parse_goalies_from_fixture():
    html = (FIXTURES / "team_min.html").read_text()
    team = _adm()
    goalies = parse_goalies(html, team)
    assert len(goalies) == 1
    g = goalies[0]
    assert (g.first, g.last, g.number, g.position) == ("Eythan", "Prendergast", "30", "G")


def test_parse_coaches_from_fixture():
    html = (FIXTURES / "personnel_min.html").read_text()
    team = _adm()
    coaches = parse_coaches(html, team)
    # Only Head Coach / Assistant Coach kept, front-office roles dropped,
    # Head Coach sorted before Assistant Coach.
    assert [ (c.position, c.first, c.last) for c in coaches ] == [
        ("Head Coach", "Blake", "Jackson"),
        ("Assistant Coach", "Rodney", "McMillin"),
        ("Assistant Coach", "Cameron", "Stephen"),
    ]
    assert all(c.role == "coach" and c.player_id is None for c in coaches)


def test_parse_coaches_none_listed():
    html = (FIXTURES / "personnel_no_coaches.html").read_text()
    coaches = parse_coaches(html, _adm())
    assert coaches == []


def test_parse_standings_order():
    md = (FIXTURES / "standings_min.md").read_text()
    from player_photos.teams import NZIHL_TEAMS
    fielding = [t for t in NZIHL_TEAMS if t.team_id is not None]
    order = parse_standings_order(md, fielding)
    assert order == ["SCS", "ADM", "DUN", "CRD", "BSW"]
