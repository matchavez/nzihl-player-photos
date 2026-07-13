"""Player-name corrections, ported from the two roster-PDF repos.

Two independent override tables exist upstream (one per league repo) and
don't share state — mirrored here as a single dict keyed by
(league, team_id, jersey) so a name bug fixed in one sibling repo doesn't
silently stay broken here. See memory: nzihl-player-name-overrides.

`normalize_name` returns the corrected (first, last) used for BOTH the
person's display name in manifest.json/the gallery AND the filename we
save the photo under — so De Jonge and Shattock resolve to clean names
regardless of how esportsdesk mangles the raw scrape.

SINGLE SOURCE OF TRUTH (2026-07-13): the constants below are only the
FALLBACK snapshot. `load_remote_overrides()` fetches the real canonical
data from nzihl-broadcast-assets/assets/name-overrides.json and replaces
them in place; call it once near the top of cli.main(). If that fetch
fails for any reason, these hardcoded values keep the scrape working
exactly as before -- a name-overrides.json outage should never break a
scheduled scrape.
"""
from __future__ import annotations

import re

# (league, team_id, jersey) -> (override_last, override_first | None)
SURNAME_OVERRIDES: dict[tuple[str, int, str], tuple[str, str | None]] = {
    # Pure NZ Admirals #26 Benjamin De Jonge — "De Jonge" is a genuine two-word
    # surname; the generic last-space split otherwise produces
    # first="Benjamin De", last="Jonge". Ported from nzihl-broadcast-rosters'
    # `multi_word` allowlist (see _split_first_last below) — recorded here too
    # as a belt-and-suspenders override keyed by (team_id, jersey).
    ("nzihl", 674110, "26"): ("De Jonge", None),
    # Canterbury Inferno #3 Reagyn Shattock — esportsdesk stores her surname as
    # "Shattock (Niskakoski)" (maiden name baked into the title attribute).
    # Ported verbatim from nzwihl-broadcast-rosters/src/nzwihl_rosters/overrides.py.
    ("nzwihl", 675637, "3"): ("Shattock", "Reagyn"),
}

# Two-word surnames to keep whole when splitting "First Middle Last" naively —
# ported from nzihl-broadcast-rosters/src/nzihl_rosters/scraper.py's
# `_split_first_last`. Lowercased, space-joined last-two-tokens form.
MULTI_WORD_SURNAMES = {"hayward jones", "de jonge"}

# Unwanted parenthetical add-ons (maiden names, nicknames) that are NOT part
# of the real surname — stripped from the raw scraped title before any
# splitting happens. Regex (pattern, replacement) pairs, case-insensitive.
# Ported from the `matchavez/hockey` live-overlay fix.
PARENTHETICAL_STRIP: list[tuple[str, str]] = [
    (r"Shattock\s*\(\s*Niskakoski\s*\)", "Shattock"),
]


def strip_parentheticals(full_name: str) -> str:
    for pattern, clean in PARENTHETICAL_STRIP:
        full_name = re.sub(pattern, clean, full_name, flags=re.IGNORECASE)
    # Generic fallback: drop any trailing "(...)" group not caught above.
    if "(" in full_name and full_name.rstrip().endswith(")"):
        full_name = full_name.split("(")[0].strip()
    return full_name


def split_first_last(full_name: str) -> tuple[str, str]:
    """Split 'Eli Seo Jun Paek' -> ('Eli Seo Jun', 'Paek').

    Hyphenated surnames stay whole ('Joel Keogh-Cope' -> ('Joel', 'Keogh-Cope')).
    Two-word surnames are detected from MULTI_WORD_SURNAMES.
    """
    full_name = strip_parentheticals(full_name)
    parts = full_name.strip().split()
    if not parts:
        return ("", "")
    if len(parts) == 1:
        return ("", parts[0])
    if len(parts) == 2:
        return (parts[0], parts[1])
    tail2 = " ".join(parts[-2:]).lower()
    if tail2 in MULTI_WORD_SURNAMES:
        return (" ".join(parts[:-2]), " ".join(parts[-2:]))
    return (" ".join(parts[:-1]), parts[-1])


def _smart_title(text: str) -> str:
    """Title-case a name but preserve mixed-case names already correct
    (MacDonald, McKenzie, ...) and hyphenated parts."""
    if not text:
        return text
    is_all_lower = text == text.lower()
    is_all_upper = text == text.upper()
    if not (is_all_lower or is_all_upper):
        return text

    def cap_part(part: str) -> str:
        if not part:
            return part
        return part[0].upper() + part[1:].lower()

    return " ".join(
        "-".join(cap_part(seg) for seg in word.split("-"))
        for word in text.split(" ")
    )


def normalize_name(full_name: str, league: str, team_id: int, jersey: str) -> tuple[str, str]:
    """Full pipeline: strip parentheticals -> split -> title-case -> apply
    explicit per-(league, team_id, jersey) overrides. Returns (first, last)."""
    first_raw, last_raw = split_first_last(full_name)
    first = _smart_title(first_raw.strip())
    last = _smart_title(last_raw.strip())

    override = SURNAME_OVERRIDES.get((league, team_id, jersey))
    if override:
        override_last, override_first = override
        last = override_last
        if override_first is not None:
            first = override_first

    return first, last


NAME_OVERRIDES_URL = (
    "https://raw.githubusercontent.com/matchavez/nzihl-broadcast-assets/"
    "main/assets/name-overrides.json"
)


def load_remote_overrides(*, timeout: int = 10) -> bool:
    """Fetch the canonical name-overrides.json (single source of truth across
    every broadcast-asset repo -- see matchavez/hockey's
    nzihl_player_name_overrides memory) and replace this module's
    MULTI_WORD_SURNAMES / SURNAME_OVERRIDES / PARENTHETICAL_STRIP in place.

    Call once near the top of cli.main(), before any scraping starts. On any
    failure (network, bad JSON, etc.) this leaves the hardcoded fallback
    values above untouched and returns False -- a scheduled scrape must never
    hard-fail just because this one extra fetch didn't land.
    """
    global MULTI_WORD_SURNAMES, SURNAME_OVERRIDES, PARENTHETICAL_STRIP
    import requests

    try:
        resp = requests.get(NAME_OVERRIDES_URL, timeout=timeout)
        resp.raise_for_status()
        cfg = resp.json()
    except Exception as exc:  # noqa: BLE001 -- deliberately broad, see docstring
        print(f"warning: could not fetch name-overrides.json ({exc}); using built-in fallback")
        return False

    words = cfg.get("multi_word_surnames")
    if words:
        MULTI_WORD_SURNAMES = {str(w).lower() for w in words}

    team_jersey = cfg.get("team_jersey_overrides")
    if team_jersey is not None:
        merged: dict[tuple[str, int, str], tuple[str, str | None]] = {}
        for entry in team_jersey:
            key = (str(entry["league"]), int(entry["team_id"]), str(entry["jersey"]))
            merged[key] = (entry["last"], entry.get("first"))
        SURNAME_OVERRIDES = merged

    strips = cfg.get("parenthetical_strips")
    if strips is not None:
        PARENTHETICAL_STRIP = [(entry["find"], entry["replace"]) for entry in strips]

    return True
