# =============================================================================
# CeDInt floor 1 - Random Forest day-ahead energy model (GENERAL / PARAMETERISED)
# TBDA DataPack - works on Google Colab. Change only the USER SETTINGS below.
#
# What it does
#   1. Loads the model-ready dataset (include_train / include_eval columns).
#   2. Builds day-ahead-safe features (calendar, lag_24h/lag_168h, indoor sensors,
#      optional outdoor weather from Open-Meteo).
#   3. Trains two variants: with 2020 (include_train) and without 2020
#      (include_train_no2020), tunes each on the VALIDATION period
#      and keeps the better one (validation CV(RMSE)).
#   4. Scores validation, test_2023 and test_2025 (only include_eval = 1 hours),
#      prints the ASHRAE Guideline 14 table and compares with the naive benchmark.
#   5. Saves predictions (CSV in the team format + Excel), metrics, SHAP plots and
#      time-series comparison plots.
# =============================================================================

# %% ---------------------------- 1. USER SETTINGS ----------------------------
ZONE = "NW"                  # "NW", "NE", "SW" or "SE"
LOAD_TYPE = "HVAC"           # "HVAC", "Plugs & Sockets", "Lighting" (also "Emerg. Lighting", "RACK")

DATA_PATH = None             # None = auto-detect (see locate_data); or e.g. "/content/drive/MyDrive/....csv.gz"
OUTPUT_DIR = "rf_outputs"    # all result files are written here

# "team"              : methodology feature list (calendar + lags + indoor sensors + outdoor weather).
# "strict_day_ahead"  : drops the indoor sensors measured in the SAME hour (temp_c, hum_pct,
#                       lum_lux, occupancy), because they are not known when a day-ahead
#                       forecast is issued at midnight. Use it to check for optimistic scores.
FEATURE_MODE = "team"

USE_OUTDOOR_WEATHER = True   # download outdoor temperature + solar radiation (Open-Meteo); skipped if offline
TUNE = True                  # small grid search on the validation period
RUN_SHAP = True              # SHAP explanation (falls back to permutation importance if SHAP is missing)
DOWNLOAD_FROM_COLAB = False  # True = trigger a browser download of every result file at the end
SEED = 42

# %% ---------------------------- 2. SETUP -------------------------------------
import os, re, sys, subprocess, itertools, warnings
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestRegressor
from sklearn.inspection import permutation_importance

warnings.filterwarnings("ignore", category=FutureWarning)

if RUN_SHAP:
    try:
        import shap
    except ImportError:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "shap"])
            import shap
        except Exception as exc:                       # no internet / install failed
            print(f"[warning] SHAP could not be installed ({exc}); permutation importance will be used.")
            shap = None
else:
    shap = None

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Agreed team definitions ------------------------------------------------------
EVAL_SPLITS = ["validation", "test_2023", "test_2025"]
ASHRAE_CV_MAX, ASHRAE_NMBE_MAX = 30.0, 10.0           # ASHRAE Guideline 14, hourly data
VARIANTS = {                                           # model name -> training-flag column
    "random_forest": "include_train",
    "random_forest_no2020": "include_train_no2020",
}
CALENDAR = ["hour_local", "dayofweek_local", "month_local", "is_weekend", "is_holiday", "is_august_low_use"]
LAGS = ["lag_24h", "lag_168h"]                         # known at forecast time (day-ahead, issued at 00:00)
INDOOR = ["temp_c", "hum_pct", "lum_lux", "occupancy"]  # zone sensors (empty for NE)
OUTDOOR = ["temp_out_c", "temp_out_lag1", "temp_out_lag2", "dh_cool_out", "dh_heat_out", "solar_wm2"]
# flag_covid_2020 is NOT used as a feature: it is always 0 in validation/test and constant in the
# "no 2020" variant, so it cannot help a forecast.

COOL_BASE_C, HEAT_BASE_C = 22.0, 18.0                  # degree-hour thresholds (outdoor temperature)
SITE_LAT, SITE_LON = 40.404, -3.839                    # CeDInt site (coordinates from the P9 notebook)
WEATHER_CACHE = "open_meteo_hourly_cache.csv"

