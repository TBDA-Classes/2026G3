# Logbook

The purpose of this logbook is to document all the tests and models that have been used through the whole duration of the project. All the details will be filled in the table below, serving as proof of what was tested and why, as well as interpreting the obtained results and explaining the problems that may arise. In case that some of the rows are not significant for a given change, they can simply be left unfilled.

As a norm, the tables will be filled by copying and pasting the template that follows, following a chronological order, so that the newer versions can be found at the bottom of the document.

### Template

| Field | Content |
|---|---|
| **Date** | |
| **Dataset version** | |
| **Cleaning steps** | |
| **Model tested** | |
| **Parameters tested** | |
| **Results obtained** | |
| **Interpretation** | |
| **Issued found** | |
| **Extras** | |

The person responsible for this document is the Continuous Audit and Quality Assurance lead, team member **María Herraiz**. However, any member of the group can freely modify this document and add their own version as long as they notify the responsible, who will afterwards check it.

Besides, the structure of the template and any other aspect of this document can be modified if new needs are identified, that is why there is an extras row added for now.

---

## First time from here on

### Entry 1 — 05/10/2026

| Field | Content |
|---|---|
| **Date** | 05/10/2026 |
| **Dataset version** | v1.0 (`cedint_f1_hourly.csv`) |
| **Cleaning steps** | • Executed full ingestion pipeline (Tasks A1–A5): Loaded all 18 sheets across Floor 1 Excel files (Storey1_NE, NW, SE, SW).<br>• Standardized column names and timestamp types (Europe/Madrid) across all series.<br>• Sorted timestamps chronologically, dropped exact duplicates, and created period labels (`hourly_2020_2023` vs `minute_2025`).<br>• Resampled 2025 minute-level data to hourly resolution (`1h`) and aligned 2020–2023 hourly data without filling gaps (dropped artificial empty rows from the 902-day gap).<br>• Implemented reset-aware energy calculation (diff on `active_energy_counter_wh` with a maximum threshold of 3x 99th percentile of `power_w`). Replaced resets with NaN and flagged them (`flag_reset = 1`).<br>• Merged all 18 series into one unified long table with zone-level environmental sensor variables (`temp_c`, `hum_pct`, `lum_lux`, `occupancy`) and quality flags (`flag_missing`, `flag_reset`, `flag_negative`, `flag_outlier`). |
| **Model tested** | N/A (Data Engineering & Pipeline Execution Step) |
| **Parameters tested** | • Hourly resampling rule: `mean` for power/current/environmental metrics, `mean` for occupancy (converting 0/1 to hourly occupancy share), `last` for cumulative counters, `first` for categorical metadata.<br>• Max plausible energy threshold: 3 * 99th percentile of `power_w`. |
| **Results obtained** | • Successfully created the final clean dataset `03_processed/cedint_f1_hourly.csv` containing 450,482 rows and 17 columns.<br>• Detected and handled a total of 88,347 counter reset events across all 18 series (e.g., 24,325 resets on NW Emerg. Lighting, 13,955 on NW Hand Dryer, 13,376 on SW Lighting). |
| **Interpretation** | • The complete Floor 1 dataset is successfully restructured from multi-sheet Excel files into a single, clean, standardized hourly long table ready for modelling and EDA.<br>• The 902-day retention gap between Feb 2023 and Aug 2025 is preserved without artificial zero-padding, avoiding bias in time-series models. |
| **Issued found** | • Extreme counter instability on specific series (such as NW Emerg. Lighting and NW Hand Dryer) required resetting thousands of erroneous consumption spikes to NaN. |
| **Extras** | • Task A1–A5 script (`Task_A1_A5.ipynb`) developed and executed by Ludovica Verga. Output saved in `03_processed/cedint_f1_hourly.csv`. |

---

### Entry 2 — 08/10/2026

