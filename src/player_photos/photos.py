"""Headshot resolution: naive-guess URL, profile-page fallback, and
normalization to a canonical JPEG we can hash-compare and commit.

URL contract (see memory: nzihl-player-headshots):
- esportsdesk stores headshots under a media folder SHARED by both leagues:
  https://admin.esportsdesk.com/media/leagues/6795/graphics/<filename>
- The "naive guess" filename is <FirstLast>.jpg with all whitespace
  stripped (matches the live overlays' `shotURL()` in matchavez/hockey).
  Many clubs use ad-hoc filenames instead (different case/extension, or a
  completely unrelated name like Dunedin Thunder's "LukeEASPORT.png") --
  the naive guess misses those.
- Ground truth for any player who HAS a photo: their public profile page
  (rosters_profile.cfm, looked up by esportsdesk playerID -- immune to any
  name-parsing/override bug since it never depends on the name at all) sets
  a CSS background-image on `.largeHeadshot` pointing at the real path.
- A 200 status is NOT proof of a real photo: esportsdesk returns 200 with an
  HTML "not found" page body for a missing image, not a real 404. Every
  candidate is validated by Content-Type + actually decoding it as an image.
"""
from __future__ import annotations

import hashlib
import io
import re
from urllib.parse import urlencode, quote

from PIL import Image

from .http import fetch_binary, fetch_text
from .scraper import profile_url
from .teams import Team

MEDIA_BASE = "https://admin.esportsdesk.com/media/leagues/6795/graphics/"

_LARGE_HEADSHOT_RE = re.compile(
    r'largeHeadshot[^"]*"[^>]*background-image\s*:\s*url\(([^)]+)\)', re.IGNORECASE
)


def naive_guess_urls(*names: str) -> list[str]:
    """Build de-duplicated naive-guess headshot URLs for each given full
    name (whitespace stripped, case preserved -- mirrors the live overlays'
    shotURL()). Pass both the raw scraped name and the override-corrected
    name; callers should try both since either form might be the one
    esportsdesk actually filed the photo under."""
    seen: list[str] = []
    for name in names:
        if not name:
            continue
        stripped = re.sub(r"\s+", "", name)
        if not stripped:
            continue
        url = MEDIA_BASE + quote(stripped) + ".jpg"
        if url not in seen:
            seen.append(url)
    return seen


def fetch_profile_headshot_url(team: Team, player_id: int) -> str | None:
    """Fetch the player's public profile page and extract the real
    largeHeadshot background-image URL, or None if the profile shows no
    photo (initials-avatar players)."""
    url = profile_url(team, player_id)
    try:
        html = fetch_text(url)
    except Exception:
        return None
    m = _LARGE_HEADSHOT_RE.search(html)
    if not m:
        return None
    path = m.group(1).strip().strip("\"'")
    # esportsdesk HTML-entity/percent-encodes the path already (e.g. %2E for
    # a literal dot) -- use as-is, just resolve to an absolute URL.
    if path.startswith("http"):
        return path
    return "https://admin.esportsdesk.com" + path


# esportsdesk's "no real photo uploaded" placeholder is consistently served
# at exactly 100x100 (observed across multiple teams/filenames: a generic
# team-crest crop AND a team's own small logo file both came back 100x100
# when used as a largeHeadshot placeholder). Real photos -- including
# genuinely SQUARE ones, e.g. a 600x600 headshot -- are all much larger.
# The smallest confirmed-real photo seen is 150x199/150x200 (Dunedin-style
# ad-hoc uploads), so the cutoff sits comfortably between 100 and 150.
_MIN_PLAUSIBLE_DIMENSION = 150


def _is_plausible_headshot(img: "Image.Image") -> bool:
    """Reject esportsdesk's small placeholder image, accept everything
    else. Earlier version of this check rejected any square image on the
    theory that headshots are portrait -- wrong: SkyCity Stampede's Lachlan
    Frear has a genuine 600x600 square headshot that got misclassified as a
    placeholder until this was caught via a live spot-check. Size, not
    aspect ratio, is what actually distinguishes the two."""
    w, h = img.size
    return w >= _MIN_PLAUSIBLE_DIMENSION and h >= _MIN_PLAUSIBLE_DIMENSION


def _looks_like_image(resp) -> bytes | None:
    """Return raw bytes if `resp` is really a plausible headshot photo, else
    None. Guards against esportsdesk's 200-OK-with-HTML-body 404 AND its
    200-OK-with-team-logo-placeholder "no photo" behaviour."""
    if resp.status_code != 200:
        return None
    content_type = resp.headers.get("Content-Type", "")
    if not content_type.startswith("image/"):
        return None
    try:
        img = Image.open(io.BytesIO(resp.content))
        img.load()
    except Exception:
        return None
    if not _is_plausible_headshot(img):
        return None
    return resp.content


def normalize_to_jpg(raw_bytes: bytes) -> bytes:
    """Return bytes for a canonical .jpg file.

    Idempotency matters here: this repo hash-compares downloaded bytes
    against the already-committed file to decide whether a run has anything
    new to commit. If we re-encoded every JPEG through PIL on every run, a
    Pillow version bump on the runner could silently change the encoder
    output and produce a spurious diff for a photo that hasn't actually
    changed. So: when the source is ALREADY a JPEG, keep the original bytes
    untouched (source files on esportsdesk don't change once uploaded, so
    the sha256 stays stable run over run). Only decode+re-encode when the
    source is a different format (PNG, etc. -- Dunedin Thunder's ad-hoc
    filenames include some) so every saved file still has a real .jpg
    extension.
    """
    img = Image.open(io.BytesIO(raw_bytes))
    if img.format == "JPEG":
        return raw_bytes
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    elif img.mode == "L":
        img = img.convert("RGB")
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=95)
    return out.getvalue()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def resolve_photo(
    team: Team, player_id: int | None, raw_full_name: str, override_full_name: str
) -> tuple[bytes | None, str | None]:
    """Try naive guesses first (fast), then the profile-page fallback
    (authoritative, requires a playerID -- unavailable for coaches).
    Returns (normalized_jpeg_bytes, source_url) or (None, None) if no real
    photo could be found anywhere."""
    candidates = naive_guess_urls(raw_full_name, override_full_name)
    for url in candidates:
        resp = fetch_binary(url)
        raw = _looks_like_image(resp)
        if raw is not None:
            return normalize_to_jpg(raw), url

    if player_id is not None:
        fallback_url = fetch_profile_headshot_url(team, player_id)
        if fallback_url:
            resp = fetch_binary(fallback_url)
            raw = _looks_like_image(resp)
            if raw is not None:
                return normalize_to_jpg(raw), fallback_url

    return None, None
