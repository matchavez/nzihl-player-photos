"""Generates this repo's index.html.

This repo is the data warehouse (photos/ + manifest.json) for NZIHL/NZWIHL
player + coach headshots. It used to also serve a browsable gallery UI at
this Pages URL, but as of 2026-07-13 that was retired -- Mat pointed out it
was just duplicating https://matchavez.com/hockey/warehouse/#photos, which
already fetches this repo's manifest.json live (plus stat lines from the
roster repos' stats.json -- see that repo's warehouse/index.html for the
join logic this module used to have). One browsable view, not two.

This module now just emits a redirect stub so the old Pages URL sends
anyone who still has it bookmarked somewhere useful instead of 404ing or
showing a stale gallery. `cli.run()` still calls this every run (cheap,
no manifest/network dependency) so `index.html` keeps existing for the
repo's existing tests/automation contract.
"""
from __future__ import annotations

REDIRECT_URL = "https://matchavez.com/hockey/warehouse/#photos"


def build_gallery_html(*_args, **_kwargs) -> str:
    """Signature accepts (and ignores) any args so callers that used to pass
    manifest/league_order/stats_index don't need to change."""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="0; url={REDIRECT_URL}">
<link rel="canonical" href="{REDIRECT_URL}">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Moved -- NZIHL / NZWIHL Player Photo Warehouse</title>
<style>
body{{background:#0b0c0f;color:#f2f3f5;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,Arial,sans-serif;
     display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;text-align:center;padding:24px;}}
a{{color:#5fb0ff;}}
p{{font-size:15px;max-width:420px;line-height:1.5;}}
</style>
</head>
<body>
<p>This gallery has moved to <a href="{REDIRECT_URL}">the NZIHL / NZWIHL Data Warehouse</a>.
If you're not redirected automatically, click the link.</p>
</body>
</html>
"""
