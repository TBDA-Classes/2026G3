"""
T37 (F1.4) - Multi-day forecast horizons for HVAC and the floor-1 total
=======================================================================
Project : DataPack Energy Forecaster - CeDInt floor 1 (TBDA)
Author  : Riccardo Tardanico
Backlog : T37 (F1.4) "Extend the best models to multi-day horizons for HVAC and the
          floor total and measure how accuracy decays with the horizon"
Input   : T32_cedint_f1_model_ready.csv.gz   (dataset v0.4, model-ready, Team B)
          openmeteo_madrid_hourly.csv         (Open-Meteo outdoor weather, T26)
Output  : outputs_T37/  (predictions, metrics xlsx, figures, experiment-log rows)

Run     : python T37_multihorizon_forecast.py <input_folder> [<output_folder>]

What the script does
--------------------
1. Builds the target series:
     - HVAC of zones NE, NW and SE (the only zones with HVAC);
     - FLOOR_TOTAL       = sum of the 10 core series (HVAC, Lighting, Plugs & Sockets
                           of every zone where they exist), the same total as T30;
     - FLOOR_TOTAL_noSW  = the same sum without zone SW, because SW has no data in 2025:
                           without it the 2025 test of the total is empty (T30, Entry 17).
   An hour of a total is usable only if ALL its parts are usable in that hour
   (include_train / include_eval of the T32 file), so a total is never a partial sum.
2. For each horizon d = 1, 2, 3, 5, 7 days trains one DIRECT model (one model per
   horizon, no recursion): the forecast for hour t only uses target values up to
   t - 24*d hours. Every target feature is lagged by at least 24*d hours, so there is
   no leakage at any horizon (d = 1 is the usual day-ahead forecast).
3. Two weather scenarios, because the history contains measured weather but no
   weather FORECASTS:
     - "weather" : outdoor Open-Meteo weather of hour t used as a perfect forecast
                   (upper bound of what a real weather forecast could give);
     - "no_weather": calendar + past load only (lower bound).
   Indoor sensors (temp_c, hum_pct, lum_lux, occupancy) are not used: they are not
   known days ahead and NE has none.
4. Learner: scikit-learn GradientBoostingRegressor with the settings of the team's
   GBM (GBM_forallzones.ipynb: 100 trees, learning rate 0.1, depth 4, seed 42), so the
   result is comparable with T29/T39. Missing feature values are set to -1 (energy
   is never negative, so the trees can isolate them).
5. Baselines per horizon: seasonal naive (same hour one week earlier, valid for all
   d <= 7) and persistence (same hour d days earlier).
6. Evaluates every forecast with MAE, RMSE, CV(RMSE) and NMBE (ASHRAE Guideline 14:
   CV(RMSE) <= 30 %, |NMBE| <= 10 %) on validation (2022-H2), test_2023 and test_2025.
   All horizons, scenarios and baselines are scored on the SAME hours, so the decay
   curve only shows the effect of the horizon.

Split (T32): train 2020-06-01 -> 2022-06-30 | validation 2022-07-01 -> 2022-12-31 |
             test_2023 2023-01-01 -> 2023-02-28 | test_2025 2025-08-18 -> 2025-10-13
NMBE sign: D1 convention (models.ipynb, GBM notebook): sum(y - y_hat) / (n * mean(y)),
           so NMBE > 0 means the model UNDER-forecasts.
"""
import os
import sys
import time

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.ensemble import GradientBoostingRegressor

# ----------------------------------------------------------------------------
# 1. CONFIGURATION
# ----------------------------------------------------------------------------
HORIZONS_DAYS = [1, 2, 3, 5, 7]
SCENARIOS = ["weather", "no_weather"]
CORE_LOADS = ["HVAC", "Lighting", "Plugs & Sockets"]
TARGETS = {                       # name -> list of (zone, load_type) that are summed
    "NE HVAC": [("NE", "HVAC")],
    "NW HVAC": [("NW", "HVAC")],
    "SE HVAC": [("SE", "HVAC")],
    "FLOOR_TOTAL": "core",        # all 10 core series
    "FLOOR_TOTAL_noSW": "core_noSW",
}
EVAL_SPLITS = ["validation", "test_2023", "test_2025"]
GBM_PARAMS = dict(n_estimators=100, learning_rate=0.1, max_depth=4, random_state=42)
CALENDAR = ["hour_local", "dayofweek_local", "month_local", "is_weekend", "is_holiday",
            "is_august_low_use", "flag_covid_2020"]
