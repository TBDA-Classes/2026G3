"""
T37 side check - is the day-ahead GBM of GBM_forallzones.ipynb leak-free?
(TBDA DataPack, CeDInt floor 1)  Author: Riccardo Tardanico

Why: T37 needs a day-ahead (1-day) reference to measure how accuracy decays with the
horizon. Before using the GBM of GBM_forallzones.ipynb as that reference, its features
are checked for information that would NOT be known when the forecast is issued.

Findings checked here (NW HVAC, same data, same model settings as the notebook):
  1. roll_mean_24 = rolling(24).mean() at hour t INCLUDES y(t) itself (target leakage).
  2. Lags are shifted by ROW, not by time; the series is complete on the hourly grid
     inside each period, so this only matters across the 902-day gap (lags of the first
     week of 2025 come from February 2023). Minor, not tested separately.
  3. temp_c, temp_lag1, temp_lag2, occupancy, lum_lux are indoor readings of hour t/t-1/t-2,
     which are not known 24 h ahead.
The script refits the notebook model three ways and prints CV(RMSE)/NMBE on test_2023
and test_2025:
  A  notebook features as they are
  B  same, but roll_mean_24 shifted by 24 h (ends at t-24)
  C  B + indoor variables lagged 24 h (fully day-ahead)

Run: python T37_check_gbm_leakage.py <path to T32_cedint_f1_model_ready.csv.gz>
"""
import sys
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor


def metrics(y, p):
    y, p = np.asarray(y, float), np.asarray(p, float)
    rmse = np.sqrt(np.mean((y - p) ** 2))
    return 100 * rmse / y.mean(), 100 * np.sum(y - p) / (len(y) * y.mean())   # D1 sign convention


def run(path, zone="NW", load="HVAC"):
    df = pd.read_csv(path, parse_dates=["timestamp_utc", "timestamp_local"])
    s = df[(df.zone == zone) & (df.load_type == load)].sort_values("timestamp_local").copy()
    # ---- notebook features (copied from GBM_forallzones.ipynb) ----
    s["energy_lag_24"] = s["energy_wh_model"].shift(24)
    s["energy_lag_168"] = s["energy_wh_model"].shift(168)
    s["temp_lag1"] = s["temp_c"].shift(1)
    s["temp_lag2"] = s["temp_c"].shift(2)
    s["roll_mean_24"] = s["energy_wh_model"].rolling(window=24).mean()
    s["dh_heat"] = (18 - s["temp_c"]).clip(lower=0)
    s["dh_cool"] = (s["temp_c"] - 24).clip(lower=0)
    # ---- corrected variants ----
    s["roll_mean_24_shift24"] = s["roll_mean_24"].shift(24)
    for c in ["temp_c", "occupancy", "lum_lux", "dh_heat", "dh_cool"]:
        s[c + "_l24"] = s[c].shift(24)
    s = s.dropna(subset=["energy_wh_model", "energy_lag_168", "roll_mean_24"])

    cal = ["hour_local", "dayofweek_local", "month_local", "is_weekend", "is_holiday"]
    feats = {
        "A notebook as is": cal + ["temp_c", "dh_cool", "dh_heat", "temp_lag1", "temp_lag2", "occupancy",
                                   "lum_lux", "energy_lag_24", "energy_lag_168", "roll_mean_24"],
        "B roll_mean shifted 24 h": cal + ["temp_c", "dh_cool", "dh_heat", "temp_lag1", "temp_lag2", "occupancy",
                                           "lum_lux", "energy_lag_24", "energy_lag_168", "roll_mean_24_shift24"],
        "C fully day-ahead": cal + ["temp_c_l24", "dh_cool_l24", "dh_heat_l24", "occupancy_l24", "lum_lux_l24",
                                    "energy_lag_24", "energy_lag_168", "roll_mean_24_shift24"],
    }
    rows = []
    for name, f in feats.items():
        X = s[f].fillna(0)
        y = s["energy_wh_model"]
        tr = s["include_train"] == 1
        m = GradientBoostingRegressor(n_estimators=100, learning_rate=0.1, max_depth=4, random_state=42)
        m.fit(X[tr], y[tr])
        for yr in (2023, 2025):
            te = (s["include_eval"] == 1) & (s["timestamp_local"].dt.year == yr)
            cv, nmbe = metrics(y[te], m.predict(X[te]))
            rows.append({"variant": name, "test": yr, "n": int(te.sum()),
                         "CV_RMSE_pct": round(cv, 1), "NMBE_pct": round(nmbe, 1)})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    out = run(sys.argv[1] if len(sys.argv) > 1 else "T32_cedint_f1_model_ready.csv.gz")
    print(out.to_string(index=False))
    out.to_csv("T37_check_gbm_leakage_results.csv", index=False)
