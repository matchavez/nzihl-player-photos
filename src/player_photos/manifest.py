"""manifest.json: per-league -> per-team -> per-person photo status.

Design points (see task spec):
- Never delete a photo just because a player dropped off a roster -- mark
  them `active: false` instead (departed players still appear in season
  retrospectives).
- A run that finds no new/changed photo bytes must produce an EMPTY git
  diff -- this module only returns "changed" when a person's manifest
  entry or a photo's sha256 actually differs from what's already committed.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone

from .teams import Team

PHOTO_ROOT = "photos"


def filename_stub(first: str, last: str) -> str:
    """<Name_No_Spaces> per the task spec: whitespace stripped, everything
    else (hyphens, apostrophes, macrons, case) preserved -- same convention
    as the live overlays' shotURL(). E.g. 'Nash Hayward Jones' ->
    'NashHaywardJones', "O'Brien" stays "O'Brien", 'Toa Ngata-Wera' ->
    'ToaNgata-Wera', 'Mere Ngāwhare' -> 'MereNgāwhare'."""
    return re.sub(r"\s+", "", f"{first}{last}")


def photo_path(league: str, team_slug: str, first: str, last: str) -> str:
    return f"{PHOTO_ROOT}/{league}/{team_slug}/{filename_stub(first, last)}.jpg"


def person_key(league: str, team: Team, role: str, player_id: int | None, first: str, last: str, position: str) -> str:
    if role == "player" and player_id is not None:
        return f"{league}:{team.short_code}:player:{player_id}"
    # Coaches have no stable playerID on personnel.cfm -- key by name+title.
    return f"{league}:{team.short_code}:coach:{first}|{last}|{position}"


def today_iso() -> str:
    return date.today().isoformat()


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_manifest() -> dict:
    # `generated_at` is deliberately DATE granularity (not a full
    # wall-clock timestamp) even though `now_iso()` is available above.
    # A full timestamp would change on literally every run, which breaks
    # the "a run with no real changes produces an empty git diff" contract
    # -- two same-day runs (e.g. testing workflow_dispatch twice in a row)
    # must commit nothing when nothing actually changed. Daily granularity
    # matches `last_verified`'s existing precision, so this only "moves"
    # once a day at most, and only within a commit that already has a real
    # reason to exist (or is itself the only thing that changed, in which
    # case a same-day rerun is still a true no-op).
    return {"generated_at": today_iso(), "leagues": {}}


def load_or_new(existing: dict | None) -> dict:
    if existing:
        m = dict(existing)
        m["generated_at"] = today_iso()
        m.setdefault("leagues", {})
        return m
    return new_manifest()


def upsert_person(
    manifest: dict,
    *,
    league: str,
    league_display: str,
    team: Team,
    role: str,
    player_id: int | None,
    first: str,
    last: str,
    number: str | None,
    position: str,
    photo_rel_path: str | None,
    source_url: str | None,
    sha256: str | None,
) -> bool:
    """Insert/update one person's manifest entry. Returns True if the
    person's record is new or materially changed (drives the "was there a
    photo change" idempotency check the workflow relies on)."""
    leagues = manifest.setdefault("leagues", {})
    league_block = leagues.setdefault(league, {"display_name": league_display, "teams": {}})
    teams_block = league_block["teams"]
    team_block = teams_block.setdefault(
        team.short_code,
        {"display_name": team.display_name, "slug": team.slug, "people": {}},
    )
    people = team_block["people"]
    key = person_key(league, team, role, player_id, first, last, position)

    today = today_iso()
    prior = people.get(key)
    changed = False

    if prior is None:
        entry = {
            "name": f"{first} {last}".strip(),
            "role": role,
            "player_id": player_id,
            "number": number,
            "position": position,
            "photo": photo_rel_path,
            "source_url": source_url,
            "sha256": sha256,
            "first_seen": today,
            "last_verified": today,
            "active": True,
        }
        people[key] = entry
        changed = True
    else:
        entry = prior
        new_name = f"{first} {last}".strip()
        if (
            entry.get("name") != new_name
            or entry.get("number") != number
            or entry.get("position") != position
            or entry.get("photo") != photo_rel_path
            or entry.get("sha256") != sha256
            or entry.get("active") is not True
        ):
            changed = True
        entry["name"] = new_name
        entry["number"] = number
        entry["position"] = position
        entry["photo"] = photo_rel_path
        entry["source_url"] = source_url or entry.get("source_url")
        entry["sha256"] = sha256
        entry["last_verified"] = today
        entry["active"] = True

    return changed


def mark_missing_as_inactive(manifest: dict, seen_keys: set[str]) -> int:
    """Anyone in the committed manifest who wasn't observed in this run gets
    `active: false` (never deleted -- departed players still appear in
    season retrospectives). Returns the count newly marked inactive."""
    newly_inactive = 0
    for league_block in manifest.get("leagues", {}).values():
        for team_block in league_block.get("teams", {}).values():
            for key, entry in team_block.get("people", {}).items():
                if key not in seen_keys and entry.get("active", True):
                    entry["active"] = False
                    newly_inactive += 1
    return newly_inactive
