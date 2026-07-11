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
