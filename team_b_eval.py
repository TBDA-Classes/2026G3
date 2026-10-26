"""
Team B evaluation toolkit (TBDA DataPack, CeDInt floor 1)

Covers the Team B parts of:
  F6.3  test on periods never used for training (split rules + leakage / validity check)
  F6.4  MAE, RMSE, CV(RMSE), NMBE and ASHRAE Guideline 14 pass/fail per series
  F6.6  forecast errors by hour, season, weekday and zone
  F7.1  largest forecast errors as candidate anomalies, with context and a first explanation
  F6.7  sensitivity: metrics with and without flagged (data-quality) hours

Input 1: a predictions file (CSV) in the agreed format, one row per forecast hour:
    timestamp_utc, zone, load_type, model, split, y_true, y_pred
    - timestamp_utc: start of the forecast hour (UTC), same as in the clean dataset
    - split: train | validation | test_2023 | test_2025
    - y_true: energy_wh_model from the clean dataset (Wh)
    - y_pred: the forecast (Wh)
Input 2: the clean dataset folder of clean_cedint.py (cedint_f1_hourly_clean.csv.gz, v0.4).

Run:  python team_b_eval.py <predictions.csv> <clean_folder> <output_folder>
"""
import os, sys
import numpy as np
import pandas as pd

PRED_COLUMNS = ["timestamp_utc", "zone", "load_type", "model", "split", "y_true", "y_pred"]

# F6.3 - agreed periods (UTC). Training never touches the validation or test periods.
SPLITS = {
    "train":      ("2020-06-01", "2022-06-30 23:00"),
    "validation": ("2022-07-01", "2022-12-31 23:00"),
    "test_2023":  ("2023-01-01", "2023-02-28 23:00"),   # only 2 months exist before the 902-day gap
    "test_2025":  ("2025-08-18", "2025-10-13 23:00"),   # minute era aggregated to hours
}
TEST_2025_ZONES = {"NE", "NW", "SE"}                   # SW 2025 is 'Do not use'
LEVEL_SHIFT_2025 = {("NW", "Lighting"), ("NW", "HVAC"), ("SE", "Lighting")}  # report separately
ASHRAE_CV_MAX, ASHRAE_NMBE_MAX = 30.0, 10.0           # hourly calibration criteria (Guideline 14)
QUALITY_FLAGS = ["flag_partial_sum", "flag_zero_record", "flag_counter_spike", "flag_counter_reset",
                 "flag_energy_implausible", "flag_power_spike", "flag_power_energy_mismatch",
                 "flag_neg_large", "flag_low_coverage"]
CONTEXT_COLS = ["timestamp_local", "is_holiday", "holiday_name", "is_weekend", "is_august_low_use",
                "flag_covid_2020", "temp_c", "flag_temp_extreme", "occupancy", "energy_source",
                "recommendation", "usable_for_model"] + QUALITY_FLAGS


def season(month):
    return np.select([month.isin([12, 1, 2]), month.isin([3, 4, 5]), month.isin([6, 7, 8])],
                     ["winter", "spring", "summer"], "autumn")


# ------------------------------------------------------------------ loading
def load_clean(folder):
    p = os.path.join(folder, "cedint_f1_hourly_clean.csv.gz")
    df = pd.read_csv(p, parse_dates=["timestamp_utc", "timestamp_local"], low_memory=False)
    return df


def load_predictions(path):
    p = pd.read_csv(path, parse_dates=["timestamp_utc"])
    missing = [c for c in PRED_COLUMNS if c not in p.columns]
    if missing:
        raise ValueError(f"predictions file is missing columns: {missing}")
    return p


