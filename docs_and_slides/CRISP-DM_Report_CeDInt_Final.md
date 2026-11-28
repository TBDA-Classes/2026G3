# CRISP-DM Report – CeDInt-SEF Smart Energy Forecasting

Group 3 · *Tools for Big Data Analysis* · Universidad Politécnica de Madrid (UPM) · Status: 28 November 2026 (end of Sprint 4)

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

Group 3 acts as a consulting team for CeDInt, a smart building on the UPM Montegancedo campus. The goal is a **day-ahead (next 24 hours) hourly forecast of electrical energy** for every zone and load type of floor 1, explained by its drivers and documented so that every step can be audited and reproduced. The work follows the Cross-Industry Standard Process for Data Mining (CRISP-DM), organised in two-week Scrum sprints. This report covers Sprints 1–4, the response to the mid-term feedback and the leak-free audit of the forecasts; it is frozen in DataPack v1.0 (Moodle, by 14 December 2026).

**Table 1 – Phase status on 28 November 2026**

| Phase | Status |
|---|---|
| 1. Business Understanding | Complete |
| 2. Data Understanding | Complete (all zones, indoor drivers, outdoor weather, secondary loads) |
| 3. Data Preparation | Complete: clean dataset v0.4 and model-ready training data; frozen v1.0 in the DataPack release |
| 4. Modelling | Complete: day-ahead forecasts from six model families, a hybrid Chronos + GBM with learned weights, a reconciled floor-total forecast and multi-day forecasts. Leakage found in the GBM (section 4.6) was corrected for the GBM and the hybrid (section 4.8) |
| 5. Evaluation | Complete: final model choice re-run after the leak correction, skill scores, targets per load type, results from hour to day and from series to floor, error analysis, anomalies, flag sensitivity, bias check and SHAP. Random Forest and CatBoost were not retrained (section 5.9) |
| 6. Deployment | Complete: dashboard, final deck and one-page summary; DataPack v1.0 is uploaded to Moodle by 14 December 2026 |

**Key findings**

1. **Most counter drops are not resets.** They are *partial sums*: some devices are missing from the total for a moment. Only 1,330 hours are real meter resets.
2. **The data has two periods.** Hourly data from 2020 to 2023 and minute data in 2025 are separated by 902 days without data. Timestamps are in Coordinated Universal Time (UTC).
3. **Zone is the strongest effect on consumption.** NW uses the most energy per device; NW HVAC follows cooling demand and SE HVAC follows heating demand.
4. **Clear skill over the naive benchmark.** After the leak-free audit, the model per series chosen on 16 October – 31 December 2022 (Chronos for 10 series, the leak-free hybrid for 2, Random Forest without 2020 for 1 and CatBoost for 1) has positive skill in all 39 series-period combinations, with a median skill of 0.27 on validation, 0.30 on test 2023 and 0.20 on test 2025 (0.27 means a 27 % lower RMSE than the naive forecast). Before the audit the figures were 37 of 39 and 0.31, 0.30 and 0.19.
5. **The targets per load type are met for part of the series:** 7 of 14 series on validation, 8 of 14 on test 2023 and 6 of 11 on test 2025 (lighting is judged per day and is not counted). The floor-1 total improves from 45.2 % (seasonal naive) to 37.4 % with MinT reconciliation on test 2023.
6. **Several large errors come from the meters, not the models.** Removing flagged hours lowers NE HVAC on test 2023 from 691.6 % to 13.2 % and on validation from 239.5 % to 15.8 %.
7. **Some errors are systematic.** Eight series-period cases have a bias above ±10 %; a simple 7-day level update fixes six of them, which points to level shifts in building use and to the value of updating the models regularly.
8. **Our self-audit found and corrected leakage in the GBM.** Its 24-hour rolling mean included the hour being forecast, and GBM, Random Forest and CatBoost use indoor readings of the same hour, which are not known a day ahead (NW HVAC test 2023: 29.6 % → 49.6 % when fixed). The corrected GBM is chosen for no series, the corrected hybrid still wins 2; Random Forest and CatBoost were not retrained.
9. **A 2–3 day outlook is possible.** A GBM per horizon still beats the seasonal naive at 7 days in 17 of 18 cases, with measured weather used as a perfect forecast (an upper bound).
10. **The mid-term feedback was addressed.** Models are compared by family rather than as one winner, Chronos and GBM are combined in a hybrid, the question why a later test can score better is answered, and every weakness comes with an improvement (section 1.7).

**Known limitations.** The test periods are short (January–February 2023 and August–October 2025) and SW has no 2025 data. The teacher must confirm the time zone and the column meanings. The leak correction is partial (Random Forest and CatBoost were not retrained), and the savings in euros are not quantified; both are on the roadmap (section 6.4).

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
| Bottlenecks between tasks | Baselines on a sample from Sprint 1; weekly check-ins |

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

Following the professor's guidance at the mid-term review, models are judged on data never used in training in three ways:

1. **Skill over the naive benchmark (main measure):** skill = 1 − RMSE<sub>model</sub> / RMSE<sub>naive</sub>. A model is useful when its skill is above 0; a skill of 0.27 means a 27 % lower root-mean-square error (RMSE) than the naive forecast.
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
| Sprint 3 | 29 October – 11 November | Training data, forecasts, error analysis, anomalies, dashboard prototype | Done |
| Sprint 4 | 12–25 November | Evaluation, explanation, multi-day forecasts, final deck | Done |
| Rehearsal | 26–28 November | Speaker split and practice | Running |
| Final presentation | 30 November | 20 minutes + 20 minutes discussion | – |
| Release | by 14 December | Feedback processed; DataPack in the Moodle dropoff area | – |

**Table 7 – Team (10 members) and types of work**

| Type of work | Covers |
|---|---|
| Data Engineering | Loading, hourly dataset, calendar features, spatial structure, weather data |
| Data Quality & Validation | Cleaning rules, flags, training data, evaluation toolkit, model validation |
| Exploration & Environment | Consumption profiles, drivers, environment and weather vs energy |
| Modelling & Forecasting | Baselines, forecasting models, explanation |
| Coordination & Communication | Repository, CRISP-DM report, backlog, logbook, dashboard, slides, final deck |

The team of 10 works in Scrum without fixed subteams: every backlog item has one named owner and a deliverable, and the work is linked through the shared GitHub repository and agreed file formats (one clean dataset and one forecast format). The types of work above are the categories of the Product Backlog. The Product Backlog has 44 items and is updated every sprint; at the mid-term review (16 November 2026), 34 were complete, 6 in progress and 4 not started.
A quality-assurance role owns the Experiment Logbook (`EXPERIMENT_LOGBOOK.md`), and the course teacher is the project owner. The team works in Python (and R for the day-ahead and floor-total models); code is kept in the GitHub repository `TBDA-Classes/2026G3` and documents in Microsoft Teams.

### 1.7 Feedback from the mid-term review and how it was addressed

At the mid-term review (16 November 2026) the professor, acting as the customer, raised three questions and gave four tips. The project's answers are summarised below and detailed in the sections listed.

**Table 8 – Mid-term feedback and response**

| Feedback | Response | Section |
|---|---|---|
| Chronos uses only the history of consumption, while Random Forest and gradient boosting also use weather, occupancy and calendar: ranking them is comparing apples and pears | Models are grouped by family (what each can see and cannot do), and the report shows where each family is chosen instead of one overall winner | 4.2, 5.2 |
| If Chronos is good at the pattern and the other models at the drivers, why not combine them, for example in a hybrid or a multivariate LSTM or CNN? | A hybrid Chronos + GBM with weights learned per series was built; after the GBM leak correction it still beats both parents in 2 of the 10 series it covers and is chosen for NE Plugs & Sockets and NW Lighting. An LSTM or CNN was not built: with two periods separated by a 902-day gap and about two years of training data per series it would overfit easily; GBM and Random Forest already combine lagged history and drivers; Chronos-2, which reads weather and calendar natively, is the next experiment | 4.5, 4.8, 6.4 |
| Why can a forecast further in the future score better than one closer in time? | Two cases are explained: test 2025 (three years after training) scores better than test 2023 because the period is easier, so the skill against the naive forecast actually falls; and SE HVAC is better at 2–3 days than at 1 day because the 1-day model copies yesterday's spikes | 5.7, 4.7 |
| Tip 1 – create value and close the loop | Every result is linked to a decision (forecast → decision → result → better forecast), and every weakness comes with an improvement | 5.10, 6.2 |
| Tip 2 – prepare for the customer's questions | The questions above, plus how often to update the model, what happens when a meter fails and how much can be saved, have prepared answers | 5.6, 5.7, 6.2 |
| Tip 3 – the advantage must come from the way of thinking | The report states why each approach was chosen, what each model family can and cannot do, what the results mean and what comes next, including a self-audit that found and corrected leakage | 4.2, 4.6, 4.8, 6.4 |
| Tip 4 – forecasting further ahead creates more value | Multi-day forecasts (1–7 days) show how accuracy decays with the horizon and where the forecast is still useful | 4.7 |

