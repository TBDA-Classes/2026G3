# Training data methodology – CeDInt floor 1 (TBDA DataPack, Team B)

**Author:** Marie Heyse (Team B – Data Quality & Validation) · **Date:** 2 November 2026
**Supports:** T29 (F1.2 day-ahead models), T32 (F6.3 test on unseen periods), T34–T40 (evaluation)
**Script:** `make_training_data.py` · **Input:** clean dataset v0.4 (`cedint_f1_hourly_clean.csv.gz`)
**Outputs:** `cedint_f1_model_ready.csv.gz`, `training_data_summary.xlsx`

---

## 1. Purpose

The clean dataset (v0.4) keeps every hour and marks problems with flags. A model, however, should only learn from hours whose target value is trustworthy, and should only be scored on hours where a true value exists. This step decides, for every hour, **whether it may be used for training and whether it may be used for scoring**, and records **why** an hour is left out.

## 2. Principle: leave out, never delete

- No row is deleted. The output file contains all 470,680 hourly rows of the clean dataset.
- Three 0/1 columns say how a row may be used:
  - `include_train`: the model may **learn** from this row (split = train).
  - `include_eval`: validation and test **scores** are computed on this row.
  - `include_train_no2020`: experiment variant without the COVID year 2020.
- `exclusion_reason` gives the first rule (R0–R6) that keeps a row out.
- **Training may be filtered more strictly than testing.** Leaving difficult hours out of the *training* set helps the model learn normal behaviour. Leaving them out of the *test* set would make the score look better than it is. So the test sets only drop hours without a true value.

## 3. Periods (agreed with Team D, same as `team_b_eval.py`)

| Split | Period (UTC) | Used for |
| --- | --- | --- |
| train | 1 Jun 2020 – 30 Jun 2022 | Fitting the models |
| validation | 1 Jul – 31 Dec 2022 | Choosing and tuning the model |
| test_2023 | 1 Jan – 28 Feb 2023 | Unseen test 1 (only two months exist before the gap) |
| test_2025 | 18 Aug – 13 Oct 2025 | Unseen test 2 (NE, NW, SE only) |
| unused | everything else | Apr–May 2020 and SW in 2025 |

The 902-day gap (Mar 2023 – Aug 2025) separates the periods. Lag features are computed per period, so no value is ever copied across the gap.

## 4. Which series are modelled per hour

| Scope | Series | Why |
| --- | --- | --- |
| **Priority** | HVAC (NE, NW, SE), Lighting (NW, SE, SW), Plugs & Sockets (all zones) | Core forecast targets (backlog section 3) |
| **Secondary (constant)** | RACK (NW, SW until Dec 2021), Emergency Lighting (NW, SE, SW) | Constant loads; the naive forecast already reaches CV(RMSE) 3–14 %; control group |
| **Daily totals only** | Hand Dryer (NW, SW) | Event-driven: hourly CV(RMSE) > 1,000 % (F2.2) |
| **Excluded** | SE Projector | Always 0 W (dead series) |

## 5. Exclusion rules

| Rule | Applies to | Rule | Why | Hours left out (train) |
| --- | --- | --- | --- | --- |
| **R0** | all | Outside the agreed periods | Apr–May 2020 is the COVID lockdown before the train start; SW 2025 is unusable | 30,805 (whole file) |
| **R1** | all | Dead series or rated "Do not use" | SE Projector always 0 W; SW 2025 and NW Hand Dryer 2025 failed the quality check (Team B report) | 18,240 |
| **R2** | all | No valid energy value | Missing hour, zero record or implausible counter step: no true value exists | 21,399 |
| **R3** | all | Value was interpolated | Gaps ≤ 3 h were filled in for convenience; an estimate is neither a lesson nor a test | 12,136 |
| **R4** | all | Event-driven load | Hand dryers cannot be forecast per hour (F2.2) | 32,203 |
| **R5** | **train only** | Energy (counter) and power × 1 h differ > 20 % | The two measurements contradict each other, so the true value is uncertain; 5.4 % of train-window hours | 9,087 |
| **R6** | **train only** | Isolated power spike (Hampel filter) | One-off outliers teach the model nothing; 0.6 % of train-window hours. Kept in validation/test so scores stay honest | 1,147 |

**Experiment variant V1 – without 2020 (`include_train_no2020`).** Subteam C found that 2020 behaves differently (F4.2). The data does not show one clear direction, however:
- Working-day occupancy (09–17 h, Jun–Dec) was lower in 2020 than in 2021 in NW (46 % vs 51 %) and SW (12 % vs 59 %), but higher in SE (79 % vs 36 %).
- Lighting and Plugs & Sockets used less energy in 2020 than in 2021 in five of seven series, but the change from 2021 to 2022 is just as large (e.g. SE Plugs & Sockets −73 %, SE Lighting +182 %).
- Dropping 2020 removes about a third of the training hours, including the only summer of 2020.

So 2020 stays in the main training set, and Team D trains each model twice (with and without 2020) and keeps the version that scores better on the **validation** period.

## 6. What is deliberately **not** left out

