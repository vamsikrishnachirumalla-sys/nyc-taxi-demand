# Sprint 4 - group zones by WHEN people ride, not how much
#
# every zone gets a 168-number fingerprint: its share of weekly rides in each
# hour of the week. normalizing to shares means midtown and a quiet zone can land
# in the same group if their rhythm matches. then kmeans on those fingerprints
#
#   python src/sprint4_clusters.py

import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

from config import CLUSTERS_FILE, FIGURES_DIR, RANDOM_STATE, REPORTS_DIR, WAREHOUSE

MIN_TRIPS = 2000  # under this a zone's weekly pattern is mostly noise
COLORS = ["#1f6f8b", "#d1495b", "#edae49", "#66a182", "#8d6a9f", "#2e4057", "#e07a5f", "#81b29a"]


def weekly_profiles():
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    df = con.execute("""
        select f.zone_id, z.zone_name, z.borough, z.is_airport,
               t.day_of_week * 24 + t.hour_of_day as how,   -- hour of week, 0 = monday midnight
               avg(f.trips) as avg_trips, sum(f.trips) as trips
        from fact_zone_hour f
        join dim_time t using (hour_ts)
        join dim_zone z using (zone_id)
        group by all
    """).df()
    con.close()

    totals = df.groupby("zone_id")["trips"].sum().astype(int)
    keep = totals[totals >= MIN_TRIPS].index
    df = df[df["zone_id"].isin(keep)]

    grid = df.pivot_table(index="zone_id", columns="how", values="avg_trips", fill_value=0)
    grid = grid.reindex(columns=range(168), fill_value=0)
    shares = grid.div(grid.sum(axis=1), axis=0)
    info = (df.drop_duplicates("zone_id").set_index("zone_id")[["zone_name", "borough", "is_airport"]]
              .join(totals.rename("trips")).loc[shares.index])
    return shares, info


def pick_k(X):
    # try a few k and keep the one with the best silhouette. capped at 8,
    # more groups than that stops being something a dispatcher can use
    scores = {}
    for k in range(3, min(9, len(X))):
        labels = KMeans(n_clusters=k, n_init=20, random_state=RANDOM_STATE).fit_predict(X)
        scores[k] = silhouette_score(X, labels)
    return max(scores, key=scores.get), scores


def traits(profile):
    hours = np.arange(168)
    day, hod = hours // 24, hours % 24
    weekday = day < 5
    return {
        "night": profile[(hod <= 4)].sum(),                                   # midnight to 5am
        "weekend": profile[day >= 5].sum(),
        "am_rush": profile[weekday & (hod >= 6) & (hod <= 9)].sum(),
        "pm_rush": profile[weekday & (hod >= 16) & (hod <= 19)].sum(),
    }


def name_clusters(centers, info, labels):
    # name each group by what makes it stand out compared to the other groups.
    # first version went by the share of airport zones in a group, but on the real
    # data JFK sits in a group of 28 with times sq and union sq, so it got called
    # "business district". now the biggest zones in a group get a say too
    t = pd.DataFrame([traits(c) for c in centers])
    z = (t - t.mean()) / (t.std() + 1e-9)
    info = info.assign(label=labels)
    ride_share = info.groupby("label")["trips"].sum() / info["trips"].sum()

    names = {}
    for c in range(len(centers)):
        top3 = info[info["label"] == c].nlargest(3, "trips")
        if ride_share.get(c, 0) < 0.01:
            # a couple of quiet zones with odd hours, not worth a real label
            name = "Low-volume / irregular"
        elif top3["is_airport"].any():
            name = "Airports & tourist hubs"
        elif z.loc[c, "night"] + z.loc[c, "weekend"] > 1.5:
            name = "Nightlife"
        elif t.loc[c, "am_rush"] > t.loc[c, "pm_rush"]:
            # more pickups in the morning than the evening = people leaving home
            name = "Residential (morning peak)"
        elif z.loc[c, "weekend"] < 0:
            name = "Weekday core (evening peak)"
        else:
            name = "Mixed"
        base, n = name, 2
        while name in names.values():
            name = f"{base} {n}"
            n += 1
        names[c] = name
    return names, t