> **Phase 1 summary.** Objectives, stakeholders, scope, constraints, risks and measurable success criteria (skill over the naive benchmark and targets per load type) are defined, and the mid-term feedback is answered. The scope of hourly forecasting is now fixed: HVAC, Lighting and Plugs & Sockets as targets, constant loads as a control group, hand dryers as daily totals.

---

## 2. Data Understanding

The data covers five and a half years of floor 1, but it is usable only after resolving missing values stored as zero, counter drops, a reversed meter and a 902-day gap between two sampling periods.

### 2.1 The data

The DataPack consists of four Excel files, `Storey1_<zone>_report_by_device.xlsx`, one per zone. Each sheet holds one load type in one zone, already summed over its devices.

**Table 9 – Raw data per zone**

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

### 2.3 Consumption profiles (notebook P7)

The team profiled HVAC, Lighting and Plugs & Sockets in every zone on dataset v0.3, in local time and only on rows with `usable_for_model = 1`: by hour, weekday and month, working days vs weekends, August vs other months, and 2020 vs 2021–22 vs 2025 on the same August–October weeks. The notebook contains 48 labelled and interpreted plots (logbook entry 5).

**Table 10 – Main consumption patterns**

| Load type | Main pattern |
|---|---|
| HVAC | NW highest, SE intermediate, NE very low; daily peak in the late morning; little difference between working days and weekends; NW highest in summer (July–August) |
| Lighting | SE and SW follow the working day and almost stop at weekends and in August; NW is highest at night and lowest in daylight hours |
| Plugs & Sockets | NW far above the other zones, with a daytime peak, lower at weekends and in August and high in winter months; NE, SE and SW lower and stable |

In the same August–October weeks, 2020 differs from 2021–22 (NW HVAC higher, SE and SW lighting lower), so **2020 is treated as a COVID-affected year**.

### 2.4 Spatial structure and comparison between zones (F3.1, F3.2)

- **Spatial structure (logbook entry 8):** all 18 series are organised in one long table keyed by timestamp, building, floor, zone code (`1NE`, `1NW`, `1SE`, `1SW`) and load type, with the zone-level environmental values aligned per zone. This allows direct aggregation by zone and load type.
- **Consumption per device (logbook entry 9):** energy was normalised by the number of installed devices, so that a larger zone is not mistaken for an inefficient one. **NW has the highest consumption per device** for Plugs & Sockets, Lighting and HVAC, with the clearest difference for Plugs & Sockets. SE Projector is always zero and was left out.

### 2.5 Environment, occupancy and outdoor weather vs energy

**Indoor drivers, NW zone (notebook P8, logbook entry 6).**

**Table 11 – Environment and occupancy vs energy (NW zone, 2021–22)**

| Analysis | Result |
|---|---|
| Light vs lighting energy | Correlation −0.372 (17,113 hours): more daylight, less lighting |
| Occupancy vs lighting | Within the same time of day, slightly higher with presence (day 0.069 vs 0.072 kWh; night 0.274 vs 0.304 kWh) |
| Occupancy vs Plugs & Sockets | About 4.8 % higher with presence (1.248 vs 1.308 kWh) |
| Indoor temperature vs HVAC | Weak linear correlation (+0.174) but a non-linear pattern: highest HVAC use at 22–24 °C |
| Humidity vs HVAC | Very weak (+0.059); 89 % of readings are 30–31 % |
| Presence by hour | 29.5 % of hours at 02:00, 67 % at 14:00; some presence also detected at night |

**Relation matrix for all zones with sensors (F5.2, logbook entry 10).** The team computed Pearson, Spearman and partial correlations that remove the effect of the hour of day, and kept relationships with |r| ≥ 0.20. NE was left out because it has no sensors.

**Table 12 – Strongest driver relationships after removing the hour of day (F5.2)**

| Zone | Relationship | Partial correlation |
|---|---|---|
| NW | Indoor temperature – Plugs & Sockets | −0.457 |
| SE | Indoor temperature – Emergency Lighting | +0.798 |
| SW | Occupancy – Lighting | +0.297 (about 350 W with presence vs 44 W without) |
| SE | Light – Lighting | +0.275 |

After the sign correction of NW Emergency Lighting, the team repeated the calculation for that series (`P7_and_F5_2_data_quality_validation.ipynb`): no negative values remain, the partial correlation with indoor temperature stays at about −0.23, and the conclusions of F5.2 are unchanged. Humidity varies very little and adds little information.

**Outdoor weather (F5.3, notebook P9, logbook entry 11).** Outdoor temperature from Open-Meteo was compared with HVAC energy, using heating and cooling degree-hours and lags of 0 to 6 hours.

- **NW HVAC is cooling-driven:** correlation with cooling degree-hours r = +0.312; average HVAC energy rises from about 97 Wh to 217 Wh with cooling demand; the relationship is strongest without delay (lag 0).
- **SE HVAC is heating-driven:** Spearman correlation with heating degree-hours +0.362; the correlation with outdoor temperature becomes stronger with the lag (from −0.124 to −0.248).
- UTC weather timestamps had to be converted to Madrid time to avoid shifts in the lag calculations.

**Limitations:** relationships are non-linear and interact (occupancy with the hour, temperature with HVAC operation); correlations do not show cause and effect; indoor temperature is itself influenced by the HVAC system.

### 2.6 Secondary loads (F2.2)

The team characterised the secondary loads on the hourly period (`secondary_loads.py`, `TeamB_F2.2_secondary_loads.xlsx`).

**Table 13 – Secondary loads (2020–23, usable hours)**

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

**Table 14 – Data quality problems**

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

**Table 15 – Hypotheses and results**

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

**Table 16 – Rating per series and period**

| Period | Use | Use with caution | Do not use |
|---|---|---|---|
| 2020–23 (hourly) | 11 series | 6 (NW Hand Dryer and all SW series) | SE Projector |
| 2025 (minute → hourly) | 8 series | 3 (NE HVAC, NW Emerg. Lighting, NW Plugs & Sockets) | 6 (SW Emerg. Lighting, Hand Dryer, Lighting, Plugs & Sockets; NW Hand Dryer; SE Projector); SW RACK has no 2025 data |

**Decisions:** keep every row and flag problems; model only usable rows; exclude SE Projector; never interpolate or compute lags across the 902-day gap.

### 3.2 Data versions

**Table 17 – Data versions**

| Version | Made with | Content | Status |
|---|---|---|---|
| v0.1 | Pilot rules (logbook entry 2) | Pilot cleaning rules on the SW file: Temp/Hum = 0 → empty; Lum = 0 → empty between 07:00 and 19:00; Pres = 0 → empty if Temp present | Replaced |
| v0.2 | `Task_A1_A5.ipynb` (logbook entry 1) | 18 sheets read, renamed and sorted; hourly resampling; energy from the counter; one long table `cedint_f1_hourly.csv` of 450,482 rows × 17 columns; 82,423 hours flagged as resets (far too many) | Replaced |
| v0.3 | `clean_cedint.py` (logbook entry 3) | `cedint_f1_hourly_clean.csv.gz`: 470,680 rows × 50 columns, series ratings and 16 quality flags | Replaced |
| v0.4 | `clean_cedint.py` | v0.3 plus calendar flags and current checks: 470,680 rows × 55 columns | **Current** |
| Model-ready | `T32_make_training_data.py` (logbook entry 13) | `cedint_f1_model_ready.csv.gz`: built from v0.4, with split, scope, training and scoring columns, calendar and sensor features and lags | **Current** |
| v1.0 | Release | Frozen dataset for the final models and Moodle | By 14 December 2026 |

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

**Table 18 – Main cleaning results (series-hours)**