WEATHER = ["w_temp", "w_hum", "w_rad", "w_wind", "w_hdh", "w_cdh", "w_temp_mean6h", "w_temp_mean24h"]
AUTHOR = "Riccardo Tardanico"
RUN_DATE = "14/11/2026"
COLORS = {"gbm_weather": "#2a78d6", "gbm_no_weather": "#eb6834",
          "persistence": "#1baf7a", "seasonal_naive": "#eda100"}
MARKERS = {"gbm_weather": "o", "gbm_no_weather": "s", "persistence": "^", "seasonal_naive": "D"}
LABELS = {"gbm_weather": "GBM + weather (perfect forecast)", "gbm_no_weather": "GBM, no weather",
          "persistence": "Persistence (same hour d days before)",
          "seasonal_naive": "Seasonal naive (same hour last week)"}


# ----------------------------------------------------------------------------
# 2. HELPERS
# ----------------------------------------------------------------------------
def metrics(y, p):
    y, p = np.asarray(y, float), np.asarray(p, float)
    ok = np.isfinite(y) & np.isfinite(p)
    y, p = y[ok], p[ok]
    n = len(y)
    if n == 0:
        return dict(n_hours=0, MAE=np.nan, RMSE=np.nan, CV_RMSE_pct=np.nan, NMBE_pct=np.nan,
                    ASHRAE14_pass=False)
    mean_y = y.mean()
    rmse = np.sqrt(np.mean((y - p) ** 2))
    cv = 100 * rmse / mean_y
    nmbe = 100 * np.sum(y - p) / (n * mean_y)
    return dict(n_hours=n, MAE=np.mean(np.abs(y - p)), RMSE=rmse, CV_RMSE_pct=cv, NMBE_pct=nmbe,
                ASHRAE14_pass=bool(cv <= 30 and abs(nmbe) <= 10))


def load_inputs(in_dir):
    df = pd.read_csv(os.path.join(in_dir, "T32_cedint_f1_model_ready.csv.gz"),
                     parse_dates=["timestamp_utc", "timestamp_local"])
    w = pd.read_csv(os.path.join(in_dir, "openmeteo_madrid_hourly.csv"))
    w["timestamp_utc"] = pd.to_datetime(w["timestamp"], utc=True).dt.tz_localize(None)
    w = w.drop(columns="timestamp").sort_values("timestamp_utc").set_index("timestamp_utc")
    w = w.asfreq("h")
    w["w_hdh"] = (18 - w["w_temp"]).clip(lower=0)        # heating degree-hours (base 18 C, as T26)
    w["w_cdh"] = (w["w_temp"] - 24).clip(lower=0)        # cooling degree-hours (base 24 C)
    w["w_temp_mean6h"] = w["w_temp"].rolling(6, min_periods=3).mean()    # delayed HVAC response (0-6 h)
    w["w_temp_mean24h"] = w["w_temp"].rolling(24, min_periods=12).mean()
    return df, w


def build_target(df, parts, name):
    """Hourly frame on a complete grid: y, usable flags, split and calendar."""
    sub = df[df.set_index(["zone", "load_type"]).index.isin(parts)]
    n_parts = len(parts)
    g = sub.groupby("timestamp_utc")
    out = pd.DataFrame({
        "y": g["energy_wh_model"].sum(min_count=1),
        "n_valid": g["energy_wh_model"].count(),
        "train_ok": g["include_train"].sum() == n_parts,
        "eval_ok": g["include_eval"].sum() == n_parts,
    })
    out.loc[out["n_valid"] < n_parts, "y"] = np.nan          # never a partial sum
    first = g[["timestamp_local", "split"] + CALENDAR].first()
    out = out.join(first)
    grid = pd.date_range(out.index.min(), out.index.max(), freq="h", name="timestamp_utc")
    out = out.reindex(grid)                                    # the 902-day gap becomes NaN rows
    out[["train_ok", "eval_ok"]] = out[["train_ok", "eval_ok"]].fillna(False).astype(bool)
    out["split"] = out["split"].fillna("unused")
    out["series"] = name
    out["zones"] = "+".join(sorted({z for z, _ in parts}))
    out["load_types"] = "+".join(sorted({l for _, l in parts}))
    return out


