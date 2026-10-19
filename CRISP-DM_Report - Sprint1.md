# CRISP-DM Report – CeDInt-SEF DataPack

**CeDInt-SEF: Smart Energy Forecasting**
Group 3 · *Tools for Big Data Analysis* · Universidad Politécnica de Madrid (UPM)
19 October 2026 · Prepared by Team E (Coordination & Communication)

---

## Contents

- [Summary](#summary)
- [1. Business Understanding](#1-business-understanding)
- [2. Data Understanding](#2-data-understanding)
- [3. Data Preparation](#3-data-preparation)
- [4. Modelling](#4-modelling)
- [5. Evaluation (plan)](#5-evaluation-plan)
- [6. Deployment (plan)](#6-deployment-plan)

---

## Summary

**Goal.** Group 3 acts as a consulting team for the CeDInt smart building (UPM Montegancedo). It builds a **day-ahead hourly forecast of electrical energy** for every zone and load type of floor 1, explains what drives consumption, and documents every step. The work follows **CRISP-DM** in two-week **Scrum** sprints.

**Status after Sprint 1 (1–14 October 2026).**

| Phase | Status |
|---|---|
| 1. Business Understanding | Complete |
| 2. Data Understanding | Complete |
| 3. Data Preparation | Clean dataset v0.3 complete; feature table in Sprint 2 |
| 4. Modelling | Started: evaluation framework and two baselines |
| 5. Evaluation | Planned (Sprints 3–4) |
| 6. Deployment | Planned (Sprint 4 – 14 December) |

**Key findings.**

1. **Most counter "resets" are not resets.** They are *partial sums*: some devices are missing from the total for a moment. Only 1,330 hours are real resets.
2. **The data has two periods.** Hourly data from April 2020 to February 2023, then 902 days without data, then minute data from August to October 2025. Timestamps are in UTC.
3. **The clean dataset is ready.** Dataset v0.3 has 470,680 rows and a model-ready target in 86 % of them. Nothing was deleted; every problem is flagged.
4. **Zone matters most.** Consumption differs more between zones than between hours or weekdays. Lighting in SE and SW follows the working day; 2020 behaves differently from 2021–22 (COVID).
5. **The first baselines fail.** On NW HVAC both baselines are far above the ASHRAE limit (CV(RMSE) 102.85 % and 113.68 % vs ≤ 30 %). This is the bar the real models must beat.

**Main open issues.** The feature table (Sprint 2) blocks advanced modelling; subteam C's presence test and environment analysis are pending; the teacher must confirm the time zone, the column meanings and the forecast target.

---

## 1. Business Understanding

### 1.1 Background and objectives

CeDInt is a smart building on the UPM Montegancedo campus. Since 2020, IoT devices have measured electricity per circuit and indoor conditions (temperature, humidity, light, presence). Today the building is only monitored: managers cannot anticipate demand or detect abnormal consumption before energy is spent.

The Business Case sets five objectives:

1. accurate energy-forecasting models;
2. data-driven decisions taken before energy is used;
3. identification of savings through abnormal patterns and peak hours;
4. an established methodology (CRISP-DM in Agile sprints);
5. documented, reproducible and auditable work.

### 1.2 Stakeholders

**Table 1 – Stakeholders**

| Stakeholder | Needs | We deliver |
|---|---|---|
| UPM / project sponsor | Credible evidence and clear metrics | Forecasts tested on unseen data against ASHRAE Guideline 14; this report and the logbook |
| Energy / building analyst | Understand past and future consumption | Profiles by zone, load type and time; driver analysis; clean dataset |
| Building manager | Day-ahead forecasts per zone and load type | Forecasts, reliability indicators, driver explanations, dashboard |
| Facilities technician | Know which meters or sensors are faulty | List of sensor and meter problems; anomaly candidates |

### 1.3 Scope and constraints

- **In scope:** floor 1 (zones NE, NW, SE, SW), electrical energy by load type, day-ahead horizon.
- **Out of scope:** sensor installation, automatic HVAC control, floors 2–3, thermal energy.
- **Constraints:** raw files are never edited; CeDInt data is confidential (GDPR), processed locally and never committed to GitHub; fixed dates (presentation 30 November, Moodle release 14 December 2026).
- **Chosen approach:** a custom open-source Python framework run locally (no licence cost, full transparency), instead of doing nothing or buying a commercial platform.
- **Tools:** Python in Jupyter Notebook; code in GitHub (TBDA-Classes/2026G3); documents in Microsoft Teams; coordination in WhatsApp.

**Table 2 – Main risks**

| Risk | Mitigation |
|---|---|
| Poor data quality (missing values, counter problems, reversed meter) | Hypothesis-based cleaning rules with flags; nothing deleted |
| Short, broken history (902-day gap) | Treat the two periods separately; report seasonal limits |
| Wrong time zone | Treat timestamps as UTC, add Madrid local time; teacher to confirm |
| Overfitting | Chronological splits only |
| Bottlenecks between subteams | Baselines on a sample from Sprint 1; weekly check-ins |

### 1.4 Data-mining goals and success criteria

- **Target:** `energy_wh_model`, active energy used in each hour (Wh).
- **Unit:** each zone × load type, plus the floor-1 total. **Horizon:** next 24 hours.
- **Explanation:** which drivers matter for each load type (temperature, light, occupancy, calendar, outdoor weather).

**Table 3 – Energy types in scope**

| Energy type | Decision | Priority |
|---|---|---|
| HVAC (NE, NW, SE) | Core – largest, weather-dependent load | High |
| Lighting (NW, SE, SW) | Core – driven by occupancy and daylight | High |
| Plugs & Sockets (all zones) | Core – present in every zone, tied to occupancy | High |
| Floor-1 total | Core – one figure for the manager | High |
| Emerg. Lighting, Hand Dryer, RACK | Secondary – constant or event-driven | Low |
| SE Projector, apparent energy | Out of scope – all zeros / not the target | – |

**Success criterion.** A model must beat the seasonal-naive baseline and meet **ASHRAE Guideline 14** for hourly models on data never used in training: **CV(RMSE) ≤ 30 %** and **NMBE within ±10 %**. MAE and RMSE are reported too.

$$\mathrm{CV(RMSE)} = \frac{\sqrt{\frac{1}{n}\sum_{i}(y_i-\hat{y}_i)^2}}{\bar{y}} \times 100\,\% \qquad \mathrm{NMBE} = \frac{\sum_{i}(y_i-\hat{y}_i)}{n\,\bar{y}} \times 100\,\%$$

### 1.5 Project plan and team

| Sprint | Dates (2026) | Focus |
|---|---|---|
| 1 | 1–14 Oct | Phases 1–3, clean data, first baselines |
| 2 | 15–28 Oct | Feature table, drivers, first models |
| 3 | 29 Oct – 11 Nov | Models, explanations, dashboard prototype |
| 4 | 12–25 Nov | Evaluation, final deck |
| – | 26–28 Nov / 30 Nov | Rehearsal / final presentation |
| Post | 1–14 Dec | Feedback and Moodle release |

**Table 4 – Team (11 members)**

| Subteam | People | Responsibility |
|---|---|---|
| A – Data Engineering | 3 | Loading, hourly dataset, feature table, weather and calendar data |
| B – Data Quality & Validation | 3 | Cleaning rules, flags, consistency checks, model validation |
| C – Exploration & Environment | 2 | Consumption profiles, drivers, environment vs energy |
| D – Modelling & Forecasting | 1 | Baselines, SARIMAX, LightGBM, evaluation |
| E – Coordination & Communication | 2 | Repository, this report, backlog, slides, dashboard, final deck |

A quality-assurance role owns the Experiment Logbook. The teacher is the project owner.

---

## 2. Data Understanding

### 2.1 The data

The DataPack has four Excel files, one per zone (`Storey1_<zone>_report_by_device.xlsx`). Each sheet is one load type in one zone, summed over its devices.

**Table 5 – Raw data**

| Zone | Load types | Rows | Environmental data |
|---|---|---|---|
| NE | HVAC, Plugs & Sockets | 175,545 | None |
| NW | Emerg. Lighting, HVAC, Hand Dryer, Lighting, Plugs & Sockets, RACK | 525,622 | Yes |
| SE | Emerg. Lighting, HVAC, Lighting, Plugs & Sockets, Projector | 345,294 | Yes |
| SW | Emerg. Lighting, Hand Dryer, Lighting, Plugs & Sockets, RACK | 288,684 | Yes |
| **Total** | **18 sheets** | **1,335,145** | |

**Columns (verified on the data):** Timestamp (UTC), W = active power, Pa = apparent power, I = current, **Er = active-energy counter (Wh)**, Ea = apparent-energy counter, number of devices, Lum = light (lux), Hum = humidity (%), Temp = indoor temperature (°C), **Pres = presence (0/1), not pressure**. Er and Ea differ from the labels on the course slides (open question for the teacher).

### 2.2 Exploration

**Data structure**

- **Two periods:** hourly from 2 April 2020 to 28 February 2023, then **902 days without data**, then one row per minute from 18 August to 13 October 2025.
- **Gaps** of up to 37 days inside the hourly period.
- **Timestamps are UTC:** no daylight-saving jump, and light follows UTC daylight.
- **Environment is zone-level:** identical on all sheets of a zone.

**Indoor conditions**

- Mean temperature: NW 22.2 °C, SE 20.9 °C, SW 20.3 °C. Real extremes: 3.8–5.4 °C after Storm Filomena (13 January 2021) and 42.2 °C in NW during the August 2021 heatwave.
- Humidity is almost constant (about 30–32 %), so it adds little as a model input.
- Presence follows the working day clearly only in SW.

**Consumption profiles (subteam C)**

Subteam C profiled HVAC, Lighting and Plugs & Sockets in every zone on dataset v0.3, in local time and only on usable rows: by hour, weekday and month, working days vs weekends, August vs other months, and 2020 vs 2021–22 vs 2025 (same August–October weeks). The notebook contains 48 labelled and interpreted plots.

**Table 6 – Main consumption patterns**

| Load type | Main pattern |
|---|---|
| HVAC | NW highest, SE medium, NE almost zero. Daily peak in the late morning. Little difference between working days and weekends. NW highest in summer (July–August). |
| Lighting | SE and SW follow the working day and almost stop at weekends and in August. NW is highest at night and lowest in daylight hours – a different operating pattern to investigate. |
| Plugs & Sockets | NW far above the other zones, with a working-day peak, lower at weekends and in August, and high in winter months. NE, SE and SW are flat. |

**What this means for modelling**

- **Zone is the strongest effect**, so each zone × load type needs its own model or a zone feature.
- **Hour, day type, month and August** are relevant features; the weekday effect is strong for lighting and weak for HVAC.
- **2020 differs from 2021–22**: in the same weeks NW HVAC was about twice as high and SE/SW lighting much lower, so 2020 gets a COVID flag.

### 2.3 Data quality problems

**Table 7 – Data quality problems**

| # | Problem | Consequence |
|---|---|---|
| Q1 | Missing values stored as 0 (Temp and Hum = 0 together) | 0 °C would be read as a real value |
| Q2 | Two periods and a 902-day hole | Few seasons to learn from |
| Q3 | Gaps of 1–37 days | Lags break at gaps |
| Q4 | Counter drops – mostly partial sums, only 1,330 real resets | Naive differences give huge negative energy |
| Q5 | NW Emerg. Lighting negative 99 % of the time (reversed clamp); small negatives elsewhere | Wrong sign or noise |
| Q6 | SE Projector all zeros; SW RACK ends 3 December 2021 | Nothing to forecast |
| Q7 | SW sensor fault 1–7 March 2022 (up to 1,411 °C) | Distorts averages |
| Q8 | No environmental data in NE | NE needs NW values or outdoor weather |
| Q9 | Column labels differ from the slides | Risk of the wrong target |
| Q10 | Timestamps in UTC | Local time needed for calendar features |
| Q11 | Incomplete sums in 2025 minute data (complete minutes: NE 94 %, NW 87 %, SE 56 %, SW 43 %) | SW 2025 not usable |

### 2.4 Hypotheses

**Table 8 – Hypotheses and results**

| # | Hypothesis | Result |
|---|---|---|
| H1 | Pres is occupancy | Partly supported (0/1 only; clear pattern in SW only); subteam C test pending |
| H2 | Temp = Hum = 0 means missing | Confirmed |
| H3 | Lum = 0 is partly darkness, partly missing | Confirmed; Lum = 0 at 10–16 h UTC is flagged |
| H4 | Counter drops are resets | Mostly rejected (27,742 partial-sum hours vs 1,330 real resets) |
| H5 | Mostly negative power = reversed clamp | Confirmed for NW Emerg. Lighting only |
| H6 | Small negatives near 0 are noise | Confirmed |
| H7 | 2025 and 2020–23 describe the same system | Partly (9 of 15 series at a similar level) |
| H8 | Environment is zone-level | Confirmed |
| H9 | Dead series carry no information | Confirmed (SE Projector, SW RACK after 2021) |
| H10 | NE has no environmental sensors | Confirmed |
| H11 | 2020 is abnormal (COVID) | Supported by subteam C's period comparison |
| H12 | Holidays and August lower consumption | Partly: August lower for lighting and NW plugs, higher for NW HVAC; holidays in Sprint 2 |
| H13 | Timestamps are UTC | Confirmed by the data; teacher to confirm |

---

## 3. Data Preparation

### 3.1 Selection

Each series is rated per period: **Use** (≥ 80 % valid hours and power–energy agreement), **Use with caution** (≥ 60 %) or **Do not use**.

**Table 9 – Rating per series**

| Period | Use | Use with caution | Do not use |
|---|---|---|---|
| 2020–23 | 11 series | 6 (NW Hand Dryer and all SW series) | SE Projector |
| 2025 | 8 series | 3 (NE HVAC, NW Emerg. Lighting, NW Plugs & Sockets) | 6 (all SW, NW Hand Dryer, SE Projector) |

Decisions: keep every row and flag problems; model only rows with `usable_for_model = 1`; exclude SE Projector; never interpolate across the 902-day gap; use NW or outdoor weather for NE.

### 3.2 Cleaning pipelines

**Table 10 – Data versions**

| Version | Made by | Content | Status |
|---|---|---|---|
| v0.1 | Subteam B | Pilot cleaning rules on the SW file | Done |
| v0.2 | Subteam A (`Task_A1_A5.ipynb`) | Hourly table, 450,482 × 17; flagged 82,423 hours as resets (too many) | Replaced |
| v0.3 | Team B (`clean_cedint.py`) | 470,680 × 50, ratings and 16 quality flags | **Current** |
| v1.0 | Sprint 4 | v0.3 + features, frozen for final models and Moodle | Planned |

**Main cleaning steps in v0.3** (raw values kept; every problem flagged):

1. Flip the sign of the reversed meter (NW Emerg. Lighting).
2. Label each counter reading as ok, zero record, partial sum, spike or real reset.
3. Remove zero records and partial sums from power; set small negatives (−5…0 W) to 0.
4. Set missing or impossible environmental values to empty (Temp = Hum = 0, Temp outside 0–50 °C).
5. Build a complete hourly grid; 2025 minutes are averaged over complete minutes only.
6. Compute hourly energy from the counter, never across a real reset.
7. Build the target `energy_wh_model`: counter energy, else power × 1 h, else interpolation for gaps of up to 3 hours.
8. Rate every series and add Madrid local time (`timestamp_local`).

**Table 11 – Main cleaning results (hours affected)**

| Problem | Rule | Hours |
|---|---|---|
| Partial sum | Power and energy empty | 27,742 |
| Zero record | Power and energy empty | 21,987 |
| Real counter reset | New counter segment | 1,330 |
| Negative power −5…0 W | Set to 0 | 33,615 |
| Missing hour | Row added and flagged | 20,198 |
| SW temperature fault | Empty | 140 |

### 3.3 Validation of the clean data

- **86 %** of rows (404,254) have a model-ready target; 94.5 % of target values come directly from the energy counter.
- **Power vs energy** agree within 20 % in at least 95 % of hours for 14 of 17 series (2020–23).
- **2025 vs 2021–22:** 9 of 15 series have a similar level in the same weeks; NW HVAC, NW Lighting, SE Lighting and the SW series changed. 2025 is therefore a valid test period only for stable series rated Use.

The full data dictionary (38 columns) is in `CeDInt_F1_quality_and_anomalies.xlsx`.

**Planned for Sprint 2 (subteam A):** feature table with hour, weekday, month, holiday, August and COVID flags, lags of 24 h and 168 h, outdoor weather from Open-Meteo and the Madrid holiday calendar.

---

## 4. Modelling

### 4.1 Model plan

**Table 12 – Model plan**

| Model | Why | Status |
|---|---|---|
| Seasonal naive (same hour one week earlier) | Minimum bar | Done |
| Linear regression (hour, weekday, indoor temperature) | Simple benchmark | Done |
| SARIMAX | Daily and weekly cycles with weather and calendar inputs | Sprint 2 |
| LightGBM | Non-linear effects, many features | Sprint 3 |

### 4.2 Test design

Chronological split for NW HVAC (no shuffling): **train** June 2020 – June 2022, **validation** July – December 2022, **test** 2023 and 2025. One function computes MAE, RMSE, CV(RMSE) and NMBE.

### 4.3 Baseline results

**Table 13 – Baselines on NW HVAC (validation period)**

| Model | MAE | RMSE | CV(RMSE) | NMBE | ASHRAE 14 |
|---|---|---|---|---|---|
| Seasonal naive | 48.87 Wh | 102.25 Wh | 102.85 % | −8.75 % | Fails |
| Linear regression | 99.98 Wh | 120.33 Wh | 113.68 % | −2.02 % | Fails |

**Lessons for Sprint 2**

- **NW HVAC is hard to forecast:** it switches between standby (about 34 Wh) and operation (170–480 Wh), and its level changes between quarters. Steadier series (Lighting, Plugs & Sockets, floor total) should also be tested.
- **No 1-hour lag** in a day-ahead forecast: only lags of 24 h or more are valid.
- **Same hours for every model:** the two baselines were scored on different hours (3,514 vs 3,859).
- **Outdoor temperature is needed:** `temp_c` is indoor temperature.
- Subteam D is **blocked** until subteam A delivers the feature table.

---

## 5. Evaluation (plan)

In Sprints 3–4, subteams B and D will:

- compare baseline, SARIMAX and LightGBM per priority series, with ASHRAE pass/fail;
- analyse errors by hour, season and zone, and list the largest errors as anomaly candidates;
- test results with and without flagged hours;
- explain the drivers with SHAP;
- estimate the business value in kWh and euros.

## 6. Deployment (plan)

In Sprint 4, subteams E and C will deliver:

- a dashboard with consumption, forecast vs actual and drivers per zone and load type;
- the 20-minute final presentation (rehearsal 26–28 November, presentation 30 November);
- a 2-minute video or one-page summary;
- the frozen DataPack v1.0 (code, dictionary, logbook, this report, deck, dashboard) in Moodle by 14 December 2026.