| Problem | Rule | Hours |
|---|---|---|
| Partial sum | Power and energy set to empty | 27,742 |
| Zero record | Power and energy set to empty | 21,987 |
| Real counter reset | New counter segment; no energy across it | 1,330 |
| Small negative power (−5…0 W) | Set to 0 | 33,615 |
| Missing hour | Row added and flagged | 20,198 |

**Table 19 – Share of the 470,680 hourly rows with each quality flag**

| Flag | What it marks | Rows |
|---|---|---|
| Missing hour | No raw row for the hour; row added to complete the grid | 4.3 % |
| Zero record | All readings exactly 0: a missing record written as zeros | 4.7 % |
| Partial sum | Counter sums only part of the devices | 5.9 % |
| Counter spike | Counter jumps up and falls back | 1.1 % |
| Counter reset | Counter drops and stays low: a real reset | 0.3 % |
| Energy implausible | Energy < 0 or > 3 × the 99.5th percentile → empty | 1.3 % |
| Negative noise | Power between −5 and 0 W → set to 0 | 7.1 % |
| Negative large | Power below −5 W → empty | 0.5 % |
| Low coverage | 2025: fewer than 10 complete minutes in the hour → empty | 1.1 % |
| Power spike | Power far from its 25-hour rolling median (kept) | 0.6 % |
| Power–energy mismatch | Energy and power × 1 h differ by more than 20 % (kept) | 5.3 % |
| Environment missing | Indoor temperature = humidity = 0 (includes NE, which has no sensors) | 14.6 % |
| Temperature impossible | Outside 0–50 °C → empty | 0.1 % |
| Temperature extreme | Below 10 °C or above 35 °C but possible (kept) | 1.9 % |
| Humidity invalid | Outside 5–95 % → empty | < 0.1 % |
| Light zero by day | Light = 0 between 10:00 and 16:00 UTC (kept) | 1.3 % |

Source: final presentation, technical appendix A1 (shares computed from `cedint_f1_hourly_clean.csv.gz`).

**Calendar features (v0.4, F4.3).** All based on local time:

- `is_holiday` and `holiday_name`: national and Comunidad de Madrid public holidays, 2020–2025;
- `is_weekend`;
- `is_august_low_use`: the August low-use period;
- `flag_covid_2020`: the COVID-affected year.

The holiday and August flags were first produced by a separate script on the v0.2 table (`Task_F4_3C.py`, logbook entry 7) and are now part of the cleaning pipeline. Version 0.4 also checks the current readings, and its data dictionary has 42 entries.

**Outdoor weather (F5.3).** Hourly outdoor temperature (and, in some models, solar radiation) comes from the Open-Meteo archive for the CeDInt site and is joined on `timestamp_utc`. Heating and cooling degree-hours are derived from it. The archive holds observed weather, which the models use in place of a weather forecast.

### 3.4 Model-ready training data (T32)

The team built one model-ready file so that every model learns from and is scored on the same hours (logbook entry 13; `T32_TRAINING_DATA_METHODOLOGY.md`, `training_data_summary_T32_DATACLEANING.xlsx`). **No row is deleted:** three 0/1 columns say how an hour may be used, and `exclusion_reason` says why an hour is left out.

- `include_train` – the model may **learn** from this hour;
- `include_eval` – validation and test **scores** are computed on this hour;
- `include_train_no2020` – the experiment variant without 2020.

**Training is filtered more strictly than testing.** Leaving uncertain hours out of training helps the model learn normal behaviour; leaving them out of the test would make the score look better than it is.

**Table 20 – Agreed periods (UTC)**

| Split | Period | Used for |
|---|---|---|
| Train | 1 June 2020 – 30 June 2022 | Fitting the models |
| Validation | 1 July – 31 December 2022 | Choosing and tuning the model |
| Test 2023 | 1 January – 28 February 2023 | Unseen test 1 (winter) |
| Test 2025 | 18 August – 13 October 2025 | Unseen test 2 (late summer and autumn; NE, NW and SE only) |

**Table 21 – Exclusion rules**

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

> **Phase 3 summary.** Dataset v0.4 adds the calendar flags to the cleaned data, outdoor weather is available, and the model-ready file fixes the same training and scoring hours for every model. The frozen v1.0 is part of the DataPack release.

---

## 4. Modelling

Besides the two Sprint 1 baselines, the team built forecasts with six model families for the 14 series forecast per hour (ten priority series and four constant loads), including the naive benchmarks and the variants without 2020, and a hybrid Chronos + GBM with learned weights; after a leakage audit, the GBM and the hybrid were corrected and re-run (section 4.8). A fixed 50/50 Chronos + GBM blend and SARIMAX were also built but are not in the final evaluation, because they have no predictions file in the agreed format. The floor-1 total has its own forecast, and HVAC and the floor total were also forecast up to 7 days ahead.

### 4.1 Common rules

- **One prediction format** for every model: `timestamp_utc, zone, load_type, model, split, y_true, y_pred`.
- **Day-ahead rule (agreed):** the forecast for an hour may only use target values from at least 24 hours earlier (`lag_24`, `lag_168`, means of the previous day or week).
- **Selection on validation (agreed):** tuning and the choice between variants use the validation period only; the test periods are reported as unseen data.
- **Evaluation toolkit** (`team_b_eval.py`): checks every predictions file, computes MAE, RMSE, CV(RMSE), NMBE and ASHRAE pass/fail, and breaks the errors down.
- **Reference forecasts** (`make_reference_baseline.py`): same hour yesterday (`naive_day`) and same hour last week (`naive_week`).

### 4.2 Models

**Table 22 – Models built**

| Model | Description | Inputs | Logbook |
|---|---|---|---|
| Seasonal naive / naive day / naive week | Same hour one week earlier or one day earlier | Target only | 4, 19 |
| Linear regression | Sprint 1 baseline on NW HVAC | Hour, weekday, indoor temperature | 4 |
| SARIMAX | Seasonal autoregressive model with daily and weekly Fourier terms and outdoor temperature, degree-hours and calendar flags; first day-ahead run only (quick mode); not in the final evaluation (no predictions file in the agreed format) | Calendar, weather | 12 |
| LightGBM (T29) | Light Gradient Boosting Machine, one model per series; 6 configurations tried, early stopping on validation | Calendar flags, target lags of 24–336 h, mean of the previous day, same-hour mean of the last 7 days, indoor values lagged 24 h | 12, 19 |
| Random Forest | Two variants (with and without 2020), tuned on validation | Calendar, `lag_24h`, `lag_168h`, indoor sensors, outdoor temperature and solar radiation | 15 |
| CatBoost | Gradient boosting with categorical calendar features; two variants, tuned on validation | As Random Forest | 16 |
| Chronos (chronos-bolt-base) | Pretrained time-series foundation model; nothing is fitted on CeDInt data; forecasts each day at local midnight from the previous weeks; context length chosen on validation; also gives 10–90 % quantiles | Past energy only | 15 |
| GBM | Gradient Boosting Regressor (100 trees, depth 4), trained with 2020 | Calendar, indoor temperature and degree-hours, occupancy, light, `lag_24`, `lag_168`, 24-hour rolling mean | 17 |
| Chronos + GBM blend 50/50 | Simple average of the two forecasts; the first version joined GBM local time with Chronos UTC; not in the final evaluation (no predictions file in the agreed format) | GBM and Chronos forecasts | 17 |
| Hybrid Chronos + GBM (T39) | Linear stacker per series: ŷ = w₁ · Chronos + w₂ · GBM + b; weights fitted on 1 July – 15 October 2022, checked on 16 October – 31 December 2022, then refitted on the whole validation period and used once on the tests; GBM timestamps corrected to UTC first | GBM and Chronos forecasts | – |
| GBM per horizon (T37) | One GBM per horizon (1, 2, 3, 5 and 7 days), target information only up to 24 × d hours before; measured weather used as a perfect forecast | Calendar, past energy, outdoor weather; no indoor sensors | 21 |
| GBM, leak-free (audit) | Same settings as the GBM, retrained for its 10 series with the rolling mean ending 24 hours earlier, indoor variables lagged 24 hours and lags by time; timestamps in UTC | Calendar, past energy, lagged indoor sensors | – |
| Hybrid, leak-free (audit) | Same stacker and protocol as T39, built on the leak-free GBM | Leak-free GBM and Chronos forecasts | – |

