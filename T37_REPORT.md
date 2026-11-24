# T37 (F1.4) – Multi-day forecast horizons for HVAC and the floor-1 total

**Author:** Riccardo Tardanico · **Date:** 14 November 2026 · **Sprint:** 4
**Backlog item:** T37 (F1.4) – *Extend the best models to multi-day horizons for HVAC and the floor total and measure how accuracy decays with the horizon*
**Depends on:** T29 (day-ahead models), T30 (floor total), T32 (model-ready data and split), T26 (outdoor weather), T19 (metrics)
**Feeds:** T38 (ASHRAE table), T39 (model comparison), T41 (final presentation), open decision 5 of the backlog (are multi-period forecasts in scope?)

---

## 1. Question

The building manager asked for day-ahead **and multi-period** forecasts (backlog, section 2). Before multi-day forecasts are promised, the team needs to know:

1. How much accuracy is lost when the forecast is issued 2, 3, 5 or 7 days ahead instead of 1 day ahead?
2. Up to which horizon is the model still better than the simplest alternative (the same hour last week)?
3. How much of the remaining accuracy depends on knowing the weather in advance?

## 2. Data and targets

| Item | Choice |
|---|---|
| Input | `T32_cedint_f1_model_ready.csv.gz` (dataset v0.4) and `openmeteo_madrid_hourly.csv` (T26) |
| Split | Same as T32: train 2020-06-01 → 2022-06-30 (`include_train = 1`); validation 2022-H2; test_2023 (Jan–Feb 2023); test_2025 (18 Aug – 13 Oct 2025) |
| HVAC targets | NE HVAC, NW HVAC, SE HVAC (SW has no HVAC) |
| `FLOOR_TOTAL` | Sum of the 10 core series (HVAC, Lighting, Plugs & Sockets wherever they exist), the same total as T30 |
| `FLOOR_TOTAL_noSW` | Same sum without zone SW (8 series). Added because SW has no 2025 data, so `FLOOR_TOTAL` cannot be tested in 2025 (same issue as T30, logbook Entry 17) |
| Totals | An hour of a total is used only if **all** its parts are valid and usable in that hour: a total is never a partial sum |

## 3. Method

**Direct strategy, one model per horizon.** For each horizon *d* ∈ {1, 2, 3, 5, 7} days a separate model is trained. The forecast for hour *t* uses target values only up to *t − 24·d* hours:

| Feature group | Features |
|---|---|
| Past load | lags of 24·d h, 24·d + 24 h, 168 h and 336 h (only those ≥ 24·d h); mean of the 24 h and of the 168 h ending at *t − 24·d*; same-hour mean of the 7 days ending at *t − 24·d* |
| Calendar | local hour, weekday, month, weekend, holiday, August low use, COVID-2020 flag |
| Outdoor weather (scenario “weather” only) | Open-Meteo temperature, humidity, radiation, wind at hour *t*; heating (base 18 °C) and cooling (base 24 °C) degree-hours; mean temperature of the last 6 h and 24 h |

Indoor sensors (`temp_c`, `hum_pct`, `lum_lux`, `occupancy`) are not used: they are not known days ahead and zone NE has none.

**Two weather scenarios.** The history contains measured weather but no weather *forecasts*. So the model is run twice:
- **weather** – the measured weather of hour *t* is used as if it were a perfect forecast (best case);
- **no_weather** – calendar and past load only (worst case).

A real deployment with an actual weather forecast would lie between the two.

**Learner.** `GradientBoostingRegressor` (scikit-learn) with the same settings as the team's GBM in `GBM_forallzones.ipynb` (100 trees, learning rate 0.1, depth 4, seed 42), so the results can be compared with T29/T39. Missing feature values are set to −1.

**Baselines (per horizon).** Seasonal naive = same hour one week earlier (valid for every horizon up to 7 days, so it is a flat line); persistence = same hour *d* days earlier.

**Fair comparison.** All horizons, scenarios and baselines are scored on exactly the same hours (`include_eval = 1` for every part and a value 168 h earlier exists). Differences between horizons therefore come only from the horizon.

**Metrics.** MAE, RMSE, CV(RMSE), NMBE, ASHRAE Guideline 14 (CV(RMSE) ≤ 30 %, |NMBE| ≤ 10 %). NMBE uses the D1 sign convention: positive = under-forecast. Skill score vs naive = 1 − RMSE_model / RMSE_naive (> 0 = better than the naive).

## 4. Check of the day-ahead reference (side finding)

