# Sprint 6 - the dashboard
#
# five tabs:
#   city overview    -> the big picture for a fleet manager
#   zone explorer    -> pick any zone, see its week and its forecast
#   zone clusters    -> which zones behave alike
#   sql answers      -> the warehouse questions, with the actual sql
#   forecast quality -> how much to trust the numbers
#
#   streamlit run app.py

import json
import re
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent
APP = ROOT / "app_data"
FIG = ROOT / "reports" / "figures"
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

st.set_page_config(page_title="NYC Taxi Demand", layout="wide")

if not (APP / "forecasts_test.parquet").exists():
    st.error("No app data yet. Run sprints 1-5, then `python src/sprint6_app_data.py`.")
    st.stop()


@st.cache_data
def load():
    zones = pd.read_csv(APP / "zones.csv")
    totals = pd.read_csv(APP / "zone_totals.csv").merge(zones, left_on="zone_id", right_on="LocationID")
    data = {
        "zones": zones,
        "totals": totals.sort_values("trips", ascending=False),
        "profile": pd.read_parquet(APP / "zone_weekly_profile.parquet"),
        "daily": pd.read_csv(APP / "daily_rides.csv", parse_dates=["date"]),
        "clusters": pd.read_csv(APP / "zone_clusters.csv"),
        "forecasts": pd.read_parquet(APP / "forecasts_test.parquet"),
        "metrics": json.loads((APP / "forecast_metrics.json").read_text()),
        "cleaning": json.loads((APP / "spark_cleaning.json").read_text()),
        "err_cluster": pd.read_csv(APP / "forecast_error_by_cluster.csv"),
        "sql": {p.stem: pd.read_csv(p) for p in (APP / "sql").glob("*.csv")},
    }
    data["forecasts"]["hour_ts"] = pd.to_datetime(data["forecasts"]["hour_ts"])
    return data


def sql_blocks():
    # pull the question text and query for each answer straight from the sql file,
    # so the dashboard always shows the exact query that produced the numbers
    text = (ROOT / "sql" / "questions.sql").read_text()
    out = {}
    for block in re.split(r"\n(?=-- name: )", text):
        name = re.search(r"-- name: (\w+)", block)
        if name:
            q = re.search(r"-- question: (.+)", block).group(1)
            body = "\n".join(l for l in block.splitlines() if not l.startswith("--")).strip()
            out[name.group(1)] = (q, body)
    return out


def heatmap(df, value, title):
    return (alt.Chart(df).mark_rect()
            .encode(x=alt.X("hour_of_day:O", title="Hour of day"),
                    y=alt.Y("day:O", sort=DAYS, title=None),
                    color=alt.Color(f"{value}:Q", scale=alt.Scale(scheme="orangered"), title=title),
                    tooltip=["day", "hour_of_day", alt.Tooltip(f"{value}:Q", format=",.1f")])
            .properties(height=230))


d = load()
m = d["metrics"]
windows = m["windows"]
# label shown in the app -> key used in the files, normal weeks first
window_keys = {w["label"]: k for k, w in windows.items()}

st.title("NYC Taxi Demand")
st.caption("Built on NYC Taxi & Limousine Commission yellow cab trip records. "
           f"Forecasts cover the {m['zones']} busiest pickup zones.")

overview, explorer, clusters_tab, sql_tab, quality = st.tabs(
    ["City overview", "Zone explorer", "Zone clusters", "SQL answers", "Forecast quality"])


with overview:
    sql = d["sql"]
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Clean rides analyzed", f"{d['cleaning']['clean_trips']:,}")
    busiest = sql["busiest_zones"].iloc[0]
    k2.metric("Busiest pickup zone", busiest["zone_name"], f"{busiest['pct_of_city']}% of all rides", delta_color="off")
    if not sql["rain_effect"].empty:
        k3.metric("Extra rides when it rains", f"{sql['rain_effect']['pct_lift'].mean():+.1f}%")
    hol = sql["holiday_effect"].set_index("day_type")["avg_daily_trips"]
    if len(hol) == 2:
        k4.metric("Holiday vs regular weekday", f"{hol['Federal holiday'] / hol['Regular weekday'] - 1:+.0%}")

    st.markdown("**Rides per day**")
    st.line_chart(d["daily"].set_index("date")["trips"], height=220)

    left, right = st.columns(2)
    with left:
        st.markdown("**Average citywide rides per hour of the week**")
        how = sql["hour_of_week"].assign(day=lambda x: x["day_name"].str[:3])
        st.altair_chart(heatmap(how, "avg_trips", "Rides"), width="stretch")
    with right:
        st.markdown("**Rides by borough**")
        st.dataframe(sql["borough_share"], hide_index=True, width="stretch")


