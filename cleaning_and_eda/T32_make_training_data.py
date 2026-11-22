"""
Model-ready training data (TBDA DataPack, Team B) - supports T29/T32 (F1.2, F6.3)

Builds on the clean dataset v0.4 of clean_cedint.py. NOTHING IS DELETED: every hour of every
in-scope series stays in the output file. Two 0/1 columns say whether an hour may be used:
    include_train  -> rows the models may LEARN from (split = train)
    include_eval   -> rows on which validation and test SCORES are computed
and `exclusion_reason` says why a row is left out. See TRAINING_DATA_METHODOLOGY.md.

Run: python make_training_data.py <clean_folder> <output_folder>
"""
import os, sys
import numpy as np
import pandas as pd

SPLITS = {                                    # same periods as team_b_eval.py (agreed with Team D)
    "train":      ("2020-06-01", "2022-06-30 23:00"),
    "validation": ("2022-07-01", "2022-12-31 23:00"),
    "test_2023":  ("2023-01-01", "2023-02-28 23:00"),
    "test_2025":  ("2025-08-18", "2025-10-13 23:00"),
}
PRIORITY = {"HVAC", "Lighting", "Plugs & Sockets"}          # core forecast targets (backlog section 3)
CONSTANT_SECONDARY = {"RACK", "Emerg. Lighting"}              # constant loads: forecastable, control group
EVENT_DRIVEN = {"Hand Dryer"}                                 # F2.2: not forecastable per hour
TRAIN_ONLY_FLAGS = {                                          # target uncertain -> do not learn from it
    "flag_power_energy_mismatch": "R5 energy and power disagree (target uncertain)",
    "flag_power_spike": "R6 isolated power spike (outlier)",
}
FEATURES = ["hour_local", "dayofweek_local", "month_local", "is_weekend", "is_holiday",
            "is_august_low_use", "flag_covid_2020", "temp_c", "hum_pct", "lum_lux", "occupancy",
            "lag_24h", "lag_168h"]


def build(df):
    df = df.copy()
    # scope of hourly modelling
    df["model_scope"] = np.select(
        [df["series_excluded"] == 1, df["load_type"].isin(EVENT_DRIVEN),
         df["load_type"].isin(PRIORITY), df["load_type"].isin(CONSTANT_SECONDARY)],
        ["excluded (dead series)", "daily totals only (event-driven)", "priority", "secondary (constant)"],
        "other")
    # split by date
    df["split"] = "unused"
    for s, (a, b) in SPLITS.items():
        df.loc[df["timestamp_utc"].between(pd.Timestamp(a), pd.Timestamp(b)), "split"] = s
    df.loc[(df["split"] == "test_2025") & (df["zone"] == "SW"), "split"] = "unused"

    # calendar features from LOCAL time (raw timestamps are UTC)
    df["hour_local"] = df["timestamp_local"].dt.hour
    df["dayofweek_local"] = df["timestamp_local"].dt.dayofweek
    df["month_local"] = df["timestamp_local"].dt.month

    # lagged target (past values only, same series and same era, never across the 902-day gap)
    df = df.sort_values(["zone", "load_type", "era", "timestamp_utc"])
    grp = df.groupby(["zone", "load_type", "era"], sort=False)["energy_wh_model"]
    df["lag_24h"] = grp.shift(24)
    df["lag_168h"] = grp.shift(168)

    # exclusion reasons, in priority order (first one that applies is recorded)
    reason = pd.Series("", index=df.index, dtype=object)

    def mark(mask, text):
        reason[(reason == "") & mask] = text

    mark(df["split"] == "unused", "R0 outside the agreed periods (Apr-May 2020 lockdown, SW 2025)")
    mark(df["model_scope"].str.startswith("excluded"), "R1 dead series (SE Projector)")
    mark(df["usable_for_model"] == 0, "R1 series/period rated 'Do not use'")
    mark(df["energy_wh_model"].isna(), "R2 no valid energy value (missing, zero record, implausible)")
    mark(df["energy_source"] == "interpolated", "R3 interpolated value, not a measurement")
    mark(df["model_scope"].str.startswith("daily"), "R4 event-driven load, not modelled per hour")
    eval_ok = reason == ""                                     # valid target -> may be scored
    for col, text in TRAIN_ONLY_FLAGS.items():
        mark((df["split"] == "train") & (df[col] == 1), text)
    df["exclusion_reason"] = reason
    df["include_train"] = ((df["split"] == "train") & (reason == "")).astype(int)
    df["include_eval"] = (df["split"].isin(["validation", "test_2023", "test_2025"]) & eval_ok).astype(int)
    # experiment variant: training without the COVID-affected year 2020
    df["include_train_no2020"] = (df["include_train"].eq(1) & df["flag_covid_2020"].eq(0)).astype(int)
    # context columns for reporting
    df["series_caution"] = (df["recommendation"] == "Use with caution").astype(int)
    df["level_shift_2025"] = (df["split"].eq("test_2025") &
                              pd.Series(list(zip(df["zone"], df["load_type"])), index=df.index)
                              .isin([("NW", "Lighting"), ("NW", "HVAC"), ("SE", "Lighting")])).astype(int)
    return df


