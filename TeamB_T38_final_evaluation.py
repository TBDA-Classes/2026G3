"""
T38 (F6.4) - Final evaluation of all day-ahead models (TBDA DataPack, Team B, Marie Heyse)

Follows the professor's guidance of 15 Nov 2026:
  * skill score per series and period: 1 - RMSE_model / RMSE_naive (naive = same hour yesterday)
  * targets per load type instead of ASHRAE pass/fail (ASHRAE 14 kept as a reference column)
      constant loads (RACK, emergency lighting) CV(RMSE) <= 15 %
      plugs & sockets                            CV(RMSE) <= 30 %
      HVAC                                       30-50 %, beats naive and |NMBE| <= 10 %
      lighting                                   judged on daily energy (MAE kWh/day) and switch-on/off timing
  * MAE in kWh next to the percentages
  * hierarchy hour -> day (daily value = sum of the 24 hourly day-ahead forecasts) and series -> floor total (T30)

Model choice per series (honest protocol)
  * the hybrid Chronos+GBM stacker learns its weights on the first half of validation (1 Jul - 15 Oct 2022),
    so validation predictions in that half are in-sample for the hybrid;
  * every model is therefore chosen on the SECOND half of validation (16 Oct - 31 Dec 2022), which is
    out-of-sample for all models, scored on the hours that every candidate forecast;
  * the two test periods (Jan-Feb 2023, Aug-Oct 2025) are scored once with the chosen model.

Run:
  python TeamB_T38_final_evaluation.py all_model_predictions.csv <clean_folder> <T30_hourly_csv> <out_folder>
Inputs:  all_model_predictions.csv from T36_combine_predictions.py (with the clean-data timestamp check),
         cedint_f1_hourly_clean.csv.gz (for local dates), outputs_T30/T30_floor1_total_forecast_hourly.csv
Outputs: TeamB_T38_final_evaluation.xlsx, best_model_selection_final.csv, best_model_predictions_final.csv
"""
import os, sys
import numpy as np
import pandas as pd

BENCH = {"naive_day", "naive_week", "seasonalnaive"}
SEL = ("2022-10-16 00:00", "2022-12-31 23:00")          # out-of-sample half of validation for every model
SPLITS = ["validation", "test_2023", "test_2025"]


def m(y, f):
    y, f = np.asarray(y, float), np.asarray(f, float)
    ok = ~np.isnan(y) & ~np.isnan(f)
    y, f = y[ok], f[ok]
    if len(y) == 0 or y.mean() == 0:
        return dict(n=len(y), MAE=np.nan, RMSE=np.nan, CV=np.nan, NMBE=np.nan)
    e = y - f
    rmse = np.sqrt((e ** 2).mean())
    return dict(n=len(y), MAE=np.abs(e).mean(), RMSE=rmse, CV=100 * rmse / y.mean(),
                NMBE=100 * e.sum() / (len(y) * y.mean()))


def skill(rm, rn):
    return 1 - rm / rn if rn and rn > 0 and pd.notna(rm) else np.nan


def load_group(lt):
    if lt in ("RACK", "Emerg. Lighting"):
        return "Constant"
    if lt == "Plugs & Sockets":
        return "Plugs & Sockets"
    return lt


def target_status(lt, cv, nmbe, sk):
    g = load_group(lt)
    if pd.isna(cv):
        return "n/a"
    if g == "Constant":
        return "on target" if cv <= 15 else "above 15 %"
    if g == "Plugs & Sockets":
        return "on target" if cv <= 30 else "above 30 %"
    if g == "HVAC":
        if cv <= 50 and abs(nmbe) <= 10 and (pd.isna(sk) or sk > 0):
            return "on target"
        return "above 50 %" if cv > 50 else ("bias > 10 %" if abs(nmbe) > 10 else "no skill")
    return "judged per day"                                # lighting


