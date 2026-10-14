# Zone Clusters (Sprint 4)

215 zones with at least 2,000 rides, grouped by the shape of their weekly demand.
Best k by silhouette: **5** (score 0.384).

| Cluster | Zones | Rides | Night share | Weekend share | Weekday AM rush | Weekday PM rush | Biggest zones |
|---|---|---|---|---|---|---|---|
| Residential (morning peak) | 141 | 2,574,862 | 16% | 31% | 17% | 10% | East Harlem North, Central Harlem North, Stuy Town/Peter Cooper Village |
| Nightlife | 11 | 3,728,758 | 32% | 50% | 7% | 7% | East Village, West Village, Greenwich Village South |
| Low-volume / irregular | 2 | 25,856 | 36% | 54% | 8% | 7% | Maspeth, Brooklyn Navy Yard |
| Weekday core (evening peak) | 33 | 25,830,100 | 4% | 26% | 12% | 19% | Upper East Side South, Midtown Center, Upper East Side North |
| Airports & tourist hubs | 28 | 11,897,658 | 13% | 34% | 8% | 15% | JFK Airport, Times Sq/Theatre District, Union Sq |

Shares are the percent of a zone's weekly rides that fall in each window. Night = midnight to 5am. Rush = 6-9am and 4-7pm on weekdays.