def summary(df):
    s = df.groupby(["zone", "load_type", "model_scope", "split"]).agg(
        hours=("timestamp_utc", "size"), include_train=("include_train", "sum"),
        include_train_no2020=("include_train_no2020", "sum"), include_eval=("include_eval", "sum")).reset_index()
    r = (df[df["exclusion_reason"] != ""].groupby(["zone", "load_type", "split", "exclusion_reason"])
         .size().rename("hours_excluded").reset_index())
    totals = (df[df["exclusion_reason"] != ""].groupby(["split", "exclusion_reason"]).size()
              .rename("hours_excluded").reset_index())
    return s, r, totals


if __name__ == "__main__":
    clean_dir, out_dir = sys.argv[1], sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    df = pd.read_csv(os.path.join(clean_dir, "cedint_f1_hourly_clean.csv.gz"),
                     parse_dates=["timestamp_utc", "timestamp_local"], low_memory=False)
    m = build(df)
    keep = ["timestamp_utc", "timestamp_local", "zone", "zone_code", "load_type", "n_devices", "era",
            "split", "model_scope", "recommendation", "series_caution", "level_shift_2025",
            "include_train", "include_train_no2020", "include_eval", "exclusion_reason",
            "energy_wh_model", "energy_source"] + FEATURES
    m[keep].to_csv(os.path.join(out_dir, "cedint_f1_model_ready.csv.gz"), index=False,
                   float_format="%.4f", compression="gzip")
    s, r, totals = summary(m)
    rules = pd.DataFrame([
        ("R0", "Outside the agreed periods", "train + eval", "Before 1 Jun 2020 (lockdown) and SW in 2025 are not part of any split"),
        ("R1", "Dead series or 'Do not use'", "train + eval", "SE Projector (always 0 W); SW 2025 and NW Hand Dryer 2025 rated 'Do not use'"),
        ("R2", "No valid energy value", "train + eval", "Missing hour, zero record or implausible counter step: there is no true value"),
        ("R3", "Interpolated value", "train + eval", "Filled in for gaps <= 3 h; not a measurement, so neither learnt from nor scored"),
        ("R4", "Event-driven load", "train + eval", "Hand dryers: hourly CV(RMSE) > 1,000 % (F2.2); report daily totals instead"),
        ("R5", "Energy and power disagree", "train only", "Counter energy and power x 1 h differ > 20 %: the true value is uncertain"),
        ("R6", "Isolated power spike", "train only", "Hampel outlier; kept in validation/test so the score stays honest"),
        ("V1", "Variant: without 2020", "train only (experiment)", "include_train_no2020: test whether the COVID year biases the model"),
    ], columns=["rule", "what", "applies to", "why"])
    with pd.ExcelWriter(os.path.join(out_dir, "training_data_summary.xlsx"), engine="xlsxwriter") as xw:
        for name, d in [("Rules", rules), ("Totals_by_reason", totals), ("Per_series_split", s),
                        ("Per_series_reason", r)]:
            d.to_excel(xw, sheet_name=name, index=False)
            xw.sheets[name].set_column(0, len(d.columns) - 1, 18)
        xw.sheets["Rules"].set_column(3, 3, 90)
        xw.sheets["Totals_by_reason"].set_column(1, 1, 60)
        xw.sheets["Per_series_reason"].set_column(3, 3, 60)
    print(m.groupby("split")[["include_train", "include_train_no2020", "include_eval"]].sum())
    print(totals.to_string(index=False))
