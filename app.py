"""MovieLens 32M explorer: a friendly Streamlit front end for the Gold tables.

Run:  streamlit run app.py
Demo: MOVIELENS_DEMO=1 streamlit run app.py     (made-up data, no connection)
"""
import json

import altair as alt
import pandas as pd
import streamlit as st

import data
import posters

TEAL, ORANGE, NAVY = "#0F7B7D", "#D9670F", "#1B2A41"

st.set_page_config(page_title="MovieLens explorer", page_icon=None, layout="wide")


# ------------------------------------------------------------------ helpers
def explain(text: str) -> None:
    """A short 'what you are looking at' note in plain English."""
    st.info(text)


def takeaway(text: str) -> None:
    """One-sentence insight, written from the data itself."""
    with st.container(border=True):
        st.markdown("**Key takeaway.** " + text)


def friendly_error(message: str, exc: Exception | None = None) -> None:
    """Plain message for everyone; the technical detail is tucked away."""
    st.error(message)
    if exc is not None:
        with st.expander("Technical details (for the developer)"):
            st.exception(exc)


RATING_COL = st.column_config.ProgressColumn(
    "Average rating", help="Average of all ratings, from 0.5 (worst) to 5 (best).",
    min_value=0, max_value=5, format="%.2f")
COUNT_HELP = "How many people rated this movie. More ratings means the average is more reliable."


@st.cache_data(ttl=600, show_spinner="Reading the data...")
def load(name: str) -> pd.DataFrame:
    return getattr(data, name)()


SHOW_POSTERS = False
if posters.enabled():
    SHOW_POSTERS = st.sidebar.checkbox("Show movie posters", value=True)


@st.cache_data(ttl=3600, show_spinner=False)
def tmdb_by_id(ids: tuple) -> dict:
    return data.tmdb_ids(ids)


@st.cache_data(ttl=3600, show_spinner=False)
def tmdb_by_title(pairs: tuple) -> dict:
    return data.tmdb_ids_by_title(pairs)


def posters_by_id(df, caption_fn, n=5, per_row=5):
    if not SHOW_POSTERS or df.empty or "movieId" not in df.columns:
        return
    d = df.head(n)
    ids = tmdb_by_id(tuple(int(i) for i in d["movieId"]))
    posters.show([(caption_fn(r), ids.get(int(r.movieId))) for r in d.itertuples()], per_row=per_row)


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.header("About this app")
    st.write("This page lets you explore **32 million movie ratings** from the MovieLens research dataset. "
             "No technical knowledge is needed: pick a tab, read the blue note at the top, and click around.")
    st.markdown("**Good to know**")
    st.markdown("- Ratings go from 0.5 to 5 stars.\n- People in the data are anonymous numbers.\n"
                "- The page only reads data. Nothing you do here changes it.")
    st.caption("New to a word? Open the **How it works** tab for a glossary.")

# --------------------------------------------------------------------- header
st.title("MovieLens 32M explorer")
st.caption("32 million ratings of movies, cleaned and checked by an automatic data pipeline, ready to explore.")
if data.DEMO:
    st.warning("DEMO MODE: made-up sample data, not real results.")

with st.expander("New here? Start with this (1 minute)", expanded=False):
    st.markdown(
        "**What is this?** Millions of people rated movies on a website called MovieLens. "
        "A data pipeline (an automatic assembly line for data) collected those ratings, fixed mistakes, "
        "checked the numbers and stored the results in tidy tables. This page shows what is inside them.")
    st.markdown("**Where should I click?**")
    st.table(pd.DataFrame({
        "Tab": ["Overview", "Genres", "Top movies", "Find a movie", "Ask a question (AI)", "Compare movies",
                "Recommendations", "Data health", "How it works"],
        "Use it to...": [
            "See the big picture: how many ratings, when people rated, and the average score.",
            "Compare kinds of movies (drama, comedy...) over the years.",
            "See the best-rated movies in each genre, with posters.",
            "Look up any movie by part of its title.",
            "Type a question in plain English and get an answer from AI.",
            "Put two movies side by side.",
            "Get movie suggestions based on a movie you liked, or for a sample user.",
            "Check that the data behind this page is complete and trustworthy.",
            "Learn how the data travelled from raw files to this page, and what the words mean."]}))

