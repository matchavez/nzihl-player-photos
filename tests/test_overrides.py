from player_photos.overrides import (
    normalize_name,
    split_first_last,
    strip_parentheticals,
)


def test_simple_two_part_name():
    first, last = normalize_name("Scott Henry", "nzihl", 674110, "4")
    assert (first, last) == ("Scott", "Henry")


def test_de_jonge_multiword_surname_and_override():
    # Even without the explicit override, the multi_word allowlist keeps
    # "De Jonge" whole rather than splitting at the last space.
    first, last = split_first_last("Benjamin De Jonge")
    assert (first, last) == ("Benjamin", "De Jonge")
    # The explicit (league, team_id, jersey) override also fires correctly.
    first, last = normalize_name("Benjamin De Jonge", "nzihl", 674110, "26")
    assert (first, last) == ("Benjamin", "De Jonge")


def test_shattock_parenthetical_maiden_name_stripped():
    first, last = normalize_name("Reagyn Shattock (Niskakoski)", "nzwihl", 675637, "3")
    assert (first, last) == ("Reagyn", "Shattock")


def test_hayward_jones_multiword_surname():
    first, last = split_first_last("Nash Hayward Jones")
    assert (first, last) == ("Nash", "Hayward Jones")


def test_hyphenated_surname_stays_whole():
    first, last = split_first_last("Joel Keogh-Cope")
    assert (first, last) == ("Joel", "Keogh-Cope")


def test_lowercase_names_are_title_cased():
    first, last = normalize_name("harry louw", "nzihl", 1, "1")
    assert (first, last) == ("Harry", "Louw")


def test_mixed_case_names_left_alone():
    # MacDonald/McKenzie-style names shouldn't get mangled by title-casing.
    first, last = normalize_name("Ewan MacDonald", "nzihl", 1, "1")
    assert (first, last) == ("Ewan", "MacDonald")


def test_strip_parentheticals_generic_trailing_group():
    assert strip_parentheticals("Some Player (Nickname)") == "Some Player"


def test_single_token_name():
    first, last = split_first_last("Cher")
    assert (first, last) == ("", "Cher")


def test_load_remote_overrides_success_updates_module_state(monkeypatch):
    from player_photos import overrides as ov

    fallback_multi = set(ov.MULTI_WORD_SURNAMES)
    fallback_so = dict(ov.SURNAME_OVERRIDES)
    fallback_ps = list(ov.PARENTHETICAL_STRIP)

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "multi_word_surnames": ["hayward jones", "de jonge", "van der berg"],
                "team_jersey_overrides": [
                    {"league": "nzwihl", "team_id": 675637, "jersey": "3",
                     "first": "Reagyn", "last": "Shattock"},
                ],
                "parenthetical_strips": [
                    {"find": r"Shattock\s*\(\s*Niskakoski\s*\)", "replace": "Shattock"},
                ],
            }

    def fake_get(url, timeout=None):
        assert "name-overrides.json" in url
        return FakeResp()

    monkeypatch.setattr("requests.get", fake_get)
    try:
        ok = ov.load_remote_overrides()
        assert ok is True
        assert ov.MULTI_WORD_SURNAMES == {"hayward jones", "de jonge", "van der berg"}
        assert ov.SURNAME_OVERRIDES == {("nzwihl", 675637, "3"): ("Shattock", "Reagyn")}
        # still functions correctly end-to-end after the swap
        assert ov.normalize_name("Reagyn Shattock (Niskakoski)", "nzwihl", 675637, "3") == ("Reagyn", "Shattock")
    finally:
        ov.MULTI_WORD_SURNAMES = fallback_multi
        ov.SURNAME_OVERRIDES = fallback_so
        ov.PARENTHETICAL_STRIP = fallback_ps


def test_load_remote_overrides_failure_keeps_fallback(monkeypatch):
    from player_photos import overrides as ov

    fallback_multi = set(ov.MULTI_WORD_SURNAMES)
    fallback_so = dict(ov.SURNAME_OVERRIDES)
    fallback_ps = list(ov.PARENTHETICAL_STRIP)

    def fake_get(url, timeout=None):
        raise ConnectionError("simulated network failure")

    monkeypatch.setattr("requests.get", fake_get)
    ok = ov.load_remote_overrides()
    assert ok is False
    # module state untouched -- an on-air/scheduled-scrape must never regress
    # just because this one extra fetch failed
    assert ov.MULTI_WORD_SURNAMES == fallback_multi
    assert ov.SURNAME_OVERRIDES == fallback_so
    assert ov.PARENTHETICAL_STRIP == fallback_ps
