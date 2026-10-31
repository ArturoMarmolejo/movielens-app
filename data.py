"""Data access for the MovieLens app. Read-only, fixed queries only.

Real mode : reads the Gold tables from a Databricks SQL warehouse.
            Connection details come from environment variables (never from code):
              DATABRICKS_SERVER_HOSTNAME, DATABRICKS_HTTP_PATH, DATABRICKS_TOKEN
Demo mode : set MOVIELENS_DEMO=1 to use made-up sample data (no connection needed).
"""
import json
import os

import numpy as np
import pandas as pd

CATALOG = os.getenv("MOVIELENS_CATALOG", "arturo_movielens")
SCHEMA = os.getenv("MOVIELENS_SCHEMA", "movielens")
DEMO = os.getenv("MOVIELENS_DEMO") == "1"


def table(name: str) -> str:
    return f"{CATALOG}.{SCHEMA}.{name}"


_conn = None


def _connection():
    global _conn
    if _conn is None:
        from databricks import sql  # imported here so demo mode needs no connector

        missing = [k for k in ("DATABRICKS_SERVER_HOSTNAME", "DATABRICKS_HTTP_PATH", "DATABRICKS_TOKEN") if not os.getenv(k)]
        if missing:
            raise RuntimeError("Missing environment variables: " + ", ".join(missing))
        _conn = sql.connect(
            server_hostname=os.environ["DATABRICKS_SERVER_HOSTNAME"],
            http_path=os.environ["DATABRICKS_HTTP_PATH"],
            access_token=os.environ["DATABRICKS_TOKEN"],
        )
    return _conn


def _run(sql_text: str, params: dict | None = None) -> pd.DataFrame:
    with _connection().cursor() as cur:
        cur.execute(sql_text, params or {})
        return cur.fetchall_arrow().to_pandas()


# ---------------------------------------------------------------- demo data
def _demo_frames():
    rng = np.random.default_rng(7)
    years = list(range(1995, 2024))
    base = np.array([0.6, 0.5, 0.3, 0.6, 1.0, 1.9, 1.1, 0.8, 1.0, 1.1, 1.0, 0.9, 0.8, 0.8, 0.7, 0.6, 0.6, 0.5, 0.5, 0.4, 1.0, 1.9, 1.8, 1.7, 1.4, 1.4, 1.3, 1.0, 0.8, 0.7])[: len(years)]
    rows = []
    for y, b in zip(years, base):
        for m in range(1, 13):
            n = int(b * 1e6 / 12 * rng.uniform(0.7, 1.3))
            rows.append((y, m, n, int(n / 40), round(float(rng.uniform(3.3, 3.8)), 3)))
    monthly = pd.DataFrame(rows, columns=["rating_year", "rating_month", "ratings_count", "active_users", "avg_rating"])
    genres = ["Action", "Adventure", "Animation", "Children", "Comedy", "Crime", "Documentary", "Drama", "Fantasy", "Film-Noir", "Horror", "IMAX", "Musical", "Mystery", "Romance", "Sci-Fi", "Thriller", "War", "Western"]
    weight = rng.uniform(0.2, 1.0, len(genres))
    gy = []
    for g, w in zip(genres, weight):
        for y, b in zip(years, base):
            n = int(b * 1e5 * w * rng.uniform(0.8, 1.2))
            gy.append((g, y, n, round(float(rng.uniform(3.0, 4.0)), 3), int(n / 30)))
    genre_year = pd.DataFrame(gy, columns=["genre", "rating_year", "ratings_count", "avg_rating", "users"])
    top = []
    for g in genres:
        for r in range(1, 11):
            top.append((g, r, f"Sample Movie {g[:3]} {r}", int(rng.integers(1950, 2022)), int(rng.integers(1000, 90000)), round(4.5 - r * 0.03 - rng.uniform(0, 0.05), 3)))
    top_movies = pd.DataFrame(top, columns=["genre", "rank_in_genre", "title_clean", "release_year", "ratings_count", "avg_rating"])
    movies = pd.DataFrame({"title_clean": [f"Sample Movie {i}" for i in range(500)], "release_year": rng.integers(1930, 2023, 500),
                           "ratings_count": rng.integers(1, 60000, 500), "avg_rating": np.round(rng.uniform(2.0, 4.6, 500), 3)})
    reports = []
    for step in ["silver_dims"] + [f"silver_ratings_{a}_{b}" for a, b in [(1995, 1999), (2000, 2004), (2005, 2009), (2010, 2014), (2015, 2019), (2020, 2023)]] + ["gold", "validate"]:
        reports.append((pd.Timestamp("2026-01-01 10:00"), step, "2026-10-20", json.dumps({"demo": True, "passed": True, "rejected_pct": 0.0})))
    dq = pd.DataFrame(reports, columns=["run_ts", "step", "ingest_date", "report_json"])
    return dict(monthly=monthly, genre_year=genre_year, top=top_movies, movies=movies, dq=dq)


