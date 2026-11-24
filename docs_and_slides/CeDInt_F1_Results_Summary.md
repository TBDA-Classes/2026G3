# CeDInt floor 1 – Day-ahead energy forecasting: results summary

*CeDInt-SEF – DataPack Energy Forecaster · Tools for Big Data Analysis (UPM) · Group 3 · Backlog task T42 (F8.3)*

## 1. Objective

The team forecasts the hourly electricity use of floor 1 of CeDInt (UPM) one day ahead, issued at local midnight for the next 24 h, per zone (NE, NW, SE, SW) and load type, and for the floor-1 total. The work followed CRISP-DM within Scrum over four sprints (1 Oct – 25 Nov 2026).

## 2. Data and method

The data cover hourly records from Apr 2020 to Feb 2023 and, after a 902-day gap, minute records aggregated to hours for 18 Aug – 13 Oct 2025. The clean dataset (v0.4, 470,680 rows) flags problems instead of deleting them; 86 % of hours have a usable target. Models were trained on 1 Jun 2020 – 30 Jun 2022. For each of the 14 series, the candidate with the lowest CV(RMSE) on 16 Oct – 31 Dec 2022, a window out-of-sample for every model, was kept (Chronos-Bolt, GBM, LightGBM, Random Forest, CatBoost or a Chronos + GBM hybrid) and scored once on two unseen tests: 1 Jan – 28 Feb 2023 and 18 Aug – 13 Oct 2025 (NE, NW, SE only). The headline measure is the skill score, 1 − RMSE(model) / RMSE(naive), where the naive forecast is the same hour yesterday; ASHRAE Guideline 14 is a reference only.

## 3. Key results

| Series meeting the load-type target | Validation | Test 2023 | Test 2025 |
|---|:---:|:---:|:---:|
| Constant loads (CV(RMSE) ≤ 15 %) | 4 of 4 | 4 of 4 | 2 of 3 |
| Plugs & Sockets (CV(RMSE) ≤ 30 %) | 2 of 4 | 2 of 4 | 1 of 3 |
| HVAC (30–50 %, \|NMBE\| ≤ 10 %, positive skill) | 1 of 3 | 2 of 3 | 2 of 3 |
| Lighting (mainly daily energy and timing; not in the hourly count) | – | – | – |
| **Total** | **7 of 14** | **8 of 14** | **5 of 11** |

- **Chosen models:** Chronos for 7 series, GBM for 3, the hybrid for 3 and Random Forest without 2020 for 1. The hybrid wins 3 of the 10 series it covers on unseen 2022 hours.
- **Skill:** positive in 37 of 39 series-period combinations; median skill 0.31 (validation), 0.30 (test 2023) and 0.19 (test 2025). Only NE Plugs & Sockets (−0.20) and NW Plugs & Sockets (−0.15) in 2025 fall below the naive forecast. Hourly lighting errors stay high (SE 255 %, SW 330 % on validation), but NW Lighting reaches a daily CV(RMSE) of 39 % and 0 h timing error.
- **Floor-1 total (MinT reconciliation):** on test 2023, CV(RMSE) 37.4 % against 45.2 % for the seasonal naive (same hour last week), skill +0.17, still above 30 %. Validation (38.3 % vs 50.6 %) is optimistic: the reconciliation weights were learned there.
- **Multi-day outlook (T37):** a GBM per horizon still beats the seasonal naive at 7 days in 17 of 18 cases. NW HVAC 2023 error grows from 50 % (1 day) to 80 % (7 days); the floor total without SW in 2025 reaches 28.3 % at 1 day and 31–33 % up to 7 days. Measured weather served as a perfect forecast (upper bound).

## 4. What explains the errors, drivers and limits

*NMBE = (actual − forecast) / mean actual: positive = too low*

- **Meter faults, not the model:** NE HVAC test 2023 CV(RMSE) falls from 688 % to 9 % without flagged hours.
- **Level shifts in building use:** 6 series-period cases have \|NMBE\| above 10 %. A 7-day level update, using only data known at midnight, brings 2 of them within target (NW Plugs & Sockets 2025: −10.3 % → −1.0 %; SE Plugs & Sockets 2025: −18.9 % → −0.8 %).
- **Drivers (SHAP, T33):** SHAP explained the chosen models (NE HVAC, NW Plugs & Sockets, SW Lighting): recent consumption dominates, and the top GBM driver, `roll_mean_24`, is the leaky feature (below).
- **Leakage found in our self-audit:** the GBM's 24-hour rolling mean includes the forecast hour, and GBM, Random Forest and CatBoost use same-hour indoor readings unknown a day ahead. Fixing this raises the GBM's NW HVAC test 2023 error from 29.6 % to 49.6 %, so GBM, Random Forest and CatBoost scores, and the GBM, hybrid and Random Forest choices, are optimistic until the leak-free re-run.

## 5. Value for the building manager and next steps

An interactive Streamlit dashboard (T36) shows consumption, drivers, forecast vs actual, the best-model scorecard, the floor-1 total and data quality, with actions and alerts. Savings in euros are not yet quantified (next step: the CeDInt tariff). Roadmap: now, re-run model selection with leak-free features; next, Chronos-2 with covariates; then, rolling re-fit and real weather forecasts. DataPack v1.0 goes to Moodle by 14 Dec 2026.


