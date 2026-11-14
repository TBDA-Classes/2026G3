"""
T31 (F3.3) - Day-ahead forecast of zone 1NE without environmental sensors
==========================================================================
DataPack Energy Forecaster - CeDInt floor 1 (TBDA)

Zone NE has no indoor environmental sensors (Temp, Hum, Lum and Pres are
missing in 100 % of its hours). This script forecasts the two NE load types
(HVAC and Plugs & Sockets) 24 h ahead and tests which PROXY can replace the
missing sensors:

    M0  no environmental data      (calendar + lags of the series itself)
    M1  proxy = zone NW            (north neighbour of NE)
    M2  proxy = adjacent zones     (mean of NW and SE, the two zones that touch NE)
    M3  proxy = whole floor        (mean of NW, SE and SW)
    M4  proxy = adjacent, "ideal"  (same-hour values, as if the drivers were
                                    known in advance: an upper bound, not usable
                                    in operation)
    M5  outdoor weather            (Open-Meteo, only if a weather file is given)
    M6  adjacent proxy + outdoor   (only if a weather file is given)

Baselines: naive day (same hour yesterday) and seasonal naive (same hour last
week), the same baselines as T21.

To check that the proxy idea is sound, the same method is applied to zones that
DO have sensors (SE and NW) in a leave-one-zone-out test: the model is trained
once with the zone's own sensors and once with the proxy built from the other
zones, and the loss of accuracy is measured (sheet LOZO_validation).

Day-ahead rule (no leakage): the forecast for every hour of day D is issued at
00:00 of day D, so only information older than 24 h is used (lags >= 24 h,
rolling windows shifted by 24 h, proxy values of the previous day). Calendar
features and outdoor weather are treated as known in advance (weather as a
"perfect forecast", the usual assumption in the literature).

Split (as in T32): train 2020-06-01 .. 2022-06-30, validation 2022-07-01 ..
2022-12-31 (hyper-parameter choice), test 2023 and test 2025 (never used for
training or tuning). For the test the chosen model is refitted on train +
validation.

Metrics (as in T19 / T38): MAE, RMSE, CV(RMSE) and NMBE, ASHRAE Guideline 14
hourly criteria CV(RMSE) <= 30 % and |NMBE| <= 10 %.
NMBE = sum(y - y_hat) / ((n - 1) * mean(y)) * 100  -> positive = under-forecast.

Model: sklearn HistGradientBoostingRegressor (histogram gradient boosting, the
same family as LightGBM, handles missing values natively; no extra install).

Usage
-----
    python T31_ne_forecast.py --data cedint_f1_hourly_clean.csv
    python T31_ne_forecast.py --data cedint_f1_hourly_clean.csv --weather open_meteo_cedint_hourly.csv
    python T31_ne_forecast.py --data cedint_f1_hourly_clean.csv --download-weather

Outputs (folder T31_outputs/):
    T31_NE_results.xlsx       all tables (see README_T31.md)
    T31_NE_predictions.csv    hourly test predictions of every method
    F_T31_*.png               figures used in the report

Author: Riccardo (TBDA group), with the help of Claude. Date: November 2026.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.request
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.dates as mdates  # noqa: E402
from sklearn.ensemble import HistGradientBoostingRegressor  # noqa: E402
from sklearn.inspection import permutation_importance  # noqa: E402

warnings.filterwarnings("ignore", category=pd.errors.DtypeWarning)

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
SEED = 42
TARGET = "energy_wh_model"
ENV_VARS = ["temp_c", "hum_pct", "lum_lux", "occupancy"]
ZONES_WITH_SENSORS = ["NW", "SE", "SW"]
NE_LOADS = ["HVAC", "Plugs & Sockets"]

# Floor-plan neighbours of NE: NW (north side) and SE (east side).
PROXY_SETS = {
    "NW": ["NW"],
    "ADJ": ["NW", "SE"],
    "FLOOR": ["NW", "SE", "SW"],
}

SPLITS = {
    "train": ("2020-06-01", "2022-07-01"),
    "val": ("2022-07-01", "2023-01-01"),
    "test_2023": ("2023-01-01", "2024-01-01"),
    "test_2025": ("2025-01-01", "2026-01-01"),
}

# CeDInt-UPM, Campus de Montegancedo (Pozuelo de Alarcon, Madrid)
LAT, LON = 40.4057, -3.8389

# Small hyper-parameter grid, chosen on the validation half-year
PARAM_GRID = [
    dict(learning_rate=lr, max_leaf_nodes=leaves, min_samples_leaf=msl)
    for lr in (0.03, 0.08)
    for leaves in (15, 31)
    for msl in (20, 60)
]

# Fallback holiday list (national + Comunidad de Madrid + Madrid city).
# Used only if the dataset has no `is_holiday` column (dataset v0.4 / T24 has it).
HOLIDAYS_MADRID = """
2020-01-01 2020-01-06 2020-04-09 2020-04-10 2020-05-01 2020-05-02 2020-05-15
2020-08-15 2020-10-12 2020-11-02 2020-11-09 2020-12-07 2020-12-08 2020-12-25
2021-01-01 2021-01-06 2021-03-19 2021-04-01 2021-04-02 2021-05-01 2021-05-03
2021-05-15 2021-10-12 2021-11-01 2021-11-09 2021-12-06 2021-12-08 2021-12-25
2022-01-01 2022-01-06 2022-04-14 2022-04-15 2022-05-02 2022-05-16 2022-07-25
2022-08-15 2022-10-12 2022-11-01 2022-11-09 2022-12-06 2022-12-08 2022-12-26
2023-01-06 2023-03-20 2023-04-06 2023-04-07 2023-05-01 2023-05-02 2023-05-15
2023-07-25 2023-08-15 2023-10-12 2023-11-01 2023-11-09 2023-12-06 2023-12-08
2023-12-25 2025-01-01 2025-01-06 2025-04-17 2025-04-18 2025-05-01 2025-05-02
2025-05-15 2025-07-25 2025-08-15 2025-10-12 2025-11-01 2025-11-10 2025-12-06
2025-12-08 2025-12-25
""".split()

# Chart palette (validated categorical order, light surface)
C_SURF, C_INK, C_INK2, C_MUTED, C_GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
PAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
GRAY = "#b5b3ab"


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def style_axes(ax, title=None, ylabel=None):
    ax.set_facecolor(C_SURF)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#c3c2b7")
    ax.tick_params(colors=C_INK2, labelsize=8)
    ax.grid(axis="y", color=C_GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    if title:
        ax.set_title(title, loc="left", fontsize=10, color=C_INK, fontweight="bold")
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=8, color=C_INK2)


def new_fig(nrows=1, ncols=1, size=(9, 4)):
    fig, axes = plt.subplots(nrows, ncols, figsize=size, squeeze=False)
    fig.patch.set_facecolor(C_SURF)
    return fig, axes


def metrics(y, yhat) -> dict:
    y, yhat = np.asarray(y, float), np.asarray(yhat, float)
    m = ~(np.isnan(y) | np.isnan(yhat))
    y, yhat = y[m], yhat[m]
    n = len(y)
    if n < 2 or y.mean() == 0:
        return dict(n=n, MAE=np.nan, RMSE=np.nan, CV_RMSE_pct=np.nan, NMBE_pct=np.nan, ASHRAE14="n/a")
    err = y - yhat
    rmse = float(np.sqrt(np.mean(err ** 2)))
    cv = rmse / y.mean() * 100
    nmbe = err.sum() / ((n - 1) * y.mean()) * 100
    ok = (cv <= 30) and (abs(nmbe) <= 10)
    return dict(n=n, MAE=float(np.abs(err).mean()), RMSE=rmse,
                CV_RMSE_pct=float(cv), NMBE_pct=float(nmbe), ASHRAE14="PASS" if ok else "FAIL")


def in_split(ts: pd.Series, name: str) -> pd.Series:
    a, b = SPLITS[name]
    return (ts >= pd.Timestamp(a)) & (ts < pd.Timestamp(b))


# --------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------
def load_data(path: str):
    cols = ["timestamp_utc", "timestamp_local", "zone", "load_type", TARGET,
            "usable_for_model", "recommendation", "n_devices"] + ENV_VARS
    head = pd.read_csv(path, nrows=2)
    extra = [c for c in ("is_holiday", "is_august_low_use", "flag_covid_2020") if c in head.columns]
    df = pd.read_csv(path, usecols=cols + extra, low_memory=False,
                     parse_dates=["timestamp_utc", "timestamp_local"])
    df.loc[df["usable_for_model"] == 0, TARGET] = np.nan
    print(f"Loaded {len(df):,} rows from {path}; calendar columns found: {extra or 'none (fallback list used)'}")

    # environment: stored once per zone and hour (it is repeated on every load row)
    env = (df[df.zone.isin(ZONES_WITH_SENSORS + ["NE"])]
           .groupby(["timestamp_utc", "zone"])[ENV_VARS].mean().unstack("zone"))
    env.columns = [f"{v}__{z}" for v, z in env.columns]

    # full hourly UTC grid
    grid = pd.date_range(df.timestamp_utc.min(), df.timestamp_utc.max(), freq="h")
    env = env.reindex(grid)

    # local time for calendar features (Europe/Madrid)
    local = (pd.Series(grid, index=grid).dt.tz_localize("UTC")
             .dt.tz_convert("Europe/Madrid").dt.tz_localize(None))
    cal = pd.DataFrame(index=grid)
    cal["hour"] = local.dt.hour.values
    cal["dow"] = local.dt.dayofweek.values
    cal["month"] = local.dt.month.values
    cal["is_weekend"] = (cal["dow"] >= 5).astype(int)
    if "is_holiday" in extra:
        h = df.drop_duplicates("timestamp_utc").set_index("timestamp_utc")["is_holiday"]
        cal["is_holiday"] = h.reindex(grid).fillna(0).astype(int).values
    else:
        hol = set(pd.to_datetime(HOLIDAYS_MADRID).date)
        cal["is_holiday"] = np.array([d in hol for d in local.dt.date]).astype(int)
    cal["is_august"] = (cal["month"] == 8).astype(int)
    cal["is_covid_2020"] = (local.dt.year.values == 2020).astype(int)
    cal["is_workday"] = ((cal.is_weekend == 0) & (cal.is_holiday == 0) & (cal.is_august == 0)).astype(int)

    series = {}
    for (z, lt), g in df.groupby(["zone", "load_type"]):
        series[(z, lt)] = g.set_index("timestamp_utc")[TARGET].reindex(grid)
    return df, env, cal, series, grid


def load_weather(args, grid) -> pd.DataFrame | None:
    """Outdoor weather from an Open-Meteo CSV (columns: time, temperature_2m, ...)."""
    path = args.weather
    if args.download_weather and not path:
        path = str(Path(args.out) / "open_meteo_cedint_hourly.csv")
        if not os.path.exists(path):
            url = ("https://archive-api.open-meteo.com/v1/archive?"
                   f"latitude={LAT}&longitude={LON}&start_date={grid.min():%Y-%m-%d}"
                   f"&end_date={grid.max():%Y-%m-%d}&hourly=temperature_2m,relative_humidity_2m,"
                   "shortwave_radiation&timezone=UTC")
            try:
                print("Downloading Open-Meteo weather ...")
                with urllib.request.urlopen(url, timeout=60) as r:
                    js = json.load(r)
                pd.DataFrame(js["hourly"]).to_csv(path, index=False)
            except Exception as e:  # noqa: BLE001
                print(f"  weather download failed ({e}); M5/M6 skipped")
                return None
    if not path or not os.path.exists(path):
        return None
    w = pd.read_csv(path)
    tcol = [c for c in w.columns if c.lower() in ("time", "timestamp", "timestamp_utc", "date")][0]
    w[tcol] = pd.to_datetime(w[tcol])
    w = w.set_index(tcol).sort_index()
    w = w[~w.index.duplicated()].reindex(grid)
    tcol2 = [c for c in w.columns if "temp" in c.lower()][0]
    out = pd.DataFrame(index=grid)
    out["out_temp"] = w[tcol2]
    out["out_hdh"] = (18 - out.out_temp).clip(lower=0)   # heating degree-hours, base 18 C
    out["out_cdh"] = (out.out_temp - 24).clip(lower=0)   # cooling degree-hours, base 24 C
    for lag in (3, 6):                                   # delayed HVAC response (T26: 0-6 h)
        out[f"out_temp_lag{lag}"] = out.out_temp.shift(lag)
    for c in w.columns:
        if "humid" in c.lower():
            out["out_hum"] = w[c]
        if "radiation" in c.lower():
            out["out_rad"] = w[c]
    print(f"Weather loaded from {path}: {out.out_temp.notna().mean():.0%} of hours")
    return out


# --------------------------------------------------------------------------
# Features
# --------------------------------------------------------------------------
def proxy_frame(env: pd.DataFrame, zones: list[str]) -> pd.DataFrame:
    """Hour-by-hour mean of the environmental variables of the given zones."""
    p = pd.DataFrame(index=env.index)
    for v in ENV_VARS:
        cols = [f"{v}__{z}" for z in zones if f"{v}__{z}" in env.columns]
        p[v] = env[cols].mean(axis=1)
    return p


def build_features(y: pd.Series, cal: pd.DataFrame, proxy: pd.DataFrame | None = None,
                   ideal: bool = False, weather: pd.DataFrame | None = None) -> pd.DataFrame:
    X = cal.copy()
    # lags of the target (all >= 24 h: valid for a forecast issued at 00:00)
    for lag in (24, 48, 72, 168, 336):
        X[f"lag{lag}"] = y.shift(lag)
    X["prevday_mean"] = y.rolling(24, min_periods=12).mean().shift(24)
    X["prevday_max"] = y.rolling(24, min_periods=12).max().shift(24)
    X["prevweek_mean"] = y.rolling(168, min_periods=84).mean().shift(24)
    if proxy is not None:
        for v in ENV_VARS:
            if ideal:  # same hour: the driver is assumed known (upper bound)
                X[f"px_{v}"] = proxy[v]
                X[f"px_{v}_day_mean"] = proxy[v].rolling(24, min_periods=12, center=True).mean()
            else:      # operational: only yesterday's proxy is known at 00:00
                X[f"px_{v}_lag24"] = proxy[v].shift(24)
                X[f"px_{v}_prevday_mean"] = proxy[v].rolling(24, min_periods=12).mean().shift(24)
    if weather is not None:
        X = X.join(weather)
    return X


# --------------------------------------------------------------------------
# Modelling
# --------------------------------------------------------------------------
def fit_hgb(X, y, params, loss="absolute_error"):
    # absolute_error (median) loss: robust to the rare HVAC spikes and to the
    # sudden regime changes of Plugs & Sockets; with loss=squared_error the
    # model learnt large "changes" from a few extreme hours and lost to the
    # naive baselines (tested, see report section 4.1).
    m = HistGradientBoostingRegressor(loss=loss, max_iter=500, l2_regularization=1.0,
                                      random_state=SEED, early_stopping=False, **params)
    m.fit(X, y)
    return m


def run_scenario(y: pd.Series, X: pd.DataFrame, eval_mask_extra: pd.Series, residual: bool = True):
    """Tune on validation, refit on train+val, predict both test periods.

    residual=True (persistence-anchored model): the model learns the CHANGE with
    respect to the same hour of the previous day, y - lag24, and the forecast is
    lag24 + predicted change. The CeDInt series are dominated by persistence
    (stable base loads with sudden regime changes), and a tree model that
    predicts the level directly tends to smooth those regimes away. Hours with
    no lag24 fall back to a direct (level) model.
    """
    ts = pd.Series(X.index, index=X.index)
    ok = y.notna()
    tr, va = ok & in_split(ts, "train"), ok & in_split(ts, "val")
    anchor = X["lag24"] if residual else pd.Series(0.0, index=X.index)
    has_a = anchor.notna()
    target = y - anchor.fillna(0)

    def fit_pair(mask, p):
        if not residual:  # plain level model with squared error (reference M0d)
            m = fit_hgb(X[mask], y[mask], p, loss="squared_error")
            return m, m
        m_res = fit_hgb(X[mask & has_a], target[mask & has_a], p)
        m_dir = fit_hgb(X[mask], y[mask], p)
        return m_res, m_dir

    def predict(models, mask):
        m_res, m_dir = models
        out = pd.Series(np.nan, index=X.index)
        a = mask & has_a
        out[a] = m_res.predict(X[a]) + anchor[a].values
        b = mask & ~has_a
        if b.any():
            out[b] = m_dir.predict(X[b])
        return out

    best, best_rmse = None, np.inf
    for p in PARAM_GRID:
        r = metrics(y[va & eval_mask_extra], predict(fit_pair(tr, p), va & eval_mask_extra)[va & eval_mask_extra])["RMSE"]
        if r < best_rmse:
            best, best_rmse = p, r
    m_val = fit_pair(tr, best)
    pred = predict(m_val, in_split(ts, "val"))
    m_final = fit_pair(tr | va, best)
    for t in ("test_2023", "test_2025"):
        msk = in_split(ts, t)
        if msk.any():
            pred[msk] = predict(m_final, msk)[msk]
    return pred, best, m_val


def evaluate(y, preds: dict, common: pd.Series, extra_cols: dict) -> list[dict]:
    ts = pd.Series(y.index, index=y.index)
    rows = []
    for period in ("val", "test_2023", "test_2025"):
        msk = in_split(ts, period) & common
        for name, p in preds.items():
            r = dict(extra_cols, period=period, method=name)
            r.update(metrics(y[msk], p[msk]))
            # daily totals (local day is close enough: UTC day used)
            yd = y[msk].resample("D").sum(min_count=20)
            pdly = p[msk].resample("D").sum(min_count=20)
            md = metrics(yd, pdly)
            r["daily_CV_RMSE_pct"], r["daily_NMBE_pct"] = md["CV_RMSE_pct"], md["NMBE_pct"]
            rows.append(r)
    return rows


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="cedint_f1_hourly_clean.csv",
                    help="clean hourly dataset (csv or csv.gz) from T12")
    ap.add_argument("--weather", default=None, help="optional Open-Meteo hourly CSV (UTC)")
    ap.add_argument("--download-weather", action="store_true",
                    help="download Open-Meteo archive weather (needs internet)")
    ap.add_argument("--out", default="T31_outputs")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(exist_ok=True, parents=True)
    np.random.seed(SEED)

    df, env, cal, series, grid = load_data(args.data)
    weather = load_weather(args, grid)
    ts = pd.Series(grid, index=grid)

    # ---------------- 1. Data availability and proxy similarity -------------
    avail_rows = []
    for z in ["NE"] + ZONES_WITH_SENSORS:
        r = dict(zone=z)
        for v in ENV_VARS:
            c = f"{v}__{z}"
            r[f"{v}_valid_pct"] = round(env[c].notna().mean() * 100, 1) if c in env else 0.0
        avail_rows.append(r)
    availability = pd.DataFrame(avail_rows)

    sim_rows = []
    zs = ZONES_WITH_SENSORS
    for v in ENV_VARS:
        for i, a in enumerate(zs):
            for b in zs[i + 1:]:
                s = env[[f"{v}__{a}", f"{v}__{b}"]].dropna()
                sim_rows.append(dict(variable=v, zone_a=a, zone_b=b, n_hours=len(s),
                                     pearson_r=round(s.corr().iloc[0, 1], 3),
                                     mean_abs_diff=round((s.iloc[:, 0] - s.iloc[:, 1]).abs().mean(), 2)))
    similarity = pd.DataFrame(sim_rows)

    # NE loads vs proxy drivers (same hour), to see what the proxies can explain
    drv_rows = []
    for lt in NE_LOADS:
        y = series[("NE", lt)]
        for pname, zones in PROXY_SETS.items():
            p = proxy_frame(env, zones)
            for v in ENV_VARS:
                s = pd.concat([y, p[v]], axis=1).dropna()
                drv_rows.append(dict(load_type=lt, proxy=pname, variable=v, n_hours=len(s),
                                     pearson_r=round(s.corr().iloc[0, 1], 3),
                                     spearman_r=round(s.corr("spearman").iloc[0, 1], 3)))
        if weather is not None:
            s = pd.concat([y, weather.out_temp], axis=1).dropna()
            drv_rows.append(dict(load_type=lt, proxy="OUTDOOR", variable="out_temp", n_hours=len(s),
                                 pearson_r=round(s.corr().iloc[0, 1], 3),
                                 spearman_r=round(s.corr("spearman").iloc[0, 1], 3)))
    drivers = pd.DataFrame(drv_rows)

    # NE series description per split
    desc_rows = []
    for lt in NE_LOADS:
        y = series[("NE", lt)]
        for sp in SPLITS:
            s = y[in_split(ts, sp)]
            desc_rows.append(dict(load_type=lt, split=sp, hours=len(s), valid_hours=int(s.notna().sum()),
                                  mean_wh=round(s.mean(), 2), median_wh=round(s.median(), 2),
                                  p99_wh=round(s.quantile(.99), 2), max_wh=round(s.max(), 2)))
    ne_desc = pd.DataFrame(desc_rows)

    # ---------------- 2. NE forecasts -------------------------------------
    scenarios = {"M0d_no_env_direct": dict(proxy=None, residual=False),
                 "M0_no_env": dict(proxy=None),
                 "M1_proxy_NW": dict(proxy="NW"),
                 "M2_proxy_adjacent": dict(proxy="ADJ"),
                 "M3_proxy_floor": dict(proxy="FLOOR"),
                 "M4_proxy_adjacent_ideal": dict(proxy="ADJ", ideal=True)}
    if weather is not None:
        scenarios["M5_outdoor"] = dict(proxy=None, weather=True)
        scenarios["M6_adjacent_plus_outdoor"] = dict(proxy="ADJ", weather=True)

    all_rows, params_rows, pred_frames, imp_rows, models_val = [], [], [], [], {}
    for lt in NE_LOADS:
        y = series[("NE", lt)]
        preds = {"B_naive_day": y.shift(24), "B_seasonal_naive_week": y.shift(168)}
        common = y.notna() & y.shift(168).notna() & y.shift(24).notna()
        Xs = {}
        for name, sc in scenarios.items():
            prox = proxy_frame(env, PROXY_SETS[sc["proxy"]]) if sc.get("proxy") else None
            X = build_features(y, cal, prox, ideal=sc.get("ideal", False),
                               weather=weather if sc.get("weather") else None)
            Xs[name] = X
            print(f"  NE {lt:16s} {name:28s} features={X.shape[1]}")
            p, best, m_val = run_scenario(y, X, common, residual=sc.get("residual", True))
            preds[name] = p
            models_val[(lt, name)] = m_val
            params_rows.append(dict(load_type=lt, scenario=name, n_features=X.shape[1], **best))
        all_rows += evaluate(y, preds, common, dict(zone="NE", load_type=lt))
        pf = pd.DataFrame(preds)
        pf.insert(0, "actual", y)
        pf.insert(0, "load_type", lt)
        pf = pf[in_split(ts, "val") | in_split(ts, "test_2023") | in_split(ts, "test_2025")]
        pred_frames.append(pf)

        # permutation importance (validation) of the operational adjacent proxy model
        for name in ("M2_proxy_adjacent",) + (("M6_adjacent_plus_outdoor",) if weather is not None else ()):
            X = Xs[name]
            msk = in_split(ts, "val") & common
            msk = msk & X["lag24"].notna()
            # importance for the residual model (target = y - lag24)
            pi = permutation_importance(models_val[(lt, name)][0], X[msk], (y - X["lag24"])[msk], n_repeats=5,
                                        random_state=SEED, scoring="neg_root_mean_squared_error")
            imp_rows += [dict(load_type=lt, scenario=name, feature=f,
                              rmse_increase_wh=round(pi.importances_mean[i], 4),
                              std=round(pi.importances_std[i], 4))
                         for i, f in enumerate(X.columns)]

    results = pd.DataFrame(all_rows)
    params = pd.DataFrame(params_rows)
    importance = (pd.DataFrame(imp_rows)
                  .sort_values(["load_type", "scenario", "rmse_increase_wh"], ascending=[True, True, False]))
    predictions = pd.concat(pred_frames)

    # NE HVAC spikes: how much of the error comes from a handful of hours
    yH = series[("NE", "HVAC")]
    thr = 10 * yH[in_split(ts, "train")].median()
    pH = predictions[predictions.load_type == "HVAC"]
    spike_rows = []
    for per in ("val", "test_2023", "test_2025"):
        w = pH[in_split(pd.Series(pH.index, index=pH.index), per)].dropna(subset=["actual", "B_seasonal_naive_week", "B_naive_day"])
        sp = w.actual > thr
        for meth in ("B_naive_day", "M2_proxy_adjacent"):
            se = (w.actual - w[meth]) ** 2
            m_ns = metrics(w.actual[~sp], w[meth][~sp])
            spike_rows.append(dict(period=per, method=meth, spike_threshold_wh=round(thr, 2),
                                   hours=len(w), spike_hours=int(sp.sum()),
                                   spike_share_of_energy_pct=round(w.actual[sp].sum() / w.actual.sum() * 100, 1),
                                   spike_share_of_squared_error_pct=round(se[sp].sum() / se.sum() * 100, 1),
                                   CV_RMSE_without_spikes_pct=round(m_ns["CV_RMSE_pct"], 2),
                                   NMBE_without_spikes_pct=round(m_ns["NMBE_pct"], 2),
                                   ASHRAE14_without_spikes=m_ns["ASHRAE14"]))
    spikes = pd.DataFrame(spike_rows)
    predictions.index.name = "timestamp_utc"

    # ---------------- 3. Leave-one-zone-out validation of the proxy -------
    lozo_rows = []
    for z in ("SE", "NW"):
        others = [o for o in ZONES_WITH_SENSORS if o != z]
        for lt in NE_LOADS:
            if (z, lt) not in series:
                continue
            y = series[(z, lt)]
            common = y.notna() & y.shift(168).notna() & y.shift(24).notna()
            variants = {"no_env": None,
                        "own_sensors": proxy_frame(env, [z]),
                        f"proxy_{'+'.join(others)}": proxy_frame(env, others)}
            preds = {"B_seasonal_naive_week": y.shift(168)}
            for vname, prox in variants.items():
                X = build_features(y, cal, prox)
                print(f"  LOZO {z} {lt:16s} {vname}")
                preds[vname], _, _ = run_scenario(y, X, common)
            lozo_rows += evaluate(y, preds, common, dict(zone=z, load_type=lt))
    lozo = pd.DataFrame(lozo_rows)

    # ---------------- 4. Experiment-log rows (format of T20) --------------
    log_rows = []
    today = pd.Timestamp.today().strftime("%d/%m/%Y")
    for i, r in results[results.period.str.startswith("test")].reset_index(drop=True).iterrows():
        log_rows.append({
            "ID": f"T31-{i + 1:02d}", "date": today, "author": "Riccardo",
            "series": f"1NE {r.load_type}", "features": r.method,
            "model": "baseline" if r.method.startswith("B_") else ("HistGradientBoosting (level, squared error)" if r.method.startswith("M0d") else "HistGradientBoosting (change vs lag24, absolute error)"),
            "train period": "2020-06-01 to 2022-12-31 (tuned on 2022-H2)",
            "test period": r.period.replace("test_", ""),
            "MAE": round(r.MAE, 3), "RMSE": round(r.RMSE, 3), "CV(RMSE)": round(r.CV_RMSE_pct, 2),
            "NMBE": round(r.NMBE_pct, 2), "notes": f"ASHRAE14 {r.ASHRAE14}; n={r.n}"})
    log = pd.DataFrame(log_rows)

    # ---------------- 5. Save tables --------------------------------------
    xlsx = out / "T31_NE_results.xlsx"
    readme = pd.DataFrame({"sheet": [
        "Env_availability", "Proxy_similarity", "NE_series", "NE_vs_proxy_drivers", "NE_results",
        "NE_best_params", "Feature_importance", "LOZO_validation", "NE_HVAC_spikes", "Experiment_log_rows"],
        "content": [
        "Share of hours with valid indoor environmental readings per zone (NE = 0 %)",
        "Correlation and mean absolute difference of each environmental variable between zones with sensors",
        "Description of the NE target series per split",
        "Same-hour correlation of NE loads with each proxy driver",
        "MAE, RMSE, CV(RMSE), NMBE, ASHRAE 14 and daily metrics for every method and period",
        "Hyper-parameters chosen on validation for each scenario",
        "Permutation importance (validation RMSE increase) of the adjacent-proxy model",
        "Leave-one-zone-out test: zones SE and NW with own sensors vs proxy vs no environment",
        "NE HVAC spike hours (> 10 x training median): share of energy and of squared error, metrics without them",
        "Rows to paste into experiment_log.xlsx (T20 format)"]})
    with pd.ExcelWriter(xlsx, engine="openpyxl") as w:
        readme.to_excel(w, sheet_name="README", index=False)
        availability.to_excel(w, sheet_name="Env_availability", index=False)
        similarity.to_excel(w, sheet_name="Proxy_similarity", index=False)
        ne_desc.to_excel(w, sheet_name="NE_series", index=False)
        drivers.to_excel(w, sheet_name="NE_vs_proxy_drivers", index=False)
        results.round(3).to_excel(w, sheet_name="NE_results", index=False)
        params.to_excel(w, sheet_name="NE_best_params", index=False)
        importance.to_excel(w, sheet_name="Feature_importance", index=False)
        lozo.round(3).to_excel(w, sheet_name="LOZO_validation", index=False)
        spikes.to_excel(w, sheet_name="NE_HVAC_spikes", index=False)
        log.to_excel(w, sheet_name="Experiment_log_rows", index=False)
        for ws in w.book.worksheets:
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = min(
                    45, max(10, max(len(str(c.value or "")) for c in col) + 2))
            ws.freeze_panes = "A2"
    predictions.round(3).to_csv(out / "T31_NE_predictions.csv")
    print(f"Saved {xlsx}")

    # ---------------- 6. Figures ------------------------------------------
    make_figures(out, env, series, results, lozo, importance, predictions, cal)
    print("Done.")


def make_figures(out, env, series, results, lozo, importance, predictions, cal):
    # F1: indoor temperature of the zones with sensors (daily mean) -> proxy rationale
    fig, axes = new_fig(1, 1, (10, 3.6))
    ax = axes[0, 0]
    for i, z in enumerate(ZONES_WITH_SENSORS):
        s = env[f"temp_c__{z}"].resample("D").mean()
        ax.plot(s.index, s.values, color=PAL[i], lw=1.2, label=z)
    style_axes(ax, "Indoor temperature, daily mean, zones with sensors (NE has none)", "°C")
    ax.legend(frameon=False, fontsize=8, ncol=3, loc="upper left")
    fig.tight_layout()
    fig.savefig(out / "F_T31_1_indoor_temp_zones.png", dpi=150)
    plt.close(fig)

    # F2: NE profiles by hour, workdays vs non-workdays
    fig, axes = new_fig(1, 2, (10, 3.6))
    for k, lt in enumerate(NE_LOADS):
        ax = axes[0, k]
        y = series[("NE", lt)]
        d = pd.DataFrame({"y": y, "hour": cal.hour, "wd": cal.is_workday})
        d = d[d.index < "2023-01-01"]
        for j, (flag, lab) in enumerate([(1, "Working days"), (0, "Weekends, holidays, August")]):
            prof = d[d.wd == flag].groupby("hour").y.median()
            ax.plot(prof.index, prof.values, color=PAL[j], lw=2, marker="o", ms=3, label=lab)
        style_axes(ax, f"NE {lt}: median energy by hour (2020-22)", "Wh per hour")
        ax.set_xlabel("hour (local)", fontsize=8, color=C_INK2)
    h, lab = axes[0, 0].get_legend_handles_labels()
    fig.legend(h, lab, loc="upper center", ncol=2, frameon=False, fontsize=8)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(out / "F_T31_2_NE_profiles.png", dpi=150)
    plt.close(fig)

    # F3: CV(RMSE) per method on the two test periods
    order = [m for m in results.method.unique()]
    fig, axes = new_fig(1, 2, (11, 4.2))
    for k, lt in enumerate(NE_LOADS):
        ax = axes[0, k]
        r = results[(results.load_type == lt) & results.period.str.startswith("test")]
        x = np.arange(len(order))
        for j, per in enumerate(["test_2023", "test_2025"]):
            vals = [r[(r.method == m) & (r.period == per)].CV_RMSE_pct.mean() for m in order]
            ax.bar(x + (j - 0.5) * 0.38, vals, width=0.36, color=PAL[j], label=per.replace("test_", "test "),
                   edgecolor=C_SURF, linewidth=1)
        ax.axhline(30, color=C_INK2, lw=1, ls="--")
        if lt == "HVAC":  # 2023 is dominated by 11 spike hours: log scale keeps 2025 readable
            ax.set_yscale("log")
        ax.text(len(order) - 0.5, 31, "ASHRAE 14 limit 30 %", ha="right", va="bottom", fontsize=7, color=C_INK2)
        ax.set_xticks(x)
        ax.set_xticklabels([m.replace("_", " ") for m in order], rotation=40, ha="right", fontsize=7)
        style_axes(ax, f"NE {lt}: CV(RMSE) by method" + (" (log scale)" if lt == "HVAC" else ""), "CV(RMSE) %")
    h, lab = axes[0, 0].get_legend_handles_labels()
    fig.legend(h, lab, loc="upper center", ncol=2, frameon=False, fontsize=8)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(out / "F_T31_3_NE_cvrmse_by_method.png", dpi=150)
    plt.close(fig)

    # F4: forecast vs actual, one week in each test period
    fig, axes = new_fig(2, 2, (11, 6))
    for k, lt in enumerate(NE_LOADS):
        p = predictions[predictions.load_type == lt]
        for j, (a, b) in enumerate([("2023-01-16", "2023-01-23"), ("2025-09-15", "2025-09-22")]):
            ax = axes[k, j]
            w = p.loc[a:b]
            ax.plot(w.index, w.actual, color=C_INK, lw=1.6, label="actual")
            ax.plot(w.index, w["B_seasonal_naive_week"], color=GRAY, lw=1.2, label="seasonal naive (week)")
            ax.plot(w.index, w["M2_proxy_adjacent"], color=PAL[0], lw=1.4, label="M2 adjacent proxy")
            style_axes(ax, f"NE {lt}, week from {a}", "Wh per hour")
            ax.tick_params(axis="x", labelsize=7)
            ax.xaxis.set_major_locator(mdates.DayLocator())
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    h, lab = axes[0, 0].get_legend_handles_labels()
    fig.legend(h, lab, loc="upper center", ncol=3, frameon=False, fontsize=8)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(out / "F_T31_4_NE_forecast_vs_actual.png", dpi=150)
    plt.close(fig)

    # F5: leave-one-zone-out
    lz = lozo[lozo.period.str.startswith("test")]
    combos = [(z, lt) for z in ("SE", "NW") for lt in NE_LOADS if ((lz.zone == z) & (lz.load_type == lt)).any()]
    fig, axes = new_fig(1, len(combos), (3.2 * len(combos), 3.8))
    for k, (z, lt) in enumerate(combos):
        ax = axes[0, k]
        r = lz[(lz.zone == z) & (lz.load_type == lt)]
        meths = list(r.method.unique())
        x = np.arange(len(meths))
        for j, per in enumerate(["test_2023", "test_2025"]):
            vals = [r[(r.method == m) & (r.period == per)].CV_RMSE_pct.mean() for m in meths]
            ax.bar(x + (j - 0.5) * 0.38, vals, width=0.36, color=PAL[j], edgecolor=C_SURF,
                   label=per.replace("test_", "test "))
        ax.axhline(30, color=C_INK2, lw=1, ls="--")
        ax.set_xticks(x)
        ax.set_xticklabels([m.replace("B_seasonal_naive_week", "naive week").replace("_", " ") for m in meths],
                           rotation=35, ha="right", fontsize=7)
        style_axes(ax, f"{z} {lt}", "CV(RMSE) %" if k == 0 else None)
        if k == 0:
            ax.legend(frameon=False, fontsize=7)
    fig.suptitle("Leave-one-zone-out: own sensors vs proxy from other zones", x=0.01, ha="left",
                 fontsize=10, fontweight="bold", color=C_INK)
    fig.tight_layout()
    fig.savefig(out / "F_T31_5_LOZO_validation.png", dpi=150)
    plt.close(fig)

    # F6: permutation importance, top 12
    fig, axes = new_fig(1, 2, (11, 4.4))
    for k, lt in enumerate(NE_LOADS):
        ax = axes[0, k]
        im = importance[(importance.load_type == lt) & (importance.scenario == "M2_proxy_adjacent")].head(12)[::-1]
        cols = [PAL[1] if f.startswith("px_") else PAL[0] for f in im.feature]
        ax.barh(im.feature, im.rmse_increase_wh, color=cols, edgecolor=C_SURF)
        style_axes(ax, f"NE {lt}: permutation importance (M2)", None)
        ax.set_xlabel("RMSE increase when shuffled (Wh)", fontsize=8, color=C_INK2)
        ax.grid(axis="x", color=C_GRID, linewidth=0.6)
        ax.grid(axis="y", visible=False)
        ax.tick_params(axis="y", labelsize=7)
    from matplotlib.patches import Patch
    axes[0, 1].legend(handles=[Patch(color=PAL[0], label="calendar / own lags"),
                               Patch(color=PAL[1], label="proxy environment")],
                      frameon=False, fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(out / "F_T31_6_NE_feature_importance.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
