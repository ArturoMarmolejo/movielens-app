"""MovieLens 32M explorer: a small Streamlit front end for the Gold tables.

Run:  streamlit run app.py
Demo: MOVIELENS_DEMO=1 streamlit run app.py     (made-up data, no connection)
"""
import json

import altair as alt
import pandas as pd
import streamlit as st

import data

TEAL, ORANGE, NAVY = "#0F7B7D", "#D9670F", "#1B2A41"

st.set_page_config(page_title="MovieLens explorer", page_icon=None, layout="wide")


@st.cache_data(ttl=600, show_spinner="Reading the Gold tables...")
def load(name: str) -> pd.DataFrame:
    return getattr(data, name)()


st.title("MovieLens 32M explorer")
st.caption("Reads only the Gold tables built by our pipeline (Bronze > Silver > Gold). Read-only.")
if data.DEMO:
    st.warning("DEMO MODE: made-up sample data, not real results.")

try:
    monthly = load("monthly_activity")
    genre_year = load("genre_year_stats")
    top = load("top_movies_by_genre")
except Exception as e:  # connection or permission problem
    st.error("Could not read the Gold tables. Check the three DATABRICKS_* environment variables and that the SQL warehouse is running.")
    st.exception(e)
    st.stop()

tab_overview, tab_genres, tab_top, tab_find, tab_ask, tab_health, tab_compare, tab_reco = st.tabs(
    ["Overview", "Genres", "Top movies", "Movie finder", "Ask (Genie)", "Pipeline health", "Compare movies", "Recommendations"]
)

# ------------------------------------------------------------------ overview
with tab_overview:
    total = int(monthly.ratings_count.sum())
    busiest = monthly.loc[monthly.ratings_count.idxmax()]
    weighted = float((monthly.avg_rating * monthly.ratings_count).sum() / total)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total ratings", f"{total:,}")
    c2.metric("Months covered", f"{len(monthly):,}")
    c3.metric("Busiest month", f"{int(busiest.rating_year)}-{int(busiest.rating_month):02d}")
    c3.caption(f"{int(busiest.ratings_count):,} ratings")
    c4.metric("Average rating", f"{weighted:.2f}")

    per_year = monthly.groupby("rating_year", as_index=False).agg(ratings=("ratings_count", "sum"))
    st.subheader("Ratings per year")
    st.altair_chart(
        alt.Chart(per_year).mark_bar(color=TEAL, cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
            x=alt.X("rating_year:O", title="Year"), y=alt.Y("ratings:Q", title="Ratings"),
            tooltip=["rating_year", alt.Tooltip("ratings:Q", format=",")]).properties(height=320),
        width="stretch")

    st.subheader("Ten busiest months")
    t = monthly.nlargest(10, "ratings_count")[["rating_year", "rating_month", "ratings_count", "active_users"]]
    st.dataframe(t.rename(columns={"rating_year": "Year", "rating_month": "Month", "ratings_count": "Ratings", "active_users": "Active users"}),
                 hide_index=True, width="stretch")

# -------------------------------------------------------------------- genres
with tab_genres:
    all_genres = sorted(genre_year.genre.unique())
    chosen = st.multiselect("Genres", all_genres, default=[g for g in ["Drama", "Comedy", "Action"] if g in all_genres])
    metric = st.radio("Show", ["Ratings per year", "Average rating per year"], horizontal=True)
    sub = genre_year[genre_year.genre.isin(chosen)]
    if sub.empty:
        st.info("Pick at least one genre.")
    else:
        col = "ratings_count" if metric == "Ratings per year" else "avg_rating"
        st.altair_chart(
            alt.Chart(sub).mark_line(point=True, strokeWidth=2).encode(
                x=alt.X("rating_year:O", title="Year"), y=alt.Y(f"{col}:Q", title=metric, scale=alt.Scale(zero=col == "ratings_count")),
                color=alt.Color("genre:N", title="Genre"), tooltip=["genre", "rating_year", col]).properties(height=360),
            width="stretch")
    st.subheader("All genres, all years")
    gtot = genre_year.groupby("genre").apply(
        lambda d: pd.Series({"ratings": d.ratings_count.sum(), "avg_rating": (d.avg_rating * d.ratings_count).sum() / d.ratings_count.sum()}),
        include_groups=False).reset_index().sort_values("ratings", ascending=False)
    st.altair_chart(
        alt.Chart(gtot).mark_bar(color=ORANGE).encode(
            y=alt.Y("genre:N", sort="-x", title=None), x=alt.X("ratings:Q", title="Ratings"),
            tooltip=["genre", alt.Tooltip("ratings:Q", format=","), alt.Tooltip("avg_rating:Q", format=".3f")]).properties(height=420),
        width="stretch")