def timing_error(df):
    """Median absolute error (hours) of switch-on and switch-off per local day.
    On = first hour above 50 % of that day's maximum; off = last such hour; for actual and forecast separately."""
    on_e, off_e = [], []
    for _, d in df.groupby("date"):
        if len(d) < 20 or d["y_true"].max() <= 0 or d["y_pred"].max() <= 0:
            continue
        a = d[d["y_true"] > 0.5 * d["y_true"].max()]["hour"]
        p = d[d["y_pred"] > 0.5 * d["y_pred"].max()]["hour"]
        if len(a) and len(p):
            on_e.append(abs(a.min() - p.min()))
            off_e.append(abs(a.max() - p.max()))
    return (np.median(on_e) if on_e else np.nan, np.median(off_e) if off_e else np.nan)


def daily(df):
    d = (df.groupby("date").agg(y_true=("y_true", "sum"), y_pred=("y_pred", "sum"), h=("y_true", "size"))
         .reset_index())
    return d[d["h"] >= 20]


if __name__ == "__main__":
    pred_path, clean_dir, t30_path, out = sys.argv[1:5]
    os.makedirs(out, exist_ok=True)
    p = pd.read_csv(pred_path, parse_dates=["timestamp_utc"])
    c = pd.read_csv(os.path.join(clean_dir, "cedint_f1_hourly_clean.csv.gz"),
                    usecols=["timestamp_utc", "timestamp_local", "zone", "load_type"],
                    parse_dates=["timestamp_utc", "timestamp_local"])
    p = p.merge(c, on=["timestamp_utc", "zone", "load_type"], how="left")
    p["date"] = p["timestamp_local"].dt.date
    p["hour"] = p["timestamp_local"].dt.hour

    # ---------------- 1. model choice per series on the out-of-sample half of validation
    sel_rows, chosen = [], {}
    for (z, l), g in p.groupby(["zone", "load_type"]):
        v = g[(g["split"] == "validation") & g["timestamp_utc"].between(pd.Timestamp(SEL[0]), pd.Timestamp(SEL[1]))]
        cands = sorted(set(v["model"]) - BENCH)
        if not cands:
            continue
        pool = v[v["model"].isin(cands + ["naive_day"])]
        cnt = pool.groupby("timestamp_utc")["model"].nunique()
        hrs = cnt[cnt == pool["model"].nunique()].index
        sc = {mod: m(gg["y_true"], gg["y_pred"]) for mod, gg in pool[pool["timestamp_utc"].isin(hrs)].groupby("model")}
        best = min(cands, key=lambda k: sc[k]["CV"] if pd.notna(sc[k]["CV"]) else 1e9)
        chosen[(z, l)] = best
        row = dict(zone=z, load_type=l, best_model=best, candidates=len(cands), selection_hours=len(hrs),
                   sel_cv_best=sc[best]["CV"], sel_cv_naive_day=sc.get("naive_day", {}).get("CV", np.nan))
        for k in cands:
            row[f"sel_cv_{k}"] = sc[k]["CV"]
        sel_rows.append(row)
    sel = pd.DataFrame(sel_rows)

    # ---------------- 2. all models, every series and period (hourly), with skill vs naive_day on the same hours
    allm = []
    for (z, l, s), g in p[p["split"].isin(SPLITS)].groupby(["zone", "load_type", "split"]):
        nv = g[g["model"] == "naive_day"].set_index("timestamp_utc")["y_pred"]
        for mod, gg in g.groupby("model"):
            r = m(gg["y_true"], gg["y_pred"])
            k = gg.set_index("timestamp_utc")
            idx = k.index.intersection(nv.index)
            rn = m(k.loc[idx, "y_true"], nv.loc[idx])["RMSE"] if len(idx) else np.nan
            rm = m(k.loc[idx, "y_true"], k.loc[idx, "y_pred"])["RMSE"] if len(idx) else np.nan
            allm.append(dict(zone=z, load_type=l, split=s, model=mod, hours=r["n"], CV=r["CV"], NMBE=r["NMBE"],
                             MAE_kWh_per_h=r["MAE"] / 1000, skill=skill(rm, rn)))
    allm = pd.DataFrame(allm)

    # ---------------- 3. final table: chosen model per series and period, hourly + daily + timing
    fin, best_parts = [], []
    for (z, l), best in chosen.items():
        for s in SPLITS:
            g = p[(p["zone"] == z) & (p["load_type"] == l) & (p["split"] == s)]
            b, n = g[g["model"] == best], g[g["model"] == "naive_day"]
            hrs = sorted(set(b["timestamp_utc"]) & set(n["timestamp_utc"]))
            if not hrs:
                continue
            b, n = b[b["timestamp_utc"].isin(hrs)], n[n["timestamp_utc"].isin(hrs)]
            hb, hn = m(b["y_true"], b["y_pred"]), m(n["y_true"], n["y_pred"])
            db, dn = daily(b), daily(n)
            dmb, dmn = m(db["y_true"], db["y_pred"]), m(dn["y_true"], dn["y_pred"])
            on_e, off_e = timing_error(b) if l == "Lighting" else (np.nan, np.nan)
            sk = skill(hb["RMSE"], hn["RMSE"])
            fin.append(dict(zone=z, load_type=l, load_group=load_group(l), split=s, best_model=best,
                            hours=hb["n"], CV=hb["CV"], NMBE=hb["NMBE"], MAE_kWh_per_h=hb["MAE"] / 1000,
                            naive_CV=hn["CV"], skill=sk,
                            days=dmb["n"], daily_CV=dmb["CV"], daily_NMBE=dmb["NMBE"],
                            daily_MAE_kWh=dmb["MAE"] / 1000, daily_skill=skill(dmb["RMSE"], dmn["RMSE"]),
                            switch_on_error_h=on_e, switch_off_error_h=off_e,
                            target=target_status(l, hb["CV"], hb["NMBE"], sk),
                            ASHRAE14_hourly_reference=(hb["CV"] <= 30) and (abs(hb["NMBE"]) <= 10)))
        best_parts.append(p[(p["zone"] == z) & (p["load_type"] == l) & (p["model"] == best)]
                          .assign(source_model=best, model="best_model"))
    fin = pd.DataFrame(fin)

    # ---------------- 4. floor total (T30): hourly + daily, MinT vs seasonal naive
    t = pd.read_csv(t30_path)
    t["ts"] = pd.to_datetime(t["timestamp"], utc=True).dt.tz_convert(None)
    t["date"] = pd.to_datetime(t["timestamp"], utc=True).dt.tz_convert("Europe/Madrid").dt.date
    t["split"] = np.where(t["ts"] < pd.Timestamp("2023-01-01"), "validation", "test_2023")
    floor = []
    for s, g in t.groupby("split"):
        for meth in ["seasonal_naive", "direct_total_model", "bottom_up", "reconciled_mint"]:
            h = m(g["actual_wh"], g[meth])
            dd = g.groupby("date").agg(a=("actual_wh", "sum"), f=(meth, "sum"), n=("actual_wh", "size"))
            dd = dd[dd["n"] >= 20]
            d = m(dd["a"], dd["f"])
            hn = m(g["actual_wh"], g["seasonal_naive"])
            floor.append(dict(split=s, method=meth, hours=h["n"], CV=h["CV"], NMBE=h["NMBE"],
                              MAE_kWh_per_h=h["MAE"] / 1000, skill_vs_seasonal_naive=skill(h["RMSE"], hn["RMSE"]),
                              days=d["n"], daily_CV=d["CV"], daily_NMBE=d["NMBE"], daily_MAE_kWh=d["MAE"] / 1000))
    floor = pd.DataFrame(floor)

    # ---------------- 5. summaries
    summ = (fin.groupby(["split", "load_group"])
            .agg(series=("load_type", "size"), positive_skill=("skill", lambda x: int((x > 0).sum())),
                 median_skill=("skill", "median"), on_target=("target", lambda x: int((x == "on target").sum())),
                 median_daily_CV=("daily_CV", "median")).reset_index())
    tot = (fin.groupby("split").agg(series=("load_type", "size"), positive_skill=("skill", lambda x: int((x > 0).sum())),
                                    median_skill=("skill", "median")).reset_index())
    wins = sel["best_model"].value_counts().rename_axis("model").reset_index(name="series_won")

    readme = pd.DataFrame({"item": [
        "Purpose", "Model choice", "Skill score", "Targets", "Daily values", "Timing (lighting)", "Floor total",
        "ASHRAE 14", "Excluded", "NMBE sign", "Run"], "description": [
        "T38 (F6.4): final evaluation of every day-ahead forecast, following the professor's guidance of 15 Nov 2026.",
        "Per series, the model with the lowest CV(RMSE) on 16 Oct - 31 Dec 2022 (second half of validation, out-of-sample for every model incl. the hybrid stacker), on the hours every candidate forecast. Tests scored once.",
        "1 - RMSE(model) / RMSE(naive same hour yesterday), on the same hours. > 0 = better than the naive forecast.",
        "Constant loads CV <= 15 %; Plugs & Sockets CV <= 30 %; HVAC 30-50 % with |NMBE| <= 10 % and positive skill; Lighting judged per day (MAE kWh/day) and on switch-on/off timing.",
        "Sum of the 24 hourly day-ahead forecasts per local (Madrid) day; days with >= 20 valid hours.",
        "Median absolute difference in hours between actual and forecast switch-on (first hour above 50 % of the day's maximum) and switch-off (last such hour).",
        "From T30 (Maria Herraiz): floor-1 total, MinT reconciliation vs seasonal naive; validation and test 2023 only.",
        "Kept as a reference column only (hourly CV <= 30 %, |NMBE| <= 10 %); it was written for whole-building calibration, not for day-ahead sub-meter forecasts.",
        "Blend 50/50 and SARIMAX: no predictions file in the agreed format on GitHub. Hand dryers: event-driven (R4). SE Projector: dead series.",
        "NMBE = (actual - forecast) / mean actual: positive = forecast too low, negative = too high. T30's own workbook uses the opposite sign.",
        "python TeamB_T38_final_evaluation.py all_model_predictions.csv cleaned outputs_T30/T30_floor1_total_forecast_hourly.csv eval_T38"]})

    xlsx = os.path.join(out, "TeamB_T38_final_evaluation.xlsx")
    with pd.ExcelWriter(xlsx, engine="xlsxwriter") as xw:
        for name, d in [("README", readme), ("Summary", summ), ("Summary_total", tot), ("Final_table", fin),
                        ("Model_choice", sel), ("Model_wins", wins), ("All_models", allm), ("Floor_total", floor)]:
            d.round(3).to_excel(xw, sheet_name=name, index=False)
            xw.sheets[name].set_column(0, max(len(d.columns) - 1, 1), 16)
        xw.sheets["README"].set_column(1, 1, 120)
    sel.round(2).to_csv(os.path.join(out, "best_model_selection_final.csv"), index=False)
    pd.concat(best_parts).drop(columns=["timestamp_local", "date", "hour"]).to_csv(
        os.path.join(out, "best_model_predictions_final.csv"), index=False)
    pd.set_option("display.width", 250)
    print(wins.to_string(index=False))
    print(tot.round(2).to_string(index=False))
    print(summ.round(2).to_string(index=False))
    print(fin[["zone", "load_type", "split", "best_model", "CV", "NMBE", "skill", "daily_CV", "daily_MAE_kWh",
               "switch_on_error_h", "target"]].round(2).to_string(index=False))
    print(floor.round(2).to_string(index=False))
