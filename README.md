# CeDInt floor 1 – data cleaning pipeline (TBDA DataPack, Team B)

This repository turns the raw CeDInt floor‑1 sensor exports into one clean, hourly dataset with quality flags. That dataset is the input for the analysis and forecasting work of the TBDA project (ETSII, UPM).

**Principle: nothing is deleted.** Raw values are kept next to the cleaned ones. Problems get a 0/1 flag column, and a clean value is left empty only when the raw value is physically impossible. Every change is a step in the code, so all results can be reproduced and audited.

## Repository contents

| File | Purpose |
| --- | --- |
| `clean_cedint.py` | Full cleaning pipeline: raw Excel files → clean hourly dataset, quality overview, consistency checks, anomaly log and data dictionary |
| `make_figures.py` | Creates the figures F1–F10 of the Team B data-quality report |
| `team_b_eval.py` | Evaluation toolkit: checks a predictions file, computes MAE, RMSE, CV(RMSE), NMBE and ASHRAE pass/fail, error breakdowns, anomaly candidates and the flagged-hours sensitivity test (backlog F6.3, F6.4, F6.6, F6.7, F7.1) |
| `make_reference_baseline.py` | Naive reference forecasts (same hour yesterday / last week) in the agreed prediction format |
| `secondary_loads.py` | Characterisation of emergency lighting, hand dryers and RACK (backlog F2.2) |
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

The run takes about 10–15 minutes, mostly for reading the Excel files. It produces dataset version **v0.4**.

## Outputs (written to the output folder)

| File | Contents |
| --- | --- |
| `Storey1_<zone>_cleaned_hourly.xlsx` | One workbook per zone (NE, NW, SE, SW), one sheet per load type, plus README and Data_dictionary sheets. Same structure as the raw files. |
| `cedint_f1_hourly_clean.csv.gz` | All 470,680 hourly rows (hour × zone × load type) in one long table, 50 columns |
| `CeDInt_F1_quality_and_anomalies.xlsx` | Sheets: Series_quality, Consistency_checks, Anomaly_summary, Series_level_issues, Anomaly_log, Data_dictionary |
| `cedint_f1_minute_2025_flagged.csv.gz` | The raw 2025 minute rows with their counter status (complete, partial, zero record, …) |
| `*.pkl`, `raw_cache/` | Intermediate pandas files and one untouched copy of every raw sheet, used by `make_figures.py` |

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
- **Calendar flags (v0.4):** `is_holiday` and `holiday_name` (national and Comunidad de Madrid holidays), `is_weekend`, `is_august_low_use` and `flag_covid_2020`, all based on local time.
- **Current:** do not use `current_a` from 2020–2023 as a feature. For series with several devices it is underestimated (see `Consistency_checks`).

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
python make_figures.py cleaned figures
```

Reads only the output folder of `clean_cedint.py` and writes F1–F10 to `figures/`.

## Evaluating forecasts (for Team D's models)

1. Save the forecasts as a CSV with one row per forecast hour and these columns: `timestamp_utc, zone, load_type, model, split, y_true, y_pred`.
   - `split` is one of `train` (1 Jun 2020 – 30 Jun 2022), `validation` (Jul–Dec 2022), `test_2023` (Jan–Feb 2023) or `test_2025` (18 Aug – 13 Oct 2025; NE, NW and SE only).
   - `y_true` is `energy_wh_model` from dataset v0.4.
2. Run the toolkit:

```bash
python team_b_eval.py predictions.csv cleaned evaluation
```

3. Open `evaluation/TeamB_evaluation.xlsx`:
   - `Check_report`: did the file pass every check?
   - `ASHRAE_table`: metrics and pass/fail per series. ASHRAE Guideline 14 hourly criteria: CV(RMSE) ≤ 30 % and |NMBE| ≤ 10 %.
   - `Errors_by_*`: when and where the forecast is least reliable.
   - `Anomaly_days`, `Anomaly_hours`: candidate anomalies with a first explanation.
   - `Sensitivity_flags`: results with and without flagged hours.

To get the reference forecasts every model must beat:

```bash
python make_reference_baseline.py cleaned reference_predictions.csv
python team_b_eval.py reference_predictions.csv cleaned evaluation_reference
```

Characterisation of the secondary loads:

```bash
python secondary_loads.py cleaned secondary
```

## Data note

The CeDInt data belongs to UPM. Keep this repository private, and keep data files out of it: add `*.xlsx`, `*.csv.gz`, `*.pkl` and the data folders to `.gitignore`. If you keep the quality workbook in the repository, add the exception `!CeDInt_F1_quality_and_anomalies.xlsx`.
