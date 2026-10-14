# Sprint 6 (part 1) - pack the small files the dashboard needs
#
# the live app can't redownload 700MB of trips and rerun spark every time it
# wakes up, so this writes a few small summaries into app_data/ that ship with the repo
#
#   python src/sprint6_app_data.py

import shutil

import duckdb

from config import APP_DIR, CLUSTERS_FILE, PROCESSED_DIR, REPORTS_DIR, WAREHOUSE, ZONES_FILE

if __name__ == "__main__":
    con = duckdb.connect(str(WAREHOUSE), read_only=True)

    # each zone's average rides for every hour of the week, for the zone explorer
    con.execute(f"""
        copy (
            select f.zone_id, t.day_of_week, t.hour_of_day, avg(f.trips) as avg_trips
            from fact_zone_hour f join dim_time t using (hour_ts)
            group by all
        ) to '{APP_DIR / "zone_weekly_profile.parquet"}' (format parquet)
    """)
    # total rides per zone and citywide rides per day
    con.execute(f"""
        copy (select zone_id, sum(trips) as trips, sum(revenue) as revenue
              from fact_zone_hour group by 1)
        to '{APP_DIR / "zone_totals.csv"}' (header)
    """)
    con.execute(f"""
        copy (select t.date, sum(f.trips) as trips
              from fact_zone_hour f join dim_time t using (hour_ts) group by 1 order by 1)
        to '{APP_DIR / "daily_rides.csv"}' (header)
    """)
    con.close()

    shutil.copy(ZONES_FILE, APP_DIR / "zones.csv")
    shutil.copy(CLUSTERS_FILE, APP_DIR / "zone_clusters.csv")
    shutil.copy(PROCESSED_DIR / "forecasts_test.parquet", APP_DIR / "forecasts_test.parquet")
    for name in ["forecast_metrics.json", "spark_cleaning.json", "forecast_error_by_cluster.csv"]:
        shutil.copy(REPORTS_DIR / name, APP_DIR / name)
    shutil.copytree(REPORTS_DIR / "sql", APP_DIR / "sql", dirs_exist_ok=True)

    total = sum(f.stat().st_size for f in APP_DIR.rglob("*") if f.is_file()) / 1e6
    print(f"app_data ready, {total:.1f} MB")