# ------------------------------------------------------------------ F6.3 checks
def check_predictions(pred, clean):
    """Returns (checked predictions joined with the clean data, list of check results)."""
    res = []

    def add(check, ok, detail):
        res.append(dict(check=check, result="PASS" if ok else "FAIL", detail=detail))

    key = ["timestamp_utc", "zone", "load_type"]
    dup = pred.duplicated(key + ["model"]).sum()
    add("No duplicate forecast rows", dup == 0, f"{dup} duplicate rows (same hour, series and model)")
    bad_split = ~pred["split"].isin(SPLITS)
    add("Split names valid", not bad_split.any(), f"{bad_split.sum()} rows with an unknown split name")
    out_of_period = 0
    for s, (a, b) in SPLITS.items():
        m = pred["split"] == s
        out_of_period += int((m & ~pred["timestamp_utc"].between(pd.Timestamp(a), pd.Timestamp(b))).sum())
    add("Every row lies inside its split period", out_of_period == 0, f"{out_of_period} rows outside their period")
    j = pred.merge(clean[key + ["energy_wh_model", "series_excluded", "era"] + CONTEXT_COLS], on=key, how="left")
    not_found = j["energy_wh_model"].isna() & j["usable_for_model"].isna()
    add("Every forecast hour exists in the clean dataset", not not_found.any(), f"{not_found.sum()} rows not found")
    unusable = (j["usable_for_model"] == 0).sum() + (j["series_excluded"] == 1).sum()
    add("No forecasts on 'Do not use' series or hours", unusable == 0, f"{unusable} rows on unusable data")
    sw25 = ((j["split"] == "test_2025") & ~j["zone"].isin(TEST_2025_ZONES)).sum()
    add("test_2025 only for NE, NW, SE", sw25 == 0, f"{sw25} rows for SW in 2025")
    diff = (j["y_true"] - j["energy_wh_model"]).abs()
    mism = (diff > 1e-3 * np.maximum(1, j["energy_wh_model"].abs())).sum()
    add("y_true equals energy_wh_model of the clean dataset", mism == 0,
        f"{mism} rows where y_true differs (wrong target or other dataset version)")
    nan_pred = j["y_pred"].isna().sum()
    add("No missing forecasts", nan_pred == 0, f"{nan_pred} rows with empty y_pred")
    for m, g in j.groupby("model"):
        tr = g[g["split"] == "train"]["timestamp_utc"]
        te = g[g["split"].str.startswith("test")]["timestamp_utc"]
        ok = tr.empty or te.empty or tr.max() < te.min()
        add(f"[{m}] training ends before testing starts", ok,
            f"train ends {tr.max() if len(tr) else '-'}, test starts {te.min() if len(te) else '-'}")
    j["season"] = season(j["timestamp_local"].dt.month)
    j["hour_local"] = j["timestamp_local"].dt.hour
    # hour-level data-quality problem. In the minute era, partial/zero-record minutes were already excluded
    # when the hour was built, so only low coverage, implausible energy, mismatch or interpolation count there.
    hourly_q = (j[QUALITY_FLAGS].fillna(0).sum(axis=1) > 0)
    minute_q = (j[["flag_low_coverage", "flag_energy_implausible", "flag_power_energy_mismatch"]].fillna(0).sum(axis=1) > 0)
    j["flag_any_quality"] = np.where(j["era"] == "minute", minute_q, hourly_q) | (j["energy_source"] == "interpolated")
    j["level_shift_2025"] = [(z, l) in LEVEL_SHIFT_2025 and s == "test_2025"
                             for z, l, s in zip(j["zone"], j["load_type"], j["split"])]
    return j, pd.DataFrame(res)


# ------------------------------------------------------------------ F6.4 metrics
def metrics(y, yhat, p=0):
    """ASHRAE Guideline 14 definitions. NMBE sign: positive = model under-predicts (sum(y - yhat))."""
    y, yhat = np.asarray(y, float), np.asarray(yhat, float)
    ok = ~np.isnan(y) & ~np.isnan(yhat)
    y, yhat = y[ok], yhat[ok]
    n = len(y)
    if n == 0 or y.mean() == 0:
        return dict(n=n, MAE=np.nan, RMSE=np.nan, CV_RMSE_pct=np.nan, NMBE_pct=np.nan, mean_actual=np.nan)
    e = y - yhat
    rmse = np.sqrt((e ** 2).sum() / max(n - p, 1))
    return dict(n=n, mean_actual=y.mean(), MAE=np.abs(e).mean(), RMSE=rmse,
                CV_RMSE_pct=100 * rmse / y.mean(), NMBE_pct=100 * e.sum() / (max(n - p, 1) * y.mean()))


