"""Figures F1-F10 for the Team B data-quality report.

Reads only the output folder of clean_cedint.py (including its raw_cache/ sub-folder).
Run: python make_figures.py <pipeline_output_folder> <figures_folder>
"""
import sys, os
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.colors import LinearSegmentedColormap

WORK = sys.argv[1] if len(sys.argv) > 1 else "cleaned"
FIG = sys.argv[2] if len(sys.argv) > 2 else "figures"
RAWPK = os.path.join(WORK, "raw_cache")
os.makedirs(FIG, exist_ok=True)

SURF, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
S1, S2, S3, S4, S7 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#6250d6"
GOOD, WARN, CRIT, NEUTRAL = "#0ca30c", "#fab219", "#d03b3b", "#c3c2b7"
SEQ = LinearSegmentedColormap.from_list("blue", ["#f0efec", "#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"])

plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "font.family": "DejaVu Sans", "font.size": 10, "text.color": INK,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "axes.linewidth": 0.8,
    "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelcolor": INK2, "ytick.labelcolor": INK2,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False,
    "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left", "axes.titlecolor": INK,
})


def title(fig, t, sub=None):
    h = fig.get_size_inches()[1]
    fig.text(0.012, 1 - 0.12 / h, t, ha="left", va="top", fontsize=13, fontweight="bold", color=INK)
    if sub:
        fig.text(0.012, 1 - 0.42 / h, sub, ha="left", va="top", fontsize=9.5, color=INK2, wrap=True)


def save(fig, name):
    fig.savefig(os.path.join(FIG, name), dpi=170)
    plt.close(fig)
    print("saved", name)


H = pd.read_pickle(os.path.join(WORK, "hourly_clean.pkl"))
Q = pd.read_pickle(os.path.join(WORK, "quality.pkl"))
C = pd.read_pickle(os.path.join(WORK, "consistency.pkl"))
M = pd.read_pickle(os.path.join(WORK, "minute_flagged.pkl"))
H["series"] = H["zone"] + " · " + H["load_type"]
order = (H[["zone", "load_type", "series"]].drop_duplicates().sort_values(["zone", "load_type"])["series"].tolist())

# ------------------------------------------------------------ F1 coverage heatmap (F6.1)
H["month"] = H["timestamp_utc"].dt.to_period("M")
cov = H.groupby(["series", "month"])["energy_wh"].apply(lambda s: s.notna().mean()).unstack()
months = pd.period_range("2020-04", "2025-10", freq="M")
cov = cov.reindex(index=order, columns=months)
keep = [m for m in months if (m <= pd.Period("2023-02", "M")) or (m >= pd.Period("2025-08", "M"))]
gap_at = keep.index(pd.Period("2025-08", "M"))
cov = cov[keep]
fig, ax = plt.subplots(figsize=(12, 6.6))
fig.subplots_adjust(left=0.2, right=0.9, top=0.86, bottom=0.12)
arr = cov.to_numpy(dtype=float).copy()
pj = order.index("SE · Projector"); arr[pj, :] = np.nan
im = ax.imshow(arr, aspect="auto", cmap=SEQ, vmin=0, vmax=1, interpolation="nearest")
ax.add_patch(plt.Rectangle((-0.5, pj - 0.5), arr.shape[1], 1, facecolor=SURF, edgecolor=AXIS, hatch="////", lw=0.5))
ax.text(arr.shape[1] / 2, pj, "excluded: always 0 W (dead series)", ha="center", va="center", fontsize=8.5, color=INK2,
        bbox=dict(facecolor=SURF, edgecolor="none", pad=1.5))
ax.set_yticks(range(len(order))); ax.set_yticklabels(order, fontsize=8.5)
xt = [i for i, m in enumerate(keep) if (m.month in (1, 7) and abs(i - gap_at) > 2) or i == gap_at]
ax.set_xticks(xt); ax.set_xticklabels([str(keep[i]) for i in xt], fontsize=8, rotation=0)
ax.axvline(gap_at - 0.5, color=INK, lw=1.2)
ax.text(gap_at - 0.6, -0.9, "902-day gap  ", ha="right", va="bottom", fontsize=8.5, color=INK2)
ax.grid(False)
for s in ax.spines.values(): s.set_visible(False)
cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.01); cb.outline.set_visible(False)
cb.set_label("share of hours with a valid energy value", color=INK2, fontsize=8.5)
cb.ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1))
title(fig, "Where data is missing: valid energy per series and month",
      "Pale cells = hours without a usable value (missing rows, zero records, partial sums, resets). SW RACK stops in Dec 2021; SW minute data (right) is mostly unusable.")