PARAM_GRID = {"max_depth": [12, None], "min_samples_leaf": [3, 10, 30], "max_features": [0.5, 1.0]}
DEFAULT_PARAMS = {"max_depth": None, "min_samples_leaf": 5, "max_features": 0.5}
TUNE_TREES, FINAL_TREES = 100, 300
SHAP_SAMPLE = 1000

LOAD_ALIASES = {
    "hvac": "HVAC", "lighting": "Lighting", "light": "Lighting", "lights": "Lighting",
    "plugs & sockets": "Plugs & Sockets", "plugs & socket": "Plugs & Sockets",
    "plugs and sockets": "Plugs & Sockets", "plugs": "Plugs & Sockets", "sockets": "Plugs & Sockets",
    "emerg. lighting": "Emerg. Lighting", "emergency lighting": "Emerg. Lighting", "rack": "RACK",
}


# %% ---------------------------- 3. HELPER FUNCTIONS --------------------------
def normalise_load_type(name):
    key = re.sub(r"\s+", " ", str(name).strip().lower())
    return LOAD_ALIASES.get(key, name)


def locate_data(path=None):
    """Find the model-ready file; on Colab offer an upload dialog if nothing is found."""
    names = [path] if path else []
    names += ["cedint_f1_model_ready.csv.gz", "T32_cedint_f1_model_ready.csv.gz",
              "cedint_f1_model_ready.csv", "T32_cedint_f1_model_ready.csv"]
    for n in names:
        if n and os.path.exists(n):
            return n
    try:
        from google.colab import files
        print("Model-ready file not found. Please upload it (cedint_f1_model_ready.csv[.gz]) ...")
        return next(iter(files.upload()))
    except ImportError:
        raise FileNotFoundError("Model-ready file not found. Set DATA_PATH at the top of the script.")


def load_outdoor_weather():
    """Hourly outdoor temperature and solar radiation (UTC) from Open-Meteo, cached on disk.
    Returns None when the download is impossible. Note: archived (observed) weather is used as a
    stand-in for a weather FORECAST, so scores can be slightly optimistic."""
    if os.path.exists(WEATHER_CACHE):
        w = pd.read_csv(WEATHER_CACHE, parse_dates=["timestamp_utc"])
    else:
        try:
            import requests
            r = requests.get("https://archive-api.open-meteo.com/v1/archive", timeout=90, params={
                "latitude": SITE_LAT, "longitude": SITE_LON,
                "start_date": "2020-04-01", "end_date": "2025-10-14",
                "hourly": "temperature_2m,shortwave_radiation", "timezone": "UTC"})
            r.raise_for_status()
            h = r.json()["hourly"]
            w = pd.DataFrame({"timestamp_utc": pd.to_datetime(h["time"]),
                              "temp_out_c": h["temperature_2m"], "solar_wm2": h["shortwave_radiation"]})
            w.to_csv(WEATHER_CACHE, index=False)
        except Exception as exc:
            print(f"[warning] Outdoor weather not available ({exc}). Continuing without it.")
            return None
    w = w.sort_values("timestamp_utc").reset_index(drop=True)
    w["timestamp_utc"] = w["timestamp_utc"].astype("datetime64[ns]")
    # the weather table is a continuous hourly grid, so shifting rows = shifting hours
    w["temp_out_lag1"] = w["temp_out_c"].shift(1)
    w["temp_out_lag2"] = w["temp_out_c"].shift(2)
    w["dh_cool_out"] = (w["temp_out_c"] - COOL_BASE_C).clip(lower=0)
    w["dh_heat_out"] = (HEAT_BASE_C - w["temp_out_c"]).clip(lower=0)
    return w[["timestamp_utc"] + OUTDOOR]


