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

## Playoff-readiness audit (2026-07-13)
See matchavez/hockey's playoff-readiness.md for the full cross-repo audit. Change made here:
**.github/workflows/force-pages-build.yml** (new) -- POSTs /pages/builds on every push to main so
this repo's GitHub Pages (legacy builder) never depends on someone remembering the manual
force-build trick. Verified green via the Actions API.

## Sync note

Keep this file and README.md in sync with every meaningful change. If they
drift, flag it to Mat and get approval before publishing the sync edit
(per [[repo-memory-md-convention]]).

## Stats-under-photo (2026-07-13)

Gallery cards now show a small stat line under each active skater/goalie's
photo, e.g. "10 PTS (4G 6A)" or "6-1, 3.14 GAA, .880 SV%". New module
`stats.py` fetches `stats.json` fresh (at gallery-build time, not persisted
into `manifest.json`) from both roster repos' raw GitHub content:
`matchavez/nzihl-broadcast-rosters` and `matchavez/nzwihl-broadcast-rosters`
(see [[nzihl-stats-json-consolidation]] for why that file is the canonical
G/A/PTS + goalie-record source). Deliberately NOT folded into
`manifest.json` -- that file's contract is the photo/hash record, and stats
change on a different cadence than photos.

**Join key: `(league, team short_code, jersey number)`, not name.** Names
need the override table to line up ([[nzihl-player-name-overrides]]);
number is already what `stats.json` itself uses as its natural key, so
joining on it sidesteps every name-matching edge case for free.

**Players with `gp == 0` get no stat line at all** (not a "0-0-0" line) --
cleaner for guys who are rostered/dressed but haven't played yet. A fetch
failure for one league degrades gracefully: that league's cards just show
no stat lines rather than breaking the whole gallery build.

**Bonus fix while in `gallery.py`:** the team-head `<span class="code">`
badge had been silently rendering blank for every real team (`team_block`
never actually carried a `short_code` key -- only the registry-fallback
default dict for a missing team did). Threaded the loop's known `code`
value down into `_team_section` explicitly instead of reading a key that
was never set. Visible now: `Pure NZ Admirals ADM` etc.

Regenerated `index.html` locally against the live manifest + a fresh
`stats.json`/standings fetch (same code path the weekly Action runs) and
committed the result rather than waiting for Thursday's cron.

## Gallery retired in favor of hockey/warehouse/#photos (2026-07-13, same day)

Mat pointed out the stats-under-photo feature above (and the gallery in
general) was **duplicating** `matchavez/hockey`'s `warehouse/index.html`,
which already fetched this repo's `manifest.json` live to render its own
photo section. Rather than maintain the same join logic in two places
(Python here, JS there), the decision was: **one browsable view, and it's
the warehouse page.** This repo goes back to being a pure data source.

**What changed:**
- `gallery.py` no longer renders a gallery at all -- `build_gallery_html()`
  now takes and ignores any args and just returns a static redirect stub
  (meta-refresh + canonical link) pointing at
  `https://matchavez.com/hockey/warehouse/#photos`. `stats.py` (the
  same-day addition described above) was deleted outright -- that join
  logic now lives in `warehouse/index.html`'s JS instead (`fetchStatsIndex`
  / `skaterLine` / `goalieLine`, same join key: league+short_code+number,
  same gp===0-means-no-line rule).
- `cli.py`'s `build_league_order()` function was deleted too -- it existed
  solely to sort the old gallery's team sections by live standings order,
  and nothing else needed it.
- `index.html` is committed as the redirect stub (not regenerated per-run
  from manifest data anymore, though `cli.run()` still writes it every run
  via `gallery.build_gallery_html()` -- cheap, no network dependency, and
  keeps the file existing for `test_cli.py`'s existing assertion).
- README.md rewritten to lead with "this is a data source, not a browsable
  page" and point at the warehouse URL.

**What did NOT change:** `manifest.json`, `photos/`, the weekly scrape --
this repo's actual job. Anything that consumes `manifest.json` or
`photos/*.jpg` directly via `raw.githubusercontent.com` (activity-banner,
scorebug-l3, scoringleaders, lowerthirds, summary, startinglineup, and the
warehouse page itself) is unaffected -- GitHub Pages still serves those
files exactly as before; only the root `index.html` changed.

See also `matchavez/hockey`'s own memory.md for the warehouse-side half of
this change (stat-line JS added, portal's duplicate "Player Photos" card
removed, all Photo Gallery buttons repointed).