try:
    monthly = load("monthly_activity")
    genre_year = load("genre_year_stats")
    top = load("top_movies_by_genre")
except Exception as e:  # connection or permission problem
    friendly_error(
        "The page could not load its data right now. The data warehouse may still be waking up, which can take "
        "a minute or two. Please wait a moment and refresh the page. If it keeps happening, tell the app owner.", e)
    st.stop()

(tab_overview, tab_genres, tab_top, tab_find, tab_ask, tab_compare, tab_reco, tab_health, tab_how) = st.tabs(
    ["Overview", "Genres", "Top movies", "Find a movie", "Ask a question (AI)", "Compare movies",
     "Recommendations", "Data health", "How it works"])

# ------------------------------------------------------------------ overview
with tab_overview:
    explain("**What you are seeing:** the big picture of the whole dataset. Each rating is one person giving one movie "
            "a score from 0.5 to 5. The numbers below add up all 32 million of them.")
    total = int(monthly.ratings_count.sum())
    busiest = monthly.loc[monthly.ratings_count.idxmax()]
    weighted = float((monthly.avg_rating * monthly.ratings_count).sum() / total)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total ratings", f"{total:,}", help="Every rating in the dataset.")
    c2.metric("Months covered", f"{len(monthly):,}", help="From the first month with ratings to the last.")
    c3.metric("Busiest month", f"{int(busiest.rating_year)}-{int(busiest.rating_month):02d}",
              help="The single month with the most ratings (year-month).")
    c3.caption(f"{int(busiest.ratings_count):,} ratings")
    c4.metric("Average rating", f"{weighted:.2f}", help="Average score over all ratings, from 0.5 to 5.")

    per_year = monthly.groupby("rating_year", as_index=False).agg(ratings=("ratings_count", "sum"))
    peak = per_year.loc[per_year.ratings.idxmax()]
    takeaway(f"People rated movies from {int(per_year.rating_year.min())} to {int(per_year.rating_year.max())}. "
             f"The busiest year was {int(peak.rating_year)} with {int(peak.ratings):,} ratings, and the average score "
             f"overall is {weighted:.2f} out of 5.")

    st.subheader("Ratings per year")
    st.caption("Taller bar = more ratings that year. Hover over a bar to see the exact number.")
    st.altair_chart(
        alt.Chart(per_year).mark_bar(color=TEAL, cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
            x=alt.X("rating_year:O", title="Year"), y=alt.Y("ratings:Q", title="Number of ratings"),
            tooltip=[alt.Tooltip("rating_year:O", title="Year"), alt.Tooltip("ratings:Q", title="Ratings", format=",")]
        ).properties(height=320), width="stretch")

    st.subheader("Ten busiest months")
    st.caption("Active users = different people who rated something that month.")
    t = monthly.nlargest(10, "ratings_count")[["rating_year", "rating_month", "ratings_count", "active_users"]]
    st.dataframe(t.rename(columns={"rating_year": "Year", "rating_month": "Month", "ratings_count": "Ratings", "active_users": "Active users"}),
                 hide_index=True, width="stretch")

