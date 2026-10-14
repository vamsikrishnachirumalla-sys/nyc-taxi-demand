# Sprint 1 - get the data and see how messy it is
#
# downloads a year of yellow cab trips, the zone lookup, and hourly weather,
# then counts every kind of bad row before anything gets cleaned.
# duckdb reads the parquet files in place, so no loading 40M rows into pandas
#
#   python src/sprint1_data.py

import json
import urllib.request

import duckdb
import pandas as pd

from config import (MONTHS, REPORTS_DIR, TLC_URL, TRIPS_DIR, WEATHER_FILE, WEATHER_URL,
                    YEAR, ZONES_FILE, ZONES_URL)


def download():
    for m in MONTHS:
        path = TRIPS_DIR / f"yellow_tripdata_{YEAR}-{m:02d}.parquet"
        if path.exists():
            continue
        print(f"downloading {path.name}...")
        urllib.request.urlretrieve(TLC_URL.format(year=YEAR, month=m), path)

    if not ZONES_FILE.exists():
        urllib.request.urlretrieve(ZONES_URL, ZONES_FILE)

    if not WEATHER_FILE.exists():
        print("downloading hourly weather...")
        url = WEATHER_URL.format(start=f"{YEAR}-01-01", end=f"{YEAR}-12-31")
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                hourly = json.load(r)["hourly"]
            pd.DataFrame(hourly).to_csv(WEATHER_FILE, index=False)
        except Exception as e:
            # weather is nice to have, not a blocker. the forecast sprint
            # just skips the weather features if this file isn't there
            print(f"  couldn't get weather ({e}), carrying on without it")


# hand-written so the dictionary actually explains things
NOTES = {
    "VendorID": "Which tech provider recorded the trip (1 = Creative Mobile, 2 = Curb/VeriFone)",
    "tpep_pickup_datetime": "Meter start, local NYC time",
    "tpep_dropoff_datetime": "Meter stop, local NYC time",
    "passenger_count": "Entered by the driver, often missing",
    "trip_distance": "Miles on the meter",
    "RatecodeID": "1 standard, 2 JFK flat fare, 3 Newark, 4 Nassau/Westchester, 5 negotiated, 6 group",
    "store_and_fwd_flag": "Y if the trip was stored on the car and sent later (no signal)",
    "PULocationID": "Pickup taxi zone (1-265), see the zone lookup",
    "DOLocationID": "Dropoff taxi zone (1-265)",
    "payment_type": "1 card, 2 cash, 3 no charge, 4 dispute, 5 unknown, 6 voided",
    "fare_amount": "Time and distance fare",
    "extra": "Rush hour and overnight surcharges",
    "mta_tax": "MTA tax",
    "tip_amount": "Tips, only recorded for card payments",
    "tolls_amount": "Tolls paid",
    "improvement_surcharge": "Improvement surcharge",
    "total_amount": "Total charged, not including cash tips",
    "congestion_surcharge": "NY state congestion surcharge",
    "airport_fee": "Fee for pickups at LaGuardia and JFK",
    "cbd_congestion_fee": "Manhattan congestion pricing fee, started January 2025",
}


def data_dictionary(con, files):
    cols = con.execute(f"describe select * from read_parquet({files}, union_by_name=true)").df()
    cols["definition"] = cols["column_name"].map(lambda c: NOTES.get(c, NOTES.get(c.lower(), "")))
    return cols[["column_name", "column_type", "definition"]]


def quality_checks(con, files, zones):
    # count every problem in one pass over the files
    q = f"""
    select
        count(*)                                                              as total_trips,
        count(*) filter (where year(tpep_pickup_datetime) <> {YEAR})          as wrong_year,
        count(*) filter (where tpep_dropoff_datetime <= tpep_pickup_datetime) as dropoff_before_pickup,
        count(*) filter (where date_diff('minute', tpep_pickup_datetime, tpep_dropoff_datetime) > 180)
                                                                              as over_3_hours,
        count(*) filter (where trip_distance <= 0)                            as zero_distance,
        count(*) filter (where trip_distance > 100)                           as over_100_miles,
        count(*) filter (where fare_amount < 0)                               as negative_fare,
        count(*) filter (where PULocationID in (264, 265))                    as unknown_zone,
        count(*) filter (where passenger_count is null)                       as missing_passengers
    from read_parquet({files}, union_by_name=true)
    """
    checks = con.execute(q).df().iloc[0].to_dict()

    by_month = con.execute(f"""
        select strftime(tpep_pickup_datetime, '%Y-%m') as month, count(*) as trips
        from read_parquet({files}, union_by_name=true)
        where year(tpep_pickup_datetime) = {YEAR}
        group by 1 order by 1
    """).df()
    return checks, by_month


def write_report(checks, by_month, dictionary):
    total = checks["total_trips"]
    labels = {
        "wrong_year": "Pickup date outside the year (clock errors, some are from 2002 or 2009)",
        "dropoff_before_pickup": "Dropoff at or before pickup",
        "over_3_hours": "Trips longer than 3 hours",
        "zero_distance": "Zero or negative distance",
        "over_100_miles": "Over 100 miles",
        "negative_fare": "Negative fare (refunds and corrections)",
        "unknown_zone": "Pickup zone unknown (264/265)",
        "missing_passengers": "Passenger count missing",
    }
    out = [
        "# Data Quality Report (Sprint 1)",
        "",
        f"**{total:,} yellow cab trips** in the {YEAR} files.",
        "",
        "## Problems found before cleaning",
        "",
        "| Check | Rows | Share |",
        "|---|---|---|",
    ]
    for key, label in labels.items():
        out.append(f"| {label} | {checks[key]:,} | {checks[key] / total:.2%} |")

    out += ["", "## Trips per month", "", "| Month | Trips |", "|---|---|"]
    for _, r in by_month.iterrows():
        out.append(f"| {r['month']} | {r['trips']:,} |")

    out += ["", "## What happens to them in Sprint 2", "",
            "Spark drops wrong-year pickups, dropoffs before pickups, trips over 3 hours, "
            "zero or 100+ mile trips, negative fares, and unknown zones. Missing passenger "
            "counts are kept, since demand is about trips, not riders.",
            "", "## Columns", "", "| Column | Type | Meaning |", "|---|---|---|"]
    for _, r in dictionary.iterrows():
        out.append(f"| {r['column_name']} | {r['column_type']} | {r['definition']} |")
    (REPORTS_DIR / "data_quality_report.md").write_text("\n".join(out))


if __name__ == "__main__":
    download()
    files = sorted(str(p) for p in TRIPS_DIR.glob("yellow_tripdata_*.parquet"))
    con = duckdb.connect()

    dictionary = data_dictionary(con, files)
    dictionary.to_csv(REPORTS_DIR / "data_dictionary.csv", index=False)
    checks, by_month = quality_checks(con, files, pd.read_csv(ZONES_FILE))
    write_report(checks, by_month, dictionary)

    print(f"trips in the files: {checks['total_trips']:,}")
    for k, v in checks.items():
        if k != "total_trips":
            print(f"  {k:22s} {v:>10,}")
    print("saved data dictionary + quality report to reports/")
