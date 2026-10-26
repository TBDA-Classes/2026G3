# CeDInt floor 1 – data cleaning pipeline (TBDA DataPack, Team B)

This repository turns the raw CeDInt floor‑1 sensor exports into one clean, hourly dataset with quality flags. That dataset is the input for the analysis and forecasting work of the TBDA project (ETSII, UPM).

**Principle: nothing is deleted.** Raw values are kept next to the cleaned ones. Problems get a 0/1 flag column, and a clean value is left empty only when the raw value is physically impossible. Every change is a step in the code, so all results can be reproduced and audited.

## Repository contents

| File | Purpose |
| --- | --- |
| `clean_cedint.py` | Full cleaning pipeline: raw Excel files → clean hourly dataset, quality overview, consistency checks, anomaly log and data dictionary |
| `make_figures.py` | Creates the figures F1–F10 of the Team B data-quality report |
| `requirements.txt` | Python packages needed |
| `figures/` | Figures F1–F10 (PNG) |
| `CeDInt_F1_quality_and_anomalies.xlsx` | Quality and anomaly results (optional; the pipeline regenerates it) |

The data itself is **not** stored in this repository. It lives in the team's shared Drive:

- Raw input files: `01_raw/`
- Cleaned outputs: `03_processed/`

## Requirements

- Python 3.10 or newer
- Install the packages:

```bash
pip install -r requirements.txt
```

## How to run

1. Download the four raw files from the Drive folder `01_raw/` into a local folder, for example `raw/`:
   - `Storey1_NE_report_by_device.xlsx`
   - `Storey1_NW_report_by_device.xlsx`
   - `Storey1_SE_report_by_device.xlsx`
   - `Storey1_SW_report_by_device.xlsx`
2. Run the pipeline. The output folder is created if it does not exist:

```bash
python clean_cedint.py raw cleaned
```

The run takes about 10 minutes, mostly for reading the Excel files.

## Outputs (written to the output folder)

| File | Contents |
| --- | --- |
| `Storey1_<zone>_cleaned_hourly.xlsx` | One workbook per zone (NE, NW, SE, SW), one sheet per load type, plus README and Data_dictionary sheets. Same structure as the raw files. |
| `cedint_f1_hourly_clean.csv.gz` | All 470,680 hourly rows (hour × zone × load type) in one long table, 50 columns |
| `CeDInt_F1_quality_and_anomalies.xlsx` | Sheets: Series_quality, Consistency_checks, Anomaly_summary, Series_level_issues, Anomaly_log, Data_dictionary |
| `cedint_f1_minute_2025_flagged.csv.gz` | The raw 2025 minute rows with their counter status (complete, partial, zero record, …) |
| `*.pkl` | Intermediate pandas files, used by `make_figures.py` |

Load the clean table in Python:

```python
import pandas as pd
df = pd.read_csv("cleaned/cedint_f1_hourly_clean.csv.gz",
                 parse_dates=["timestamp_utc", "timestamp_local"])
```

## Using the clean data

- **Forecast target:** `energy_wh_model` (Wh per hour). Use only rows with `usable_for_model = 1`.
- **Check the series first:** the sheet `Series_quality` gives each series a recommendation (Use / Use with caution / Do not use) and the reason.
- **Time:** the raw timestamps are UTC. Use `timestamp_local` (Europe/Madrid) for hour-of-day, weekday and holiday features.
- **Two periods:** `era = hourly` covers 2 Apr 2020 – 28 Feb 2023 (hourly averages). `era = minute` covers 18 Aug – 13 Oct 2025 (minute data aggregated to hours). Never interpolate across the 902-day gap between them.
- **Environment:** `temp_c`, `hum_pct`, `lum_lux` and `occupancy` are zone-level values, repeated on every load type of a zone. Zone NE has no environmental sensors.
- **Occupancy:** the raw column `Pres` is presence (0/1), not pressure. `occupancy` is the share of the hour that the zone was occupied.

## Main cleaning rules

The full list (14 rules) is in the Team B report and in the `Data_dictionary` sheet. In short:

- **Reversed current clamp:** a series that is negative more than 90 % of the time gets its sign flipped (NW Emergency Lighting).
- **Zero records:** rows where all electrical values are exactly 0 are treated as missing.
- **Partial sums:** a counter that dips and recovers means some devices are missing from the zone total. Those rows are excluded.
- **Minute data:** only minutes with a complete device sum are used, and an hour needs at least 10 complete minutes.
- **Hourly energy:** computed from the active-energy counter as a centred difference, (C(t+1) − C(t−1)) / 2. It is never computed across a real counter reset and must be physically plausible.
- **Negative power:** values between −5 and 0 W are meter noise and set to 0. Values below −5 W are left empty.
- **Missing environmental readings:** Temp = Hum = 0 means the reading is missing. Temperatures outside 0–50 °C are left empty. Extreme but possible temperatures (below 10 °C or above 35 °C) are kept and flagged.

## Figures

```bash
python make_figures.py <pipeline_output_folder> <raw_sheet_pickles_folder> figures
```

**Known limitation:** besides the pipeline outputs, `make_figures.py` also reads one pickle per raw sheet (`<zone>_<load_type>.pkl`, for example `SE_HVAC.pkl`). The step that creates those pickles is not yet part of this repository, so the figures cannot be regenerated on a new machine yet. `clean_cedint.py` is fully self-contained.

## Data note

The CeDInt data belongs to UPM. Keep this repository private, and keep data files out of it: add `*.xlsx`, `*.csv.gz`, `*.pkl` and the data folders to `.gitignore`. If you keep the quality workbook in the repository, add the exception `!CeDInt_F1_quality_and_anomalies.xlsx`.