# ----------------------------------------------------------------- top movies
with tab_top:
    g = st.selectbox("Genre", sorted(top.genre.unique()))
    st.caption("Only movies with at least 1,000 ratings are ranked. Best average first; ties broken by number of ratings.")
    t = top[top.genre == g].sort_values("rank_in_genre")
    st.dataframe(t.rename(columns={"rank_in_genre": "Rank", "title_clean": "Title", "release_year": "Year", "ratings_count": "Ratings", "avg_rating": "Average"})
                 [["Rank", "Title", "Year", "Ratings", "Average"]], hide_index=True, width="stretch")
    st.altair_chart(
        alt.Chart(t).mark_bar(color=TEAL).encode(
            y=alt.Y("title_clean:N", sort=alt.EncodingSortField("rank_in_genre"), title=None),
            x=alt.X("avg_rating:Q", title="Average rating", scale=alt.Scale(domain=[0, 5])),
            tooltip=["title_clean", "release_year", "ratings_count", "avg_rating"]).properties(height=320),
        width="stretch")

# ---------------------------------------------------------------- movie finder
with tab_find:
    q = st.text_input("Part of a title", "movie" if data.DEMO else "star")
    m = st.slider("Minimum number of ratings", 1, 5000, 1000)
    if q.strip():
        try:
            res = data.find_movies(q.strip(), m)
            st.dataframe(res.rename(columns={"title_clean": "Title", "release_year": "Year", "ratings_count": "Ratings", "avg_rating": "Average"}),
                         hide_index=True, width="stretch")
        except Exception as e:
            st.error("The search failed.")
            st.exception(e)

# ------------------------------------------------------------------ ask genie
with tab_ask:
    st.write("Ask a question in plain English. The question goes to our Genie space, which writes SQL over the four Gold tables, runs it, and answers. "
             "Always check the SQL: AI answers can be wrong.")
    if not data.genie_configured():
        st.info("Set the environment variable GENIE_SPACE_ID (the ID in your Genie space's web address) and restart the app to enable this tab.")
    else:
        if "chat" not in st.session_state:
            st.session_state.chat = []
            st.session_state.conv = None
        if st.button("New conversation"):
            st.session_state.chat, st.session_state.conv = [], None
        for m in st.session_state.chat:
            with st.chat_message(m["role"]):
                st.markdown(m["text"])
                if m.get("sql"):
                    with st.expander("Show SQL"):
                        st.code(m["sql"], language="sql")
                if m.get("table") is not None:
                    st.dataframe(m["table"], hide_index=True, width="stretch")
        question = st.chat_input("For example: Which month had the most ratings?")
        if question:
            st.session_state.chat.append({"role": "user", "text": question})
            with st.chat_message("user"):
                st.markdown(question)
            with st.chat_message("assistant"):
                with st.spinner("Genie is working..."):
                    try:
                        r = data.genie_ask(question, st.session_state.conv)
                        st.session_state.conv = r["conversation_id"]
                        text = r["text"] or ("Genie returned an error: " + r["error"] if r["error"] else "No text answer.")
                        st.markdown(text)
                        if r["sql"]:
                            with st.expander("Show SQL"):
                                st.code(r["sql"], language="sql")
                        if r["table"] is not None:
                            st.dataframe(r["table"], hide_index=True, width="stretch")
                        st.session_state.chat.append({"role": "assistant", "text": text, "sql": r["sql"], "table": r["table"]})
                    except Exception as e:
                        st.error("Could not reach Genie. Check GENIE_SPACE_ID, that the token's scope allows Genie, and that you can open the space.")
                        st.exception(e)

