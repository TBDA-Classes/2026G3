# =============================================================================
# CeDInt floor 1 - CatBoost day-ahead energy model (GENERAL / PARAMETERISED)
# TBDA DataPack - works on Google Colab. Change only the USER SETTINGS below.
#
# Colab install cell (run once):
#     !pip install -q catboost pandas numpy matplotlib openpyxl
#
# What it does
#   1. Loads the model-ready dataset (include_train / include_eval columns).
#   2. Builds day-ahead-safe features: CATEGORICAL calendar features (hour, weekday, month, weekend,
#      holiday, August) declared explicitly to CatBoost, plus numeric features (lag_24h, lag_168h,
#      indoor sensors, optional outdoor weather). Empty numeric values stay empty: CatBoost handles
#      them natively, so no row of the official train / eval sets is dropped or imputed.
#   3. Trains two variants - with 2020 (include_train) and without 2020 (include_train_no2020) -
#      tunes each on the VALIDATION period and keeps the one with the lower validation CV(RMSE).
#   4. Scores validation, test_2023 and test_2025 (only include_eval = 1 hours), prints the
#      ASHRAE Guideline 14 table and compares with the naive benchmark.
#   5. Saves predictions (CSV in the team format + Excel), metrics, native CatBoost SHAP plots and
#      time-series comparison plots.
# =============================================================================

# %% ---------------------------- 1. USER SETTINGS ----------------------------
ZONE = "NW"                  # "NW", "NE", "SW" or "SE"
LOAD_TYPE = "HVAC"           # "HVAC", "Plugs & Sockets", "Lighting" (also "Emerg. Lighting", "RACK")

DATA_PATH = None             # None = auto-detect (upload dialog on Colab); or e.g. "/content/drive/MyDrive/x.csv.gz"
OUTPUT_DIR = "catboost_outputs"

# "team"              : methodology features (calendar + lags + indoor sensors + outdoor weather).
# "strict_day_ahead"  : drops the indoor sensors measured in the SAME hour (temp_c, hum_pct, lum_lux,
#                       occupancy), which are not known when a day-ahead forecast is issued at midnight.
FEATURE_MODE = "team"

USE_OUTDOOR_WEATHER = True   # download outdoor temperature + solar radiation (Open-Meteo); skipped if offline
TUNE = True                  # small grid search on the validation period
RUN_SHAP = True              # native CatBoost SHAP plots
DOWNLOAD_FROM_COLAB = False  # True = trigger a browser download of every result file at the end
SEED = 42

# %% ---------------------------- 2. SETUP -------------------------------------
import os, re, sys, subprocess, itertools, warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore", category=FutureWarning)
try:
    from catboost import CatBoostRegressor, Pool
except ImportError:                                       # not installed: install and import
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "catboost"])
    from catboost import CatBoostRegressor, Pool

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Agreed team definitions ------------------------------------------------------
EVAL_SPLITS = ["validation", "test_2023", "test_2025"]
ASHRAE_CV_MAX, ASHRAE_NMBE_MAX = 30.0, 10.0           # ASHRAE Guideline 14, hourly data
VARIANTS = {                                           # model name -> training-flag column
    "catboost": "include_train",
    "catboost_no2020": "include_train_no2020",
}
# Categorical features: passed to CatBoost explicitly (cat_features) and encoded with its ordered target
# statistics. They are integers without empty values, as CatBoost requires.
CAT_FEATURES = ["hour_local", "dayofweek_local", "month_local", "is_weekend", "is_holiday", "is_august_low_use"]
LAGS = ["lag_24h", "lag_168h"]                         # known at forecast time (day-ahead, issued at 00:00)
INDOOR = ["temp_c", "hum_pct", "lum_lux", "occupancy"]  # zone sensors (empty for NE)
OUTDOOR = ["temp_out_c", "temp_out_lag1", "temp_out_lag2", "dh_cool_out", "dh_heat_out", "solar_wm2"]
# flag_covid_2020 is NOT a feature: it is always 0 in validation/test and constant in the "no 2020" variant.

