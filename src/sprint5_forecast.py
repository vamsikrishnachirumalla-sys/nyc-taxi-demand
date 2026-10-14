# Sprint 5 - forecast hourly demand per zone, one week ahead
#
# the setup: on any given day, predict how many pickups each busy zone will have
# in every hour a week from now. so every input has to be something you'd know
# 7 days early. that's why the lags start at 168 hours (one week) and nothing shorter
#
# two 4-week test windows (see config.py). for each one the models only train on
# hours before the window starts. time series can't use a random split, the model
# would be peeking at the future
#
#   python src/sprint5_forecast.py

import json

import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from config import (CLUSTERS_FILE, FIGURES_DIR, PROCESSED_DIR, RANDOM_STATE, REPORTS_DIR, TEST_WINDOWS,
                    TOP_ZONES, WAREHOUSE)

LAGS = [168, 336, 504, 672]  # same hour 1, 2, 3, 4 weeks back


def load():
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    top = con.execute(f"""
        select zone_id from fact_zone_hour group by 1 order by sum(trips) desc limit {TOP_ZONES}
    """).df()["zone_id"].tolist()

    # full grid of zone x hour, so hours with zero rides show up as zero instead of missing
    df = con.execute(f"""
        select z.zone_id, z.zone_name, t.hour_ts, t.hour_of_day, t.day_of_week, t.is_weekend,
               t.is_holiday, t.month, coalesce(f.trips, 0) as trips,
               w.temp_f, w.precip_in, w.is_raining
        from dim_zone z
        cross join dim_time t
        left join fact_zone_hour f on f.zone_id = z.zone_id and f.hour_ts = t.hour_ts
        left join dim_weather w on w.hour_ts = t.hour_ts
        where z.zone_id in ({",".join(map(str, top))})
        order by z.zone_id, t.hour_ts
    """).df()
    has_weather = con.execute("select count(*) from dim_weather").fetchone()[0] > 0
    con.close()
    return df, has_weather


def add_features(df):
    g = df.groupby("zone_id")["trips"]
    for lag in LAGS:
        df[f"lag_{lag}"] = g.shift(lag)
    df["avg_4wk"] = df[[f"lag_{l}" for l in LAGS]].mean(axis=1)
    # the first 4 weeks have no full history yet, so they can't be used
    df = df.dropna(subset=[f"lag_{l}" for l in LAGS]).copy()

    clusters = pd.read_csv(CLUSTERS_FILE)[["zone_id", "cluster_name"]]
    df = df.merge(clusters, on="zone_id", how="left")
    df["cluster_name"] = df["cluster_name"].fillna("Unclustered")
    df["is_weekend"] = df["is_weekend"].astype(int)
    df["is_holiday"] = df["is_holiday"].astype(int)
    return df


def split(df, start, end):
    start = pd.Timestamp(start)
    end = pd.Timestamp(end) + pd.Timedelta(days=1)  # end date is inclusive
    train = df[df["hour_ts"] < start].copy()
    test = df[(df["hour_ts"] >= start) & (df["hour_ts"] < end)].copy()
    return train, test


def wape(actual, pred):
    # weighted absolute percent error: total miss / total rides.
    # plain MAPE blows up on hours with zero rides, this doesn't
    return float(np.abs(actual - pred).sum() / max(actual.sum(), 1))