def ashrae_metrics(y_true, y_pred):
    """MAE, RMSE, CV(RMSE) %, NMBE % and ASHRAE 14 pass/fail (hourly: CV(RMSE) <= 30 %, |NMBE| <= 10 %).
    NMBE = sum(y_true - y_pred) / (n * mean(y_true)) * 100  -> positive = model under-predicts."""
    y_true, y_pred = np.asarray(y_true, float), np.asarray(y_pred, float)
    n = len(y_true)
    if n == 0:
        return None
    err = y_true - y_pred
    mean_y = y_true.mean()
    rmse = float(np.sqrt(np.mean(err ** 2)))
    cv = rmse / mean_y * 100 if mean_y > 0 else np.nan
    nmbe = err.sum() / (n * mean_y) * 100 if mean_y > 0 else np.nan
    ok_cv, ok_nmbe = bool(cv <= ASHRAE_CV_MAX), bool(abs(nmbe) <= ASHRAE_NMBE_MAX)
    return {"n": n, "mean_y_Wh": mean_y, "MAE": float(np.abs(err).mean()), "RMSE": rmse,
            "CV_RMSE_%": cv, "NMBE_%": nmbe, "CV_ok": ok_cv, "NMBE_ok": ok_nmbe,
            "ASHRAE_pass": ok_cv and ok_nmbe}


def candidate_features():
    feats = CALENDAR + LAGS
    if FEATURE_MODE == "team":
        feats += INDOOR
    elif FEATURE_MODE != "strict_day_ahead":
        raise ValueError("FEATURE_MODE must be 'team' or 'strict_day_ahead'")
    return feats


def fit_variant(series, model_name, train_flag, feats_all):
    """Select features, build the training set (include_train rows only), tune on validation,
    fit the final model and return everything needed for scoring and explanation."""
    tr = series[series[train_flag] == 1]
    val = series[(series["split"] == "validation") & (series["include_eval"] == 1)]

    # keep only features that carry information in THIS training set (e.g. NE has no indoor sensors)
    feats = [f for f in feats_all if f in tr.columns and tr[f].notna().any() and tr[f].nunique() > 1]
    dropped = sorted(set(feats_all) - set(feats))
    if dropped:
        print(f"  [{model_name}] features dropped (empty/constant in training data): {dropped}")

    # Training may be stricter than testing: drop training hours with an empty feature.
    n_before = len(tr)
    tr = tr.dropna(subset=feats + ["energy_wh_model"])
    print(f"  [{model_name}] training rows: {len(tr):,} (of {n_before:,} with {train_flag} = 1; "
          f"{n_before - len(tr):,} dropped for empty features)")
    if len(tr) < 500:
        raise RuntimeError(f"Too few training rows ({len(tr)}) for {ZONE} / {LOAD_TYPE}.")

    medians = tr[feats].median()                       # used to fill empty features in eval rows
    X_tr, y_tr = tr[feats], tr["energy_wh_model"]
    X_val = val[feats].fillna(medians)

    best_params, tuning_log, best_cv = dict(DEFAULT_PARAMS), [], np.inf
    if TUNE and len(val) > 0:
        keys = list(PARAM_GRID)
        for combo in itertools.product(*PARAM_GRID.values()):
            p = dict(zip(keys, combo))
            rf = RandomForestRegressor(n_estimators=TUNE_TREES, random_state=SEED, n_jobs=-1, **p)
            rf.fit(X_tr, y_tr)
            m = ashrae_metrics(val["energy_wh_model"], rf.predict(X_val))
            tuning_log.append({"model": model_name, **{k: str(v) for k, v in p.items()},
                               "val_CV_RMSE_%": m["CV_RMSE_%"], "val_NMBE_%": m["NMBE_%"]})
            if m["CV_RMSE_%"] < best_cv:
                best_cv, best_params = m["CV_RMSE_%"], p
    rf = RandomForestRegressor(n_estimators=FINAL_TREES, random_state=SEED, n_jobs=-1, **best_params)
    rf.fit(X_tr, y_tr)
    val_m = ashrae_metrics(val["energy_wh_model"], rf.predict(X_val)) if len(val) else None
    return {"name": model_name, "model": rf, "features": feats, "medians": medians, "params": best_params,
            "val_cv": val_m["CV_RMSE_%"] if val_m else np.nan, "tuning": tuning_log, "n_train": len(tr)}