_DEMO = _demo_frames() if DEMO else None


# ---------------------------------------------------------------- queries
def monthly_activity() -> pd.DataFrame:
    if DEMO:
        return _DEMO["monthly"].copy()
    return _run(f"SELECT rating_year, rating_month, ratings_count, active_users, avg_rating FROM {table('gold_monthly_activity')}")


def genre_year_stats() -> pd.DataFrame:
    if DEMO:
        return _DEMO["genre_year"].copy()
    return _run(f"SELECT genre, rating_year, ratings_count, avg_rating, users FROM {table('gold_genre_year_stats')}")


def top_movies_by_genre() -> pd.DataFrame:
    if DEMO:
        return _DEMO["top"].copy()
    return _run(f"SELECT genre, rank_in_genre, title_clean, release_year, ratings_count, avg_rating FROM {table('gold_top_movies_by_genre')}")


def find_movies(text: str, min_ratings: int, limit: int = 50) -> pd.DataFrame:
    if DEMO:
        d = _DEMO["movies"]
        d = d[d.title_clean.str.lower().str.contains(text.lower()) & (d.ratings_count >= min_ratings)]
        return d.sort_values("avg_rating", ascending=False).head(limit)
    return _run(
        f"SELECT title_clean, release_year, ratings_count, avg_rating FROM {table('gold_movie_stats')} "
        "WHERE ratings_count >= :min_ratings AND lower(title_clean) LIKE :pattern "
        f"ORDER BY avg_rating DESC, ratings_count DESC LIMIT {int(limit)}",
        {"min_ratings": int(min_ratings), "pattern": "%" + text.lower() + "%"},
    )


def quality_reports() -> pd.DataFrame:
    if DEMO:
        return _DEMO["dq"].copy()
    return _run(f"SELECT run_ts, step, ingest_date, report_json FROM {table('dq_reports')} ORDER BY run_ts DESC LIMIT 100")


# ------------------------------------------------------------ Genie chatbot
# Calls the Genie space through the Databricks SDK (Genie Conversation API).
# Extra environment variable: GENIE_SPACE_ID (the ID in the Genie space's URL).
MAX_ROWS_SHOWN = 200
_workspace = None


def genie_configured() -> bool:
    return DEMO or bool(os.getenv("GENIE_SPACE_ID"))


def _client():
    global _workspace
    if _workspace is None:
        from databricks.sdk import WorkspaceClient

        _workspace = WorkspaceClient(
            host="https://" + os.environ["DATABRICKS_SERVER_HOSTNAME"].replace("https://", "").strip("/"),
            token=os.environ["DATABRICKS_TOKEN"],
        )
    return _workspace


def _demo_genie(question: str) -> dict:
    q = question.lower()
    if "month" in q:
        return {"conversation_id": "demo", "text": "DEMO: December 1999 had the most ratings (made-up answer).",
                "sql": "SELECT * FROM gold_monthly_activity ORDER BY ratings_count DESC LIMIT 1",
                "table": pd.DataFrame({"rating_year": [1999], "rating_month": [12], "ratings_count": [444681]}), "error": None}
    return {"conversation_id": "demo", "text": "DEMO MODE: this is a canned reply, not Genie. Try asking which month had the most ratings.",
            "sql": None, "table": None, "error": None}