save(fig, "F1_coverage_heatmap.png")

# ------------------------------------------------------------ F2 sampling regime
fig, ax = plt.subplots(figsize=(12, 4.2))
fig.subplots_adjust(left=0.13, right=0.97, top=0.8, bottom=0.14)
for z, col in zip(["NE", "NW", "SE", "SW"], [S1, S2, S3, S7]):
    d = pd.read_pickle(os.path.join(RAWPK, f"{z}_HVAC.pkl" if z != "SW" else "SW_Lighting.pkl"))
    t = pd.to_datetime(d["Timestamp"])
    per_day = t.dt.floor("D").value_counts().sort_index()
    per_day = per_day.reindex(pd.date_range(per_day.index.min(), per_day.index.max(), freq="D"), fill_value=0)
    ax.plot(per_day.index, per_day.values, color=col, lw=1.4, label=z)
ax.set_yscale("symlog", linthresh=10)
ax.set_yticks([0, 24, 100, 1440]); ax.set_yticklabels(["0", "24 (hourly)", "100", "1,440 (per minute)"])
ax.set_ylabel("")
ax.xaxis.set_major_locator(mdates.YearLocator()); ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax.legend(ncol=4, loc="upper left", bbox_to_anchor=(0, 1.02), fontsize=9)
ax.annotate("no data Mar 2023 – Aug 2025", xy=(pd.Timestamp("2024-04-01"), 1), ha="center", fontsize=9, color=INK2)
title(fig, "Two sampling regimes: hourly 2020–2023, per minute in 2025",
      "Rows per day for one sheet per zone. Old data was kept by the retention policy only as hourly averages; SE and SW minute data have many missing minutes.")
save(fig, "F2_sampling_regimes.png")

# ------------------------------------------------------------ F3 counter problems (hourly + minute example)
fig, axes = plt.subplots(1, 2, figsize=(12, 4.4), gridspec_kw={"width_ratios": [1.35, 1]})
fig.subplots_adjust(left=0.07, right=0.98, top=0.78, bottom=0.15, wspace=0.22)
d = pd.read_pickle(os.path.join(RAWPK, "SE_HVAC.pkl")); d["t"] = pd.to_datetime(d["Timestamp"])
w = d[(d.t >= "2020-08-01") & (d.t < "2020-10-01")].set_index("t")
hh = H[(H.zone == "SE") & (H.load_type == "HVAC")].set_index("timestamp_utc").loc["2020-08-01":"2020-09-30"]
ax = axes[0]
wg = w["Er"].asfreq("1h")
ax.plot(wg.index, wg / 1000, color=S1, lw=1.2, label="raw counter Er (breaks = missing hours)")
zr = w[w["Er"] == 0]; ax.scatter(zr.index, zr["Er"] / 1000, s=22, color=S2, zorder=3, label="zero record (all values 0)", edgecolor=SURF, lw=0.8)
part = hh[hh["flag_partial_sum"] == 1].index
pw = w.loc[w.index.isin(part)]
ax.scatter(pw.index, pw["Er"] / 1000, s=22, color=S7, zorder=3, label="partial sum (dips, then recovers)", edgecolor=SURF, lw=0.8)
ax.set_ylabel("cumulative energy (kWh)"); ax.legend(loc="upper left", fontsize=8.5)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
ax.set_title("Hourly era · SE HVAC, Aug–Sep 2020", fontsize=10.5)
mm = M[(M.zone == "NW") & (M.load_type == "Plugs & Sockets")].set_index("t").loc["2025-09-10 09:00":"2025-09-10 12:00"]
ax = axes[1]
ok = mm[mm.counter_status == "ok"]; pa = mm[mm.counter_status != "ok"]
ax.scatter(ok.index, ok["Er"] / 1000, s=10, color=S1, label="complete minute (used)", zorder=3)
ax.scatter(pa.index, pa["Er"] / 1000, s=10, color=S7, label="partial minute (excluded)", zorder=3)
ax.set_ylabel("cumulative energy (kWh)"); ax.legend(loc="lower left", fontsize=8.5)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
ax.set_title("Minute era · NW Plugs & Sockets, 10 Sep 2025", fontsize=10.5)
title(fig, "Counter drops are missing devices, not real meter resets",
      "Left: one-hour drops to 0 or to about half, then back. Right: within one hour the sum jumps between levels because only some devices report in each minute.")
