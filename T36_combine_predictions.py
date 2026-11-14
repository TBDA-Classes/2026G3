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

Run:  python combine_predictions.py <folder_with_model_outputs> all_model_predictions.csv
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
    p["split"] = "unused"
    for s, (a, b) in SPLITS.items():
        p.loc[p["timestamp_utc"].between(pd.Timestamp(a), pd.Timestamp(b)), "split"] = s
    p = (p[p["split"] != "unused"].dropna(subset=["y_true", "y_pred"])
         .drop_duplicates(["timestamp_utc", "zone", "load_type", "model"]).sort_values(["model", "zone", "load_type", "timestamp_utc"]))
    p.to_csv(out, index=False)
    print(f"\n{len(p):,} rows written to {out}")
    print(p.groupby(["model", "split"]).size().unstack(fill_value=0).to_string())