# -------------------------------------------------------------------- genres
with tab_genres:
    explain("**What you are seeing:** a genre is a kind of movie, such as Drama or Comedy. Pick genres to see how many "
            "ratings each got over the years, or how highly people scored them. One movie can belong to several genres.")
    all_genres = sorted(genre_year.genre.unique())
    chosen = st.multiselect("Genres to compare", all_genres, default=[g for g in ["Drama", "Comedy", "Action"] if g in all_genres])
    metric = st.radio("Show", ["Ratings per year", "Average rating per year"], horizontal=True,
                      help="Ratings per year = how popular. Average rating per year = how much people liked them.")
    sub = genre_year[genre_year.genre.isin(chosen)]
    if sub.empty:
        st.info("Pick at least one genre above to draw the chart.")
    else:
        col = "ratings_count" if metric == "Ratings per year" else "avg_rating"
        st.altair_chart(
            alt.Chart(sub).mark_line(point=True, strokeWidth=2).encode(
                x=alt.X("rating_year:O", title="Year"), y=alt.Y(f"{col}:Q", title=metric, scale=alt.Scale(zero=col == "ratings_count")),
                color=alt.Color("genre:N", title="Genre"),
                tooltip=[alt.Tooltip("genre:N", title="Genre"), alt.Tooltip("rating_year:O", title="Year"),
                         alt.Tooltip(f"{col}:Q", title=metric, format=",.2f" if col == "avg_rating" else ",")]).properties(height=360),
            width="stretch")
    gtot = genre_year.groupby("genre").apply(
        lambda d: pd.Series({"ratings": d.ratings_count.sum(), "avg_rating": (d.avg_rating * d.ratings_count).sum() / d.ratings_count.sum()}),
        include_groups=False).reset_index().sort_values("ratings", ascending=False)
    lead = gtot.iloc[0]
    share = lead.ratings / gtot.ratings.sum() * 100
    solid = gtot[gtot.ratings >= gtot.ratings.sum() * 0.01]
    best = solid.loc[solid.avg_rating.idxmax()]
    takeaway(f"{lead.genre} is the most-rated genre ({int(lead.ratings):,} ratings; many movies carry several genres, so shares overlap). "
             f"Among genres with a lot of ratings, {best.genre} scores highest on average ({best.avg_rating:.2f}).")
    st.subheader("All genres, all years")
    st.caption("Longer bar = more ratings. Hover to see the average rating of that genre.")
    st.altair_chart(
        alt.Chart(gtot).mark_bar(color=ORANGE).encode(
            y=alt.Y("genre:N", sort="-x", title=None), x=alt.X("ratings:Q", title="Number of ratings"),
            tooltip=[alt.Tooltip("genre:N", title="Genre"), alt.Tooltip("ratings:Q", title="Ratings", format=","),
                     alt.Tooltip("avg_rating:Q", title="Average rating", format=".2f")]).properties(height=420),
        width="stretch")

# ----------------------------------------------------------------- top movies
with tab_top:
    explain("**What you are seeing:** the best-rated movies in one genre. To keep it fair, only movies with at least "
            "1,000 ratings are ranked, so a film liked by just three people cannot win.")
    g = st.selectbox("Choose a genre", sorted(top.genre.unique()))
    t = top[top.genre == g].sort_values("rank_in_genre")
    if not t.empty:
        first = t.iloc[0]
        takeaway(f"The top {g} movie is {first.title_clean}"
                 + (f" ({int(first.release_year)})" if pd.notna(first.release_year) else "")
                 + f", with an average of {first.avg_rating:.2f} from {int(first.ratings_count):,} ratings.")
    st.dataframe(
        t.rename(columns={"rank_in_genre": "Rank", "title_clean": "Title", "release_year": "Year", "ratings_count": "Ratings", "avg_rating": "Average rating"})
        [["Rank", "Title", "Year", "Ratings", "Average rating"]],
        hide_index=True, width="stretch",
        column_config={"Average rating": RATING_COL, "Ratings": st.column_config.NumberColumn("Ratings", help=COUNT_HELP, format="%d")})
    posters_by_id(t, lambda r: f"#{r.rank_in_genre} {r.title_clean}", n=5)
    st.caption("Bar length = average rating (0 to 5). Ties are broken by the number of ratings.")
    st.altair_chart(
        alt.Chart(t).mark_bar(color=TEAL).encode(
            y=alt.Y("title_clean:N", sort=alt.EncodingSortField("rank_in_genre"), title=None),
            x=alt.X("avg_rating:Q", title="Average rating", scale=alt.Scale(domain=[0, 5])),
            tooltip=[alt.Tooltip("title_clean:N", title="Title"), alt.Tooltip("release_year:Q", title="Year", format="d"),
                     alt.Tooltip("ratings_count:Q", title="Ratings", format=","), alt.Tooltip("avg_rating:Q", title="Average", format=".2f")]
        ).properties(height=320), width="stretch")