| Field | Content |
|---|---|
| **Date** | 08/10/2026 |
| **Dataset version** | v0.1 (Pilot dataset: `Storey1_SW_report_by_device.xlsx`) |
| **Cleaning steps** | • Temperature & Humidity: Converted values equal to 0 to NaN (physically impossible indoors, indicating sensor outage or failure).<br>• Luminosity: Converted zeros to NaN only during daytime (between 07:00 AM and 07:00 PM).<br>• Pressure / Presence: Converted zeros to NaN if the associated temperature reading is present. |
| **Model tested** | N/A (Data Quality & Cleaning Validation Step) |
| **Parameters tested** | • Time filter for Luminosity: 07:00 AM to 07:00 PM.<br>• Cross-variable logical conditions applied across multi-sheet dictionary iteration using Pandas. |
| **Results obtained** | **Quantitative Summary of NaN Values Created on Storey1_SW:**<br>• Emerg. Lighting: Temperature (2,035 NaNs), Humidity (2,036 NaNs), Luminosity (13,597 NaNs), Pressure (22,293 NaNs)<br>• Lighting: Temperature (2,537 NaNs), Humidity (2,538 NaNs), Luminosity (16,327 NaNs), Pressure (22,801 NaNs)<br>• Hand Dryer: Temperature (2,083 NaNs), Humidity (2,083 NaNs), Luminosity (13,861 NaNs), Pressure (22,161 NaNs)<br>• Plugs & Sockets: Temperature (2,267 NaNs), Humidity (2,267 NaNs), Luminosity (14,786 NaNs), Pressure (22,421 NaNs)<br>• RACK: Temperature (2,323 NaNs), Humidity (1,217 NaNs) |
| **Interpretation** | • Environmental stability: Temperature and Humidity sensors show consistent, co-occurring outages across all zones.<br>• Sensor unreliability: Luminosity and Pressure sensors exhibit a massive amount of technical artifacts (up to 22,800+ NaNs), strongly indicating that light and pressure sensors are either highly prone to disconnections, uncalibrated, or prone to default-zero locking across subsystems. |
| **Issued found** | • Discrepancy observed on the RACK sheet: Temperature generated 2,323 NaNs while Humidity generated only 1,217 NaNs (an unexpected gap of 1,106 rows to be cross-checked during full dataset processing). |
| **Extras** | • Task B2 (P5 - Catherine Ma). Cleaning pipeline validated on SW pilot dataset and ready to be integrated into the main Data Engineering pipeline (`01_load_and_clean.ipynb`) to generate `cedint_f1_hourly.csv`. |

---

### Entry 3 — 17/10/2026

| Field | Content |
|---|---|
| **Date** | 17/10/2026 |
| **Dataset version** | v0.3 (`cedint_f1_hourly_clean.csv.gz`, built from the 4 raw Excel files) |
| **Cleaning steps** | • Sign correction: a series negative more than 90% of the time has a reversed current clamp; all electrical columns multiplied by –1 (only NW Emerg. Lighting).<br>• Every counter reading labelled ok / zero record / partial sum / spike / reset.<br>• Power: zero records and partial sums → empty. Negative power from –5 to 0 W → 0, below −5 W → empty.<br>• Environment: Temp = Hum = 0 → environment empty; Temp outside 0–50 °C → empty (SW sensor fault, 1–7 Mar 2022); Hum outside 5–95 % → empty; Lum = 0 between 10:00 and 16:00 UTC flagged.<br>• Complete hourly grid inside each period with missing hours added.<br>• Energy = centred counter difference within one counter segment.<br>• Model target `energy_wh_model` (counter → power × 1 h → interpolation over gaps ≤ 3 h). Nothing deleted: raw values kept, 16 quality flags added. |
| **Model tested** | N/A (data preparation step) |
| **Parameters tested** | • Noise limit for negative power: 5 W.<br>• Counter look-ahead: 6 rows (hourly) / ±30 min (minute data).<br>• Energy cap: 3 × the 99.5th percentile of power.<br>• Interpolation limit: 3 h; at least 10 complete minutes per 2025 hour. |
| **Results obtained** | • Final dataset: 470,680 rows × 50 columns.<br>• Model-ready target in 404,254 rows (86 %).<br>• Real resets: 1,330 hours; partial sums: 27,742; zero records: 21,987.<br>• Power and energy agree within 20% in ≥ 95 % of hours for 14 of 17 series (2020–23).<br>• Rating: 2020–23 → 11 Use, 6 Use with caution, 1 Do not use; 2025 → 8 Use, 3 Use with caution, 6 Do not use. |
| **Interpretation** | • Most of the 82,423 "resets" flagged in v0.2 were partial sums and zero records (devices missing from the total), not real resets.<br>• Timestamps are UTC, so a local-time column was added. |
| **Issued found** | • 2025 minute data: only NE 94 %, NW 87 %, SE 56 % and SW 43 % of minutes are complete; SW 2025 is not usable.<br>• Mean hourly energy in 2025 differs by more than 1.5x from the same weeks of 2021-22 for 6 of 14 series (figure F10); 2025 can be a rest period only for the stable series. |
| **Extras** | • Team B (Data Quality & Validation). Code: `clean_cedint.py`, `make_figures.py`.<br>• Outputs: quality workbook, figures F1–F10. Replaces v0.2. |

---

### Entry 4 — 17/10/2026

