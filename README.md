# NYC Taxi Demand Forecasting

[![Open the live dashboard](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://nyc-taxi-demand-cxh7drjmmmg3bs8emlw4s4.streamlit.app/)

**[View the live dashboard →](https://nyc-taxi-demand-cxh7drjmmmg3bs8emlw4s4.streamlit.app/)**

**Where and when will people need a cab next week, and which parts of the city behave alike?**

A year of New York City yellow cab trips is close to 49 million rides, too big to work with comfortably in pandas. This project cleans them with PySpark, loads them into a star-schema warehouse to answer business questions in SQL, groups the city's zones by the rhythm of their weekly demand, and forecasts hourly pickups a week ahead for the busiest zones.

I ran it as a six-sprint agile project. The backlog, user stories, and retrospectives are in [docs/agile_backlog.md](docs/agile_backlog.md).

---

## Key findings

All numbers are from the 2025 yellow cab data: 48.7 million raw trips, 44.1 million after cleaning (9.5% dropped as clock errors, refunds, zero-distance and impossible trips).

1. **The city peaks on weekday evenings, not mornings.** The busiest hour of the week is Thursday 6pm at about 9,000 rides citywide, and 6pm Wednesday is close behind. The quietest is Tuesday 3am at under 300.
2. **Rain adds riders, mostly at night.** Comparing wet and dry hours at the same hour and day type, rides go up in 37 of the 48 slots, by 6% on average. The biggest jump is weekday 1am (+35%).
3. **Five kinds of zones.** Clustering 215 zones on the shape of their week (silhouette 0.38) found a weekday core that peaks in the evening (33 zones, 59% of rides, led by the Upper East Side and Midtown), airports and tourist hubs (28 zones, 27%, led by JFK and Times Square), nightlife (11 zones, half their rides on weekends), residential zones that peak in the morning (141 zones but only 6% of rides), and two quiet zones with irregular late-night spikes.
4. **The simple baseline was hard to beat.** On four normal weeks (Oct 27 to Nov 23), the average of the same hour over the last four weeks had 15.4% error (WAPE), 18% less than repeating last week. Ridge regression (15.9%) and gradient boosting (16.1%) didn't beat it. In the December holiday window everything got worse: Ridge was best at 30.0%, against 33.8% for last week's numbers.
5. **Residential zones and holidays are the weak spots.** In normal weeks the weekday core forecasts to 14% error while residential zones sit at 35%, because they're small and noisy. Over the holidays error roughly doubles in the other three zone types.

Other answers from the warehouse: airports are 7% of trips but 19% of revenue ($56 average fare vs $17). Federal holidays average 26% fewer rides than regular weekdays. Recorded card tips are 23.5% of the fare in Manhattan and under 5% in Brooklyn and the Bronx, though cash tips aren't recorded at all.

## Recommendation

For staffing a normal week, a four-week rolling average per zone and hour is accurate to about 15% and needs no model to maintain, so start there. Plan holiday weeks separately. In December every method's error doubled to about 30%, because the weeks before don't look like Christmas week.

---

## What's in the dashboard

The [live dashboard](https://nyc-taxi-demand-cxh7drjmmmg3bs8emlw4s4.streamlit.app/) (or `streamlit run app.py` locally) has five tabs:

| Tab | Who it's for | What it does |
|---|---|---|
| City overview | Operations manager | Daily rides, the hour-of-week heatmap, rain and holiday effects, borough split |
| Zone explorer | Dispatchers | Pick any zone, see its typical week and forecast vs actual in either test window |
| Zone clusters | Operations manager | Which zones share the same weekly rhythm |
| SQL answers | Finance, operations | Every business question with its answer and the SQL that produced it |
| Forecast quality | Anyone checking the work | Error for every model and zone type in both test windows, against the baselines |

---

## How it was built

| Sprint | Goal | Script | Course it draws on |
|---|---|---|---|
| 1 | Data foundation and quality report | `src/sprint1_data.py` | Introduction to Data Science |
| 2 | Clean ~49M trips and roll up to hourly demand | `src/sprint2_spark.py` | Intro to Business Analytics and Big Data |
| 3 | Star schema warehouse and SQL questions | `src/sprint3_warehouse.py`, `sql/` | Database Management Systems |
| 4 | Cluster zones by weekly rhythm | `src/sprint4_clusters.py` | Data Mining and Machine Learning |
| 5 | Forecast pickups a week ahead | `src/sprint5_forecast.py` | Data Mining and Predictive Analytics |
| 6 | Dashboard | `src/sprint6_app_data.py`, `app.py` | |

## Decisions worth explaining

**Spark for the heavy lifting, DuckDB for the questions.** Spark cleans and aggregates the full year of trips. The result is small enough (one row per zone per hour) for DuckDB, which runs real SQL from a single file with no server to set up.

**Reading the monthly files one at a time.** The TLC files aren't consistent from month to month: column types change size and the airport fee column changes capitalization. Each month is read on its own and cast to one type per column before combining, instead of trusting Spark to merge them.

**Hours as text across the Spark boundary.** Timestamps moving from Spark to Parquet to pandas are where timezone bugs hide. The hourly output stores the hour as plain text, which can't get shifted.

**A star schema.** One fact table (rides per zone per hour) and three dimensions (zone, time, weather). Questions like "do people ride more in the rain" become a join. The rain question also compares wet and dry hours at the same hour of day and day type, so rush hour doesn't skew the result.

**Clustering on shape, not size.** Each zone's weekly demand is turned into shares that add up to 100%, so a quiet zone and a busy one land together if their riders keep the same schedule. The number of clusters is picked by silhouette score.

**One week ahead, no peeking.** Every forecast input is something you'd know seven days early, so the shortest lag is 168 hours. Each test window is trained only on the hours before it starts. A random split would leak the future into training.

**Two test windows, not one.** My first run tested only on the last four weeks of the year. That window is Christmas, and its one-week lags point back at Thanksgiving, so the score said more about holidays than about the model. Now there are two: four normal weeks (Oct 27 to Nov 23) as the headline number, and December 4 to 31 kept as a holiday stress test.

**Baselines first.** Each model has to beat "same hour last week" and "average of the last four weeks" to be worth using.

**WAPE instead of MAPE.** Many zone-hours have zero rides, and percentage error divides by zero there. WAPE divides total error by total rides.

**Poisson loss for gradient boosting.** Ride counts are never negative, and busy zones swing by more than quiet ones. A Poisson loss fits that kind of target better than squared error.

**Weather caveat.** The forecast uses the weather that actually happened, as a stand-in for a weather forecast. A real week-ahead weather forecast is less accurate, so the weather benefit is a best case.

---

## Run it yourself

The easiest way is Google Colab.

```bash
git clone https://github.com/vamsikrishnachirumalla-sys/nyc-taxi-demand.git
cd nyc-taxi-demand
pip install -r requirements-pipeline.txt

python src/sprint1_data.py        # downloads ~700MB of trips on the first run
python src/sprint2_spark.py       # needs Java for Spark
python src/sprint3_warehouse.py
python src/sprint4_clusters.py
python src/sprint5_forecast.py
python src/sprint6_app_data.py
streamlit run app.py
```

To try everything offline with fake data first, run `python src/make_sample_data.py` before Sprint 1.

## Project structure

```
nyc-taxi-demand/
├── app.py                       dashboard
├── src/
│   ├── config.py                shared paths and settings
│   ├── make_sample_data.py      practice data generator
│   ├── sprint1_data.py
│   ├── sprint2_spark.py
│   ├── sprint3_warehouse.py
│   ├── sprint4_clusters.py
│   ├── sprint5_forecast.py
│   └── sprint6_app_data.py
├── sql/
│   ├── schema.sql               star schema
│   └── questions.sql            business questions
├── app_data/                    small files the live dashboard reads
├── reports/                     findings, SQL answers, metrics and charts
├── docs/agile_backlog.md        epics, user stories, retros
├── requirements.txt             dashboard only
└── requirements-pipeline.txt    adds Spark, DuckDB, scikit-learn
```

## Data sources

- Trip records: [NYC Taxi & Limousine Commission](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page), yellow taxi, 2025
- Taxi zone lookup: NYC TLC
- Hourly weather for Central Park: [Open-Meteo historical weather API](https://open-meteo.com/)

---

Built by Vamsi Krishna Chirumalla · [Portfolio](https://vamsikrishnachirumalla.com) · [GitHub](https://github.com/vamsikrishnachirumalla-sys)