# ---------------------------------------------------------------- movie finder
with tab_find:
    explain("**What you are seeing:** a search box for the dataset. Type any part of a movie title (for example "
            "\"star\" or \"toy\") and see how many people rated it and how well. Raise the minimum to hide obscure titles.")
    q = st.text_input("Part of a title", "movie" if data.DEMO else "star")
    mmin = st.slider("Only show movies with at least this many ratings", 1, 5000, 1000,
                     help="A higher number means better-known movies and more reliable averages.")
    if q.strip():
        try:
            res = data.find_movies(q.strip(), mmin)
            if res.empty:
                st.info("No movie matched. Try a shorter word or lower the minimum number of ratings.")
            else:
                st.caption(f"Found {len(res)} movie(s).")
                st.dataframe(res.rename(columns={"title_clean": "Title", "release_year": "Year", "ratings_count": "Ratings", "avg_rating": "Average rating"}),
                             hide_index=True, width="stretch",
                             column_config={"Average rating": RATING_COL, "Ratings": st.column_config.NumberColumn("Ratings", help=COUNT_HELP, format="%d")})
                posters_by_id(res, lambda r: f"{r.title_clean} ({int(r.release_year)})" if pd.notna(r.release_year) else r.title_clean, n=8, per_row=4)
        except Exception as e:
            friendly_error("The search did not work this time. Please try again in a moment.", e)
    else:
        st.caption("Type something above to start searching.")

# ------------------------------------------------------------------ ask genie
GENIE_EXAMPLES = ["Which month had the most ratings?", "How many ratings are there in total?",
                  "Which genre has the highest average rating?"]
with tab_ask:
    explain("**What you are seeing:** a chat with an AI assistant called Genie. Type a question in everyday English. "
            "Genie writes a database query for you, runs it on our tables and shows the answer. "
            "AI can make mistakes, so open **Show SQL** (the exact query it ran) if a number looks odd.")
    if not data.genie_configured():
        st.info("This tab is switched off because the app owner has not connected it to the AI assistant yet.")
    else:
        if "chat" not in st.session_state:
            st.session_state.chat = []
            st.session_state.conv = None
        st.markdown("**Try one of these:**")
        ex_cols = st.columns(len(GENIE_EXAMPLES))
        clicked = None
        for col_, ex in zip(ex_cols, GENIE_EXAMPLES):
            if col_.button(ex, key="ex_" + ex, width="stretch"):
                clicked = ex
        if st.button("Start a new conversation"):
            st.session_state.chat, st.session_state.conv = [], None
        for msg in st.session_state.chat:
            with st.chat_message(msg["role"]):
                st.markdown(msg["text"])
                if msg.get("sql"):
                    with st.expander("Show SQL"):
                        st.code(msg["sql"], language="sql")
                if msg.get("table") is not None:
                    st.dataframe(msg["table"], hide_index=True, width="stretch")
        question = st.chat_input("Ask about the data, for example: Which month had the most ratings?") or clicked
        if question:
            st.session_state.chat.append({"role": "user", "text": question})
            with st.chat_message("user"):
                st.markdown(question)
            with st.chat_message("assistant"):
                with st.spinner("Genie is thinking (this can take up to a minute)..."):
                    try:
                        r = data.genie_ask(question, st.session_state.conv)
                        st.session_state.conv = r["conversation_id"]
                        text = r["text"] or ("Genie could not answer this: " + r["error"] if r["error"] else "Genie did not return a text answer.")
                        st.markdown(text)
                        if r["sql"]:
                            with st.expander("Show SQL"):
                                st.code(r["sql"], language="sql")
                        if r["table"] is not None:
                            st.dataframe(r["table"], hide_index=True, width="stretch")
                        st.session_state.chat.append({"role": "assistant", "text": text, "sql": r["sql"], "table": r["table"]})
                    except Exception as e:
                        friendly_error("Could not reach the AI assistant. Please try again in a moment.", e)

# ------------------------------------------------------------ compare movies
@st.cache_data(ttl=600, show_spinner="Searching...")
def search_movies(text: str, min_ratings: int) -> pd.DataFrame:
    return data.find_movies(text, min_ratings, limit=20).reset_index(drop=True)


