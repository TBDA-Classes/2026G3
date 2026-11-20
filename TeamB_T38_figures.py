"""
Figures for T38 (Team B). Reads Final_table from TeamB_T38_final_evaluation.xlsx.
  F13_best_model_vs_benchmark.png : CV(RMSE) of the chosen model vs the naive benchmark (validation, same hours)
  F14_skill_by_series.png         : skill score per series in validation, test 2023 and test 2025
Run: python TeamB_T38_figures.py eval_T38/TeamB_T38_final_evaluation.xlsx eval_T38
"""
import sys, os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e1e0d9"
plt.rcParams.update({"figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
                     "font.family": "DejaVu Sans", "text.color": INK, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2})
SHORT = {"chronos_bolt_base": "Chronos", "gbm": "GBM", "hybrid_chronos_gbm_learned_weights": "Hybrid",
         "random_forest_no2020": "RF without 2020", "random_forest": "RF", "catboost": "CatBoost", "lightgbm": "LightGBM"}

xlsx, out = sys.argv[1], sys.argv[2]
f = pd.read_excel(xlsx, sheet_name="Final_table")
f["series"] = f["zone"] + " · " + f["load_type"]
f["label"] = f["series"] + "   (" + f["best_model"].map(lambda m: SHORT.get(m, m)) + ")"

# ---------------- F13: CV(RMSE) chosen model vs naive, validation
v = f[f["split"] == "validation"].sort_values("CV")
fig, ax = plt.subplots(figsize=(11, 7.4)); fig.subplots_adjust(left=0.33, right=0.95, top=0.86, bottom=0.1)
y = np.arange(len(v))
ax.barh(y + 0.2, v["naive_CV"], 0.38, color="#b5b3aa", label="benchmark: same hour yesterday")
ax.barh(y - 0.2, v["CV"], 0.38, color="#0F4C5C", label="chosen model")
ax.set_xscale("log"); ax.set_xlim(0.3, 1500); ax.set_ylim(-0.8, len(v) - 0.4)
ax.set_yticks(y); ax.set_yticklabels(v["label"], fontsize=9)
for i, val in enumerate(v["CV"]):
    ax.text(val * 1.08, i - 0.2, f"{val:.0f} %" if val >= 10 else f"{val:.1f} %", va="center", fontsize=8)
ax.set_xlabel("CV(RMSE) on validation 2022-H2, log scale (lower is better)")
for sp in ["top", "right"]:
    ax.spines[sp].set_visible(False)
ax.grid(axis="x", color=GRID, lw=0.6); ax.set_axisbelow(True)
ax.legend(loc="upper left", bbox_to_anchor=(0, 1.06), ncol=2, frameon=False, fontsize=9)
fig.text(0.012, 0.965, "The chosen model has a lower error than the benchmark in every series", fontsize=13.5,
         fontweight="bold", va="top")
fig.text(0.012, 0.925, "Model chosen on 16 Oct - 31 Dec 2022 (out-of-sample for all models); same hours for model and benchmark.",
         fontsize=10, color=INK2, va="top")
fig.savefig(os.path.join(out, "F13_best_model_vs_benchmark.png"), dpi=170); plt.close(fig)

# ---------------- F14: skill score per series and period
order = f[f["split"] == "validation"].sort_values("skill")["series"].tolist()
fig, ax = plt.subplots(figsize=(11, 7.4)); fig.subplots_adjust(left=0.24, right=0.95, top=0.86, bottom=0.1)
cols = {"validation": "#0F4C5C", "test_2023": "#E8A33D", "test_2025": "#C8553D"}
names = {"validation": "validation 2022-H2", "test_2023": "test Jan-Feb 2023", "test_2025": "test Aug-Oct 2025"}
yy = {s: i for i, s in enumerate(order)}
for sp_, off in [("validation", 0.22), ("test_2023", 0), ("test_2025", -0.22)]:
    d = f[f["split"] == sp_]
    ax.scatter(d["skill"], [yy[s] + off for s in d["series"]], s=42, color=cols[sp_], label=names[sp_], zorder=3)
ax.axvline(0, color=INK2, lw=1)
ax.text(0.005, len(order) - 0.35, "better than the naive forecast →", fontsize=8.5, color=INK2, va="bottom")
ax.text(-0.005, len(order) - 0.35, "← worse", fontsize=8.5, color=INK2, va="bottom", ha="right")
ax.set_yticks(range(len(order))); ax.set_yticklabels(order, fontsize=9)
ax.set_ylim(-0.7, len(order) - 0.1); ax.set_xlim(-0.3, 0.65)
ax.set_xlabel("Skill score = 1 − RMSE model / RMSE naive (same hour yesterday)")
for sp in ["top", "right"]:
    ax.spines[sp].set_visible(False)
ax.grid(axis="x", color=GRID, lw=0.6); ax.set_axisbelow(True)
ax.legend(loc="lower right", frameon=False, fontsize=9)
n_pos = int((f["skill"] > 0).sum()); n_all = int(f["skill"].notna().sum())
fig.text(0.012, 0.965, f"Positive skill in {n_pos} of {n_all} series-period combinations", fontsize=13.5,
         fontweight="bold", va="top")
fig.text(0.012, 0.925, "Only NE and NW Plugs & Sockets in 2025 fall below the naive forecast.", fontsize=10,
         color=INK2, va="top")
fig.savefig(os.path.join(out, "F14_skill_by_series.png"), dpi=170); plt.close(fig)
print("figures written")
