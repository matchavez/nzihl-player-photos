# memory.md — matchavez/nzihl-player-photos

Self-context for Claude. README.md is human-facing (URL contract, filename
rules, quick start). This file adds automation state, design decisions and
gotchas README doesn't need to spell out. Created 2026-07-11 (initial build).

## What this repo is

Weekly GitHub Action (`build-photos.yml`, cron `0 19 * * 4` = Thu 19:00 UTC)
that scrapes every rostered NZIHL/NZWIHL player + coach's headshot from
esportsdesk into a committed archive (`photos/<league>/<team_slug>/<Name>.jpg`),
writes `manifest.json`, and regenerates a static `index.html` gallery served
by GitHub Pages. Built as a warehouse the live broadcast overlays
(`matchavez/hockey`) can eventually consume instead of live-fetching photos
during a broadcast -- that migration is explicitly NOT done yet (task
scope said don't touch the Game Summary's live headshot URLs).

## Layout

`src/player_photos/{teams,overrides,scraper,photos,manifest,gallery,cli}.py`,
`tests/` (fixture + monkeypatch-driven, no live network -- 43 tests as of
initial build), `.github/workflows/build-photos.yml`.

## Key design decisions (things a future me would otherwise re-derive)

**Photo resolution order:** try the naive-guess URL first (fast, one
request), fall back to the profile-page (`rosters_profile.cfm`) scrape only
if the guess misses. The profile-page fallback is keyed by esportsdesk
`playerID` (captured from the same `<a href="...playerID=...">` anchor the
roster scrape already parses), so it's immune to any name-splitting/override
bug -- this is WHY De Jonge/Shattock "resolve correctly": the photo lookup
never depends on how their name was split, only the saved filename does.

**The false-positive that shaped `_is_plausible_headshot`:** esportsdesk
does NOT reliably 404 a missing image. Two distinct failure modes exist and
both had to be handled:
1. Missing naive-guess filename -> 200 OK with an HTML "not found" page body
   (`Content-Type: text/html`). Caught by requiring `Content-Type` to start
   with `image/`.
2. A player/coach with NO uploaded photo has their profile page's
   `.largeHeadshot` background-image literally set to a **real, valid,
   200-status, image/jpeg, 100x100 square crop of the team crest (or, for
   some teams, their own small team-logo file -- also served at 100x100)**
   -- esportsdesk's own UI "no photo" placeholder, baked into the HTML, not
   a fetch-layer artifact. This is genuinely indistinguishable from a real
   photo by status/content-type/decodability alone. Caught live during dev:
   Pure NZ Admirals #26 Benjamin De Jonge's naive guess AND his profile-page
   fallback BOTH resolved to `PureNZAdmirals2000x2000.jpg` (100x100).
   **First fix attempt (WRONG, since corrected):** `_is_plausible_headshot()`
   required `height > width` (strict portrait), reasoning real headshots are
   always portrait. This misclassified a REAL photo as a placeholder:
   SkyCity Stampede's Lachlan Frear has a genuine 600x600 SQUARE headshot
   (`LachlanFrear.jpg`, confirmed via his profile page's largeHeadshot),
   caught during acceptance-criteria spot-checking when Stampede's hit rate
   (4/34) was anomalously low next to every other NZIHL team (70-90%).
   **Actual fix:** size, not aspect ratio, is what distinguishes the two --
   `_is_plausible_headshot()` now requires BOTH dimensions >= 150px
   (`_MIN_PLAUSIBLE_DIMENSION`). The placeholder is consistently exactly
   100x100 across every team/filename observed; the smallest confirmed-real
   photo is 150x199/150x200 (Dunedin-style ad-hoc uploads) -- the cutoff
   sits in the comfortable gap between the two. Applied uniformly to both
   the naive-guess and profile-fallback paths.
   **If a future check ever needs to special-case a specific team's
   placeholder image by hash instead of by size, that's the fallback plan
   -- size-based rejection was chosen first because it generalizes without
   needing to catalog every team's placeholder.**
   **Lesson for next time a "some teams have way lower coverage than
   others" pattern shows up: don't assume it's real (teams genuinely not
   uploading photos) without spot-checking a specific miss's actual
   profile-page largeHeadshot URL first -- the anomaly was the tell that a
   validation heuristic itself was wrong, not the underlying data.**

