# CRISP-DM Report – CeDInt-SEF Smart Energy Forecasting

Group 3 · *Tools for Big Data Analysis* · Universidad Politécnica de Madrid (UPM) · Sprint 1 (1–14 October 2026)

---

## Contents

- [Summary](#summary)
- [1. Business Understanding](#1-business-understanding)
- [2. Data Understanding](#2-data-understanding)
- [3. Data Preparation](#3-data-preparation)
- [4. Modelling (Sprint 1 part)](#4-modelling-sprint-1-part)
- [5. Evaluation (plan)](#5-evaluation-plan)
- [6. Deployment (plan)](#6-deployment-plan)

---

## Summary

Group 3 acts as a consulting team for CeDInt, a smart building on the UPM Montegancedo campus. The goal is a **day-ahead (next 24 hours) hourly forecast of electrical energy** for every zone and load type of floor 1, explained by its drivers and documented so that every step can be audited and reproduced. The work follows the Cross-Industry Standard Process for Data Mining (CRISP-DM), organised in two-week Scrum sprints. This report covers Sprint 1; later sprints are described as plans only.

**Table 1 – Phase status after Sprint 1**

| Phase | Status |
|---|---|
| 1. Business Understanding | Complete |
| 2. Data Understanding | Complete (environment analysis so far for the NW zone only) |
| 3. Data Preparation | Clean dataset v0.3 complete; feature table in Sprint 2 |
| 4. Modelling | Started: evaluation framework, two baselines, model plan |
| 5. Evaluation | Planned (Sprints 3–4) |
| 6. Deployment | Planned (Sprint 4 – 14 December) |

**Key findings**

1. **Most counter drops are not resets.** They are *partial sums*: some devices are missing from the total for a moment. Only 1,330 hours are real meter resets.
2. **The data has two periods.** Hourly data from 2020 to 2023 and minute data in 2025 are separated by 902 days without data. Timestamps are in Coordinated Universal Time (UTC).
3. **The clean dataset is ready.** Dataset v0.3 has a model-ready target in 86 % of rows, and nothing was deleted: every problem is flagged.
4. **Zone is the strongest effect on consumption,** and 2020 behaves differently from 2021–22 (COVID).
5. **Both baselines fail the accuracy criterion** on NW HVAC, with a CV(RMSE) of 102.85 % and 113.68 % against a limit of 30 %.

**Main open issues.** The feature table (Sprint 2) blocks advanced modelling. The teacher must confirm the time zone, the column meanings and the forecast target (floor total, zone or load type).

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
| Short and broken history (902-day gap) | Treat the two periods separately; report seasonal limits |
| Wrong time zone | Treat timestamps as UTC and add Madrid local time; teacher to confirm |
| Overfitting | Chronological splits only, no random shuffling |
| Bottlenecks between subteams | Baselines on a sample from Sprint 1; weekly check-ins |

### 1.4 Data-mining goals

- **Target:** `energy_wh_model`, the active energy used in each hour (Wh).
- **Unit of forecast:** each zone × load type, plus the floor-1 total.
- **Horizon:** the next 24 hours.
- **Explanation:** which drivers matter for each load type.

**Table 4 – Energy types in scope (Product Backlog v2)**

| Energy type | Decision | Priority |
|---|---|---|
| HVAC (NE, NW, SE) | Core – largest and most weather-dependent load | High |
| Lighting (NW, SE, SW) | Core – driven by occupancy and daylight | High |
| Plugs & Sockets (all four zones) | Core – present in every zone, tied to occupancy | High |
| Floor-1 total | Core – one figure for the building manager | High |
| Emergency Lighting, Hand Dryer, RACK | Secondary – constant or event-driven loads | Low |
| SE Projector, apparent energy | Out of scope – always zero / not the target | – |

### 1.5 Success criteria

A model succeeds if it beats the seasonal-naive baseline and meets **ASHRAE Guideline 14** (American Society of Heating, Refrigerating and Air-Conditioning Engineers) for hourly models on data never used in training: a coefficient of variation of the root-mean-square error **CV(RMSE) ≤ 30 %** and a normalised mean bias error **NMBE within ±10 %**. The mean absolute error (MAE) and root-mean-square error (RMSE) are also reported.

$$\mathrm{CV(RMSE)} = \frac{\sqrt{\frac{1}{n}\sum_{i}(y_i-\hat{y}_i)^2}}{\bar{y}} \times 100\,\% \qquad \mathrm{NMBE} = \frac{\sum_{i}(y_i-\hat{y}_i)}{n\,\bar{y}} \times 100\,\%$$

where $y_i$ is the measured and $\hat{y}_i$ the forecast energy in hour $i$, $n$ the number of hours and $\bar{y}$ the mean measured energy.

### 1.6 Project plan and team

**Table 5 – Project calendar (2026)**

| Period | Dates | Focus |
|---|---|---|
| Sprint 1 | 1–14 October | Business and data understanding, clean data, first baselines |
| Sprint 2 | 15–28 October | Feature table, drivers, first models |
| Sprint 3 | 29 October – 11 November | Forecasts, explanations, dashboard prototype |
| Sprint 4 | 12–25 November | Evaluation, final deck |
| Rehearsal | 26–28 November | Speaker split and practice |
| Final presentation | 30 November | 20 minutes + 20 minutes discussion |
| Release | by 14 December | Feedback processed; DataPack in the Moodle dropoff area |

**Table 6 – Team (11 members)**

| Subteam | People | Responsibility |
|---|---|---|
| A – Data Engineering | 3 | Loading, hourly dataset, feature table, weather and calendar data |
| B – Data Quality & Validation | 3 | Cleaning rules, flags, consistency checks, model validation |
| C – Exploration & Environment | 2 | Consumption profiles, drivers, environment vs energy |
| D – Modelling & Forecasting | 1 | Baselines, SARIMAX, LightGBM, evaluation |
| E – Coordination & Communication | 2 | Repository, CRISP-DM report, backlog, slides, final deck |

A quality-assurance role owns the Experiment Logbook, and the course teacher is the project owner. The team works in Python with Jupyter Notebook, run locally; code is kept in the GitHub repository `TBDA-Classes/2026G3` and documents in Microsoft Teams.

> **Phase 1 summary.** Objectives, stakeholders, scope, constraints, risks and a measurable success criterion are defined. Open: the teacher's confirmation of the forecast target.

---

## 2. Data Understanding

The data covers five and a half years of floor 1, but it is usable only after resolving missing values stored as zero, counter drops, a reversed meter and a 902-day gap between two sampling periods.

### 2.1 The data

The DataPack consists of four Excel files, `Storey1_<zone>_report_by_device.xlsx`, one per zone. Each sheet holds one load type in one zone, already summed over its devices.

**Table 7 – Raw data per zone**

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
- **Environment is zone-level:** temperature, humidity, light and presence are identical on all sheets of a zone.
- **Indoor temperature** (clean dataset v0.3, hourly period): mean NW 22.1 °C, SE 20.7 °C, SW 20.1 °C. The lowest values (5.4 / 4.1 / 3.8 °C) occur on 13 January 2021, after Storm Filomena; the highest are 42.2 °C in NW on 14 August 2021 and 33.2 °C in SE on 15 August 2021, during a heatwave.
- **Humidity** is almost constant (mean 30–32 %).

### 2.3 Consumption profiles (subteam C, notebook P7)

Subteam C profiled HVAC, Lighting and Plugs & Sockets in every zone on dataset v0.3, in local time and only on rows with `usable_for_model = 1`: by hour, weekday and month, working days vs weekends, August vs other months, and 2020 vs 2021–22 vs 2025 on the same August–October weeks. The notebook contains 48 labelled and interpreted plots (logbook entry 19/10).

**Table 8 – Main consumption patterns**

| Load type | Main pattern |
|---|---|
| HVAC | NW highest, SE intermediate, NE very low; daily peak in the late morning; little difference between working days and weekends; NW highest in summer (July–August) |
| Lighting | SE and SW follow the working day and almost stop at weekends and in August; NW is highest at night and lowest in daylight hours (to be investigated) |
| Plugs & Sockets | NW far above the other zones, with a daytime peak, lower at weekends and in August and high in winter months; NE, SE and SW lower and stable |

In the same August–October weeks, 2020 differs from 2021–22 (NW HVAC higher, SE and SW lighting lower), so **2020 is treated as a COVID-affected year**.

### 2.4 Environment and occupancy vs energy (subteam C, notebook P8)

Subteam C compared environmental and presence data with energy use for the NW zone in 2021–22 (logbook entry 19/10).

**Table 9 – Environment and occupancy vs energy (NW zone, 2021–22)**

| Analysis | Result |
|---|---|
| Light vs lighting energy | Correlation −0.372 (17,113 hours): more daylight, less lighting |
| Occupancy vs lighting | Within the same time of day, slightly higher with presence (day 0.069 vs 0.072 kWh; night 0.274 vs 0.304 kWh) |
| Occupancy vs Plugs & Sockets | About 4.8 % higher with presence (1.248 vs 1.308 kWh) |
| Indoor temperature vs HVAC | Weak linear correlation (+0.174) but a non-linear pattern: highest HVAC use at 22–24 °C |
| Humidity vs HVAC | Very weak (+0.059); 89 % of readings are 30–31 % |
| Presence by hour | 29.5 % of hours at 02:00, 67 % at 14:00; some presence also detected at night |

**Candidate predictors** (Team C final considerations): zone, load type, hour of day, weekday/weekend, month/season, August, year or period, luminosity, temperature and occupancy.

**Limitations:** the relationships are non-linear and interact (occupancy with the hour, temperature with HVAC operation), correlations do not show cause and effect, and P8 covers only the NW zone in 2021–22.

### 2.5 Data quality problems

**Table 10 – Data quality problems**

| # | Problem | Consequence |
|---|---|---|
| Q1 | Missing values stored as 0 (Temp and Hum = 0 together) | 0 °C would be read as a real value |
| Q2 | Two periods and a 902-day gap | Few seasons to learn from; never interpolate across the gap |
| Q3 | Gaps of 1–37 days | Lag features break at gaps |
| Q4 | Counter drops – mostly partial sums, only 1,330 real resets | Naive differences give large negative energy |
| Q5 | NW Emerg. Lighting negative 99 % of the time (reversed clamp); small negatives elsewhere | Wrong sign or noise |
| Q6 | SE Projector always 0; SW RACK ends on 3 December 2021 | Nothing to forecast |
| Q7 | SW temperature sensor error in early March 2022 (about 850 °C) | Distorts averages |
| Q8 | No environmental data in NE | NE needs NW values or outdoor weather |
| Q9 | Column labels differ from the course slides | Risk of choosing the wrong target |
| Q10 | Timestamps in UTC | Local time needed for calendar features |
| Q11 | 2025 minute data sums only the devices that reported (complete minutes: NE 94 %, NW 87 %, SE 56 %, SW 43 %) | SW 2025 not usable |

### 2.6 Hypotheses

Each hypothesis was tested with a count or a plot; a confirmed hypothesis becomes a preparation rule in phase 3.

**Table 11 – Hypotheses and results**

| # | Hypothesis | Result |
|---|---|---|
| H1 | Pres is occupancy | Supported: 0/1 values with a daily pattern (P8, NW); night readings to be treated with caution |
| H2 | Temp = Hum = 0 means missing | Confirmed |
| H3 | Lum = 0 is partly darkness, partly missing | Confirmed; Lum = 0 between 10:00 and 16:00 UTC is flagged |
| H4 | Counter drops are resets | Mostly rejected (27,742 partial-sum hours, 21,987 zero-record hours, 1,330 real resets) |
| H5 | Mostly negative power = reversed clamp | Confirmed for NW Emerg. Lighting only |
| H6 | Small negatives near 0 are noise | Confirmed |
| H7 | 2025 and 2020–23 describe the same system | Partly (9 of 15 series at a similar level) |
| H8 | Environment is zone-level | Confirmed |
| H9 | Dead series carry no information | Confirmed (SE Projector; SW RACK after 2021) |
| H10 | NE has no environmental sensors | Confirmed |
| H11 | 2020 is abnormal (COVID) | Supported (P7) |
| H12 | Holidays and August lower consumption | Partly: August lower for lighting and NW Plugs & Sockets, higher for NW HVAC; holidays in Sprint 2 |
| H13 | Timestamps are UTC | Confirmed by the data; teacher to confirm |

> **Phase 2 summary.** All 18 sheets profiled, 11 quality problems and 13 hypotheses documented, consumption profiles and the first environment analysis delivered. Open: environment analysis for the other zones and the holiday effect (Sprint 2).

---

## 3. Data Preparation

The current dataset v0.3 is ready for modelling: 470,680 rows × 50 columns, a model-ready target in 86 % of rows, and nothing deleted.

### 3.1 Data selection

Each series is rated separately for each period: **Use** (at least 80 % of hours with a valid energy value and power–energy agreement), **Use with caution** (at least 60 %) or **Do not use**.

**Table 12 – Rating per series and period**

| Period | Use | Use with caution | Do not use |
|---|---|---|---|
| 2020–23 (hourly) | 11 series | 6 (NW Hand Dryer and all SW series) | SE Projector |
| 2025 (minute → hourly) | 8 series | 3 (NE HVAC, NW Emerg. Lighting, NW Plugs & Sockets) | 6 (SW Emerg. Lighting, Hand Dryer, Lighting, Plugs & Sockets; NW Hand Dryer; SE Projector); SW RACK has no 2025 data |

**Decisions:** keep every row and flag problems; model only rows with `usable_for_model = 1`; exclude SE Projector; never interpolate across the 902-day gap.

### 3.2 Data versions

**Table 13 – Data versions**

| Version | Made by | Content | Status |
|---|---|---|---|
| v0.1 | Subteam B (logbook 08/10) | Pilot cleaning rules on the SW file: Temp/Hum = 0 → empty; Lum = 0 → empty between 07:00 and 19:00; Pres = 0 → empty if Temp present | Done |
| v0.2 | Subteam A (`Task_A1_A5.ipynb`, logbook 05/10) | 18 sheets read, renamed and sorted; hourly resampling; energy from the counter; one long table `cedint_f1_hourly.csv` of 450,482 rows × 17 columns; 82,423 hours flagged as resets (far too many) | Replaced |
| v0.3 | Team B (`clean_cedint.py`, logbook 17/10) | `cedint_f1_hourly_clean.csv.gz`: 470,680 rows × 50 columns, series ratings and 16 quality flags | **Current** |
| v1.0 | Sprint 4 | v0.3 plus features, frozen for the final models and Moodle | Planned |

### 3.3 Cleaning steps in v0.3

Raw values are kept, every problem gets a flag, and nothing is deleted:

1. Flip the sign of the reversed meter (NW Emerg. Lighting).
2. Label each counter reading as ok, zero record, partial sum, spike or real reset.
3. Remove zero records and partial sums from power; set small negatives (−5…0 W) to 0.
4. Set missing or impossible environmental values to empty (Temp = Hum = 0; Temp outside 0–50 °C; Hum outside 5–95 %).
5. Build a complete hourly grid; 2025 minutes are averaged over complete minutes only.
6. Compute hourly energy from the counter, never across a real reset.
7. Build the target `energy_wh_model`: counter energy, else power × 1 h, else interpolation for gaps of up to 3 hours.
8. Rate every series and add Madrid local time (`timestamp_local`) for calendar features.

**Table 14 – Main cleaning results (series-hours)**

| Problem | Rule | Hours |
|---|---|---|
| Partial sum | Power and energy set to empty | 27,742 |
| Zero record | Power and energy set to empty | 21,987 |
| Real counter reset | New counter segment; no energy across it | 1,330 |
| Small negative power (−5…0 W) | Set to 0 | 33,615 |
| Missing hour | Row added and flagged | 20,198 |

### 3.4 Validation of the prepared data

- **Coverage:** a model-ready target in 404,254 rows (86 %).
- **Source of the target:** 91.0 % centred counter difference, 3.5 % one-sided difference, 4.1 % interpolated, 1.4 % power × 1 h.
- **Power vs energy:** agreement within 20 % in at least 95 % of hours for 14 of 17 series in 2020–23 (exceptions: NE HVAC, NW Hand Dryer, SE Emerg. Lighting).
- **2025 vs the same weeks of 2021–22:** 9 of 15 series are at a similar level (within 1.5×), so 2025 is a valid test period only for stable series rated Use.
- **Documentation:** the full data dictionary (38 entries) is in `CeDInt_F1_quality_and_anomalies.xlsx`, together with the series quality, consistency checks, anomaly log and series-level issues.

**Planned for Sprint 2 (subteam A):** a feature table with calendar variables (hour, weekday, month), holiday, August and COVID-2020 flags, lags of 24 h and 168 h, outdoor weather and the Madrid holiday calendar.

> **Phase 3 summary.** Three dataset versions built; v0.3 applies every cleaning rule with flags and rates every series. Open: the Sprint 2 feature table.

---

## 4. Modelling (Sprint 1 part)

Sprint 1 set up a fair evaluation framework and two baselines on NW HVAC; both fail ASHRAE Guideline 14 and define the bar that later models must beat.

### 4.1 Model plan

**Table 15 – Model plan**

| Model | Description | Status |
|---|---|---|
| Seasonal naive | Forecast = same hour one week earlier | Done |
| Linear regression | Hour, weekday and indoor temperature | Done |
| SARIMAX | Seasonal autoregressive integrated moving average with exogenous inputs: daily and weekly cycles with weather and calendar inputs | Planned |
| LightGBM | Light Gradient Boosting Machine: non-linear effects, many features, handles missing values | Planned |

### 4.2 Test design

Subteam D split the NW HVAC series chronologically, without shuffling (logbook entry 17/10):

- **Train:** 1 June 2020 – 30 June 2022 (18,240 rows).
- **Validation:** 1 July – 31 December 2022 (4,417 rows).
- **Test:** 2023 + 2025 (2,758 rows, not yet used).

One function returns MAE, RMSE, CV(RMSE) and NMBE with the ASHRAE targets.

### 4.3 Baseline results

**Table 16 – Baselines on NW HVAC (validation period)**

| Model | MAE | RMSE | CV(RMSE) | NMBE | ASHRAE 14 |
|---|---|---|---|---|---|
| Seasonal naive | 48.87 Wh | 102.25 Wh | 102.85 % | −8.75 % | Fails |
| Linear regression | 99.98 Wh | 120.33 Wh | 113.68 % | −2.02 % | Fails |

### 4.4 Interpretation and next steps

- Both baselines are far above the 30 % CV(RMSE) limit; they set the bar every later model must beat.
- Subteam D is blocked until subteam A delivers the feature table.
- For a day-ahead forecast only lags of 24 hours or more (`lag_24`, `lag_168`) are available; a 1-hour lag cannot be used.
- `temp_c` is indoor temperature; outdoor weather must come from an external source.
- The quality flags to use are Team B's specific flags and `usable_for_model`.

> **Phase 4 summary.** Evaluation framework, two baselines and a model plan are in place. Open: feature table, SARIMAX and LightGBM, baselines for all priority series.

---

## 5. Evaluation (plan)

Evaluation will decide which model is good enough for the building manager. In Sprints 3–4, subteams B and D will:

- compare the baseline, SARIMAX and LightGBM for each priority series, with ASHRAE pass/fail;
- analyse forecast errors by hour, season and zone, and list the largest errors as anomaly candidates;
- test results with and without flagged hours;
- explain the drivers with SHAP (SHapley Additive exPlanations);
- estimate the business value in kWh and euros.

**Status: not started.**

---

## 6. Deployment (plan)

Deployment will turn the results into material the client can use. In Sprint 4, subteams E and C will deliver:

- a dashboard with consumption, forecast vs actual and drivers per zone and load type;
- the 20-minute final presentation with 3–4 key visuals (rehearsal 26–28 November, presentation 30 November);
- a 2-minute video or one-page summary;
- the frozen DataPack v1.0 (code, data dictionary, logbook, this report, deck and dashboard) in the Moodle dropoff area by 14 December 2026.

**Status: not started.**
