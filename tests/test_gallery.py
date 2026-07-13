from player_photos import gallery


def test_build_gallery_html_is_a_redirect_stub():
    """2026-07-13: the browsable gallery was retired in favor of the single
    consolidated view at hockey/warehouse/#photos -- this repo's index.html
    is now just a redirect stub. Also confirms the function still accepts
    (and ignores) whatever args old callers used to pass, since cli.py's
    contract with this function shouldn't need to change again if a caller
    forgets to update."""
    html = gallery.build_gallery_html()
    assert gallery.REDIRECT_URL in html
    assert "<html" in html

    # accepts arbitrary args/kwargs without error
    html2 = gallery.build_gallery_html({"some": "manifest"}, ["ADM"], stats_index={"x": "y"})
    assert html2 == html
