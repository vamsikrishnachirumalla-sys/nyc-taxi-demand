# Sprint 3 - build a star schema warehouse and answer business questions in SQL
#
# the spark output is one flat table. a warehouse splits it into a fact table
# (rides per zone per hour) and dimensions (zone, time, weather) so questions like
# "do people ride more in the rain" are a join instead of a pile of pandas code.
# duckdb because it's a real SQL engine that runs in a single file, no server
#
#   python src/sprint3_warehouse.py

import re

import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar

from config import FIGURES_DIR, HOURLY_DIR, REPORTS_DIR, SQL_DIR, WAREHOUSE, WEATHER_FILE, YEAR, ZONES_FILE

SQL_OUT = REPORTS_DIR / "sql"
SQL_OUT.mkdir(exist_ok=True)


def build(con):
    con.execute((SQL_DIR / "schema.sql").read_text())

    zones = pd.read_csv(ZONES_FILE)
    zones["is_airport"] = zones["service_zone"].isin(["Airports", "EWR"])
    con.execute("""insert into dim_zone
                   select LocationID, Borough, Zone, service_zone, is_airport from zones""")

    # every hour of the year, even ones with no rides at all
    hours = pd.DataFrame({"hour_ts": pd.date_range(f"{YEAR}-01-01", f"{YEAR}-12-31 23:00", freq="h")})
    holidays = USFederalHolidayCalendar().holidays(f"{YEAR}-01-01", f"{YEAR}-12-31")
    hours["date"] = hours["hour_ts"].dt.date
    hours["hour_of_day"] = hours["hour_ts"].dt.hour
    hours["day_of_week"] = hours["hour_ts"].dt.dayofweek
    hours["day_name"] = hours["hour_ts"].dt.day_name()
    hours["is_weekend"] = hours["day_of_week"] >= 5
    hours["month"] = hours["hour_ts"].dt.month
    hours["is_holiday"] = hours["hour_ts"].dt.normalize().isin(holidays)
    con.execute("insert into dim_time select * from hours")

    if WEATHER_FILE.exists():
        wx = pd.read_csv(WEATHER_FILE)
        wx["hour_ts"] = pd.to_datetime(wx["time"])
        # any measurable rain counts. 0.01 inch is the smallest amount stations report
        wx["is_raining"] = wx["precipitation"] >= 0.01
        con.execute("""insert into dim_weather
                       select hour_ts, temperature_2m, precipitation, snowfall, is_raining
                       from wx where year(hour_ts) = ?""", [YEAR])

    # only keep fact rows whose zone is in the lookup, so the foreign key holds
    con.execute(f"""
        insert into fact_zone_hour
        select h.zone_id, cast(h.hour as timestamp), h.trips, h.avg_fare, h.avg_miles, h.avg_minutes,
               h.card_trips, h.card_tips, h.card_fares, h.revenue
        from read_parquet('{HOURLY_DIR}/*.parquet') h
        where h.zone_id in (select zone_id from dim_zone)
    """)


def run_questions(con):
    text = (SQL_DIR / "questions.sql").read_text()
    blocks = re.split(r"\n(?=-- name: )", text)
    answers = {}
    for block in blocks:
        name = re.search(r"-- name: (\w+)", block)
        if not name:
            continue
        question = re.search(r"-- question: (.+)", block).group(1)
        query = "\n".join(l for l in block.splitlines() if not l.startswith("--")).strip()
        result = con.execute(query).df()
        result.to_csv(SQL_OUT / f"{name.group(1)}.csv", index=False)
        answers[name.group(1)] = (question, query, result)
    return answers


def chart_heatmap(df):
    grid = df.pivot(index="day_of_week", columns="hour_of_day", values="avg_trips")
    days = df.drop_duplicates("day_of_week").sort_values("day_of_week")["day_name"].str[:3]
    fig, ax = plt.subplots(figsize=(11, 3.8))
    im = ax.imshow(grid, aspect="auto", cmap="YlOrRd")
    ax.set_yticks(range(7), days)
    ax.set_xticks(range(0, 24, 2), [f"{h}:00" for h in range(0, 24, 2)], fontsize=8)
    fig.colorbar(im, ax=ax, label="Avg rides per hour (citywide)")
    fig.suptitle("When the city rides: average pickups by hour of week", x=0.01, ha="left",
                 fontsize=12, fontweight="bold")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "01_hour_of_week.png", dpi=150)
    plt.close(fig)