def horizon_features(s, d, weather):
    """Features for a direct forecast d days ahead: target info only up to t - 24*d h."""
    L = 24 * d
    y = s["y"]
    F = s[CALENDAR].copy()
    for lag in sorted({L, L + 24, 168, 336}):
        if lag >= L:
            F[f"lag_{lag}h"] = y.shift(lag)
    F["mean_prev_24h"] = y.rolling(24, min_periods=12).mean().shift(L)
    F["mean_prev_7d"] = y.rolling(168, min_periods=84).mean().shift(L)
    F["same_hour_mean_7d"] = pd.concat([y.shift(L + 24 * k) for k in range(7)], axis=1).mean(axis=1)
    if weather is not None:
        F = F.join(weather[WEATHER], how="left")
    return F


# ----------------------------------------------------------------------------
# 3. MAIN LOOP
# ----------------------------------------------------------------------------
def run(in_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()
    df, w = load_inputs(in_dir)
    core = [(z, l) for z, l in df[["zone", "load_type"]].drop_duplicates().itertuples(index=False)
            if l in CORE_LOADS]
    core = sorted(p for p in core if df.loc[(df.zone == p[0]) & (df.load_type == p[1]),
                                            "energy_wh_model"].notna().any())
    resolved = {}
    for name, parts in TARGETS.items():
        if parts == "core":
            parts = core
        elif parts == "core_noSW":
            parts = [p for p in core if p[0] != "SW"]
        resolved[name] = parts
    print("Core series in the floor total:", core)

    preds, rows, imps = [], [], []
    for name, parts in resolved.items():
        s = build_target(df, parts, name)
        # common evaluation hours: valid target, usable for scoring, last-week value exists
        lag168 = s["y"].shift(168)
        eval_mask = s["eval_ok"] & s["y"].notna() & lag168.notna() & s["split"].isin(EVAL_SPLITS)
        train_mask = s["train_ok"] & s["y"].notna() & (s["split"] == "train")
        print(f"\n{name}: {len(parts)} part(s), train hours {train_mask.sum()}, "
              f"eval hours {eval_mask.sum()} "
              f"({s.loc[eval_mask, 'split'].value_counts().to_dict()})")
        ev = s.loc[eval_mask]
        base = pd.DataFrame({"timestamp_utc": ev.index, "timestamp_local": ev["timestamp_local"].values,
                             "series": name, "split": ev["split"].values, "y_true": ev["y"].values})
        for d in HORIZONS_DAYS:
            # baselines
            fc = {"seasonal_naive": lag168[eval_mask].values,
                  "persistence": s["y"].shift(24 * d)[eval_mask].values}
            for sc in SCENARIOS:
                F = horizon_features(s, d, w if sc == "weather" else None)
                cols = list(F.columns)
                Xtr = F.loc[train_mask, cols].fillna(-1)
                ytr = s.loc[train_mask, "y"]
                m = GradientBoostingRegressor(**GBM_PARAMS).fit(Xtr, ytr)
                fc[f"gbm_{sc}"] = np.clip(m.predict(F.loc[eval_mask, cols].fillna(-1)), 0, None)
                imps.append(pd.DataFrame({"series": name, "horizon_days": d, "scenario": sc,
                                          "feature": cols, "importance": m.feature_importances_}))
            for model, p in fc.items():
                pr = base.copy()
                pr["model"], pr["horizon_days"], pr["y_pred"] = model, d, p
                preds.append(pr)
                for sp in EVAL_SPLITS + ["test_all"]:
                    msk = (base["split"].str.startswith("test") if sp == "test_all"
                           else base["split"] == sp).values
                    rows.append({"series": name, "horizon_days": d, "model": model, "split": sp,
                                 **metrics(base["y_true"].values[msk], np.asarray(p)[msk])})
            print(f"  horizon {d} d done ({time.time() - t0:.0f} s)")

    P = pd.concat(preds, ignore_index=True)
    M = pd.DataFrame(rows)
    I = pd.concat(imps, ignore_index=True)
    return P, M, I, resolved


# ----------------------------------------------------------------------------
# 4. TABLES
# ----------------------------------------------------------------------------
def decay_table(M):
    """CV(RMSE) at every horizon relative to the 1-day value of the same model."""
    t = M[M["n_hours"] > 0].copy()
    ref = t[t.horizon_days == 1].set_index(["series", "model", "split"])["CV_RMSE_pct"]
    t["CV_RMSE_at_1d"] = t.set_index(["series", "model", "split"]).index.map(ref)
    t["CV_increase_pts_vs_1d"] = t["CV_RMSE_pct"] - t["CV_RMSE_at_1d"]
    t["CV_increase_pct_vs_1d"] = 100 * t["CV_increase_pts_vs_1d"] / t["CV_RMSE_at_1d"]
    return t[["series", "split", "model", "horizon_days", "CV_RMSE_pct", "CV_RMSE_at_1d",
              "CV_increase_pts_vs_1d", "CV_increase_pct_vs_1d"]]


def skill_table(M):
    """Skill score vs seasonal naive: 1 - RMSE_model / RMSE_naive (> 0 = better than naive)."""
    t = M[M["n_hours"] > 0]
    nv = t[t.model == "seasonal_naive"].set_index(["series", "split", "horizon_days"])["RMSE"]
    o = t[t.model != "seasonal_naive"].copy()
    o["RMSE_seasonal_naive"] = o.set_index(["series", "split", "horizon_days"]).index.map(nv)
    o["skill_vs_naive"] = 1 - o["RMSE"] / o["RMSE_seasonal_naive"]
    return o[["series", "split", "model", "horizon_days", "RMSE", "RMSE_seasonal_naive", "skill_vs_naive"]]


def daily_metrics(P):
    """Accuracy of DAILY energy (local days with all 24 hours scored), useful for planning."""
    q = P.copy()
    q["date_local"] = pd.to_datetime(q["timestamp_local"]).dt.date
    g = q.groupby(["series", "split", "model", "horizon_days", "date_local"])
    dd = g.agg(y_true=("y_true", "sum"), y_pred=("y_pred", "sum"), n=("y_true", "size")).reset_index()
    dd = dd[dd["n"] == 24]
    rows = []
    for k, x in dd.groupby(["series", "split", "model", "horizon_days"]):
        r = metrics(x["y_true"], x["y_pred"])
        rows.append(dict(zip(["series", "split", "model", "horizon_days"], k),
                         n_days=r["n_hours"], MAE_wh_day=r["MAE"], CV_RMSE_daily_pct=r["CV_RMSE_pct"],
                         NMBE_daily_pct=r["NMBE_pct"]))
    return pd.DataFrame(rows)


def importance_groups(I):
    def grp(f):
        if f.startswith("lag_") or f.startswith("mean_prev") or f.startswith("same_hour"):
            return "past load (lags, means)"
        if f.startswith("w_"):
            return "outdoor weather"
        return "calendar"
    J = I.copy()
    J["group"] = J["feature"].map(grp)
    return (J.groupby(["series", "scenario", "horizon_days", "group"])["importance"].sum()
            .unstack("group").reset_index())


# ----------------------------------------------------------------------------
# 5. FIGURES
# ----------------------------------------------------------------------------
def _style(ax):
    ax.set_facecolor("#fcfcfb")
    ax.grid(axis="y", color="#e4e3df", linewidth=0.8)
    ax.set_axisbelow(True)
    for sp in ["top", "right"]:
        ax.spines[sp].set_visible(False)
    for sp in ["left", "bottom"]:
        ax.spines[sp].set_color("#9a9994")
    ax.tick_params(colors="#52514e", labelsize=9)


def fig_decay(M, out_dir, metric="CV_RMSE_pct", fname="F37a_CV_RMSE_vs_horizon.png",
              ylabel="CV(RMSE) %", ref_lines=(30,)):
    series = list(dict.fromkeys(M["series"]))
    splits = ["test_2023", "test_2025"]
    fig, axes = plt.subplots(len(splits), len(series), figsize=(3.4 * len(series), 6.6),
                             facecolor="#fcfcfb", sharex=True)
    for i, sp in enumerate(splits):
        for j, se in enumerate(series):
            ax = axes[i, j]
            _style(ax)
            t = M[(M.series == se) & (M.split == sp) & (M.n_hours > 0)]
            if t.empty:
                ax.text(0.5, 0.5, "no valid hours\n(SW has no 2025 data)", ha="center", va="center",
                        transform=ax.transAxes, color="#52514e", fontsize=9)
                ax.set_yticks([])
            for model in COLORS:
                x = t[t.model == model].sort_values("horizon_days")
                if x.empty:
                    continue
                ax.plot(x["horizon_days"], x[metric], color=COLORS[model], linewidth=2,
                        marker=MARKERS[model], markersize=6, markeredgecolor="#fcfcfb",
                        markeredgewidth=1.5, label=LABELS[model])
            for r in ref_lines:
                if not t.empty:
                    ax.axhline(r, color="#52514e", linewidth=1, linestyle="--")
                    if metric == "NMBE_pct":
                        ax.axhline(-r, color="#52514e", linewidth=1, linestyle="--")
            ax.set_xticks(HORIZONS_DAYS)
            n_txt = f"n = {int(t['n_hours'].iloc[0])} h" if not t.empty else ""
            if i == 0:
                ax.set_title(f"{se}\n", fontsize=11, color="#0b0b0b", fontweight="bold")
            ax.text(0.5, 1.02, n_txt, transform=ax.transAxes, ha="center", va="bottom",
                    fontsize=8, color="#52514e")
            if j == 0:
                ax.set_ylabel(f"{sp}\n{ylabel}", color="#0b0b0b", fontsize=10)
            if i == len(splits) - 1:
                ax.set_xlabel("horizon (days ahead)", color="#52514e", fontsize=9)
    h, l = axes[0, 1].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=4, frameon=False, fontsize=9)
    ref_txt = "dashed: ASHRAE 14 limit (CV(RMSE) 30 %)" if metric == "CV_RMSE_pct" else \
        "dashed: ASHRAE 14 limits (NMBE ±10 %); NMBE > 0 = under-forecast"
    fig.suptitle(f"T37 - {ylabel} by forecast horizon ({ref_txt})", fontsize=12, color="#0b0b0b")
    fig.tight_layout(rect=(0, 0.06, 1, 0.95))
    fig.savefig(os.path.join(out_dir, fname), dpi=200)
    plt.close(fig)