with explorer:
    options = d["totals"]["Zone"] + " (" + d["totals"]["Borough"] + ")"
    pick = st.selectbox("Zone", options.tolist())
    zone_id = int(d["totals"].iloc[options.tolist().index(pick)]["zone_id"])
    row = d["totals"][d["totals"]["zone_id"] == zone_id].iloc[0]
    cl = d["clusters"][d["clusters"]["zone_id"] == zone_id]

    c1, c2, c3 = st.columns(3)
    c1.metric("Rides this year", f"{int(row['trips']):,}")
    c2.metric("Revenue", f"${row['revenue']:,.0f}")
    c3.metric("Cluster", cl["cluster_name"].iloc[0] if len(cl) else "Too few rides to cluster")

    prof = d["profile"][d["profile"]["zone_id"] == zone_id].assign(day=lambda x: x["day_of_week"].map(dict(enumerate(DAYS))))
    st.markdown("**This zone's typical week** (average rides per hour)")
    st.altair_chart(heatmap(prof, "avg_trips", "Rides"), width="stretch")

    fc = d["forecasts"][d["forecasts"]["zone_id"] == zone_id]
    if fc.empty:
        st.info("Forecasts only cover the busiest zones. Pick one higher in the list to see them.")
    else:
        wlabel = st.radio("Test window", list(window_keys), horizontal=True, key="explorer_window")
        w = windows[window_keys[wlabel]]
        fc = fc[fc["window"] == window_keys[wlabel]]
        st.markdown(f"**Forecast vs actual, {w['start']} to {w['end']}** ({w['best_model']})")
        days = sorted(fc["hour_ts"].dt.date.unique())
        start, end = st.select_slider("Dates", options=days, value=(days[7], days[13]))
        view = fc[(fc["hour_ts"].dt.date >= start) & (fc["hour_ts"].dt.date <= end)]
        long = view.melt(id_vars="hour_ts", value_vars=["trips", "pred_best", "pred_naive"],
                         var_name="series", value_name="rides")
        long["series"] = long["series"].map({"trips": "Actual", "pred_best": "Forecast",
                                             "pred_naive": "Same hour last week"})
        chart = (alt.Chart(long).mark_line()
                 .encode(x=alt.X("hour_ts:T", title=None), y=alt.Y("rides:Q", title="Rides per hour"),
                         color=alt.Color("series:N", scale=alt.Scale(
                             domain=["Actual", "Forecast", "Same hour last week"],
                             range=["#333333", "#d1495b", "#9aa5b1"]), title=None),
                         strokeDash=alt.condition(alt.datum.series == "Same hour last week",
                                                  alt.value([4, 3]), alt.value([1, 0])))
                 .properties(height=280))
        st.altair_chart(chart, width="stretch")
        err = (view["trips"] - view["pred_best"]).abs().sum() / max(view["trips"].sum(), 1)
        st.caption(f"Forecast error for this zone over these dates: {err:.1%} (WAPE)")


with clusters_tab:
    st.markdown("Zones grouped by the **shape** of their week, not their size. "
                "A quiet zone and a busy one can land together if people ride at the same times.")
    img = FIG / "04_zone_clusters.png"
    if img.exists():
        st.image(str(img), width="stretch")
    pick_c = st.selectbox("Cluster", sorted(d["clusters"]["cluster_name"].unique()))
    st.dataframe(d["clusters"][d["clusters"]["cluster_name"] == pick_c]
                 .sort_values("trips", ascending=False)[["zone_name", "borough", "trips"]],
                 hide_index=True, width="stretch")


with sql_tab:
    blocks = sql_blocks()
    names = [n for n in blocks if n in d["sql"]]
    pick_q = st.selectbox("Question", names, format_func=lambda n: blocks[n][0])
    st.dataframe(d["sql"][pick_q], hide_index=True, width="stretch")
    with st.expander("Show the SQL"):
        st.code(blocks[pick_q][1], language="sql")


with quality:
    st.subheader("How good are the forecasts?")
    st.write("Every model predicted each hour **one week ahead**, on two 4-week windows it never saw "
             "during training. Normal weeks are the everyday test. The holiday season is a stress test: "
             "Christmas demand drops off and the lags point back at Thanksgiving week.")

    summary = pd.DataFrame([{"Window": w["label"], "Dates": f"{w['start']} to {w['end']}",
                             "Best model": w["best_model"],
                             "Best WAPE": w["models"][w["best_model"]]["wape"],
                             "Same hour last week": w["models"]["Same hour last week"]["wape"],
                             "Less error than last week": w["improvement_vs_last_week"]}
                            for w in windows.values()])
    pct = st.column_config.NumberColumn(format="percent")
    st.dataframe(summary, hide_index=True, width="stretch",
                 column_config={"Best WAPE": pct, "Same hour last week": pct, "Less error than last week": pct})

    wlabel = st.radio("Show models for", list(window_keys), horizontal=True, key="quality_window")
    w = windows[window_keys[wlabel]]
    rows = [{"Model": k, "WAPE": v["wape"], "MAE (rides/hour)": v["mae"]} for k, v in w["models"].items()]
    st.dataframe(pd.DataFrame(rows).sort_values("WAPE"), hide_index=True, width="stretch",
                 column_config={"WAPE": pct})
    st.markdown(f"**{w['best_model']}** cut the error by **{w['improvement_vs_last_week']:.0%}** compared to "
                "simply repeating the same hour from last week.")

    err = d["err_cluster"][d["err_cluster"]["window"] == window_keys[wlabel]].sort_values("wape")
    st.markdown("**Error by zone type**")
    st.dataframe(err.drop(columns="window").rename(columns={"cluster_name": "Zone type", "wape": "WAPE",
                                                            "trips": "Rides in window"}),
                 hide_index=True, width="stretch", column_config={"WAPE": pct})
    if m["weather_used"]:
        st.caption("Weather features use the weather that actually happened, as a stand-in for a weather "
                   "forecast. A real week-ahead weather forecast is less accurate, so treat this as a best case.")

    cols = st.columns(2)
    for i, name in enumerate(["06_model_comparison.png", "08_error_by_cluster.png", "07_forecast_week.png"]):
        if (FIG / name).exists():
            cols[i % 2].image(str(FIG / name), width="stretch")