def ashrae_table(j):
    rows = []
    for (m, s, z, l), g in j.groupby(["model", "split", "zone", "load_type"]):
        r = metrics(g["y_true"], g["y_pred"])
        r.update(model=m, split=s, zone=z, load_type=l,
                 recommendation=g["recommendation"].iloc[0],
                 level_shift_2025=bool(g["level_shift_2025"].iloc[0]))
        r["ashrae_cv_pass"] = r["CV_RMSE_pct"] <= ASHRAE_CV_MAX
        r["ashrae_nmbe_pass"] = abs(r["NMBE_pct"]) <= ASHRAE_NMBE_MAX
        r["ashrae_pass"] = bool(r["ashrae_cv_pass"] and r["ashrae_nmbe_pass"])
        rows.append(r)
    cols = ["model", "split", "zone", "load_type", "recommendation", "level_shift_2025", "n", "mean_actual",
            "MAE", "RMSE", "CV_RMSE_pct", "NMBE_pct", "ashrae_cv_pass", "ashrae_nmbe_pass", "ashrae_pass"]
    return pd.DataFrame(rows)[cols]


# ------------------------------------------------------------------ F6.6 error breakdown
def error_breakdown(j, by):
    """MAE as % of the mean actual per group, plus bias; computed per model and split."""
    g = j.assign(abs_err=(j["y_true"] - j["y_pred"]).abs(), err=j["y_true"] - j["y_pred"])
    out = g.groupby(["model", "split"] + by).agg(n=("err", "size"), mean_actual=("y_true", "mean"),
                                                 MAE=("abs_err", "mean"), bias=("err", "mean")).reset_index()
    out["MAE_pct_of_mean"] = 100 * out["MAE"] / out["mean_actual"].replace(0, np.nan)
    out["bias_pct_of_mean"] = 100 * out["bias"] / out["mean_actual"].replace(0, np.nan)
    return out


# ------------------------------------------------------------------ F7.1 anomaly candidates
def anomaly_candidates(j, top_days=40, top_hours=60, per_series=3):
    """Rank days and hours by error size, relative to each series' normal error (robust z-score),
    and attach context so every candidate gets a first explanation."""
    t = j[j["split"] != "train"].copy()
    t["err"] = t["y_true"] - t["y_pred"]
    grp = t.groupby(["model", "zone", "load_type"])["err"]
    med = grp.transform("median")
    mad = (t["err"] - med).abs().groupby([t["model"], t["zone"], t["load_type"]]).transform("median")
    # robust scale with a floor of 10 % of the series' mean level, so near-zero loads (lighting at night)
    # do not turn every small deviation into an "anomaly"
    lvl = t.groupby(["model", "zone", "load_type"])["y_true"].transform("mean").abs()
    t["robust_z"] = (t["err"] - med) / np.maximum(1.4826 * mad, 0.1 * lvl).replace(0, np.nan)
    t["date_local"] = t["timestamp_local"].dt.date

    def explain(r):
        why = []
        if r.get("is_holiday", 0): why.append(f"public holiday ({r.get('holiday_name', '')})")
        if r.get("is_weekend", 0): why.append("weekend")
        if r.get("is_august_low_use", 0): why.append("August low use")
        if r.get("flag_covid_2020", 0): why.append("COVID year 2020")
        if r.get("flag_temp_extreme", 0): why.append("extreme indoor temperature")
        if r.get("quality_share", 0) > 0.25: why.append(f"data quality flags in {r['quality_share']:.0%} of hours")
        if r.get("level_shift_2025", False): why.append("2025 level shift of this series")
        if not why: why.append("no context found: check on site (behaviour change or meter fault)")
        return "; ".join(why)

    # days
    d = t.groupby(["model", "split", "zone", "load_type", "date_local"]).agg(
        actual_wh=("y_true", "sum"), forecast_wh=("y_pred", "sum"), max_abs_robust_z=("robust_z", lambda s: s.abs().max()),
        is_holiday=("is_holiday", "max"), holiday_name=("holiday_name", lambda s: next((x for x in s if isinstance(x, str) and x), "")),
        is_weekend=("is_weekend", "max"), is_august_low_use=("is_august_low_use", "max"),
        flag_covid_2020=("flag_covid_2020", "max"), flag_temp_extreme=("flag_temp_extreme", "max"),
        quality_share=("flag_any_quality", "mean"), level_shift_2025=("level_shift_2025", "max")).reset_index()
    d["error_wh"] = d["actual_wh"] - d["forecast_wh"]
    d["error_pct"] = 100 * d["error_wh"] / d["forecast_wh"].replace(0, np.nan)
    d["direction"] = np.where(d["error_wh"] > 0, "more than forecast", "less than forecast")
    d = (d.sort_values("max_abs_robust_z", ascending=False)
          .groupby(["model", "zone", "load_type"]).head(per_series)       # at most N days per series
          .head(top_days))
    d["first_explanation"] = d.apply(explain, axis=1)
    # hours
    h = (t.assign(abs_z=t["robust_z"].abs()).sort_values("abs_z", ascending=False)
          .groupby(["model", "zone", "load_type"]).head(per_series).head(top_hours).copy())
    h["quality_share"] = h["flag_any_quality"].astype(float)
    h["first_explanation"] = h.apply(explain, axis=1)
    h = h[["model", "split", "zone", "load_type", "timestamp_local", "y_true", "y_pred", "err", "robust_z",
           "first_explanation"]].rename(columns={"err": "error_wh"})
    d = d[["model", "split", "zone", "load_type", "date_local", "actual_wh", "forecast_wh", "error_wh", "error_pct",
           "direction", "max_abs_robust_z", "first_explanation"]]
    return d, h


