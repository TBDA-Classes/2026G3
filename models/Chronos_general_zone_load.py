# =============================================================================
# CeDInt floor 1 - Amazon Chronos day-ahead energy forecast (GENERAL / PARAMETERISED)
# TBDA DataPack - Google Colab (GPU recommended: Runtime > Change runtime type > T4 GPU)
#
# Colab install cell (run once; if Colab asks to restart the runtime, restart and run again):
#
#     !pip install -q git+https://github.com/amazon-science/chronos-forecasting.git
#     !pip install -q pandas numpy matplotlib openpyxl
#
#   (stable alternative from PyPI:  !pip install -q chronos-forecasting)
#
# How the day-ahead evaluation works
#   * Chronos is a pretrained, ZERO-SHOT foundation model: nothing is fitted on the CeDInt data.
#     The "training" period (Jun 2020 - Jun 2022) is only used as HISTORICAL CONTEXT.
#   * For every evaluation day, a forecast is issued at local midnight (00:00 Europe/Madrid) using only
#     data BEFORE that moment (the last CONTEXT_HOURS hours) and predicts the next 24 hours.
#   * Scored hours = rows with include_eval = 1 in validation, test_2023 and test_2025 (same hours as
#     every other model of the team, so the scores are comparable).
#   * Context never crosses the 902-day gap: 2025 forecasts only see 2025 history.
#   * Output = median forecast (point forecast) + quantiles 10-90 % (probabilistic forecast).
# =============================================================================

# %% ---------------------------- 1. USER SETTINGS ----------------------------
ZONE = "NW"                  # "NW", "NE", "SW" or "SE"
LOAD_TYPE = "HVAC"           # "HVAC", "Plugs & Sockets", "Lighting" (also "Emerg. Lighting", "RACK")

# Chronos-Bolt sizes: chronos-bolt-tiny / -mini / -small / -base  (base = most accurate; small is
# a good choice on CPU). The original T5 models (amazon/chronos-t5-*) also work but are slower.
MODEL_ID = "amazon/chronos-bolt-base"

CONTEXT_HOURS = 672          # hours of history shown to the model (672 = 4 weeks) if TUNE_CONTEXT = False
TUNE_CONTEXT = True          # pick the best context length on the VALIDATION period
CONTEXT_CANDIDATES = [168, 336, 672, 1344]
MIN_CONTEXT_HOURS = 24       # a day is only forecast if at least this many valid hours of history exist

DATA_PATH = None             # None = auto-detect / upload dialog on Colab
OUTPUT_DIR = "chronos_outputs"
DOWNLOAD_FROM_COLAB = False  # True = trigger a browser download of every result file at the end
BATCH_SIZE = 64
SEED = 42

# %% ---------------------------- 2. SETUP -------------------------------------
import os, re, sys, subprocess, warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore", category=FutureWarning)


def ensure_chronos():
    """Import chronos; if missing, install it (GitHub first, then PyPI)."""
    try:
        import chronos  # noqa: F401
    except ImportError:
        for target in ["git+https://github.com/amazon-science/chronos-forecasting.git", "chronos-forecasting"]:
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", target])
                import chronos  # noqa: F401
                return
            except Exception as exc:
                print(f"[warning] pip install {target} failed: {exc}")
        raise ImportError("chronos-forecasting could not be installed. Run the install cell shown at the top.")


ensure_chronos()
import torch
from chronos import BaseChronosPipeline

torch.manual_seed(SEED)
os.makedirs(OUTPUT_DIR, exist_ok=True)

EVAL_SPLITS = ["validation", "test_2023", "test_2025"]
ASHRAE_CV_MAX, ASHRAE_NMBE_MAX = 30.0, 10.0           # ASHRAE Guideline 14, hourly data
QUANTILES = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]   # levels Chronos-Bolt was trained on
QCOLS = [f"q{int(q * 100):02d}" for q in QUANTILES]
PRED_LEN = 25                # 24 h; 25 only so that the 25-hour local day (October clock change) is covered
TZ = "Europe/Madrid"
INTERVALS = {40: ("q30", "q70"), 60: ("q20", "q80"), 80: ("q10", "q90")}   # central prediction intervals
LOAD_ALIASES = {
    "hvac": "HVAC", "lighting": "Lighting", "light": "Lighting", "lights": "Lighting",
    "plugs & sockets": "Plugs & Sockets", "plugs & socket": "Plugs & Sockets",
    "plugs and sockets": "Plugs & Sockets", "plugs": "Plugs & Sockets", "sockets": "Plugs & Sockets",
    "emerg. lighting": "Emerg. Lighting", "emergency lighting": "Emerg. Lighting", "rack": "RACK",
}