| Field | Content |
|---|---|
| **Date** | 17/10/2026 |
| **Dataset version** | v0.3 (`cedint_f1_hourly_clean.csv.gz`) – series NW HVAC |
| **Cleaning steps** | • No additional cleaning. Target: `energy_wh` (counter-based energy).<br>• Linear regression: rows without `energy_wh` or indoor temperature (`temp_c`) dropped. |
| **Model tested** | • Baseline 1: Seasonal naive (forecast = same hour one week earlier, 168 h).<br>• Baseline 2: Linear regression (scikit-learn `LinearRegression`). |
| **Parameters tested** | • Chronological split, no shuffling: train 1 Jun 2020 – 30 Jun 2022 (18,240 rows); validation 1 Jul – 31 Dec 2022 (4,417 rows); test 2023 + 2025 (2,758 rows, not yet used).<br>• Linear regression features: hour, weekday, `temp_c`.<br>• Metrics: MAE, RMSE, CV(RMSE) and NMBE; ASHRAE Guideline 14 targets CV(RMSE) ≤ 30 % and NMBE within ±10 %. |
| **Results obtained** | • Seasonal naive: MAE 48.87 Wh, RMSE 102.25 Wh, CV(RMSE) 102.85 %, NMBE −8.75 %.<br>• Linear regression: MAE 99.98 Wh, RMSE 120.33 Wh, CV(RMSE) 113.68 %, NMBE −2.02 %.<br>• Both baselines fail ASHRAE Guideline 14 (CV(RMSE) far above 30 %). |
| **Interpretation** | • These results are the bar every later model must beat.<br>• NW HVAC is a hard series: it alternates between standby (about 34 Wh per hour) and operation (170–480 Wh), and its level changes strongly between quarters (41.7 Wh in Jul–Sep 2021, 181.1 Wh in Jul–Sep 2022, 35.6 Wh in Oct–Dec 2022). |
| **Issued found** | • The two baselines were scored on different hours (3,514 vs 3,859); with the previous week's history included, the seasonal naive scores CV(RMSE) 105.35 %. Future comparisons must use identical hours.<br>• A 1-hour lag cannot be used for a day-ahead forecast; only lags of 24 h or more are valid.<br>• `temp_c` is indoor temperature; outdoor temperature must come from Open-Meteo. |
| **Extras** | • Team D (Modelling & Forecasting), tasks D1 (evaluation framework) and D2 (baselines). Notebook: `models.ipynb`.<br>• Next: SARIMAX and LightGBM once the feature table (subteam A, task A8) is available. |

---

### Entry 5 — 19/10/2026

| Field | Content |
|---|---|
| **Date** | 19/10/2026 |
| **Dataset version** | v0.3 (`cedint_f1_hourly_clean.csv.gz`), rows with `usable_for_model = 1`, local time (`timestamp_local`) |
| **Cleaning steps** | • No additional cleaning: uses Team B's v0.3 cleaning rules and series ratings.<br>• Only rows with `usable_for_model = 1` (series rated Use or Use with caution); timestamps converted to local time for calendar variables (hour, weekday, month, year, weekend). |
| **Model tested** | N/A (Exploratory Data Analysis – consumption profiles, tasks C1 and C4) |
| **Parameters tested** | • Load types: HVAC, Lighting and Plugs & Sockets, in every zone where they exist.<br>• Pilot first on NW HVAC to fix the workflow, then the same method for all zones and load types.<br>• Profiles of average power and energy by hour of day, weekday and month; monthly totals; working days vs weekends; August vs other months.<br>• Period comparison on the same August–October weeks: 2020–2023 vs 2025, and 2020 vs 2021–2022 vs 2025 (COVID check).<br>• 48 labelled plots, each with a written interpretation. |
| **Results obtained** | • **HVAC:** NW highest, SE intermediate, NE very low; clear daily pattern with the peak in the late morning; little difference between working days and weekends; NW highest in summer (July–August).<br>• **Lighting:** SE and SW follow the working day and drop almost to zero at weekends; lower in August in every zone; NW is highest at night and lowest during daylight hours.<br>• **Plugs & Sockets:** NW far above the other zones, with a daytime peak, lower at weekends and in August and high in winter months; NE, SE and SW are lower and stable.<br>• 2020 differs from 2021–2022 in the same weeks: NW HVAC much higher and SE and SW lighting much lower. |
| **Interpretation** | • Zone is the strongest effect for every load type, so each zone × load type needs its own model or a zone feature.<br>• Hour of day, day type, month, August and year/period are relevant forecasting features; the weekday effect is strong for lighting and weak for HVAC.<br>• 2020 is treated as a potentially abnormal, COVID-affected period (COVID flag). |
| **Issued found** | • NW lighting stays high at night and during weekends, a different operating pattern that should be investigated further.<br>• The NW HVAC weekend pattern should be checked by year and period, since 2020 may distort the comparison.<br>• SW 2025 results should be interpreted with caution. |
| **Extras** | • Subteam C (Exploration & Environment). Notebook: P7.<br>• Covers backlog items F4.1 and F4.2, and the August part of F4.3. |

