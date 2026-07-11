"""End-to-end CLI test with the network mocked out.

Covers the task's core idempotency requirement: a second run against
unchanged upstream data must not rewrite any photo bytes (and therefore
would produce an empty git diff), and a person who disappears from the
scrape gets marked inactive rather than deleted.
"""
import json

import pytest

from player_photos import cli, photos, scraper
from player_photos.scraper import Person
from player_photos.teams import by_short_code

ADM = by_short_code("nzihl", "ADM")

FAKE_JPEG = None  # filled in by a fixture below


@pytest.fixture(autouse=True)
def _fake_jpeg_bytes():
    import io
    from PIL import Image
    global FAKE_JPEG
    img = Image.new("RGB", (300, 400), color=(10, 20, 30))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    FAKE_JPEG = buf.getvalue()
    yield


def _fake_scrape_team(team):
    assert team.short_code == "ADM"
    return [
        Person("player", 111, "Scott", "Henry", "4", "D"),
        Person("player", 222, "Benjamin", "De Jonge", "26", "F"),
        Person("coach", None, "Blake", "Jackson", None, "Head Coach"),
    ]


def _fake_resolve_photo(team, player_id, raw_name, override_name):
    # Scott Henry has a photo, De Jonge and the coach don't.
    if player_id == 111:
        return FAKE_JPEG, "https://example/ScottHenry.jpg"
    return None, None


def test_full_run_writes_expected_files(tmp_path, monkeypatch):
    monkeypatch.setattr(scraper, "scrape_team", _fake_scrape_team)
    monkeypatch.setattr(photos, "resolve_photo", _fake_resolve_photo)
    monkeypatch.setattr(
        scraper, "fetch_standings_html",
        lambda cid, lid: (_ for _ in ()).throw(RuntimeError("no network in tests")),
    )

    man = cli.run(tmp_path, teams_filter={"ADM"})

    photo_file = tmp_path / "photos/nzihl/pure_nz_admirals/ScottHenry.jpg"
    assert photo_file.exists()
    assert photo_file.read_bytes() == FAKE_JPEG
    assert not (tmp_path / "photos/nzihl/pure_nz_admirals/BenjaminDeJonge.jpg").exists()

    assert (tmp_path / "manifest.json").exists()
    assert (tmp_path / "index.html").exists()

    people = man["leagues"]["nzihl"]["teams"]["ADM"]["people"]
    henry = people["nzihl:ADM:player:111"]
    assert henry["photo"] == "photos/nzihl/pure_nz_admirals/ScottHenry.jpg"
    dejonge = people["nzihl:ADM:player:222"]
    assert dejonge["photo"] is None
    assert dejonge["name"] == "Benjamin De Jonge"
    coach = people["nzihl:ADM:coach:Blake|Jackson|Head Coach"]
    assert coach["position"] == "Head Coach"


def test_second_identical_run_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(scraper, "scrape_team", _fake_scrape_team)
    monkeypatch.setattr(photos, "resolve_photo", _fake_resolve_photo)
    monkeypatch.setattr(
        scraper, "fetch_standings_html",
        lambda cid, lid: (_ for _ in ()).throw(RuntimeError("no network in tests")),
    )

    cli.run(tmp_path, teams_filter={"ADM"})
    photo_file = tmp_path / "photos/nzihl/pure_nz_admirals/ScottHenry.jpg"
    first_bytes = photo_file.read_bytes()
    first_mtime = photo_file.stat().st_mtime_ns

    # Second run: identical upstream data.
    man2 = cli.run(tmp_path, teams_filter={"ADM"})

    assert photo_file.read_bytes() == first_bytes
    # The file must not have been rewritten at all (hash-compare skip).
    assert photo_file.stat().st_mtime_ns == first_mtime

    people = man2["leagues"]["nzihl"]["teams"]["ADM"]["people"]
    assert people["nzihl:ADM:player:111"]["active"] is True
    assert people["nzihl:ADM:player:222"]["active"] is True


def test_departed_player_marked_inactive_not_deleted(tmp_path, monkeypatch):
    monkeypatch.setattr(scraper, "scrape_team", _fake_scrape_team)
    monkeypatch.setattr(photos, "resolve_photo", _fake_resolve_photo)
    monkeypatch.setattr(
        scraper, "fetch_standings_html",
        lambda cid, lid: (_ for _ in ()).throw(RuntimeError("no network in tests")),
    )
    cli.run(tmp_path, teams_filter={"ADM"})

    # Next run: Scott Henry has dropped off the roster.
    def _scrape_without_henry(team):
        return [
            Person("player", 222, "Benjamin", "De Jonge", "26", "F"),
            Person("coach", None, "Blake", "Jackson", None, "Head Coach"),
        ]
    monkeypatch.setattr(scraper, "scrape_team", _scrape_without_henry)

    man2 = cli.run(tmp_path, teams_filter=None)  # full run so inactive-marking runs
    people = man2["leagues"]["nzihl"]["teams"]["ADM"]["people"]
    assert people["nzihl:ADM:player:111"]["active"] is False
    # Still present, and the photo file on disk is untouched (never deleted).
    assert (tmp_path / "photos/nzihl/pure_nz_admirals/ScottHenry.jpg").exists()
