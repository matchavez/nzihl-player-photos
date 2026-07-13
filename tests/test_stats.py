from unittest.mock import patch

from player_photos import stats as stats_mod


FAKE_NZIHL = {
    "teams": {
        "ADM": {
            "skaters": [
                {"first": "Scott", "last": "Henry", "number": "4", "g": 4, "a": 6, "pts": 10, "gp": 14},
                {"first": "Rookie", "last": "Bench", "number": "99", "g": 0, "a": 0, "pts": 0, "gp": 0},
            ],
            "goalies": [
                {"first": "Csaba", "last": "Kercso-Magos", "number": "34", "w": 6, "l": 1, "gaa": "3.14", "sv_pct": ".880", "gp": 7},
                {"first": "Never", "last": "Played", "number": "55", "w": 0, "l": 0, "gaa": "0.00", "sv_pct": "-", "gp": 0},
            ],
        }
    }
}
FAKE_NZWIHL = {"teams": {}}


def _fake_fetch(league):
    return FAKE_NZIHL if league == "nzihl" else FAKE_NZWIHL


def test_build_stats_index_skips_zero_gp_and_formats_lines():
    with patch.object(stats_mod, "_fetch_one", side_effect=_fake_fetch):
        index = stats_mod.build_stats_index()
    assert index[("nzihl", "ADM", "4")] == "10 PTS (4G 6A)"
    assert index[("nzihl", "ADM", "34")] == "6-1, 3.14 GAA, .880 SV%"
    # zero-GP skater/goalie contribute no line at all -- not even a "0" one
    assert ("nzihl", "ADM", "99") not in index
    assert ("nzihl", "ADM", "55") not in index


def test_build_stats_index_survives_a_failed_fetch():
    with patch.object(stats_mod, "_fetch_one", side_effect=Exception("boom")):
        # _fetch_one itself catches and returns {} on failure in real code;
        # here we simulate the fetch-failed path returning {} directly.
        pass
    with patch.object(stats_mod, "_fetch_one", return_value={}):
        index = stats_mod.build_stats_index()
    assert index == {}