| Kept | Why |
| --- | --- |
| Extreme but real temperatures (`flag_temp_extreme`) | The January 2021 cold and the August 2021 heat wave really happened; the model must learn how HVAC reacts to them |
| Holidays, weekends, August | Real low-use days; they are features, not errors |
| Hours rebuilt after a partial sum or counter spike | The energy value comes from valid counter readings around that hour, so it is trustworthy |
| Hours where energy comes from power × 1 h | A real measurement, only from the other meter channel (1.3 % of train hours) |
| SW series rated "Use with caution" | Usable; `series_caution = 1` lets Team D report them separately |
| 2025 series with a level shift (NW Lighting, NW HVAC, SE Lighting) | Kept in test_2025 with `level_shift_2025 = 1`, to be reported separately |

## 7. Result

| Split | Rows used | Of which priority | Of which secondary |
| --- | --- | --- | --- |
| train (`include_train`) | 229,086 | – | – |
| train without 2020 (`include_train_no2020`) | 157,319 | – | – |
| validation (`include_eval`) | 52,566 | 37,746 | 14,820 |
| test_2023 (`include_eval`) | 17,185 | 12,516 | 4,669 |
| test_2025 (`include_eval`) | 13,470 | 9,825 | 3,645 |

Share of train-period hours kept per series (`include_train`):

| Series | Kept | Series | Kept |
| --- | --- | --- | --- |
| NE HVAC | 83 % | SE HVAC | 86 % |
| NE Plugs & Sockets | 99 % | SE Lighting | 84 % |
| NW HVAC | 92 % | SE Plugs & Sockets | 84 % |
| NW Lighting | 92 % | SE Emerg. Lighting | 74 % |
| NW Plugs & Sockets | 96 % | SW Lighting | 69 % |
| NW Emerg. Lighting | 94 % | SW Plugs & Sockets | 72 % |
| NW RACK | 100 % | SW Emerg. Lighting | 73 % |
|  |  | SW RACK (until Dec 2021) | 80 % |

Every series keeps at least 69 % of its training hours, so no series loses so much data that it cannot be modelled. Per-series and per-reason counts are in `training_data_summary.xlsx`.

## 8. Columns in `cedint_f1_model_ready.csv.gz`

| Group | Columns |
| --- | --- |
| Keys | `timestamp_utc`, `timestamp_local`, `zone`, `zone_code`, `load_type`, `n_devices`, `era` |
| Use | `split`, `model_scope`, `include_train`, `include_train_no2020`, `include_eval`, `exclusion_reason` |
| Context | `recommendation`, `series_caution`, `level_shift_2025`, `energy_source` |
| Target | `energy_wh_model` (Wh per hour) |
| Features | `hour_local`, `dayofweek_local`, `month_local`, `is_weekend`, `is_holiday`, `is_august_low_use`, `flag_covid_2020`, `temp_c`, `hum_pct`, `lum_lux`, `occupancy`, `lag_24h`, `lag_168h` |

Notes on features:
- Calendar features use **local** time; the raw timestamps are UTC.
- `lag_24h` and `lag_168h` are the target 24 h and 168 h earlier in the same series and period. They are known at forecast time for a day-ahead forecast issued at midnight. They can be empty at the start of a period or after a gap.
- Environmental features are empty for zone NE (no sensors) and in about 2 % of other hours. LightGBM handles empty values; SARIMAX needs them filled in (for example with the previous hour) or replaced by outdoor weather.
- `current_a` is **not** included: in 2020–23 it is underestimated for multi-device series (F6.2).
- Outdoor weather (Open-Meteo, T26) can be joined on `timestamp_utc`.

## 9. How to use it

```python
import pandas as pd
df = pd.read_csv("cedint_f1_model_ready.csv.gz", parse_dates=["timestamp_utc", "timestamp_local"])

series = (df["zone"] == "NW") & (df["load_type"] == "HVAC")
train = df[series & (df["include_train"] == 1)]           # or include_train_no2020 for variant V1
valid = df[series & (df["split"] == "validation") & (df["include_eval"] == 1)]
test  = df[series & df["split"].str.startswith("test") & (df["include_eval"] == 1)]

features = ["hour_local", "dayofweek_local", "month_local", "is_weekend", "is_holiday",
            "is_august_low_use", "temp_c", "hum_pct", "lum_lux", "occupancy", "lag_24h", "lag_168h"]
X_train, y_train = train[features], train["energy_wh_model"]
```

Then save the forecasts for the validation and test rows in the agreed format (`timestamp_utc, zone, load_type, model, split, y_true, y_pred`) and run `team_b_eval.py`. Give the two variants different model names (for example `lightgbm` and `lightgbm_no2020`), so the evaluation compares them automatically. Record the filters used in the experiment logbook.

## 10. Limitations

- test_2023 covers only two winter months; test_2025 covers only late summer and autumn.
- For SW, 20–31 % of training hours are left out; SW forecasts should state this.
- R5 uses a 20 % tolerance. A stricter or looser value would change the training set slightly; the choice is documented and can be changed in one line of `make_training_data.py`.