# %% ---------------------------- 3. HELPER FUNCTIONS --------------------------
def locate_data(path=None):
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


def ashrae_metrics(y_true, y_pred):
    """MAE, RMSE, CV(RMSE) % and NMBE % with ASHRAE Guideline 14 pass/fail criteria."""
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


def build_context_store(series):
    """Hourly UTC history per era (hourly 2020-23 / minute 2025), NaN where no trustworthy value exists."""
    usable = (series["include_train"] == 1) | (series["include_eval"] == 1)
    work = series.assign(_v=series["energy_wh_model"].where(usable))
    store = {}
    for era, g in work.groupby("era"):
        g = g.drop_duplicates("timestamp_utc").set_index("timestamp_utc").sort_index()
        grid = pd.date_range(g.index.min(), g.index.max(), freq="h")
        store[era] = (grid[0], g["_v"].reindex(grid).to_numpy(float))
    return store


def forecast_days(pipeline, store, origins, eras, context_hours):
    """Day-ahead forecasts for many origins. Returns an array [n_days, PRED_LEN, n_quantiles]"""
    contexts, keep = [], []
    for i, (origin, era) in enumerate(zip(origins, eras)):
        start_ts, arr = store[era]
        idx = int(round((origin - start_ts) / pd.Timedelta(hours=1)))      # position of the origin in the era
        if idx <= 0:
            continue
        ctx = arr[max(0, idx - context_hours): min(idx, len(arr))]
        if np.isfinite(ctx).sum() < MIN_CONTEXT_HOURS:
            continue
        ctx = ctx[np.argmax(np.isfinite(ctx)):]                              # strip leading NaNs
        contexts.append(torch.tensor(ctx, dtype=torch.float32))
        keep.append(i)
    out = np.full((len(origins), PRED_LEN, len(QUANTILES)), np.nan)
    for b in range(0, len(contexts), BATCH_SIZE):
        # Use positional argument for contexts to support both Chronos-T5 (context=) and Chronos-Bolt (inputs=)
        q, _mean = pipeline.predict_quantiles(contexts[b:b + BATCH_SIZE], PRED_LEN, quantile_levels=QUANTILES)
        out[keep[b:b + BATCH_SIZE]] = q.float().cpu().numpy()
    out = np.sort(np.clip(out, 0, None), axis=-1)             # energy >= 0 and non-crossing quantiles
    return out


def attach_forecasts(ev_rows, days, q_days):
    """Copy the forecast of each row's day / step into the row."""
    day_i = ev_rows["local_day"].map({d: i for i, d in enumerate(days["local_day"])}).to_numpy()
    step = ev_rows["step_h"].to_numpy()
    assert step.max() < PRED_LEN and step.min() >= 0, "unexpected forecast step"
    q_rows = q_days[day_i, step]
    out = ev_rows.copy()
    for j, c in enumerate(QCOLS):
        out[c] = q_rows[:, j]
    out["y_pred"] = out["q50"]                                 # median = point forecast
    return out


def hourly(d, col):
    x = d.set_index("timestamp_utc")[col]
    x = x[~x.index.duplicated()]
    return x.reindex(pd.date_range(x.index.min(), x.index.max(), freq="h"))   # gaps stay NaN


def best_window(index, days=14):
    daily = pd.Series(1, index=index).resample("D").sum()
    roll = daily.rolling(days).sum()
    if roll.notna().any():
        end = roll.idxmax()
        return end - pd.Timedelta(days=days - 1), end + pd.Timedelta(days=1)
    return index.min(), index.max()


# %% ---------------------------- 4. LOAD AND CHECK DATA -----------------------
LOAD_TYPE = LOAD_ALIASES.get(re.sub(r"\blighting\b", "Lighting", LOAD_TYPE.strip().lower()), LOAD_TYPE)
tag = f"{ZONE}_{re.sub(r'[^A-Za-z0-9]+', '_', LOAD_TYPE).strip('_')}"
model_tag = MODEL_ID.split("/")[-1].replace("-", "_")                 # e.g. chronos_bolt_base
MODEL_NAME = model_tag if model_tag.startswith("chronos") else f"chronos_{model_tag}"
prefix = os.path.join(OUTPUT_DIR, f"{tag}_{MODEL_NAME}")
title = f"{ZONE} {LOAD_TYPE}"

path = locate_data(DATA_PATH)
print("Loading", path)
df = pd.read_csv(path, parse_dates=["timestamp_utc", "timestamp_local"], low_memory=False)
df["timestamp_utc"] = df["timestamp_utc"].astype("datetime64[ns]")
df["timestamp_local"] = df["timestamp_local"].astype("datetime64[ns]")
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

