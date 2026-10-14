# paths + settings shared by every sprint script

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RAW_DIR = ROOT / "data" / "raw"
TRIPS_DIR = RAW_DIR / "trips"
PROCESSED_DIR = ROOT / "data" / "processed"
REPORTS_DIR = ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"
SQL_DIR = ROOT / "sql"
# small files the live dashboard reads. these get committed, everything
# in data/ gets rebuilt from scratch
APP_DIR = ROOT / "app_data"

ZONES_FILE = RAW_DIR / "taxi_zone_lookup.csv"
WEATHER_FILE = RAW_DIR / "weather_hourly.csv"
HOURLY_DIR = PROCESSED_DIR / "hourly_zone"  # spark writes a folder of parquet parts
WAREHOUSE = PROCESSED_DIR / "warehouse.duckdb"
CLUSTERS_FILE = PROCESSED_DIR / "zone_clusters.csv"

# yellow cab trip records from the NYC Taxi & Limousine Commission, one parquet per month
TLC_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_{year}-{month:02d}.parquet"
ZONES_URL = "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv"

# free historical weather, no api key. central park coordinates
WEATHER_URL = ("https://archive-api.open-meteo.com/v1/archive?latitude=40.78&longitude=-73.97"
               "&start_date={start}&end_date={end}&hourly=temperature_2m,precipitation,snowfall"
               "&timezone=America%2FNew_York&temperature_unit=fahrenheit&precipitation_unit=inch")

YEAR = 2025
MONTHS = list(range(1, 13))

# two 4-week test windows. the first run only tested on the last 4 weeks of the
# year, which turned out to be christmas, with lags pointing at thanksgiving week.
# that says more about holidays than about the model, so now there's a normal
# stretch (the headline number) and december kept as a stress test.
# each window is trained only on data from before it starts, no random split
TEST_WINDOWS = {
    "normal": ("Normal weeks", f"{YEAR}-10-27", f"{YEAR}-11-23"),
    "holiday": ("Holiday season", f"{YEAR}-12-04", f"{YEAR}-12-31"),
}

# forecasting every one of the 260 zones is mostly forecasting zeros.
# the busiest zones carry the vast majority of rides
TOP_ZONES = 60

RANDOM_STATE = 42

for folder in [TRIPS_DIR, PROCESSED_DIR, REPORTS_DIR, FIGURES_DIR, SQL_DIR, APP_DIR]:
    folder.mkdir(parents=True, exist_ok=True)
