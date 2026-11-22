"""
Reference baselines in the agreed prediction format (Team B, TBDA).

Purpose: test the Team B evaluation toolkit (team_b_eval.py) before Team D delivers its models,
and give every later model a simple bar to beat. These are NOT Team D's models.

  naive_day      forecast for hour h = actual energy at hour h one day earlier (lag 24 h).
                 Valid for a day-ahead forecast issued at midnight: yesterday is fully known.
  naive_week     forecast for hour h = actual energy at hour h one week earlier (lag 168 h).

Only hours with usable_for_model = 1 are forecast; lags never cross the 902-day gap.
Run: python make_reference_baseline.py <clean_folder> <output_csv>
"""
import sys
import pandas as pd
from team_b_eval import SPLITS, TEST_2025_ZONES, load_clean

clean_dir, out_csv = sys.argv[1], sys.argv[2]
df = load_clean(clean_dir)
df = df[df["series_excluded"] == 0].sort_values(["zone", "load_type", "era", "timestamp_utc"])
rows = []
for (z, l, era), g in df.groupby(["zone", "load_type", "era"]):
    s = g.set_index("timestamp_utc")["energy_wh_model"]
    s = s.asfreq("1h")
    for name, lag in [("naive_day", 24), ("naive_week", 168)]:
        p = pd.DataFrame({"y_true": s, "y_pred": s.shift(lag)}).dropna().reset_index()
        p["zone"], p["load_type"], p["model"] = z, l, name
        rows.append(p)
pred = pd.concat(rows, ignore_index=True)
pred["split"] = None
for sp, (a, b) in SPLITS.items():
    pred.loc[pred["timestamp_utc"].between(pd.Timestamp(a), pd.Timestamp(b)), "split"] = sp
pred = pred[pred["split"].notna()]
pred = pred[~((pred["split"] == "test_2025") & ~pred["zone"].isin(TEST_2025_ZONES))]
pred[["timestamp_utc", "zone", "load_type", "model", "split", "y_true", "y_pred"]].to_csv(out_csv, index=False)
print(len(pred), "rows written to", out_csv)