with tab_compare:
    explain("**What you are seeing:** two movies side by side. Type part of a title on each side, choose the right "
            "movie from the list, and see which one people rate higher and which one more people have rated.")
    min_r = st.slider("Only search movies with at least this many ratings", 1, 5000, 100, key="cmp_min")
    picks = []
    for col, tag in zip(st.columns(2), ("A", "B")):
        with col:
            text = st.text_input(f"Movie {tag}: part of the title", key=f"cmp_text_{tag}")
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
            "Side": ["A", "B"],
            "Movie": [f"{t}: {lbl}" for t, lbl, _ in picks],
            "Ratings": [int(r.ratings_count) for _, _, r in picks],
            "Average rating": [round(float(r.avg_rating), 2) for _, _, r in picks],
        })
        st.dataframe(rows[["Movie", "Ratings", "Average rating"]], hide_index=True, width="stretch",
                     column_config={"Average rating": RATING_COL, "Ratings": st.column_config.NumberColumn("Ratings", help=COUNT_HELP, format="%d")})
        if SHOW_POSTERS and all("movieId" in r.index for _, _, r in picks):
            ids = tmdb_by_id(tuple(int(r.movieId) for _, _, r in picks))
            posters.show([(lbl, ids.get(int(r.movieId))) for _, lbl, r in picks], per_row=2, width=170)
        diff = rows["Average rating"][0] - rows["Average rating"][1]
        more = rows["Movie"][0] if rows["Ratings"][0] > rows["Ratings"][1] else rows["Movie"][1]
        if diff == 0:
            takeaway(f"Both movies have the same average rating. {more} has been rated by more people.")
        else:
            better = rows["Movie"][0] if diff > 0 else rows["Movie"][1]
            takeaway(f"{better} is rated higher, by {abs(diff):.2f} points. {more} has more ratings, "
                     "so its average is the more reliable of the two.")
        st.caption("Tip: always read the number of ratings next to the average. A small group of raters can be a very different crowd.")
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
    explain("**What you are seeing:** movie suggestions made by a machine-learning model. It learned from people's ratings: "
            "if many people who liked movie X also liked movie Y, it suggests Y to others who liked X. "
            "It was trained on a 10% sample of users, and 'similar movies' covers the 5,000 most-rated titles.")
    left, right = st.columns(2)
    with left:
        st.subheader("If you liked this movie...")
        text = st.text_input("Part of a title", key="reco_text", help="For example: matrix, toy story, godfather")
        if text.strip():
            found = reco_search(text.strip())
            if found.empty:
                st.info("No match among the 5,000 most-rated movies. Try another title.")
            else:
                labels = [f"{r.title} ({int(r.year)})" if pd.notna(r.year) else r.title for r in found.itertuples()]
                i = st.selectbox("Pick a movie", range(len(found)), format_func=labels.__getitem__, key="reco_pick")
                sim = reco_similar(int(found.iloc[i].movieId))
                st.caption("Similarity: higher means the model sees the two movies as more alike.")
                st.dataframe(sim.rename(columns={"rank": "Rank", "similar_title": "Similar movie", "similar_year": "Year", "similarity": "Similarity"}),
                             hide_index=True, width="stretch")
                if SHOW_POSTERS:
                    pairs = [(found.iloc[i].title, found.iloc[i].year)] + [(s.similar_title, s.similar_year) for s in sim.head(4).itertuples()]
                    pairs = [(str(t), int(y)) for t, y in pairs if pd.notna(y)]
                    ids = tmdb_by_title(tuple(pairs))
                    posters.show([(t, ids.get((t.lower(), y))) for t, y in pairs], per_row=5)
        else:
            st.caption("Type a title to see similar movies.")
    with right:
        st.subheader("Picks for a sample viewer")
        st.caption("Viewers in the dataset are anonymous numbers. Choose one to see what the model would suggest, "
                   "based on the movies that person rated.")
        uid = st.number_input("Viewer number (multiples of 10, starting at 10)", min_value=1, value=10, step=10, key="reco_user")
        recs = reco_user(int(uid))
        if recs.empty:
            st.info("No suggestions for that number. Try 10, 20 or 30.")
        else:
            st.caption("Predicted rating = the model's guess of the score this viewer would give (0.5 to 5).")
            st.dataframe(recs.rename(columns={"rank": "Rank", "title_clean": "Title", "release_year": "Year", "predicted_rating": "Predicted rating"}),
                         hide_index=True, width="stretch")
            if SHOW_POSTERS:
                top5 = [(str(r.title_clean), int(r.release_year)) for r in recs.head(5).itertuples() if pd.notna(r.release_year)]
                ids = tmdb_by_title(tuple(top5))
                posters.show([(t, ids.get((t.lower(), y))) for t, y in top5], per_row=5)