COOL_BASE_C, HEAT_BASE_C = 22.0, 18.0                  # degree-hour thresholds (outdoor temperature)
SITE_LAT, SITE_LON = 40.404, -3.839                    # CeDInt site (coordinates from the P9 notebook)
WEATHER_CACHE = "open_meteo_hourly_cache.csv"

PARAM_GRID = {"depth": [4, 6, 8], "l2_leaf_reg": [1, 5, 20]}   # tuned on validation
LEARNING_RATE, MAX_ITERATIONS, EARLY_STOP = 0.05, 1500, 100
SHAP_SAMPLE = 3000

LOAD_ALIASES = {
    "hvac": "HVAC", "lighting": "Lighting", "light": "Lighting", "lights": "Lighting",
    "plugs & sockets": "Plugs & Sockets", "plugs & socket": "Plugs & Sockets",
    "plugs and sockets": "Plugs & Sockets", "plugs": "Plugs & Sockets", "sockets": "Plugs & Sockets",
    "emerg. lighting": "Emerg. Lighting", "emergency lighting": "Emerg. Lighting", "rack": "RACK",
}


# %% ---------------------------- 3. HELPER FUNCTIONS --------------------------
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
    Returns None if the download is impossible. Observed weather stands in for a weather FORECAST,
    so scores can be slightly optimistic."""
    if os.path.exists(WEATHER_CACHE):
        w = pd.read_csv(WEATHER_CACHE, parse_dates=["timestamp_utc"])
    else:
        try:
            import requests
            r = requests.get("https://archive-api.open-meteo.com/v1/archive", timeout=90, params={
                "latitude": SITE_LAT, "longitude": SITE_LON, "start_date": "2020-04-01", "end_date": "2025-10-14",
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
    w["temp_out_lag1"] = w["temp_out_c"].shift(1)          # continuous hourly grid: shifting rows = shifting hours
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
    err, mean_y = y_true - y_pred, y_true.mean()
    rmse = float(np.sqrt(np.mean(err ** 2)))
    cv = rmse / mean_y * 100 if mean_y > 0 else np.nan
    nmbe = err.sum() / (n * mean_y) * 100 if mean_y > 0 else np.nan
    ok_cv, ok_nmbe = bool(cv <= ASHRAE_CV_MAX), bool(abs(nmbe) <= ASHRAE_NMBE_MAX)
    return {"n": n, "mean_y_Wh": mean_y, "MAE": float(np.abs(err).mean()), "RMSE": rmse,
            "CV_RMSE_%": cv, "NMBE_%": nmbe, "CV_ok": ok_cv, "NMBE_ok": ok_nmbe, "ASHRAE_pass": ok_cv and ok_nmbe}


def make_pool(frame, feats, label=True):
    """CatBoost Pool with the categorical features declared explicitly (integers, no empty values)."""
    X = frame[feats].copy()
    cats = [c for c in CAT_FEATURES if c in feats]
    X[cats] = X[cats].astype(int)
    return Pool(X, label=frame["energy_wh_model"] if label else None, cat_features=cats)


def new_model(params):
    return CatBoostRegressor(
        iterations=MAX_ITERATIONS, learning_rate=LEARNING_RATE, loss_function="RMSE", eval_metric="RMSE",
        early_stopping_rounds=EARLY_STOP, has_time=True,       # rows are sorted by time: keep that order
        random_seed=SEED, verbose=False, allow_writing_files=False, thread_count=-1, **params)


def fit_variant(series, name, train_flag, feats_all):
    """Train one variant (rows with train_flag = 1), tune on validation, return model + info."""
    tr = series[series[train_flag] == 1]
    val = series[(series["split"] == "validation") & (series["include_eval"] == 1)]
    # keep numeric features that carry information in THIS training set (e.g. NE has no indoor sensors)
    feats = [f for f in feats_all if f in CAT_FEATURES or (tr[f].notna().any() and tr[f].nunique() > 1)]
    dropped = sorted(set(feats_all) - set(feats))
    if dropped:
        print(f"  [{name}] features dropped (empty/constant in training data): {dropped}")
    print(f"  [{name}] training rows: {len(tr):,} ({train_flag} = 1)")
    if len(tr) < 500:
        raise RuntimeError(f"Too few training rows ({len(tr)}) for {ZONE} / {LOAD_TYPE}.")
    train_pool = make_pool(tr, feats)
    val_pool = make_pool(val, feats) if len(val) else None

    best, tuning_log = None, []
    combos = [dict(zip(PARAM_GRID, c)) for c in itertools.product(*PARAM_GRID.values())] if TUNE else [{"depth": 6, "l2_leaf_reg": 3}]
    for p in combos:
        model = new_model(p)
        if val_pool is not None:
            model.fit(train_pool, eval_set=val_pool, use_best_model=True)     # early stopping on validation
            m = ashrae_metrics(val["energy_wh_model"], model.predict(val_pool))
            cv, nmbe = m["CV_RMSE_%"], m["NMBE_%"]
        else:
            model.fit(train_pool)
            cv, nmbe = np.nan, np.nan
        tuning_log.append({"model": name, **p, "best_iteration": model.get_best_iteration() if val_pool is not None else MAX_ITERATIONS,
                           "val_CV_RMSE_%": cv, "val_NMBE_%": nmbe})
        if best is None or (np.isfinite(cv) and cv < best["val_cv"]):
            best = {"model": model, "params": p, "val_cv": cv}
    return {"name": name, "model": best["model"], "features": feats, "params": best["params"],
            "val_cv": best["val_cv"], "tuning": tuning_log, "n_train": len(tr)}


def predict_eval(series, fitted):
    ev = series[series["split"].isin(EVAL_SPLITS) & (series["include_eval"] == 1)].copy()
    ev["y_pred"] = np.clip(fitted["model"].predict(make_pool(ev, fitted["features"], label=False)), 0, None)
    ev["model"] = fitted["name"]
    return ev


def hourly_view(d, col):
    """Series on a continuous hourly UTC grid (gaps = NaN so lines are not drawn across them)."""
    s = d.set_index("timestamp_utc")[col]
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
            ax.plot(yp.index, yp.values, color="#d9822b", lw=1.1, alpha=0.95, label="CatBoost")
            ax.set_title(f"{title} - {sp}" + (" (14-day zoom)" if zoom else ""), fontweight="bold")
            ax.set_ylabel("Energy (Wh per hour)")
            ax.grid(True, ls="--", alpha=0.4)
            ax.legend(loc="upper right")
        axes[-1, 0].set_xlabel("Time (UTC)")
        fig.tight_layout()
        fig.savefig(path, dpi=200)
        plt.close(fig)


def plot_daily_profile(pred, title, path):
    """Average 24-hour profile, measured vs predicted, per evaluation period."""
    splits = [s for s in EVAL_SPLITS if (pred["split"] == s).any()]
    fig, axes = plt.subplots(1, len(splits), figsize=(5.2 * len(splits), 4), squeeze=False, sharey=True)
    for ax, sp in zip(axes[0], splits):
        g = pred[pred["split"] == sp].groupby("hour_local")[["y_true", "y_pred"]].mean()
        ax.plot(g.index, g["y_true"], color="black", marker="o", ms=3, label="Measured")
        ax.plot(g.index, g["y_pred"], color="#d9822b", marker="o", ms=3, label="CatBoost")
        ax.set_title(sp, fontweight="bold")
        ax.set_xlabel("Hour of day (local)")
        ax.grid(True, ls="--", alpha=0.4)
    axes[0, 0].set_ylabel("Mean energy (Wh per hour)")
    axes[0, 0].legend()
    fig.suptitle(f"{title} - mean daily profile", fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def explain_shap(fitted, ev_rows, prefix, title):
    """Native CatBoost SHAP values (model.get_feature_importance(type='ShapValues')) on a sample of the
    evaluation hours. Saves a beeswarm summary plot, a mean-|SHAP| bar plot and SHAP-by-category plots
    (what each hour / weekday / month adds to the forecast).
    Returns (importance table, average model output)."""
    model, feats = fitted["model"], fitted["features"]
    sample = ev_rows.sample(min(SHAP_SAMPLE, len(ev_rows)), random_state=SEED)
    X = sample[feats].copy()
    cats = [c for c in CAT_FEATURES if c in feats]
    X[cats] = X[cats].astype(int)
    sv = model.get_feature_importance(Pool(X, cat_features=cats), type="ShapValues")
    base_value, sv = float(np.mean(sv[:, -1])), np.asarray(sv)[:, :-1]      # last column = expected value
    mean_abs = np.abs(sv).mean(axis=0)
    order = np.argsort(mean_abs)[::-1]

    # (a) beeswarm: one dot per hour; x = effect on the forecast (Wh), colour = feature value (blue low, red high)
    top = order[:15][::-1]
    fig, ax = plt.subplots(figsize=(10, 0.55 * len(top) + 2))
    rng = np.random.default_rng(SEED)
    for row, j in enumerate(top):
        v = X.iloc[:, j].to_numpy(float)
        ok = np.isfinite(v)
        y = row + rng.uniform(-0.32, 0.32, len(v))
        if ok.any():
            lo, hi = np.nanpercentile(v[ok], [5, 95])
            c = np.clip((v - lo) / (hi - lo), 0, 1) if hi > lo else np.full(len(v), 0.5)
            sc = ax.scatter(sv[ok, j], y[ok], c=c[ok], cmap="coolwarm", vmin=0, vmax=1, s=7, alpha=0.65, lw=0)
        if (~ok).any():
            ax.scatter(sv[~ok, j], y[~ok], color="lightgrey", s=7, alpha=0.65, lw=0)   # empty value
    ax.set_yticks(range(len(top)))
    ax.set_yticklabels([feats[j] for j in top])
    ax.axvline(0, color="grey", lw=0.8)
    ax.set_xlabel("SHAP value = effect on the forecast (Wh per hour)")
    ax.set_title(f"SHAP summary (native CatBoost) - what drives {title}", fontweight="bold")
    cb = fig.colorbar(sc, ax=ax, pad=0.01, ticks=[0, 1])
    cb.ax.set_yticklabels(["low", "high"])
    cb.set_label("Feature value")
    fig.tight_layout()
    fig.savefig(f"{prefix}_SHAP_summary.png", dpi=200)
    plt.close(fig)

    # (b) global importance: mean |SHAP|
    fig, ax = plt.subplots(figsize=(9, 6))
    t = order[:15][::-1]
    ax.barh([feats[j] for j in t], mean_abs[t], color="#d9822b")
    ax.set_xlabel("Mean |SHAP value| (Wh per hour)")
    ax.set_title(f"Feature importance - {title} ({fitted['name']})", fontweight="bold")
    ax.grid(True, axis="x", ls="--", alpha=0.4)
    fig.tight_layout()
    fig.savefig(f"{prefix}_SHAP_importance.png", dpi=200)
    plt.close(fig)

    # (c) SHAP by calendar category: average contribution of each hour / weekday / month
    shown = [c for c in ["hour_local", "dayofweek_local", "month_local"] if c in feats]
    if shown:
        fig, axes = plt.subplots(1, len(shown), figsize=(5.5 * len(shown), 4), squeeze=False)
        for ax, c in zip(axes[0], shown):
            j = feats.index(c)
            g = pd.DataFrame({"cat": X[c].to_numpy(), "shap": sv[:, j]}).groupby("cat")["shap"].agg(["mean", "std"])
            ax.bar(g.index, g["mean"], yerr=g["std"].fillna(0), color="#d9822b", alpha=0.85, ecolor="grey")
            ax.axhline(0, color="black", lw=0.8)
            ax.set_xlabel(c)
            ax.set_ylabel("Mean SHAP (Wh per hour)")
            ax.grid(True, axis="y", ls="--", alpha=0.4)
        fig.suptitle(f"{title} - contribution of calendar features (bars = mean, whiskers = std)", fontweight="bold")
        fig.tight_layout()
        fig.savefig(f"{prefix}_SHAP_calendar.png", dpi=200)
        plt.close(fig)

    return pd.DataFrame({"feature": feats, "mean_abs_SHAP_Wh": mean_abs,
                         "catboost_importance": model.get_feature_importance()}).sort_values(
        "mean_abs_SHAP_Wh", ascending=False).reset_index(drop=True), base_value


# %% ---------------------------- 4. LOAD AND CHECK DATA -----------------------
LOAD_TYPE = LOAD_ALIASES.get(re.sub(r"\s+", " ", LOAD_TYPE.strip().lower()), LOAD_TYPE)
tag = f"{ZONE}_{re.sub(r'[^A-Za-z0-9]+', '_', LOAD_TYPE).strip('_')}"
prefix = os.path.join(OUTPUT_DIR, tag + "_CatBoost")
title = f"{ZONE} {LOAD_TYPE}"

path = locate_data(DATA_PATH)
print("Loading", path)
df = pd.read_csv(path, parse_dates=["timestamp_utc", "timestamp_local"], low_memory=False)
df["timestamp_utc"] = df["timestamp_utc"].astype("datetime64[ns]")

series = df[(df["zone"] == ZONE) & (df["load_type"] == LOAD_TYPE)].sort_values("timestamp_utc").reset_index(drop=True)
if series.empty:
    raise ValueError(f"No data for zone={ZONE!r}, load_type={LOAD_TYPE!r}. Zones: {sorted(df['zone'].unique())}; "
                     f"load types: {sorted(df['load_type'].unique())}")
scope = series["model_scope"].iloc[0]
print(f"Series {title}: {len(series):,} rows | scope = {scope} | recommendation = {series['recommendation'].iloc[0]}")
if scope not in ("priority", "secondary (constant)"):
    raise ValueError(f"{title} is '{scope}' in the team methodology and is not modelled per hour.")
print(series.groupby("split").agg(hours=("split", "size"), include_train=("include_train", "sum"),
                                  include_eval=("include_eval", "sum")).to_string())

# %% ---------------------------- 5. FEATURES ----------------------------------
weather = load_outdoor_weather() if USE_OUTDOOR_WEATHER else None
if weather is not None:
    series = series.merge(weather, on="timestamp_utc", how="left")      # join on UTC (no DST ambiguity)
if FEATURE_MODE not in ("team", "strict_day_ahead"):
    raise ValueError("FEATURE_MODE must be 'team' or 'strict_day_ahead'")
feats_all = CAT_FEATURES + LAGS + (INDOOR if FEATURE_MODE == "team" else []) + (OUTDOOR if weather is not None else [])
print(f"\nFeature mode: {FEATURE_MODE} | candidate features ({len(feats_all)}): {feats_all}")
print(f"Categorical features: {CAT_FEATURES}")

# %% ---------------------------- 6. TRAIN, TUNE, SELECT -----------------------
print("\nTraining variants (early stopping + grid search on the validation period) ...")
fitted = {n: fit_variant(series, n, flag, feats_all) for n, flag in VARIANTS.items()}
best_name = min(fitted, key=lambda k: np.nan_to_num(fitted[k]["val_cv"], nan=1e9))
selection = pd.DataFrame([{"model": n, "train_rows": f["n_train"], "n_features": len(f["features"]),
                           "best_params": str(f["params"]), "best_iteration": f["model"].get_best_iteration(),
                           "validation_CV_RMSE_%": f["val_cv"], "selected": n == best_name} for n, f in fitted.items()])
print("\nVariant selection (lower validation CV(RMSE) wins):")
print(selection.round(2).to_string(index=False))

# %% ---------------------------- 7. SCORE: ASHRAE + BENCHMARK -----------------------
all_pred, rows = [], []
for name, f in fitted.items():
    ev = predict_eval(series, f)
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

bench_rows = []                                           # naive benchmark: same hour yesterday / last week
best_ev = pred_all[pred_all["model"] == best_name]
for sp in EVAL_SPLITS:
    d = best_ev[best_ev["split"] == sp].dropna(subset=LAGS)
    if d.empty:
        continue
    y = d["energy_wh_model"]
    cv_m, cv_24, cv_168 = (ashrae_metrics(y, d[c])["CV_RMSE_%"] for c in ["y_pred", "lag_24h", "lag_168h"])
    bench_rows.append({"model": best_name, "split": sp, "n_common_hours": len(d), "CatBoost_CV_RMSE_%": cv_m,
                       "naive_yesterday_CV_RMSE_%": cv_24, "naive_last_week_CV_RMSE_%": cv_168,
                       "beats_benchmark": bool(cv_m < min(cv_24, cv_168))})
bench = pd.DataFrame(bench_rows)
print(f"\n=== Benchmark comparison for the selected model ({best_name}) ===")
print(bench.round(2).to_string(index=False) if not bench.empty else "no common hours")

# %% ---------------------------- 8. SAVE PREDICTIONS ---------------------------------
team = pred_all.rename(columns={"energy_wh_model": "y_true"})
team["zone"], team["load_type"] = ZONE, LOAD_TYPE
team_cols = ["timestamp_utc", "zone", "load_type", "model", "split", "y_true", "y_pred"]
team[team_cols].to_csv(f"{prefix}_predictions.csv", index=False)           # format agreed with Team B
pred_xlsx = team[team_cols + ["timestamp_local", "hour_local", "series_caution", "level_shift_2025", "energy_source"]]
fitted[best_name]["model"].save_model(f"{prefix}_{best_name}.cbm")          # reusable for the dashboard

# %% ---------------------------- 9. EXPLAIN (native SHAP) -----------------------------
importance, base_value = pd.DataFrame(), np.nan
if RUN_SHAP:
    print("\nComputing native CatBoost SHAP values for the selected model ...")
    importance, base_value = explain_shap(fitted[best_name], best_ev, prefix, f"{title} ({best_name})")
    print(importance.head(10).round(3).to_string(index=False))

# %% ---------------------------- 10. PLOTS + EXCEL -----------------------------------
best_pred = team[team["model"] == best_name]
plot_predictions(best_pred, f"{title} ({best_name})", f"{prefix}_comparison_full.png", f"{prefix}_comparison_zoom.png")
plot_daily_profile(best_pred, f"{title} ({best_name})", f"{prefix}_daily_profile.png")

with pd.ExcelWriter(f"{prefix}_results.xlsx", engine="openpyxl") as xw:
    metrics.to_excel(xw, sheet_name="ASHRAE_table", index=False)
    bench.to_excel(xw, sheet_name="Benchmark", index=False)
    selection.to_excel(xw, sheet_name="Variant_selection", index=False)
    pd.DataFrame([r for f in fitted.values() for r in f["tuning"]]).to_excel(xw, sheet_name="Tuning_log", index=False)
    if not importance.empty:
        importance.to_excel(xw, sheet_name="Feature_importance", index=False)
    pred_xlsx.to_excel(xw, sheet_name="Predictions", index=False)
    pd.DataFrame({"setting": ["ZONE", "LOAD_TYPE", "FEATURE_MODE", "USE_OUTDOOR_WEATHER", "weather_used",
                              "selected_model", "features_selected_model", "categorical_features", "seed"],
                  "value": [ZONE, LOAD_TYPE, FEATURE_MODE, USE_OUTDOOR_WEATHER, weather is not None, best_name,
                            ", ".join(fitted[best_name]["features"]),
                            ", ".join(c for c in CAT_FEATURES if c in fitted[best_name]["features"]), SEED]}
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
