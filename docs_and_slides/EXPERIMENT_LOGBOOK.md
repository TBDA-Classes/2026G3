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


---

### Entry 13 — 02/11/2026

| Field | Content |
|---|---|
| **Date** | 02/11/2026 |
| **Dataset version** | v0.4 (`cedint_f1_hourly_clean.csv.gz`) → model-ready file `cedint_f1_model_ready.csv.gz` (`T32_cedint_f1_model_ready.csv.gz` in the repository) |
| **Cleaning steps** | • Nothing deleted: all 470,680 hourly rows of the clean dataset are kept in the output file.<br>• Three 0/1 columns say how an hour may be used: `include_train` (the model may learn from it), `include_eval` (validation and test scores are computed on it) and `include_train_no2020` (experiment variant without the COVID year 2020); `exclusion_reason` records the first rule that keeps a row out.<br>• Split assigned by date (train / validation / test_2023 / test_2025 / unused); SW in 2025 set to unused.<br>• Model scope per series: priority (HVAC, Lighting, Plugs & Sockets), secondary constant (RACK, Emergency Lighting), daily totals only (Hand Dryer), excluded (SE Projector).<br>• Calendar features from local time (`hour_local`, `dayofweek_local`, `month_local`); target lags `lag_24h` and `lag_168h` computed per series and per period, never across the 902-day gap.<br>• Training filtered more strictly than evaluation: test hours are only dropped when no true value exists. |
| **Model tested** | N/A (Data Preparation – model-ready training data, T32) |
| **Parameters tested** | • Periods (UTC), agreed with Team D: train 1 Jun 2020 – 30 Jun 2022; validation 1 Jul – 31 Dec 2022; test_2023 1 Jan – 28 Feb 2023; test_2025 18 Aug – 13 Oct 2025 (NE, NW, SE only).<br>• Exclusion rules for training and evaluation: R0 outside the agreed periods; R1 dead series or rated "Do not use"; R2 no valid energy value; R3 interpolated value; R4 event-driven load (hand dryers).<br>• Exclusion rules for training only: R5 counter energy and power × 1 h differ by more than 20 %; R6 isolated power spike (Hampel filter).<br>• Variant V1: training without 2020 (`include_train_no2020`). |
| **Results obtained** | • Rows used: train 229,086 (157,319 without 2020); validation 52,566; test_2023 17,185; test_2025 13,470.<br>• Training hours left out: R1 18,240; R2 21,399; R3 12,136; R4 32,203; R5 9,087; R6 1,147. R0 leaves out 30,805 hours of the whole file.<br>• Every series keeps at least 69 % of its training hours (from 69 % for SW Lighting to 100 % for NW RACK). |
| **Interpretation** | • One model-ready file means every model learns from and is scored on the same hours, so the scores are comparable.<br>• Leaving doubtful hours out of training helps the model learn normal behaviour; keeping them in the test keeps the scores honest.<br>• 2020 stays in the main training set because the data shows no single direction: working-day occupancy was lower than in 2021 in NW (46 % vs 51 %) and SW (12 % vs 59 %) but higher in SE (79 % vs 36 %), and the change from 2021 to 2022 is just as large. Dropping 2020 removes about a third of the training hours, so each model is trained with and without 2020 and the version with the better validation score is kept. |
| **Issued found** | • test_2023 covers only two winter months; test_2025 covers only late summer and autumn.<br>• For SW, 20–31 % of training hours are left out; SW forecasts should state this.<br>• R5 uses a 20 % tolerance; another value would change the training set slightly.<br>• Environmental features are empty for NE (no sensors) and in about 2 % of other hours; `current_a` is not included because it is underestimated for multi-device series in 2020–23. |
| **Extras** | • Task executed by Marie Heyse (Team B – Data Quality & Validation). Script: `T32_make_training_data.py`. Documentation: `T32_TRAINING_DATA_METHODOLOGY.md`, `README_T32_datacleaning.md`. Summary: `training_data_summary_T32_DATACLEANING.xlsx`.<br>• Supports T29 (F1.2), T32 (F6.3) and T34–T40 (evaluation). |

---

### Entry 14 — 06/11/2026

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

### Entry 15 — 10/11/2026

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

### Entry 16 — 11/11/2026

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

### Entry 17 — 13/11/2026

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


---

### Entry 18 — 14/11/2026

