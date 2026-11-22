"""
T40 (F6.7) - Robustness and bias analysis of the chosen models (TBDA DataPack, Team B, Marie Heyse)

Answers two questions from the professor's feedback of 15 Nov 2026:
  1. Why is CV(RMSE) so high for some series?  -> scores with and without flagged hours (meter faults vs model error)
  2. Where does the large bias come from?       -> level-shift check + a simple rolling recalibration
     (forecast x  sum(actual) / sum(forecast) over the previous 7 days, which are known at 00:00 on day D;
      ratio clipped to 0.5-2). If recalibration removes most of the bias, the bias is a level change,
      not random error, and the fix is to update the model regularly ("close the loop").

Run: python TeamB_T40_robustness_bias.py best_model_predictions_final.csv <clean_folder> <out_folder>
     (the predictions file written by TeamB_T38_final_evaluation.py; team_b_eval.py must be in the same folder)
"""
import os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from team_b_eval import load_clean, load_predictions, check_predictions   # noqa: E402

SPLITS = ["validation", "test_2023", "test_2025"]


def m(y, f):
    y, f = np.asarray(y, float), np.asarray(f, float)
    if len(y) == 0 or y.mean() == 0:
        return dict(n=len(y), CV=np.nan, NMBE=np.nan, MAE=np.nan)
    e = y - f
    return dict(n=len(y), CV=100 * np.sqrt((e ** 2).mean()) / y.mean(), NMBE=100 * e.sum() / (len(y) * y.mean()),
                MAE=np.abs(e).mean())


def recalibrate(g, days=7):
    """Rolling level correction using only days before the forecast day (local dates)."""
    d = g.groupby("date").agg(a=("y_true", "sum"), f=("y_pred", "sum")).sort_index()
    ra = d["a"].rolling(days, min_periods=3).sum().shift(1)
    rf = d["f"].rolling(days, min_periods=3).sum().shift(1)
    ratio = (ra / rf).clip(0.5, 2.0)
    ratio = ratio.where(rf > 0)
    g = g.merge(ratio.rename("ratio"), left_on="date", right_index=True, how="left")
    g["y_recal"] = g["y_pred"] * g["ratio"].fillna(1.0)
    return g