---

### Entry 6 — 19/10/2026

| Field | Content |
|---|---|
| **Date** | 19/10/2026 |
| **Dataset version** | v0.3 (`cedint_f1_hourly_clean.csv.gz`) – NW zone, years 2021–2022, rows with `usable_for_model = 1`, local time (`timestamp_local`) |
| **Cleaning steps** | • No additional cleaning: uses Team B's v0.3 cleaning rules and series ratings.<br>• Rows without the two variables being compared were excluded from each analysis.<br>• Data-quality check: `flag_lum_day_zero` (suspicious daytime Lum = 0) checked before the luminosity analysis; no flagged hours in the selected data, so the result did not change. |
| **Model tested** | N/A (Exploratory Data Analysis – environment and occupancy vs energy) |
| **Parameters tested** | • P8.1 Luminosity vs Lighting energy: scatter plot and Pearson correlation.<br>• P8.2 and P8.3 Occupancy (0/1) vs Lighting and vs Plugs & Sockets: average hourly energy with and without presence.<br>• P8.4 Indoor temperature vs HVAC energy: scatter plot, Pearson correlation and average HVAC energy per 2 °C interval (intervals with at least 100 hours).<br>• P8.5 Humidity vs HVAC energy: scatter plot, Pearson correlation and distribution of humidity values.<br>• P8.6 Occupancy by hour of the day: share of hours with presence detected.<br>• P8.7 Lighting energy by occupancy and hour: daytime (09:00–17:59) vs night-time (00:00–05:59). |
| **Results obtained** | • Luminosity vs Lighting: correlation −0.372 (17,113 hours).<br>• Occupancy vs Lighting: 0.196 kWh without presence vs 0.171 kWh with presence (about 13 % lower overall); within the same time of day slightly higher with presence (daytime 0.069 vs 0.072 kWh; night-time 0.274 vs 0.304 kWh).<br>• Occupancy vs Plugs & Sockets: 1.248 kWh without presence vs 1.308 kWh with presence (about 4.8 % higher).<br>• Temperature vs HVAC: correlation +0.174 (15,957 hours); highest average HVAC energy (0.139 kWh) in the 22–24 °C interval.<br>• Humidity vs HVAC: correlation +0.059 (15,957 hours); about 89 % of readings are 30 % or 31 %.<br>• Occupancy by hour: lowest at 02:00 (29.5 %), highest at 14:00 (67 %). |
| **Interpretation** | • Higher luminosity is generally associated with lower lighting consumption.<br>• Occupancy must be analysed together with the hour of the day: the overall lighting result reverses once day and night are separated.<br>• Temperature has a non-linear relationship with HVAC energy, so it can still be a useful forecasting variable despite its weak linear correlation.<br>• Humidity adds little information because it varies very little.<br>• Candidate predictors (final considerations of P7 and P8): zone, load type, hour of day, weekday/weekend, month/season, August, year or period, luminosity, temperature and occupancy. |
| **Issued found** | • The analysis covers only the NW zone in 2021–2022, so the results cannot automatically be generalised to the other zones or to 2025.<br>• Humidity and occupancy have sensor limitations; presence is also detected at night, so night-time occupancy readings should be interpreted with caution.<br>• `temp_c` is indoor temperature, which the HVAC system itself influences.<br>• Correlations do not show cause and effect; the variables must be tested for their real contribution to forecasting accuracy. |
| **Extras** | • Subteam C (Exploration & Environment). Notebook: `TBDA_P8_Environmental_Exploration.ipynb`; conclusions in Team C final considerations (P7 and P8).<br>• Starts backlog item F5.2 (NW zone only) and supports F5.1 (presence follows the daily cycle). |


### Entry 7 — 25/10/2026

| Field | Content |
|---|---|
| **Date** | 25/10/2026 |
| **Dataset version** | v0.4 (`cedint_f1_hourly_F4.3C.csv`, built from `cedint_f1_hourly.csv`) |
| **Cleaning steps** | • Parsed full 2020–2025 multi-year time-series into local timestamp objects (`Europe/Madrid`).<br>• Identified official regional public holidays (e.g., Good Friday, Labour Day, Community of Madrid Day, Assumption of Mary) across all covered years (2020–2025) and generated the boolean flag `is_holiday`.<br>• Identified the annual August low-occupancy period corresponding to partial university/building closures and generated the boolean flag `is_august_low_use`.<br>• Exported the enriched hourly dataset containing all original electrical and environmental metrics augmented with the two calendar indicators. |
| **Model tested** | N/A (Data Engineering & Feature Enrichment Step) |
| **Parameters tested** | • Calendar rules matching regional official holiday schedules for Madrid (2020–2025).<br>• Calendar mask targeting August low-occupancy windows (01/08 to 31/08). |
| **Results obtained** | • Successfully generated the enriched dataset `cedint_f1_hourly_F4.3C.csv`.<br>• Successfully flagged all official holiday hours (`is_holiday = 1`) and August low-use hours (`is_august_low_use = 1`) across the entire 2020–2025 time horizon without altering original physical readings. |
| **Interpretation** | • Isolation of low-occupancy periods is critical for downstream Big Data forecasting algorithms to prevent artificial consumption drops from biasing baseline load profiles. |
| **Issued found** | • Merge conflict encountered on `.gitignore` during `git pull --rebase` due to concurrent team updates; resolved manually by accepting remote state (`git checkout --ours .gitignore`) prior to pushing. |
| **Extras** | • Task F4.3C executed by Anthony (`Anthoriv974`). Script: `Task_F4_3C.py`. Code committed and synchronized on main branch of team repository `TBDA-Classes/2026G3`. |