The Random Forest and CatBoost scripts note that indoor sensor values of the same hour are not known when a day-ahead forecast is issued and that observed weather stands in for a weather forecast, so their scores can be slightly optimistic; both scripts include a `strict_day_ahead` mode to check this. The same applies to the GBM (section 4.6).

**Table 23 – Model families: what each can see and where it is chosen**

| Family | What it sees | What it cannot do | Where it is chosen (section 5.2) |
|---|---|---|---|
| Naive benchmark | Same hour yesterday (or last week) | Anything else | Never a candidate: the bar to beat |
| GBM, Random Forest, LightGBM, CatBoost (SARIMAX tested in T29) | Past consumption (lags of 24 h and 168 h) plus calendar, weather and sensors | Needs tomorrow's weather and sensor values as input; goes stale if not re-fitted | NE HVAC (Random Forest without 2020), NW Plugs & Sockets (CatBoost); the leak-free GBM is not chosen |
| Chronos-Bolt (foundation model) | Past consumption only | Use weather, occupancy or calendar | All four constant loads, NW and SE HVAC, SE and SW Lighting, SE and SW Plugs & Sockets |
| Hybrid Chronos + GBM (leak-free) | Both signals, weights learned per series | Inherits the input risks of the GBM; unconstrained weights can be unstable | NE Plugs & Sockets, NW Lighting |

No single family wins everywhere: each is chosen where its information matters. The multivariate models are not "drivers only": GBM and Random Forest also use past consumption through lags and rolling means.

### 4.3 Day-ahead LightGBM vs seasonal naive (T29)

The first run (logbook entry 12) compared seasonal naive, SARIMAX and LightGBM on validation: LightGBM was best in 9 of 10 series, and SARIMAX was weaker, especially on NW HVAC (105 % vs 67 % CV(RMSE)), because a linear model fits an on/off HVAC pattern poorly. The final version (`F1.2_T29_dayahead_models_MH_v2.Rmd`, logbook entry 19) keeps seasonal naive and LightGBM only.

- **LightGBM beats the seasonal naive in 26 of 28** series-period comparisons; it loses only for SE Lighting in 2023 and NW Lighting in 2025.
- **Most important inputs** (by gain): `lag_24`, the mean of the previous day and the same-hour mean of the last 7 days in almost every series; lagged light (`lum_lux_l24`) for NW and SE Lighting. The models mainly extend the recent past; calendar flags and indoor drivers add little.

### 4.4 Floor-1 total (T30)

`F1.3_T30_floor1_total_forecast_MH.R` (logbook entries 14 and 18) forecasts the floor-1 total with a hierarchy of 22 nodes (total, 4 zones, 4 load types and 13 zone × load series) and one LightGBM model per node with fixed settings. Six methods are compared on the same hours: seasonal naive, a direct model on the total, bottom-up (sum of the zone × load forecasts) and three reconciliation methods (OLS, WLS and MinT-shrink) that make the zone forecasts add up exactly to the total. Results are in section 5.3.

### 4.5 Hybrid Chronos + GBM with learned weights (T39)

Chronos reads only the history of a series, while the GBM also reads the drivers. Instead of the fixed 50/50 average, the hybrid (`hybrid_blend_learned_weights.ipynb`) learns per series how much to trust each forecast. Before blending, every `y_true` of both models is checked against `energy_wh_model` of the clean dataset; the GBM timestamps, stored as Madrid local time in the column `timestamp_utc`, are converted to UTC (0 rows matched at the labelled timestamp, 26,863 at −2 h and 19,353 at −1 h).

**Table 24 – Hybrid against its parents on 16 October – 31 December 2022, CV(RMSE) %**

| Series | Chronos | GBM | Blend 50/50 | Hybrid |
|---|---|---|---|---|
| NW Lighting | 65.4 | 84.8 | 64.4 | **64.3** |
| SE Lighting | 263.3 | 249.2 | 243.4 | **200.6** |
| SE Plugs & Sockets | 125.5 | 141.9 | 124.9 | **123.8** |

- The hybrid wins **3 of the 10 series** it covers and beats the fixed 50/50 blend in all three; where one parent clearly dominates (for example GBM for NE Plugs & Sockets), it does not beat it.
- It covers 10 of the 14 series, because there is no GBM run for NW RACK and the emergency lighting loads (the GBM notebook looks for the load type "Emergency Lighting", while the data uses "Emerg. Lighting", so those series are skipped); SW 2025 is excluded, as in the project rules.
- These results use the original GBM, which contains same-hour inputs (section 4.6). Rebuilt on the corrected GBM, the hybrid is best in 2 of 10 series (section 4.8).

### 4.6 Leakage audit of the day-ahead GBM

Before using the GBM of `GBM_forallzones.ipynb` as the 1-day reference for the multi-day work, the team audited its features (T37, `T37_check_gbm_leakage.py`, `T37_check_gbm_leakage_results.csv`, NW HVAC):

- **Found:** the 24-hour rolling mean (`roll_mean_24`) includes the hour being forecast, and the indoor readings of that hour are not known a day ahead. GBM, Random Forest and CatBoost all use same-hour inputs.
- **Effect:** for NW HVAC on test 2023, the GBM error rises from 29.6 % (as in the notebook) to 49.6 % with the rolling mean shifted by 24 hours and 49.5 % fully day-ahead; on test 2025 from 84.8 % to 98.5 % and 98.4 %. The only ASHRAE 14 pass of this series disappears. The fully day-ahead result agrees with T29 LightGBM (47.2 %).
- **Also found:** lags are shifted by row, not by time; inside each period the hourly grid is complete, so this only matters across the 902-day gap (lags of the first week of 2025 come from February 2023).
- **Consequence:** the GBM and the hybrid were corrected and the model choice was re-run (section 4.8); Random Forest and CatBoost were not retrained.

### 4.7 Multi-day forecasts (T37)

