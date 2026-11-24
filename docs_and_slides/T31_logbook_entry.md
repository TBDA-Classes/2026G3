# T31 – Text for the experiment logbook and the product backlog

## Experiment logbook entry (11/11/2026)

**T31 (F3.3) – Forecast of zone NE without environmental sensors (Riccardo)**

- **Goal:** forecast NE HVAC and NE Plugs & Sockets day-ahead, even though NE has no Temp, Hum, Lum or Pres sensors, and measure how much a proxy from other zones helps.
- **Data:** `cedint_f1_hourly_clean.csv` (v0.3), target `energy_wh_model`, rows with `usable_for_model = 1`.
- **Set-up:** split from T32 (train 2020-06 to 2022-06, validation 2022-H2, test 2023 and 2025). Forecast issued at 00:00, using only lags of 24 h or more. HistGradientBoosting anchored on lag24 with absolute-error loss.
- **Scenarios:** M0 no environment · M1 NW proxy · M2 adjacent proxy (NW + SE) · M3 floor proxy (NW + SE + SW) · M4 ideal same-hour proxy · M0d level model with squared error · naive-day and seasonal-naive baselines.
- **Results:**
  - NE Plugs & Sockets passes ASHRAE 14 in every period: best on validation is M1 at 25.2 %; test 2023 is 27.1 %; test 2025 is 8.3–8.9 %, against 10.3 % for naive day.
  - NE HVAC passes on test 2025 (19.2–20.1 %, against 23.1 % for naive day) and fails on 2023, where 11 spike hours carry 57.5 % of the energy.
  - The proxies change CV(RMSE) by at most about 3 points. In the leave-one-zone-out test on SE and NW, own sensors, proxy and no environment are within about 3 points of each other, the only exception being NW HVAC on 2025.
- **Findings:**
  - (1) Anchoring the model on lag24 with absolute-error loss is necessary: the usual level model with squared error loses to naive day (31.5 % against 26.5 % on validation).
  - (2) NE Plugs & Sockets switches between a ~190 Wh base load and a ~24 Wh low-power state, for example in Oct–Nov 2022 and Jan 2023. These switches are confirmed by both power and counter readings and are not predictable from the drivers.
- **Next:** run M5/M6 with the T26 Open-Meteo file; send the spike hours and low-power periods to T35; send `T31_NE_predictions.csv` to T34, T38 and T40.
- **Files:** `T31_ne_forecast.py`, `T31_NE_results.xlsx`, `T31_NE_predictions.csv`, `T31_NE_Forecast_Report.docx`, figures F_T31_1–6.

## Rows for experiment_log.xlsx

The 32 test rows, already in T20 format, are in sheet **Experiment_log_rows** of `T31_NE_results.xlsx`. Copy and paste them.

## Product backlog update (T31 row)

| ID | Person | Status | Evidence |
|---|---|---|---|
| **T31** (F3.3) | Riccardo | 🟢 Complete | `T31_ne_forecast.py` → `T31_NE_results.xlsx`, `T31_NE_predictions.csv`, figures F_T31_1–6 and report `T31_NE_Forecast_Report.docx`. NE forecast day-ahead with no proxy, NW, adjacent (NW + SE) and floor proxies. Plugs & Sockets passes ASHRAE 14 in every period (CV(RMSE) 25–27 % in 2022-H2 and 2023, 8–9 % in 2025). HVAC passes in 2025 (19 %) and fails in 2023 because of 11 spike hours (57 % of the energy). Proxies change accuracy by at most about 3 points; the leave-one-zone-out test on SE and NW confirms that own sensors add little day-ahead. Limits stated in the report, section 5. Logbook entry 11/11/2026. |
