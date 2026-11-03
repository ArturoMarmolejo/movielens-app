"""Movie posters from TMDB (themoviedb.org), shown in the Streamlit app.

The token comes from the environment variable TMDB_TOKEN (never from code or git).
Without it, or if TMDB is unreachable, the app shows plain placeholders and keeps working.
Images are loaded by the viewer's browser straight from TMDB's image server; nothing is stored.

MovieLens stores TMDB *movie* ids. A few titles (documentaries, mini-series) are TV shows at TMDB,
so when the movie lookup finds no poster we search the TV section by exact title and year.
"""
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

import streamlit as st

IMG_BASE = "https://image.tmdb.org/t/p/w342"
CREDIT = "Posters: TMDB. This product uses the TMDB API but is not endorsed or certified by TMDB."


def enabled() -> bool:
    return bool(os.getenv("TMDB_TOKEN"))


def _get(url: str) -> dict:
    req = urllib.request.Request(
        url, headers={"Authorization": "Bearer " + os.environ["TMDB_TOKEN"], "accept": "application/json"})
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.loads(r.read())


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def _lookup(tmdb_id: int):
    """Poster URL for a MOVIE id, or None. Network errors raise, so they are NOT cached."""
    try:
        path = _get(f"https://api.themoviedb.org/3/movie/{int(tmdb_id)}").get("poster_path")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    return IMG_BASE + path if path else None


def _norm(s: str) -> str:
    s = (s or "").lower().strip()
    if s.endswith(", the"):
        s = "the " + s[:-5]
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def _tv_lookup(title: str, year: int):
    """Poster URL of a TV show whose name matches the title exactly (and first aired that year)."""
    q = {"query": title}
    if year:
        q["first_air_date_year"] = year
    results = _get("https://api.themoviedb.org/3/search/tv?" + urllib.parse.urlencode(q)).get("results", [])
    want = _norm(title)
    for h in results:
        if h.get("poster_path") and want in (_norm(h.get("name")), _norm(h.get("original_name"))):
            return IMG_BASE + h["poster_path"]
    return None


def poster_url(tmdb_id, title=None, year=None):
    if not enabled():
        return None
    url = None
    if tmdb_id is not None:
        try:
            url = _lookup(int(tmdb_id))
        except Exception:
            url = None
    if url is None and title:
        try:
            y = int(year) if year is not None and year == year else 0
            url = _tv_lookup(str(title), y)
        except Exception:
            url = None
    return url


def show(items, per_row: int = 5, width: int = 150):
    """items: (caption, tmdb_id) or (caption, tmdb_id, title, year). Shows rows of posters;
    a plain placeholder when none is found."""
    for start in range(0, len(items), per_row):
        cols = st.columns(per_row)
        for col, item in zip(cols, items[start:start + per_row]):
            caption, tmdb_id, *rest = item
            title, year = (rest + [None, None])[:2]
            url = poster_url(tmdb_id, title, year)
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