# ------------------------------------------------------------------ F6.7 sensitivity
def sensitivity_flags(j):
    rows = []
    for (m, s, z, l), g in j[j["split"] != "train"].groupby(["model", "split", "zone", "load_type"]):
        a = metrics(g["y_true"], g["y_pred"])
        b = metrics(g.loc[~g["flag_any_quality"], "y_true"], g.loc[~g["flag_any_quality"], "y_pred"])
        rows.append(dict(model=m, split=s, zone=z, load_type=l, share_flagged=g["flag_any_quality"].mean(),
                         CV_RMSE_all=a["CV_RMSE_pct"], CV_RMSE_unflagged=b["CV_RMSE_pct"],
                         NMBE_all=a["NMBE_pct"], NMBE_unflagged=b["NMBE_pct"]))
    out = pd.DataFrame(rows)
    out["CV_RMSE_change_pts"] = out["CV_RMSE_unflagged"] - out["CV_RMSE_all"]
    return out


# ------------------------------------------------------------------ figures
def figures(j, ash, out_dir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap
    SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e1e0d9"
    cmap = LinearSegmentedColormap.from_list("b", ["#f0efec", "#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"])
    plt.rcParams.update({"figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
                         "font.family": "DejaVu Sans", "text.color": INK, "axes.labelcolor": INK2,
                         "xtick.color": INK2, "ytick.color": INK2, "axes.edgecolor": "#c3c2b7"})
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for m, jm in j[j["split"] == "validation"].groupby("model"):
        jm = jm.assign(ape=(jm["y_true"] - jm["y_pred"]).abs())
        jm["series"] = jm["zone"] + " · " + jm["load_type"]
        piv = jm.groupby(["series", "hour_local"])["ape"].mean() / jm.groupby("series")["y_true"].mean()
        piv = (100 * piv).unstack()
        fig, ax = plt.subplots(figsize=(12, 0.42 * len(piv) + 1.8))
        fig.subplots_adjust(left=0.22, right=0.92, top=1 - 0.75 / fig.get_size_inches()[1], bottom=0.12)
        im = ax.imshow(piv.to_numpy(float), aspect="auto", cmap=cmap, vmin=0, vmax=min(100, np.nanpercentile(piv, 95)))
        ax.set_yticks(range(len(piv))); ax.set_yticklabels(piv.index, fontsize=8.5)
        ax.set_xticks(range(0, 24, 2)); ax.set_xticklabels([f"{h:02d}" for h in range(0, 24, 2)], fontsize=8.5)
        ax.set_xlabel("hour of day (local time)")
        for sp in ax.spines.values(): sp.set_visible(False)
        cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.01); cb.outline.set_visible(False)
        cb.set_label("MAE as % of the series' mean", color=INK2, fontsize=8.5)
        h = fig.get_size_inches()[1]
        fig.text(0.012, 1 - 0.12 / h, f"When is the forecast least reliable? Error by hour of day ({m}, validation 2022-H2)",
                 ha="left", va="top", fontsize=12.5, fontweight="bold")
        fig.text(0.012, 1 - 0.40 / h, "Darker = larger average error relative to the series' normal level.",
                 ha="left", va="top", fontsize=9.5, color=INK2)
        p = os.path.join(out_dir, f"F11_error_by_hour_{m}.png"); fig.savefig(p, dpi=170); plt.close(fig); paths.append(p)
    return paths


