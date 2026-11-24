# CRISP-DM Report – CeDInt-SEF Smart Energy Forecasting

Group 3 · *Tools for Big Data Analysis* · Universidad Politécnica de Madrid (UPM) · Status: 15 November 2026 (Sprint 4)

---

## Contents

- [Summary](#summary)
- [1. Business Understanding](#1-business-understanding)
- [2. Data Understanding](#2-data-understanding)
- [3. Data Preparation](#3-data-preparation)
- [4. Modelling](#4-modelling)
- [5. Evaluation](#5-evaluation)
- [6. Deployment](#6-deployment)

---

## Summary

Group 3 acts as a consulting team for CeDInt, a smart building on the UPM Montegancedo campus. The goal is a **day-ahead (next 24 hours) hourly forecast of electrical energy** for every zone and load type of floor 1, explained by its drivers and documented so that every step can be audited and reproduced. The work follows the Cross-Industry Standard Process for Data Mining (CRISP-DM), organised in two-week Scrum sprints. This report covers Sprints 1–3 and the start of Sprint 4.

**Table 1 – Phase status on 15 November 2026**

| Phase | Status |
|---|---|
| 1. Business Understanding | Complete |
| 2. Data Understanding | Complete (all zones, indoor drivers, outdoor weather, secondary loads) |
| 3. Data Preparation | Complete: clean dataset v0.4 and model-ready training data; frozen v1.0 for the release planned |
| 4. Modelling | Day-ahead forecasts done (final check): six model families in the evaluation and a reconciled floor-total forecast; the Chronos + GBM blend and SARIMAX still to be added to the evaluation |
| 5. Evaluation | In progress: best model per series, skill scores, targets per load type, error analysis, anomalies and flag sensitivity done; SHAP, bias check and final model choice open |
| 6. Deployment | In progress: dashboard prototype working; final deck, summary and DataPack v1.0 open |

**Key findings**

1. **Most counter drops are not resets.** They are *partial sums*: some devices are missing from the total for a moment. Only 1,330 hours are real meter resets.
2. **The data has two periods.** Hourly data from 2020 to 2023 and minute data in 2025 are separated by 902 days without data. Timestamps are in Coordinated Universal Time (UTC).
3. **Zone is the strongest effect on consumption.** NW uses the most energy per device; NW HVAC follows cooling demand and SE HVAC follows heating demand.
4. **Clear skill over the naive benchmark.** The best model per series, chosen on the validation period (Chronos for 8 series, GBM for 5, Random Forest without 2020 for 1), has positive skill in 14 of 14 series on validation and test 2023 (median skill 0.32, i.e. a 32 % lower RMSE than the naive forecast) and in 9 of 11 series in 2025.
5. **The targets per load type are met for part of the series.** Constant loads meet their 15 % target in every period (except NW Emergency Lighting in 2025); Plugs & Sockets meet 30 % in NE and SW; HVAC is within 30–50 % for SE in every period and for NW in 2023. The floor-1 total improves from 51 % (naive) to 38 % with reconciliation.
6. **Several large errors come from the meters, not the models.** Removing flagged hours lowers NE HVAC on validation from 243 % to 12 %.
7. **Some errors are systematic.** SE and SW Lighting and NE HVAC in test 2023 show a large bias, which points to a level shift or regime change rather than random error.

**Main open issues.** The test periods are short (January–February 2023 and August–October 2025) and SW has no 2025 data. The teacher must confirm the time zone and the column meanings. Still to finish before the presentation: adding the Chronos + GBM blend and SARIMAX to the evaluation, the final model choice, the SHAP explanation, the bias check, the business value in kWh and euros, the final deck and the DataPack v1.0.

---

## 1. Business Understanding

The business need is to move CeDInt from passive monitoring to predictive energy management, with forecasts a building manager can act on one day ahead.

### 1.1 Background and objectives

Since 2020, Internet of Things (IoT) devices at CeDInt have measured electricity per circuit and indoor conditions (temperature, humidity, light and presence). Today the building is only monitored: managers cannot anticipate demand or detect abnormal consumption before energy is spent.

The Business Case sets five expected outcomes:

1. accurate energy-forecasting models;
2. data-driven decision support, so that managers act before energy is used;
3. identification of energy and cost savings through abnormal patterns and peak hours;
4. adherence to CRISP-DM in two-week Agile sprints;
5. documented and auditable deliverables (experiments, metrics, reproducible code).

### 1.2 Stakeholders

**Table 2 – Stakeholders and their needs**

| Stakeholder | Need |
|---|---|
| UPM / project sponsor | Credible predictive evidence and clear performance metrics |
| Energy / building analyst | Understand past consumption and what may happen next |
| Building manager | Day-ahead forecasts per zone and load type, to act on consumption drivers |
| Facilities technician | Know which meters or sensors are faulty and where anomalies occur |

### 1.3 Scope and constraints

- **In scope:** floor 1 (zones NE, NW, SE and SW – north-east, north-west, south-east, south-west), electrical energy by load type, day-ahead horizon.
- **Out of scope:** sensor installation, automatic control of heating, ventilation and air conditioning (HVAC), floors 2–3, thermal energy.
- **Constraints:** raw files are never edited; CeDInt data is confidential under the General Data Protection Regulation (GDPR), processed locally and never committed to GitHub; the dates are fixed.
- **Chosen approach (Business Case, alternative C):** a custom open-source predictive framework run locally, instead of doing nothing (alternative A) or buying a commercial software-as-a-service (SaaS) platform (alternative B). External cost: €0.

**Table 3 – Main risks**

| Risk | Mitigation |
|---|---|
| Poor data quality (missing values, counter problems, reversed meter) | Hypothesis-based cleaning rules; problems are flagged, never deleted |
| Short and broken history (902-day gap) | Treat the two periods separately; never compute lags across the gap; report seasonal limits |
| Wrong time zone | Treat timestamps as UTC and add Madrid local time; teacher to confirm |
| Overfitting | Chronological splits only; models chosen on the validation period; scores reported on unseen test periods |
| Unfair model comparison | One prediction format, one evaluation script and the same hours for every model |
| Bottlenecks between subteams | Baselines on a sample from Sprint 1; weekly check-ins |

### 1.4 Data-mining goals

- **Target:** `energy_wh_model`, the active energy used in each hour (Wh).
- **Unit of forecast:** each zone × load type, plus the floor-1 total.
- **Horizon:** the next 24 hours, issued at 00:00 on day D for hours 1–24; only information available at that moment may be used.
- **Explanation:** which drivers matter for each load type.

**Table 4 – Energy types in scope**

| Energy type | Decision | Priority |
|---|---|---|
| HVAC (NE, NW, SE) | Core – largest and most weather-dependent load | High |
| Lighting (NW, SE, SW) | Core – driven by occupancy and daylight | High |
| Plugs & Sockets (all four zones) | Core – present in every zone, tied to occupancy | High |
| Floor-1 total | Core – one figure for the building manager | High |
| RACK, Emergency Lighting | Secondary – constant loads, forecast per hour as a control group | Low |
| Hand Dryer | Secondary – event-driven, reported as daily totals only | Low |
| SE Projector, apparent energy | Out of scope – always zero / not the target | – |

### 1.5 Success criteria

Following the professor's guidance, models are judged on data never used in training in three ways:

1. **Skill over the naive benchmark (main measure):** skill = 1 − RMSE<sub>model</sub> / RMSE<sub>naive</sub>. A model is useful when its skill is above 0; a skill of 0.32 means a 32 % lower root-mean-square error (RMSE) than the naive forecast.
2. **Targets per load type**, because the load types behave very differently (table below).
3. **ASHRAE Guideline 14** (American Society of Heating, Refrigerating and Air-Conditioning Engineers) as a common reference, **not a pass/fail test**: for hourly models a coefficient of variation of the root-mean-square error **CV(RMSE) ≤ 30 %** and a normalised mean bias error **NMBE within ±10 %**; for coarser steps such as months, ASHRAE uses 15 % and 5 %.

**Table 5 – Targets per load type**

| Load type | Target (hourly) |
|---|---|
| Constant loads (RACK, emergency lighting) | CV(RMSE) ≤ 15 % |
| Plugs & Sockets | CV(RMSE) ≤ 30 % |
| HVAC | CV(RMSE) 30–50 %, beats the naive forecast, NMBE within ±10 % |
| Lighting | Judged on daily energy, MAE in kWh and switch-on timing |

The mean absolute error (MAE), also in kWh, and the RMSE are reported as well. Results are reported as a hierarchy, from hour to day and from series to zone to floor; daily values are the sum of the 24 hourly day-ahead forecasts, so every level comes from the same model.

$$\mathrm{CV(RMSE)} = \frac{\sqrt{\frac{1}{n}\sum_{i}(y_i-\hat{y}_i)^2}}{\bar{y}} \times 100\,\% \qquad \mathrm{NMBE} = \frac{\sum_{i}(y_i-\hat{y}_i)}{n\,\bar{y}} \times 100\,\%$$

where $y_i$ is the measured and $\hat{y}_i$ the forecast energy in hour $i$, $n$ the number of hours and $\bar{y}$ the mean measured energy. With this formula a positive NMBE means the model forecasts too little.

### 1.6 Project plan and team

**Table 6 – Project calendar (2026)**

| Period | Dates | Focus | Status |
|---|---|---|---|
| Sprint 1 | 1–14 October | Business and data understanding, clean data, first baselines | Done |
| Sprint 2 | 15–28 October | Calendar features, spatial structure, drivers, outdoor weather | Done |
| Sprint 3 | 29 October – 11 November | Training data, forecasts, error analysis, anomalies, dashboard prototype | Mostly done |
| Sprint 4 | 12–25 November | Evaluation, explanation, final deck | Running |
| Rehearsal | 26–28 November | Speaker split and practice | – |
| Final presentation | 30 November | 20 minutes + 20 minutes discussion | – |
| Release | by 14 December | Feedback processed; DataPack in the Moodle dropoff area | – |

**Table 7 – Team (11 members), initial subteam structure**

| Subteam | People | Responsibility |
|---|---|---|
| A – Data Engineering | 3 | Loading, hourly dataset, calendar features, spatial structure, weather data |
| B – Data Quality & Validation | 3 | Cleaning rules, flags, training data, evaluation toolkit, model validation |
| C – Exploration & Environment | 2 | Consumption profiles, drivers, environment and weather vs energy |
| D – Modelling & Forecasting | 1 | Baselines and forecasting models |
| E – Coordination & Communication | 2 | Repository, CRISP-DM report, backlog, slides, final deck |

The group started with these subteams; now every backlog item has one named owner and a deliverable, and the work is linked through the shared GitHub repository and agreed file formats (one clean dataset and one forecast format). The Product Backlog has 44 items and is updated every sprint; at the mid-term review (16 November 2026), 34 were complete, 6 in progress and 4 not started.

A quality-assurance role owns the Experiment Logbook (`EXPERIMENT_LOGBOOK.md`), and the course teacher is the project owner. The team works in Python (and R for the day-ahead and floor-total models); code is kept in the GitHub repository `TBDA-Classes/2026G3` and documents in Microsoft Teams.

> **Phase 1 summary.** Objectives, stakeholders, scope, constraints, risks and measurable success criteria (skill over the naive benchmark and targets per load type) are defined. The scope of hourly forecasting is now fixed: HVAC, Lighting and Plugs & Sockets as targets, constant loads as a control group, hand dryers as daily totals.

---

## 2. Data Understanding

The data covers five and a half years of floor 1, but it is usable only after resolving missing values stored as zero, counter drops, a reversed meter and a 902-day gap between two sampling periods.

### 2.1 The data

The DataPack consists of four Excel files, `Storey1_<zone>_report_by_device.xlsx`, one per zone. Each sheet holds one load type in one zone, already summed over its devices.

**Table 8 – Raw data per zone**

| Zone | Load types (sheets) | Rows | Environmental data |
|---|---|---|---|
| NE | HVAC, Plugs & Sockets | 175,545 | None |
| NW | Emerg. Lighting, HVAC, Hand Dryer, Lighting, Plugs & Sockets, RACK | 525,622 | Yes |
| SE | Emerg. Lighting, HVAC, Lighting, Plugs & Sockets, Projector | 345,294 | Yes |
| SW | Emerg. Lighting, Hand Dryer, Lighting, Plugs & Sockets, RACK | 288,684 | Yes |
| **Total** | **18 sheets** | **1,335,145** | |

**Columns (meanings verified on the data):** Timestamp (UTC); W = active power; Pa = apparent power; I = current; **Er = active-energy counter (Wh)**; Ea = apparent-energy counter; number of devices; Lum = light (lux); Hum = humidity (%); Temp = indoor temperature (°C); **Pres = presence (0/1), not pressure**. The meanings of Er and Ea differ from the labels on the course slides; this is an open question for the teacher.

### 2.2 Data structure and indoor conditions

- **Two sampling periods:** hourly data from 2 April 2020 to 28 February 2023, then **902 days without data**, then one row per minute from 18 August to 13 October 2025.
- **Gaps** of up to 37 days inside the hourly period.
- **Environment is zone-level:** temperature, humidity, light and presence are identical on all sheets of a zone. Zone NE has no environmental sensors.
- **Indoor temperature** (clean dataset v0.3, hourly period): mean NW 22.1 °C, SE 20.7 °C, SW 20.1 °C. The lowest values (5.4 / 4.1 / 3.8 °C) occur on 13 January 2021, after Storm Filomena; the highest are 42.2 °C in NW on 14 August 2021 and 33.2 °C in SE on 15 August 2021, during a heatwave.
- **Humidity** is almost constant (mean 30–32 %).

### 2.3 Consumption profiles (subteam C, notebook P7)

Subteam C profiled HVAC, Lighting and Plugs & Sockets in every zone on dataset v0.3, in local time and only on rows with `usable_for_model = 1`: by hour, weekday and month, working days vs weekends, August vs other months, and 2020 vs 2021–22 vs 2025 on the same August–October weeks. The notebook contains 48 labelled and interpreted plots (logbook entry 5).

**Table 9 – Main consumption patterns**

| Load type | Main pattern |
|---|---|
| HVAC | NW highest, SE intermediate, NE very low; daily peak in the late morning; little difference between working days and weekends; NW highest in summer (July–August) |
| Lighting | SE and SW follow the working day and almost stop at weekends and in August; NW is highest at night and lowest in daylight hours |
| Plugs & Sockets | NW far above the other zones, with a daytime peak, lower at weekends and in August and high in winter months; NE, SE and SW lower and stable |

In the same August–October weeks, 2020 differs from 2021–22 (NW HVAC higher, SE and SW lighting lower), so **2020 is treated as a COVID-affected year**.

### 2.4 Spatial structure and comparison between zones (F3.1, F3.2)

- **Spatial structure (logbook entry 8):** all 18 series are organised in one long table keyed by timestamp, building, floor, zone code (`1NE`, `1NW`, `1SE`, `1SW`) and load type, with the zone-level environmental values aligned per zone. This allows direct aggregation by zone and load type.
- **Consumption per device (logbook entry 9):** energy was normalised by the number of installed devices, so that a larger zone is not mistaken for an inefficient one. **NW has the highest consumption per device** for Plugs & Sockets, Lighting and HVAC, with the clearest difference for Plugs & Sockets. SE Projector is always zero and was left out.

### 2.5 Environment, occupancy and outdoor weather vs energy (subteam C)

**Indoor drivers, NW zone (notebook P8, logbook entry 6).**

**Table 10 – Environment and occupancy vs energy (NW zone, 2021–22)**

| Analysis | Result |
|---|---|
| Light vs lighting energy | Correlation −0.372 (17,113 hours): more daylight, less lighting |
| Occupancy vs lighting | Within the same time of day, slightly higher with presence (day 0.069 vs 0.072 kWh; night 0.274 vs 0.304 kWh) |
| Occupancy vs Plugs & Sockets | About 4.8 % higher with presence (1.248 vs 1.308 kWh) |
| Indoor temperature vs HVAC | Weak linear correlation (+0.174) but a non-linear pattern: highest HVAC use at 22–24 °C |
| Humidity vs HVAC | Very weak (+0.059); 89 % of readings are 30–31 % |
| Presence by hour | 29.5 % of hours at 02:00, 67 % at 14:00; some presence also detected at night |

**Relation matrix for all zones with sensors (F5.2, logbook entry 10).** Subteam C computed Pearson, Spearman and partial correlations that remove the effect of the hour of day, and kept relationships with |r| ≥ 0.20. NE was left out because it has no sensors.

**Table 11 – Strongest driver relationships after removing the hour of day (F5.2)**

| Zone | Relationship | Partial correlation |
|---|---|---|
| NW | Indoor temperature – Plugs & Sockets | −0.457 |
| SE | Indoor temperature – Emergency Lighting | +0.798 |
| SW | Occupancy – Lighting | +0.297 (about 350 W with presence vs 44 W without) |
| SE | Light – Lighting | +0.275 |

After the sign correction of NW Emergency Lighting, subteam C repeated the calculation for that series (`P7_and_F5_2_data_quality_validation.ipynb`): no negative values remain, the partial correlation with indoor temperature stays at about −0.23, and the conclusions of F5.2 are unchanged. Humidity varies very little and adds little information.

**Outdoor weather (F5.3, notebook P9, logbook entry 11).** Outdoor temperature from Open-Meteo was compared with HVAC energy, using heating and cooling degree-hours and lags of 0 to 6 hours.

- **NW HVAC is cooling-driven:** correlation with cooling degree-hours r = +0.312; average HVAC energy rises from about 97 Wh to 217 Wh with cooling demand; the relationship is strongest without delay (lag 0).
- **SE HVAC is heating-driven:** Spearman correlation with heating degree-hours +0.362; the correlation with outdoor temperature becomes stronger with the lag (from −0.124 to −0.248).
- UTC weather timestamps had to be converted to Madrid time to avoid shifts in the lag calculations.

**Limitations:** relationships are non-linear and interact (occupancy with the hour, temperature with HVAC operation); correlations do not show cause and effect; indoor temperature is itself influenced by the HVAC system.

### 2.6 Secondary loads (F2.2)

Subteam B characterised the secondary loads on the hourly period (`secondary_loads.py`, `TeamB_F2.2_secondary_loads.xlsx`).

**Table 12 – Secondary loads (2020–23, usable hours)**

| Series | Mean (Wh per hour) | Hours near 0 Wh | Naive day-ahead CV(RMSE) | Class |
|---|---|---|---|---|
| NW RACK | 160.1 | 0 % | 2.9 % | Constant |
| SW RACK (until December 2021) | 277.8 | 0 % | 3.8 % | Constant |
| NW Emerg. Lighting | 12.3 | 3 % | 9.6 % | Constant |
| SE Emerg. Lighting | 1.7 | 4 % | 13.7 % | Constant |
| SW Emerg. Lighting | 11.1 | 0 % | 14.3 % | Constant |
| NW Hand Dryer | 2.3 | 98 % | 3,147 % | Event-driven |
| SW Hand Dryer | 11.6 | 83 % | 1,314 % | Event-driven |

Constant loads are already forecast within their 15 % target by the naive benchmark, so they serve as a control group. Hand dryers cannot be forecast per hour and are reported as daily totals; 17 long high-power runs (at least 3 hours above 500 W), mostly in winter, are listed as anomaly candidates.

### 2.7 Data quality problems

**Table 13 – Data quality problems**

| # | Problem | Consequence |
|---|---|---|
| Q1 | Missing values stored as 0 (Temp and Hum = 0 together) | 0 °C would be read as a real value |
| Q2 | Two periods and a 902-day gap | Few seasons to learn from; never interpolate across the gap |
| Q3 | Gaps of 1–37 days | Lag features break at gaps |
| Q4 | Counter drops – mostly partial sums, only 1,330 real resets | Naive differences give large negative energy |
| Q5 | NW Emerg. Lighting negative 99 % of the time (reversed clamp); small negatives elsewhere | Wrong sign or noise |
| Q6 | SE Projector always 0; SW RACK ends on 3 December 2021 | Nothing to forecast |
| Q7 | SW temperature sensor error in early March 2022 (about 850 °C) | Distorts averages |
| Q8 | No environmental data in NE | NE needs outdoor weather or calendar features only |
| Q9 | Column labels differ from the course slides | Risk of choosing the wrong target |
| Q10 | Timestamps in UTC | Local time needed for calendar features |
| Q11 | 2025 minute data sums only the devices that reported (complete minutes: NE 94 %, NW 87 %, SE 56 %, SW 43 %) | SW 2025 not usable |
| Q12 | 2025 level differs from the same weeks of 2021–22 for NW Lighting, NW HVAC and SE Lighting | Reported separately in test 2025 |

### 2.8 Hypotheses

Each hypothesis was tested with a count, a plot or a model result; a confirmed hypothesis becomes a preparation rule in phase 3.

**Table 14 – Hypotheses and results**

| # | Hypothesis | Result |
|---|---|---|
| H1 | Pres is occupancy | Supported: 0/1 values with a daily pattern; night readings to be treated with caution |
| H2 | Temp = Hum = 0 means missing | Confirmed |
| H3 | Lum = 0 is partly darkness, partly missing | Confirmed; Lum = 0 between 10:00 and 16:00 UTC is flagged |
| H4 | Counter drops are resets | Mostly rejected (27,742 partial-sum hours, 21,987 zero-record hours, 1,330 real resets) |
| H5 | Mostly negative power = reversed clamp | Confirmed for NW Emerg. Lighting only |
| H6 | Small negatives near 0 are noise | Confirmed |
| H7 | 2025 and 2020–23 describe the same system | Partly (9 of 15 series at a similar level) |
| H8 | Environment is zone-level | Confirmed |
| H9 | Dead series carry no information | Confirmed (SE Projector; SW RACK after 2021) |
| H10 | NE has no environmental sensors | Confirmed |
| H11 | 2020 is abnormal (COVID) | Supported (P7), but without one clear direction (section 3.4); 2020 kept in training and tested as a variant |
| H12 | Holidays and August lower consumption | Partly: August lower for lighting and NW Plugs & Sockets, higher for NW HVAC; holidays flagged in v0.4 and among the hardest days to forecast (section 5.4) |
| H13 | Timestamps are UTC | Confirmed by the data; teacher to confirm |
| H14 | HVAC depends on outdoor weather | Supported: NW cooling-driven, SE heating-driven (F5.3) |
| H15 | Secondary loads need no complex model | Confirmed for RACK and emergency lighting; hand dryers not forecastable per hour |

> **Phase 2 summary.** All 18 sheets profiled; consumption profiles, the spatial structure, the comparison per device, indoor drivers for every zone with sensors, outdoor weather and the secondary loads are analysed. Twelve quality problems and fifteen hypotheses are documented.

---

## 3. Data Preparation

The current dataset v0.4 keeps every hour and flags every problem; a model-ready file built on it decides, for every hour, whether it may be used for training and for scoring.

### 3.1 Data selection

Each series is rated separately for each period: **Use** (at least 80 % of hours with a valid energy value and power–energy agreement), **Use with caution** (at least 60 %) or **Do not use**.

**Table 15 – Rating per series and period**

| Period | Use | Use with caution | Do not use |
|---|---|---|---|
| 2020–23 (hourly) | 11 series | 6 (NW Hand Dryer and all SW series) | SE Projector |
| 2025 (minute → hourly) | 8 series | 3 (NE HVAC, NW Emerg. Lighting, NW Plugs & Sockets) | 6 (SW Emerg. Lighting, Hand Dryer, Lighting, Plugs & Sockets; NW Hand Dryer; SE Projector); SW RACK has no 2025 data |

**Decisions:** keep every row and flag problems; model only usable rows; exclude SE Projector; never interpolate or compute lags across the 902-day gap.

### 3.2 Data versions

**Table 16 – Data versions**

| Version | Made by | Content | Status |
|---|---|---|---|
| v0.1 | Subteam B (logbook entry 2) | Pilot cleaning rules on the SW file: Temp/Hum = 0 → empty; Lum = 0 → empty between 07:00 and 19:00; Pres = 0 → empty if Temp present | Replaced |
| v0.2 | Subteam A (`Task_A1_A5.ipynb`, logbook entry 1) | 18 sheets read, renamed and sorted; hourly resampling; energy from the counter; one long table `cedint_f1_hourly.csv` of 450,482 rows × 17 columns; 82,423 hours flagged as resets (far too many) | Replaced |
| v0.3 | Subteam B (`clean_cedint.py`, logbook entry 3) | `cedint_f1_hourly_clean.csv.gz`: 470,680 rows × 50 columns, series ratings and 16 quality flags | Replaced |
| v0.4 | Subteam B (`clean_cedint.py`) | v0.3 plus calendar flags and current checks: 470,680 rows × 55 columns | **Current** |
| Model-ready | Subteam B (`T32_make_training_data.py`) | `cedint_f1_model_ready.csv.gz`: built from v0.4, with split, scope, training and scoring columns, calendar and sensor features and lags | **Current** |
| v1.0 | Sprint 4 | Frozen dataset for the final models and Moodle | Planned |

### 3.3 Cleaning steps and calendar features

**Cleaning (v0.3, kept in v0.4).** Raw values are kept, every problem gets a flag, and nothing is deleted:

1. Flip the sign of the reversed meter (NW Emerg. Lighting).
2. Label each counter reading as ok, zero record, partial sum, spike or real reset.
3. Remove zero records and partial sums from power; set small negatives (−5…0 W) to 0.
4. Set missing or impossible environmental values to empty (Temp = Hum = 0; Temp outside 0–50 °C; Hum outside 5–95 %).
5. Build a complete hourly grid; 2025 minutes are averaged over complete minutes only.
6. Compute hourly energy from the counter, never across a real reset.
7. Build the target `energy_wh_model`: counter energy, else power × 1 h, else interpolation for gaps of up to 3 hours.
8. Rate every series and add Madrid local time (`timestamp_local`) for calendar features.

**Table 17 – Main cleaning results (series-hours)**

| Problem | Rule | Hours |
|---|---|---|
| Partial sum | Power and energy set to empty | 27,742 |
| Zero record | Power and energy set to empty | 21,987 |
| Real counter reset | New counter segment; no energy across it | 1,330 |
| Small negative power (−5…0 W) | Set to 0 | 33,615 |
| Missing hour | Row added and flagged | 20,198 |

**Calendar features (v0.4, F4.3).** All based on local time:

- `is_holiday` and `holiday_name`: national and Comunidad de Madrid public holidays, 2020–2025;
- `is_weekend`;
- `is_august_low_use`: the August low-use period;
- `flag_covid_2020`: the COVID-affected year.

The holiday and August flags were first produced by a separate script on the v0.2 table (`Task_F4_3C.py`, logbook entry 7) and are now part of the cleaning pipeline. Version 0.4 also checks the current readings, and its data dictionary has 42 entries.

**Outdoor weather (F5.3).** Hourly outdoor temperature (and, in some models, solar radiation) comes from the Open-Meteo archive for the CeDInt site and is joined on `timestamp_utc`. Heating and cooling degree-hours are derived from it. The archive holds observed weather, which the models use in place of a weather forecast.

### 3.4 Model-ready training data (T32)

Subteam B built one model-ready file so that every model learns from and is scored on the same hours (`T32_TRAINING_DATA_METHODOLOGY.md`, `training_data_summary_T32_DATACLEANING.xlsx`). **No row is deleted:** three 0/1 columns say how an hour may be used, and `exclusion_reason` says why an hour is left out.

- `include_train` – the model may **learn** from this hour;
- `include_eval` – validation and test **scores** are computed on this hour;
- `include_train_no2020` – the experiment variant without 2020.

**Training is filtered more strictly than testing.** Leaving uncertain hours out of training helps the model learn normal behaviour; leaving them out of the test would make the score look better than it is.

**Table 18 – Agreed periods (UTC)**

| Split | Period | Used for |
|---|---|---|
| Train | 1 June 2020 – 30 June 2022 | Fitting the models |
| Validation | 1 July – 31 December 2022 | Choosing and tuning the model |
| Test 2023 | 1 January – 28 February 2023 | Unseen test 1 (winter) |
| Test 2025 | 18 August – 13 October 2025 | Unseen test 2 (late summer and autumn; NE, NW and SE only) |

**Table 19 – Exclusion rules**

| Rule | Applies to | What is left out | Training hours left out |
|---|---|---|---|
| R0 | Train and scoring | Hours outside the agreed periods (April–May 2020 lockdown, SW in 2025) | 30,805 (whole file) |
| R1 | Train and scoring | Dead series or series rated "Do not use" | 18,240 |
| R2 | Train and scoring | Hours without a valid energy value | 21,399 |
| R3 | Train and scoring | Interpolated values (not a measurement) | 12,136 |
| R4 | Train and scoring | Event-driven loads (hand dryers) | 32,203 |
| R5 | Train only | Counter energy and power × 1 h differ by more than 20 % | 9,087 |
| R6 | Train only | Isolated power spikes (Hampel filter) | 1,147 |

**Result:** 229,086 training hours (157,319 without 2020), 52,566 validation hours, 17,185 test 2023 hours and 13,470 test 2025 hours. Every series keeps at least 69 % of its training hours.

**Why 2020 stays in training.** The data does not show one clear direction for 2020: working-day occupancy was lower than in 2021 in NW and SW but higher in SE, and the change from 2021 to 2022 is just as large as from 2020 to 2021. Dropping 2020 would remove about a third of the training hours. Each model is therefore trained with and without 2020, and the version with the better validation score is kept.

**Deliberately kept:** extreme but real temperatures, holidays, weekends and August, hours rebuilt after a partial sum or counter spike, energy from power × 1 h, series rated "Use with caution" (marked with `series_caution`) and the 2025 series with a level shift (marked with `level_shift_2025`).

> **Phase 3 summary.** Dataset v0.4 adds the calendar flags to the cleaned data, outdoor weather is available, and the model-ready file fixes the same training and scoring hours for every model. Open: the frozen v1.0 for the release.

---

## 4. Modelling

Besides the two Sprint 1 baselines, the team built forecasts with six model families for the 14 series forecast per hour (ten priority series and four constant loads): ten models in total, including the naive benchmarks and the variants without 2020. A Chronos + GBM blend and SARIMAX were also built and are still to be added to the evaluation. The floor-1 total has its own forecast.

### 4.1 Common rules

- **One prediction format** for every model: `timestamp_utc, zone, load_type, model, split, y_true, y_pred`.
- **Day-ahead rule (agreed):** the forecast for an hour may only use target values from at least 24 hours earlier (`lag_24`, `lag_168`, means of the previous day or week).
- **Selection on validation (agreed):** tuning and the choice between variants use the validation period only; the test periods are reported as unseen data.
- **Evaluation toolkit** (`team_b_eval.py`): checks every predictions file, computes MAE, RMSE, CV(RMSE), NMBE and ASHRAE pass/fail, and breaks the errors down.
- **Reference forecasts** (`make_reference_baseline.py`): same hour yesterday (`naive_day`) and same hour last week (`naive_week`).

### 4.2 Models

**Table 20 – Models built**

| Model | Description | Inputs | Logbook |
|---|---|---|---|
| Seasonal naive / naive day / naive week | Same hour one week earlier or one day earlier | Target only | 4, 18 |
| Linear regression | Sprint 1 baseline on NW HVAC | Hour, weekday, indoor temperature | 4 |
| SARIMAX | Seasonal autoregressive model with daily and weekly Fourier terms and outdoor temperature, degree-hours and calendar flags; first day-ahead run only (quick mode); to be added to the evaluation | Calendar, weather | 12 |
| LightGBM (T29) | Light Gradient Boosting Machine, one model per series; 6 configurations tried, early stopping on validation | Calendar flags, target lags of 24–336 h, mean of the previous day, same-hour mean of the last 7 days, indoor values lagged 24 h | 12, 18 |
| Random Forest | Two variants (with and without 2020), tuned on validation | Calendar, `lag_24h`, `lag_168h`, indoor sensors, outdoor temperature and solar radiation | 14 |
| CatBoost | Gradient boosting with categorical calendar features; two variants, tuned on validation | As Random Forest | 15 |
| Chronos (chronos-bolt-base) | Pretrained time-series foundation model; nothing is fitted on CeDInt data; forecasts each day at local midnight from the previous weeks; context length chosen on validation; also gives 10–90 % quantiles | Past energy only | 14 |
| GBM | Gradient Boosting Regressor (100 trees, depth 4), trained with 2020 | Calendar, indoor temperature and degree-hours, occupancy, light, `lag_24`, `lag_168`, 24-hour rolling mean | 16 |
| Chronos + GBM blend | Simple average of the two forecasts, scored so far on the test periods only; to be added to the evaluation | GBM and Chronos forecasts | 16 |

The Random Forest and CatBoost scripts note that indoor sensor values of the same hour are not known when a day-ahead forecast is issued and that observed weather stands in for a weather forecast, so their scores can be slightly optimistic; both scripts include a `strict_day_ahead` mode to check this.

### 4.3 Day-ahead LightGBM vs seasonal naive (T29)

The first run (logbook entry 12) compared seasonal naive, SARIMAX and LightGBM on validation: LightGBM was best in 9 of 10 series, and SARIMAX was weaker, especially on NW HVAC (105 % vs 67 % CV(RMSE)), because a linear model fits an on/off HVAC pattern poorly. The final version (`F1.2_T29_dayahead_models_MH_v2.Rmd`, logbook entry 18) keeps seasonal naive and LightGBM only.

- **LightGBM beats the seasonal naive in 26 of 28** series-period comparisons; it loses only for SE Lighting in 2023 and NW Lighting in 2025.
- **Most important inputs** (by gain): `lag_24`, the mean of the previous day and the same-hour mean of the last 7 days in almost every series; lagged light (`lum_lux_l24`) for NW and SE Lighting. The models mainly extend the recent past; calendar flags and indoor drivers add little.

### 4.4 Floor-1 total (T30)

`F1.3_T30_floor1_total_forecast_MH.R` (logbook entry 17) forecasts the floor-1 total with a hierarchy of 22 nodes (total, 4 zones, 4 load types and 13 zone × load series) and one LightGBM model per node with fixed settings. Six methods are compared on the same hours: seasonal naive, a direct model on the total, bottom-up (sum of the zone × load forecasts) and three reconciliation methods (OLS, WLS and MinT-shrink) that make the zone forecasts add up exactly to the total. Results are in section 5.3.

> **Phase 4 summary.** Forecasts from six model families (ten models) are built in one format, on the same hours and with one evaluation toolkit, and the floor total has its own hierarchical forecast. Open: adding the Chronos + GBM blend and SARIMAX to the evaluation.

---

## 5. Evaluation

Evaluation decides which model is good enough for the building manager and where the forecast can be trusted. Subteam B evaluated 10 models on 763,171 forecast hours (`TeamB_Sprint3_results.md`, `TeamB_evaluation_all_models.xlsx`, `TeamB_evaluation_best_model.xlsx`).

### 5.1 Checks before the evaluation

- All prediction files are in the agreed format, and `y_true` matches `energy_wh_model` of v0.4 in every row except 5–10 hours around the October clock change.
- The GBM file stored Madrid local time in the column `timestamp_utc`; the combining script (`T36_combine_predictions.py`) converts it to UTC so that all models line up hour by hour. GBM also labelled the whole out-of-sample period "test"; the script re-labels it by date.
- The day-ahead LightGBM (T29) and floor-total (T30) files report NMBE with the opposite sign to the formula in section 1.5 (positive = forecast too high), as stated in those files.

### 5.2 Best model per series

The best model is chosen on the **validation period only**, on the hours that every model forecast, and then scored on the test periods (`TeamB_select_best_model.py`, `best_model_selection.csv`).

**Skill over the naive benchmark.** The best model has **positive skill in 14 of 14 series on validation and test 2023** (median skill 0.32, i.e. a 32 % lower RMSE than the naive forecast) and in **9 of 11 series in test 2025**. In 2025 the skill is negative for NE and NW Plugs & Sockets: in that period these loads repeat almost exactly from day to day, so "same hour yesterday" is very hard to beat.

**Table 21 – Best model per series against the target for its load type, CV(RMSE)**

| Series | Best model | Target | Validation | Test 2023 | Test 2025 |
|---|---|---|---|---|---|
| NW RACK | Chronos | ≤ 15 % | **0.7 %** ✓ | **0.5 %** ✓ | **3.6 %** ✓ |
| NW Emerg. Lighting | Chronos | ≤ 15 % | **2.9 %** ✓ | **5.3 %** ✓ | 34 % (4 % without flagged hours) |
| SE Emerg. Lighting | Chronos | ≤ 15 % | **8.5 %** ✓ | **12.4 %** ✓ | **14 %** ✓ |
| SW Emerg. Lighting | Chronos | ≤ 15 % | **6.0 %** ✓ | **10.5 %** ✓ | – |
| NE Plugs & Sockets | GBM | ≤ 30 % | **13 %** ✓ | **19 %** ✓ | **8 %** ✓ |
| NW Plugs & Sockets | GBM | ≤ 30 % | 43 % | 40 % | 52 % |
| SE Plugs & Sockets | Chronos | ≤ 30 % | 116 % | 123 % | **29 %** ✓ |
| SW Plugs & Sockets | Chronos | ≤ 30 % | **14 %** ✓ | **18 %** ✓ | – |
| NE HVAC | GBM | 30–50 % | 243 % | 688 % | **15 %** ✓ |
| NW HVAC | GBM | 30–50 % | 52 % | **30 %** ✓ | 86 % |
| SE HVAC | Chronos | 30–50 % | **48 %** ✓ | **40 %** ✓ | **35 %** ✓ |
| NW Lighting | Chronos | Daily | 73 % | 62 % | 91 % |
| SE Lighting | GBM | Daily | 322 % | 204 % | 284 % |
| SW Lighting | Random Forest (without 2020) | Daily | 433 % | 209 % | – |

✓ = meets the target for its load type (section 1.5). Lighting is judged on daily energy and timing (below), so its hourly CV(RMSE) is shown for reference only. SW has no 2025 data. Validation values for SE HVAC, SE and SW Plugs & Sockets and SE Emergency Lighting are as reported in the mid-term review (16 November 2026); the other values are from `best_model_selection.csv`.

**Lighting, judged per day (NW):** daily CV(RMSE) 42 % on validation, 26 % on test 2023 and 41 % on test 2025, with a mean absolute error of 0.7, 0.65 and 0.5 kWh per day.

- **Constant loads** meet their 15 % target in every period except NW Emergency Lighting in 2025 (34 %, but 4 % without flagged hours); the naive forecast is already very good there, so models add little value. The forecasting effort belongs to HVAC, Lighting and Plugs & Sockets.
- **Plugs & Sockets** meet 30 % in NE and SW; **HVAC** is within 30–50 % for SE in every period and for NW in 2023.
- **Chronos is best for 8 series, GBM for 5 and Random Forest without 2020 for 1.** The variant without 2020 was chosen only for SW Lighting. No single model wins everywhere, so the dashboard and the report use the best model per series.
- **ASHRAE 14 as a reference:** its hourly limits (CV(RMSE) ≤ 30 %, NMBE within ±10 %) are met by 6 of 14 series on validation, 7 of 14 on test 2023 and 5 of 11 on test 2025.
- **The Chronos + GBM blend** (`Model_Comparison_ASHRAE.xlsx`) has the lowest CV(RMSE) of the three in several test results (for example NE Plugs & Sockets 2023: 14.2 %; SW Plugs & Sockets 2023: 16.4 %), but it has no validation scores yet; it will be added to the evaluation together with SARIMAX.

### 5.3 From hour to day and from series to the floor total

Results are reported as a hierarchy: hour → day, and series → zone → floor. Daily values are the sum of the 24 hourly day-ahead forecasts, so every level comes from the same model.

- **From hour to day:** NW HVAC improves from 52 % per hour to 27 % per day (validation).
- **From series to floor:** the floor-1 total improves from 51 % (naive) to 38 % with MinT reconciliation (validation), and the zones add up exactly to the total.

**Table 22 – Floor-1 total, day-ahead (T30), CV(RMSE)**

| Method | Validation (2,682 h) | Test 2023 (586 h) |
|---|---|---|
| Seasonal naive | 50.57 % | 45.21 % |
| LightGBM direct on the total | 41.95 % | 38.64 % |
| Bottom-up | 39.63 % | 37.98 % |
| Reconciliation OLS | 39.71 % | 37.85 % |
| Reconciliation WLS | 38.55 % | **37.14 %** |
| Reconciliation MinT-shrink | 38.32 % | 37.40 % |

- **As a reference, no method meets the ASHRAE 14 hourly limit of 30 %**; all LightGBM-based methods beat the seasonal naive by about 8 points on test 2023.
- **Reconciliation** improves accuracy only slightly (about 1.5 points); its main benefit is coherence: the direct total differs from the sum of the zone forecasts by 437 Wh per hour (12.8 % of mean consumption), while all reconciled forecasts add up exactly.
- **By zone (test 2023):** NE 28.4 % (passes), NW 46.9 %, SW 62.5 %, SE 103.4 %. NW Plugs & Sockets is the main source of error.
- **Errors are concentrated in working hours** (MAE about 1.4–1.7 kWh between 07:00 and 15:00 vs about 0.55 kWh at night); the models smooth the peaks.
- **Test 2025 could not be scored**, because SW has no 2025 data and the total needs every series.

### 5.4 When is the forecast least reliable? (T34)

Error = MAE as a percentage of the series mean, best model, priority series, validation period.

**Table 23 – Error by time and series**

| By | Result |
|---|---|
| Hour of day | Lowest at night (17–22 % between 00:00 and 06:00); highest at the start and end of the working day (29–30 % at 07:00–09:00, 34 % at 17:00) |
| Day type | Weekend 20 %, working day 26 %, holiday 29 % (few holidays to learn from) |
| Season | Validation: summer 17 %, winter 24 %, autumn 30 %; tests: winter 2023 31 %, summer/autumn 2025 34–35 % |
| Load type | Lighting hardest (SE 82 %, SW 110 % of the mean); HVAC 14–27 %; Plugs & Sockets 5–24 %; constant loads 0–6 % |

The models know the daily pattern but not the exact moment devices switch on and off.

### 5.5 Anomaly candidates (T35)

Days and hours where the best model is far off compared with its normal error (robust z-score), at most 3 per series, each with a first explanation from the calendar and the quality flags. The full list (17 days) is in `TeamB_evaluation_best_model.xlsx`.

**Table 24 – Main anomaly candidates**

| Date | Series | Actual vs forecast | First explanation |
|---|---|---|---|
| 3, 17 and 20 February 2023 | NE HVAC | 1.1–3.5 kWh vs about 0.07 kWh | Quality flags in 33–42 % of hours: likely a meter problem |
| 22 and 29 August, 28 September 2025 | SE Lighting | 11.7–14.3 kWh vs 0.3–1.3 kWh | Lighting on in August and on a Sunday; 2025 level shift: check whether lights were left on |
| 19–20 December 2022 | SW Lighting | 8.4–9.9 kWh vs 0.7–1.1 kWh | Quality flags in 50 % of hours |
| 1 December 2022, 30 January 2023 | SE Plugs & Sockets | 3.0–6.3 kWh vs 0.7–1.6 kWh | No context found: check on site |
| 26–27 July 2022 | SE HVAC | About twice the forecast | Quality flags in about 30 % of hours |

### 5.6 Sensitivity to flagged hours (T40)

Removing hours with quality flags changes some scores a lot (best model, validation): **NE HVAC 243 % → 12 %**, SE Plugs & Sockets 119 % → 60 %, SE HVAC 51 % → 28 %. For these series the large errors come from meter problems, not from the model. For SE and SW Lighting the score gets worse without flagged hours, so their problem is the series itself (rare, large switch-on events).

### 5.7 Bias and interpretation

- **Systematic bias:** NMBE of +60 to +81 % for SE Lighting, +33 to +54 % for SW Lighting and +58 % for NE HVAC in test 2023. This points to a level shift or regime change, not random error; recalibration and the 2025 level shift are checked next.
- **NW HVAC:** 30 % in test 2023 but 86 % in test 2025, with almost no bias (0.7 %). The level is right, but the hourly pattern differs between winter 2023 and late summer 2025, in the new data period.
- **Meter faults:** the large NE HVAC errors come from meter faults (243 % → 12 % without flagged hours, section 5.6).

### 5.8 Limitations stated in the files

- Test 2023 covers only January–February and test 2025 only 18 August – 13 October, so the two tests cover different seasons and are not directly comparable.
- SW has no 2025 data; NE has no indoor sensors.
- CV(RMSE) is unreliable for very low series: NE HVAC averages a few Wh per hour, so a small absolute error (MAE 4.6 Wh in 2023, 0.4 Wh in 2025) gives a CV(RMSE) of hundreds of percent; MAE is reported alongside.
- Validation scores are slightly optimistic for models that use the validation period for early stopping or tuning; only the test periods are out of sample.
- NW Lighting, NW HVAC and SE Lighting changed level in 2025.

### 5.9 Still open

- **Final evaluation and model choice (by 25 November):** skill scores, MAE in kWh, targets per load type and results from hour to day to floor, with the Chronos + GBM blend and SARIMAX added. The ASHRAE table for all models and periods already exists (`TeamB_evaluation_all_models.xlsx`, sheet *ASHRAE_table*).
- **Driver explanation with SHAP (T33, by 25 November):** which drivers matter per load type. The Random Forest and CatBoost scripts already produce SHAP plots.
- **Bias check:** SE Lighting and NE HVAC in 2023, recalibration and the 2025 level shift.
- **Business value:** no file yet estimates the savings in kWh and euros.

> **Phase 5 summary.** Every model is scored with the same rules on the same hours. The best model per series has positive skill over the naive benchmark in every series on validation and test 2023 (median 0.32); the targets per load type are met for the constant loads, Plugs & Sockets in NE and SW, and HVAC in SE (and NW in 2023). Errors, anomalies, bias and the effect of meter problems are documented.

---

## 6. Deployment

Deployment turns the results into material the client can use.

### 6.1 Interactive Dashboard & Final Evaluation Integration (T36 / T38 / T30)

`T36_dashboard_app.py` is an interactive Streamlit dashboard running locally on `cedint_f1_hourly_clean.csv.gz` and `best_model_predictions_final.csv`, integrated with `predictions_and_eval/TeamB_T38_final_evaluation.xlsx` and `models/outputs_T30/T30_floor1_total_forecast_hourly.csv`. It covers:

1. **Overview** – energy breakdown by zone and load type, share of consumption, and floor plans (`figures/proyectoedificio-planta-*.svg`).
2. **Consumption** – daily energy, average daily profiles (working day, weekend, holiday), and monthly trends.
3. **Drivers** – energy demand against indoor temperature, humidity, occupancy, and luminosity.
4. **Forecast vs Actual & Best-Model Scorecard** – load-type targets, best-model selection per series (7 Chronos-Bolt, 3 GBM, 3 Hybrid, 1 RF without 2020; median skill 0.30 on test 2023 and 0.19 on test 2025), reconciled Floor 1 totals (T30 MinT), sensorless NE analysis (T31), multi-horizon outlook (T37), and bias/skill alerts.
5. **Data Quality** – series reliability ratings, usable hours, and documented sensor/meter anomalies.

### 6.2 Repository Architecture & Reproducibility (`DataPack v1.0`)

The repository is organized into 7 thematic folders (`data/`, `cleaning_and_eda/`, `models/`, `predictions_and_eval/`, `figures/`, `docs_and_slides/`, `archive/`) with full Git rename history preserved and only 7 essential files at the root.

### 6.3 Remaining Delivery Milestones

- Rehearsal (26–28 November) and 20-minute final presentation (30 November 2026);
- One-page executive summary (`docs_and_slides/CeDInt_F1_Results_Summary.md` completed) / 2-minute walkthrough video;
- Frozen **DataPack v1.0** submission in Moodle by 14 December 2026.

> **Phase 6 summary.** The production-ready Streamlit dashboard, standardized 7-folder repository structure, executive summary (T42), and reproducible pipeline (T26–T42) are complete and verified.