def fig_example(P, out_dir, series="NW HVAC", split="test_2023", days=14):
    t = P[(P.series == series) & (P.split == split) & (P.model == "gbm_weather")].copy()
    t["timestamp_local"] = pd.to_datetime(t["timestamp_local"])
    start = t["timestamp_local"].min().normalize() + pd.Timedelta(days=7)
    t = t[(t.timestamp_local >= start) & (t.timestamp_local < start + pd.Timedelta(days=days))]
    fig, ax = plt.subplots(figsize=(13, 4.6), facecolor="#fcfcfb")
    _style(ax)
    full = pd.date_range(start, start + pd.Timedelta(days=days), freq="h", inclusive="left")
    a = t[t.horizon_days == 1].set_index("timestamp_local").reindex(full)   # NaN -> no line across gaps
    ax.plot(full, a["y_true"], color="#0b0b0b", linewidth=1.6, label="actual")
    for d, col in [(1, "#2a78d6"), (7, "#eb6834")]:
        x = t[t.horizon_days == d].set_index("timestamp_local").reindex(full)
        ax.plot(full, x["y_pred"], color=col, linewidth=1.4, label=f"GBM + weather, {d} day{'s' if d > 1 else ''} ahead")
    ax.set_ylabel("energy (Wh per hour)", color="#0b0b0b")
    ax.set_title(f"T37 - {series}, {split}: actual vs forecast issued 1 day and 7 days ahead "
                 f"({days} days from {start:%d %b %Y})", fontsize=11, color="#0b0b0b")
    ax.legend(frameon=False, fontsize=9, loc="upper right")
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "F37c_example_NW_HVAC_1d_vs_7d.png"), dpi=200)
    plt.close(fig)