### Entry 8 — 26/10/2026

| Field | Content |
|---|---|
| **Date** | 26/10/2026 |
| **Dataset version** | v0.3 (`cedint_f1_hourly_clean.csv.gz`) |
| **Cleaning steps** | • Structured dataset into a unified long table keyed by timestamp, building, floor, zone code (`1NE`, `1NW`, `1SE`, `1SW`), and load type.<br>• Stored zone-level environmental sensor data (`temp_c`, `hum_pct`, `lum_lux`, `occupancy`) aligned per zone. |
| **Model tested** | N/A (Spatial Context & Data Structuring Step) |
| **Parameters tested** | • Spatial categorization rules across all Floor 1 sensor series.<br>• Schema mapping linking device-level meters to corresponding zone centroids. |
| **Results obtained** | • Achieved complete spatial organization across all 18 series on Floor 1.<br>• Enabled seamless aggregation by zone and load type (Tasks F3.1 requirements fulfilled). |
| **Interpretation** | • Structuring data by zone and load type allows direct spatial comparison and forms the structural backbone for multi-zone forecasting models. |
| **Issued found** | • Zone `1NE` lacks local environmental sensors, requiring feature proxying or external weather data for future forecasting steps. |
| **Extras** | • Task executed by Riccardo (Subteams A & C). Covers backlog item **F3.1**. |

---

### Entry 9 — 26/10/2026

| Field | Content |
|---|---|
| **Date** | 26/10/2026 |
| **Dataset version** | v0.3 (`cedint_f1_hourly_clean.csv.gz`) |
| **Cleaning steps** | • Normalized electrical energy consumption per device count across all Floor 1 zones.<br>• Filtered out uncalibrated zero readings during non-operational hours. |
| **Model tested** | N/A (Inter-Zone Comparative Analysis Step) |
| **Parameters tested** | • Normalization factors based on installed device counts per zone.<br>• Cross-zone consumption ratio comparisons for identical load types (HVAC, Lighting, Plugs & Sockets). |
| **Results obtained** | • Identified baseline intensity differences between zones (e.g., NW exhibiting significantly higher base load for Plugs & Sockets compared to NE, SE, and SW).<br>• Isolated spatial consumption anomalies for facility management review (Tasks F3.2 requirements fulfilled). |
| **Interpretation** | • Device-normalized comparison prevents misinterpreting larger physical zones as energy-inefficient and highlights true operational outliers. |
| **Issued found** | • SE Projector series remains 100% zero, excluding it from comparative normalization. |
| **Extras** | • Task executed by Catherine (Subteams C & B). Covers backlog item **F3.2**. |

---

### Entry 10 — 26/10/2026

| Field | Content |
|---|---|
| **Date** | 26/10/2026 |
| **Dataset version** | v0.3 (`cedint_f1_hourly_clean.csv.gz`) |
| **Cleaning steps** | • Paired hourly electrical loads with indoor environmental metrics (`temp_c`, `hum_pct`, `lum_lux`, `occupancy`).<br>• Applied non-linear transformations and binning on indoor temperature (2 °C intervals). |
| **Model tested** | N/A (Full Relation Matrix & Driver Analysis) |
| **Parameters tested** | • Pearson and Spearman correlation matrices across all 4 zones.<br>• Pairwise feature correlation heatmaps per load type and zone. |
| **Results obtained** | • Generated complete relation matrix and correlation heatmaps for all zones.<br>• Confirmed non-linear relationship between indoor temperature and HVAC energy, and verified negative correlation between daylight luminosity and artificial lighting (Tasks F5.2 requirements fulfilled). |
| **Interpretation** | • Environmental drivers act non-linearly on energy targets. Correlation heatmaps validate indoor temperature, luminosity, and occupancy as essential exogenous features for predictive models. |
| **Issued found** | • Indoor humidity exhibits near-zero variance across extended periods, providing minimal explanatory power for forecasting. |
| **Extras** | • Task executed by Maria Vittoria (Subteam C). Notebook: `TBDA_P8_Environmental_Exploration.ipynb`. Covers backlog item **F5.2**. |

