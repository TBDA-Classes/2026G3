# T37 – text to paste into the shared documents

## A. New entry for `EXPERIMENT_LOGBOOK.md` (after Entry 18)

### Entry 19 — 14/11/2026

| Field | Content |
|---|---|
| **Date** | 14/11/2026 |
| **Dataset version** | v0.4 (`T32_cedint_f1_model_ready.csv.gz`) + Open-Meteo outdoor weather (`openmeteo_madrid_hourly.csv`, T26) |
| **Cleaning steps** | • No cleaning of values: the file was already clean.<br>• Training rows `include_train = 1`, scored rows `include_eval = 1`; for the floor totals an hour is used only if **all** parts are usable (never a partial sum).<br>• Lags computed on a complete hourly grid by timestamp, so they are empty across the 902-day gap.<br>• All horizons, scenarios and baselines scored on the same hours (value 168 h earlier must exist). |
| **Model tested** | • **Multi-day forecasts (F1.4 / T37)**, direct strategy (one model per horizon) for horizons 1, 2, 3, 5 and 7 days.<br>• Targets: NE, NW, SE HVAC; `FLOOR_TOTAL` (10 core series, as T30); `FLOOR_TOTAL_noSW` (8 series, so 2025 can be tested).<br>• GBM with outdoor weather used as a perfect forecast ("weather", best case) and GBM without weather ("no_weather", worst case).<br>• Baselines: seasonal naive (same hour last week) and persistence (same hour d days earlier). |
| **Parameters tested** | • `GradientBoostingRegressor(n_estimators=100, learning_rate=0.1, max_depth=4, random_state=42)` = settings of `GBM_forallzones.ipynb`; missing values → −1.<br>• Features for horizon d: target lags ≥ 24·d h (24·d, 24·d+24, 168, 336 h), 24-h and 7-day means ending at t − 24·d, same-hour mean of 7 days; calendar flags; weather scenario adds Open-Meteo temperature, humidity, radiation, wind, heating/cooling degree-hours, 6-h and 24-h mean temperature. Indoor sensors not used (not known days ahead).<br>• Split as T32: train 2020-06-01 → 2022-06-30; validation 2022-H2; test_2023 Jan–Feb 2023; test_2025 18 Aug – 13 Oct 2025. |
| **Results obtained** | • **CV(RMSE) %, GBM + weather, 1 d → 7 d:** NW HVAC 2023 50.0 → 80.0; NW HVAC 2025 93.6 → 99.7; SE HVAC 2023 51.6 → 54.1; SE HVAC 2025 42.8 → 43.9; NE HVAC 2025 18.3 → 20.1; FLOOR_TOTAL 2023 44.0 → 43.8 (non-monotone, 542 h); FLOOR_TOTAL_noSW 2023 47.5 → 54.7; FLOOR_TOTAL_noSW 2025 28.3 → 32.5.<br>• **ASHRAE 14 pass:** NE HVAC 2025 at every horizon; FLOOR_TOTAL_noSW 2025 at 1 day only (28.3 %, NMBE +0.3 %). No other series passes at any horizon.<br>• GBM beats the seasonal naive at 7 days in 17 of 18 series-period-scenario combinations; skill falls with the horizon (NW HVAC 2023: 0.52 at 1 d → 0.23 at 7 d).<br>• NMBE of NW HVAC 2023 grows from +9 % (1 d) to +41 % (7 d): under-forecast of cold-weather peaks.<br>• Perfect weather changes 1-day CV(RMSE) by < 3 points in most series; it helps NW HVAC 2025 at 7 d (99.7 vs 109.7 %) and slightly worsens the 2023 floor totals.<br>• Side check (`T37_check_gbm_leakage.py`): in `GBM_forallzones.ipynb`, `roll_mean_24` includes the hour being forecast (target leakage). NW HVAC test 2023: 29.6 % as is → 49.6 % with the rolling mean shifted 24 h (in line with T29 LightGBM 47.2 %).<br>• Files: `T37_multihorizon_results.xlsx`, `T37_multihorizon_predictions.csv.gz`, `T37_experiment_log_rows.csv` (280 rows), `T37_check_gbm_leakage_results.csv`, figures F37a–F37d, `T37_REPORT.md`. |
| **Interpretation** | • Accuracy decays with the horizon, strongly for NW HVAC and slowly for SE HVAC and the floor totals; the model keeps an advantage over the naive up to 7 days, so a 2–3-day outlook is useful for planning.<br>• Multi-day forecasts can stay in scope as an indicative product (shown with their horizon-specific error), not as an ASHRAE-validated one: almost no series passes even at 1 day.<br>• With longer horizons the GBM shifts from past load to weather, but with two training years it partly uses weather as a proxy for the season, so perfect weather gives little gain; a real weather forecast would give even less. |
| **Issued found** | • Target leakage in `roll_mean_24` of `GBM_forallzones.ipynb` (the NW HVAC 29.6 % pass in `Model_Comparison_ASHRAE.xlsx` is not reachable day-ahead); the Blend inherits it. To fix before T39.<br>• `GBM_forallzones.ipynb` looks for load type "Emergency Lighting", but the file uses "Emerg. Lighting", so those series are skipped.<br>• Test sets are short (floor total 2023: 542 h) and seasonal; the decay curves of the totals are noisy (± 5 points).<br>• NE HVAC 2023 CV(RMSE) ≈ 690 % is not meaningful (mean ≈ 7 Wh/h).<br>• No archive of real weather forecasts: the weather scenario is an upper bound. |
| **Extras** | • Task executed by Riccardo Tardanico. Covers backlog item **F1.4**, T37. Files: `T37_multihorizon_forecast.py`, `T37_check_gbm_leakage.py`, `T37_REPORT.md`, `outputs_T37/`. |

