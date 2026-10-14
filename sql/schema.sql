-- star schema for the taxi warehouse
-- one fact table (rides per zone per hour) and three dimensions around it.
-- grain of the fact = one pickup zone in one hour

create or replace table dim_zone (
    zone_id       integer primary key,
    borough       varchar,
    zone_name     varchar,
    service_zone  varchar,
    is_airport    boolean
);

create or replace table dim_time (
    hour_ts      timestamp primary key,
    date         date,
    hour_of_day  integer,
    day_of_week  integer,   -- 0 = monday, matches pandas
    day_name     varchar,
    is_weekend   boolean,
    month        integer,
    is_holiday   boolean
);

create or replace table dim_weather (
    hour_ts      timestamp primary key,
    temp_f       double,
    precip_in    double,
    snow_in      double,
    is_raining   boolean
);

create or replace table fact_zone_hour (
    zone_id      integer references dim_zone (zone_id),
    hour_ts      timestamp references dim_time (hour_ts),
    trips        integer,
    avg_fare     double,
    avg_miles    double,
    avg_minutes  double,
    card_trips   integer,
    card_tips    double,
    card_fares   double,
    revenue      double,
    primary key (zone_id, hour_ts)
);