def fit_models(train, test, has_weather):
    numeric = [f"lag_{l}" for l in LAGS] + ["avg_4wk", "is_weekend", "is_holiday"]
    if has_weather:
        # using the weather that actually happened as a stand-in for a weather forecast.
        # a week-ahead forecast is less accurate than this, so it's a small best case
        train[["temp_f", "precip_in"]] = train[["temp_f", "precip_in"]].fillna(0)
        test[["temp_f", "precip_in"]] = test[["temp_f", "precip_in"]].fillna(0)
        numeric += ["temp_f", "precip_in"]
    categorical = ["hour_of_day", "day_of_week", "cluster_name"]
    y = train["trips"]
    preds = {}

    # baselines. any model that can't beat these isn't worth shipping
    preds["Same hour last week"] = test["lag_168"].to_numpy()
    preds["Avg of last 4 weeks"] = test["avg_4wk"].to_numpy()

    ridge = make_pipeline(
        ColumnTransformer([("num", StandardScaler(), numeric),
                           ("cat", OneHotEncoder(handle_unknown="ignore"), categorical)]),
        Ridge(alpha=1.0))
    ridge.fit(train[numeric + categorical], y)
    preds["Ridge regression"] = ridge.predict(test[numeric + categorical]).clip(0)

    # poisson loss because the target is a count: never negative, and the
    # spread grows with the level (a busy zone swings by more rides than a quiet one)
    feats = numeric + categorical
    Xtr, Xte = train[feats].copy(), test[feats].copy()
    for c in categorical:
        cats = pd.Categorical(Xtr[c]).categories
        Xtr[c] = pd.Categorical(Xtr[c], categories=cats).codes
        Xte[c] = pd.Categorical(Xte[c], categories=cats).codes
    gbm = HistGradientBoostingRegressor(loss="poisson", max_iter=400, learning_rate=0.06,
                                        max_leaf_nodes=48, categorical_features=[feats.index(c) for c in categorical],
                                        random_state=RANDOM_STATE)
    gbm.fit(Xtr, y)
    preds["Gradient boosting"] = gbm.predict(Xte)
    return preds


def chart_models(results):
    # one panel per test window, same x scale so they can be compared by eye
    fig, axes = plt.subplots(1, len(results), figsize=(12, 3.8), sharex=True)
    top = max(s["wape"] for r in results.values() for s in r["models"].values()) * 100
    for ax, r in zip(np.atleast_1d(axes), results.values()):
        names = list(r["models"])
        vals = [r["models"][n]["wape"] * 100 for n in names]
        bars = ax.barh(names[::-1], vals[::-1],
                       color=["#d1495b" if n == r["best_model"] else "#1f6f8b" for n in names[::-1]])
        for b, v in zip(bars, vals[::-1]):
            ax.text(v + 0.3, b.get_y() + b.get_height() / 2, f"{v:.1f}%", va="center", fontsize=9)
        ax.set_xlim(0, top * 1.15)
        ax.set_title(f"{r['label']} ({pd.Timestamp(r['start']):%b %d} to {pd.Timestamp(r['end']):%b %d})",
                     fontsize=10, loc="left")
        ax.set_xlabel("WAPE (lower is better)")
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Forecast error by model, one week ahead", x=0.01, ha="left", fontsize=12, fontweight="bold")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "06_model_comparison.png", dpi=150)
    plt.close(fig)


def chart_week(test, best_name, label):
    zone = test.groupby("zone_name")["trips"].sum().idxmax()
    part = test[test["zone_name"] == zone].sort_values("hour_ts")
    start = part["hour_ts"].min() + pd.Timedelta(days=7)  # a week inside the test window
    part = part[(part["hour_ts"] >= start) & (part["hour_ts"] < start + pd.Timedelta(days=7))]
    fig, ax = plt.subplots(figsize=(11, 3.8))
    ax.plot(part["hour_ts"], part["trips"], color="#333", linewidth=1.5, label="Actual")
    ax.plot(part["hour_ts"], part["pred_best"], color="#d1495b", linewidth=1.5, label=best_name)
    ax.plot(part["hour_ts"], part["lag_168"], color="#9aa5b1", linewidth=1, linestyle="--", label="Same hour last week")
    ax.set_ylabel("Pickups per hour")
    ax.legend(frameon=False, fontsize=9, loc="upper left", bbox_to_anchor=(1, 1))
    ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle(f"{zone}: forecast vs actual, one week from the {label.lower()} test window", x=0.01, ha="left",
                 fontsize=12, fontweight="bold")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "07_forecast_week.png", dpi=150)
    plt.close(fig)


