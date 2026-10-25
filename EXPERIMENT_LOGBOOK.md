# Experiment Logbook – CeDInt-SEF Smart Energy Forecasting

> **Purpose:** The purpose of this logbook is to document all the tests, data cleaning validation steps, exploratory data analyses, and models that have been used through the whole duration of the project. All details are filled in the tables below, serving as proof of what was tested and why, interpreting the obtained results, and explaining the problems that may arise.  
>  
> **Governance:** The person responsible for this document is the Continuous Audit and Quality Assurance lead, team member **María Herraiz**. However, any member of the group can freely modify this document and add their own version as long as they notify the responsible member, who will afterwards check it.

---

## Template Structure

When adding a new entry, copy and paste the following template at the bottom of the document to maintain chronological order:

```markdown
### [Date] – [Dataset Version / Topic]

| Field | Details |
|---|---|
| **Date** | DD/MM/YYYY |
| **Dataset version** | e.g. v0.3 (cedint_f1_hourly_clean.csv.gz) |
| **Cleaning steps** | Summary of data cleaning or selection rules applied |
| **Model tested** | Model architecture, algorithm, or process step |
| **Parameters tested** | Hyperparameters, split dates, features used, thresholds |
| **Results obtained** | Quantitative metrics (MAE, RMSE, CV(RMSE), NMBE, count of NaNs, etc.) |
| **Interpretation** | What the results mean for the project or forecasting goals |
| **Issues found** | Data anomalies, bugs, limitations, or metric failures |
| **Extras** | Subteam, responsible members, linked notebooks/scripts, backlog tasks |