# Evaluation rows and their forecast origin (local midnight of the row's local day, expressed in UTC)
ev = series[series["split"].isin(EVAL_SPLITS) & (series["include_eval"] == 1)].copy()
if ev.empty:
    raise ValueError("No include_eval rows for this series.")
ev["local_day"] = ev["timestamp_local"].dt.normalize()
days = ev.drop_duplicates("local_day")[["local_day", "era"]].sort_values("local_day").reset_index(drop=True)
days["origin_utc"] = (pd.DatetimeIndex(days["local_day"]).tz_localize(TZ).tz_convert("UTC").tz_localize(None)
                      .astype("datetime64[ns]"))
ev = ev.merge(days[["local_day", "origin_utc"]], on="local_day", how="left")
ev["step_h"] = ((ev["timestamp_utc"] - ev["origin_utc"]) / pd.Timedelta(hours=1)).round().astype(int)
print(f"\nEvaluation: {len(ev):,} hours on {len(days)} local days")

store = build_context_store(series)

# %% ---------------------------- 5. LOAD CHRONOS --------------------------------
try:
    from google.colab import userdata
    os.environ["HF_TOKEN"] = userdata.get("HF_TOKEN")
except Exception:
    pass

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"\nLoading {MODEL_ID} on {device} ...")
if device == "cpu":
    print("[note] No GPU found. This works but is slower; consider MODEL_ID = 'amazon/chronos-bolt-small'.")
pipeline = BaseChronosPipeline.from_pretrained(
    MODEL_ID, device_map=device, torch_dtype=torch.bfloat16 if device == "cuda" else torch.float32)


def run_eval(context_hours, day_mask=None):
    d = days if day_mask is None else days[day_mask].reset_index(drop=True)
    q = forecast_days(pipeline, store, list(d["origin_utc"]), list(d["era"]), context_hours)
    rows = ev[ev["local_day"].isin(d["local_day"])]
    return attach_forecasts(rows, d, q)


# %% ---------------------------- 6. TUNE THE CONTEXT LENGTH (validation) --------
tuning = []
best_ctx = CONTEXT_HOURS
if TUNE_CONTEXT:
    val_days = set(ev.loc[ev["split"] == "validation", "local_day"])
    vmask = days["local_day"].isin(val_days).to_numpy()
    print(f"\nTuning the context length on {int(vmask.sum())} validation days ...")
    for c in CONTEXT_CANDIDATES:
        r = run_eval(c, vmask)
        r = r[(r["split"] == "validation")].dropna(subset=["y_pred"])
        m = ashrae_metrics(r["energy_wh_model"], r["y_pred"])
        tuning.append({"context_hours": c, "validation_CV_RMSE_%": m["CV_RMSE_%"], "validation_NMBE_%": m["NMBE_%"],
                       "hours_scored": m["n"]})
        print(f"  context {c:5d} h -> validation CV(RMSE) = {m['CV_RMSE_%']:.1f} %")
    best_ctx = min(tuning, key=lambda t: t["validation_CV_RMSE_%"])["context_hours"]
print(f"Context length used: {best_ctx} h")

# %% ---------------------------- 7. FINAL FORECASTS FOR ALL EVAL PERIODS --------
print("\nForecasting all evaluation days ...")
res = run_eval(best_ctx)
n_missing = int(res["y_pred"].isna().sum())
if n_missing:
    print(f"[note] {n_missing} evaluation hours have no forecast (less than {MIN_CONTEXT_HOURS} h of valid history "
          f"before the day started, e.g. the first day of 2025). They are not scored.")
pred = res.dropna(subset=["y_pred"]).rename(columns={"energy_wh_model": "y_true"}).copy()
pred["zone"], pred["load_type"], pred["model"], pred["context_hours"] = ZONE, LOAD_TYPE, MODEL_NAME, best_ctx

# %% ---------------------------- 8. ASHRAE METRICS + PROBABILISTIC CHECK --------
rows = []
for sp in EVAL_SPLITS:
    d = pred[pred["split"] == sp]
    m = ashrae_metrics(d["y_true"], d["y_pred"])
    if m is None:
        continue
    cov = {f"PI{k}_coverage_%": float(((d["y_true"] >= d[lo]) & (d["y_true"] <= d[hi])).mean() * 100)
           for k, (lo, hi) in INTERVALS.items()}
    width = float((d["q90"] - d["q10"]).mean())
    rows.append({"zone": ZONE, "load_type": LOAD_TYPE, "model": MODEL_NAME, "split": sp, **m, **cov,
                 "PI80_mean_width_Wh": width})