if __name__ == "__main__":
    pred_path, clean_dir, out = sys.argv[1:4]
    os.makedirs(out, exist_ok=True)
    clean = load_clean(clean_dir)
    j, _ = check_predictions(load_predictions(pred_path), clean)
    j = j[j["model"] == "best_model"].copy()
    j["date"] = pd.to_datetime(j["timestamp_local"]).dt.date
    cl = pd.read_csv(os.path.join(clean_dir, "cedint_f1_hourly_clean.csv.gz"),
                     usecols=["timestamp_utc", "zone", "load_type", "energy_wh_model", "usable_for_model"],
                     parse_dates=["timestamp_utc"])

    # 1. sensitivity: with and without flagged hours
    sens = []
    for (z, l, s), g in j[j["split"].isin(SPLITS)].groupby(["zone", "load_type", "split"]):
        a, b = m(g["y_true"], g["y_pred"]), m(g.loc[~g["flag_any_quality"], "y_true"], g.loc[~g["flag_any_quality"], "y_pred"])
        sens.append(dict(zone=z, load_type=l, split=s, share_flagged=g["flag_any_quality"].mean(),
                         CV_all=a["CV"], CV_unflagged=b["CV"], NMBE_all=a["NMBE"], NMBE_unflagged=b["NMBE"]))
    sens = pd.DataFrame(sens)
    sens["CV_change_pts"] = sens["CV_unflagged"] - sens["CV_all"]
    sens["reading"] = np.select(
        [sens["CV_change_pts"] <= -0.5 * sens["CV_all"], sens["CV_change_pts"] < -5, sens["CV_change_pts"] > 5],
        ["error mainly from meter faults", "flags explain part of the error", "rare real peaks drive the error"],
        "model error, flags play no role")

    # 2. level shift: mean hourly energy per period vs the training period (usable hours)
    tr = cl[(cl["usable_for_model"] == 1) & cl["timestamp_utc"].between("2020-06-01", "2022-06-30 23:00")]
    tr_mean = tr.groupby(["zone", "load_type"])["energy_wh_model"].mean()
    lvl = (j[j["split"].isin(SPLITS)].groupby(["zone", "load_type", "split"])
           .agg(mean_actual=("y_true", "mean"), mean_forecast=("y_pred", "mean")).reset_index())
    lvl["train_mean"] = [tr_mean.get((z, l), np.nan) for z, l in zip(lvl["zone"], lvl["load_type"])]
    lvl["actual_vs_train_pct"] = 100 * (lvl["mean_actual"] / lvl["train_mean"] - 1)
    lvl["forecast_vs_actual_pct"] = 100 * (lvl["mean_forecast"] / lvl["mean_actual"] - 1)

    # 3. rolling recalibration
    rec = []
    for (z, l, s), g in j[j["split"].isin(SPLITS)].groupby(["zone", "load_type", "split"]):
        g = recalibrate(g.sort_values("timestamp_utc"))
        a, b = m(g["y_true"], g["y_pred"]), m(g["y_true"], g["y_recal"])
        rec.append(dict(zone=z, load_type=l, split=s, NMBE_before=a["NMBE"], NMBE_after=b["NMBE"],
                        CV_before=a["CV"], CV_after=b["CV"], MAE_kWh_before=a["MAE"] / 1000,
                        MAE_kWh_after=b["MAE"] / 1000))
    rec = pd.DataFrame(rec)
    rec["bias_removed_pts"] = rec["NMBE_before"].abs() - rec["NMBE_after"].abs()
    rec["verdict"] = np.select(
        [(rec["NMBE_before"].abs() > 10) & (rec["NMBE_after"].abs() <= 10),
         (rec["NMBE_before"].abs() > 10) & (rec["bias_removed_pts"] > 0),
         rec["NMBE_before"].abs() > 10],
        ["level shift: recalibration fixes the bias", "partly a level shift", "bias not explained by level"],
        "no bias problem (|NMBE| <= 10 %)")

    big = rec[rec["NMBE_before"].abs() > 10].merge(lvl, on=["zone", "load_type", "split"]) \
        .merge(sens[["zone", "load_type", "split", "share_flagged", "NMBE_unflagged"]], on=["zone", "load_type", "split"])
    readme = pd.DataFrame({"item": ["Purpose", "Sensitivity", "Level shift", "Recalibration", "Sign"], "description": [
        "T40 (F6.7): what the chosen models get wrong and why (professor's feedback, 15 Nov 2026).",
        "Same model scored on all hours and on hours without quality flags (counter spikes, resets, partial sums, implausible energy, power/energy mismatch, power spikes, low coverage, interpolated).",
        "Mean actual energy per period compared with the training period (Jun 2020 - Jun 2022, usable hours).",
        "Forecast multiplied by sum(actual)/sum(forecast) of the 7 previous local days (known at 00:00 on day D), ratio clipped to 0.5-2. A simple stand-in for regular model updates.",
        "NMBE = (actual - forecast) / mean actual: positive = forecast too low."]})
    xlsx = os.path.join(out, "TeamB_T40_robustness_bias.xlsx")
    with pd.ExcelWriter(xlsx, engine="xlsxwriter") as xw:
        for name, d in [("README", readme), ("Bias_cases", big), ("Recalibration", rec), ("Level_shift", lvl),
                        ("Sensitivity_flags", sens)]:
            d.round(3).to_excel(xw, sheet_name=name, index=False)
            xw.sheets[name].set_column(0, max(len(d.columns) - 1, 1), 17)
        xw.sheets["README"].set_column(1, 1, 120)

    # figure: bias before / after recalibration for the series with |NMBE| > 10 %
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e1e0d9"
    plt.rcParams.update({"figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
                         "font.family": "DejaVu Sans", "text.color": INK, "axes.labelcolor": INK2,
                         "xtick.color": INK2, "ytick.color": INK2})
    b = big.copy()
    b["label"] = b["zone"] + " · " + b["load_type"] + "  (" + b["split"].str.replace("_", " ") + ")"
    b = b.sort_values("NMBE_before")
    fig, ax = plt.subplots(figsize=(10, 0.55 * len(b) + 2.2)); fig.subplots_adjust(left=0.36, right=0.95, top=0.80, bottom=0.16)
    yv = np.arange(len(b))
    ax.axvspan(-10, 10, color="#EEF3F4", zorder=0)
    for i, (x0, x1) in enumerate(zip(b["NMBE_before"], b["NMBE_after"])):
        ax.annotate("", xy=(x1, i), xytext=(x0, i), arrowprops=dict(arrowstyle="->", color="#9AA5A8", lw=1.4))
    ax.scatter(b["NMBE_before"], yv, color="#C8553D", s=45, zorder=3, label="before (chosen model)")
    ax.scatter(b["NMBE_after"], yv, color="#0F4C5C", s=45, zorder=3, label="after 7-day recalibration")
    ax.set_yticks(yv); ax.set_yticklabels(b["label"], fontsize=9)
    ax.set_xlabel("NMBE % (positive = forecast too low); shaded band = ±10 % target")
    for sp in ["top", "right"]:
        ax.spines[sp].set_visible(False)
    ax.grid(axis="x", color=GRID, lw=0.6); ax.set_axisbelow(True)
    ax.legend(loc="upper left", bbox_to_anchor=(0, 1.13), ncol=2, frameon=False, fontsize=9)
    fixed = int((b["NMBE_after"].abs() <= 10).sum())
    fig.text(0.012, 0.97, f"A simple 7-day level update brings {fixed} of {len(b)} biased cases within ±10 %",
             fontsize=12.5, fontweight="bold", va="top")
    fig.savefig(os.path.join(out, "F15_bias_recalibration.png"), dpi=170)
    pd.set_option("display.width", 250)
    print(big[["zone", "load_type", "split", "NMBE_before", "NMBE_after", "CV_before", "CV_after",
               "actual_vs_train_pct", "share_flagged", "NMBE_unflagged", "verdict"]].round(1).to_string(index=False))
    print(sens.sort_values("CV_change_pts").head(8).round(1).to_string(index=False))
    print(rec[["NMBE_before", "NMBE_after", "CV_before", "CV_after"]].describe().round(1))