# ------------------------------------------------------------- pipeline health
with tab_health:
    st.write("Every pipeline step writes a JSON report into the Delta table `dq_reports`. This tab reads the latest rows.")
    try:
        dq = load("quality_reports")
        rows = []
        for _, r in dq.iterrows():
            try:
                rep = json.loads(r.report_json)
            except Exception:
                rep = {}
            rows.append({"Time": r.run_ts, "Step": r.step, "Batch": r.ingest_date,
                         "Rows in": rep.get("rows_in", rep.get("movies_in", rep.get("silver_ratings"))),
                         "Rejected %": rep.get("rejected_pct"),
                         "Passed": rep.get("passed")})
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        with st.expander("Show one raw JSON report"):
            if len(dq):
                pick = st.selectbox("Step", dq.step.unique())
                st.json(json.loads(dq[dq.step == pick].iloc[0].report_json))
    except Exception as e:
        st.error("Could not read dq_reports.")
        st.exception(e)

# ------------------------------------------------------------ compare movies
@st.cache_data(ttl=600, show_spinner="Searching...")
def search_movies(text: str, min_ratings: int) -> pd.DataFrame:
    return data.find_movies(text, min_ratings, limit=20).reset_index(drop=True)


with tab_compare:
    st.subheader("Compare two movies")
    st.caption("Type part of a title for each side, pick a result, and compare. Source: gold_movie_stats.")
    min_r = st.slider("Minimum number of ratings", 1, 5000, 100, key="cmp_min")
    picks = []
    for col, tag in zip(st.columns(2), ("A", "B")):
        with col:
            text = st.text_input(f"Movie {tag}: title contains", key=f"cmp_text_{tag}")
            if not text.strip():
                picks.append(None)
                continue
            found = search_movies(text.strip(), min_r)
            if found.empty:
                st.info("No movie found. Try a shorter title or lower the minimum.")
                picks.append(None)
                continue
            labels = [f"{r.title_clean} ({int(r.release_year)})" if pd.notna(r.release_year) else r.title_clean
                      for r in found.itertuples()]
            i = st.selectbox(f"Pick movie {tag}", range(len(found)), format_func=labels.__getitem__, key=f"cmp_pick_{tag}")
            picks.append((tag, labels[i], found.iloc[i]))

    if all(picks):
        rows = pd.DataFrame({
            "Movie": [f"{t}: {lbl}" for t, lbl, _ in picks],
            "Ratings": [int(r.ratings_count) for _, _, r in picks],
            "Average rating": [round(float(r.avg_rating), 2) for _, _, r in picks],
        })
        st.dataframe(rows, hide_index=True, width="stretch")
        diff = rows["Average rating"][0] - rows["Average rating"][1]
        if diff == 0:
            st.write("Both movies have the same average rating.")
        else:
            better = rows["Movie"][0] if diff > 0 else rows["Movie"][1]
            st.write(f"{better} is rated higher by {abs(diff):.2f} points.")
            rows["Side"] = ["A", "B"]
        colors = alt.Scale(range=[TEAL, ORANGE])
        c1, c2 = st.columns(2)
        for chart_col, field, title, domain in (
            (c1, "Average rating", "Average rating (0 to 5)", [0, 5]),
            (c2, "Ratings", "Number of ratings", None),
        ):
            y_scale = alt.Scale(domain=domain) if domain else alt.Undefined
            chart_col.altair_chart(
                alt.Chart(rows).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
                    x=alt.X("Side:N", title=None, sort=None, axis=alt.Axis(labelAngle=0)),
                    y=alt.Y(f"{field}:Q", title=title, scale=y_scale),
                    color=alt.Color("Movie:N", scale=colors, legend=alt.Legend(orient="bottom", title=None, labelLimit=400)),
                    tooltip=["Movie", alt.Tooltip(f"{field}:Q", format=",")]).properties(height=300),
                width="stretch")
    else:
        st.caption("Search and pick both movies to see the comparison.")



# ------------------------------------------------------------ recommendations
@st.cache_data(ttl=600, show_spinner="Searching...")
def reco_search(text: str) -> pd.DataFrame:
    return data.similar_search(text).reset_index(drop=True)


@st.cache_data(ttl=600)
def reco_similar(movie_id: int) -> pd.DataFrame:
    return data.similar_to(movie_id)


@st.cache_data(ttl=600)
def reco_user(user_id: int) -> pd.DataFrame:
    return data.user_recommendations(user_id)