Before using the GBM of `GBM_forallzones.ipynb` as the 1-day reference, its features were checked (`T37_check_gbm_leakage.py`, NW HVAC):

| Variant | CV(RMSE) test 2023 | CV(RMSE) test 2025 |
|---|---|---|
| A – notebook as it is | **29.6 %** (reproduced exactly) | 84.8 % |
| B – `roll_mean_24` shifted by 24 h | 49.6 % | 98.5 % |
| C – B + indoor variables lagged 24 h (fully day-ahead) | 49.5 % | 98.4 % |

`roll_mean_24 = rolling(24).mean()` at hour *t* **includes the value of hour t itself**, which is the value being forecast. This is target leakage: the 29.6 % (the only ASHRAE pass of NW HVAC in `Model_Comparison_ASHRAE.xlsx`) is not achievable in a real day-ahead forecast. With the rolling mean shifted by 24 h the result (49.6 %) agrees with T29 LightGBM (47.2 %) and with the 1-day GBM of this task (50.0 %). Recommendation for T39: use variant B/C or the T29 LightGBM as the reference, and re-run the Blend with the corrected GBM.

## 5. Results

### 5.1 CV(RMSE) by horizon – GBM + weather (test periods)

| Series | Test | 1 d | 2 d | 3 d | 5 d | 7 d | Seasonal naive | n hours |
|---|---|---|---|---|---|---|---|---|
| NE HVAC | 2023 | 689.7 | 689.9 | 689.8 | 689.9 | 689.8 | 974.9 | 1,365 |
| NE HVAC | 2025 | **18.3** | **19.4** | **19.2** | **19.1** | **20.1** | 25.0 | 1,113 |
| NW HVAC | 2023 | 50.0 | 61.1 | 62.5 | 72.7 | 80.0 | 104.0 | 805 |
| NW HVAC | 2025 | 93.6 | 92.7 | 98.4 | 98.1 | 99.7 | 133.5 | 1,094 |
| SE HVAC | 2023 | 51.6 | 51.2 | 52.1 | 54.5 | 54.1 | 66.6 | 1,125 |
| SE HVAC | 2025 | 42.8 | 36.7 | 35.5 | 43.0 | 43.9 | 44.3 | 962 |
| FLOOR_TOTAL | 2023 | 44.0 | 51.0 | 49.3 | 48.3 | 43.8 | 49.6 | 542 |
| FLOOR_TOTAL_noSW | 2023 | 47.5 | 52.5 | 51.0 | 54.9 | 54.7 | 55.4 | 604 |
| FLOOR_TOTAL_noSW | 2025 | **28.3** | 31.3 | 32.1 | 32.8 | 32.5 | 40.8 | 782 |

Bold = passes ASHRAE 14 (CV(RMSE) and NMBE). All values and the no-weather scenario are in `T37_multihorizon_results.xlsx`, sheet *CV_by_horizon*; figure `F37a_CV_RMSE_vs_horizon.png`.

### 5.2 Main findings

1. **Accuracy decays with the horizon, but slowly for most series.** From 1 to 7 days CV(RMSE) rises by about 30 points for NW HVAC in 2023 (50 → 80 %), by 2–7 points for SE HVAC, NE HVAC, NW HVAC 2025 and the totals, and does not rise steadily for the totals in 2023 (the test set has only 542–604 hours, so ±5 points is noise).
2. **The model is better than the naive at every horizon up to 7 days** in 17 of 18 series-period-scenario combinations at 7 days (the exception is SE HVAC 2025 without weather, skill −0.07) (sheet *Skill_vs_naive*). The advantage shrinks with the horizon: for NW HVAC 2023 the skill falls from 0.52 at 1 day to 0.23 at 7 days. For the 2023 floor total the advantage at 2–5 days is close to zero (skill −0.03 to 0.12).
3. **ASHRAE 14 passes are rare at any horizon.** NE HVAC 2025 passes at every horizon (but it is a very small load, a few Wh per hour). `FLOOR_TOTAL_noSW` 2025 passes only at 1 day (28.3 %, NMBE +0.3 %) and is just above the limit from 2 to 7 days (31–33 %). No other series passes, even at 1 day.
4. **Bias grows with the horizon for HVAC** (`F37b_NMBE_vs_horizon.png`): in winter 2023 NW HVAC goes from NMBE +9 % (1 day) to +41 % (7 days), meaning that at long horizons the model strongly under-forecasts cold-weather peaks. Most of the CV(RMSE) increase for NW HVAC is this bias.
5. **Perfect weather helps less than expected.** At 1 day, weather changes CV(RMSE) by less than 3 points in most series. It helps most for NW HVAC at long horizons in 2025 (7 days: 99.7 % vs 109.7 %) and for SE HVAC; for the floor totals in 2023 it is slightly *worse* (e.g. 2 days: 51.0 % vs 47.7 %). As the horizon grows, the GBM moves from past load to weather (`F37d_feature_groups_by_horizon.png`: weather is ~60 % of the importance of the floor-total model from 2 days on), but with only two training years it partly uses the weather as a stand-in for the season and does not generalise well. With a *real* (imperfect) weather forecast the gain would be even smaller.
6. **Example (`F37c_example_NW_HVAC_1d_vs_7d.png`).** The 1-day forecast follows the level of the current week; the 7-day forecast is anchored to the previous week, so it misses changes of regime (heating switched on or off) until a week later.