save(fig, "F3_counter_problems.png")

# ------------------------------------------------------------ F4 negative power
neg = []
for k in order:
    z, l = k.split(" · ")
    fn = f"{z}_{l.replace(' ', '_').replace('&', 'and').replace('.', '')}.pkl"
    d = pd.read_pickle(os.path.join(RAWPK, fn))
    neg.append(dict(series=k, share=(d["W"] < 0).mean(), large=(d["W"] < -5).mean()))
neg = pd.DataFrame(neg).sort_values("share")
fig, ax = plt.subplots(figsize=(11, 5.6))
fig.subplots_adjust(left=0.22, right=0.95, top=0.84, bottom=0.1)
y = np.arange(len(neg))
colors = [S2 if s.startswith("NW · Emerg") else S1 for s in neg["series"]]
ax.barh(y, neg["share"], color=colors, height=0.62)
large = np.where(neg["series"].str.startswith("NW · Emerg"), 0, neg["large"])
ax.barh(y, large, color=INK2, height=0.62)
ax.set_yticks(y); ax.set_yticklabels(neg["series"], fontsize=8.5)
ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1)); ax.set_xlim(0, 1.05)
ax.grid(axis="y", visible=False)
for yi, (s, sh, lg) in enumerate(zip(neg["series"], neg["share"], neg["large"])):
    if sh > 0.05:
        ax.text(sh + 0.01, yi, f"{sh:.0%}", va="center", fontsize=8.5, color=INK2)
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color=S1, label="small negatives (−5…0 W): noise around 0 → set to 0"),
                   Patch(color=INK2, label="below −5 W in a normal series → NaN in clean column"),
                   Patch(color=S2, label="whole series negative: reversed clamp → sign flipped")],
          loc="lower right", fontsize=8.5)
title(fig, "Negative power: one reversed clamp, the rest is noise around zero",
      "Share of raw rows (both periods) with W < 0. Idle loads (lighting at night, hand dryers) jitter ±2 W around zero.")
save(fig, "F4_negative_power.png")

# ------------------------------------------------------------ F5 environment missing over time
env = H[H.load_type.isin(["HVAC", "Lighting"])].drop_duplicates(["zone", "timestamp_utc"])
fig, ax = plt.subplots(figsize=(12, 3.8))
fig.subplots_adjust(left=0.07, right=0.97, top=0.78, bottom=0.14)
for z, col in zip(["NE", "NW", "SE", "SW"], [S1, S2, S3, S7]):
    e = env[env.zone == z].set_index("timestamp_utc")
    miss = (e["flag_env_missing"].astype(float).where(e["flag_missing_hour"] == 0)).resample("MS").mean()
    for era_mask in [miss.index < "2024-01-01", miss.index >= "2024-01-01"]:
        ax.plot(miss.index[era_mask], miss[era_mask], color=col, lw=1.5, marker="o", ms=3, label=z if era_mask[0] else None)
ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1)); ax.set_ylim(-0.03, 1.05)
ax.set_ylabel("hours without env. data"); ax.legend(ncol=4, loc="center left", fontsize=9)
title(fig, "Environmental sensors: NE has none, the others are nearly complete until 2025",
      "Monthly share of hours where Temp = Hum = 0 (missing reading). In the 2025 minute data the env. readings drop out more often.")
save(fig, "F5_env_missing.png")

# ------------------------------------------------------------ F6 temperature extremes vs error
fig, axes = plt.subplots(1, 2, figsize=(12, 4.3), gridspec_kw={"width_ratios": [1.6, 1]})
fig.subplots_adjust(left=0.07, right=0.98, top=0.78, bottom=0.14, wspace=0.2)
ax = axes[0]
for z, col in zip(["NW", "SE", "SW"], [S2, S3, S7]):
    e = env[(env.zone == z) & (env.era == "hourly")].set_index("timestamp_utc")["temp_c"].resample("D").mean()
    ax.plot(e.index, e.values, color=col, lw=1.0, label=z)
