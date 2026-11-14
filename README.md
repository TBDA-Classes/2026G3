# CeDInt Floor 1 – Data Cleaning, Forecasting & Analytics Pipeline (TBDA Group 3)

This repository turns the raw CeDInt floor‑1 sensor exports into one clean, hourly dataset with quality flags, and provides the full forecasting, ASHRAE Guideline 14 evaluation, and interactive dashboard pipeline for the TBDA project (ETSII, UPM).

**Principle: nothing is deleted.** Raw values are kept next to the cleaned ones. Problems get a 0/1 flag column, and a clean value is left empty only when the raw value is physically impossible. Every change is a step in the code, so all results can be reproduced and audited.

## Current Project Status (November 2026 – Sprint 3/4)

- **Data Pipeline & Model-Ready Dataset (v0.4):** Completed (`clean_cedint.py` & `T32_make_training_data.py`), integrating physical anomaly corrections and calendar drivers (`Task_F4_3C.py`: `is_holiday`, `is_august_low_use`, `is_weekend`, `flag_covid_2020`).
- **Multi-Model Day-Ahead Forecasting:** Implemented and evaluated across floor-1 zones (`NE`, `NW`, `SE`, `SW`) using **SARIMAX**, **LightGBM**, **Gradient Boosting (GBM)**, **Random Forest**, **CatBoost**, **Chronos** (time-series foundation model), and a **Blend (Chronos + GBM)** ensemble.
- **Normative Validation:** Evaluated against **ASHRAE Guideline 14** hourly criteria (CV(RMSE) ≤ 30 % and |NMBE| ≤ 10 %) via `team_b_eval.py` and consolidated in `Model_Comparison_ASHRAE.xlsx`.
- **Interactive Dashboard:** Streamlit prototype deployed in `T36_dashboard_app.py` (see `T36_README_dashboard.md`) for consumption exploration, driver analysis, forecast vs. actual comparison, and data quality reporting.
- **Project Management:** Tracked in `TBDA_Product_Backlog_Report_v10_Scrum_MVC_final.md` and `EXPERIMENT_LOGBOOK.md`.

## Repository contents

| File | Purpose |
| --- | --- |
| `clean_cedint.py` | Full cleaning pipeline: raw Excel files → clean hourly dataset (`v0.4`), quality overview, consistency checks, anomaly log and data dictionary |
| `T32_make_training_data.py` | Model-ready training data: decides per hour whether it may be used for training or scoring (`include_train` / `include_eval`), with the reason (see `T32_TRAINING_DATA_METHODOLOGY.md`) |
| `Task_F4_3C.py` | Feature engineering script adding national & Comunidad de Madrid holidays (`is_holiday`) and August low-use day flags (`is_august_low_use`) |
| `make_figures.py` | Creates the figures F1–F10 of the Team B data-quality report |
| `team_b_eval.py` | Evaluation toolkit: checks a predictions file, computes MAE, RMSE, CV(RMSE), NMBE and ASHRAE pass/fail, error breakdowns, anomaly candidates and the flagged-hours sensitivity test (backlog F6.3, F6.4, F6.6, F6.7, F7.1) |
| `make_reference_baseline.py` | Naive reference forecasts (same hour yesterday / last week) in the agreed prediction format |
| `secondary_loads.py` | Characterisation of emergency lighting, hand dryers and RACK (backlog F2.2) |
| `F1.2_T29_dayahead_models_MH.Rmd` | Day-ahead SARIMAX and LightGBM modeling & cross-validation across zones |
| `F1.3_T30_floor1_total_forecast_MH.R` | Floor 1 total load aggregation across all zones |
| `GBM_forallzones.ipynb` / `gbm_model.ipynb` | Gradient Boosting (GBM) forecasting across all zones and sensors |
| `RF_general_zone_load.py` | Random Forest day-ahead forecasting across zones |
| `CatBoost_general_zone_load.py` | CatBoost day-ahead forecasting across zones |
| `Chronos_general_zone_load.py` | Chronos foundation model time-series forecasting across zones |
| `blend_model_chronos&gbm.ipynb` | Hybrid ensemble blending Chronos and GBM predictions |
| `Model_Comparison_ASHRAE.xlsx` | Consolidated ASHRAE Guideline 14 performance comparison across models and zones |
| `T36_dashboard_app.py` | Dashboard prototype (T36 / F8.1, Streamlit): overview, consumption, drivers, forecast vs actual (ASHRAE 14) and data quality. Works without models via the reference forecasts; Team D's predictions can be uploaded |
| `requirements.txt` | Python packages needed |
| `T36_requirements_dashboard.txt` | Python packages needed for the Streamlit dashboard |
| `figures/` | Figures F1–F11 (PNG) |
| `CeDInt_F1_quality_and_anomalies.xlsx` | Quality and anomaly results (optional; the pipeline regenerates it) |

The data itself is **not** stored in this repository. It lives in the team's shared Drive:

- Raw input files: `01_raw/`
- Cleaned outputs: `03_processed/`

## Requirements

- Python 3.10 or newer
- Detailed cleaning and training instructions are available in `README_T32_datacleaning.md` and `T32_TRAINING_DATA_METHODOLOGY.md`.
- Dashboard setup and launch instructions are available in `T36_README_dashboard.md`.