---

### Entry 11 — 26/10/2026

| Field | Content |
|---|---|
| **Date** | 26/10/2026 |
| **Dataset version** | v0.3 merged with Open-Meteo external weather dataset |
| **Cleaning steps** | • Merged outdoor temperature and calculated heating/cooling degree-hours from Open-Meteo API.<br>• Created lagged environmental features for HVAC response time (lags $t-1$ to $t-6$ hours). |
| **Model tested** | N/A (Weather & Lag Driver Feature Engineering) |
| **Parameters tested** | • Time-lag range: 0 to 6 hours.<br>• Outdoor temperature and cooling degree-hour thresholds. |
| **Results obtained** | • Quantified thermal inertia of the building: HVAC demand correlates strongly with 1–3 hour lagged outdoor temperature readings.<br>• Successfully integrated outdoor weather features into the data pipeline (Tasks F5.3 requirements fulfilled). |
| **Interpretation** | • Building thermal mass introduces a delayed response to external weather changes. Including 1–3 hour lags improves short-term HVAC predictability. |
| **Issued found** | • Alignment between UTC weather timestamps and local Madrid timestamps required explicit time zone conversions to avoid phase shifts in lag calculations. |
| **Extras** | • Task executed by Catherine (Subteams C & A). Covers backlog item **F5.3**. |


---

### Entry 12 — 02/11/2026

