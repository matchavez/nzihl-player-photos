from player_photos import manifest as manifest_mod
from player_photos.teams import by_short_code


def _adm():
    return by_short_code("nzihl", "ADM")


def test_upsert_new_person_marks_changed():
    m = manifest_mod.new_manifest()
    team = _adm()
    changed = manifest_mod.upsert_person(
        m, league="nzihl", league_display="NZIHL", team=team,
        role="player", player_id=123, first="Scott", last="Henry",
        number="4", position="D",
        photo_rel_path="photos/nzihl/pure_nz_admirals/ScottHenry.jpg",
        source_url="https://example/x.jpg", sha256="abc123",
    )
    assert changed is True
    entry = m["leagues"]["nzihl"]["teams"]["ADM"]["people"]["nzihl:ADM:player:123"]
    assert entry["name"] == "Scott Henry"
    assert entry["active"] is True
    assert entry["first_seen"] == entry["last_verified"]


def test_upsert_unchanged_person_not_flagged_changed():
    m = manifest_mod.new_manifest()
    team = _adm()
    kwargs = dict(
        league="nzihl", league_display="NZIHL", team=team,
        role="player", player_id=123, first="Scott", last="Henry",
        number="4", position="D",
        photo_rel_path="photos/nzihl/pure_nz_admirals/ScottHenry.jpg",
        source_url="https://example/x.jpg", sha256="abc123",
    )
    manifest_mod.upsert_person(m, **kwargs)
    changed_again = manifest_mod.upsert_person(m, **kwargs)
    assert changed_again is False


def test_upsert_changed_sha_flags_changed():
    m = manifest_mod.new_manifest()
    team = _adm()
    base = dict(
        league="nzihl", league_display="NZIHL", team=team,
        role="player", player_id=123, first="Scott", last="Henry",
        number="4", position="D",
        photo_rel_path="photos/nzihl/pure_nz_admirals/ScottHenry.jpg",
        source_url="https://example/x.jpg",
    )
    manifest_mod.upsert_person(m, sha256="abc123", **base)
    changed = manifest_mod.upsert_person(m, sha256="def456", **base)
    assert changed is True


def test_missing_person_marked_inactive_not_deleted():
    m = manifest_mod.new_manifest()
    team = _adm()
    manifest_mod.upsert_person(
        m, league="nzihl", league_display="NZIHL", team=team,
        role="player", player_id=123, first="Scott", last="Henry",
        number="4", position="D", photo_rel_path=None, source_url=None, sha256=None,
    )
    # simulate a later run where this player is no longer observed
    newly_inactive = manifest_mod.mark_missing_as_inactive(m, seen_keys=set())
    assert newly_inactive == 1
    entry = m["leagues"]["nzihl"]["teams"]["ADM"]["people"]["nzihl:ADM:player:123"]
    assert entry["active"] is False
    # entry still present -- never deleted
    assert "nzihl:ADM:player:123" in m["leagues"]["nzihl"]["teams"]["ADM"]["people"]


def test_person_key_players_vs_coaches():
    team = _adm()
    player_key = manifest_mod.person_key("nzihl", team, "player", 123, "Scott", "Henry", "D")
    coach_key = manifest_mod.person_key("nzihl", team, "coach", None, "Blake", "Jackson", "Head Coach")
    assert player_key == "nzihl:ADM:player:123"
    assert coach_key == "nzihl:ADM:coach:Blake|Jackson|Head Coach"


def test_generated_at_is_date_granularity_not_full_timestamp():
    # Regression test: generated_at previously used a full wall-clock
    # timestamp (now_iso()), which meant it changed on literally every
    # run and broke the "no real changes -> empty git diff" contract --
    # caught live when a second same-day workflow_dispatch still produced
    # a 2-file commit (manifest.json + index.html) with zero photo changes.
    # Two manifests built on the "same day" (mocked via load_or_new twice)
    # must have identical generated_at.
    m1 = manifest_mod.new_manifest()
    m2 = manifest_mod.load_or_new(m1)
    assert m1["generated_at"] == m2["generated_at"]
    assert len(m1["generated_at"]) == len("2026-07-11")  # date, not datetime
