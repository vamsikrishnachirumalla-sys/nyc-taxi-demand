# SQL Answers (Sprint 3)

Each answer comes from `sql/questions.sql`, run against the star schema in `sql/schema.sql`.

## Which 10 pickup zones generate the most rides, and what share of the city do they cover?

`busiest_zones`

| zone_name | borough | trips | pct_of_city |
|---|---|---|---|
| Upper East Side South | Manhattan | 1,998,154 | 4.5 |
| Midtown Center | Manhattan | 1,945,577 | 4.4 |
| JFK Airport | Queens | 1,878,630 | 4.3 |
| Upper East Side North | Manhattan | 1,746,408 | 4 |
| Penn Station/Madison Sq West | Manhattan | 1,443,748 | 3.3 |
| Midtown East | Manhattan | 1,411,874 | 3.2 |
| Times Sq/Theatre District | Manhattan | 1,392,575 | 3.2 |
| Lincoln Square East | Manhattan | 1,286,088 | 2.9 |
| LaGuardia Airport | Queens | 1,224,530 | 2.8 |
| Union Sq | Manhattan | 1,187,689 | 2.7 |

## How are rides and revenue split across boroughs?

`borough_share`

| borough | trips | pct_trips | revenue | pct_revenue |
|---|---|---|---|---|
| Manhattan | 38,095,705 | 86.4 | 933,869,893 | 73.4 |
| Queens | 4,170,203 | 9.5 | 282,338,893 | 22.2 |
| Brooklyn | 1,472,360 | 3.3 | 44,683,184 | 3.5 |
| Bronx | 339,417 | 0.8 | 10,763,616 | 0.8 |
| Staten Island | 3,666 | 0 | 158,541 | 0 |
| EWR | 1,341 | 0 | 133,748 | 0 |

## When is the city busiest? Average rides per hour for every hour of the week.

`hour_of_week`

| day_of_week | day_name | hour_of_day | avg_trips |
|---|---|---|---|
| 0 | Monday | 0 | 1,992 |
| 0 | Monday | 1 | 993 |
| 0 | Monday | 2 | 546 |
| 0 | Monday | 3 | 402 |
| 0 | Monday | 4 | 546 |
| 0 | Monday | 5 | 979 |
| 0 | Monday | 6 | 2,124 |
| 0 | Monday | 7 | 3,938 |
| 0 | Monday | 8 | 5,184 |
| 0 | Monday | 9 | 5,147 |
| 0 | Monday | 10 | 5,058 |
| 0 | Monday | 11 | 5,271 |

## How did ride volume move month to month?

`monthly_trend`

| month | trips | pct_change |
|---|---|---|
| 1 | 3,243,640 | nan |
| 2 | 3,298,307 | 1.7 |
| 3 | 3,818,680 | 15.8 |
| 4 | 3,663,779 | -4.1 |
| 5 | 4,084,274 | 11.5 |
| 6 | 3,862,445 | -5.4 |
| 7 | 3,487,923 | -9.7 |
| 8 | 3,174,761 | -9 |
| 9 | 3,831,491 | 20.7 |
| 10 | 3,936,822 | 2.7 |
| 11 | 3,637,246 | -7.6 |
| 12 | 4,043,324 | 11.2 |

## Do people take more cabs when it rains? Compared at the same hour of day and day type, so rush hour doesn't skew it.

`rain_effect`

| hour_of_day | is_weekend | dry_avg | rain_avg | pct_lift |
|---|---|---|---|---|
| 0 | 0 | 2,414 | 2,741 | 13.6 |
| 1 | 0 | 1,191 | 1,614 | 35.5 |
| 2 | 0 | 677 | 755 | 11.5 |
| 3 | 0 | 464 | 411 | -11.4 |
| 4 | 0 | 524 | 612 | 16.6 |
| 5 | 0 | 945 | 1,111 | 17.6 |
| 6 | 0 | 2,134 | 2,491 | 16.7 |
| 7 | 0 | 4,177 | 4,671 | 11.8 |
| 8 | 0 | 5,573 | 6,328 | 13.6 |
| 9 | 0 | 5,571 | 6,134 | 10.1 |
| 10 | 0 | 5,463 | 5,986 | 9.6 |
| 11 | 0 | 5,689 | 6,236 | 9.6 |

## How different are airport rides from everything else?

`airport_vs_city`

| segment | trips | pct_trips | pct_revenue | avg_fare | avg_miles |
|---|---|---|---|---|---|
| Rest of the city | 40,978,191 | 93 | 81.1 | 17.28 | 2.8 |
| Airports (JFK, LGA, EWR) | 3,104,501 | 7 | 18.9 | 56.41 | 13.1 |

## Where do riders tip the most? (card payments only, cash tips aren't recorded)

`tip_rate_by_borough`

| borough | card_trips | tip_pct_of_fare |
|---|---|---|
| Manhattan | 26,908,419 | 23.5 |
| Queens | 2,818,963 | 19.8 |
| EWR | 1,206 | 14.3 |
| Brooklyn | 404,070 | 4.3 |
| Bronx | 124,503 | 0.8 |

## How much do federal holidays cut demand compared to a normal weekday?

`holiday_effect`

| day_type | days | avg_daily_trips |
|---|---|---|
| Federal holiday | 11 | 90,340 |
| Regular weekday | 250 | 121,390 |

## Which busy zones grew the most from the first half of the year to the second?

`fastest_growing_zones`

| zone_name | borough | h1 | h2 | pct_growth |
|---|---|---|---|---|
| Queensbridge/Ravenswood | Queens | 8,197 | 12,276 | 49.8 |
| Inwood | Manhattan | 6,568 | 9,760 | 48.6 |
| Coney Island | Brooklyn | 5,458 | 8,089 | 48.2 |
| Washington Heights North | Manhattan | 14,544 | 21,213 | 45.9 |
| Co-Op City | Bronx | 5,281 | 7,497 | 42 |
| Stuyvesant Heights | Brooklyn | 18,311 | 25,288 | 38.1 |
| Bushwick South | Brooklyn | 23,904 | 32,980 | 38 |
| Greenpoint | Brooklyn | 22,882 | 30,863 | 34.9 |
| DUMBO/Vinegar Hill | Brooklyn | 21,304 | 28,680 | 34.6 |
| Williamsburg (North Side) | Brooklyn | 35,661 | 47,277 | 32.6 |