## 6. Answer to the open decision (backlog section 7, point 5)

Multi-day forecasts **can stay in scope as an indicative product, not as an ASHRAE-validated one**:
- for HVAC and the floor total the model keeps an advantage over the naive up to 7 days, so a 2–3-day outlook is useful for planning (e.g. preconditioning);
- the error is already above the ASHRAE limit at 1 day for almost every series, and it grows with the horizon; the dashboard (T36) should show multi-day forecasts with their horizon-specific error (sheet *CV_by_horizon*), not as a pass/fail result;
- the most useful single number for the building manager is the floor total without SW in 2025: about 28 % at 1 day and 31–33 % up to 7 days.

## 7. Limitations

- Test periods are short (2023: Jan–Feb, 805 h for NW HVAC and 542 h for the floor total; 2025: Aug–Oct) and cover different seasons, so 2023 and 2025 results cannot be compared directly.
- The “weather” scenario uses measured weather, which is an upper bound; no archive of real weather forecasts was available.
- CV(RMSE) is not meaningful for NE HVAC in 2023 (mean ≈ 7 Wh per hour with one large event): the 690 % comes from a few hours.
- Daily-energy metrics (sheet *Daily_energy*) only use days with all 24 hours scored; for the totals there are only 6–7 such days, so they are not interpreted.
- Hyperparameters are the team's GBM settings and were not re-tuned per horizon; a tuned model (e.g. the T29 LightGBM) would shift every curve by a few points but is unlikely to change the shape of the decay.
- Learner: LightGBM, CatBoost and Chronos were not available in the environment where this task was run; scikit-learn GBM was used, the same learner as `GBM_forallzones.ipynb`.

## 8. Files

| File | Content |
|---|---|
| `T37_multihorizon_forecast.py` | Full pipeline: targets, features per horizon, models, baselines, metrics, tables, figures, experiment-log rows |
| `T37_check_gbm_leakage.py` | Check of the day-ahead GBM features (section 4) |
| `outputs_T37/T37_multihorizon_results.xlsx` | Sheets README, CV_by_horizon, Metrics_long, Decay_vs_1day, Skill_vs_naive, Daily_energy, Feature_groups, Series_definition |
| `outputs_T37/T37_multihorizon_predictions.csv.gz` | Hourly forecasts (`timestamp_utc, timestamp_local, series, split, y_true, model, horizon_days, y_pred`) for the dashboard and `team_b_eval.py` |
| `outputs_T37/T37_experiment_log_rows.csv` | 280 rows in the columns of `experiment_log.xlsx` |
| `outputs_T37/T37_check_gbm_leakage_results.csv` | Results of section 4 |
| `outputs_T37/F37a_CV_RMSE_vs_horizon.png` | CV(RMSE) vs horizon, per series and test period |
| `outputs_T37/F37b_NMBE_vs_horizon.png` | NMBE vs horizon |
| `outputs_T37/F37c_example_NW_HVAC_1d_vs_7d.png` | Actual vs 1-day and 7-day forecasts, NW HVAC, two weeks of 2023 |
| `outputs_T37/F37d_feature_groups_by_horizon.png` | Share of importance of past load, calendar and weather at each horizon |

**How to run** (Python ≥ 3.10, pandas, numpy, scikit-learn, matplotlib, xlsxwriter; about 3 minutes):

```bash
python T37_multihorizon_forecast.py <folder with the two input files> outputs_T37
python T37_check_gbm_leakage.py <folder>/T32_cedint_f1_model_ready.csv.gz
```
