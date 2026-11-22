# Product Backlog Report – v3

**DataPack Energy Forecaster – CeDInt floor 1 (TBDA)**

Product: an analytical and predictive solution that transforms the historical CeDInt sensor data into understandable, spatially contextualised and evaluated energy insights and forecasts for the building: a day-ahead (24 h) forecast of electrical energy per zone and load type, with the conditions that drive it.

This is a product backlog: every item is a feature or value increment for a stakeholder (sponsor, analyst, building manager, facilities technician). The team tasks of the Week 5 sprint plan (A1–E4) are not backlog items; they appear in the delivery plan (section 5) as the way each feature is built.

| | |
|---|---|
| **Status on** | **26 October 2026** (Sprint 2 in progress) |
| **Items** | 32 · 20 High, 11 Medium, 1 Low |
| **Progress** | 🟢 16 Complete · 🟡 1 In Progress · 🔵 15 Not Started · 🟠 0 Overdue · ⚪ 0 On Hold |
| **Sprints** | 1 = 1–14 October · 2 = 15–28 October · 3 = 29 October – 11 November · 4 = 12–25 November · Post = 1–14 December |

**Status:** 🔵 Not Started · 🟡 In Progress · 🟢 Complete · 🟠 Overdue · ⚪ On Hold  
**Priority:** High · Medium · Low

---

## Changes since v2 (status on 5 October 2026)

| ID | v2 status | v3 status | Evidence |
|---|---|---|---|
| F1.1 | In Progress | 🟢 Complete | Subteam D, `models.ipynb` and Sprint 1 summary: chronological split, ASHRAE metric function, seasonal-naive (CV(RMSE) 102.85 %, NMBE −8.75 %) and linear-regression (CV(RMSE) 113.68 %, NMBE −2.02 %) baselines on NW HVAC; logbook entry 17/10/2026 |
| F2.1 | In Progress | 🟢 Complete | Energy types defined, justified with the data and prioritised (section 3) and used in the CRISP-DM report; agreed by the team |
| F4.1 | In Progress | 🟢 Complete | Subteam C, notebook P7: 48 labelled and interpreted plots of average power and energy by hour, weekday and month, working days vs weekends and August vs other months, for HVAC, Lighting and Plugs & Sockets in every zone; logbook entry 19/10/2026. *Note: the secondary loads (Emergency Lighting, Hand Dryer, RACK) are not profiled.* |
| F4.2 | In Progress | 🟢 Complete | Subteam C, notebook P7: 2020 vs 2021–22 vs 2025 on the same August–October weeks; 2020 differs and is treated as a COVID-affected year; logbook entry 19/10/2026. *Note: there is no COVID-2020 flag in `cedint_f1_hourly_clean.csv.gz` yet.* |
| F5.1 | In Progress | 🟢 Complete | Pres is presence (0/1), not pressure, and is used as `occupancy` (Team B data dictionary); subteam C, notebook P8: presence follows the daily cycle in NW, 2021–22 (29.5 % of hours at 02:00, 67 % at 14:00), with some presence also detected at night; logbook entry 19/10/2026; agreed by the team. *Note: the presence analysis covers only the NW zone, and night-time readings should be interpreted with caution.* |
| F6.1 | In Progress | 🟢 Complete | Team B, figure F1 (valid energy per series and month, 902-day gap marked) and sheet *Anomaly_log* (every gap and flag with start and end hour) |
| F6.2 | In Progress | 🟢 Complete | Team B, sheet *Consistency_checks*: power vs energy, apparent ≥ active power, power factor and current vs apparent power, per series and period; power and energy agree within 20 % in at least 95 % of hours for 14 of 17 series (2020–23). *Note: current is checked against apparent power as a correlation, not as a pass rate against active power.* |
| F7.2 | In Progress | 🟢 Complete | Team B, sheets *Series_level_issues* and *Anomaly_summary* |
| F9.1 | In Progress | 🟢 Complete | Team B, `clean_cedint.py` → `cedint_f1_hourly_clean.csv.gz` (dataset v0.3): 470,680 rows × 50 columns, 16 quality flags, model-ready target in 86 % of rows; replaces subteam A's v0.2 (`cedint_f1_hourly.csv`, 450,482 rows × 17 columns); logbook entries 05/10, 08/10 and 17/10/2026 |
| F9.2 | In Progress | 🟢 Complete | Team B, sheet *Data_dictionary* (38 entries), also in each `Storey1_<zone>_cleaned_hourly.xlsx` |
| F9.3 | In Progress | 🟢 Complete | Experiment Logbook with six entries in chronological order – 05/10 (subteam A pipeline), 08/10 (v0.1 pilot), 17/10 (v0.3 dataset), 17/10 (baselines), 19/10 (consumption profiles) and 19/10/2026 (environment and occupancy) – and the CRISP-DM report for Sprint 1; both are updated every sprint |
| F2.2 | Not Started | 🟡 In Progress | Team B rated every secondary series (Use / Use with caution / Do not use); characterisation and forecasts by subteam D still to do |
| F3.1 | In Progress | 🟢 Complete | Task executed by Riccardo (Subteams A & C): Dataset v0.3 organized as a unified long table structured by building, floor, zone code (1NE, 1NW, 1SE, 1SW) and load type; logbook entry 26/10/2026.
| F4.3 | In Progress | 🟢 Complete | Subteam C & A: Script `Task_F4_3C.py` executed by Anthony (`Anthoriv974`). Multi-year time-series (2020–2025) parsed to generate official holiday flags (`is_holiday`) and August low-occupancy flags (`is_august_low_use`). Dataset exported as `cedint_f1_hourly_F4.3C.csv` and code published on main repository `TBDA-Classes/2026G3`; logbook entry 25/10/2026. |
| F5.2 | Started | 🟢 Complete | Task executed by Maria Vittoria (Subteam C): Full relation matrix completed across all zones with correlation heatmaps linking indoor temperature, humidity, luminosity, and occupancy to each load type; logbook entry 26/10/2026. |
| F3.2 | Started | 🟢 Complete | Task executed by Catherine (Subteams B): Zones compared across identical load types and normalized per device count to isolate spatial consumption anomalies; logbook entry 26/10/2026. |
| F5.3 | Started | 🟢 Complete | Task executed by Catherine (Subteams B): Outdoor weather impact (temperature, degree-hours) and delayed HVAC response time lags (0–6 h) evaluated and integrated into the feature pipeline; logbook entry 26/10/2026. |