def chart_monthly(df):
    fig, ax = plt.subplots(figsize=(9, 3.8))
    ax.bar(df["month"], df["trips"], color="#1f6f8b")
    ax.set_xticks(range(1, 13), ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                                 "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
    # 3.2M reads better than 3200000 on an axis
    ax.yaxis.set_major_formatter(plt.FuncFormatter(
        lambda v, _: f"{v / 1e6:.1f}M" if v >= 1e6 else f"{v / 1e3:.0f}K" if v >= 1e3 else f"{v:.0f}"))
    ax.set_ylabel("Rides")
    ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle(f"Yellow cab rides per month, {YEAR}", x=0.01, ha="left", fontsize=12, fontweight="bold")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "02_monthly_rides.png", dpi=150)
    plt.close(fig)


def chart_rain(df):
    if df.empty:
        return
    fig, ax = plt.subplots(figsize=(9, 3.8))
    for weekend, color, label in [(False, "#1f6f8b", "Weekdays"), (True, "#edae49", "Weekends")]:
        part = df[df["is_weekend"] == weekend]
        ax.plot(part["hour_of_day"], part["pct_lift"], marker="o", color=color, label=label, linewidth=2)
    ax.axhline(0, color="#999", linewidth=0.8)
    ax.set_xticks(range(0, 24, 2), [f"{h}:00" for h in range(0, 24, 2)], fontsize=8)
    ax.set_ylabel("Change vs a dry hour (%)")
    ax.legend(frameon=False, loc="lower right", bbox_to_anchor=(1, 1), ncol=2)
    ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Extra rides when it rains, by hour of day", x=0.01, ha="left", fontsize=12, fontweight="bold")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "03_rain_effect.png", dpi=150)
    plt.close(fig)


def fmt(v):
    # duckdb hands back sums as floats, so 123232 shows up as 123232.0. tidy that up
    if isinstance(v, (int, np.integer)) or (isinstance(v, float) and v.is_integer()):
        return f"{int(v):,}"
    return str(v)


def write_report(answers):
    out = ["# SQL Answers (Sprint 3)", "",
           "Each answer comes from `sql/questions.sql`, run against the star schema in `sql/schema.sql`.", ""]
    for name, (question, query, result) in answers.items():
        out += [f"## {question}", "", f"`{name}`", ""]
        if result.empty:
            out += ["_No rows (weather data missing?)_", ""]
            continue
        show = result.head(12)
        out.append("| " + " | ".join(show.columns) + " |")
        out.append("|" + "---|" * len(show.columns))
        for _, r in show.iterrows():
            out.append("| " + " | ".join(fmt(v) for v in r.values) + " |")
        out.append("")
    (REPORTS_DIR / "sql_answers.md").write_text("\n".join(out))


if __name__ == "__main__":
    WAREHOUSE.unlink(missing_ok=True)
    con = duckdb.connect(str(WAREHOUSE))
    build(con)

    counts = {t: con.execute(f"select count(*) from {t}").fetchone()[0]
              for t in ["dim_zone", "dim_time", "dim_weather", "fact_zone_hour"]}
    answers = run_questions(con)
    con.close()

    chart_heatmap(answers["hour_of_week"][2])
    chart_monthly(answers["monthly_trend"][2])
    chart_rain(answers["rain_effect"][2])
    write_report(answers)

    for t, n in counts.items():
        print(f"{t:16s} {n:>10,} rows")
    print("\nbusiest zones:")
    print(answers["busiest_zones"][2].head(5).to_string(index=False))
    rain = answers["rain_effect"][2]
    if not rain.empty:
        print(f"\naverage rain lift: {rain['pct_lift'].mean():+.1f}%")
    print("\nsaved answers to reports/sql/ and reports/sql_answers.md")