def fig_importance(G, out_dir):
    g = G[G.scenario == "weather"]
    series = list(dict.fromkeys(g["series"]))
    groups = ["past load (lags, means)", "calendar", "outdoor weather"]
    cols = {"past load (lags, means)": "#2a78d6", "calendar": "#eb6834", "outdoor weather": "#1baf7a"}
    fig, axes = plt.subplots(1, len(series), figsize=(3.4 * len(series), 3.8), facecolor="#fcfcfb",
                             sharey=True)
    for ax, se in zip(axes, series):
        _style(ax)
        x = g[g.series == se].sort_values("horizon_days")
        bottom = np.zeros(len(x))
        pos = np.arange(len(x))
        for gr in groups:
            v = x[gr].fillna(0).values
            ax.bar(pos, v, bottom=bottom, color=cols[gr], width=0.7, edgecolor="#fcfcfb",
                   linewidth=1.5, label=gr)
            bottom += v
        ax.set_xticks(pos, [f"{d} d" for d in x["horizon_days"]])
        ax.set_title(se, fontsize=11, color="#0b0b0b", fontweight="bold")
    axes[0].set_ylabel("share of GBM importance", color="#0b0b0b")
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=3, frameon=False, fontsize=9)
    fig.suptitle("T37 - What the GBM (+ weather) relies on at each horizon", fontsize=12, color="#0b0b0b")
    fig.tight_layout(rect=(0, 0.08, 1, 0.93))
    fig.savefig(os.path.join(out_dir, "F37d_feature_groups_by_horizon.png"), dpi=200)
    plt.close(fig)