**All Sprint 1 items are complete.**

---

## 1. Product vision and scope

**Vision:** an analytical and predictive solution that turns historical sensor data from the CeDInt building into understandable, spatially contextualised and evaluated energy insights and forecasts.

**Scope of this release:** floor 1 (zones NE, NW, SE, SW), electrical energy by load type, hourly data 2020–2023 and 2025, day-ahead horizon, final presentation on 30 November 2026 and release on Moodle by 14 December 2026.

**Out of scope:** control actions on the building, floors 2–3 (unless the data are made available), and thermal or non-electrical energy.

## 2. Stakeholders and needs

| Stakeholder | Need | Value we deliver (evidence) |
| --- | --- | --- |
| **UPM / Project Sponsor** | Assess whether the project produces credible predictive evidence and clear performance metrics. | Forecasts tested on unseen data (2023, 2025) and judged with MAE, RMSE, CV(RMSE) ≤ 30 % and NMBE ±10 % (ASHRAE 14); full documentation (CRISP-DM, experiment log). Epics F6, F8, F9. |
| **Energy / Building Analyst** | Understand past consumption and what may happen next, with spatial context and forecasts. | Profiles by zone, load type, hour, weekday and month; relation of consumption with indoor, outdoor and calendar drivers; clean dataset and data dictionary. Epics F3, F4, F5, F9. |
| **Building Manager** | Short-term (24 h day-ahead) and multi-period forecasts per zone and load type (HVAC, lighting, plugs) to anticipate energy behaviour and act on consumption drivers. | Day-ahead forecasts, reliability indicators, driver explanations and a dashboard. Epics F1, F5, F6, F8. |
| **Facilities Technician** | Identify candidate anomalies and faulty meters, and know where to act. | Largest forecast errors as candidate anomalies; list of sensor and meter problems found. Epic F7. |

