from player_photos import gallery, manifest as manifest_mod
from player_photos.teams import LEAGUE_DISPLAY_NAMES, by_short_code


def test_build_gallery_html_smoke():
    m = manifest_mod.new_manifest()
    team = by_short_code("nzihl", "ADM")
    manifest_mod.upsert_person(
        m, league="nzihl", league_display="NZIHL", team=team,
        role="player", player_id=1, first="Scott", last="Henry",
        number="4", position="D",
        photo_rel_path="photos/nzihl/pure_nz_admirals/ScottHenry.jpg",
        source_url="u", sha256="s",
    )
    manifest_mod.upsert_person(
        m, league="nzihl", league_display="NZIHL", team=team,
        role="player", player_id=2, first="Benjamin", last="De Jonge",
        number="26", position="F",
        photo_rel_path=None, source_url=None, sha256=None,
    )
    order = {"nzihl": ["ADM"], "nzwihl": []}
    html = gallery.build_gallery_html(m, order, LEAGUE_DISPLAY_NAMES)
    assert "Pure NZ Admirals" in html
    assert "Scott Henry" in html
    assert "Benjamin De Jonge" in html
    assert "1 missing photo" in html
    assert "<html" in html


def test_build_gallery_html_placeholder_team():
    m = manifest_mod.new_manifest()
    m["leagues"]["nzihl"] = {
        "display_name": "NZIHL",
        "teams": {"MKO": {"display_name": "Auckland Mako", "short_code": "MKO", "slug": "auckland_mako", "no_team_id": True, "people": {}}},
    }
    order = {"nzihl": ["MKO"], "nzwihl": []}
    html = gallery.build_gallery_html(m, order, LEAGUE_DISPLAY_NAMES)
    assert "Auckland Mako" in html
    assert "Not fielding a team" in html