# ----------------------------------------------------------------------------
# 6. EXPERIMENT-LOG ROWS (columns of experiment_log.xlsx, T20)
# ----------------------------------------------------------------------------
def log_rows(M, resolved):
    periods = {"validation": "2022-07-01 to 2022-12-31", "test_2023": "2023-01-01 to 2023-02-28",
               "test_2025": "2025-08-18 to 2025-10-13"}
    t = M[(M.split.isin(periods)) & (M.n_hours > 0)].reset_index(drop=True)
    feats = {"gbm_weather": "calendar; target lags >= 24*d h; prev-24h/7-day means; Open-Meteo weather at t",
             "gbm_no_weather": "calendar; target lags >= 24*d h; prev-24h/7-day means",
             "persistence": "y(t - 24*d h)", "seasonal_naive": "y(t - 168 h)"}
    return pd.DataFrame({
        "ID": [f"T37-{i + 1:03d}" for i in range(len(t))],
        "date": RUN_DATE, "author": AUTHOR,
        "series": t["series"] + " (" + t["series"].map(lambda s: str(len(resolved[s]))) + " part(s))",
        "features": t["model"].map(feats),
        "model": t["model"] + " direct, horizon " + t["horizon_days"].astype(str) + " d",
        "train period": "2020-06-01 to 2022-06-30 (include_train = 1)",
        "test period": t["split"] + " " + t["split"].map(periods),
        "MAE": t["MAE"].round(2), "RMSE": t["RMSE"].round(2),
        "CV(RMSE)": t["CV_RMSE_pct"].round(2), "NMBE": t["NMBE_pct"].round(2),
        "notes": "T37 (F1.4) multi-horizon; n = " + t["n_hours"].astype(str) + " h; ASHRAE14 " +
                 np.where(t["ASHRAE14_pass"], "pass", "fail"),
    })


