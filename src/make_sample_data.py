# fake taxi data in the same layout as the real TLC files, so every sprint can be
# tested in a couple of minutes without downloading ~700MB.
# numbers are made up, never quote findings from this
#
#   python src/make_sample_data.py

import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar

from config import MONTHS, RANDOM_STATE, TRIPS_DIR, WEATHER_FILE, YEAR, ZONES_FILE

# a slice of real zone ids/names, with a made-up "personality" that drives demand.
# the real data has 265 zones, this keeps it small
ZONES = [
    (132, "Queens", "JFK Airport", "Airports", "airport", 140),
    (138, "Queens", "LaGuardia Airport", "Airports", "airport", 110),
    (161, "Manhattan", "Midtown Center", "Yellow Zone", "business", 160),
    (162, "Manhattan", "Midtown East", "Yellow Zone", "business", 130),
    (230, "Manhattan", "Times Sq/Theatre District", "Yellow Zone", "business", 120),
    (186, "Manhattan", "Penn Station/Madison Sq West", "Yellow Zone", "business", 115),
    (237, "Manhattan", "Upper East Side South", "Yellow Zone", "residential", 125),
    (236, "Manhattan", "Upper East Side North", "Yellow Zone", "residential", 105),
    (239, "Manhattan", "Upper West Side South", "Yellow Zone", "residential", 80),
    (142, "Manhattan", "Lincoln Square East", "Yellow Zone", "residential", 75),
    (79, "Manhattan", "East Village", "Yellow Zone", "nightlife", 90),
    (48, "Manhattan", "Clinton East", "Yellow Zone", "nightlife", 85),
    (249, "Manhattan", "West Village", "Yellow Zone", "nightlife", 70),
    (148, "Manhattan", "Lower East Side", "Yellow Zone", "nightlife", 55),
    (68, "Manhattan", "East Chelsea", "Boro Zone", "nightlife", 65),
    (234, "Manhattan", "Union Sq", "Yellow Zone", "business", 70),
    (170, "Manhattan", "Murray Hill", "Yellow Zone", "residential", 60),
    (107, "Manhattan", "Gramercy", "Yellow Zone", "residential", 55),
    (113, "Manhattan", "Greenwich Village North", "Yellow Zone", "nightlife", 45),
    (141, "Manhattan", "Lenox Hill West", "Yellow Zone", "residential", 50),
    (7, "Queens", "Astoria", "Boro Zone", "residential", 12),
    (181, "Brooklyn", "Park Slope", "Boro Zone", "residential", 8),
    (255, "Brooklyn", "Williamsburg (North Side)", "Boro Zone", "nightlife", 10),
    (264, "Unknown", "N/A", "N/A", "unknown", 6),
    (265, "N/A", "Outside of NYC", "N/A", "unknown", 3),
]

# relative demand by hour of day (0-23) for each personality
SHAPES = {
    "business":    [.2, .1, .05, .05, .05, .2, .5, 1.1, 1.5, 1.3, 1.0, 1.0, 1.1, 1.0, 1.0, 1.1, 1.3, 1.6, 1.7, 1.4, 1.1, .9, .7, .4],
    "residential": [.3, .2, .1, .05, .1, .3, .8, 1.5, 1.6, 1.2, .9, .8, .8, .8, .8, .9, 1.0, 1.1, 1.0, .9, .8, .7, .6, .4],
    "nightlife":   [1.4, 1.2, .9, .5, .2, .1, .1, .2, .3, .4, .5, .6, .7, .7, .7, .8, .9, 1.0, 1.2, 1.4, 1.5, 1.6, 1.7, 1.6],
    "airport":     [.4, .2, .1, .1, .3, .6, .9, 1.0, 1.0, 1.0, 1.0, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.5, 1.4, 1.3, 1.3, 1.2, 1.0, .7],
    "unknown":     [1] * 24,
}


def weather(rng):
    hours = pd.date_range(f"{YEAR}-01-01", f"{YEAR}-12-31 23:00", freq="h")
    day = hours.dayofyear.to_numpy()
    temp = 55 - 22 * np.cos(2 * np.pi * (day - 15) / 365) + rng.normal(0, 5, len(hours))
    raining = rng.random(len(hours)) < 0.08
    precip = np.where(raining, rng.gamma(1.2, 0.05, len(hours)), 0.0)
    snow = np.where((temp < 32) & raining, precip * 8, 0.0)
    return pd.DataFrame({"time": hours.strftime("%Y-%m-%dT%H:%M"),
                         "temperature_2m": temp.round(1),
                         "precipitation": precip.round(3),
                         "snowfall": snow.round(2)})


