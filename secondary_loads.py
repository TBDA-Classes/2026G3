"""
F2.2 (Team B part) - characterise the secondary loads: emergency lighting, hand dryer, RACK.

For each series (2020-2023, hourly era, usable hours only):
  level      mean / median / 99th percentile of hourly energy (Wh)
  stability  coefficient of variation, share of hours near 0 Wh
  pattern    working-day daytime vs night, weekday vs weekend, highest vs lowest month
  predictability  CV(RMSE) of the naive-day and naive-week baselines (ASHRAE hourly limit = 30 %)
and a class: constant / event-driven, with a recommendation for Team D.

Run: python secondary_loads.py <clean_folder> <output_folder>
"""
import os, sys
import numpy as np
import pandas as pd
from team_b_eval import load_clean, metrics

clean_dir, out_dir = sys.argv[1], sys.argv[2]
os.makedirs(out_dir, exist_ok=True)
df = load_clean(clean_dir)
sec = df[df["load_type"].isin(["Emerg. Lighting", "Hand Dryer", "RACK"]) & (df["era"] == "hourly")].copy()
sec["hour"] = sec["timestamp_local"].dt.hour
sec["wd"] = sec["timestamp_local"].dt.dayofweek
sec["month"] = sec["timestamp_local"].dt.month

rows = []
for (z, l), g in sec.groupby(["zone", "load_type"]):
    e = g.set_index("timestamp_utc")["energy_wh_model"].asfreq("1h")
    v = e.dropna()
    if v.empty:
        continue
    day = g[g["hour"].between(8, 19) & (g["wd"] < 5)]["energy_wh_model"].mean()
    night = g[g["hour"] < 6]["energy_wh_model"].mean()
    wk, we = g[g["wd"] < 5]["energy_wh_model"].mean(), g[g["wd"] >= 5]["energy_wh_model"].mean()
    mon = g.groupby("month")["energy_wh_model"].mean()
    nd, nw = metrics(e, e.shift(24)), metrics(e, e.shift(168))
    cv = v.std() / v.mean() * 100
    near0 = (v < 1).mean()
    if near0 > 0.5 or cv > 200:
        cls = "event-driven"
        advice = "Not forecastable per hour; report daily totals and treat long high-power runs as anomaly candidates"
    else:
        cls = "constant"
        advice = "Naive baseline is already accurate; no complex model needed. Use as control group"
    rows.append(dict(zone=z, load_type=l, recommendation=g["recommendation"].iloc[0], usable_hours=len(v),
                     mean_wh=v.mean(), median_wh=v.median(), p99_wh=v.quantile(0.99), cv_pct=cv,
                     share_hours_near_0=near0,
                     daytime_vs_night=day / night if night > 0 else np.nan,
                     weekday_vs_weekend=wk / we if we > 0 else np.nan,
                     max_vs_min_month=mon.max() / mon.min() if mon.min() > 0 else np.nan,
                     cvrmse_naive_day_pct=nd["CV_RMSE_pct"], cvrmse_naive_week_pct=nw["CV_RMSE_pct"],
                     class_=cls, advice_for_team_D=advice))
tab = pd.DataFrame(rows).rename(columns={"class_": "class"})

# long high-power runs of the hand dryers (candidate anomalies for F7.1)
runs = []
for (z, l), g in sec[sec["load_type"] == "Hand Dryer"].groupby(["zone", "load_type"]):
    g = g.sort_values("timestamp_utc")
    hi = (g["power_w"] > 500).astype(int).to_numpy()
    grp = (np.diff(np.r_[0, hi]) == 1).cumsum() * hi
    for k in np.unique(grp[grp > 0]):
        idx = np.where(grp == k)[0]
        if len(idx) >= 3:
            s = g.iloc[idx]
            runs.append(dict(zone=z, load_type=l, start_local=s["timestamp_local"].iloc[0],
                             end_local=s["timestamp_local"].iloc[-1], hours=len(idx),
                             mean_power_w=s["power_w"].mean(), holiday=s["holiday_name"].fillna("").max(),
                             weekend=int(s["is_weekend"].max())))
runs = pd.DataFrame(runs).sort_values("hours", ascending=False) if runs else pd.DataFrame()

with pd.ExcelWriter(os.path.join(out_dir, "TeamB_F2.2_secondary_loads.xlsx"), engine="xlsxwriter") as xw:
    tab.to_excel(xw, sheet_name="Characterisation", index=False)
    runs.to_excel(xw, sheet_name="Hand_dryer_long_runs", index=False)
    for ws in xw.sheets.values():
        ws.set_column(0, 20, 16)

# figure: daily energy per secondary load
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e1e0d9"
COL = {"NE": "#2a78d6", "NW": "#eb6834", "SE": "#1baf7a", "SW": "#6250d6"}
plt.rcParams.update({"figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
                     "font.family": "DejaVu Sans", "text.color": INK, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.edgecolor": "#c3c2b7",
                     "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
                     "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False})
fig, axes = plt.subplots(3, 1, figsize=(12, 8.4), sharex=True)
fig.subplots_adjust(left=0.08, right=0.97, top=0.88, bottom=0.06, hspace=0.32)
for ax, l, scale, unit in zip(axes, ["RACK", "Emerg. Lighting", "Hand Dryer"], [1000, 1000, 1000], ["kWh/day"] * 3):
    for z, g in sec[sec["load_type"] == l].groupby("zone"):
        if g["recommendation"].iloc[0] == "Do not use":
            continue
        d = g.set_index("timestamp_local")["energy_wh_model"].resample("D").sum(min_count=12) / scale
        ax.plot(d.index, d.values, color=COL[z], lw=1.0, label=z)
    ax.set_title({"RACK": "RACK – constant load", "Emerg. Lighting": "Emergency lighting – constant load",
                  "Hand Dryer": "Hand dryers – event-driven, with long high-power runs in winter"}[l],
                 loc="left", fontsize=10.5, fontweight="bold")
    ax.set_ylabel(unit)
    ax.legend(ncol=4, loc="upper left", fontsize=8.5)
axes[-1].xaxis.set_major_locator(mdates.YearLocator()); axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
fig.text(0.012, 0.985, "Secondary loads: two are flat and easy to forecast, the hand dryers are not",
         ha="left", va="top", fontsize=13, fontweight="bold")
fig.text(0.012, 0.95, "Daily energy, 2020–2023, usable hours only. Naive day-ahead CV(RMSE): RACK 3–4 %, emergency lighting 10–14 %, hand dryers > 1,000 %.",
         ha="left", va="top", fontsize=9.5, color=INK2)
fig.savefig(os.path.join(out_dir, "F12_secondary_loads.png"), dpi=170)
print(tab.round(2).to_string())
print(runs.head(10).to_string())