## 3. Energy types to forecast: decision, justification and priority

The requirements left the energy types open. The team defines them from the profiling of the 18 sheets (about 1.34 million rows) of floor 1 and prioritises them by the value for the building manager and by data quality.

| Energy type | Decision | Justification (from the data) | Priority | Forecast offered |
| --- | --- | --- | --- | --- |
| **HVAC (zones NE, NW, SE)** | In scope – core | Largest and most weather-dependent load; forecasting it is where the building manager can act (preconditioning, set-points). Available in 3 of 4 zones; NW HVAC has clean hourly data and is the first benchmark series. | High | Day-ahead per zone, plus multi-period |
| **Lighting (zones NW, SE, SW)** | In scope – core | Driven by occupancy and daylight (Lum); the clearest case for explaining drivers (more daylight → less artificial light). Available in 3 zones. | High | Day-ahead per zone |
| **Plugs & Sockets (all 4 zones)** | In scope – core | Only load present in every zone; strongly tied to occupancy and working calendar, so it is predictable and shows whether occupancy is a valid driver. | High | Day-ahead per zone |
| **Floor 1 total (sum of loads and zones)** | In scope – core | Gives the building manager one figure and lets us check that zone forecasts add up. Open question for the teacher: target total, zone or load type. | High | Day-ahead and multi-period |
| **Emergency lighting, hand dryer, RACK** | In scope – secondary (control group) | Mostly constant or event-driven loads; useful as a control group for the driver analysis. NW emergency lighting is negative 99 % of the time (reversed clamp) and SW RACK ends in Dec 2021, so quality limits what can be promised. | Low | Characterise and forecast only if data allow |
| **SE Projector** | Out of scope | Series is 100 % zeros: it carries no information to predict. | n/a | Reported as sensor issue (F7.2) |
| **Apparent energy (Ea) and reactive/other electrical quantities** | Out of scope | The forecast target is active energy (Wh, from Er). Column meaning is pending confirmation (Er behaves as active energy, Ea as apparent energy, unlike the slide labels). | n/a | Revisit if the teacher says otherwise |

## 4. Product backlog

Items are grouped by feature (epic). The sprint is the release in which the stakeholder gets the increment; the *Team* column shows the subteam(s) that build it.

### F1. Day-ahead and multi-period energy forecast

| ID | Team | As a … | I want to … | So that … | Priority | Sprint | Status |
|---|---|---|---|---|---|---|---|
| **F1.1** | D | Building Manager | see a first day-ahead (next 24 h) hourly forecast of HVAC energy for the NW zone, compared with a simple baseline | I can see what the product will deliver and the accuracy bar every later model must beat | High | 1 | 🟢 Complete |
| **F1.2** | D + A | Building Manager | get a day-ahead (24 h) hourly forecast of HVAC, lighting and plugs & sockets energy for every zone of floor 1 where that load exists | I can anticipate energy behaviour and plan operation one day ahead | High | 3 | 🔵 Not Started |
| **F1.3** | D | Building Manager | get a day-ahead forecast of the total energy of floor 1 (sum of the zones) | I have one number for the whole floor and can check it against the zone forecasts | High | 3 | 🔵 Not Started |
| **F1.4** | D | Energy / Building Analyst | get multi-period forecasts (several days ahead) for HVAC and the floor total | I can anticipate energy use beyond the next day and compare how accuracy decays with the horizon | Medium | 4 | 🔵 Not Started |

### F2. Energy types in scope (decision and justification)

| ID | Team | As a … | I want to … | So that … | Priority | Sprint | Status |
|---|---|---|---|---|---|---|---|
| **F2.1** | E + D | UPM / Project Sponsor | have the energy types to be forecast defined, justified with the data and prioritised (see section 3) | the scope of the product is explicit, creative and agreed before modelling starts | High | 1 | 🟢 Complete |
| **F2.2** | D + B | Energy / Building Analyst | get the secondary loads (emergency lighting, hand dryer, RACK) characterised and forecast where the data allow | I can tell which loads are predictable and which are constant or unreliable | Low | 3 | 🟡 In Progress |

