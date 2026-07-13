"""Build the static index.html gallery from manifest.json.

One section per team in league/standings order (falls back to the team
registry's declared order when a live standings order isn't supplied),
thumbnail grid with name + number, initials placeholder tiles for missing
photos, and a per-team "missing photos" count (doubles as a chase-list for
teams). Self-contained: no JS frameworks, one file, renders via GitHub Pages.
"""
from __future__ import annotations

import html as html_lib

CSS = """
:root{--bg:#0b0c0f;--panel:#15171c;--line:#262a33;--ink:#f2f3f5;--muted:#9aa0ab;--accent:#5fb0ff;--miss:#3a2226;--missink:#ff9b9b;}
*{box-sizing:border-box;}
body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,Arial,sans-serif;}
header{padding:28px 24px 12px;border-bottom:1px solid var(--line);}
header h1{margin:0 0 4px;font-size:22px;}
header p{margin:0;color:var(--muted);font-size:13.5px;}
main{padding:20px 24px 60px;max-width:1200px;margin:0 auto;}
nav.leaguejump{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0 4px;}
nav.leaguejump a{color:var(--accent);text-decoration:none;font-size:12.5px;border:1px solid var(--line);padding:5px 10px;border-radius:20px;}
nav.leaguejump a:hover{border-color:var(--accent);}
h2.league-head{margin:34px 0 6px;font-size:18px;letter-spacing:.04em;color:var(--muted);text-transform:uppercase;}
section.team{margin:22px 0;padding:16px;background:var(--panel);border:1px solid var(--line);border-radius:14px;}
.team-head{display:flex;align-items:baseline;justify-content:space-between;flex-wrap:wrap;gap:8px;margin-bottom:12px;}
.team-head h3{margin:0;font-size:16px;}
.team-head .code{color:var(--muted);font-weight:600;font-size:12px;margin-left:8px;}
.missing-badge{font-size:11.5px;padding:3px 9px;border-radius:20px;background:var(--miss);color:var(--missink);border:1px solid #5a2b30;}
.missing-badge.zero{background:#132a1c;color:#8fe0ab;border-color:#1f4a30;}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(110px,1fr));gap:12px;}
.person{text-align:center;}
.thumb{width:100%;aspect-ratio:3/4;border-radius:10px;object-fit:cover;background:#1d2027;display:block;border:1px solid var(--line);}
.thumb.placeholder{display:flex;align-items:center;justify-content:center;font-size:26px;font-weight:700;color:var(--muted);}
.pname{font-size:12px;margin-top:6px;line-height:1.25;}
.pnum{color:var(--muted);font-size:11px;}
.pstat{color:var(--accent);font-size:10px;margin-top:2px;line-height:1.25;}
.inactive{opacity:.4;}
.inactive .pname::after{content:" (inactive)";color:var(--missink);font-size:10px;}
.empty-note{color:var(--muted);font-size:12.5px;padding:6px 2px;}
footer{padding:20px 24px 40px;color:var(--muted);font-size:11.5px;text-align:center;}
"""


def _initials(first: str, last: str) -> str:
    a = (first[:1] or "").upper()
    b = (last[:1] or "").upper()
    return (a + b) or "?"


def _person_card(entry: dict, stat_line: str | None = None) -> str:
    name = html_lib.escape(entry.get("name", ""))
    number = entry.get("number")
    role = entry.get("role")
    photo = entry.get("photo")
    active = entry.get("active", True)
    sub = f"#{number}" if number else html_lib.escape((entry.get("position") or "").upper())
    cls = "person" + ("" if active else " inactive")
    if photo:
        img = f'<img class="thumb" loading="lazy" src="{html_lib.escape(photo)}" alt="{name}">'
    else:
        first_last = entry.get("name", "").split(" ", 1)
        initials = _initials(first_last[0] if first_last else "", first_last[1] if len(first_last) > 1 else "")
        img = f'<div class="thumb placeholder">{html_lib.escape(initials)}</div>'
    stat_html = f'<div class="pstat">{html_lib.escape(stat_line)}</div>' if stat_line else ""
    return (
        f'<div class="{cls}">{img}'
        f'<div class="pname">{name}</div>'
        f'<div class="pnum">{sub}</div>{stat_html}</div>'
    )


