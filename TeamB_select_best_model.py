"""Choose the best model per series on the VALIDATION period only (fair: same hours for all models),
then report its test scores. Writes best_model_selection.csv and best_model_predictions.csv.
Run: python TeamB_select_best_model.py all_model_predictions.csv"""
import sys, numpy as np, pandas as pd
p = pd.read_csv(sys.argv[1], parse_dates=["timestamp_utc"])
BENCH = {"naive_day", "naive_week", "seasonalnaive"}
def m(y, f):
    e = y - f; return 100*np.sqrt((e**2).mean())/y.mean(), 100*e.sum()/(len(y)*y.mean())
rows, best_parts = [], []
for (z, l), g in p.groupby(["zone", "load_type"]):
    v = g[g.split == "validation"]
    cands = sorted(set(v.model) - BENCH)
    if not cands: continue
    common = v.groupby("timestamp_utc").model.nunique()
    common = common[common == v.model.nunique()].index
    vc = v[v.timestamp_utc.isin(common)]
    sc = {mod: m(gg.y_true, gg.y_pred) for mod, gg in vc.groupby("model")}
    best = min(cands, key=lambda k: sc[k][0])
    r = dict(zone=z, load_type=l, best_model=best, n_models=len(cands), val_hours=len(common),
             val_cv_best=sc[best][0], val_nmbe_best=sc[best][1], val_cv_naive_day=sc.get("naive_day", (np.nan,))[0])
    for s in ["test_2023", "test_2025"]:
        t = g[g.split == s]
        tb, tn = t[t.model == best], t[t.model == "naive_day"]
        both = set(tb.timestamp_utc) & set(tn.timestamp_utc)
        if both:
            tb, tn = tb[tb.timestamp_utc.isin(both)], tn[tn.timestamp_utc.isin(both)]
            r[f"{s}_cv_best"], r[f"{s}_nmbe_best"] = m(tb.y_true, tb.y_pred)
            r[f"{s}_cv_naive_day"] = m(tn.y_true, tn.y_pred)[0]
    rows.append(r)
    best_parts.append(g[g.model == best].assign(model="best_model", source_model=best))
    best_parts.append(g[g.model == "naive_day"].assign(source_model="naive_day"))
sel = pd.DataFrame(rows)
for c in ["val", "test_2023", "test_2025"]:
    sel[f"{c}_beats_naive"] = sel[f"{c}_cv_best"] < sel[f"{c}_cv_naive_day"]
    sel[f"{c}_ashrae_pass"] = ((sel[f"{c}_cv_best"] <= 30) & (sel[f"{c}_nmbe_best"].abs() <= 10)).where(sel[f"{c}_cv_best"].notna())
    sel[f"{c}_beats_naive"] = sel[f"{c}_beats_naive"].where(sel[f"{c}_cv_best"].notna())
sel.round(2).to_csv("best_model_selection.csv", index=False)
bp = pd.concat(best_parts)
bp.drop(columns="source_model").to_csv("best_model_predictions.csv", index=False)
pd.set_option("display.width", 250)
print(sel[["zone","load_type","best_model","val_cv_best","val_cv_naive_day","val_nmbe_best","test_2023_cv_best","test_2023_cv_naive_day","test_2025_cv_best","test_2025_cv_naive_day","val_ashrae_pass","test_2023_ashrae_pass","test_2025_ashrae_pass"]].round(1).to_string(index=False))
