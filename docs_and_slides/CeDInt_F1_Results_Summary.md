# CeDInt floor 1 – Day-ahead energy forecasting: results summary

*CeDInt-SEF – DataPack Energy Forecaster · Tools for Big Data Analysis (UPM) · Group 3 · Backlog task T42 (F8.3)*

## 1. Objective

The team forecasts the hourly electricity use of floor 1 of CeDInt (UPM) one day ahead, issued at local midnight for the next 24 h, per zone (NE, NW, SE, SW) and load type, and for the floor-1 total. The work followed CRISP-DM within Scrum over four sprints (1 Oct – 25 Nov 2026).

## 2. Data and method

The data cover hourly records from Apr 2020 to Feb 2023 and, after a 902-day gap, minute records aggregated to hours for 18 Aug – 13 Oct 2025. The clean dataset (v0.4, 470,680 rows) flags problems instead of deleting them; 86 % of hours have a usable target. Models were trained on 1 Jun 2020 – 30 Jun 2022. For each of the 14 series, the candidate with the lowest CV(RMSE) on 16 Oct – 31 Dec 2022, a window out-of-sample for every model, was kept (Chronos-Bolt, GBM, LightGBM, Random Forest, CatBoost or a Chronos + GBM hybrid) and scored once on two unseen tests: 1 Jan – 28 Feb 2023 and 18 Aug – 13 Oct 2025 (NE, NW, SE only). After a self-audit, the GBM and hybrid were rebuilt without leaking inputs and the choice was re-run (audit notebooks 00–04); these are the final results. The headline measure is the skill score, 1 − RMSE(model) / RMSE(naive), where the naive forecast is the same hour yesterday; ASHRAE Guideline 14 is a reference only.

## 3. Key results

| Series meeting the load-type target | Validation | Test 2023 | Test 2025 |
|---|:---:|:---:|:---:|
| Constant loads (CV(RMSE) ≤ 15 %) | 4 of 4 | 4 of 4 | 2 of 3 |
| Plugs & Sockets (CV(RMSE) ≤ 30 %) | 2 of 4 | 2 of 4 | 2 of 3 |
| HVAC (30–50 %, \|NMBE\| ≤ 10 %, positive skill) | 1 of 3 | 2 of 3 | 2 of 3 |
| Lighting (mainly daily energy and timing; not in the hourly count) | – | – | – |
| **Total** | **7 of 14** | **8 of 14** | **6 of 11** |

- **Chosen models:** Chronos for 10 series, the leak-free hybrid for 2 (NE Plugs & Sockets, NW Lighting), Random Forest without 2020 for NE HVAC (a tie with Chronos) and CatBoost for NW Plugs & Sockets. Before the audit: Chronos 7, GBM 3, hybrid 3, Random Forest 1.
- **Skill:** positive in all 39 series-period combinations (before the audit 37 of 39); median skill 0.27 (validation), 0.30 (test 2023) and 0.20 (test 2025). Hourly lighting errors stay high (SE 354 %, SW 314 % on validation), but NW Lighting reaches a daily CV(RMSE) of 41 % and 0 h switch-on error.
- **Floor-1 total (MinT reconciliation):** on test 2023, CV(RMSE) 37.4 % against 45.2 % for the seasonal naive (same hour last week), skill +0.17, still above 30 %. Validation (38.3 % vs 50.6 %) is optimistic.
- **Multi-day outlook (T37):** a GBM per horizon still beats the seasonal naive at 7 days in 17 of 18 cases. NW HVAC 2023 error grows from 50 % (1 day) to 80 % (7 days); the floor total without SW in 2025 reaches 28.3 % at 1 day and 31–33 % up to 7 days. Measured weather served as a perfect forecast (upper bound).

## 4. What explains the errors, drivers and limits

*NMBE = (actual − forecast) / mean actual: positive = too low*

- **Meter faults, not the model:** NE HVAC test 2023: CV(RMSE) 691.6 % → 13.2 % without flagged hours (a diagnostic).
- **Level shifts in building use:** 8 series-period cases have \|NMBE\| above 10 %; a 7-day level update (data known at midnight) brings 6 within target (e.g. SE Plugs & Sockets 2023: +15.4 % → −0.7 %). Not fixed: NE HVAC 2023, SE Lighting 2025.
- **Leakage found and corrected:** the GBM's 24-hour rolling mean included the forecast hour, and same-hour indoor readings are unknown a day ahead; fixing this raises the GBM's NW HVAC test 2023 error from 29.6 % to 49.5 %. SHAP (T33) had shown `roll_mean_24` as the top GBM driver. The corrected GBM is chosen for no series; Random Forest and CatBoost were not retrained (NW Plugs & Sockets, CatBoost, still to check).

## 5. Value for the building manager and next steps

A Streamlit dashboard (T36) with seven views shows consumption, drivers, forecasts against actuals, the best-model scorecard, the floor total and data quality, with actions and alerts. The product is a historical forecasting prototype, not yet a live nightly system; savings in euros are not quantified (they need the CeDInt tariff). Roadmap: now, retrain Random Forest and CatBoost with strict day-ahead inputs; next, Chronos-2 with covariates and constrained hybrids; then, rolling re-fit and real weather forecasts. DataPack v1.0: Moodle by 14 Dec 2026.