ax.axhspan(35, 45, color=WARN, alpha=0.15, lw=0); ax.axhspan(0, 10, color=WARN, alpha=0.15, lw=0)
ax.text(pd.Timestamp("2020-04-15"), 36, "extreme but plausible (> 35 °C): flagged, kept", fontsize=8.5, color=INK2)
ax.text(pd.Timestamp("2021-02-10"), 3.5, "< 10 °C: Christmas closure + storm Filomena, Jan 2021", fontsize=8.5, color=INK2)
ax.set_ylim(0, 45); ax.set_ylabel("daily mean indoor temperature (°C)")
ax.legend(ncol=3, loc="upper right", fontsize=9)
ax.set_title("Clean temp_c, hourly era", fontsize=10.5)
ax = axes[1]
d = pd.read_pickle(os.path.join(RAWPK, "SW_Lighting.pkl")); d["t"] = pd.to_datetime(d["Timestamp"])
s = d[(d.t >= "2022-02-25") & (d.t < "2022-03-12") & (d.Temp != 0)].set_index("t")["Temp"]
ax.plot(s.index, s.values, color=S7, lw=1.0)
bad = s[s > 50]; ax.scatter(bad.index, bad.values, color=CRIT, s=12, zorder=3, label="> 50 °C: sensor error → NaN")
ax.set_yscale("log"); ax.set_ylabel("raw Temp (°C, log scale)"); ax.legend(loc="center right", fontsize=8.5)
ax.xaxis.set_major_locator(mdates.DayLocator(interval=4)); ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
ax.set_title("Raw SW Temp, early March 2022", fontsize=10.5)
title(fig, "Real extremes are kept and flagged; impossible values are removed from the clean column",
      "Left: the cold winter 2020–21 and the Aug 2021 heat wave appear in all zones at once, so they are real. Right: ~850 °C for a week in SW is a sensor error.")
save(fig, "F6_temperature.png")

# ------------------------------------------------------------ F7 consistency pass rates (F6.2)
c = C[C.era == "hourly"].copy(); c["series"] = c.zone + " · " + c.load_type
q = Q[Q.era == "hourly"].copy(); q["series"] = q.zone + " · " + q.load_type
c = c.merge(q[["series", "pct_valid_energy"]], on="series").sort_values("power_vs_energy_pass")
fig, ax = plt.subplots(figsize=(11, 5.8))
fig.subplots_adjust(left=0.22, right=0.95, top=0.8, bottom=0.1)
y = np.arange(len(c))
ax.hlines(y, c[["power_vs_energy_pass", "pct_valid_energy"]].min(axis=1), c[["power_vs_energy_pass", "pct_valid_energy"]].max(axis=1), color=GRID, lw=2)
ax.scatter(c["power_vs_energy_pass"], y, s=46, color=S1, label="power and energy agree (within 20%)", zorder=3, edgecolor=SURF, lw=1)
ax.scatter(c["pct_valid_energy"], y, s=46, color=S2, marker="D", label="hours with a valid energy value", zorder=3, edgecolor=SURF, lw=1)
ax.set_yticks(y); ax.set_yticklabels(c["series"], fontsize=8.5); ax.grid(axis="y", visible=False)
ax.set_xlim(0.5, 1.02); ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1))
ax.axvline(0.8, color=AXIS, lw=1); ax.text(0.802, -0.7, "80% = 'Use' threshold", fontsize=8.5, color=INK2)
ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, fontsize=9)
title(fig, "Do the measurements match? Hourly era passes; SW has the least usable hours",
      "Hourly era, per series: share of hours where energy from the counter matches average power, and share of hours with a valid energy value.\nApparent ≥ active power holds in ≥ 99% of hours, except SE Lighting (90%).")
save(fig, "F7_consistency.png")

# ------------------------------------------------------------ F8 recommendation matrix
rec_col = {"Use": GOOD, "Use with caution": WARN, "Do not use": CRIT}
Q["series"] = Q.zone + " · " + Q.load_type
fig, ax = plt.subplots(figsize=(8.6, 6.4))
fig.subplots_adjust(left=0.27, right=0.97, top=0.84, bottom=0.05)
for i, s in enumerate(order):
    for j, era in enumerate(["hourly", "minute"]):
        r = Q[(Q.series == s) & (Q.era == era)]
        if not len(r):
            ax.text(j, i, "no data", ha="center", va="center", fontsize=8.5, color=MUTED); continue
        rec = r["recommendation"].iloc[0]
        ax.add_patch(plt.Rectangle((j - 0.46, i - 0.4), 0.92, 0.8, color=rec_col[rec], alpha=0.22, lw=0))
        mark = {"Use": "✓", "Use with caution": "!", "Do not use": "✕"}[rec]
        ax.text(j, i, f"{mark}  {rec}", ha="center", va="center", fontsize=8.5, color=INK)