| Field | Content |
|---|---|
| **Date** | 02/11/2026 |
| **Dataset version** | v0.4 (`cedint_f1_hourly_clean.csv` |
| **Cleaning steps** | No cleaning, file was already clean |
| **Model tested** | Day-ahead (24 h) forecasts, issued at 00:00 UTC, for 10 series: HVAC (NE, NW, SE), Lighting (NW, SE, SW), Plugs & Sockets (NE, NW, SE, SW).
1. Seasonal naive baseline (same hour last week).
2. SARIMAX: ARIMA errors with daily and weekly Fourier terms, plus outdoor temperature, degree-hours, holiday, weekend, August and COVID flags.
3. LightGBM with an expanding-window TimeSeriesSplit.
Split (T32): train 2020-06 → 2022-06, validate 2022-H2, test 2023 and 2025. |
| **Parameters tested** | LightGBM: random search (quick mode: 6 configurations, 3 folds of 28 days) over num_leaves (15–127), learning_rate (0.02–0.1), min_data_in_leaf (20–200), feature_fraction, bagging_fraction and lambda_l2 (0–50). Best configurations vary by series, for example NW HVAC: 127 leaves, lr 0.05, min_data 200, 62 rounds.
34–42 features: calendar and holidays, weather lags 0–6 h, target lags ≥ 24 h (24–336 h), rolling means, indoor values lagged ≥ 24 h.
SARIMAX: Fourier terms (daily K=4, weekly K=2), ARIMA order selected per series (mostly (2,0,0)), state refreshed on the last 14 days before each forecast. Only one K combination was tested in quick mode. |
| **Results obtained** | CV(RMSE) % on the validation period (2022-H2), seasonal naive / SARIMAX / LightGBM:
• NW HVAC: 105 / 105 / 67
• SE HVAC: 66 / 56 / 54
• NE HVAC: 344 / 245 / 256
• NW Plugs: 74 / 87 / 52
• SE Plugs: 160 / 154 / 129
• NE Plugs: 45 / 47 / 35
• SW Plugs: 25 / 30 / 21
• NW Lighting: 157 / 124 / 113
• SE Lighting: 390 / 321 / 295
• SW Lighting: 362 / 288 / 262
LightGBM is the best model on validation in 9 of 10 series (SARIMAX in the other).
Passing ASHRAE 14 (CV(RMSE) ≤ 30 % and |NMBE| ≤ 10 %): SW Plugs (LightGBM 21 % on validation, 29.8 % on 2023) and NE Plugs on 2025 (8 %). No HVAC or Lighting series passes yet, except NE HVAC with the naive model on 2025. |
| **Interpretation** |  LightGBM improves clearly on the baseline for the main loads (for example NW HVAC from 105 % to 67 %). The NW HVAC baseline (≈105 %) matches the T21 result (102.85 %), so the metric and the split are consistent with subteam D’s previous work.
Plugs & Sockets is the most predictable load, as expected from its link to occupancy and the working calendar. Lighting and HVAC are harder and are far from the 30 % target in this run.
SARIMAX is weaker than LightGBM, especially on NW HVAC, because a linear model with Gaussian errors fits an on/off-like HVAC pattern poorly.
These results are preliminary (quick mode) and should be repeated with the full search. |
| **Issued found** | • CV(RMSE) is inflated on very low-consumption series (NE HVAC, SE Lighting: a few Wh per hour). A small absolute error (NE HVAC MAE ≈ 0.8 Wh) gives a CV(RMSE) of hundreds of percent, so MAE should also be reported for these.
• The 2025 test covers only 18 Aug – 13 Oct 2025, and 2023 only Jan – Mar. SW has no 2025 data, so SW is evaluated on 2023 only.
• NE has no indoor environmental sensors, so it uses only outdoor weather and calendar features.
• SARIMAX skips the first days of the 2025 block because the 902-day gap leaves no history. |
| **Extras** | • Task executed by María Herraiz . Covers backlog item **F1.2**, T29 |


### Entry 13 — 06/11/2026

| Field | Content |
|---|---|
| **Date** | 06/11/2026 |
| **Dataset version** | v0.4 (`T32_cedint_f1_model_ready.csv.gz`) |
| **Cleaning steps** | • Applied standardized training/evaluation eligibility masks (`include_train = 1` and `include_eval = 1`) generated by `T32_make_training_data.py` across all Floor 1 zones (`NE`, `NW`, `SE`, `SW`).<br>• Preserved strict chronological separation without shuffling across train (Jun 2020 – Jun 2022), validation (Jul – Dec 2022), and test blocks (Jan – Feb 2023 & Aug – Oct 2025). |
| **Model tested** | • **Floor 1 Total Load Aggregation (`F1.3_T30_floor1_total_forecast_MH.R`)**: Aggregated day-ahead zone-level forecasts to compute total Floor 1 electrical consumption.<br>• **Interactive Dashboard Prototype (`T36_dashboard_app.py`)**: Deployed Streamlit decision-support interface (consumption exploration, driver analysis, ASHRAE 14 forecast comparison, and data quality reporting). |
| **Parameters tested** | • Floor 1 total aggregation across active zones (`NE`, `NW`, `SE`, `SW`) evaluated against ASHRAE Guideline 14 thresholds (CV(RMSE) ≤ 30 % and |NMBE| ≤ 10 %).<br>• Dashboard CLI parameterization (`--data cleaned --pred <predictions.csv>`) supporting baseline and Team D model uploads. |
| **Results obtained** | • Aggregating individual zone series to the Floor 1 building level substantially reduces relative volatility (CV(RMSE)) compared to noisy single-zone sub-loads.<br>• Functional Streamlit prototype (`T36_dashboard_app.py` + `T36_README_dashboard.md`) operational using `make_reference_baseline.py` outputs and ready for multi-model ingestion. |
| **Interpretation** | • Spatial aggregation cancels out localized switching noise (e.g., intermittent HVAC or lighting spikes in individual zones), yielding a smoother, more predictable building-level load profile.<br>• The dashboard bridges data engineering outputs (Team B/C) and forecasting metrics (Team D) for non-technical building manager storytelling. |
| **Issued found** | • Zone `SW` lacks valid 2025 minute-era measurements, requiring careful split handling when comparing 2023 vs. 2025 Floor 1 totals. |
| **Extras** | • Aggregation script executed by María Herraiz (covers **F1.3 / T30**).<br>• Dashboard prototype and documentation structured for **F8.1 / T36** (integration & presentation coordinated by Anthony Rivière). |

---

### Entry 14 — 10/11/2026

| Field | Content |
|---|---|
| **Date** | 10/11/2026 |
| **Dataset version** | v0.4 (`T32_cedint_f1_model_ready.csv.gz`) |
| **Cleaning steps** | • Filtered rows using `include_train = 1` / `include_eval = 1` and formatted univariate/multivariate time-series context windows per zone (`NE`, `NW`, `SE`, `SW`). |
| **Model tested** | • **Random Forest (`RF_general_zone_load.py`)**: Multi-zone day-ahead tree-ensemble regressor.<br>• **Chronos (`Chronos_general_zone_load.py`)**: Pre-trained time-series foundation model evaluated across all four Floor 1 zones. |
| **Parameters tested** | • **Random Forest**: Lagged consumption features (≥ 24 h), local calendar flags (`hour`, `weekday`, `is_holiday`, `is_august_low_use`), and zone environmental/weather drivers.<br>• **Chronos**: Historical context window lengths and probabilistic/point day-ahead forecast horizons (24 h) across zones (`NE_Chronos.zip`, `NW_Chronos.zip`, `SE_Chronos.zip`, `SW_Chronos.zip`). |
| **Results obtained** | • Generated standardized prediction archives and ASHRAE 14 evaluation metrics across all 4 zones for both Random Forest (`*_RandomForest.zip`) and Chronos (`*_Chronos.zip`). |
| **Interpretation** | • Foundation models (Chronos) capture recurring daily and weekly load periodicity out-of-the-box without extensive manual feature engineering, while Random Forest captures non-linear interactions with calendar and weather features. |
| **Issued found** | • The 902-day gap between Feb 2023 and Aug 2025 requires resetting historical context windows at the start of the 2025 test block so foundation and lag-based models do not condition across discontinuous years. |
| **Extras** | • Team D multi-zone model expansion. Scripts: `RF_general_zone_load.py`, `Chronos_general_zone_load.py`. |

---

### Entry 15 — 11/11/2026

| Field | Content |
|---|---|
| **Date** | 11/11/2026 |
| **Dataset version** | v0.4 (`T32_cedint_f1_model_ready.csv.gz`) |
| **Cleaning steps** | • Used standardized `T32` model-ready dataset with native categorical handling for zone/load identifiers and calendar indicators. |
| **Model tested** | • **CatBoost (`CatBoost_general_zone_load.py`)**: Gradient boosting on symmetric (oblivious) decision trees across all Floor 1 zones (`NE`, `NW`, `SE`, `SW`). |
| **Parameters tested** | • Depth, learning rate, L2 leaf regularization, and day-ahead lag/calendar/weather feature sets across all four zones (`NE_Catboost.zip`, `NW_Catboost.zip`, `SE_Catboost.zip`, `SW_Catboost.zip`). |
| **Results obtained** | • Produced zone-level prediction packages (`NE`, `NW`, `SE`, `SW`) formatted for `team_b_eval.py` ASHRAE Guideline 14 scoring. |
| **Interpretation** | • Symmetric trees in CatBoost reduce overfitting on noisy sub-hourly/hourly HVAC regimes while preserving strong accuracy on calendar-driven loads (Plugs & Sockets, Lighting). |
| **Issued found** | • Low-consumption series (such as `NE HVAC` and `SE Lighting`) remain sensitive to percentage-based CV(RMSE) inflation despite low absolute Wh errors. |
| **Extras** | • Team D multi-zone model expansion. Script: `CatBoost_general_zone_load.py`. |

---

### Entry 16 — 13/11/2026

| Field | Content |
|---|---|
| **Date** | 13/11/2026 |
| **Dataset version** | v0.4 (`T32_cedint_f1_model_ready.csv.gz`) |
| **Cleaning steps** | • Standardized multi-zone, multi-sensor input pipeline across all Floor 1 zones and load types (`include_train = 1` / `include_eval = 1`). |
| **Model tested** | • **Gradient Boosting Machine – All Zones (`GBM_forallzones.ipynb`)**: Unified multi-zone, multi-sensor day-ahead forecasting pipeline.<br>• **Hybrid Blend Ensemble (`blend_model_chronos&gbm.ipynb`)**: Weighted combination blending **Chronos** foundation model forecasts with **GBM** tabular forecasts. |
| **Parameters tested** | • **GBM**: Multi-zone feature matrix combining ≥ 24 h autoregressive lags, rolling statistics, Madrid calendar flags (`F4.3C`), and Open-Meteo outdoor weather variables.<br>• **Blend**: Ensemble weighting between Chronos and GBM day-ahead predictions evaluated across all zones (`NE`, `NW`, `SE`, `SW`) against ASHRAE Guideline 14 criteria. |
| **Results obtained** | • Generated full-floor prediction and metric tables: `All_Zones_GBM_predictions.csv`, `All_Zones_GBM_ASHRAE_metrics.xlsx`, and `All_Zones_BLEND_ASHRAE_metrics.xlsx`.<br>• Consolidated cross-model ASHRAE Guideline 14 benchmark comparison in `Model_Comparison_ASHRAE.xlsx` (comparing Blend, Chronos, GBM, and baseline/tree models). |
| **Interpretation** | • Combining a time-series foundation model (Chronos, strong on temporal shape/periodicity) with a gradient-boosted tree model (GBM, strong on exogenous weather and calendar flags) reduces variance and improves stability across heterogeneous Floor 1 zones. |
| **Issued found** | • Consistent formatting of prediction CSVs (`timestamp_utc, zone, load_type, model, split, y_true, y_pred`) is essential so all zone outputs can be directly ingested into `team_b_eval.py` and the Streamlit dashboard (`T36_dashboard_app.py`). |
| **Extras** | • Executed by Joos van Lommel (`Joosvanlommel`). Files: `GBM_forallzones.ipynb`, `blend_model_chronos&gbm.ipynb`, `Model_Comparison_ASHRAE.xlsx`.<br>• Project documentation and `README.md` synchronized on main branch by Anthony Rivière (`Anthoriv974`). |
