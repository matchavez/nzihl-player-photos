# nzihl-player-photos

Weekly warehouse of NZIHL/NZWIHL rostered players' and coaches' headshots,
scraped from esportsdesk into a committed, version-controlled archive -- so
broadcast graphics can pull a photo from this repo instead of live-fetching
it from esportsdesk during a broadcast.

**This repo is a data source, not a browsable page.** It used to also
publish its own gallery UI via GitHub Pages; that was retired 2026-07-13 in
favor of a single consolidated view at
[matchavez.com/hockey/warehouse/#photos](https://matchavez.com/hockey/warehouse/#photos),
which fetches this repo's `manifest.json` live (plus stat lines from the
roster repos' `stats.json`). This repo's own Pages URL now just redirects
there. Browse photos at the warehouse link above, not here.

## Why this exists

The live broadcast overlays (`matchavez/hockey`) already resolve player
photos on the fly (a naive filename guess, with a profile-page fallback for
ad-hoc filenames). That works, but it means every photo lookup is a live
network round-trip during a broadcast, with no record of who has a real
photo and who doesn't. This repo runs the same kind of resolution logic
**once a week** and saves the result as real files + a manifest that the
warehouse page (and, eventually, the live overlays themselves) can consume
instead of live-fetching. Migrating the live overlays to consume this
warehouse is a deliberate follow-up, not part of this repo.

## What it produces

Each run:

1. Scrapes the current roster (players + coaches) for all 6 NZIHL and all 4
   NZWIHL teams from esportsdesk's `stats_1team.cfm` / `personnel.cfm`
   print-page views (same source as `nzihl-broadcast-rosters` /
   `nzwihl-broadcast-rosters`).
2. Resolves a headshot for every person and saves it to
   `photos/<league>/<team_slug>/<Name_No_Spaces>.jpg`, or records them as
   missing (broadcast graphics already fall back to an initials tile, so a
   missing photo is an expected, tracked state -- not an error).
3. Writes `manifest.json`: per league -> per team -> per person, with name,
   number/position, photo path (or null), source URL, sha256, first-seen /
   last-verified dates, and an `active` flag.
4. Writes `index.html` as a plain redirect stub to
   [matchavez.com/hockey/warehouse/#photos](https://matchavez.com/hockey/warehouse/#photos)
   -- see "Why this exists" above. Not a data product; just keeps this
   repo's old Pages URL from 404ing.

A run that finds no new/changed photos produces an **empty git diff** --
files are only rewritten when their content actually changes (hash-compared
against what's already committed).

**Departed players are never deleted.** If someone drops off a roster
they're marked `"active": false` in `manifest.json` and keep their existing
photo file -- they still show up in season retrospectives.

## URL contract

- Rosters: `https://admin.esportsdesk.com/leagues/stats_1team.cfm?clientid=<CID>&leagueid=<LID>&teamid=<teamID>`
- Coaches: `https://admin.esportsdesk.com/leagues/personnel.cfm?clientid=<CID>&leagueid=<LID>&teamid=<teamID>`
  (only "Head Coach" / "Assistant Coach" rows kept; front-office roles dropped)
- NZIHL: `clientid=7131, leagueid=35499`. NZWIHL: `clientid=7132, leagueid=35501`.
- Headshot "naive guess": `https://admin.esportsdesk.com/media/leagues/6795/graphics/<FirstLast>.jpg`
  (whitespace stripped, case preserved -- media folder `6795` is shared by
  both leagues). Misses on ad-hoc filenames (different case/extension, or
  unrelated names like Dunedin Thunder's `LukeEASPORT.png`).
- Headshot fallback (authoritative, used whenever the naive guess misses and
  we have the person's esportsdesk `playerID`): fetch their public profile
  page (`rosters_profile.cfm?clientID=&leagueID=&teamID=&playerID=&printPage=0`)
  and read the real photo path off the `.largeHeadshot` CSS
  `background-image`. Coaches have no `playerID` on `personnel.cfm`, so only
  the naive guess is available for them.

### Gotcha: esportsdesk's "no photo" placeholder looks like a real 200

A missing image is **not** always a real HTTP 404. Two failure modes exist,
both handled:

- A genuinely missing naive-guess filename returns **200 OK with an HTML
  "not found" page body** (`Content-Type: text/html`), not a 404 status.
- A player/coach with no uploaded headshot has their profile page's
  `.largeHeadshot` **set to a real, valid, 200-status square team-logo
  image** as esportsdesk's own "no photo" placeholder (observed: a 100x100
  crop of the team crest). This is a real image that decodes fine -- it is
  NOT distinguishable from a genuine photo by status code or Content-Type.

So every candidate is validated by: `Content-Type` starts with `image/`,
the bytes actually decode as an image, **and** both dimensions are >= 150px.
The placeholder is consistently served at exactly 100x100 (confirmed across
multiple teams/filenames -- both a generic team-crest crop and a team's own
small logo file); the smallest confirmed-real photo is 150x199/150x200
(Dunedin-style ad-hoc uploads), so the cutoff sits comfortably between the
two. Size, not aspect ratio, is what distinguishes a real photo from the
placeholder -- an earlier version of this check rejected anything non-portrait
on the (wrong) assumption that all real headshots are portrait, which
misclassified SkyCity Stampede's Lachlan Frear's genuine 600x600 SQUARE
headshot as a placeholder. This guard was added after Pure NZ Admirals #26
Benjamin De Jonge's naive guess AND profile-page fallback both initially
resolved to the Admirals' 100x100 team-logo placeholder.

## Filename normalization

`<Name_No_Spaces>` = first + last with only **whitespace** stripped;
everything else is preserved as-is:

| Input | Output |
|---|---|
| `Nash` `Hayward Jones` | `NashHaywardJones` |
| `Joel` `Keogh-Cope` | `JoelKeogh-Cope` (hyphen kept) |
| `Liam` `O'Brien` | `LiamO'Brien` (apostrophe kept) |
| `Mere` `Ngāwhare` | `MereNgāwhare` (macron kept) |

Same convention as the live overlays' `shotURL()` in `matchavez/hockey`, so
a filename here always matches what the naive-guess URL would have been.

## Name overrides

Ported from the two roster-PDF repos (`SURNAME_OVERRIDES`, keyed by
`(league, team_id, jersey)`), plus a generic multi-word-surname allowlist
and parenthetical-stripping (maiden names, nicknames). Both known cases are
regression-tested:

- Pure NZ Admirals #26 **Benjamin De Jonge** -- two-word surname, not split
  at the last space.
- Canterbury Inferno #3 **Reagyn Shattock** -- esportsdesk stores her as
  "Shattock (Niskakoski)"; the maiden-name parenthetical is stripped.

These overrides affect the **display name and saved filename**, not photo
*lookup* -- the profile-page fallback is keyed by `playerID`, so it finds
the right person's real photo regardless of any surname-splitting bug.

## Auckland Mako

Not fielding a team in the 2026 NZIHL season (absent from both the live
`TEAMS` nav and `standings.cfm` as of 2026-07-11) -- same "no teamID yet"
state as the `TODO @publish` markers already in `matchavez/hockey`'s
scorebug/summary overlays. Kept in the team registry with `team_id=None` so
consumers (the warehouse page, `manifest.json`'s `no_team_id` flag) can
render a "not fielding a team this season" placeholder instead of silently
omitting the franchise. Fill in `team_id` in
`src/player_photos/teams.py` the moment Mako plays a game.

## Project layout

```
src/player_photos/
  teams.py       # registry: league, team_id, short_code, client/league IDs
  overrides.py   # name-override tables + splitting/title-casing
  scraper.py     # parses stats_1team.cfm / personnel.cfm / standings.cfm
  photos.py      # headshot resolution (naive guess + profile-page fallback)
  manifest.py    # manifest.json read/merge/upsert, filename normalization
  gallery.py     # index.html generator -- now just a redirect stub to hockey/warehouse
  cli.py         # orchestration: scrape -> resolve -> write -> manifest -> redirect stub
.github/workflows/build-photos.yml   # weekly cron (Thu 19:00 UTC) + workflow_dispatch
manifest.json    # committed per-person photo manifest -- the actual data product
index.html       # redirect stub -> hockey/warehouse/#photos (served by GitHub Pages)
photos/          # committed headshots, <league>/<team_slug>/<Name>.jpg
tests/           # fixture + mock-driven unit tests, no live network needed
```

## Quick start (local)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .

# Full run against every team, writing into the repo root:
python -m player_photos --output-dir .

# One team only, useful for testing a single override/photo:
python -m player_photos --output-dir . --teams-only ADM,CIN
```

## Testing

```bash
PYTHONPATH=src python -m pytest tests/
```

All tests run against fixtures and mocks -- no live network required. The
CI workflow additionally does a real end-to-end scrape as part of every
run, so upstream HTML drift surfaces as a workflow failure.

## Robustness (learned live, during acceptance testing)

Two upstream quirks surfaced only once this ran against every real team,
not just a couple during development:

- **esportsdesk occasionally returns a 200 with an unexpectedly short/empty
  stats page** under sustained request volume -- not an HTTP-level failure,
  just a "successful" response with much less content than expected.
  `scraper.scrape_team()` retries the whole team fetch (up to 3 attempts,
  backoff) if a team parses to zero skaters AND zero goalies, since a real
  rostered team is never actually empty. `http.py`'s `fetch_text`/
  `fetch_binary` separately retry on network-level exceptions. Caught live:
  Auckland Steel was recorded with only 3 people (should be ~37) in the
  first production run.
- **A real headshot can be square, not just portrait.** An earlier version
  of `_is_plausible_headshot()` rejected anything non-portrait, on the
  assumption real photos are always portrait (~600x750+) and esportsdesk's
  placeholder is a square crop. That logic misclassified SkyCity Stampede's
  Lachlan Frear's genuine 600x600 square headshot as a placeholder --
  caught because Stampede's hit rate (4/34) was a visible outlier next to
  every other NZIHL team (70-90%). Fixed to reject by **size** instead
  (both dimensions >= 150px) -- the placeholder is consistently exactly
  100x100 regardless of which team/filename serves it.

`manifest.json`'s top-level `generated_at` is **date granularity, not a full timestamp** -- a full
timestamp would "change" on every single run and defeat the "no real
changes -> empty git diff" idempotency contract even when zero photos
actually changed.

## Automation

Runs weekly, Thursday 19:00 UTC (Friday 07:00 NZST winter / 08:00 NZDT
summer). Trigger a run manually any time:

```bash
gh workflow run "Build player photo warehouse"
```

Politeness: all esportsdesk requests (roster pages, personnel pages,
profile-page fallbacks, image downloads) share one throttle enforcing
>=1 second between requests.

## Related repos

- **matchavez/nzihl-broadcast-rosters** / **nzwihl-broadcast-rosters** --
  same esportsdesk platform/team IDs, source of the name-override
  conventions ported here.
- **matchavez/hockey** -- the live broadcast overlays this warehouse is
  eventually meant to back (not yet wired up, deliberate follow-up), and
  home of `warehouse/index.html`, the actual browsable UI for this repo's
  photos (see top of this file).
