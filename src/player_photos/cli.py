"""Orchestration: scrape every team -> resolve photos -> write manifest.json
-> write index.html gallery -> write only new/changed photo files.

Usage: python -m player_photos [--output-dir .] [--teams-only ADM,CRD]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import gallery, manifest as manifest_mod, overrides, photos, scraper
from .teams import ALL_TEAMS, LEAGUE_DISPLAY_NAMES, LEAGUES


def _stat_dict(t):
    return {"display_name": t.display_name, "short_code": t.short_code, "slug": t.slug}


def build_league_order() -> dict[str, list[str]]:
    """Best-effort dynamic team order per league from standings.cfm; falls
    back to the registry's declared order if the fetch/parse fails."""
    order: dict[str, list[str]] = {}
    for league_key, teams in LEAGUES.items():
        default_order = [t.short_code for t in teams]
        fielding_teams = [t for t in teams if t.team_id is not None]
        placeholder_codes = [t.short_code for t in teams if t.team_id is None]
        try:
            cid, lid = fielding_teams[0].client_id, fielding_teams[0].league_id
            html = scraper.fetch_standings_html(cid, lid)
            live_order = scraper.parse_standings_order(html, fielding_teams)
            order[league_key] = live_order + placeholder_codes
        except Exception as e:
            print(f"  [warn] standings order fetch failed for {league_key}: {e}", file=sys.stderr)
            order[league_key] = default_order
    return order


def run(output_dir: Path, teams_filter: set[str] | None = None) -> dict:
    photos_dir = output_dir / "photos"
    manifest_path = output_dir / "manifest.json"

    existing_manifest = None
    if manifest_path.exists():
        try:
            existing_manifest = json.loads(manifest_path.read_text())
        except Exception:
            existing_manifest = None

    man = manifest_mod.load_or_new(existing_manifest)
    seen_keys: set[str] = set()
    photos_written = 0
    photos_unchanged = 0
    photos_missing = 0

    for team in ALL_TEAMS:
        if teams_filter and team.short_code not in teams_filter:
            continue
        league = team.league
        league_display = LEAGUE_DISPLAY_NAMES[league]

        leagues_block = man.setdefault("leagues", {})
        league_block = leagues_block.setdefault(league, {"display_name": league_display, "teams": {}})
        team_block = league_block["teams"].setdefault(
            team.short_code, {"display_name": team.display_name, "slug": team.slug, "people": {}}
        )

        if team.team_id is None:
            team_block["no_team_id"] = True
            print(f"[{team.short_code}] no team_id on record -- skipping scrape (not fielding a team).")
            continue
        team_block.pop("no_team_id", None)

        print(f"[{team.short_code}] scraping roster + coaches...")
        try:
            people = scraper.scrape_team(team)
        except Exception as e:
            print(f"  [error] scrape failed for {team.short_code}: {e}", file=sys.stderr)
            continue

        for person in people:
            raw_full_name = person.first + " " + person.last  # already override-normalized by scraper
            override_full_name = raw_full_name
            key = manifest_mod.person_key(league, team, person.role, person.player_id, person.first, person.last, person.position)
            seen_keys.add(key)

            rel_path = manifest_mod.photo_path(league, team.slug, person.first, person.last)
            abs_path = output_dir / rel_path

            existing_sha = None
            if abs_path.exists():
                existing_sha = photos.sha256_hex(abs_path.read_bytes())

            img_bytes, source_url = photos.resolve_photo(
                team, person.player_id, raw_full_name, override_full_name
            )

            if img_bytes is None:
                photos_missing += 1
                manifest_mod.upsert_person(
                    man, league=league, league_display=league_display, team=team,
                    role=person.role, player_id=person.player_id,
                    first=person.first, last=person.last, number=person.number,
                    position=person.position, photo_rel_path=None,
                    source_url=None, sha256=None,
                )
                continue

            new_sha = photos.sha256_hex(img_bytes)
            if new_sha == existing_sha:
                photos_unchanged += 1
            else:
                abs_path.parent.mkdir(parents=True, exist_ok=True)
                abs_path.write_bytes(img_bytes)
                photos_written += 1

            manifest_mod.upsert_person(
                man, league=league, league_display=league_display, team=team,
                role=person.role, player_id=person.player_id,
                first=person.first, last=person.last, number=person.number,
                position=person.position, photo_rel_path=rel_path,
                source_url=source_url, sha256=new_sha,
            )

    if not teams_filter:
        # Only mark people inactive on a full run -- a partial/filtered run
        # (e.g. testing one team) must not wipe everyone else's active flag.
        newly_inactive = manifest_mod.mark_missing_as_inactive(man, seen_keys)
    else:
        newly_inactive = 0

    manifest_path.write_text(json.dumps(man, indent=2, sort_keys=True, ensure_ascii=False) + "\n")

    league_order = build_league_order()
    gallery_html = gallery.build_gallery_html(man, league_order, LEAGUE_DISPLAY_NAMES)
    (output_dir / "index.html").write_text(gallery_html)

    print(
        f"Done. {photos_written} photo(s) written, {photos_unchanged} unchanged, "
        f"{photos_missing} missing, {newly_inactive} newly marked inactive."
    )
    return man


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Scrape NZIHL/NZWIHL headshots into a committed warehouse.")
    parser.add_argument("--output-dir", default=".", help="Repo root to write photos/, manifest.json, index.html into.")
    parser.add_argument("--teams-only", default="", help="Comma-separated short codes to limit the run to (testing).")
    args = parser.parse_args(argv)

    teams_filter = {c.strip().upper() for c in args.teams_only.split(",") if c.strip()} or None
    # Single source of truth for player-name corrections (see overrides.py) --
    # best-effort, falls back to the hardcoded snapshot on any failure.
    overrides.load_remote_overrides()
    run(Path(args.output_dir), teams_filter)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