def month_of_trips(month, rng, wx):
    hours = pd.date_range(f"{YEAR}-{month:02d}-01", periods=pd.Timestamp(f"{YEAR}-{month:02d}-01").days_in_month * 24, freq="h")
    rain = wx.set_index(pd.to_datetime(wx["time"]))["precipitation"].reindex(hours).fillna(0).to_numpy() > 0
    holidays = USFederalHolidayCalendar().holidays(f"{YEAR}-01-01", f"{YEAR}-12-31")

    parts = []
    for zid, _, _, _, kind, base in ZONES:
        shape = np.array(SHAPES[kind])[hours.hour]
        dow = hours.dayofweek.to_numpy()
        if kind == "business":
            dow_factor = np.where(dow >= 5, 0.45, 1.0)
        elif kind == "nightlife":
            dow_factor = np.where(dow >= 4, 1.5, 0.8)
        else:
            dow_factor = np.ones(len(hours))
        holiday = np.isin(hours.normalize(), holidays)
        # slow growth through the year, more rides in the rain, fewer on holidays
        lam = (base / 10) * shape * dow_factor * (1 + 0.02 * (month - 1)) * np.where(rain, 1.15, 1.0) * np.where(holiday, 0.6, 1.0)
        counts = rng.poisson(lam)
        starts = np.repeat(hours.to_numpy(), counts) + rng.integers(0, 3600, counts.sum()).astype("timedelta64[s]")
        parts.append(pd.DataFrame({"PULocationID": zid, "tpep_pickup_datetime": starts}))

    df = pd.concat(parts, ignore_index=True)
    n = len(df)
    dist = np.round(rng.gamma(2.0, 1.6, n), 2)
    dist[df["PULocationID"].isin([132, 138]).to_numpy()] += 12  # airport rides run long
    minutes = dist * 3.2 + rng.normal(6, 3, n).clip(1)
    fare = np.round(3 + dist * 2.8 + minutes * 0.7, 2)
    pay = rng.choice([1, 2, 3, 4], n, p=[0.78, 0.18, 0.02, 0.02])
    tip = np.where(pay == 1, np.round(fare * rng.uniform(0.1, 0.25, n), 2), 0.0)

    df["tpep_dropoff_datetime"] = df["tpep_pickup_datetime"] + pd.to_timedelta(minutes, unit="min")
    df["VendorID"] = rng.choice([1, 2], n)
    df["passenger_count"] = rng.choice([1, 1, 1, 2, 3], n).astype(float)
    df["trip_distance"] = dist
    df["RatecodeID"] = 1.0
    df["store_and_fwd_flag"] = "N"
    df["DOLocationID"] = rng.choice([z[0] for z in ZONES], n)
    df["payment_type"] = pay
    df["fare_amount"] = fare
    df["extra"] = 1.0
    df["mta_tax"] = 0.5
    df["tip_amount"] = tip
    df["tolls_amount"] = 0.0
    df["improvement_surcharge"] = 1.0
    df["total_amount"] = np.round(fare + tip + 2.5, 2)
    df["congestion_surcharge"] = 2.5

    # the junk the real files always have
    bad = rng.choice(n, size=int(n * 0.03), replace=False)
    third = len(bad) // 3
    df.loc[bad[:third], "fare_amount"] *= -1
    df.loc[bad[third:2 * third], "trip_distance"] = 0
    df.loc[bad[2 * third:], "tpep_dropoff_datetime"] = df.loc[bad[2 * third:], "tpep_pickup_datetime"] - pd.Timedelta(minutes=5)
    df.loc[rng.choice(n, 20, replace=False), "tpep_pickup_datetime"] = pd.Timestamp("2009-01-01 00:05")

    # the real files aren't consistent month to month either: the airport fee
    # column changes capitalization and some int columns change size
    if month <= 6:
        df["Airport_fee"] = np.where(df["PULocationID"].isin([132, 138]), 1.75, 0.0)
        df["VendorID"] = df["VendorID"].astype("int32")
    else:
        df["airport_fee"] = np.where(df["PULocationID"].isin([132, 138]), 1.75, 0.0)
        df["VendorID"] = df["VendorID"].astype("int64")
    df["PULocationID"] = df["PULocationID"].astype("int32")
    df["DOLocationID"] = df["DOLocationID"].astype("int32")
    return df.sort_values("tpep_pickup_datetime").reset_index(drop=True)


if __name__ == "__main__":
    rng = np.random.default_rng(RANDOM_STATE)
    pd.DataFrame(ZONES, columns=["LocationID", "Borough", "Zone", "service_zone", "_kind", "_base"]) \
      .drop(columns=["_kind", "_base"]).to_csv(ZONES_FILE, index=False)

    wx = weather(rng)
    wx.to_csv(WEATHER_FILE, index=False)

    total = 0
    for m in MONTHS:
        df = month_of_trips(m, rng, wx)
        # microseconds like the real TLC files. pandas defaults to nanoseconds,
        # which spark refuses to read
        df.to_parquet(TRIPS_DIR / f"yellow_tripdata_{YEAR}-{m:02d}.parquet", index=False,
                      coerce_timestamps="us", allow_truncated_timestamps=True)
        total += len(df)
    print(f"wrote {total:,} fake trips across {len(MONTHS)} months, plus zones and weather")
    print("heads up: practice data only, run sprint 1 for real before sharing anything")
