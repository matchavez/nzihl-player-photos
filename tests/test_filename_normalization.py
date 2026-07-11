"""Filename-normalization tests -- spaces, hyphens, apostrophes, macrons.

Task acceptance criterion explicitly calls out testing these cases.
"""
from player_photos.manifest import filename_stub, photo_path


def test_spaces_stripped():
    assert filename_stub("Nash", "Hayward Jones") == "NashHaywardJones"


def test_hyphen_preserved():
    assert filename_stub("Joel", "Keogh-Cope") == "JoelKeogh-Cope"


def test_apostrophe_preserved():
    assert filename_stub("Liam", "O'Brien") == "LiamO'Brien"


def test_macron_preserved():
    # Macronised vowels (te reo Māori names) must survive untouched -- only
    # whitespace is stripped, everything else (including non-ASCII) stays.
    assert filename_stub("Mere", "Ngāwhare") == "MereNgāwhare"
    assert filename_stub("Tāne", "Māori") == "TāneMāori"


def test_multiple_internal_spaces_collapsed_by_strip():
    assert filename_stub("De", "  Jonge  Benjamin ") == "DeJongeBenjamin"


def test_photo_path_shape():
    p = photo_path("nzihl", "pure_nz_admirals", "Benjamin", "De Jonge")
    assert p == "photos/nzihl/pure_nz_admirals/BenjaminDeJonge.jpg"