metrics = pd.DataFrame(rows)
print("\n=== ASHRAE Guideline 14 (hourly): CV(RMSE) <= 30 % and |NMBE| <= 10 % ===")
print(metrics[["model", "split", "n", "MAE", "RMSE", "CV_RMSE_%", "NMBE_%", "ASHRAE_pass"]].round(2).to_string(index=False))
print("\n=== Probabilistic forecast: share of measured values inside the interval ===")
print(metrics[["split", "PI40_coverage_%", "PI60_coverage_%", "PI80_coverage_%", "PI80_mean_width_Wh"]
      ].round(1).to_string(index=False))

bench = []                                                 # naive benchmark on the same hours
for sp in EVAL_SPLITS:
    d = pred[pred["split"] == sp].dropna(subset=["lag_24h", "lag_168h"])
    if d.empty:
        continue
    y = d["y_true"]
    cv_m, cv_24, cv_168 = (ashrae_metrics(y, d[c])["CV_RMSE_%"] for c in ["y_pred", "lag_24h", "lag_168h"])
    bench.append({"split": sp, "n_common_hours": len(d), "Chronos_CV_RMSE_%": cv_m,
                  "naive_yesterday_CV_RMSE_%": cv_24, "naive_last_week_CV_RMSE_%": cv_168,
                  "beats_benchmark": bool(cv_m < min(cv_24, cv_168))})
bench = pd.DataFrame(bench)
print("\n=== Benchmark: Chronos vs naive forecasts (same hours) ===")
print(bench.round(2).to_string(index=False) if not bench.empty else "no common hours")

# %% ---------------------------- 9. SAVE PREDICTIONS ------------------------------
team_cols = ["timestamp_utc", "zone", "load_type", "model", "split", "y_true", "y_pred"]
pred[team_cols].to_csv(f"{prefix}_predictions.csv", index=False)              # format agreed with Team B
extra = ["timestamp_local", "origin_utc", "step_h", "context_hours"] + QCOLS + ["series_caution", "level_shift_2025"]

# %% ---------------------------- 10. PLOTS (probabilistic forecasts) --------------
splits = [s for s in EVAL_SPLITS if (pred["split"] == s).any()]


def band(ax, x, lo, hi, color, alpha, label):
    ax.fill_between(x, lo, hi, color=color, alpha=alpha, lw=0, label=label)


# (a) full periods and (b) 14-day zoom: measured vs median
for zoom, fn in [(False, "forecast_full"), (True, "forecast_zoom")]:
    fig, axes = plt.subplots(len(splits), 1, figsize=(15, 3.8 * len(splits)), squeeze=False)
    for ax, sp in zip(axes[:, 0], splits):
        d = pred[pred["split"] == sp]
        s = {c: hourly(d, c) for c in ["y_true", "y_pred", "q10", "q90", "q30", "q70"]}
        if zoom:
            a, b = best_window(d["timestamp_utc"])
            s = {k: v.loc[a:b] for k, v in s.items()}
        x = s["y_true"].index
        band(ax, x, s["q10"].values, s["q90"].values, "#9ec5ee", 0.55, "80 % prediction interval (q10-q90)")
        band(ax, x, s["q30"].values, s["q70"].values, "#4f8fd6", 0.55, "40 % prediction interval (q30-q70)")
        ax.plot(x, s["y_pred"].values, color="#1c5cab", lw=1.0, label="Chronos median")
        ax.plot(x, s["y_true"].values, color="black", lw=1.1, label="Measured")
        ax.set_title(f"{title} - {sp}" + (" (14-day zoom)" if zoom else "") + f" - {MODEL_NAME}", fontweight="bold")
        ax.set_ylabel("Energy (Wh per hour)")
        ax.grid(True, ls="--", alpha=0.4)
        ax.legend(loc="upper right", fontsize=8, ncol=2)
    axes[-1, 0].set_xlabel("Time (UTC)")
    fig.tight_layout()
    fig.savefig(f"{prefix}_{fn}.png", dpi=200)
    plt.close(fig)

# (c) single example days against the hour after local midnight
pred["err2"] = (pred["y_true"] - pred["y_pred"]) ** 2
daily = (pred.groupby(["split", "origin_utc"])
         .agg(n=("err2", "size"), rmse=("err2", lambda v: float(np.sqrt(v.mean()))), mean_y=("y_true", "mean"))
         .reset_index())
