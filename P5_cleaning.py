# -*- coding: utf-8 -*-
"""
Created on Sun Oct  4 11:02:58 2026

@author: macat
"""

import numpy as np
import pandas as pd

# 1. Load ALL sheets from the raw Excel file
excel_path = "Storey1_SW_report_by_device.xlsx"
dfs_raw = pd.read_excel(excel_path, sheet_name=None)

# Dictionary to store processed results
dfs_processed = {}

print("Starting Task B2 processing...\n")

# 2. Loop through each sheet (each device type)
for sheet_name, df_raw in dfs_raw.items():
  print(f"--- Processing sheet: {sheet_name} ---")
  df_processed = df_raw.copy()

  # A. Extract the hour from the Timestamp (if the column exists)
  if "Timestamp" in df_processed.columns:
    df_processed["Timestamp"] = pd.to_datetime(df_processed["Timestamp"])
    df_processed["Hour"] = df_processed["Timestamp"].dt.hour

  # B. Rule: Temp = 0 or Hum = 0 -> NaN (missing value)
  if "Temp" in df_processed.columns:
    df_processed.loc[df_processed["Temp"] == 0, "Temp"] = np.nan

  if "Hum" in df_processed.columns:
    df_processed.loc[df_processed["Hum"] == 0, "Hum"] = np.nan

  # C. Rule: Lum = 0 checked by time of day (daytime between 7 AM and 7 PM)
  if "Lum" in df_processed.columns and "Hour" in df_processed.columns:
    is_daytime = (df_processed["Hour"] >= 7) & (df_processed["Hour"] <= 19)
    df_processed.loc[is_daytime & (df_processed["Lum"] == 0), "Lum"] = np.nan

  # D. Rule: Pres = 0 is "absent" only when Temp is present
  if "Pres" in df_processed.columns and "Temp" in df_processed.columns:
    temp_is_present = df_processed["Temp"].notna()
    df_processed.loc[
        (df_processed["Pres"] == 0) & temp_is_present, "Pres"
    ] = np.nan

  # Store the cleaned dataframe
  dfs_processed[sheet_name] = df_processed

  # Display a summary of the created NaNs (useful for your anomalies report!)
  cols_to_check = [
      c for c in ["Temp", "Hum", "Lum", "Pres"] if c in df_processed.columns
  ]
  print("Number of values transformed into NaN:")
  print(df_processed[cols_to_check].isna().sum())
  print("\n")

# 3. Save all cleaned sheets into a new "processed" Excel file
output_path = "dataset_processed_tache_B2.xlsx"
with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
  for sheet_name, df_proc in dfs_processed.items():
    df_proc.to_excel(writer, sheet_name=sheet_name, index=False)

print(f"Task B2 completed successfully! File saved as: {output_path}")