ax.set_xlim(-0.5, 1.5); ax.set_ylim(len(order) - 0.5, -0.5)
ax.set_xticks([0, 1]); ax.set_xticklabels(["2020–2023 (hourly)", "2025 (minute → hourly)"], fontsize=9)
ax.xaxis.tick_top(); ax.set_yticks(range(len(order))); ax.set_yticklabels(order, fontsize=8.5)
ax.grid(False)
for sp in ax.spines.values(): sp.set_visible(False)
ax.tick_params(length=0)
title(fig, "Which data to use", "Use: ≥ 80% valid energy and power/energy agree. Caution: ≥ 60%. SW 2025 and the projector are not usable.")
save(fig, "F8_recommendation_matrix.png")

# ------------------------------------------------------------ F9 high vs low frequency: one day
fig, axes = plt.subplots(1, 2, figsize=(12, 4.2))
fig.subplots_adjust(left=0.07, right=0.98, top=0.78, bottom=0.15, wspace=0.18)
for ax, (z, l) in zip(axes, [("NW", "Lighting"), ("NW", "Plugs & Sockets")]):
    mm = M[(M.zone == z) & (M.load_type == l)].set_index("t").loc["2025-09-10 04:00":"2025-09-10 20:00"]
    ok = mm[mm.counter_status == "ok"]
    ax.plot(ok.index, ok["W_s"], color=S1, lw=0.7, alpha=0.75, label="per minute (complete minutes)")
    hh = H[(H.zone == z) & (H.load_type == l)].set_index("timestamp_utc").loc["2025-09-10 04:00":"2025-09-10 19:00"]
    ax.step(hh.index, hh["power_w"], where="post", color=S2, lw=2, label="hourly average (used)")
    ax.set_title(f"{z} · {l}, 10 Sep 2025 (UTC)", fontsize=10.5)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M")); ax.set_ylabel("power (W)")
    ax.legend(loc="upper left", fontsize=8.5)
title(fig, "Hourly averages keep the daily pattern; minute detail is mostly short-term noise",
      "The forecast target is energy per hour, so the hourly average is the right resolution.")
save(fig, "F9_frequency_day.png")

# ------------------------------------------------------------ F10 2025 vs 2021-22 level
rows = []
for k in order:
    z, l = k.split(" · ")
    h = H[(H.zone == z) & (H.load_type == l)]
    md = h.timestamp_utc.dt.strftime("%m-%d")
    win = (md >= "08-18") & (md <= "10-13")
    a = h[win & (h.era == "hourly") & h.timestamp_utc.dt.year.isin([2021, 2022])]["energy_wh"].mean()
    b = h[win & (h.era == "minute")]["energy_wh"].mean()
    if pd.notna(a) and pd.notna(b) and a > 0.5:
        rows.append(dict(series=k, ratio=b / a))
r = pd.DataFrame(rows).sort_values("ratio")
fig, ax = plt.subplots(figsize=(11, 5.4))
fig.subplots_adjust(left=0.22, right=0.95, top=0.84, bottom=0.1)
y = np.arange(len(r))
col = [S1 if 0.67 <= v <= 1.5 else S2 for v in r["ratio"]]
ax.hlines(y, 1, r["ratio"], color=col, lw=2)
ax.scatter(r["ratio"], y, color=col, s=40, zorder=3, edgecolor=SURF, lw=1)
ax.set_xscale("log"); ax.axvline(1, color=AXIS, lw=1)
ax.set_xticks([0.25, 0.5, 1, 2, 4, 10, 50]); ax.set_xticklabels(["¼×", "½×", "same", "2×", "4×", "10×", "50×"])
ax.set_yticks(y); ax.set_yticklabels(r["series"], fontsize=8.5); ax.grid(axis="y", visible=False)
for yi, v in enumerate(r["ratio"]):
    ax.text(v * (1.08 if v >= 1 else 0.92), yi, f"{v:.2f}×", va="center", ha="left" if v >= 1 else "right", fontsize=8.5, color=INK2)
title(fig, "2025 is comparable for half the series; others shifted level",
      "Mean hourly energy 18 Aug–13 Oct 2025 divided by the same weeks of 2021–22. Orange = more than 1.5× apart: check before using 2025 as a test period.")
save(fig, "F10_level_2025_vs_2021_22.png")