**Idempotency / no-diff-on-unchanged-run:** `photos.normalize_to_jpg()`
does NOT re-encode a source image that's already a JPEG -- it returns the
original bytes untouched. This matters because re-encoding through Pillow
on every run risks a spurious diff if the Pillow version on the runner ever
changes (different encoder output for pixel-identical input). Pillow is
pinned to an exact version (`Pillow==10.4.0`) in both `requirements.txt` and
`pyproject.toml` as a second safety net, since PNG sources (Dunedin
Thunder's ad-hoc filenames) still need to go through PIL to become `.jpg`.
`cli.run()` also explicitly hash-compares new bytes against the existing
on-disk file and skips the write entirely when unchanged (belt and
suspenders on top of git's own content-based diffing).

**Auckland Mako:** genuinely has no `team_id` right now -- confirmed live
2026-07-11 via both `standings.cfm` and the site's `TEAMS` nav (5 teams
listed, Mako absent). Registered in `teams.py` with `team_id=None`;
`cli.run()` skips the scrape for any team with `team_id=None` and the
gallery renders a "not fielding a team this season" placeholder section
instead of omitting the franchise silently. Same state as the
`TODO @publish` comments already sitting in `matchavez/hockey`'s
scorebug/summary overlays -- fill in the real ID there too whenever Mako's
teamID surfaces.

**Team ordering in the gallery:** dynamic, fetched from `standings.cfm`
live each run (`cli.build_league_order()` + `scraper.parse_standings_order()`)
rather than hardcoded, since standings change weekly. Falls back to the
registry's declared order if the fetch/parse fails (best-effort, never
fails the whole run). `Team` rows without a `team_id` (Mako) are always
appended last, since they can't appear in a real standings table.

**Coaches have no photo fallback path:** `personnel.cfm` doesn't expose a
`playerID`, so only the naive-guess URL is attempted for coaches -- if it
misses, they're recorded as missing with no further lookup attempted (no
profile page to scrape). This is a known, accepted gap, not a bug.

## Sandbox note (contradicts the task brief's assumption)

The task brief assumed the sandbox can't reach esportsdesk at all. In
practice `admin.esportsdesk.com` DOES respond to the sandbox when hit with
`requests` + full browser-like headers (matches the precedent already noted
in [[nzihl-roster-schedule-pipeline]]: "admin.esportsdesk.com 403s plain
curl but works fine with Python requests + full browser-like headers").
This let most of this repo's development be validated against LIVE data
directly in the sandbox (De Jonge, Shattock, Scott Henry, standings order,
etc. all spot-checked live) rather than only via GitHub Actions. The
45-second-per-call sandbox tool limit means a FULL 9-team run (many
minutes, throttled to 1req/s) still can't complete inside one call though
-- use `--teams-only <CODE>` for interactive sandbox testing, and trust the
GitHub Actions run (no such per-call limit) for full-scale validation.

## Related repos

- **matchavez/nzihl-broadcast-rosters** / **nzwihl-broadcast-rosters** --
  source of the team registry, name-override philosophy, and the
  `admin.esportsdesk.com` no-cache-host / browser-header-session pattern
  this repo's `http.py` mirrors.
- **matchavez/hockey** -- portal (links to this repo's Pages gallery) and
  the live overlays that are the eventual (not-yet-done) consumer of this
  warehouse.

## Sync note

Keep this file and README.md in sync with every meaningful change. If they
drift, flag it to Mat and get approval before publishing the sync edit
(per [[repo-memory-md-convention]]).