def _team_section(league_key: str, short_code: str, team_block: dict, stats_index: dict | None = None) -> str:
    people = list(team_block.get("people", {}).values())
    # active first, then inactive; players before coaches; then by number/name
    def sort_key(p):
        try:
            num = int(p.get("number") or 9999)
        except ValueError:
            num = 9999
        return (
            0 if p.get("active", True) else 1,
            0 if p.get("role") == "player" else 1,
            num,
            p.get("name", ""),
        )
    people.sort(key=sort_key)
    active_people = [p for p in people if p.get("active", True)]
    missing = sum(1 for p in active_people if not p.get("photo"))
    badge_cls = "missing-badge zero" if missing == 0 else "missing-badge"
    def _stat_for(p):
        if not stats_index or p.get("role") != "player":
            return None
        return stats_index.get((league_key, short_code, str(p.get("number") or "")))
    cards = "".join(_person_card(p, _stat_for(p)) for p in people) or '<p class="empty-note">No roster data yet.</p>'
    team_id_note = ""
    if team_block.get("no_team_id"):
        cards = '<p class="empty-note">Not fielding a team this season -- no roster to scrape yet.</p>'
        badge_cls = "missing-badge zero"
        missing = 0
    anchor = f'{league_key}-{team_block.get("slug","")}'
    return f"""
  <section class="team" id="{anchor}">
    <div class="team-head">
      <h3>{html_lib.escape(team_block.get('display_name',''))}<span class="code">{html_lib.escape(short_code)}</span></h3>
      <span class="{badge_cls}">{missing} missing photo{'s' if missing != 1 else ''}</span>
    </div>
    <div class="grid">{cards}</div>
  </section>"""


def build_gallery_html(manifest: dict, league_order: dict[str, list[str]], league_display: dict[str, str], stats_index: dict | None = None) -> str:
    leagues = manifest.get("leagues", {})
    nav_links = []
    body_sections = []
    total_missing = 0
    total_active = 0

    for league_key, short_codes in league_order.items():
        league_block = leagues.get(league_key, {"teams": {}})
        teams_by_code = league_block.get("teams", {})
        nav_links.append(f'<a href="#lg-{league_key}">{html_lib.escape(league_display.get(league_key, league_key.upper()))}</a>')
        body_sections.append(f'<h2 class="league-head" id="lg-{league_key}">{html_lib.escape(league_display.get(league_key, league_key.upper()))}</h2>')
        for code in short_codes:
            team_block = teams_by_code.get(code, {"display_name": code, "short_code": code, "slug": code.lower(), "people": {}})
            for p in team_block.get("people", {}).values():
                if p.get("active", True):
                    total_active += 1
                    if not p.get("photo"):
                        total_missing += 1
            body_sections.append(_team_section(league_key, code, team_block, stats_index))

    generated = html_lib.escape(manifest.get("generated_at", ""))
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NZIHL / NZWIHL Player Photo Warehouse</title>
<style>{CSS}</style>
</head>
<body>
<header>
  <h1>Player Photo Warehouse</h1>
  <p>NZIHL &amp; NZWIHL rostered players and coaches &middot; {total_active} active people, {total_missing} missing a photo &middot; generated {generated}</p>
  <nav class="leaguejump">{''.join(nav_links)}</nav>
</header>
<main>
{''.join(body_sections)}
</main>
<footer>Auto-generated weekly from esportsdesk by matchavez/nzihl-player-photos. Missing photos fall back to initials tiles on broadcast graphics -- this page doubles as a chase-list for teams.</footer>
</body>
</html>
"""