# ----------------------------------------------------------------------------
# 7. ENTRY POINT
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    in_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    out_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(".", "outputs_T37")
    P, M, I, resolved = run(in_dir, out_dir)
    D, S, DM, G = decay_table(M), skill_table(M), daily_metrics(P), importance_groups(I)

    piv = (M[M.split.isin(["test_2023", "test_2025", "validation"])]
           .pivot_table(index=["series", "split", "model"], columns="horizon_days",
                        values="CV_RMSE_pct").round(1).reset_index())
    piv.columns = [f"CV_RMSE_{c}d" if isinstance(c, (int, np.integer)) else c for c in piv.columns]
    comp = pd.DataFrame([(k, "+".join(f"{z} {l}" for z, l in v)) for k, v in resolved.items()],
                        columns=["series", "parts summed"])
    readme = pd.DataFrame({"item": [
        "Task", "Author", "Input", "Method", "Horizons", "Scenarios", "Learner", "Baselines",
        "Evaluation hours", "NMBE sign", "ASHRAE 14", "Sheets"], "description": [
        "T37 (F1.4) - multi-day forecast horizons for HVAC and the floor-1 total",
        AUTHOR + ", " + RUN_DATE,
        "T32_cedint_f1_model_ready.csv.gz (v0.4) + openmeteo_madrid_hourly.csv",
        "Direct strategy: one model per horizon; target information only up to t - 24*d h (no leakage)",
        ", ".join(f"{d} d" for d in HORIZONS_DAYS),
        "weather = Open-Meteo weather of hour t used as a perfect forecast (upper bound); "
        "no_weather = calendar + past load only (lower bound)",
        "GradientBoostingRegressor(n_estimators=100, learning_rate=0.1, max_depth=4, random_state=42) "
        "= settings of GBM_forallzones.ipynb",
        "seasonal_naive = same hour last week; persistence = same hour d days earlier",
        "Same hours for every horizon, scenario and baseline: include_eval = 1 for all parts, "
        "value 168 h earlier exists",
        "D1 convention: NMBE = sum(y - y_hat)/(n*mean(y)); > 0 = under-forecast",
        "pass = CV(RMSE) <= 30 % and |NMBE| <= 10 % (hourly)",
        "CV_by_horizon (pivot), Metrics_long, Decay_vs_1day, Skill_vs_naive, Daily_energy, "
        "Feature_groups, Series_definition"]})
    xl = os.path.join(out_dir, "T37_multihorizon_results.xlsx")
    with pd.ExcelWriter(xl, engine="xlsxwriter") as xw:
        for nm, d in [("README", readme), ("CV_by_horizon", piv), ("Metrics_long", M.round(3)),
                      ("Decay_vs_1day", D.round(2)), ("Skill_vs_naive", S.round(3)),
                      ("Daily_energy", DM.round(2)), ("Feature_groups", G.round(3)),
                      ("Series_definition", comp)]:
            d.to_excel(xw, sheet_name=nm, index=False)
            xw.sheets[nm].set_column(0, len(d.columns) - 1, 16)
            xw.sheets[nm].freeze_panes(1, 0)
        xw.sheets["README"].set_column(1, 1, 120)
        xw.sheets["Series_definition"].set_column(1, 1, 140)
    P.to_csv(os.path.join(out_dir, "T37_multihorizon_predictions.csv.gz"), index=False,
             float_format="%.3f", compression="gzip")
    log_rows(M, resolved).to_csv(os.path.join(out_dir, "T37_experiment_log_rows.csv"), index=False)

    fig_decay(M, out_dir)
    fig_decay(M, out_dir, metric="NMBE_pct", fname="F37b_NMBE_vs_horizon.png", ylabel="NMBE %",
              ref_lines=(10,))
    fig_example(P, out_dir)
    fig_importance(G, out_dir)

    print("\n===== CV(RMSE) % by horizon (test periods) =====")
    print(piv[piv.split != "validation"].to_string(index=False))
    print("\nFiles written to", out_dir)
