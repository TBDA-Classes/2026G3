# T31 (F3.3) – Forecast of zone 1NE without environmental sensors

**Backlog item:** T31 / F3.3 · **Sprint:** 3 · **Author:** Riccardo · **Status:** 🟢 Complete (M5/M6 with outdoor weather pending the T26 file)

Zone NE has no indoor sensors (Temp, Hum, Lum and Pres are empty in 100 % of its hours). This task forecasts NE HVAC and NE Plugs & Sockets 24 h ahead. It tests which proxy can replace the missing sensors (zone NW, the adjacent zones NW + SE, or the whole floor), and checks the proxy idea on zones that do have sensors (leave-one-zone-out).

## Files

| File | What it is |
|---|---|
| `T31_ne_forecast.py` | Full pipeline: features, proxies, models, metrics, figures, Excel |
| `T31_outputs/T31_NE_results.xlsx` | All result tables (see the sheet list below) |
| `T31_outputs/T31_NE_predictions.csv` | Hourly predictions of every method for validation, test 2023 and test 2025 (input for T34, T35, T38 and T40) |
| `T31_outputs/T31_NE_Forecast_Report.docx` | Report: data, method, results, limitations, conclusions |
| `T31_outputs/F_T31_1 … F_T31_6.png` | Figures used in the report |
| `T31_logbook_entry.md` | Text for the experiment logbook and the backlog update |

Sheets in `T31_NE_results.xlsx`: README, Env_availability, Proxy_similarity, NE_series, NE_vs_proxy_drivers, NE_results, NE_best_params, Feature_importance, LOZO_validation, NE_HVAC_spikes, Experiment_log_rows.

## How to run

```bash
pip install pandas numpy scikit-learn matplotlib openpyxl
python T31_ne_forecast.py --data cedint_f1_hourly_clean.csv
# with outdoor weather (adds scenarios M5 and M6):
python T31_ne_forecast.py --data cedint_f1_hourly_clean.csv --weather open_meteo_cedint_hourly.csv
python T31_ne_forecast.py --data cedint_f1_hourly_clean.csv --download-weather   # needs internet
```

A run takes about 10 minutes on a laptop. The seed is fixed at 42. With dataset v0.4, the script uses the `is_holiday` column of T24; otherwise it uses a built-in Madrid holiday list.

## Method in short

- **Day-ahead rule:** forecast issued at 00:00 for the next 24 hours, so only lags of 24 h or more and the previous day's proxy values are used.
- **Split (as in T32):** train 2020-06 to 2022-06 · validation 2022-H2 (tuning) · test 2023 and 2025.
- **Model:** scikit-learn `HistGradientBoostingRegressor`, persistence-anchored (it learns y − lag24) with absolute-error loss.
- **Metrics:** MAE, RMSE, CV(RMSE), NMBE and ASHRAE 14 (CV(RMSE) ≤ 30 %, |NMBE| ≤ 10 %).

## Main results (hourly CV(RMSE), test 2023 / test 2025)

| Series | Naive day | M0 no env | M1 NW proxy | M2 adjacent proxy |
|---|---|---|---|---|
| NE Plugs & Sockets | 26.2 / 10.3 % | 27.2 / 8.8 % | 27.1 / 8.9 % | 29.6 / 8.5 % |
| NE HVAC | 974 / 23.1 % | 948 / 19.9 % | 970 / 19.4 % | 962 / 19.2 % |

- The proxies change CV(RMSE) by at most about 3 points. The leave-one-zone-out test shows that even a zone's own sensors add little to a day-ahead forecast, so NE loses almost nothing by not having sensors.
- NE HVAC fails in 2023 only because of 11 spike hours, which are 57 % of that period's energy. These are candidate anomalies for T35.
