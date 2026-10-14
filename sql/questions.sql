-- business questions answered straight from the warehouse.
-- sprint 3 runs each block and saves the answer to reports/sql/<name>.csv

-- name: busiest_zones
-- question: Which 10 pickup zones generate the most rides, and what share of the city do they cover?
select z.zone_name, z.borough,
       sum(f.trips) as trips,
       round(100.0 * sum(f.trips) / sum(sum(f.trips)) over (), 1) as pct_of_city
from fact_zone_hour f
join dim_zone z using (zone_id)
group by 1, 2
order by trips desc
limit 10;

-- name: borough_share
-- question: How are rides and revenue split across boroughs?
select z.borough,
       sum(f.trips) as trips,
       round(100.0 * sum(f.trips) / sum(sum(f.trips)) over (), 1) as pct_trips,
       round(sum(f.revenue)) as revenue,
       round(100.0 * sum(f.revenue) / sum(sum(f.revenue)) over (), 1) as pct_revenue
from fact_zone_hour f
join dim_zone z using (zone_id)
group by 1
order by trips desc;

-- name: hour_of_week
-- question: When is the city busiest? Average rides per hour for every hour of the week.
with citywide as (
    select hour_ts, sum(trips) as trips
    from fact_zone_hour
    group by 1
)
select t.day_of_week, t.day_name, t.hour_of_day,
       round(avg(c.trips)) as avg_trips
from dim_time t
left join citywide c using (hour_ts)
group by 1, 2, 3
order by 1, 3;

-- name: monthly_trend
-- question: How did ride volume move month to month?
select t.month,
       sum(f.trips) as trips,
       round(100.0 * (sum(f.trips) - lag(sum(f.trips)) over (order by t.month))
             / lag(sum(f.trips)) over (order by t.month), 1) as pct_change
from fact_zone_hour f
join dim_time t using (hour_ts)
group by 1
order by 1;

-- name: rain_effect
-- question: Do people take more cabs when it rains? Compared at the same hour of day and day type, so rush hour doesn't skew it.
with citywide as (
    select hour_ts, sum(trips) as trips
    from fact_zone_hour
    group by 1
),
by_condition as (
    select t.hour_of_day, t.is_weekend, w.is_raining, avg(c.trips) as avg_trips
    from citywide c
    join dim_time t using (hour_ts)
    join dim_weather w using (hour_ts)
    group by 1, 2, 3
)
select dry.hour_of_day, dry.is_weekend,
       round(dry.avg_trips) as dry_avg,
       round(wet.avg_trips) as rain_avg,
       round(100.0 * (wet.avg_trips - dry.avg_trips) / dry.avg_trips, 1) as pct_lift
from by_condition dry
join by_condition wet
  on dry.hour_of_day = wet.hour_of_day and dry.is_weekend = wet.is_weekend
where not dry.is_raining and wet.is_raining
order by dry.is_weekend, dry.hour_of_day;

-- name: airport_vs_city
-- question: How different are airport rides from everything else?
select case when z.is_airport then 'Airports (JFK, LGA, EWR)' else 'Rest of the city' end as segment,
       sum(f.trips) as trips,
       round(100.0 * sum(f.trips) / sum(sum(f.trips)) over (), 1) as pct_trips,
       round(100.0 * sum(f.revenue) / sum(sum(f.revenue)) over (), 1) as pct_revenue,
       round(sum(f.avg_fare * f.trips) / sum(f.trips), 2) as avg_fare,
       round(sum(f.avg_miles * f.trips) / sum(f.trips), 1) as avg_miles
from fact_zone_hour f
join dim_zone z using (zone_id)
group by 1
order by trips desc;

-- name: tip_rate_by_borough
-- question: Where do riders tip the most? (card payments only, cash tips aren't recorded)
select z.borough,
       sum(f.card_trips) as card_trips,
       round(100.0 * sum(f.card_tips) / nullif(sum(f.card_fares), 0), 1) as tip_pct_of_fare
from fact_zone_hour f
join dim_zone z using (zone_id)
group by 1
having sum(f.card_trips) > 1000
order by tip_pct_of_fare desc;

-- name: holiday_effect
-- question: How much do federal holidays cut demand compared to a normal weekday?
with daily as (
    select t.date, any_value(t.is_holiday) as is_holiday, any_value(t.is_weekend) as is_weekend,
           sum(f.trips) as trips
    from fact_zone_hour f
    join dim_time t using (hour_ts)
    group by 1
)
select case when is_holiday then 'Federal holiday' else 'Regular weekday' end as day_type,
       count(*) as days,
       round(avg(trips)) as avg_daily_trips
from daily
where not is_weekend or is_holiday
group by 1;

-- name: fastest_growing_zones
-- question: Which busy zones grew the most from the first half of the year to the second?
with halves as (
    select z.zone_name, z.borough,
           sum(f.trips) filter (where t.month <= 6) as h1,
           sum(f.trips) filter (where t.month > 6) as h2
    from fact_zone_hour f
    join dim_zone z using (zone_id)
    join dim_time t using (hour_ts)
    group by 1, 2
)
select zone_name, borough, h1, h2,
       round(100.0 * (h2 - h1) / h1, 1) as pct_growth
from halves
where h1 >= 5000
order by pct_growth desc
limit 10;
