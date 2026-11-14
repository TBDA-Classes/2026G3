"""
Combine the forecasts of all models into ONE predictions file for the dashboard and team_b_eval.py
(TBDA DataPack, T36 / T38 / T39).

What it does
  1. Finds every *predictions*.csv in a folder, also inside .zip files (e.g. NW_Chronos.zip).
  2. Keeps only files in the agreed format: timestamp_utc, zone, load_type, model, split, y_true, y_pred.
  3. Re-labels `split` from the date, so every model uses the same names
     (some files call the whole out-of-sample period "test"):
        validation = Jul-Dec 2022 · test_2023 = Jan-Feb 2023 · test_2025 = Aug-Oct 2025
  4. Drops training-period rows (models are only scored on validation/test).
  5. Removes duplicates (same hour, series and model) and writes one csv.
  6. Optional (recommended): with the clean-data folder as 3rd argument, it checks per model that
     y_true matches energy_wh_model at that UTC hour. If a model saved LOCAL time in `timestamp_utc`
     (found for gbm), its timestamps are converted to UTC so all models line up hour by hour.

Run:  python combine_predictions.py <folder_with_model_outputs> all_model_predictions.csv [cleaned]
"""
import glob, io, os, sys, zipfile
import pandas as pd

NEED = ["timestamp_utc", "zone", "load_type", "model", "split", "y_true", "y_pred"]
SPLITS = {"validation": ("2022-07-01", "2022-12-31 23:00"),
          "test_2023": ("2023-01-01", "2023-02-28 23:00"), "test_2025": ("2025-08-18", "2025-10-13 23:00")}


def read_any(src, name, opener):
    try:
        with opener() as fh:
            d = pd.read_csv(fh)
    except Exception as e:
        print(f"  skip {name}: {e}")
        return None
    if not set(NEED) <= set(d.columns):
        print(f"  skip {name}: not in the agreed format (columns: {list(d.columns)[:8]})")
        return None
    print(f"  ok   {name}: {len(d):,} rows, models {sorted(d['model'].astype(str).unique())}")
    return d[NEED]


def collect(folder):
    parts = []
    for path in glob.glob(os.path.join(folder, "**", "*"), recursive=True):
        base = os.path.basename(path)
        if "__MACOSX" in path or base.startswith("._"):
            continue
        if base.lower().endswith(".csv") and "pred" in base.lower():
            d = read_any(path, base, lambda p=path: open(p, "rb"))
            if d is not None:
                parts.append(d)
        elif base.lower().endswith(".zip"):
            with zipfile.ZipFile(path) as z:
                for n in z.namelist():
                    b = os.path.basename(n)
                    if "__MACOSX" in n or b.startswith("._") or not (b.lower().endswith(".csv") and "pred" in b.lower()):
                        continue
                    d = read_any(path, f"{base}/{b}", lambda n=n, z=z: io.BytesIO(z.read(n)))
                    if d is not None:
                        parts.append(d)
    return parts


if __name__ == "__main__":
    folder, out = sys.argv[1], sys.argv[2]
    print(f"Searching {folder} ...")
    parts = collect(folder)
    if not parts:
        sys.exit("No predictions files in the agreed format found.")
    p = pd.concat(parts, ignore_index=True)
    p["timestamp_utc"] = pd.to_datetime(p["timestamp_utc"])
    p["model"] = p["model"].astype(str).str.strip().str.lower()
    if len(sys.argv) > 3:                                   # timestamp check against the clean dataset
        c = pd.read_csv(os.path.join(sys.argv[3], "cedint_f1_hourly_clean.csv.gz"),
                        usecols=["timestamp_utc", "timestamp_local", "zone", "load_type", "energy_wh_model"],
                        parse_dates=["timestamp_utc", "timestamp_local"])
        key = ["zone", "load_type"]
        fixed = []
        for m in p["model"].unique():
            g = p[p["model"] == m]
            a = g.merge(c, on=["timestamp_utc"] + key, how="left")
            bad_utc = (~((a["y_true"] - a["energy_wh_model"]).abs() < 0.01)).mean()
            b = g.merge(c.rename(columns={"timestamp_utc": "_utc", "timestamp_local": "timestamp_utc"}),
                        on=["timestamp_utc"] + key, how="left")
            bad_loc = (~((b["y_true"] - b["energy_wh_model"]).abs() < 0.01)).mean()
            if bad_utc > 0.5 and bad_loc < 0.05:
                print(f"  fix  {m}: timestamps were local time -> converted to UTC "
                      f"({bad_utc:.0%} mismatch as UTC, {bad_loc:.1%} as local)")
                b = b.dropna(subset=["_utc"]).drop_duplicates(["_utc"] + key + ["model"])
                fixed.append(b.assign(timestamp_utc=b["_utc"])[NEED])
            else:
                print(f"  check {m}: y_true matches the clean dataset in {1 - bad_utc:.1%} of rows")
                fixed.append(g)
        p = pd.concat(fixed, ignore_index=True)
    p["split"] = "unused"
    for s, (a, b) in SPLITS.items():
        p.loc[p["timestamp_utc"].between(pd.Timestamp(a), pd.Timestamp(b)), "split"] = s
    p = (p[p["split"] != "unused"].dropna(subset=["y_true", "y_pred"])
         .drop_duplicates(["timestamp_utc", "zone", "load_type", "model"]).sort_values(["model", "zone", "load_type", "timestamp_utc"]))
    p.to_csv(out, index=False)
    print(f"\n{len(p):,} rows written to {out}")
    print(p.groupby(["model", "split"]).size().unstack(fill_value=0).to_string())