| Field | Content |
|---|---|
| **Date** | 14/11/2026 |
| **Dataset version** | v0.4 (`cedint_f1_model_ready.csv` |
| **Cleaning steps** | No cleaning, file was already clean |
| **Model tested** | 
| **Parameters tested** | 
| **Results obtained** |
| **Interpretation** | 
| **Issued found** | 
| **Extras** | • Task executed by María Herraiz . Covers backlog item **F1.3**, T30 |

| **Cleaning steps** | • No cleaning of values: the file was already clean.
| **Model tested** | • **Floor 1 total, day-ahead (24 h) forecast (F1.3 / T30)**, six methods compared on the same hours: 
    - Seasonal naive (same hour last week, baseline)
    – LightGBM direct on the floor total
    – Bottom-up (sum of the 13 zone × load forecasts)
    – Hierarchical reconciliation: OLS, WLS (structural) and MinT-shrink. |
| **Parameters tested** |  Hierarchy of 22 nodes (total, 4 zones, 4 load types, 13 bottom series), one LightGBM model per node.  LightGBM: learning_rate 0.05, num_leaves 31, min_data_in_leaf 50, feature_fraction 0.8, bagging_fraction 0.8, 300 fixed rounds, seed 42 (no tuning). Features: lag_24, lag_48, lag_168, mean_prev_24h, mean_prev_7d, hour, wday, month, is_weekend, is_holiday, is_august_low_use, flag_covid_2020 (no weather or indoor variables). All lags ≥ 24 h, so no leakage. Reconciliation: MinT shrinkage λ = 0.018; negative forecasts clipped to 0 and aggregates rebuilt. Train 2020-06-01 to 2022-06-30; validation 2022-07-01 to 2022-12-31 (2,682 valid h); test 2023 = 586 valid h (19 Jan – 1 Mar 2023). 2025 has 0 valid hours (SW has no 2025 data). |
| **Results obtained** |    **Validation** CV(RMSE) % / NMBE %: seasonal naive 50.57 / −4.19; LightGBM direct 41.95 / +2.41; bottom-up 39.63 / +4.17; OLS 39.71 / +5.81; WLS 38.55 / +4.35; MinT 38.32 / +3.81.
                            **Test 2023** CV(RMSE) % / NMBE % (MAE Wh/h): seasonal naive 45.21 / +6.30 (994); LightGBM direct 38.64 / +7.91 (969); bottom-up 37.98 / +7.42 (966); OLS 37.85 / +10.40 (964); WLS 37.14 / +8.54 (945); MinT 37.40 / +7.86 (958).
                            **No method passes ASHRAE 14** (CV(RMSE) ≤ 30 %, NMBE within ±10 %) in validation or test; OLS also fails NMBE in test.
                            Zone level (test, direct model): NE 28.4 % (pass), NW 46.9 %, SW 62.5 %, SE 103.4 %. NW Plugs & Sockets (CV 53.5 %, MAE 826 Wh/h) is the main source of floor-total error.
                            Coherence (test): the direct total differs from the sum of the zone forecasts by 437 Wh/h (12.8 % of mean consumption); all reconciled forecasts have gap = 0.
                            Files: `T30_floor1_total_forecast_results.xlsx`, `T30_floor1_total_forecast_hourly.csv`, `T30_experiment_log_rows.csv`, figures `T30_total_forecast_vs_actual.png`, `T30_total_MAE_by_hour.png`, `T30_coherence_gap.png`. |
| **Interpretation** |  All LightGBM-based methods beat the seasonal-naive baseline (about 8 CV points in test), but the best result (WLS, 37.14 %) is still above the 30 % ASHRAE threshold. The model is not good enough for the floor total, which supports trying other approaches.
                        Reconciliation improves accuracy only slightly (about 1.5 CV points vs the direct model). The differences between OLS, WLS and MinT are within noise, so no method can be declared best. Its main benefit is coherence between total and zones.
                        Error is concentrated in working hours (MAE ≈ 1.4–1.7 kWh between 07:00 and 15:00 vs ≈ 0.55 kWh at night). The models smooth the peaks (hours above 6 kWh: actual mean 7.8 kWh vs forecast 6.4 kWh) and over-forecast low-load periods (all methods have positive NMBE; Lighting is strongly over-forecast).
| **Issued found** |  The 2025 test block could not be evaluated: SW has no valid 2025 data, so no hour passes the "all series valid" rule. `test_2023` and `test_all` are identical.
                      The test set is small and fragmented (586 h, 19 Jan – 1 Mar 2023, winter only). The test period written in `T30_experiment_log_rows.csv` (2023-01-01 to 2023-12-31) overstates the real coverage.
                      Midday hours are barely represented (only 8–13 test hours at 12:00–14:00), so the MAE-by-hour curve is unreliable there.
                      Validation metrics of OLS/WLS/MinT are optimistic: the reconciliation weights are estimated from the validation residuals. Only the test results are out-of-sample.
                      Regex bug: Emergency Lighting series were not excluded from the total (negligible effect).
                      In the forecast-vs-actual plot, lines are drawn across data gaps (misleading straight segments). |
| **Extras** | • Task executed by María Herraiz.|



### Entry 19 — 14/11/2026

| Field | Content |
|---|---|
| **Date** | 14/11/2026 |
| **Dataset version** | v0.4 (`cedint_f1_model_ready.csv`) |
| **Cleaning steps** | • No cleaning of values: the file was already clean.• Used the `split`, `include_train` and `include_eval` columns of the file (training rows: `include_train = 1`; evaluation rows: `include_eval = 1`, no shuffling).• Kept only HVAC, Lighting and Plugs & Sockets (10 zone × load series: NE HVAC, NE P&S, NW HVAC, NW Lighting, NW P&S, SE HVAC, SE Lighting, SE P&S, SW Lighting, SW P&S). Secondary loads and SE Projector excluded.• Lags computed by timestamp (not by row), so they are empty across the 902-day gap. Hours without a value 168 h earlier are not scored, so both models are compared on the same hours. |
| **Model tested** | • **Day-ahead (24 h) forecast per zone × load type (F1.2 / T29)** in `F1.2_T29_dayahead_models_MH_v2.Rmd`:
    – Seasonal naive (same hour last week, baseline).
    – LightGBM (one model per series).
  • SARIMAX (part of the original T29 plan) was not run in this version, just the LightGBM model. |
| **Parameters tested** | • **LightGBM:** 6 configurations per series (num_leaves 15/31/63 × min_data_in_leaf 20/100); fixed learning_rate 0.05, feature_fraction 0.8, bagging_fraction 0.8, lambda_l2 1; up to 500 rounds with early stopping (30) on the validation period; best configuration chosen on validation RMSE. Chosen: num_leaves 15 in 7 of 10 series, 31 in the other 3; best iterations 35–128.• **Features (14 for NE, 18 for the others):** local hour, weekday, month, is_weekend, is_holiday, is_august_low_use, flag_covid_2020; target lags 24, 48, 72, 168, 336 h; mean of the previous day; same-hour mean of the last 7 days; indoor temp, humidity, luminosity and occupancy lagged 24 h (NE has no indoor sensors). All target features lagged ≥ 24 h (no leakage). No outdoor weather.• **Split:** train 2020-06-01 to 2022-06-30; validation 2022-07-01 to 2022-12-31; test_2023 2023-01-01 to 2023-02-28; test_2025 2025-08-18 to 2025-10-13. |
| **Results obtained** | • **LightGBM beats the seasonal naive in 26 of 28 series-period comparisons** (validation 10/10, test 2023 9/10, test 2025 7/8). It loses only in SE Lighting 2023 (211.6 vs 197.3 %) and NW Lighting 2025 (157.0 vs 117.9 %).• **ASHRAE 14 pass (CV(RMSE) ≤ 30 %, NMBE within ±10 %), LightGBM:** validation 1/10 (SW P&S 20.4 %); test 2023 2/10 (NE P&S 26.5 %, SW P&S 29.3 %); test 2025 2/8 (NE HVAC 17.6 %, NE P&S 6.7 %). All other series fail.• **Test 2023, CV(RMSE) % LightGBM (naive):** HVAC: NE 689.7 (974.9), NW 47.2 (104.0), SE 49.0 (66.6). Lighting: NW 91.1 (117.4), SE 211.6 (197.3), SW 193.1 (209.8). Plugs & Sockets: NE 26.5 (53.8), NW 53.4 (63.8), SE 144.0 (173.8), SW 29.3 (38.5).• **Test 2025, CV(RMSE) % LightGBM (naive):** HVAC: NE 17.6 (25.0), NW 95.4 (133.5), SE 35.8 (44.3). Lighting: NW 157.0 (117.9), SE 325.4 (408.0). Plugs & Sockets: NE 6.7 (10.8), NW 41.7 (54.6), SE 34.7 (43.9). SW has no 2025 data.• The main load, NW Plugs & Sockets, reaches CV 53.4 % (MAE 1,106 Wh) in 2023 and 41.7 % (MAE 179 Wh) in 2025.• Top LightGBM features by gain: `lag_24`, `mean_prev_day` and `same_hour_mean_7d` in almost every series; `lum_lux_l24` is second or third for NW and SE Lighting.• Files: `T29_dayahead_predictions.csv`, `T29_metrics_ashrae.csv`, `T29_best_params.csv`, `T29_lgb_importance.csv`, `T29_experiment_log_rows.csv` (56 rows), `zone_load_forecasts_T29.csv` (input for T30), figure `Day_ahead_CV_by_series_T29.png`. |
| **Interpretation** | • LightGBM is clearly better than the baseline, but it reaches the ASHRAE 14 limit in only a few series. Plugs & Sockets is the most predictable load (calendar-driven), HVAC is intermediate, and Lighting is the worst, with large systematic bias (NMBE: NW Lighting +27.8 % in 2023 and +98.0 % in 2025; SE Lighting −76.9 % and −85.8 %).<br>• The importance ranking shows that the models mainly extrapolate the recent past (previous day, same hour last week). Calendar flags and indoor drivers add little, except lagged luminosity for Lighting.<br>• Results for test 2023 (Jan–Feb, winter) and test 2025 (Aug–Oct) are not directly comparable: they cover different seasons and only about 2 months each. 2025 is better in several series (e.g. NW Plugs & Sockets 53.4 → 41.7 %), but this cannot be attributed to the model.<br>• CV(RMSE) is unreliable for very low-consumption series (NE HVAC: mean of only a few Wh per hour; 689.7 % in 2023 vs 17.6 % in 2025 with MAE 4.6 vs 0.4 Wh). This agrees with the CV inflation seen in Entry 15. |
| **Issued found** | • SW has no 2025 data, so it is evaluated on 2023 only; NE has no Lighting and SW no HVAC.• Test periods are short (2023: Jan–Feb; 2025: 18 Aug – 13 Oct).• Validation metrics are slightly optimistic: validation is used for early stopping and for choosing the configuration. Only the test results are out-of-sample.• Strong bias in Lighting forecasts (see Interpretation); possible level shifts or changes in use between periods still to be checked.• `zone_load_forecasts_T29.csv` covers only the 10 core series. |
| **Extras** | • Task executed by María Herraiz. Covers backlog item **F1.2**, T29.|

### Entry 20 — 14/11/2026

| Field | Content |
|---|---|
| **Date** | 14/11/2026 |
| **Dataset version** | v0.4 (`cedint_f1_hourly_clean.csv.gz`, used as the reference for `y_true`) + forecasts of all subteam D models in the agreed format (`timestamp_utc, zone, load_type, model, split, y_true, y_pred`) |
| **Cleaning steps** | • All predictions files (also inside the zips) merged into one file with `T36_combine_predictions.py`: the same split names set by date for every model, training rows dropped, duplicates removed.<br>• Timestamps checked against the clean dataset: `y_true` matches `energy_wh_model` in 100 % of rows for every model except GBM.<br>• `All_Zones_GBM_predictions.csv` stores Madrid local time in the column `timestamp_utc` (95 % of rows do not match as UTC, 0 % mismatch as local time): converted to UTC automatically. GBM also labels the whole out-of-sample period `test`: re-labelled by date (validation / test_2023 / test_2025). |
| **Model tested** | N/A (Evaluation of all forecasts – T28, T34, T35, preparation of T38 and T40).<br>10 models, 763,171 forecast hours: Chronos (`chronos_bolt_base`), CatBoost and CatBoost without 2020, Random Forest and Random Forest without 2020, GBM, LightGBM, seasonal naive, plus the reference benchmarks `naive_day` (same hour yesterday) and `naive_week` (same hour last week). |
| **Parameters tested** | • Best model per series chosen on the validation period only, on the hours that every model forecast (lowest CV(RMSE)); then scored on test_2023 and test_2025 against `naive_day` on the same hours (`TeamB_select_best_model.py`).<br>• ASHRAE Guideline 14 hourly criteria: CV(RMSE) ≤ 30 % and \|NMBE\| ≤ 10 %.<br>• T34: error = MAE as % of the series mean, by hour of day, day type, season and zone / load type.<br>• T35: days and hours where the best model is far off compared with its normal error (robust z-score), at most 3 per series, each with a first explanation from the calendar and the quality flags.<br>• T40: scores with and without flagged hours. |
| **Results obtained** | • Best model: Chronos for 8 series, GBM for 5, Random Forest without 2020 for 1 (SW Lighting).<br>• The best model beats the benchmark in 14 of 14 series on validation and on test 2023, and in 9 of 11 on test 2025 (exceptions: NE and NW Plugs & Sockets).<br>• ASHRAE 14 met by 6 of 14 series on validation, 7 of 14 on test 2023 and 5 of 11 on test 2025.<br>• T34 (best model, priority series, validation): lowest error at night (17–22 % from 00 to 06 h), highest at 07–09 h (29–30 %) and at 17 h (34 %); weekend 20 %, working day 26 %, holiday 29 %; Lighting hardest (SE 82 %, SW 110 % of the mean), HVAC 14–27 %, Plugs & Sockets 5–24 %, constant loads 0–6 %.<br>• T35: 17 anomaly days, e.g. NE HVAC on 3, 17 and 20 Feb 2023 (quality flags in 33–42 % of hours), SE Lighting on 22 and 29 Aug and 28 Sep 2025 (lighting on during August low use and on a Sunday), SE Plugs & Sockets on 1 Dec 2022 and 30 Jan 2023 (no context found).<br>• T40: removing flagged hours changes NE HVAC validation from 243 % to 12 %, SE Plugs & Sockets from 119 % to 60 % and SE HVAC from 51 % to 28 %; SE and SW Lighting get worse without flagged hours.<br>• T28 (F2.2) closed: NW RACK 0.7 % / 0.5 % / 3.6 % (validation / 2023 / 2025); emergency lighting 2.9–8.6 % on validation; NW Emergency Lighting 2025 34 %, 4.3 % without flagged hours; SW RACK ends in Dec 2021 and is not forecast; hand dryers are not forecastable per hour. |
| **Interpretation** | • No single model wins everywhere, so the dashboard and the report use the best model per series.<br>• The variant without 2020 was only chosen for SW Lighting; for the other series the full training set (with 2020) scored better.<br>• The models know the daily pattern but not the exact moment devices switch on and off.<br>• For NE HVAC, SE Plugs & Sockets and SE HVAC the large errors come from meter problems, not from the model; for SE and SW Lighting the problem is the series itself (rare, large switch-on events).<br>• The constant loads are easy to forecast, but even the benchmark is already within ASHRAE (0.9–12 %), so the forecasting effort belongs to HVAC, Lighting and Plugs & Sockets. |
| **Issued found** | • GBM timestamps stored in local time and the whole out-of-sample period labelled `test`; fixed in `T36_combine_predictions.py`.<br>• 5–10 rows around the October clock change still do not match the clean dataset (negligible).<br>• Lighting shows a strong under-forecast bias (41–60 %).<br>• In 2025, NE and NW Plugs & Sockets are so stable that "same hour yesterday" is hard to beat. |
| **Extras** | • Task executed by Marie Heyse (Team B – Data Quality & Validation). Summary: `TeamB_Sprint3_results.md`. Files: `best_model_selection.csv`, `TeamB_evaluation_best_model.xlsx`, `TeamB_evaluation_all_models.xlsx`, figures `F13_best_model_vs_benchmark.png` and `F11_error_by_hour_best_model.png`. Code: `T36_combine_predictions.py`, `TeamB_select_best_model.py`, `team_b_eval.py`.<br>• Covers backlog items T28 (F2.2), T34 (F6.6) and T35 (F7.1); ready for T38 (F6.4, sheet *ASHRAE_table*) and T40 (F6.7, sheet *Sensitivity_flags*). |

---

### Entry 21 — 11/11/2026

| Field | Content |
|---|---|
| **Date** | 11/11/2026 |
| **Dataset version** | v0.3 (`cedint_f1_hourly_clean.csv.gz`) |
| **Cleaning steps** | • Filtered to `usable_for_model = 1`, target `energy_wh_model`; split aligned with T32 (train 2020-06 to 2022-06, val 2022-H2, test 2023 and 2025). |
| **Model tested** | • **Forecast of zone NE without environmental sensors (F3.3 / T31)**: HistGradientBoosting anchored on `lag_24` with L1 loss, issued at 00:00 using lags ≥ 24 h (scenarios M0–M4, M0d, naive baselines). |
| **Results obtained** | • **NE Plugs & Sockets** passes ASHRAE 14 in every period (val M1 25.2 %, test 2023 27.1 %, test 2025 8.3–8.9 %). **NE HVAC** passes on test 2025 (19.2–20.1 %) and fails on 2023 (11 spike hours carry 57.5 % of energy). Spatial proxies change CV(RMSE) by ≤ 3 pts.<br>• Files: `models/T31_ne_forecast.py`, `predictions_and_eval/T31_NE_results.xlsx`, `predictions_and_eval/T31_NE_predictions.csv`, `docs_and_slides/T31_NE_Forecast_Report.docx`, `figures/F_T31_1`–`6`. |
| **Extras** | • Task executed by Riccardo Tardanico (backlog **F3.3** / T31). |

### Entry 22 — 14/11/2026

| Field | Content |
|---|---|
| **Date** | 14/11/2026 |
| **Dataset version** | v0.4 (`data/T32_cedint_f1_model_ready.csv.gz`) + Open-Meteo weather (`data/openmeteo_madrid_hourly.csv`, T26) |
| **Model tested** | • **Multi-day forecasts (F1.4 / T37)**: direct `GradientBoostingRegressor` for horizons 1, 2, 3, 5, and 7 days across NE, NW, SE HVAC, `FLOOR_TOTAL`, and `FLOOR_TOTAL_noSW`, with/without weather. |
| **Results obtained** | • **CV(RMSE) % (GBM + weather, 1 d → 7 d):** NW HVAC 2023: 50.0 → 80.0 %; SE HVAC 2025: 42.8 → 43.9 %; NE HVAC 2025: 18.3 → 20.1 %; `FLOOR_TOTAL_noSW` 2025: 28.3 → 32.5 %. Beats seasonal naive up to 7 d in 17/18 cases.<br>• **Leakage audit (`cleaning_and_eda/T37_check_gbm_leakage.py`):** identified target leakage in `roll_mean_24` inside `GBM_forallzones.ipynb` (NW HVAC 2023 shifts from 29.6 % to 49.6 % once shifted 24 h).<br>• Files: `models/T37_multihorizon_forecast.py`, `predictions_and_eval/T37_multihorizon_results.xlsx`, `predictions_and_eval/T37_multihorizon_predictions.csv.gz`, `figures/F37a`–`F37d`, `docs_and_slides/T37_REPORT.md`. |
| **Extras** | • Task executed by Riccardo Tardanico (backlog **F1.4** / T37). |

### Entry 23 — 24/11/2026

| Field | Content |
|---|---|
| **Date** | 24/11/2026 |
| **Dataset version** | v0.4 (`cedint_f1_hourly_clean.csv.gz`, `best_model_predictions_final.csv`, `predictions_and_eval/TeamB_T38_final_evaluation.xlsx`, `models/outputs_T30/T30_floor1_total_forecast_hourly.csv`) |
| **Cleaning steps** | • Consolidated 150+ artifacts into the **DataPack v1.0** 7-folder structure (`data/`, `cleaning_and_eda/`, `models/`, `predictions_and_eval/`, `figures/`, `docs_and_slides/`, `archive/`) via `git mv`, leaving 7 core files at the root. |
| **Results obtained** | • **Final Model Selection & Executive Summary (T38 / T42):** across 14 series (Chronos-Bolt 7, GBM 3, Hybrid 3, RF without 2020 1), positive skill over `naive_day` in 37/39 cases (median skill 0.31 val, 0.30 test 2023, 0.19 test 2025); MinT floor total 37.4 % vs 45.2 % naive on test 2023.<br>• Summary published in `docs_and_slides/CeDInt_F1_Results_Summary.md` and Streamlit dashboard (`T36_dashboard_app.py`) validated end-to-end. |
| **Extras** | • Executed by Team G3 (Marie Heyse, Riccardo Tardanico, Anthony Rivière, Ludovica, María Herraiz). |