def chart_clusters(by_cluster, label):
    by = by_cluster.sort_values("wape")
    # show each group's share of rides in the label. a tiny group with high error
    # matters a lot less than a big one, and the chart should make that obvious
    share = by["trips"] / by["trips"].sum()
    labels = [f"{n} ({s:.0%} of rides)" if s >= 0.01 else f"{n} (<1% of rides)"
              for n, s in zip(by["cluster_name"], share)]
    fig, ax = plt.subplots(figsize=(8, 0.5 * len(by) + 1.4))
    ax.barh(labels, by["wape"] * 100, color=["#9aa5b1" if s < 0.05 else "#1f6f8b" for s in share])
    for i, v in enumerate(by["wape"] * 100):
        ax.text(v + 0.3, i, f"{v:.1f}%", va="center", fontsize=9)
    ax.set_xlabel("WAPE (lower is better)")
    ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle(f"Which kinds of zones are hardest to forecast? ({label.lower()})", x=0.01, ha="left",
                 fontsize=12, fontweight="bold")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "08_error_by_cluster.png", dpi=150)
    plt.close(fig)


def evaluate(df, key, label, start, end, has_weather):
    train, test = split(df, start, end)
    preds = fit_models(train, test, has_weather)
    actual = test["trips"].to_numpy()
    scores = {name: {"wape": round(wape(actual, p), 4), "mae": round(float(np.abs(actual - p).mean()), 3)}
              for name, p in preds.items()}

    best_name = min(scores, key=lambda n: scores[n]["wape"])
    test["pred_best"] = preds[best_name]
    test["pred_naive"] = preds["Same hour last week"]
    test["window"] = key
    by_cluster = (test.groupby("cluster_name")
                      .apply(lambda g: pd.Series({"wape": wape(g["trips"], g["pred_best"]),
                                                  "trips": int(g["trips"].sum())}), include_groups=False)
                      .reset_index())
    by_cluster["trips"] = by_cluster["trips"].astype(int)
    by_cluster.insert(0, "window", key)

    naive = scores["Same hour last week"]["wape"]
    result = {"label": label, "start": start, "end": end, "train_hours": int(len(train)),
              "test_hours": int(len(test)), "best_model": best_name,
              "improvement_vs_last_week": round(1 - scores[best_name]["wape"] / naive, 4),
              "models": scores}
    return result, test, by_cluster


if __name__ == "__main__":
    df, has_weather = load()
    df = add_features(df)

    results, tests, clusters = {}, [], []
    for key, (label, start, end) in TEST_WINDOWS.items():
        results[key], test, by_cluster = evaluate(df, key, label, start, end, has_weather)
        tests.append(test)
        clusters.append(by_cluster)

    summary = {"zones": int(df["zone_id"].nunique()), "weather_used": bool(has_weather), "windows": results}
    (REPORTS_DIR / "forecast_metrics.json").write_text(json.dumps(summary, indent=2))
    by_cluster = pd.concat(clusters, ignore_index=True)
    by_cluster.to_csv(REPORTS_DIR / "forecast_error_by_cluster.csv", index=False)
    test = pd.concat(tests, ignore_index=True)
    test[["window", "zone_id", "zone_name", "cluster_name", "hour_ts", "trips", "pred_best", "pred_naive"]] \
        .to_parquet(PROCESSED_DIR / "forecasts_test.parquet", index=False)

    # the normal window is the headline, december charts would mostly show christmas
    head = results["normal"]
    chart_models(results)
    chart_week(test[test["window"] == "normal"], head["best_model"], head["label"])
    chart_clusters(by_cluster[by_cluster["window"] == "normal"], head["label"])

    print(f"{summary['zones']} zones, weather used: {has_weather}")
    for key, r in results.items():
        print(f"\n{r['label']}: {r['start']} to {r['end']}")
        for name, s in r["models"].items():
            print(f"  {name:22s} WAPE {s['wape']:.1%}   MAE {s['mae']:.2f} rides/hour")
        print(f"  best: {r['best_model']}, {r['improvement_vs_last_week']:.0%} less error than 'same hour last week'")
        print(by_cluster[by_cluster["window"] == key].drop(columns="window").to_string(index=False))