def genie_ask(question: str, conversation_id: str | None = None, timeout_minutes: int = 3) -> dict:
    """Send one question to the Genie space. Returns text, the SQL Genie wrote, and the result table.

    Genie itself runs the SQL (on the warehouse, with the token owner's permissions). This app never
    executes SQL written by the model.
    """
    if DEMO:
        return _demo_genie(question)
    from datetime import timedelta

    space_id = os.environ["GENIE_SPACE_ID"]
    w = _client()
    wait = timedelta(minutes=timeout_minutes)
    if conversation_id:
        msg = w.genie.create_message_and_wait(space_id, conversation_id, question, timeout=wait)
    else:
        msg = w.genie.start_conversation_and_wait(space_id, question, timeout=wait)
    conv = getattr(msg, "conversation_id", None) or conversation_id
    mid = getattr(msg, "message_id", None) or getattr(msg, "id", None)
    out = {"conversation_id": conv, "text": "", "sql": None, "table": None, "error": None}
    err = getattr(msg, "error", None)
    if err is not None:
        out["error"] = str(getattr(err, "error", None) or err)
    texts = []
    for att in getattr(msg, "attachments", None) or []:
        t = getattr(att, "text", None)
        if t is not None and getattr(t, "content", None):
            texts.append(t.content)
        qa = getattr(att, "query", None)
        if qa is not None and getattr(qa, "query", None):
            out["sql"] = qa.query
            if getattr(qa, "description", None):
                texts.append(qa.description)
            res = w.genie.get_message_attachment_query_result(space_id, conv, mid, att.attachment_id)
            sr = getattr(res, "statement_response", None)
            if sr is not None and getattr(sr, "manifest", None) and getattr(sr, "result", None):
                cols = [c.name for c in sr.manifest.schema.columns]
                rows = (sr.result.data_array or [])[:MAX_ROWS_SHOWN]
                out["table"] = pd.DataFrame(rows, columns=cols)
    out["text"] = "\n\n".join(texts)
    return out




# ------------------------------------------------------------ recommendations
def similar_search(text: str, limit: int = 20) -> pd.DataFrame:
    if DEMO:
        return pd.DataFrame(columns=["movieId", "title", "year"])
    return _run(
        f"SELECT DISTINCT movieId, title, year FROM {table('gold_similar_movies')} "
        f"WHERE lower(title) LIKE :pattern ORDER BY title LIMIT {int(limit)}",
        {"pattern": "%" + text.lower() + "%"},
    )


def similar_to(movie_id: int) -> pd.DataFrame:
    if DEMO:
        return pd.DataFrame(columns=["rank", "similar_title", "similar_year", "similarity"])
    return _run(
        f"SELECT rank, similar_title, similar_year, similarity FROM {table('gold_similar_movies')} "
        "WHERE movieId = :movie_id ORDER BY rank",
        {"movie_id": int(movie_id)},
    )


def user_recommendations(user_id: int) -> pd.DataFrame:
    if DEMO:
        return pd.DataFrame(columns=["rank", "title_clean", "release_year", "predicted_rating"])
    return _run(
        f"SELECT rank, title_clean, release_year, predicted_rating FROM {table('gold_recommendations')} "
        "WHERE userId = :user_id ORDER BY rank",
        {"user_id": int(user_id)},
    )



# ---------------------------------------------------------------- dq trend
def dq_trend() -> pd.DataFrame:
    if DEMO:
        return pd.DataFrame(columns=["run_ts", "step", "ingest_date", "rows_in", "rows_out", "rejected_rows", "rejected_pct", "passed"])
    return _run(f"SELECT run_ts, step, ingest_date, rows_in, rows_out, rejected_rows, rejected_pct, passed "
                f"FROM {table('v_dq_trend')} ORDER BY run_ts")
