import io
from dataclasses import dataclass

from PIL import Image

from player_photos.photos import (
    naive_guess_urls,
    normalize_to_jpg,
    sha256_hex,
    _looks_like_image,
    _is_plausible_headshot,
)


def _make_image_bytes(size, fmt="JPEG", mode="RGB"):
    img = Image.new(mode, size, color=(120, 130, 140))
    out = io.BytesIO()
    img.save(out, format=fmt)
    return out.getvalue()


@dataclass
class FakeResponse:
    status_code: int
    headers: dict
    content: bytes


def test_naive_guess_urls_strip_whitespace_and_dedup():
    urls = naive_guess_urls("Benjamin De Jonge", "Benjamin De Jonge")
    assert urls == [
        "https://admin.esportsdesk.com/media/leagues/6795/graphics/BenjaminDeJonge.jpg"
    ]


def test_naive_guess_urls_two_distinct_names():
    urls = naive_guess_urls("benjamin de jonge", "Benjamin De Jonge")
    assert len(urls) == 2
    assert urls[0] != urls[1]


def test_looks_like_image_accepts_portrait_photo():
    data = _make_image_bytes((600, 750))
    resp = FakeResponse(200, {"Content-Type": "image/jpeg"}, data)
    assert _looks_like_image(resp) == data


def test_looks_like_image_rejects_tiny_placeholder():
    # esportsdesk serves a real, valid, 200-status 100x100 team-logo image
    # as a "no photo" placeholder for players/coaches with no real headshot
    # -- this is the exact false-positive caught during development
    # (Benjamin De Jonge's naive-guess/profile fallback both resolved to a
    # 100x100 team crest before this guard was added).
    data = _make_image_bytes((100, 100))
    resp = FakeResponse(200, {"Content-Type": "image/jpeg"}, data)
    assert _looks_like_image(resp) is None


def test_looks_like_image_accepts_genuine_square_photo():
    # A real headshot can legitimately be square (SkyCity Stampede's Lachlan
    # Frear is 600x600) -- an earlier "reject anything non-portrait" version
    # of this check misclassified real square photos as placeholders. Size,
    # not aspect ratio, is what distinguishes a real photo from the 100x100
    # placeholder.
    data = _make_image_bytes((600, 600))
    resp = FakeResponse(200, {"Content-Type": "image/jpeg"}, data)
    assert _looks_like_image(resp) == data


def test_looks_like_image_accepts_landscape_above_threshold():
    data = _make_image_bytes((800, 600))
    resp = FakeResponse(200, {"Content-Type": "image/jpeg"}, data)
    assert _looks_like_image(resp) == data


def test_looks_like_image_rejects_non_200():
    resp = FakeResponse(404, {"Content-Type": "image/jpeg"}, b"")
    assert _looks_like_image(resp) is None


def test_looks_like_image_rejects_html_disguised_as_jpg():
    # esportsdesk returns 200 OK with an HTML "not found" page body for a
    # genuinely missing image, not a real 404 status.
    resp = FakeResponse(200, {"Content-Type": "text/html;charset=UTF-8"}, b"<html>not found</html>")
    assert _looks_like_image(resp) is None


def test_is_plausible_headshot_small_ad_hoc_upload_ok():
    # Dunedin-style ad-hoc uploads, smallest real photo size observed.
    assert _is_plausible_headshot(Image.new("RGB", (150, 199))) is True


def test_is_plausible_headshot_genuine_square_photo_ok():
    assert _is_plausible_headshot(Image.new("RGB", (600, 600))) is True


def test_is_plausible_headshot_placeholder_rejected():
    assert _is_plausible_headshot(Image.new("RGB", (100, 100))) is False


def test_is_plausible_headshot_tiny_rejected():
    assert _is_plausible_headshot(Image.new("RGB", (10, 15))) is False


def test_normalize_to_jpg_keeps_jpeg_bytes_unchanged():
    # Idempotency guard: a real JPEG source must round-trip byte-identical
    # so re-running against an unchanged source never produces a diff.
    data = _make_image_bytes((300, 400), fmt="JPEG")
    assert normalize_to_jpg(data) == data


def test_normalize_to_jpg_converts_png_to_jpeg():
    data = _make_image_bytes((300, 400), fmt="PNG")
    out = normalize_to_jpg(data)
    assert out != data
    img = Image.open(io.BytesIO(out))
    assert img.format == "JPEG"
    assert img.size == (300, 400)


def test_sha256_hex_stable():
    data = b"hello world"
    assert sha256_hex(data) == sha256_hex(data)
    assert sha256_hex(data) != sha256_hex(b"hello world!")
