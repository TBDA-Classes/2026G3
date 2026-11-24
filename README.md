# CeDInt Floor 1 – Data Cleaning, Forecasting & Analytics Pipeline (TBDA Group 3)

This repository turns the raw CeDInt floor-1 sensor exports into one clean, hourly dataset with quality flags, and provides the full forecasting, ASHRAE Guideline 14 / skill-score evaluation, and interactive dashboard pipeline for the TBDA project (ETSII, UPM).

**Principle: nothing is deleted.** Raw values are kept next to the cleaned ones. Problems get a 0/1 flag column, and a clean value is left empty only when the raw value is physically impossible. Every change is a step in the code, so all results can be reproduced and audited.

## Current Project Status (November 2026 – Sprint 4 / DataPack v1.0)

- **Data Pipeline & Model-Ready Dataset (`v0.4`):** Completed (`cleaning_and_eda/clean_cedint.py` & `cleaning_and_eda/T32_make_training_data.py`), integrating physical anomaly corrections, spatial/environmental tables (`data/`), and calendar drivers (`cleaning_and_eda/Task_F4_3C.py`).
- **Multi-Model Day-Ahead & Multi-Horizon Forecasting:** Evaluated across floor-1 zones (`NE`, `NW`, `SE`, `SW`) using **Chronos-Bolt**, **GBM**, **LightGBM (`T29`)**, **Random Forest**, **CatBoost**, **Chronos + GBM Hybrid**, sensorless NE models (`T31`), MinT floor-total reconciliation (`T30`), and 1–7 day multi-horizon models (`T37`).
- **Final Selection & Validation (`T38` / `T40` / `T42`):** Best model selected per series on unseen late-2022 validation hours (7 Chronos-Bolt, 3 GBM, 3 Hybrid, 1 RF without 2020), achieving positive skill over `naive_day` in 37/39 cases (median skill 0.30 on test 2023 and 0.19 on test 2025). See `docs_and_slides/CeDInt_F1_Results_Summary.md`.
- **Interactive Dashboard (`T36`):** Production-ready Streamlit app (`T36_dashboard_app.py`) for consumption exploration, drivers, best-model scorecard, floor totals, and data quality.

## Quickstart & Repository Structure (`DataPack v1.0`)

- **Interactive Dashboard (`T36`):** See launch command and instructions in `docs_and_slides/T36_README_dashboard.md` (uses `T36_dashboard_app.py`, `best_model_predictions_final.csv`, and `cedint_f1_hourly_clean.csv.gz` at root).
- **`data/`:** Model-ready dataset (`T32`), spatial/environmental tables, Open-Meteo Madrid weather.
- **`cleaning_and_eda/`:** Data cleaning (`clean_cedint.py`), dataset builder, leakage checks (`T37`), and EDA notebooks.
- **`models/`:** Forecasting models (`T29`, `T30`, `T31`, CatBoost, RF, Chronos, Blends, `T37`).
- **`predictions_and_eval/`:** Predictions, final evaluation (`TeamB_T38_final_evaluation.xlsx`), bias checks (`T40`).
- **`figures/`:** Diagnostic, EDA, multi-horizon (`F37*`), sensorless NE (`F_T31_*`), and floor-plan SVGs.
- **`docs_and_slides/`:** CRISP-DM Sprint 4 report, Experiment Logbook (Entries 1–23), Backlog, executive summary (`CeDInt_F1_Results_Summary.md`, `T42`), and presentation slides.
- **`archive/`:** Legacy drafts, intermediate ZIP exports, and superseded prediction runs.
