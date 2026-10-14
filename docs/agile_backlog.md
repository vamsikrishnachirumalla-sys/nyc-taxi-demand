# Agile Backlog: NYC Taxi Demand Forecasting

## Product vision

Help a taxi fleet put cars where the riders will be. Know when and where demand peaks, which neighborhoods behave alike, and how many pickups to expect in each busy zone a week from now.

## Roles

| Role | Person | Cares about |
|---|---|---|
| Product owner | Fleet operations manager | Fewer empty miles, shorter rider waits |
| End users | Dispatchers | Where to send drivers each shift |
| Stakeholder | Finance | Revenue by area and time |
| Data analyst | Vamsi Krishna Chirumalla | Building and explaining the analysis |

## Definition of done

The script runs from a clean checkout, outputs land in `reports/`, every model is compared against a simple baseline, and findings are written in plain language for the person who asked.

---

## Epic 1: Data foundation (Sprint 1)

**US-1.1** As an analyst, I need a year of trip records, zone names, and weather in one place.
- Acceptance: download is repeatable, skips files already on disk, and keeps going if weather is unavailable.

**US-1.2** As an analyst, I need to know how dirty the raw data is before cleaning it.
- Acceptance: every problem type counted on the raw files, written up with what Sprint 2 does about it.

## Epic 2: Big data processing (Sprint 2)

**US-2.1** As an analyst, I need ~40M trips cleaned and rolled up to hourly demand per zone.
- Acceptance: PySpark job, consistent column types across months, rows in vs rows kept reported.

## Epic 3: Data warehouse (Sprint 3)

**US-3.1** As finance and operations, I want answers to business questions without writing Python.
- Acceptance: star schema (one fact, three dimensions), every question answered by a SQL file anyone can rerun.

## Epic 4: Zone segmentation (Sprint 4)

**US-4.1** As the operations manager, I want zones grouped by when people ride, so I can plan shifts by area type.
- Acceptance: zones clustered on the shape of their weekly demand, k chosen by silhouette, groups named in plain language.

## Epic 5: Forecasting (Sprint 5)

**US-5.1** As a dispatcher, I want each busy zone's hourly pickups forecast a week ahead.
- Acceptance: only inputs known a week early, tested on a normal 4-week window and the December holidays separately, every model compared with "same hour last week".

**US-5.2** As the operations manager, I want to know where the forecast is weakest.
- Acceptance: error broken out by zone cluster.

## Epic 6: Dashboard (Sprint 6)

**US-6.1** As all users, I want one place to explore demand, zones, SQL answers, and forecasts.
- Acceptance: live Streamlit app that runs on the free tier without Spark or the raw data.

---

## Sprint plan

| Sprint | Goal | Course it draws on |
|---|---|---|
| 1 | Data foundation and quality report | Introduction to Data Science |
| 2 | PySpark cleaning and aggregation | Intro to Business Analytics and Big Data |
| 3 | Star schema and SQL questions | Database Management Systems |
| 4 | Zone clustering | Data Mining and Machine Learning |
| 5 | Week-ahead forecasting | Data Mining and Predictive Analytics |
| 6 | Dashboard | |

---

## Sprint retrospectives

### Sprint 1
- **What went well:** DuckDB counted problems across all twelve files in place, without loading them into memory.
- **What didn't:** Passenger count is missing on 23.8% of trips, so I left it out of every analysis.
- **What I'll change:** Nothing for now.

### Sprint 2
- **What went well:** 48.7M raw trips came down to 44.1M clean ones and 1.36M zone-hour rows, small enough for everything after this sprint.
- **What didn't:** 9.5% of trips were dropped. The two biggest causes were negative fares (refunds and corrections) and zero-distance trips.
- **What I'll change:** Keep refunds in a separate table if finance ever needs net revenue.

### Sprint 3
- **What went well:** Every business question is one block in `sql/questions.sql`, and the dashboard shows the exact query next to the answer.
- **What didn't:** Tip rates only cover card payments. Cash tips aren't in the data, which makes Brooklyn and the Bronx look worse than they probably are.
- **What I'll change:** Label that caveat wherever tip rates are shown.

### Sprint 4
- **What went well:** Five groups with a clear story, and the residential zones stood out on their morning peak.
- **What didn't:** My first naming rules went by the share of airport zones in a group, so JFK's group got called "Business district" and the Upper East Side's group got the same name.
- **What I'll change:** Names now come from each group's biggest zones and its ride share, checked against the real zone lists.

### Sprint 5
- **What went well:** The time-based setup held up. Nothing in a test window was seen during training.
- **What didn't:** My first test window was the last four weeks of the year, which is Christmas, with lags pointing at Thanksgiving. And on normal weeks neither model beat the four-week average.
- **What I'll change:** Test on a normal window and the holidays separately (done). Next I'd try predicting the ratio to the four-week average instead of the raw count, plus a holiday calendar feature.

### Sprint 6
- **What went well:** The dashboard runs from about 1MB of prepared files, no Spark or raw data needed.
- **What didn't:**
- **What I'll change:** Add a view of next week's forecast for dispatchers, not just the test windows.