One GBM per horizon (1, 2, 3, 5 and 7 days, direct strategy, the settings of the team's GBM) was trained for NE, NW and SE HVAC and the floor total, using target values only up to 24 × d hours before the forecast hour and no indoor sensors. Two scenarios are compared: measured outdoor weather used as a perfect forecast (upper bound) and no weather (lower bound). Every horizon, scenario and baseline is scored on the same hours (`T37_REPORT.md`, `T37_multihorizon_results.xlsx`, logbook entry 21).

**Table 25 – CV(RMSE) by forecast horizon**

| Series and period | 1 day | 2 days | 3 days | 5 days | 7 days | Seasonal naive |
|---|---|---|---|---|---|---|
| NW HVAC, test 2023 | 50.0 % | 61.1 % | 62.5 % | 72.7 % | 80.0 % | 104.0 % |
| SE HVAC, test 2025 | 42.8 % | 36.7 % | 35.5 % | 43.0 % | 43.9 % | 44.3 % |
| Floor total without SW, 2025 | 28.3 % | 31.3 % | 32.1 % | 32.8 % | 32.5 % | 40.8 % |

- **Accuracy decays with the horizon,** but the GBM still beats the seasonal naive at 7 days in 17 of 18 series-period-scenario cases (exception: SE HVAC 2025 without weather).
- **ASHRAE 14 passes are rare at any horizon:** NE HVAC 2025 passes at every horizon (18.3–20.1 %, but it is a very small load), and the floor total without SW in 2025 passes at 1 day (28.3 %, NMBE +0.3 %) and stays at 31–33 % up to 7 days. No other series passes, even at 1 day.
- **SE HVAC is better at 2–3 days than at 1 day** on the same 962 hours: the 1-day model copies yesterday's cooling spikes (bias −21.4 % against −13.6 % and −13.3 % at 2 and 3 days). The gain disappears at 5–7 days.
- **NW HVAC 2023:** the bias grows from +9 % at 1 day to +41 % at 7 days, so cold-weather peaks are under-forecast.
- **Perfect weather helps less than expected:** at 1 day it changes CV(RMSE) by less than 3 points in most series; with only two training years the model partly uses weather as a stand-in for the season.
- **Decision:** multi-day forecasts stay in scope as an indicative outlook up to 7 days, shown with their horizon-specific error, not as an ASHRAE-validated product. Measured weather was used as a perfect forecast, so these results are an upper bound; a real weather-forecast feed is the next step.

### 4.8 Leak-free audit: corrected GBM and hybrid (notebooks 01–04)

To act on the leakage audit, the team reproduced the problem, corrected the GBM and the hybrid and re-ran the model choice in five notebooks; the original project files were kept unchanged and all new outputs were written to separate files.

- **00 – Preliminary audit** (`00_Preliminary_Audit.ipynb`): re-runs `T37_check_gbm_leakage.py` on the repository data and reproduces the problem: NW HVAC test 2023 is 29.6 % with the notebook features, 49.6 % with the rolling mean shifted by 24 hours and 49.5 % fully day-ahead (test 2025: 85.0 %, 97.6 % and 98.4 %).
- **01 – GBM timezone audit** (`01_GBM_Timezone_Audit.ipynb`): confirms that `All_Zones_GBM_predictions.csv` holds Madrid local time labelled as UTC (5.28 % of values match as UTC, 99.96 % as local time). The 48,221 timestamps are converted to UTC; the 20 ambiguous hours of the clock change on 30 October 2022 are matched by value, giving a 100 % match (`All_Zones_GBM_predictions_utc.csv`).
- **02 – GBM leakage correction** (`02_GBM_Leakage_Correction.ipynb`): the GBM is retrained for its 10 series with the same settings, with the rolling mean ending 24 hours before the forecast hour, indoor variables lagged 24 hours and lags computed by time rather than by row (`GBM_Corrected_Predictions_10series.csv`, 46,007 predictions). NW HVAC test 2023 reaches 48.52 %, close to the 49.5 % of T37. On the selection window the corrected GBM is worse than the original in 8 of 10 series (for example NE Plugs & Sockets 23.59 % → 77.19 %) and better in 2 (SW Plugs & Sockets 24.35 % → 8.03 %). Row-based lags differ from true 24-hour lags in only 24 of 26,806 eligible hours (0.09 %).
- **03 – Hybrid re-evaluation** (`03_Hybrid_Reevaluation.ipynb`): the hybrid is rebuilt on the corrected GBM with the original protocol (weights fitted on 1 July – 15 October, compared on 16 October – 31 December, refitted on the whole validation period for the tests). Among Chronos, the corrected GBM and the corrected hybrid, the hybrid is best in 2 of 10 series (NE Plugs & Sockets 41.91 % against 42.89 % for Chronos; NW Lighting 64.39 % against 66.14 %) and Chronos in 8. The unconstrained weights are unstable: for NE HVAC the Chronos weight moves from 0.74 to 1.36 and the GBM weight from 0.25 to −0.56 between the two fits.
- **04 – Final model selection audit** (`04_Final_Model_Selection_Audit.ipynb`): the official T38, figure and T40 scripts are re-run with the corrected GBM and hybrid in place of the originals; the results are in sections 5.2, 5.6 and 5.7.

**Limits stated in the notebooks.** This is a partial leakage correction: Random Forest and CatBoost were not retrained with strict day-ahead features; the corrected GBM is a fixed 24-hour-horizon experiment whose full availability at forecast issue time is not yet demonstrated; differences between the runs cannot be attributed only to the leak correction, because features, training samples and prediction coverage also changed.

> **Phase 4 summary.** Forecasts from six model families are built in one format, on the same hours and with one evaluation toolkit; a hybrid Chronos + GBM learns its weights per series, the floor total has its own hierarchical forecast and HVAC and the floor total are also forecast up to 7 days ahead. A self-audit found leakage in the GBM; the GBM and the hybrid were corrected and the model choice re-run, while retraining Random Forest and CatBoost with strict day-ahead features remains the first roadmap step.

---

## 5. Evaluation

Evaluation decides which model is good enough for the building manager and where the forecast can be trusted. The team first evaluated 10 models on 763,171 forecast hours (logbook entry 20; `TeamB_Sprint3_results.md`, `TeamB_evaluation_all_models.xlsx`, `TeamB_evaluation_best_model.xlsx`). The final evaluation (T38, `TeamB_T38_final_evaluation.py` and `TeamB_T38_final_evaluation.xlsx`) follows the professor's guidance of 15 November 2026, adds the hybrid and replaces that first selection.

### 5.1 Checks before the evaluation

- All prediction files are in the agreed format, and `y_true` matches `energy_wh_model` of v0.4 in every row except 5–10 hours around the October clock change.
- The GBM file stored Madrid local time in the column `timestamp_utc`; the combining script (`T36_combine_predictions.py`) converts it to UTC so that all models line up hour by hour. GBM also labelled the whole out-of-sample period "test"; the script re-labels it by date.
- The day-ahead LightGBM (T29) and floor-total (T30) files report NMBE with the opposite sign to the formula in section 1.5 (positive = forecast too high), as stated in those files. The final evaluation (T38) and the bias analysis (T40) use the sign of section 1.5 (positive = forecast too low).
- The 50/50 blend and SARIMAX are not in the final evaluation, because they have no predictions file in the agreed format.
- The leak-free audit checked the GBM timestamps independently (100 % match after conversion to UTC) and confirmed that the actual values of the corrected GBM and of Chronos are identical on every shared hour.

### 5.2 Model choice per series (T38 and the leak-free audit)

**Protocol.** Per series, the candidate with the lowest CV(RMSE) on **16 October – 31 December 2022** is chosen, on the hours that every candidate forecast. This window is out-of-sample for every model, including the hybrid, which learned its weights on 1 July – 15 October 2022. The choice is then frozen and scored once on both test periods. Naive forecasts are benchmarks, never candidates.

**Two runs.** The first final evaluation (T38, `best_model_selection_final.csv`) used the original GBM and hybrid, which contain same-hour inputs (section 4.6). The leak-free audit (`04_Final_Model_Selection_Audit.ipynb`, section 4.8) re-ran the same T38 scripts with the corrected GBM and hybrid and keeps all other candidates. **The audit results are the final results of this report**; the original T38 results are kept for comparison. The priority series have 8 candidates (CatBoost and Random Forest, each with and without 2020, Chronos, leak-free GBM, LightGBM and leak-free hybrid) and the constant loads 5 (CatBoost and Random Forest with and without 2020, Chronos).

**Table 26 – Model choice before and after the leak-free audit (selection window, CV(RMSE) %)**

| Series | T38 choice | CV | Audit choice | CV | Naive | Hours |
|---|---|---|---|---|---|---|
| NE HVAC | GBM | 325.35 | Random Forest (without 2020) | 326.59 | 462.30 | 1,810 |
| NE Plugs & Sockets | GBM | 23.24 | Hybrid (leak-free) | 41.91 | 50.45 | 1,810 |
| NW Emerg. Lighting | Chronos | 2.70 | Chronos | 2.70 | 3.46 | 1,630 |
| NW HVAC | Chronos | 19.12 | Chronos | 19.10 | 23.52 | 1,603 |
| NW Lighting | Hybrid | 64.35 | Hybrid (leak-free) | 64.39 | 95.51 | 1,810 |
| NW Plugs & Sockets | GBM | 37.88 | CatBoost | 48.28 | 65.55 | 1,810 |
| NW RACK | Chronos | 0.74 | Chronos | 0.74 | 1.03 | 1,837 |
| SE Emerg. Lighting | Chronos | 12.74 | Chronos | 12.74 | 19.93 | 1,612 |
| SE HVAC | Chronos | 21.86 | Chronos | 23.24 | 44.19 | 1,108 |
| SE Lighting | Hybrid | 193.67 | Chronos | 211.59 | 277.35 | 1,038 |
| SE Plugs & Sockets | Hybrid | 124.11 | Chronos | 131.50 | 157.17 | 1,237 |
| SW Emerg. Lighting | Chronos | 8.50 | Chronos | 8.50 | 12.57 | 1,325 |
| SW Lighting | Random Forest (without 2020) | 440.06 | Chronos | 302.14 | 329.85 | 554 |
| SW Plugs & Sockets | Chronos | 7.11 | Chronos | 12.12 | 14.94 | 663 |

Naive and Hours refer to the audit run. The common selection hours changed for 10 of the 14 series, because the corrected models have fewer predictions, so the two runs are not always scored on identical hours.

- **Seven series changed their chosen model**; the corrected GBM is not chosen for any series. The model counts move from Chronos 7, GBM 3, hybrid 3 and Random Forest 1 to **Chronos 10, leak-free hybrid 2, Random Forest (without 2020) 1 and CatBoost 1**.
- **NE HVAC is an effective tie:** Random Forest without 2020 reaches 326.59 %, Chronos 326.62 % and the leak-free hybrid 326.63 %; the series is also dominated by meter faults (section 5.6).

**Table 27 – Headline results before and after the leak-free audit**

| Measure | T38 (original) | Leak-free audit (final) |
|---|---|---|
| Positive skill: validation / test 2023 / test 2025 | 14 of 14 / 14 of 14 / 9 of 11 | 14 of 14 / 14 of 14 / 11 of 11 |
| Positive skill, all periods | 37 of 39 | **39 of 39** |
| Median skill: validation / test 2023 / test 2025 | 0.31 / 0.30 / 0.19 | **0.27 / 0.30 / 0.20** |
| Load targets met: validation / test 2023 / test 2025 | 7 of 14 / 8 of 14 / 5 of 11 | **7 of 14 / 8 of 14 / 6 of 11** |

The lower median skill on validation fits the removal of inflated GBM and hybrid scores, but the change cannot be attributed only to the leak correction, because the selection hours and the chosen models also changed.

**Skill over the naive benchmark.** After the audit, the chosen model has **positive skill in all 39 series-period combinations**. The lowest skill is NW Plugs & Sockets in 2025 (CatBoost, 0.08); this series has a 2025 level 40 % below training, its occupancy input changed meaning (0/1 per hour until 2023, a share of minutes in 2025, mean 0.48 → 0.05), and CatBoost is the only chosen model still exposed to same-hour indoor inputs.

**Table 28 – Chosen model per series against the target for its load type: CV(RMSE) and skill (leak-free audit)**

| Series | Chosen model | Target | Validation | Test 2023 | Test 2025 | Skill (validation / 2023 / 2025) |
|---|---|---|---|---|---|---|
| NW RACK | Chronos | ≤ 15 % | **0.7 %** ✓ | **0.5 %** ✓ | **3.6 %** ✓ | +0.25 / +0.39 / +0.29 |
| NW Emerg. Lighting | Chronos | ≤ 15 % | **2.9 %** ✓ | **5.3 %** ✓ | 34.3 % | +0.20 / +0.57 / +0.28 |
| SE Emerg. Lighting | Chronos | ≤ 15 % | **8.5 %** ✓ | **12.4 %** ✓ | **14.0 %** ✓ | +0.32 / +0.35 / +0.34 |
| SW Emerg. Lighting | Chronos | ≤ 15 % | **5.8 %** ✓ | **10.5 %** ✓ | – | +0.32 / +0.05 / – |
| NE Plugs & Sockets | Hybrid (leak-free) | ≤ 30 % | **22.0 %** ✓ | **21.0 %** ✓ | **5.5 %** ✓ | +0.18 / +0.21 / +0.20 |
| NW Plugs & Sockets | CatBoost | ≤ 30 % | 54.7 % | 53.2 % | 42.2 % | +0.24 / +0.19 / +0.08 |
| SE Plugs & Sockets | Chronos | ≤ 30 % | 116.1 % | 123.2 % | **29.2 %** ✓ | +0.20 / +0.27 / +0.26 |
| SW Plugs & Sockets | Chronos | ≤ 30 % | **13.7 %** ✓ | **17.5 %** ✓ | – | +0.35 / +0.39 / – |
| NE HVAC | Random Forest (without 2020) | 30–50 % | 240.0 % | 690.3 % | **19.1 %** ✓ | +0.29 / +0.29 / +0.15 |
| NW HVAC | Chronos | 30–50 % | 68.6 % | **39.3 %** ✓ | 93.8 % | +0.11 / +0.24 / +0.14 |
| SE HVAC | Chronos | 30–50 % | **48.3 %** ✓ | **40.0 %** ✓ | **34.7 %** ✓ | +0.26 / +0.30 / +0.23 |
| NW Lighting | Hybrid (leak-free) | Daily | 71.0 % | 61.7 % | 87.9 % | +0.36 / +0.41 / +0.20 |
| SE Lighting | Chronos | Daily | 353.8 % | 158.4 % | 264.5 % | +0.27 / +0.25 / +0.14 |
| SW Lighting | Chronos | Daily | 314.2 % | 157.6 % | – | +0.28 / +0.37 / – |

✓ = meets the target for its load type (section 1.5). Values are computed on the hours shared by the chosen model and the naive forecast (T38 sheet *Final_table*, re-run in the audit). Lighting is judged on daily energy and timing (below), so its hourly CV(RMSE) is shown for reference only. SW has no 2025 data.

**Lighting, judged per day.** Daily CV(RMSE) and switch-on timing (median error in hours):

- **NW Lighting (leak-free hybrid):** daily CV(RMSE) 40.6 % on validation, 26.9 % on test 2023 and 39.5 % on test 2025, with a mean absolute error of 0.72, 0.63 and 0.46 kWh per day and a median switch-on error of 0 hours.
- **SE Lighting (Chronos):** daily CV(RMSE) 188.3 %, 99.1 % and 149.8 %; switch-on error 2, 1 and 5 hours.
- **SW Lighting (Chronos):** daily CV(RMSE) 439.8 % and 196.2 %; switch-on error 4 and 5.5 hours.

**Findings**

- **Targets per load type** are met by **7 of 14 series on validation, 8 of 14 on test 2023 and 6 of 11 on test 2025** (lighting not counted): constant loads 4 of 4, 4 of 4 and 2 of 3; Plugs & Sockets 2 of 4, 2 of 4 and 2 of 3; HVAC 1 of 3, 2 of 3 and 2 of 3. The only change from T38 is Plugs & Sockets in 2025 (1 → 2 of 3).
- **No single model wins everywhere.** Chronos, which reads only the history, is chosen for 10 series (all four constant loads, NW and SE HVAC, SE and SW Lighting, SE and SW Plugs & Sockets); the leak-free hybrid for 2 (NE Plugs & Sockets, NW Lighting); Random Forest without 2020 for NE HVAC and CatBoost for NW Plugs & Sockets. The dashboard and the report use the chosen model per series.
- **Constant loads:** on validation the naive forecast already meets their 15 % target (0.9–12.5 %), so models add little value there; the forecasting effort belongs to HVAC, Lighting and Plugs & Sockets.
- **ASHRAE 14 as a reference:** its hourly limits (CV(RMSE) ≤ 30 %, NMBE within ±10 %) are met by 6 of 14 series on validation, 6 of 14 on test 2023 and 5 of 11 on test 2025.
- **Remaining limit:** Random Forest and CatBoost were not retrained with strict day-ahead features; among the chosen models only NW Plugs & Sockets (CatBoost) is still exposed to same-hour indoor inputs, while NE HVAC (Random Forest) is not, because NE has no indoor sensors (section 5.9).

### 5.3 From hour to day and from series to the floor total

Results are reported as a hierarchy: hour → day, and series → zone → floor. Daily values are the sum of the 24 hourly day-ahead forecasts, so every level comes from the same model.

- **From hour to day (validation):** NW HVAC improves from 68.6 % per hour to 48.9 % per day and NW Plugs & Sockets from 54.7 % to 31.2 %; timing errors average out over the day.
- **From series to floor:** on test 2023 the floor-1 total improves from 45.2 % (seasonal naive, same hour last week) to 37.4 % with MinT reconciliation, a skill of +0.17, and the zones add up exactly to the total. On validation the figures are 50.6 % and 38.3 % (skill +0.24, daily CV(RMSE) 18.4 % against 27.4 %), but these are optimistic, because the reconciliation weights are estimated on the validation residuals.

**Table 29 – Floor-1 total, day-ahead (T30), CV(RMSE)**

| Method | Validation (2,682 h) | Test 2023 (586 h) |
|---|---|---|
| Seasonal naive | 50.57 % | 45.21 % |
| LightGBM direct on the total | 41.95 % | 38.64 % |
| Bottom-up | 39.63 % | 37.98 % |
| Reconciliation OLS | 39.71 % | 37.85 % |
| Reconciliation WLS | 38.55 % | **37.14 %** |
| Reconciliation MinT-shrink | 38.32 % | 37.40 % |

- **As a reference, no method meets the ASHRAE 14 hourly limit of 30 %**; all LightGBM-based methods beat the seasonal naive on test 2023, by 6.6 (direct model) to 8.1 points (WLS).
- **Reconciliation** improves accuracy only slightly (about 1.5 points); its main benefit is coherence: the direct total differs from the sum of the zone forecasts by 437 Wh per hour (12.8 % of mean consumption), while all reconciled forecasts add up exactly.
- **Per day on test 2023** (only 11 complete days), MinT reaches a daily CV(RMSE) of 33.1 % against 33.6 % for the seasonal naive, so the daily gain is small there.
- **By zone (test 2023, direct model per zone):** NE 28.4 % (passes), NW 46.9 %, SW 62.5 %, SE 103.4 %. NW Plugs & Sockets is the main source of error.
- **Errors are concentrated in working hours** (MAE about 1.4–1.7 kWh between 07:00 and 15:00 vs about 0.55 kWh at night); the models smooth the peaks.
- **Test 2025 could not be scored**, because SW has no 2025 data and the total needs every series.

### 5.4 When is the forecast least reliable? (T34)

Error = MAE as a percentage of the series mean, best model, priority series, validation period. These results were computed on the first model selection (logbook entry 20: Chronos 8, GBM 5, Random Forest 1), before the hybrid and the leak-free audit.

**Table 30 – Error by time and series**

| By | Result |
|---|---|
| Hour of day | Lowest at night (17–22 % between 00:00 and 06:00); highest at the start and end of the working day (29–30 % at 07:00–09:00, 34 % at 17:00) |
| Day type | Weekend 20 %, working day 26 %, holiday 29 % (few holidays to learn from) |
| Season | Validation: summer 17 %, winter 24 %, autumn 30 %; tests: winter 2023 31 %, summer/autumn 2025 34–35 % |
| Load type | Lighting hardest (SE 82 %, SW 110 % of the mean); HVAC 14–27 %; Plugs & Sockets 5–24 %; constant loads 0–6 % |

The models know the daily pattern but not the exact moment devices switch on and off.

**Check on the final model.** Recomputed for the final presentation from the Chronos-Bolt forecasts of the 10 series where Chronos is chosen (validation 2022-H2, MAE as a percentage of the mean): the error is highest in working hours, 25–27 % between 09:00 and 13:00 against about 2 % at night, and on holidays the model (15.0 %) is worse than the naive forecast (11.2 %, same hour last week).

### 5.5 Anomaly candidates (T35)

Days and hours where the best model is far off compared with its normal error (robust z-score), at most 3 per series, each with a first explanation from the calendar and the quality flags. The full list (17 days) is in `TeamB_evaluation_best_model.xlsx`; like section 5.4, it comes from the first model selection.

**Table 31 – Main anomaly candidates**

| Date | Series | Actual vs forecast | First explanation |
|---|---|---|---|
| 3, 17 and 20 February 2023 | NE HVAC | 1.1–3.5 kWh vs about 0.07 kWh | Quality flags in 33–42 % of hours: likely a meter problem |
| 22 and 29 August, 28 September 2025 | SE Lighting | 11.7–14.3 kWh vs 0.3–1.3 kWh | Lighting on in August and on a Sunday; 2025 level shift: check whether lights were left on |
| 19–20 December 2022 | SW Lighting | 8.4–9.9 kWh vs 0.7–1.1 kWh | Quality flags in 50 % of hours |
| 1 December 2022, 30 January 2023 | SE Plugs & Sockets | 3.0–6.3 kWh vs 0.7–1.6 kWh | No context found: check on site |
| 26–27 July 2022 | SE HVAC | About twice the forecast | Quality flags in about 30 % of hours |

**Examples from the final model** (largest daily differences in the tests, days with at least 20 hours; final presentation, appendix A4). They are candidates to check, not confirmed faults:

- **SW Lighting, Monday 2 January 2023:** 11.6 kWh measured against 0.0 kWh forecast: lights on after the holiday break.
- **SE Lighting, Tuesday 2 September 2025:** 0.2 kWh measured against 13.3 kWh forecast: lights or meter off.
- **NW HVAC, 23 January, 9 February and 24 February 2023:** daily errors of −53 % to −67 % on the days the load restarts after a low period; Chronos reacts a day late.

### 5.6 Sensitivity to flagged hours (T40)

The T40 script was re-run on the models chosen in the leak-free audit; the chosen model is scored on all hours and on hours without quality flags. T40 uses all hours of the chosen model, while Table 28 uses only the hours shared with the naive forecast, so values differ slightly.

- **Error mainly from meter faults:** NE HVAC 691.6 % → 13.2 % on test 2023 and 239.5 % → 15.8 % on validation; NW Emergency Lighting 34.1 % → 4.3 % on test 2025.
- **Flags explain part of the error:** SE Plugs & Sockets 118.8 % → 60.1 % on validation and 127.3 % → 72.9 % on test 2023; SE HVAC 50.6 % → 28.2 % on validation; SE Lighting 257.4 % → 235.7 % on test 2025.

These hours go to facilities as maintenance tasks rather than to the model.

### 5.7 Bias and interpretation (T40)

In the re-run on the audited models, eight series-period cases have a bias above ±10 % (NMBE, positive = forecast too low). A simple 7-day level update, which multiplies the forecast by actual ÷ forecast over the previous 7 days (known at midnight, ratio limited to 0.5–2), shows whether the bias is a change in level:

**Table 32 – Biased cases before and after a 7-day level update**

| Series | Period | NMBE before | NMBE after | Mean actual vs training | Verdict |
|---|---|---|---|---|---|
| NE HVAC | Test 2023 | +59.4 % | +45.8 % | +134 % | Partly a level shift |
| SE Lighting | Validation | +30.5 % | −6.5 % | +132 % | Level shift: fixed |
| SE Lighting | Test 2023 | +26.4 % | +1.2 % | +273 % | Level shift: fixed |
| SE Lighting | Test 2025 | −13.2 % | −20.8 % | +302 % | Not explained by level |
| SE Plugs & Sockets | Validation | +12.3 % | −2.6 % | −68 % | Level shift: fixed |
| SE Plugs & Sockets | Test 2023 | +15.4 % | −0.7 % | −58 % | Level shift: fixed |
| SW Lighting | Validation | +32.4 % | −1.3 % | −27 % | Level shift: fixed |
| SW Lighting | Test 2023 | +25.2 % | +2.8 % | +102 % | Level shift: fixed |

- **The level update fixes 6 of the 8 cases** and reduces NE HVAC; for SE Lighting 2025 it makes the bias worse. Where it works, the bias is a change in building use, not a model fault, and regular re-fitting removes it. In the original T38 run, 2 of 6 biased cases were fixed.
- **NW HVAC** is at 39.3 % on test 2023 but 93.8 % on test 2025 with little bias (+4.2 % and +1.0 %): the level is right, but the hourly pattern differs between winter 2023 and late summer 2025.
- **Why can a test three years after training score better than one a month after?** The 2025 window is easier: the naive forecast improves even more, so the skill falls. For example SE HVAC goes from 40.0 % (naive 57.1 %) in 2023 to 34.7 % (naive 45.0 %) in 2025, while the skill falls from 0.30 to 0.23; SE Plugs & Sockets goes from 123.2 % (naive 167.7 %) to 29.2 % (naive 39.7 %) and NE Plugs & Sockets from 21.0 % (naive 26.7 %) to 5.5 % (naive 6.8 %), with almost unchanged skill. NE HVAC in 2023 is also dominated by meter faults. Where behaviour changed, 2025 is worse (NW HVAC 39.3 % → 93.8 %). Forecasts are therefore compared by skill within the same period.

### 5.8 Driver explanation (T33)

SHAP values (`T33.ipynb`, `T33_F5.4_driver_summary.csv`) were computed for models of the first final evaluation, before the leak-free audit; none of these three models is chosen after the audit, but they show which inputs drive the forecast:

**Table 33 – Top drivers per series (SHAP)**

| Series | Model | Validation CV(RMSE) | Top 3 drivers | Reading |
|---|---|---|---|---|
| NE HVAC | GBM | 243.04 % | `roll_mean_24`, `energy_lag_24`, `hour_local` | Mainly autoregressive; no indoor sensors in NE |
| NW Plugs & Sockets | GBM | 42.63 % | `roll_mean_24`, `temp_lag2`, `energy_lag_24` | Autoregressive, with temperature and light effects |
| SW Lighting | Random Forest (without 2020) | 323.35 % | `occupancy`, `lag_24h`, `lag_168h` | Occupancy and past use dominate; light also important |

Recent consumption dominates, as in the LightGBM gain ranking (section 4.3). The top driver of both GBM series, `roll_mean_24`, is the leaky feature found in section 4.6, so its weight is overstated. SHAP therefore also supports the self-audit: the most important driver of the original GBM was the leaky feature.

### 5.9 Limitations stated in the files

- Test 2023 covers only January–February and test 2025 only 18 August – 13 October, so the two tests cover different seasons and are not directly comparable.
- SW has no 2025 data, so 2025 results cover 11 of 14 series; NE has no indoor sensors.
- CV(RMSE) is unreliable for very low series: NE HVAC averages a few Wh per hour, so a small absolute error gives a CV(RMSE) of hundreds of percent; MAE is reported alongside.
- Validation scores are slightly optimistic for models that use the validation period for early stopping or tuning; only the test periods are fully out of sample.
- The leak correction is partial: Random Forest and CatBoost were not retrained with strict day-ahead features, so their scores may be optimistic; among the chosen models only NW Plugs & Sockets (CatBoost) is still exposed to same-hour indoor inputs, and other forms of leakage are not fully excluded.
- The corrected GBM is a fixed 24-hour-horizon experiment; full availability of every feature at forecast issue time is not yet demonstrated.
- The selection hours changed for 10 of 14 series in the audit (SW Lighting is chosen on only 554 hours), and NE HVAC is an effective tie between three models.
- The hybrid uses unconstrained weights, which change strongly between fits for some series.
- Outdoor weather is observed, not forecast; the multi-day results (section 4.7) are therefore an upper bound.
- The error breakdown (T34), the anomaly list (T35) and the SHAP analysis (T33) come from earlier model selections, before the leak-free audit.
- NW Lighting, NW HVAC and SE Lighting changed level in 2025.

### 5.10 Weak points and how to improve them

Following the professor's first tip, every weakness found is linked to an improvement:

**Table 34 – Weak points, evidence and improvement**

| Weak point | Evidence | How to improve |
|---|---|---|
| Working hours | First selection: 34 % at 17:00 against 17–22 % at night; final model: 25–27 % between 09:00 and 13:00 against about 2 % at night (section 5.4) | Schedule and occupancy features; quantile forecasts |
| Holidays | First selection: about 29 %; final model: 15.0 % against 11.2 % for the naive forecast (section 5.4) | Academic calendar as a feature |
| Meter faults | NE HVAC test 2023: 691.6 % → 13.2 % without flagged hours (section 5.6) | Fault alerts to facilities; flag-aware training |
| Floor total | Test 2023: 45.2 % (seasonal naive) → 37.4 % reconciled, still above 30 % (section 5.3) | Reconcile all levels, not only the total |
| Frozen models | Level shifts; a 7-day level update fixes 6 of 8 biased cases (section 5.7) | Rolling re-fit and drift monitoring |
| Same-hour inputs | GBM and hybrid corrected; Random Forest and CatBoost not retrained (sections 4.8, 5.9) | Retrain Random Forest and CatBoost with strict day-ahead features; check feature availability at issue time |
| Savings not quantified | No file estimates savings in kWh or euros | Quantify with the CeDInt tariff, starting from anomaly days |

> **Phase 5 summary.** Every model is scored with the same rules on the same hours, and the model per series is chosen on a window that is out-of-sample for every model. After the leak-free audit, the chosen model beats the naive benchmark in all 39 series-period combinations (median skill 0.27, 0.30 and 0.20), and the targets per load type are met by 7, 8 and 6 series. Errors, anomalies, the effect of meter problems, the bias and its correction, the drivers, the limits and an improvement for every weak point are documented.

---

## 6. Deployment

Deployment turns the results into material the client can use.

### 6.1 Dashboard (T36)

`T36_dashboard_app.py` is a Streamlit dashboard that runs locally in the browser on the clean dataset; the data itself is not stored in the repository. It has seven tabs:

1. **Overview** – energy by zone and load type and its share.
2. **Consumption** – daily energy, average daily profile (working day, weekend, holiday) and monthly energy.
3. **Drivers** – daily energy against indoor temperature, occupancy and light per series.
4. **Forecast vs actual** – CV(RMSE), NMBE, MAE, skill against the naive forecast and the target per load type, per model, period and series, hourly or per day; one week of forecast vs actual; a comparison of all models on the hours that every model forecast, grouped by model family (benchmark, history only, drivers, hybrid); and a decision box with a recommended action per load type and a bias alert (|NMBE| > 10 %) or a skill alert (does not beat the naive forecast).
5. **Best model scorecard** – the T38 model choice, skill per series, targets met, bias before and after the 7-day level update and the error with and without meter-fault hours (T40).
6. **Floor-1 total** – actual against the T30 forecasts (seasonal naive, direct model, bottom-up, MinT), hourly or per day.
7. **Data quality** – series ratings, usable hours and known sensor and meter problems.

Any model's forecasts can be loaded as one file with the seven agreed columns; `T36_combine_predictions.py` merges the predictions of all models into one file for the dashboard and the evaluation. The multi-day outlook (T37) is not in the dashboard yet; adding it, with its error per horizon, is the next step.

### 6.2 Value for the building manager

The forecast is useful through the decision it enables, and each result feeds the next forecast:

- **Forecast → decision:** day-ahead forecasts and a 2–3 day outlook let the manager pre-heat or pre-cool, buy energy, plan maintenance and staff, and check alerts.
- **Decision → result → better forecast:** measured and forecast values are compared in the dashboard; rolling re-fits and drift alerts keep the models current (section 5.7).
- **Anomalies:** for example, one SE Lighting day used about 12–14 kWh against a forecast of about 0.3–1.3 kWh (section 5.5); such days, and the meter-fault hours, go to facilities.
- **Worked example:** for NW HVAC on Tuesday 31 January 2023, Chronos forecast 5.35 kWh for the day and 5.38 kWh was measured (−0.5 %), against 6.65 kWh for the naive forecast. The decision box shows the target met (39.3 %, bias +4.2 %, skill +0.24 over test 2023) and the HVAC action: pre-cool or pre-heat ahead of peak-tariff hours and align chiller and boiler schedules with the forecast outdoor temperature. This is a good day; on the days the load restarts after a low period the daily forecast misses by 53–67 %.
- **Cost:** the tools are open source, but implementation, maintenance and infrastructure still cost; the savings in euros are not yet quantified and need the CeDInt tariff and a test after an intervention.

**Status of the product.** The deliverable is a historical forecasting prototype: forecasts were produced and evaluated for past periods, with a dashboard and quality indicators. It is not yet an automated nightly system, live monitoring is not deployed, and live use needs a weather-forecast feed.

### 6.3 Reproducibility

Every step can be rerun from the raw files: `clean_cedint.py` (clean dataset), `make_figures.py` (figures), `T32_make_training_data.py` (model-ready data), the model scripts, `hybrid_blend_learned_weights.ipynb` (hybrid), `T36_combine_predictions.py`, `TeamB_T38_final_evaluation.py` and `TeamB_T38_figures.py` (final evaluation), `TeamB_T40_robustness_bias.py` (bias and robustness), `team_b_eval.py` (evaluation toolkit) and the five audit notebooks (`00_Preliminary_Audit.ipynb`, `01_GBM_Timezone_Audit.ipynb`, `02_GBM_Leakage_Correction.ipynb`, `03_Hybrid_Reevaluation.ipynb`, `04_Final_Model_Selection_Audit.ipynb`). Experiments are recorded in `EXPERIMENT_LOGBOOK.md`.

### 6.4 Deliverables and roadmap

**Table 35 – Final deliverables**

| Deliverable | Status |
|---|---|
| Final presentation (20 minutes, four key visuals: data coverage, main result, forecast horizon, dashboard) | Deck ready (`TBDA_Group3_Final_Presentation_v33.pptx`); rehearsal 26–28 November, presentation 30 November |
| One-page summary of the results (T42) | Complete |
| Frozen DataPack v1.0 (code, data dictionary, logbook, this report, deck and dashboard) | Moodle dropoff area by 14 December 2026 |

**Table 36 – Roadmap**

| When | What |
|---|---|
| Now | Retrain Random Forest and CatBoost with strict day-ahead features; check that every feature is available at forecast issue time |
| Next | Chronos-2 with covariates (weather and calendar); hybrids with constrained weights (non-negative, summing to one) |
| Then | Rolling re-fit; real weather forecasts |
| Later | LSTM or CNN models once more data exist |

> **Phase 6 summary.** A working dashboard, a reproducible pipeline, the final deck and a one-page summary exist, and the roadmap sets out the next steps. The DataPack v1.0 is uploaded to Moodle by 14 December 2026.