daily = daily[(daily["n"] >= 18) & (daily["mean_y"] > 0)]
daily["day_cv_%"] = daily["rmse"] / daily["mean_y"] * 100
fig, axes = plt.subplots(len(splits), 3, figsize=(15, 3.6 * len(splits)), squeeze=False)
for r_i, sp in enumerate(splits):
    dd = daily[daily["split"] == sp].sort_values("rmse").reset_index(drop=True)   # rank days by absolute error
    picks = [("best day", 0), ("typical day", len(dd) // 2), ("worst day", len(dd) - 1)] if len(dd) else []
    for c_i in range(3):
        ax = axes[r_i, c_i]
        if c_i >= len(picks):
            ax.axis("off")
            continue
        label, k = picks[c_i]
        o = dd.loc[k, "origin_utc"]
        d = pred[(pred["split"] == sp) & (pred["origin_utc"] == o)].sort_values("step_h")
        ax.fill_between(d["step_h"], d["q10"], d["q90"], color="#9ec5ee", alpha=0.6, lw=0, label="80 % interval")
        ax.fill_between(d["step_h"], d["q30"], d["q70"], color="#4f8fd6", alpha=0.6, lw=0, label="40 % interval")
        ax.plot(d["step_h"], d["y_pred"], color="#1c5cab", lw=1.4, label="Chronos median")
        ax.plot(d["step_h"], d["y_true"], color="black", lw=1.4, marker="o", ms=3, label="Measured")
        ax.set_title(f"{sp}: {label} ({d['timestamp_local'].iloc[0]:%d %b %Y}, RMSE {dd.loc[k, 'rmse']:.0f} Wh, CV {dd.loc[k, 'day_cv_%']:.0f} %)", fontsize=8)
        ax.set_xlabel("Hours after local midnight")
        ax.set_ylabel("Wh per hour")
        ax.grid(True, ls="--", alpha=0.4)
        if r_i == 0 and c_i == 0:
            ax.legend(fontsize=7)
fig.suptitle(f"{title} - single-day probabilistic forecasts ({MODEL_NAME})", fontweight="bold")
fig.tight_layout()
fig.savefig(f"{prefix}_forecast_example_days.png", dpi=200)
plt.close(fig)

# (d) calibration: are the intervals honest?
fig, ax = plt.subplots(figsize=(8, 5))
width, nominal = 0.8 / max(len(metrics), 1), [40, 60, 80]
for i, (_, r) in enumerate(metrics.iterrows()):
    ax.bar(np.arange(3) + i * width, [r[f"PI{k}_coverage_%"] for k in nominal], width, label=r["split"])
for j, k in enumerate(nominal):
    ax.hlines(k, j - 0.1, j + 0.9, colors="black", linestyles="--", lw=1)
ax.set_xticks(np.arange(3) + width * (len(metrics) - 1) / 2)
ax.set_xticklabels([f"{k} % interval\n(dashed = ideal)" for k in nominal])
ax.set_ylabel("Measured values inside the interval (%)")
ax.set_title(f"{title} - calibration of the prediction intervals", fontweight="bold")
ax.legend()
ax.grid(True, axis="y", ls="--", alpha=0.4)
fig.tight_layout()
fig.savefig(f"{prefix}_calibration.png", dpi=200)
plt.close(fig)

# %% ---------------------------- 11. EXCEL OUTPUT ---------------------------------
with pd.ExcelWriter(f"{prefix}_results.xlsx", engine="openpyxl") as xw:
    metrics.to_excel(xw, sheet_name="ASHRAE_table", index=False)
    bench.to_excel(xw, sheet_name="Benchmark", index=False)
    pd.DataFrame(tuning).to_excel(xw, sheet_name="Context_tuning", index=False)
    pred[team_cols + extra].to_excel(xw, sheet_name="Predictions", index=False)
    pd.DataFrame({"setting": ["ZONE", "LOAD_TYPE", "MODEL_ID", "context_hours_used", "TUNE_CONTEXT",
                              "MIN_CONTEXT_HOURS", "quantile_levels", "device", "eval_hours_without_forecast"],
                  "value": [ZONE, LOAD_TYPE, MODEL_ID, best_ctx, TUNE_CONTEXT, MIN_CONTEXT_HOURS,
                            str(QUANTILES), device, n_missing]}).to_excel(xw, sheet_name="Settings", index=False)

print("\nFiles written to", os.path.abspath(OUTPUT_DIR))
for fn in sorted(os.listdir(OUTPUT_DIR)):
    if fn.startswith(tag):
        print("  -", fn)
if DOWNLOAD_FROM_COLAB and "google.colab" in sys.modules:
    from google.colab import files
    for fn in sorted(os.listdir(OUTPUT_DIR)):
        if fn.startswith(tag):
            files.download(os.path.join(OUTPUT_DIR, fn))
