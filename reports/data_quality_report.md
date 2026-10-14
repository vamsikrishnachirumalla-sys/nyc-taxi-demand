# Data Quality Report (Sprint 1)

**48,722,602 yellow cab trips** in the 2025 files.

## Problems found before cleaning

| Check | Rows | Share |
|---|---|---|
| Pickup date outside the year (clock errors, some are from 2002 or 2009) | 29 | 0.00% |
| Dropoff at or before pickup | 546,304 | 1.12% |
| Trips longer than 3 hours | 18,374 | 0.04% |
| Zero or negative distance | 1,402,958 | 2.88% |
| Over 100 miles | 2,870 | 0.01% |
| Negative fare (refunds and corrections) | 2,848,620 | 5.85% |
| Pickup zone unknown (264/265) | 103,043 | 0.21% |
| Passenger count missing | 11,611,894 | 23.83% |

## Trips per month

| Month | Trips |
|---|---|
| 2025-01 | 3,475,234 |
| 2025-02 | 3,577,542 |
| 2025-03 | 4,145,229 |
| 2025-04 | 3,970,568 |
| 2025-05 | 4,591,844 |
| 2025-06 | 4,322,949 |
| 2025-07 | 3,898,971 |
| 2025-08 | 3,574,080 |
| 2025-09 | 4,251,019 |
| 2025-10 | 4,428,708 |
| 2025-11 | 4,181,432 |
| 2025-12 | 4,304,997 |

## What happens to them in Sprint 2

Spark drops wrong-year pickups, dropoffs before pickups, trips over 3 hours, zero or 100+ mile trips, negative fares, and unknown zones. Missing passenger counts are kept, since demand is about trips, not riders.

## Columns

| Column | Type | Meaning |
|---|---|---|
| VendorID | INTEGER | Which tech provider recorded the trip (1 = Creative Mobile, 2 = Curb/VeriFone) |
| tpep_pickup_datetime | TIMESTAMP | Meter start, local NYC time |
| tpep_dropoff_datetime | TIMESTAMP | Meter stop, local NYC time |
| passenger_count | BIGINT | Entered by the driver, often missing |
| trip_distance | DOUBLE | Miles on the meter |
| RatecodeID | BIGINT | 1 standard, 2 JFK flat fare, 3 Newark, 4 Nassau/Westchester, 5 negotiated, 6 group |
| store_and_fwd_flag | VARCHAR | Y if the trip was stored on the car and sent later (no signal) |
| PULocationID | INTEGER | Pickup taxi zone (1-265), see the zone lookup |
| DOLocationID | INTEGER | Dropoff taxi zone (1-265) |
| payment_type | BIGINT | 1 card, 2 cash, 3 no charge, 4 dispute, 5 unknown, 6 voided |
| fare_amount | DOUBLE | Time and distance fare |
| extra | DOUBLE | Rush hour and overnight surcharges |
| mta_tax | DOUBLE | MTA tax |
| tip_amount | DOUBLE | Tips, only recorded for card payments |
| tolls_amount | DOUBLE | Tolls paid |
| improvement_surcharge | DOUBLE | Improvement surcharge |
| total_amount | DOUBLE | Total charged, not including cash tips |
| congestion_surcharge | DOUBLE | NY state congestion surcharge |
| Airport_fee | DOUBLE | Fee for pickups at LaGuardia and JFK |
| cbd_congestion_fee | DOUBLE | Manhattan congestion pricing fee, started January 2025 |