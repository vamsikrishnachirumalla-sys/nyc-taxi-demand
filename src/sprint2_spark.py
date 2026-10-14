# Sprint 2 - clean a year of trips with spark and roll them up to hourly demand
#
# ~40M rows is past what pandas handles comfortably on a laptop, so this is
# a spark job. output is one row per zone per hour, which is what every later
# sprint actually needs
#
#   python src/sprint2_spark.py

import json

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from config import HOURLY_DIR, REPORTS_DIR, TRIPS_DIR, YEAR

# only the columns that matter downstream, cast to one type each.
# the monthly files don't agree on types (int32 vs int64, double vs int),
# so reading them all in one go with mergeSchema blows up. one at a time + cast works
COLUMNS = {
    "tpep_pickup_datetime": "timestamp",
    "tpep_dropoff_datetime": "timestamp",
    "PULocationID": "int",
    "trip_distance": "double",
    "fare_amount": "double",
    "tip_amount": "double",
    "total_amount": "double",
    "payment_type": "int",
}


def spark_session():
    return (SparkSession.builder
            .master("local[*]")
            .appName("nyc-taxi-demand")
            .config("spark.driver.memory", "6g")
            .config("spark.sql.shuffle.partitions", "64")
            # keep timestamps exactly as written. without this spark shifts them
            # by whatever timezone the machine is in
            .config("spark.sql.session.timeZone", "UTC")
            .config("spark.ui.enabled", "false")
            .config("spark.ui.showConsoleProgress", "false")  # progress bars flood the colab output
            .getOrCreate())


def load_trips(spark):
    files = sorted(TRIPS_DIR.glob("yellow_tripdata_*.parquet"))
    frames = []
    for f in files:
        df = spark.read.parquet(str(f))
        frames.append(df.select([F.col(c).cast(t).alias(c) for c, t in COLUMNS.items()]))
    trips = frames[0]
    for df in frames[1:]:
        trips = trips.unionByName(df)
    return trips


def clean(trips):
    minutes = (F.unix_timestamp("tpep_dropoff_datetime") - F.unix_timestamp("tpep_pickup_datetime")) / 60
    return (trips
            .withColumn("minutes", minutes)
            .where(F.year("tpep_pickup_datetime") == YEAR)
            .where((F.col("minutes") > 0) & (F.col("minutes") <= 180))
            .where((F.col("trip_distance") > 0) & (F.col("trip_distance") <= 100))
            .where(F.col("fare_amount") >= 0)
            .where(~F.col("PULocationID").isin(264, 265)))


def hourly(trips):
    # hour as plain text on purpose. timestamps crossing spark -> parquet -> pandas
    # is where timezone bugs sneak in, a string can't get shifted
    card = F.col("payment_type") == 1
    return (trips
            .withColumn("hour", F.date_format("tpep_pickup_datetime", "yyyy-MM-dd HH:00:00"))
            .groupBy("PULocationID", "hour")
            .agg(F.count("*").alias("trips"),
                 F.round(F.avg("fare_amount"), 2).alias("avg_fare"),
                 F.round(F.avg("trip_distance"), 2).alias("avg_miles"),
                 F.round(F.avg("minutes"), 1).alias("avg_minutes"),
                 F.sum(F.when(card, 1).otherwise(0)).alias("card_trips"),
                 F.round(F.sum(F.when(card, F.col("tip_amount")).otherwise(0)), 2).alias("card_tips"),
                 F.round(F.sum(F.when(card, F.col("fare_amount")).otherwise(0)), 2).alias("card_fares"),
                 F.round(F.sum("total_amount"), 2).alias("revenue"))
            .withColumnRenamed("PULocationID", "zone_id"))


if __name__ == "__main__":
    spark = spark_session()
    spark.sparkContext.setLogLevel("ERROR")

    raw = load_trips(spark)
    raw_count = raw.count()
    trips = clean(raw).cache()
    kept = trips.count()

    out = hourly(trips)
    out.coalesce(4).write.mode("overwrite").parquet(str(HOURLY_DIR))
    rows = spark.read.parquet(str(HOURLY_DIR)).count()

    stats = {"raw_trips": raw_count, "clean_trips": kept, "dropped": raw_count - kept,
             "dropped_share": round((raw_count - kept) / raw_count, 4), "zone_hour_rows": rows}
    (REPORTS_DIR / "spark_cleaning.json").write_text(json.dumps(stats, indent=2))
    spark.stop()

    print(f"raw trips:        {raw_count:,}")
    print(f"after cleaning:   {kept:,}  (dropped {stats['dropped_share']:.1%})")
    print(f"zone-hour rows:   {rows:,}")