def predict_eval(series, fitted):
    ev = series[(series["split"].isin(EVAL_SPLITS)) & (series["include_eval"] == 1)].copy()
    X = ev[fitted["features"]].fillna(fitted["medians"])
    ev["y_pred"] = fitted["model"].predict(X)
    ev["model"] = fitted["name"]
    return ev, X


def hourly_view(df_split, col):
    """Series on a continuous hourly UTC grid (gaps = NaN so lines are not drawn across them)."""
    s = df_split.set_index("timestamp_utc")[col]
    s = s[~s.index.duplicated()]
    return s.reindex(pd.date_range(s.index.min(), s.index.max(), freq="h"))


def best_window(index, days=14):
    daily = pd.Series(1, index=index).resample("D").sum()
    roll = daily.rolling(days).sum()
    if roll.notna().any():
        end = roll.idxmax()
        return end - pd.Timedelta(days=days - 1), end + pd.Timedelta(days=1)
    return index.min(), index.max()


def plot_predictions(pred, title, path_full, path_zoom):
    splits = [s for s in EVAL_SPLITS if (pred["split"] == s).any()]
    for path, zoom in [(path_full, False), (path_zoom, True)]:
        fig, axes = plt.subplots(len(splits), 1, figsize=(15, 3.6 * len(splits)), squeeze=False)
        for ax, sp in zip(axes[:, 0], splits):
            d = pred[pred["split"] == sp]
            yt, yp = hourly_view(d, "y_true"), hourly_view(d, "y_pred")
            if zoom:
                a, b = best_window(d["timestamp_utc"])
                yt, yp = yt.loc[a:b], yp.loc[a:b]
            ax.plot(yt.index, yt.values, color="black", lw=1.1, label="Measured")
            ax.plot(yp.index, yp.values, color="#1c5cab", lw=1.1, alpha=0.9, label="Random Forest")
            ax.set_title(f"{title} - {sp}" + (" (14-day zoom)" if zoom else ""), fontweight="bold")
            ax.set_ylabel("Energy (Wh per hour)")
            ax.grid(True, ls="--", alpha=0.4)
            ax.legend(loc="upper right")
        axes[-1, 0].set_xlabel("Time (UTC)")
        fig.tight_layout()
        fig.savefig(path, dpi=200)
        plt.close(fig)


def explain(fitted, X_eval, prefix, title):
    """SHAP beeswarm + bar plot (or permutation importance if SHAP is unavailable).
    Returns a feature-importance table."""
    Xs = X_eval.sample(min(SHAP_SAMPLE, len(X_eval)), random_state=SEED)
    model = fitted["model"]
    imp = None
    if shap is not None:
        try:
            sv = shap.TreeExplainer(model).shap_values(Xs, check_additivity=False)
            shap.summary_plot(sv, Xs, show=False, max_display=15, plot_size=(10, 7))
            plt.title(f"SHAP - what drives {title}", fontweight="bold")
            plt.tight_layout()
            plt.savefig(f"{prefix}_SHAP_summary.png", dpi=200, bbox_inches="tight")
            plt.close()
            imp = pd.DataFrame({"feature": Xs.columns, "importance": np.abs(sv).mean(axis=0)})
            label = "Mean |SHAP value| (Wh per hour)"
        except Exception as exc:                        # e.g. SHAP / numpy version mismatch
            plt.close("all")
            print(f"[warning] SHAP failed ({exc}); using permutation importance instead.")
    if imp is None:
        r = permutation_importance(model, Xs, model.predict(Xs), n_repeats=5, random_state=SEED, n_jobs=-1)
        imp = pd.DataFrame({"feature": Xs.columns, "importance": r.importances_mean})
        label = "Permutation importance (increase in squared error)"
    imp = imp.sort_values("importance", ascending=False).reset_index(drop=True)
    top = imp.head(15).iloc[::-1]
    plt.figure(figsize=(9, 6))
    plt.barh(top["feature"], top["importance"], color="#1c5cab")
    plt.xlabel(label)
    plt.title(f"Feature importance - {title}", fontweight="bold")
    plt.grid(True, axis="x", ls="--", alpha=0.4)
    plt.tight_layout()
    plt.savefig(f"{prefix}_feature_importance.png", dpi=200)
    plt.close()
    return imp