### F3. Spatial context: building → floor → zone

| ID | Team | As a … | I want to … | So that … | Priority | Sprint | Status |
|---|---|---|---|---|---|---|---|
| **F3.1** | A + C | Energy / Building Analyst | see every consumption series and forecast organised by building, floor and zone (NE, NW, SE, SW) and load type | I understand where energy is used and can aggregate by space, not only by device | High | 2 | 🟢 Complete |
| **F3.2** | C + B | Facilities Technician | compare zones for the same load type, normalised per device | I can spot a zone that consumes unusually more than its neighbours | Medium | 3 | 🟢 Complete |
| **F3.3** | D + C | Energy / Building Analyst | get a forecast for zone NE, which has no environmental sensors, with the limits of that forecast stated | I know what can and cannot be predicted without local sensors | Medium | 3 | 🔵 Not Started |

### F4. Understand past consumption

| ID | Team | As a … | I want to … | So that … | Priority | Sprint | Status |
|---|---|---|---|---|---|---|---|
| **F4.1** | C | Building Manager | see average power by hour, weekday and month for each zone and load type, split into working days, weekends and August | I understand where and when energy is used | High | 1 | 🟢 Complete |
| **F4.2** | C | Energy / Building Analyst | see 2020–23 compared with 2025, with 2020 flagged as a possible COVID-affected year | abnormal periods do not mislead the interpretation or bias the forecasts | Medium | 1 | 🟢 Complete |
| **F4.3** | C + A | Building Manager | see how holidays and August change consumption | low-use days are expected and explained instead of looking like anomalies | Medium | 2 | 🟢 Complete |

### F5. Explain what drives consumption

| ID | Team | As a … | I want to … | So that … | Priority | Sprint | Status |
|---|---|---|---|---|---|---|---|
| **F5.1** | C | Energy / Building Analyst | know whether the sensor value "Pres" represents occupancy | occupancy can be used as a driver with confidence | High | 1 | 🟢 Complete |
| **F5.2** | C | Energy / Building Analyst | see how indoor temperature, humidity, light and occupancy relate to each load type (relation matrix with correlation heatmaps per zone) | I know which conditions drive each type of energy | High | 2 | 🟢 Complete |
| **F5.3** | C + A | Energy / Building Analyst | see the effect of outdoor weather (temperature, degree-hours) and of delayed responses (0–6 h) on HVAC | HVAC consumption can be anticipated from the weather forecast | High | 2 | 🟢 Complete |
| **F5.4** | C + D | Building Manager | see which drivers matter most for each forecast (SHAP explanations per load type) | I can trust the forecast and act on the consumption drivers | High | 3 | 🔵 Not Started |

### F6. Trust: data reliability and forecast evidence

| ID | Team | As a … | I want to … | So that … | Priority | Sprint | Status |
|---|---|---|---|---|---|---|---|
| **F6.1** | B | Building Manager | see a map of the hours with data for every series, with coverage per year, gaps longer than 24 h and quality flags | I know how far I can trust each forecast | High | 1 | 🟢 Complete |
| **F6.2** | B + A | Energy / Building Analyst | see proof that the sensor data are physically plausible (power vs energy, apparent vs active, current vs power) with a pass rate per series | forecasts rest on credible data, not assumptions | High | 1 | 🟢 Complete |
| **F6.3** | D + B | UPM / Project Sponsor | see the models tested on periods never used for training (2023 and 2025) | the reported predictive performance is honest | High | 3 | 🔵 Not Started |
| **F6.4** | D + B | UPM / Project Sponsor | see every forecast evaluated with MAE, RMSE, CV(RMSE) and NMBE against the ASHRAE Guideline 14 criteria (pass/fail per series) | I can judge whether the predictive evidence is credible | High | 4 | 🔵 Not Started |
| **F6.5** | D | UPM / Project Sponsor | see a comparison of the baseline, SARIMAX and LightGBM models for each priority series | the chosen model is justified with evidence | High | 4 | 🔵 Not Started |
| **F6.6** | B + D | Building Manager | see forecast errors by hour, season and zone | I know when the forecast is less reliable | Medium | 3 | 🔵 Not Started |
| **F6.7** | B | Energy / Building Analyst | read what the models get wrong and why, including results with and without flagged data | the limits of the forecasts are stated clearly | Medium | 4 | 🔵 Not Started |