---

## B. Rows to update in the Product Backlog (v11)

**Section 4 – product backlog, row T37:**

| ID | Type of work | Person who has executed the task | Quick description of the task | What do I need | What I will deliver | Priority | Sprint | Status |
|---|---|---|---|---|---|---|---|---|
| **T37** (F1.4) | Modelling & Forecasting | Riccardo Tardanico | Extend the best models to multi-day horizons (1, 2, 3, 5, 7 days, direct strategy) for HVAC (NE, NW, SE) and the floor total, with and without weather, and measure how accuracy decays with the horizon | `T32_cedint_f1_model_ready.csv.gz`; Open-Meteo weather (T26); GBM settings (T29); floor-total definition (T30) | `T37_multihorizon_forecast.py`, `T37_multihorizon_results.xlsx`, figures F37a–F37d, `T37_REPORT.md`: multi-period forecasts and a horizon-vs-accuracy comparison | Medium | 4 | 🟢 Complete |

**"Changes since" table, new row:**

| ID | previous status | new status | Evidence |
|---|---|---|---|
| **T37** (F1.4) | Not Started | 🟢 Complete | Riccardo Tardanico, `T37_multihorizon_forecast.py` → `T37_multihorizon_results.xlsx` (CV(RMSE), NMBE, skill vs naive per horizon 1–7 days) and figures F37a–F37d: accuracy decays from 50 % to 80 % CV(RMSE) for NW HVAC 2023 and from 28 % to 33 % for the floor total without SW in 2025; GBM beats the seasonal naive up to 7 days in 17 of 18 cases. Side check `T37_check_gbm_leakage.py`: target leakage in `roll_mean_24` of the GBM notebook (NW HVAC 29.6 % → 49.6 %); logbook entry 14/11/2026 (Entry 19) |

**Section 7 – open decisions, point 5 (answer):**
> Multi-period forecasts (F1.4): kept in scope as an indicative outlook up to 7 days, shown with the horizon-specific error; not ASHRAE-validated (T37).

**Header counters:** Progress becomes 🟢 32 Complete · 🟡 9 In Progress · 🔵 3 Not Started.