# %% ---------------------------- 4. LOAD AND CHECK DATA -----------------------
LOAD_TYPE = normalise_load_type(LOAD_TYPE)
tag = f"{ZONE}_{re.sub(r'[^A-Za-z0-9]+', '_', LOAD_TYPE).strip('_')}"
prefix = os.path.join(OUTPUT_DIR, tag + "_RandomForest")
title = f"{ZONE} {LOAD_TYPE}"

path = locate_data(DATA_PATH)
print("Loading", path)
df = pd.read_csv(path, parse_dates=["timestamp_utc", "timestamp_local"], low_memory=False)
df["timestamp_utc"] = df["timestamp_utc"].astype("datetime64[ns]")

series = df[(df["zone"] == ZONE) & (df["load_type"] == LOAD_TYPE)].sort_values("timestamp_utc").reset_index(drop=True)
if series.empty:
    raise ValueError(f"No data for zone={ZONE!r}, load_type={LOAD_TYPE!r}. "
                     f"Zones: {sorted(df['zone'].unique())}; load types: {sorted(df['load_type'].unique())}")
scope = series["model_scope"].iloc[0]
print(f"Series {title}: {len(series):,} rows | scope = {scope} | recommendation = {series['recommendation'].iloc[0]}")
if scope not in ("priority", "secondary (constant)"):
    raise ValueError(f"{title} is '{scope}' in the team methodology and is not modelled per hour.")
print("Rows per split:")
print(series.groupby("split").agg(hours=("split", "size"), include_train=("include_train", "sum"),
                                  include_eval=("include_eval", "sum")).to_string())

# %% ---------------------------- 5. FEATURES ----------------------------------
weather = load_outdoor_weather() if USE_OUTDOOR_WEATHER else None
if weather is not None:
    series = series.merge(weather, on="timestamp_utc", how="left")      # join on UTC (no DST ambiguity)
feats_all = candidate_features() + (OUTDOOR if weather is not None else [])
print(f"\nFeature mode: {FEATURE_MODE} | candidate features ({len(feats_all)}): {feats_all}")
if series["include_train"].sum() == 0:
    raise ValueError("No include_train rows for this series.")

# %% ---------------------------- 6. TRAIN, TUNE, SELECT -----------------------
print("\nTraining variants (tuning on the validation period) ...")
fitted = {name: fit_variant(series, name, flag, feats_all) for name, flag in VARIANTS.items()}
best_name = min(fitted, key=lambda k: np.nan_to_num(fitted[k]["val_cv"], nan=1e9))
selection = pd.DataFrame([{"model": n, "train_rows": f["n_train"], "n_features": len(f["features"]),
                           "best_params": str(f["params"]), "validation_CV_RMSE_%": f["val_cv"],
                           "selected": n == best_name} for n, f in fitted.items()])
print("\nVariant selection (lower validation CV(RMSE) wins):")
print(selection.round(2).to_string(index=False))

# %% ---------------------------- 7. SCORE: ASHRAE + BENCHMARK -----------------------
all_pred, rows, X_eval_by_model = [], [], {}
for name, f in fitted.items():
    ev, X_ev = predict_eval(series, f)
    X_eval_by_model[name] = X_ev
    all_pred.append(ev)
    for sp in EVAL_SPLITS:
        d = ev[ev["split"] == sp]
        m = ashrae_metrics(d["energy_wh_model"], d["y_pred"])
        if m:
            rows.append({"zone": ZONE, "load_type": LOAD_TYPE, "model": name, "split": sp,
                         "selected": name == best_name, **m})
pred_all = pd.concat(all_pred, ignore_index=True)
metrics = pd.DataFrame(rows)
print("\n=== ASHRAE Guideline 14 (hourly): CV(RMSE) <= 30 % and |NMBE| <= 10 % ===")
cols = ["model", "split", "n", "MAE", "RMSE", "CV_RMSE_%", "NMBE_%", "ASHRAE_pass"]
print(metrics[cols].round(2).to_string(index=False))