### F7. Anomaly candidates and sensor issues

| ID | Team | As a … | I want to … | So that … | Priority | Sprint | Status |
|---|---|---|---|---|---|---|---|
| **F7.1** | B + D | Facilities Technician | get a list of the largest forecast errors as candidate anomalies (days, hours, zones) | I can check unusual consumption or broken meters | Medium | 3 | 🔵 Not Started |
| **F7.2** | B | Facilities Technician | receive a list of sensor and meter problems found (dead series, reversed clamps, counter resets, missing environmental data) | I can have the faulty devices checked or fixed | Medium | 1 | 🟢 Complete |

### F8. Dashboard and communication of results

| ID | Team | As a … | I want to … | So that … | Priority | Sprint | Status |
|---|---|---|---|---|---|---|---|
| **F8.1** | E + C | Building Manager | use a dashboard showing consumption, forecast vs actual and drivers per zone and load type | I have one place to monitor and plan energy use | High | 3 | 🔵 Not Started |
| **F8.2** | E + C | UPM / Project Sponsor | see a 20-minute final presentation with 3–4 key visuals, rehearsed before 30 November | I "see the evidence" that our organisation has the right tools and capabilities | High | 4 | 🔵 Not Started |
| **F8.3** | E | UPM / Project Sponsor | get a 2-minute video or one-page summary of the results | I get the message without reading the full report | Medium | 4 | 🔵 Not Started |

### F9. DataPack: clean data, documentation and release

| ID | Team | As a … | I want to … | So that … | Priority | Sprint | Status |
|---|---|---|---|---|---|---|---|
| **F9.1** | A + B | Energy / Building Analyst | use one clean hourly dataset (hour × zone × load type) with environmental data and quality flags | I can analyse any series without cleaning or joining files myself | High | 1 | 🟢 Complete |
| **F9.2** | B + E | Energy / Building Analyst | read a data dictionary with every column, unit, source sheet and cleaning rule | I understand every variable and every change made to the raw data | Medium | 1 | 🟢 Complete |
| **F9.3** | E | UPM / Project Sponsor | find every experiment and its performance in an experiment log and a CRISP-DM report | the work can be audited with a well-established methodology | High | 1 | 🟢 Complete |
| **F9.4** | A + E | UPM / Project Sponsor | receive the frozen DataPack v1.0 (code, data, dictionary, log, report, deck, dashboard) in the Moodle dropoff area by 14 December 2026 | the product can be reproduced, graded and reused after the course | High | Post | 🔵 Not Started |

## 5. Delivery plan: how each feature is built (Week 5 roles and tasks)

Subteams: A Data Engineering (3) · B Data Quality & Validation (3) · C Exploration & Environment (2) · D Modelling & Forecasting (1) · E Coordination & Communication (2) – 11 members. Pairs: A+B on cleaning rules (B decides, A implements); C+D on model features; E in every weekly check-in.