def write_excel(path, sheets):
    with pd.ExcelWriter(path, engine="xlsxwriter") as xw:
        hdr = xw.book.add_format({"bold": True, "bg_color": "#E8EEF7", "text_wrap": True, "valign": "top"})
        for name, df in sheets.items():
            df.to_excel(xw, sheet_name=name, index=False)
            ws = xw.sheets[name]
            ws.set_column(0, max(len(df.columns) - 1, 0), 16)
            for k, c in enumerate(df.columns):
                ws.write(0, k, c, hdr)
            ws.freeze_panes(1, 0)
            if len(df):
                ws.autofilter(0, 0, len(df), len(df.columns) - 1)


def split_rules_table():
    rows = [dict(split=s, start_utc=a, end_utc=b) for s, (a, b) in SPLITS.items()]
    df = pd.DataFrame(rows)
    df["rule"] = ["fit the model only on these hours",
                  "tune / choose the model here; never used for the final score",
                  "unseen test 1: only Jan-Feb 2023 exist",
                  "unseen test 2: NE, NW, SE only; report NW Lighting, NW HVAC, SE Lighting separately (level shift)"]
    return df


def format_table():
    return pd.DataFrame([
        ("timestamp_utc", "datetime", "Start of the forecast hour in UTC (same key as the clean dataset)"),
        ("zone", "text", "NE, NW, SE or SW"),
        ("load_type", "text", "Exactly as in the clean dataset, e.g. 'Plugs & Sockets'"),
        ("model", "text", "Short model name, e.g. seasonal_naive, sarimax, lightgbm_v2"),
        ("split", "text", "train, validation, test_2023 or test_2025"),
        ("y_true", "Wh", "energy_wh_model from the clean dataset v0.4"),
        ("y_pred", "Wh", "The forecast for that hour"),
    ], columns=["column", "unit", "meaning"])


if __name__ == "__main__":
    pred_path, clean_dir, out_dir = sys.argv[1], sys.argv[2], sys.argv[3]
    os.makedirs(out_dir, exist_ok=True)
    clean = load_clean(clean_dir)
    pred = load_predictions(pred_path)
    j, checks = check_predictions(pred, clean)
    print(checks.to_string(index=False))
    ash = ashrae_table(j)
    by_hour = error_breakdown(j, ["zone", "load_type", "hour_local"])
    by_season = error_breakdown(j, ["zone", "load_type", "season"])
    by_weekday = error_breakdown(j.assign(day_type=np.where(j["is_holiday"] == 1, "holiday",
                                                   np.where(j["is_weekend"] == 1, "weekend", "working day"))),
                                 ["zone", "load_type", "day_type"])
    by_zone = error_breakdown(j, ["load_type", "zone"])
    days, hours = anomaly_candidates(j)
    sens = sensitivity_flags(j)
    figs = figures(j, ash, out_dir)
    write_excel(os.path.join(out_dir, "TeamB_evaluation.xlsx"), {
        "Prediction_format": format_table(), "Split_rules": split_rules_table(), "Check_report": checks,
        "ASHRAE_table": ash, "Errors_by_hour": by_hour, "Errors_by_season": by_season,
        "Errors_by_daytype": by_weekday, "Errors_by_zone": by_zone,
        "Anomaly_days": days, "Anomaly_hours": hours, "Sensitivity_flags": sens})
    print("wrote", os.path.join(out_dir, "TeamB_evaluation.xlsx"), *figs)