# Naive benchmark: same hour yesterday / same hour last week, on the same hours as the model
bench_rows = []
best_ev = pred_all[pred_all["model"] == best_name]
for sp in EVAL_SPLITS:
    d = best_ev[(best_ev["split"] == sp)].dropna(subset=["lag_24h", "lag_168h"])
    if d.empty:
        continue
    y = d["energy_wh_model"]
    rf_cv = ashrae_metrics(y, d["y_pred"])["CV_RMSE_%"]
    n24 = ashrae_metrics(y, d["lag_24h"])["CV_RMSE_%"]
    n168 = ashrae_metrics(y, d["lag_168h"])["CV_RMSE_%"]
    bench_rows.append({"model": best_name, "split": sp, "n_common_hours": len(d), "RF_CV_RMSE_%": rf_cv,
                       "naive_yesterday_CV_RMSE_%": n24, "naive_last_week_CV_RMSE_%": n168,
                       "beats_benchmark": bool(rf_cv < min(n24, n168))})
bench = pd.DataFrame(bench_rows)
print(f"\n=== Benchmark comparison for the selected model ({best_name}) ===")
print(bench.round(2).to_string(index=False) if not bench.empty else "no common hours")

# %% ---------------------------- 8. SAVE PREDICTIONS ---------------------------------
team = pred_all.rename(columns={"energy_wh_model": "y_true"})
team["zone"], team["load_type"] = ZONE, LOAD_TYPE
team_cols = ["timestamp_utc", "zone", "load_type", "model", "split", "y_true", "y_pred"]
team[team_cols].to_csv(f"{prefix}_predictions.csv", index=False)          # format agreed with Team B

pred_xlsx = team[team_cols + ["timestamp_local", "series_caution", "level_shift_2025", "energy_source"]]
importance = pd.DataFrame()
# %% ---------------------------- 9. EXPLAIN (SHAP) ------------------------------------
if RUN_SHAP:
    print("\nComputing feature importance for the selected model ...")
    importance = explain(fitted[best_name], X_eval_by_model[best_name], prefix, f"{title} ({best_name})")
    print(importance.head(10).round(3).to_string(index=False))

# %% ---------------------------- 10. PLOTS + EXCEL -----------------------------------
plot_predictions(team[team["model"] == best_name], f"{title} ({best_name})",
                 f"{prefix}_comparison_full.png", f"{prefix}_comparison_zoom.png")

with pd.ExcelWriter(f"{prefix}_results.xlsx", engine="openpyxl") as xw:
    metrics.to_excel(xw, sheet_name="ASHRAE_table", index=False)
    bench.to_excel(xw, sheet_name="Benchmark", index=False)
    selection.to_excel(xw, sheet_name="Variant_selection", index=False)
    pd.DataFrame([r for f in fitted.values() for r in f["tuning"]]).to_excel(xw, sheet_name="Tuning_log", index=False)
    if not importance.empty:
        importance.to_excel(xw, sheet_name="Feature_importance", index=False)
    pred_xlsx.to_excel(xw, sheet_name="Predictions", index=False)
    pd.DataFrame({"setting": ["ZONE", "LOAD_TYPE", "FEATURE_MODE", "USE_OUTDOOR_WEATHER", "weather_used",
                              "selected_model", "features_selected_model", "seed"],
                  "value": [ZONE, LOAD_TYPE, FEATURE_MODE, USE_OUTDOOR_WEATHER, weather is not None,
                            best_name, ", ".join(fitted[best_name]["features"]), SEED]}
                 ).to_excel(xw, sheet_name="Settings", index=False)

print("\nFiles written to", os.path.abspath(OUTPUT_DIR))
for fn in sorted(os.listdir(OUTPUT_DIR)):
    if fn.startswith(tag):
        print("  -", fn)
if DOWNLOAD_FROM_COLAB and "google.colab" in sys.modules:
    from google.colab import files
    for fn in sorted(os.listdir(OUTPUT_DIR)):
        if fn.startswith(tag):
            files.download(os.path.join(OUTPUT_DIR, fn))