| Feature (epic) | Roles | Week 5 tasks that build it | How we accomplish it | Definition of done |
| --- | --- | --- | --- | --- |
| **F1 Forecast** | D leads with A (features) and C (variables) | D1–D3 (S1); baselines, SARIMAX, LightGBM (S2–S3); feature variants from A | Chronological split (no shuffling); seasonal naive and linear-regression baselines; SARIMAX with exogenous drivers; LightGBM tuned with TimeSeriesSplit; target energy_wh, horizon 24 h | Forecast reproducible from one notebook, logged in the experiment log |
| **F2 Energy types** | E coordinates with D and B; teacher confirms | E2 (CRISP-DM phase 1); D3 model plan; open questions | Decision table (section 3) updated with the profiling results and the teacher’s answers | Table approved and referenced in the CRISP-DM report |
| **F3 Spatial context** | A with C | A1, A2, A5; C1 | Zone code = floor + orientation (e.g. 1NE); one long table keyed by timestamp, zone and load type; environment stored once per zone | Any series traceable from plan to zone to forecast |
| **F4 Past consumption** | C leads | C1, C4; hypotheses H11, H12 | Profiles by hour, weekday, month; split working days, weekends, August; 2020 vs 2021–22 vs 2025 | Plots labelled and interpreted in the EDA notebook (≥ 10 plots) |
| **F5 Drivers** | C leads with D | C2, C3 (S1); relation matrix and SHAP (S2–S3); hypothesis H1 | Scatter + LOWESS, Pearson and Spearman, cross-correlation 0–6 h, partial correlation controlling for hour; SHAP on the best model | One heatmap per zone plus written interpretation |
| **F6 Trust and evidence** | B leads with D | B1–B5 (S1); validation and residuals (S2–S4) | Missing-value heatmap, reset and negative-power rules, outlier flags (flag, never delete), consistency checks; train 2020-06 to 2022-06, validate 2022-H2, test 2023 and 2025; ASHRAE 14 | Pass rate per series and pass/fail table in the final comparison |
| **F7 Anomalies** | B with D | B residual analysis (S3); quality findings from S1 | Rank hours and days by absolute forecast error; cross-check against holidays and sensor flags | Candidate list delivered with explanation of each |
| **F8 Dashboard and story** | E leads with C | E4 weekly slides; dashboard prototype (S3); final deck, video (S4) | Power BI or Streamlit; 3–4 key visuals from C; speaker split and rehearsal 26–28 November | Presentation on 30 November and summary delivered |
| **F9 DataPack release** | A with E | A5, E1, E3 (S1); freeze v1.0 (S4); Moodle (Post) | Raw files never edited; every change is a Python step; GitHub repository for code and Microsoft Teams for documents; data dictionary, experiment log, CRISP-DM | Everything in the Moodle dropoff area by 14 December 2026 |

## 6. Release plan by sprint

| Sprint | Increment | Delivered value and items | Status on 19 October 2026 |
|---|---|---|---|
| **Sprint 1 · 1–14 October** | Trusted data and first understanding | Clean hourly dataset with flags, quality evidence, profiles, occupancy test, energy-type decision, first baseline forecast (NW HVAC), documentation started.<br>Items: F1.1, F2.1, F4.1, F4.2, F5.1, F6.1, F6.2, F7.2, F9.1, F9.2, F9.3 | Closed. All 11 items complete. |
| **Sprint 2 · 15–28 October** | Context and drivers | Spatial organisation, weather and holiday drivers, full relation matrix, holiday and August effects.<br>Items: F3.1, F4.3, F5.2, F5.3 | Running. F3.1, F3.2, F4.3, F5.2, and F5.3 complete. F2.2 partially completed by Team B. |
| **Sprint 3 · 29 October – 11 November** | Forecasts and explanations | Day-ahead forecasts for all priority series, unseen-data tests, SHAP, residuals, anomaly candidates, dashboard prototype.<br>Items: F1.2, F1.3, F2.2, F3.2, F3.3, F5.4, F6.3, F6.6, F7.1, F8.1 | F2.2 started early. |
| **Sprint 4 · 12–25 November** | Evidence and story | ASHRAE 14 evaluation, model comparison, robustness, multi-period forecast, final deck, video or one-page summary.<br>Items: F1.4, F6.4, F6.5, F6.7, F8.2, F8.3 | Not started. |
| **Post · 1–14 December** | Release | Feedback from the 30 November presentation processed; DataPack v1.0 in Moodle by 14 December.<br>Items: F9.4 | Not started. |

## 7. Open decisions

- Should the forecast target the floor total, each zone, or each load type? (Backlog assumes all three, with priority on zone × load type.)
- Confirm the column meanings: Er behaves as active energy (Wh) and Ea as apparent energy, which differs from the slide labels.
- Is the 902-day gap (Mar 2023 – Aug 2025) expected, or is more data available? It limits the training and test periods.
- Are exports for floors 2 and 3 and the BMP02 system-level meters available, to compare zone totals with the building total?
- Multi-period forecasts (F1.4) are an extension of the Week 5 plan (day-ahead only); the team confirms whether they stay in scope after Sprint 3.
