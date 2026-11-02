"""Movie posters from TMDB (themoviedb.org), shown in the Streamlit app.

The token comes from the environment variable TMDB_TOKEN (never from code or git).
Without it, or if TMDB is unreachable, the app shows plain placeholders and keeps working.
Images are loaded by the viewer's browser straight from TMDB's image server; nothing is stored.
"""
import json
import os
import urllib.error
import urllib.request

import streamlit as st

IMG_BASE = "https://image.tmdb.org/t/p/w342"
CREDIT = "Posters: TMDB. This product uses the TMDB API but is not endorsed or certified by TMDB."


def enabled() -> bool:
    return bool(os.getenv("TMDB_TOKEN"))


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def _lookup(tmdb_id: int):
    """Poster URL, or None if TMDB has none. Network errors raise, so they are NOT cached."""
    req = urllib.request.Request(
        f"https://api.themoviedb.org/3/movie/{int(tmdb_id)}",
        headers={"Authorization": "Bearer " + os.environ["TMDB_TOKEN"], "accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            path = json.loads(r.read()).get("poster_path")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    return IMG_BASE + path if path else None


def poster_url(tmdb_id):
    if not enabled() or tmdb_id is None:
        return None
    try:
        return _lookup(int(tmdb_id))
    except Exception:
        return None


def show(items, per_row: int = 5, width: int = 150):
    """items: list of (caption, tmdb_id or None). Shows a row of posters, placeholders when missing."""
    for start in range(0, len(items), per_row):
        cols = st.columns(per_row)
        for col, (caption, tmdb_id) in zip(cols, items[start:start + per_row]):
            url = poster_url(tmdb_id)
            if url:
                col.image(url, caption=caption, width=width)
            else:
                col.markdown(
                    f"<div style='width:{width}px;height:{int(width * 1.5)}px;background:#2a3446;color:#aab4c3;"
                    "display:flex;align-items:center;justify-content:center;border-radius:6px;font-size:12px'>"
                    "no poster</div>",
                    unsafe_allow_html=True,
                )
                col.caption(caption)