def chart_profiles(centers, names, sizes):
    fig, ax = plt.subplots(figsize=(11, 4.2))
    for c, center in enumerate(centers):
        ax.plot(range(168), center * 100, color=COLORS[c % len(COLORS)], linewidth=1.8,
                label=f"{names[c]} ({sizes[c]} zones)")
    for d in range(1, 7):
        ax.axvline(d * 24, color="#ddd", linewidth=0.8)
    ax.set_xticks([d * 24 + 12 for d in range(7)], ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
    ax.set_ylabel("Share of the zone's weekly rides (%)")
    ax.legend(frameon=False, fontsize=8, loc="upper left", bbox_to_anchor=(1, 1))
    ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Zone clusters: the weekly rhythm of each group", x=0.01, ha="left",
                 fontsize=12, fontweight="bold")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "04_zone_clusters.png", dpi=150)
    plt.close(fig)


def chart_silhouette(scores, best):
    fig, ax = plt.subplots(figsize=(6, 3.5))
    ks = list(scores)
    ax.plot(ks, [scores[k] for k in ks], marker="o", color="#1f6f8b", linewidth=2)
    ax.scatter([best], [scores[best]], color="#d1495b", zorder=3, s=60)
    ax.set_xlabel("Number of clusters (k)")
    ax.set_ylabel("Silhouette score")
    ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle(f"Picking k: {best} groups separate best", x=0.01, ha="left", fontsize=12, fontweight="bold")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "05_silhouette.png", dpi=150)
    plt.close(fig)


def write_report(info, names, t, scores, best):
    out = ["# Zone Clusters (Sprint 4)", "",
           f"{len(info)} zones with at least {MIN_TRIPS:,} rides, grouped by the shape of their weekly demand.",
           f"Best k by silhouette: **{best}** (score {scores[best]:.3f}).", "",
           "| Cluster | Zones | Rides | Night share | Weekend share | Weekday AM rush | Weekday PM rush | Biggest zones |",
           "|---|---|---|---|---|---|---|---|"]
    for c, name in names.items():
        part = info[info["cluster"] == c].sort_values("trips", ascending=False)
        top = ", ".join(part["zone_name"].head(3))
        r = t.loc[c]
        out.append(f"| {name} | {len(part)} | {part['trips'].sum():,} | {r['night']:.0%} | {r['weekend']:.0%} | "
                   f"{r['am_rush']:.0%} | {r['pm_rush']:.0%} | {top} |")
    out += ["", "Shares are the percent of a zone's weekly rides that fall in each window. "
            "Night = midnight to 5am. Rush = 6-9am and 4-7pm on weekdays."]
    (REPORTS_DIR / "zone_clusters.md").write_text("\n".join(out))


if __name__ == "__main__":
    shares, info = weekly_profiles()
    X = shares.to_numpy()

    best, scores = pick_k(X)
    km = KMeans(n_clusters=best, n_init=20, random_state=RANDOM_STATE).fit(X)
    info["cluster"] = km.labels_
    names, t = name_clusters(km.cluster_centers_, info, km.labels_)
    info["cluster_name"] = info["cluster"].map(names)

    info.reset_index().to_csv(CLUSTERS_FILE, index=False)
    sizes = info["cluster"].value_counts().to_dict()
    chart_profiles(km.cluster_centers_, names, sizes)
    chart_silhouette(scores, best)
    write_report(info, names, t, scores, best)

    print("silhouette by k:", {k: round(v, 3) for k, v in scores.items()})
    print(f"picked k = {best}\n")
    for c, name in names.items():
        part = info[info["cluster"] == c].sort_values("trips", ascending=False)
        print(f"{name:32s} {len(part):3d} zones  e.g. {', '.join(part['zone_name'].head(3))}")