# ----------------------------------------------------------------- data health
with tab_health:
    explain("**What you are seeing:** a report card for the data. Every time the pipeline runs, it counts the rows it "
            "received, sets aside rows that look wrong (a 'rejected' row, for example a rating outside 0.5 to 5) and "
            "refuses to publish if too many are bad. Green means the data passed all its checks.")
    try:
        tr = load("dq_trend")
        if tr.empty:
            st.info("No pipeline runs have been recorded yet.")
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

            last = runs.iloc[-1]
            ok = last["Status"] == "OK"
            if ok:
                st.success(f"All checks passed on the latest run ({last['Started']}). The data on this page can be trusted.")
            else:
                st.warning(f"The latest run ({last['Started']}) needs attention: some checks failed or too many rows were rejected. "
                           "Treat the numbers on this page with care until it is fixed.")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Latest run", "Healthy" if ok else "Needs a look")
            m2.metric("Ratings processed", f"{int(last['ratings']):,}", help="Rows that made it through the last run.")
            m3.metric("Rows rejected", f"{last['worst']:.2f}%", help="Share of rows set aside as bad. The pipeline stops above 1%.")
            m4.metric("Runs recorded", f"{len(runs)}")

            st.subheader("Quality over time")
            st.caption("Left: the share of rejected rows per run. The dashed orange line is the 1% limit, and bars must stay below it. "
                       "Right: how many ratings each run processed.")
            c1, c2 = st.columns(2)
            ymax = max(1.5, float(runs["worst"].max()) * 1.2)
            bars = alt.Chart(runs).mark_bar(color=TEAL, cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
                x=alt.X("Started:N", title=None, sort=None, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("worst:Q", title="Rejected rows (%)", scale=alt.Scale(domain=[0, ymax])),
                tooltip=["Started", alt.Tooltip("worst:Q", title="Rejected %", format=".2f")]).properties(height=260)
            limit = alt.Chart(pd.DataFrame({"y": [1.0]})).mark_rule(color=ORANGE, strokeDash=[4, 4]).encode(y="y:Q")
            c1.altair_chart(bars + limit, width="stretch")
            c2.altair_chart(
                alt.Chart(runs).mark_bar(color=TEAL, cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
                    x=alt.X("Started:N", title=None, sort=None, axis=alt.Axis(labelAngle=0)),
                    y=alt.Y("ratings:Q", title="Ratings processed"),
                    tooltip=["Started", alt.Tooltip("ratings:Q", title="Ratings", format=",")]).properties(height=260),
                width="stretch")
            with st.expander("Table of all runs"):
                show = runs.rename(columns={"ratings": "Ratings processed", "worst": "Worst rejected %", "failed": "Failed checks"})
                st.dataframe(show[["Started", "Duration (min)", "Ratings processed", "Worst rejected %", "Failed checks", "Status"]],
                             hide_index=True, width="stretch")
    except Exception as e:
        friendly_error("The data health report is not available right now.", e)

    with st.expander("Technical details: raw step reports (for engineers)"):
        try:
            dq = load("quality_reports")
            rows_ = []
            for _, r in dq.iterrows():
                try:
                    rep = json.loads(r.report_json)
                except Exception:
                    rep = {}
                rows_.append({"Time": r.run_ts, "Step": r.step, "Batch": r.ingest_date,
                              "Rows in": rep.get("rows_in", rep.get("movies_in", rep.get("silver_ratings"))),
                              "Rejected %": rep.get("rejected_pct"), "Passed": rep.get("passed")})
            st.dataframe(pd.DataFrame(rows_), hide_index=True, width="stretch")
            if len(dq):
                pick = st.selectbox("Show the full JSON report of a step", dq.step.unique())
                st.json(json.loads(dq[dq.step == pick].iloc[0].report_json))
        except Exception as e:
            friendly_error("Could not read the step reports.", e)

# ------------------------------------------------------------------ how it works
GLOSSARY = {
    "Pipeline": "An automatic assembly line for data. It collects raw files, cleans them, checks them and saves tidy results.",
    "Bronze table": "The first stop: the raw ratings exactly as they arrived, kept untouched so we can always start over.",
    "Silver table": "The cleaned version: wrong or missing values fixed or set aside, years and genres split into proper columns.",
    "Gold table": "The final, ready-to-use tables (totals, averages, top lists). This app reads only these.",
    "Delta table": "A table stored in the cloud that keeps a history of every change, so mistakes can be undone.",
    "Rejected row": "A row that failed a check (for example a rating of 7). It is set aside with a reason instead of polluting the results.",
    "Quality gate": "A rule that stops the pipeline when too much data is bad (more than 1% rejected).",
    "Reconciliation": "Making sure the totals match at every step: 32,000,204 ratings in, 32,000,204 ratings out.",
    "Genre": "A category of movie, such as Drama or Comedy. A movie can have several.",
    "Average rating": "The mean of all ratings for a movie, from 0.5 to 5.",
    "Recommendation model (ALS)": "A machine-learning method that learns people's tastes from ratings and predicts what they might like.",
    "Similarity": "How alike the model thinks two movies are, based on who liked them. Higher is more alike.",
    "RMSE": "A score for prediction error. Lower is better. Our model scores 0.816 against 1.043 for a lazy 'always guess the average' baseline.",
    "SQL": "The language used to ask questions of a database. Genie writes it for you.",
    "SQL warehouse": "The computer in the cloud that runs the queries. It switches itself off after 10 idle minutes to save money.",
    "Genie": "An AI assistant that turns a plain-English question into SQL and runs it on the Gold tables.",
    "Unity Catalog": "The cloud 'library catalog' that lists our tables, who may read them and where they came from.",
    "Dashboard": "A page of charts and numbers that updates from the data.",
    "Alert": "An automatic email sent when a check fails.",
    "MERGE (upsert)": "Update rows that already exist and add the ones that are new, in one safe step.",
}
with tab_how:
    explain("**What you are seeing:** the journey of the data, from raw files to the page you are using, plus a dictionary "
            "of the technical words used in this app.")
    st.subheader("From raw files to this page")
    st.graphviz_chart("""
    digraph G {
      rankdir=LR; bgcolor="transparent";
      node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11, color="#1B2A41", fillcolor="#E4F2F2"];
      edge [color="#1B2A41"];
      raw [label="Raw files\\n(MovieLens CSVs)", fillcolor="#F3F4F6"];
      bronze [label="Bronze\\nraw copy"];
      silver [label="Silver\\ncleaned and typed"];
      gate [label="Quality gate\\nstop if over 1% bad", fillcolor="#FDEBDD"];
      gold [label="Gold\\ntotals, averages,\\ntop lists", fillcolor="#FFF3C4"];
      app [label="This app,\\ndashboard, alert,\\nGenie", fillcolor="#E3F1E6"];
      raw -> bronze -> silver -> gate -> gold -> app;
    }""")
    st.markdown(
        "1. **Raw files** are downloaded as they are and never changed.\n"
        "2. **Bronze** stores them as a table. **Silver** cleans them and sets aside bad rows.\n"
        "3. The **quality gate** counts rejected rows. If more than 1% are bad, the run stops and an email alert is sent.\n"
        "4. **Gold** holds the final numbers. This page, the dashboard and the AI assistant read only Gold.\n"
        "5. At every step the row counts are compared (reconciliation), so no rating gets lost on the way.")
    st.subheader("Glossary")
    term = st.text_input("Search the glossary", placeholder="for example: silver, SQL, quality")
    shown = {k: v for k, v in GLOSSARY.items() if not term.strip() or term.strip().lower() in (k + " " + v).lower()}
    if not shown:
        st.info("No word matched. Try another search.")
    for k, v in shown.items():
        st.markdown(f"**{k}.** {v}")
    st.caption("Data: MovieLens 32M, GroupLens Research, University of Minnesota. Used for learning and research.")

if SHOW_POSTERS:
    st.divider()
    st.caption(posters.CREDIT)