with tab_reco:
    st.subheader("Recommendations")
    st.caption("Made with an ALS model (Spark MLlib) trained on a 10% sample of users. "
               "Similar movies cover the 5,000 most-rated titles.")
    left, right = st.columns(2)
    with left:
        st.markdown("**If you liked...**")
        text = st.text_input("Part of a title", key="reco_text")
        if text.strip():
            found = reco_search(text.strip())
            if found.empty:
                st.info("No match among the 5,000 most-rated movies.")
            else:
                labels = [f"{r.title} ({int(r.year)})" if pd.notna(r.year) else r.title for r in found.itertuples()]
                i = st.selectbox("Pick a movie", range(len(found)), format_func=labels.__getitem__, key="reco_pick")
                sim = reco_similar(int(found.iloc[i].movieId))
                st.dataframe(sim.rename(columns={"rank": "Rank", "similar_title": "Similar movie", "similar_year": "Year", "similarity": "Similarity"}),
                             hide_index=True, width="stretch")
    with right:
        st.markdown("**Picks for a user**")
        uid = st.number_input("User ID (multiples of 10, starting at 10)", min_value=1, value=10, step=10, key="reco_user")
        recs = reco_user(int(uid))
        if recs.empty:
            st.info("No recommendations for that user. Try 10, 20 or 30.")
        else:
            st.dataframe(recs.rename(columns={"rank": "Rank", "title_clean": "Title", "release_year": "Year", "predicted_rating": "Predicted rating"}),
                         hide_index=True, width="stretch")




# ------------------------------------------------------- quality trend (health)
with tab_health:
    st.divider()
    st.subheader("Quality trend over runs")
    st.caption("One row per pipeline run (a run ends at its validate step). Source: view v_dq_trend.")
    try:
        tr = load("dq_trend")
        if tr.empty:
            st.info("No runs recorded yet.")
        else:
            tr = tr.copy()
            tr["run_ts"] = pd.to_datetime(tr["run_ts"])
            tr = tr.sort_values("run_ts").reset_index(drop=True)
            tr["run_no"] = tr["step"].eq("validate").shift(fill_value=False).cumsum() + 1
            tr["failed"] = tr["passed"].eq(False).astype(int)
            runs = tr.groupby("run_no").agg(
                started=("run_ts", "min"), finished=("run_ts", "max"),
                ratings=("rows_out", "sum"), worst=("rejected_pct", "max"), failed=("failed", "sum")).reset_index()
            runs["worst"] = runs["worst"].fillna(0.0)
            runs["Started"] = runs["started"].dt.strftime("%b %d %H:%M")
            runs["Duration (min)"] = ((runs["finished"] - runs["started"]).dt.total_seconds() / 60).round(1)
            runs["Status"] = ["OK" if (f == 0 and w <= 1) else "Check" for f, w in zip(runs["failed"], runs["worst"])]
            show = runs.rename(columns={"ratings": "Ratings processed", "worst": "Worst rejected %", "failed": "Failed checks"})
            st.dataframe(show[["Started", "Duration (min)", "Ratings processed", "Worst rejected %", "Failed checks", "Status"]],
                         hide_index=True, width="stretch")

            c1, c2 = st.columns(2)
            top = max(1.5, float(runs["worst"].max()) * 1.2)
            bars = alt.Chart(runs).mark_bar(color=TEAL, cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
                x=alt.X("Started:N", title=None, sort=None, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("worst:Q", title="Worst rejected % (limit 1%)", scale=alt.Scale(domain=[0, top])),
                tooltip=["Started", alt.Tooltip("worst:Q", format=".2f")]).properties(height=260)
            limit = alt.Chart(pd.DataFrame({"y": [1.0]})).mark_rule(color=ORANGE, strokeDash=[4, 4]).encode(y="y:Q")
            c1.altair_chart(bars + limit, width="stretch")
            c2.altair_chart(
                alt.Chart(runs).mark_bar(color=TEAL, cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
                    x=alt.X("Started:N", title=None, sort=None, axis=alt.Axis(labelAngle=0)),
                    y=alt.Y("ratings:Q", title="Ratings processed"),
                    tooltip=["Started", alt.Tooltip("ratings:Q", format=",")]).properties(height=260),
                width="stretch")
    except Exception as e:
        st.error("Could not read the quality trend.")
        st.exception(e)
