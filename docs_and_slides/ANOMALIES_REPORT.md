# Data Quality Report - Task B2 (P5)

This report documents the application of cleaning rules and the identification of technical artifacts (failure zeros) on the environmental sensors of the dataset.

## 1. Applied Rules (Hypothesis B2)
- **Temperature & Humidity:** Conversion of values equal to `0` to `NaN` (physically impossible values indoors, indicating a sensor outage or failure).
- **Luminosity:** Conversion of zeros to `NaN` only during daytime (between 7:00 AM and 7:00 PM).
- **Pressure:** Conversion of zeros to `NaN` if the associated temperature is present.
- 
## 2. Test Conditions & Validation Approach
- **Pilot Dataset:** Testing and rule verification were initially conducted and validated on a pilot dataset (`Storey1_SW_report_by_device.xlsx`) to ensure boundary conditions and physical logic behaved as expected.
- **Scalability:** Once validated on this primary file, the Python script uses a multi-sheet dictionary iteration (`pandas`) to seamlessly replicate the cleaning pipeline across all remaining floor datasets.
- 
## 3. Quantitative Summary by Sheet (NaN Values Created)
| Sheet (Device) | Temperature (NaN) | Humidity (NaN) | Luminosity (NaN) | Pressure (NaN) |
| :--- | :--- | :--- | :--- | :--- |
| **Emerg. Lighting** | 2035 | 2036 |13597 | 22293|
| **Lighting** | 2537| 2538| 16327|22801 |
| **Hand Dryer** | 2083 |2083 |13861| 22161 |
| **Plugs & Sockets** | 2267 | 2267 | 14786 | 22421 |
| **RACK** | | 23|23 |1217| 10923 |

## 4. Observations and Analysis
-Environmental stability: Temperature and Humidity sensors show consistent and reliable behavior across all zones 

Sensor failure / Unreliability: Luminosity and Pressure sensors exhibit a massive amount of technical artifacts (up to 22,000+ NaNs in Pressure). This strongly indicates that pressure and light sensors are either highly prone to disconnections, uncalibrated, or prone to default-zero locking across the building's subsystems.
