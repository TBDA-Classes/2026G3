"""
CeDInt floor 1 - data cleaning pipeline (TBDA, Team B: Data Quality & Validation)

Principle: NOTHING IS DELETED. Raw values are kept in *_raw columns, problems are
marked with 0/1 flag columns, and only the *clean* columns set a value to NaN
when a rule says the raw value cannot be trusted.

Input : the four Storey1_<zone>_report_by_device.xlsx files (18 sheets)
Output: hourly clean table (long format), minute-level flagged table (2025),
        anomaly event log, per-series quality overview, consistency checks.

Run   : python clean_cedint.py <folder_with_xlsx_files> <output_folder>
"""
import sys, glob, os, re
import numpy as np
import pandas as pd

RAW_DIR = sys.argv[1] if len(sys.argv) > 1 else "raw"
OUT_DIR = sys.argv[2] if len(sys.argv) > 2 else "cleaned"
os.makedirs(OUT_DIR, exist_ok=True)

ERA_SPLIT = pd.Timestamp("2024-01-01")          # hourly era < split <= minute era
LOOKAHEAD = {"hourly": 6, "minute": 60}          # rows to look ahead for a counter dip to recover
SHORT_GAP_H = 3                                   # gaps <= 3 h may be interpolated in the model column
NOISE_W = 5.0                                     # |negative power| up to 5 W = meter noise around 0
TEMP_IMPOSSIBLE = (0.0, 50.0)                     # outside -> sensor error (NaN in clean column)
TEMP_EXTREME = (10.0, 35.0)                       # outside (but possible) -> flag only
HUM_VALID = (5.0, 95.0)
DAY_HOURS_UTC = range(10, 16)                     # hours where Lum = 0 is suspicious (UTC)
EXCLUDE = {("SE", "Projector"): "100% zeros: no information"}


# ---------------------------------------------------------------- 1. load
def load_raw(raw_dir):
    frames = {}
    for f in sorted(glob.glob(os.path.join(raw_dir, "*Storey1_*_report_by_device.xlsx"))):
        zone = re.search(r"Storey1_(\w\w)_", f).group(1)
        for sheet, d in pd.read_excel(f, sheet_name=None).items():
            d = d.rename(columns={"E Device type": "load_type", "Number of Edevices": "n_devices"})
            d["t"] = pd.to_datetime(d["Timestamp"])
            d = d.sort_values("t").drop_duplicates("t").reset_index(drop=True)
            frames[(zone, sheet)] = d
    return frames


# ---------------------------------------------------------------- 2. counter validation
def classify_counter(er, lookahead, tol, cap):
    """Walk through the cumulative counter and label every row:
    ok          normal reading
    zero_record all electrical values written as 0 (missing record)
    partial     counter dips and comes back within `lookahead` rows -> some devices missing in the sum
    spike       counter jumps up by more than `cap` and falls back -> corrupt reading
    reset       counter drops and stays low -> real reset, a new counter segment starts
    Small decreases (< tol) are meter noise and are accepted as ok."""
    n = len(er)
    status = np.empty(n, dtype=object)
    seg = np.zeros(n, dtype=int)
    ref, s = None, 0
    typical_zero = np.nanmedian(np.abs(er)) < 1  # series whose counter is genuinely ~0
    for i in range(n):
        v = er[i]
        if np.isnan(v) or (v == 0 and not typical_zero):
            status[i] = "zero_record"; seg[i] = s; continue
        if ref is None:
            ref = v; status[i] = "ok"; seg[i] = s; continue
        fut = er[i + 1:i + 1 + lookahead]
        fut = fut[~np.isnan(fut) & (fut != 0)]
        if v < ref - tol:                                    # counter went down
            if fut.size and (fut >= ref - tol).any():
                status[i] = "partial"                        # comes back -> devices missing in sum
            else:
                s += 1; ref = v; status[i] = "reset"         # stays low -> real reset
        elif v > ref + cap and fut.size and (fut < v - tol).any() and (fut <= ref + cap).any():
            status[i] = "spike"                              # jumps up and falls back
        else:
            status[i] = "ok"; ref = v
        seg[i] = s
    return status, seg


# ---------------------------------------------------------------- 3. per-series cleaning
def clean_series(zone, sheet, d):
    load = sheet
    d = d.copy()
    d["era"] = np.where(d["t"] < ERA_SPLIT, "hourly", "minute")
    excluded = EXCLUDE.get((zone, load))

    # 3a sign: a series that is negative most of the time has a reversed current clamp
    reversed_sign = (d["W"] < 0).mean() > 0.9
    sign = -1.0 if reversed_sign else 1.0
    for c in ["W", "Pa", "I", "Er", "Ea"]:
        d[c + "_s"] = d[c].astype(float) * sign

    # 3b counter status per era
    d["counter_status"] = "ok"
    d["segment"] = 0
    for era, g in d.groupby("era"):
        step = g["Er_s"].diff().abs()
        tol = max(NOISE_W, 0.5 * step[step > 0].median()) if (step > 0).any() else NOISE_W
        if era == "hourly":
            # hourly era: rows are hourly averages -> walk the counter row by row
            cap = 3 * max(g["W_s"].abs().quantile(0.995), 1.0) + 10
            st, sg = classify_counter(g["Er_s"].to_numpy(float), LOOKAHEAD[era], tol, cap)
            d.loc[g.index, "counter_status"] = st
            d.loc[g.index, "segment"] = sg
        else:
            # minute era: each row sums only the devices that reported in that minute.
            # The most complete sum is the upper envelope of the counter (rolling max over +-30 min).
            # A minute is complete if its counter is within (noise + 1 h of consumption) of that envelope.
            # A level only counts for the envelope if >= 3 readings within +-30 rows confirm it,
            # so one isolated corrupt reading cannot lift the envelope.
            er = g["Er_s"].astype(float)
            typical_zero = er.abs().median() < 1
            zero = er.isna() | ((er == 0) & (not typical_zero))
            x = er.where(~zero).to_numpy()
            band = tol + 3 * max(g["W_s"].abs().quantile(0.995), 1.0) + 10
            W = 30
            pad = np.r_[np.full(W, np.nan), x, np.full(W, np.nan)]
            win = np.lib.stride_tricks.sliding_window_view(pad, 2 * W + 1)          # n x 61
            support = (np.abs(win - x[:, None]) <= band).sum(axis=1)                 # readings at ~same level
            cand = np.where(support >= 3, x, np.nan)
            padc = np.r_[np.full(W, np.nan), cand, np.full(W, np.nan)]
            with np.errstate(all="ignore"):
                env = np.nanmax(np.lib.stride_tricks.sliding_window_view(padc, 2 * W + 1), axis=1)
            st = np.where(zero, "zero_record",
                 np.where(np.isnan(env), "unconfirmed",
                 np.where(x > env + band, "spike",
                 np.where(x >= env - band, "ok", "partial"))))
            d.loc[g.index, "counter_status"] = st
            d.loc[g.index, "segment"] = 1000

    bad_elec = d["counter_status"].isin(["zero_record", "partial", "spike", "unconfirmed"])
    # power columns: NaN where the row is a zero-record or a partial sum
    for c in ["W_s", "Pa_s", "I_s"]:
        d.loc[bad_elec, c] = np.nan
    # negative power that is only noise around 0 -> clip to 0 ; larger negatives -> NaN
    neg_noise = (d["W_s"] < 0) & (d["W_s"] >= -NOISE_W)
    neg_large = d["W_s"] < -NOISE_W
    d.loc[neg_noise, "W_s"] = 0.0
    d.loc[neg_large, "W_s"] = np.nan
    d["flag_neg_noise"] = neg_noise.astype(int)
    d["flag_neg_large"] = neg_large.astype(int)
    d.loc[d["Pa_s"] < 0, "Pa_s"] = np.nan
    d.loc[d["I_s"] < 0, "I_s"] = np.nan

    # 3c environment (zone-level, identical on all sheets of a zone)
    env_missing = (d["Temp"] == 0) & (d["Hum"] == 0)
    d["temp_c"] = d["Temp"].where(~env_missing)
    d["hum_pct"] = d["Hum"].where(~env_missing)
    d["lum_lux"] = d["Lum"].where(~env_missing)
    d["occupancy"] = d["Pres"].where(~env_missing).astype(float)
    temp_impossible = d["temp_c"].notna() & ~d["temp_c"].between(*TEMP_IMPOSSIBLE)
    temp_extreme = d["temp_c"].notna() & ~temp_impossible & ~d["temp_c"].between(*TEMP_EXTREME)
    d.loc[temp_impossible, "temp_c"] = np.nan
    hum_bad = d["hum_pct"].notna() & ~d["hum_pct"].between(*HUM_VALID)
    d.loc[hum_bad, "hum_pct"] = np.nan
    lum_day_zero = (d["lum_lux"] == 0) & d["t"].dt.hour.isin(DAY_HOURS_UTC)
    d["flag_env_missing"] = env_missing.astype(int)
    d["flag_temp_impossible"] = temp_impossible.astype(int)
    d["flag_temp_extreme"] = temp_extreme.astype(int)
    d["flag_hum_invalid"] = hum_bad.astype(int)
    d["flag_lum_day_zero"] = lum_day_zero.astype(int)

    d["zone"], d["load_type"], d["reversed_sign"], d["excluded"] = zone, load, int(reversed_sign), excluded or ""
    return d


# ---------------------------------------------------------------- 4. to hourly grid
def to_hourly(d):
    """Hourly era: 1 row per hour already (Graphite hourly averages).
    Minute era: average of the *complete* minutes in [t, t+1h).
    Then reindex to a full hourly grid inside each era (missing hours = new rows, flag_missing_hour=1)."""
    d = d.copy()
    d["hour"] = d["t"].dt.floor("1h")
    d["valid_counter"] = d["Er_s"].where(d["counter_status"].isin(["ok", "reset"]))
    agg = d.groupby(["era", "hour"]).agg(
        source_rows=("t", "size"),
        complete_rows=("counter_status", lambda s: int(s.isin(["ok", "reset"]).sum())),
        power_w_raw=("W", "mean"),
        power_w=("W_s", "mean"),
        apparent_power_va=("Pa_s", "mean"),
        current_a=("I_s", "mean"),
        counter_wh=("valid_counter", "mean"),
        counter_wh_raw=("Er", "mean"),
        segment=("segment", "max"),
        n_zero_record=("counter_status", lambda s: int((s == "zero_record").sum())),
        n_partial=("counter_status", lambda s: int((s == "partial").sum())),
        n_reset=("counter_status", lambda s: int((s == "reset").sum())),
        n_spike=("counter_status", lambda s: int((s == "spike").sum())),
        n_neg_noise=("flag_neg_noise", "sum"),
        n_neg_large=("flag_neg_large", "sum"),
        temp_c=("temp_c", "mean"), hum_pct=("hum_pct", "mean"),
        lum_lux=("lum_lux", "mean"), occupancy=("occupancy", "mean"),
        flag_env_missing=("flag_env_missing", "max"),
        flag_temp_impossible=("flag_temp_impossible", "max"),
        flag_temp_extreme=("flag_temp_extreme", "max"),
        flag_hum_invalid=("flag_hum_invalid", "max"),
        flag_lum_day_zero=("flag_lum_day_zero", "max"),
    ).reset_index()
    # env in an hour where every minute was missing -> mean is NaN already; if some minutes missing keep mean
    cap = 3 * max(agg["power_w"].abs().quantile(0.995), 1.0) + 10   # Wh per hour, whole series
    out = []
    for era, g in agg.groupby("era"):
        g = g.set_index("hour")
        grid = pd.date_range(g.index.min(), g.index.max(), freq="1h")
        g = g.reindex(grid)
        g["era"] = era
        g["flag_missing_hour"] = g["source_rows"].isna().astype(int)
        g["source_rows"] = g["source_rows"].fillna(0).astype(int)
        g["complete_rows"] = g["complete_rows"].fillna(0).astype(int)
        for c in ["n_zero_record", "n_partial", "n_reset", "n_spike", "n_neg_noise", "n_neg_large"]:
            g[c] = g[c].fillna(0).astype(int)
        # The counter value of hour t is the average over [t, t+1), i.e. the counter at ~t+30 min.
        # Energy used in [t, t+1) = (C(t+1) - C(t-1)) / 2  (centred difference; tested: best match with power).
        # If a neighbour is missing or in another counter segment, fall back to a one-sided difference.
        C, S = g["counter_wh"], g["segment"]
        same_n, same_p = S.shift(-1) == S, S.shift(1) == S
        cen = ((C.shift(-1) - C.shift(1)) / 2).where(same_n & same_p)
        fwd = (C.shift(-1) - C).where(same_n)
        bwd = (C - C.shift(1)).where(same_p)
        e = cen.fillna(fwd).fillna(bwd)
        method = np.where(cen.notna(), "counter_centred",
                 np.where(fwd.notna() | bwd.notna(), "counter_one_sided", None))
        g["flag_counter_reset"] = ((~same_n) & S.shift(-1).notna() & S.notna()).astype(int)
        # plausibility of energy: between 0 and 3x the series' p99.5 power (+10 Wh slack)
        jump = e.notna() & ((e < -1) | (e > cap))
        g["flag_energy_implausible"] = jump.astype(int)
        e = e.where(~jump).clip(lower=0)
        g["energy_wh"] = e
        g["energy_method"] = np.where(e.notna(), method, None)
        out.append(g.rename_axis("timestamp_utc").reset_index())
    h = pd.concat(out, ignore_index=True)
    h["flag_partial_sum"] = (h["n_partial"] > 0).astype(int)
    h["flag_zero_record"] = (h["n_zero_record"] > 0).astype(int)
    h["flag_counter_spike"] = (h["n_spike"] > 0).astype(int)
    h["flag_neg_noise"] = (h["n_neg_noise"] > 0).astype(int)
    h["flag_neg_large"] = (h["n_neg_large"] > 0).astype(int)
    # minute era: an hour with fewer than 10 complete minutes is not representative
    low_cov = (h["era"] == "minute") & (h["complete_rows"] < 10)
    h["flag_low_coverage"] = low_cov.astype(int)
    for c in ["power_w", "apparent_power_va", "current_a"]:
        h.loc[low_cov, c] = np.nan

    # power spike: Hampel filter (24 h window, 8 robust SD) -> flag only
    med = h["power_w"].rolling(25, center=True, min_periods=6).median()
    mad = (h["power_w"] - med).abs().rolling(25, center=True, min_periods=6).median()
    scale = max(h["power_w"].quantile(0.99), 1.0)
    dev = (h["power_w"] - med).abs()
    h["flag_power_spike"] = ((dev > 8 * 1.4826 * mad.clip(lower=1)) & (dev > 0.5 * scale)).astype(int)

    # model-ready energy: counter -> else power x 1 h -> else short-gap interpolation
    em = h["energy_wh"].copy()
    src = pd.Series(np.where(em.notna(), h["energy_method"], None), index=h.index, dtype=object)
    use_p = em.isna() & h["power_w"].notna()
    em[use_p] = h.loc[use_p, "power_w"]; src[use_p] = "power"
    filled = em.groupby(h["era"]).transform(lambda s: s.interpolate(limit=SHORT_GAP_H, limit_area="inside"))
    interp = em.isna() & filled.notna()
    em[interp] = filled[interp]; src[interp] = "interpolated"
    h["energy_wh_model"], h["energy_source"] = em, src
    # agreement between counter energy and power x 1h (consistency check)
    both = h["energy_wh"].notna() & h["power_w"].notna()
    dev = (h["energy_wh"] - h["power_w"]).abs()
    tol_pe = np.maximum(0.2 * h["power_w"].abs(), 0.05 * max(h["power_w"].quantile(0.99), 1.0))
    h["flag_power_energy_mismatch"] = (both & (dev > tol_pe)).astype(int)
    return h


# ---------------------------------------------------------------- 5. event log
def events(h, zone, load):
    """Compress hourly flags into events (start, end, hours) for the anomaly log."""
    rows = []
    checks = {
        "missing_hour": "flag_missing_hour", "zero_record": "flag_zero_record",
        "partial_sum": "flag_partial_sum", "counter_reset": "flag_counter_reset",
        "energy_implausible": "flag_energy_implausible", "counter_spike": "flag_counter_spike", "negative_large": "flag_neg_large",
        "env_missing": "flag_env_missing", "temp_impossible": "flag_temp_impossible",
        "temp_extreme": "flag_temp_extreme", "power_spike": "flag_power_spike",
        "low_coverage_minute_hour": "flag_low_coverage",
    }
    for name, col in checks.items():
        f = h[col].fillna(0).astype(int).to_numpy()
        if not f.any():
            continue
        grp = (np.diff(np.r_[0, f]) == 1).cumsum() * f
        for gid in np.unique(grp[grp > 0]):
            idx = np.where(grp == gid)[0]
            rows.append(dict(zone=zone, load_type=load, anomaly=name,
                             start_utc=h["timestamp_utc"].iloc[idx[0]], end_utc=h["timestamp_utc"].iloc[idx[-1]],
                             hours=len(idx), era=h["era"].iloc[idx[0]]))
    return rows


# ---------------------------------------------------------------- 6. quality overview + consistency checks
def consistency(H):
    """F6.2 - physical plausibility checks per series and era (only on hours where both values exist)."""
    rows = []
    for (z, l, era), g in H.groupby(["zone", "load_type", "era"]):
        if g["series_excluded"].iloc[0]:
            continue
        both = g["energy_wh"].notna() & g["power_w"].notna()
        dev = (g["energy_wh"] - g["power_w"]).abs()
        tol_pe = np.maximum(0.2 * g["power_w"].abs(), 0.05 * max(g["power_w"].quantile(0.99), 1.0))
        pe_pass = (dev[both] <= tol_pe[both]).mean()
        pa = g["apparent_power_va"].notna() & g["power_w"].notna() & (g["power_w"] > 1)
        app_pass = (g.loc[pa, "apparent_power_va"] >= 0.99 * g.loc[pa, "power_w"]).mean()
        pf = (g.loc[pa, "power_w"] / g.loc[pa, "apparent_power_va"].replace(0, np.nan))
        pf_pass = pf.between(0, 1.01).mean()
        ci = g["current_a"].notna() & g["apparent_power_va"].notna()
        r_ci = g.loc[ci, "current_a"].corr(g.loc[ci, "apparent_power_va"]) if ci.sum() > 30 else np.nan
        r_pe = g.loc[both, "energy_wh"].corr(g.loc[both, "power_w"]) if both.sum() > 30 else np.nan
        rows.append(dict(zone=z, load_type=l, era=era, hours_checked=int(both.sum()),
                         power_vs_energy_pass=round(pe_pass, 3), power_vs_energy_r=round(r_pe, 3),
                         apparent_ge_active_pass=round(app_pass, 3), power_factor_0_1_pass=round(pf_pass, 3),
                         current_vs_apparent_r=round(r_ci, 3),
                         median_power_factor=round(pf.median(), 2) if pf.notna().any() else np.nan))
    return pd.DataFrame(rows)


def quality_overview(H, cons):
    rows = []
    for (z, l, era), g in H.groupby(["zone", "load_type", "era"]):
        c = cons[(cons.zone == z) & (cons.load_type == l) & (cons.era == era)]
        pe = c["power_vs_energy_pass"].iloc[0] if len(c) else np.nan
        has = 1 - g["flag_missing_hour"].mean()
        e_ok = g["energy_wh"].notna().mean()
        p_ok = g["power_w"].notna().mean()
        if g["series_excluded"].iloc[0]:
            rec, why = "Do not use", "series is 100% zeros"
        elif e_ok >= 0.8 and (pe >= 0.8 or np.isnan(pe)):
            rec, why = "Use", "high coverage and power/energy agree"
        elif e_ok >= 0.6 and (pe >= 0.6 or np.isnan(pe)):
            why = []
            if e_ok < 0.8: why.append(f"only {e_ok:.0%} of hours have a valid energy value")
            if pe < 0.8: why.append(f"power and energy agree in only {pe:.0%} of hours")
            rec, why = "Use with caution", "; ".join(why)
        else:
            why = []
            if e_ok < 0.6: why.append(f"only {e_ok:.0%} of hours have a valid energy value")
            if pe < 0.6: why.append(f"power and energy agree in only {pe:.0%} of hours")
            rec, why = "Do not use", "; ".join(why)
        rows.append(dict(zone=z, load_type=l, era=era, n_devices=int(g["n_devices"].iloc[0]),
                         first_hour_utc=g["timestamp_utc"].min(), last_hour_utc=g["timestamp_utc"].max(),
                         hours_in_grid=len(g), pct_hours_with_data=round(has, 3),
                         pct_valid_power=round(p_ok, 3), pct_valid_energy=round(e_ok, 3),
                         pct_model_ready=round(g["energy_wh_model"].notna().mean(), 3),
                         pct_partial_sum_hours=round(g["flag_partial_sum"].mean(), 3),
                         pct_zero_record_hours=round(g["flag_zero_record"].mean(), 3),
                         counter_resets=int(g["flag_counter_reset"].sum()),
                         energy_implausible_hours=int(g["flag_energy_implausible"].sum()),
                         pct_env_missing=round(g["flag_env_missing"].mean(), 3),
                         reversed_sign=int(g["reversed_sign"].iloc[0]),
                         power_vs_energy_pass=pe, recommendation=rec, reason=why))
    return pd.DataFrame(rows)


SERIES_LEVEL = [
    ("SE", "Projector", "dead_series", "All values are 0 in both periods", "Excluded from analysis; ask whether the meter is connected"),
    ("NW", "Emerg. Lighting", "reversed_clamp", "Power, current and counters negative ~98-100% of the time", "Sign flipped (x -1); flag reversed_sign = 1; ask facilities to check the clamp"),
    ("SW", "RACK", "series_ends", "Data stop on 2021-12-03 17:00; no data in 2022-2023 or 2025", "Use only Apr 2020 - Dec 2021"),
    ("NE", "(zone)", "no_env_sensors", "Temp, Hum, Lum and Pres are 0 in every row", "Env columns empty (NaN); use NW or outdoor weather as proxy"),
    ("SW", "(zone)", "temp_sensor_error", "Temp around 850 C on several days in March 2022", "Values outside 0-50 C set to NaN in temp_c; raw kept"),
    ("All", "(all)", "retention_gap", "No data between 2023-02-28 23:00 and 2025-08-18 18:00 (902 days)", "Two separate periods; never interpolate across"),
    ("All", "(all)", "timestamps_utc", "No missing/duplicate hour at DST changes; daylight 05-19 h in June and 08-16 h in December", "Timestamps treated as UTC; timestamp_local added for calendar features"),
    ("SE, SW", "(all)", "asynchronous_device_reports", "In the minute data each row sums only the devices that reported in that minute (counter jumps between levels)", "Only complete minutes used; SW minute data not usable"),
]


# ---------------------------------------------------------------- 7. write deliverables
DICTIONARY = [
    ("timestamp_utc", "datetime", "Start of the hour in UTC (raw timestamps are UTC: no DST gaps, daylight 05-19 h in June)."),
    ("timestamp_local", "datetime", "Same hour in Europe/Madrid local time - use for hour-of-day, weekday and holiday features."),
    ("zone / zone_code", "text", "Floor-1 orientation zone (NE, NW, SE, SW) and code 1NE ... 1SW."),
    ("load_type", "text", "Sheet name = load type (HVAC, Lighting, Plugs & Sockets, Emerg. Lighting, Hand Dryer, RACK, Projector)."),
    ("n_devices", "count", "Number of devices summed in the series (column 'Number of Edevices')."),
    ("era", "text", "hourly = Apr 2020 - Feb 2023 (Graphite hourly averages); minute = Aug - Oct 2025 (aggregated here to hours)."),
    ("recommendation", "text", "Use / Use with caution / Do not use, per series and era (see sheet Series_quality)."),
    ("usable_for_model", "0/1", "1 if recommendation is not 'Do not use'."),
    ("energy_wh_model", "Wh", "MODEL TARGET. Energy in the hour: counter value, else power x 1 h, else linear interpolation for gaps <= 3 h. Empty if not usable."),
    ("energy_source", "text", "Where energy_wh_model comes from: counter_centred, counter_one_sided, power, interpolated."),
    ("energy_wh", "Wh", "Energy in the hour from the active-energy counter Er (centred difference, same counter segment, plausibility-checked)."),
    ("energy_method", "text", "counter_centred = (C(t+1)-C(t-1))/2 ; counter_one_sided = neighbour missing."),
    ("power_w", "W", "Clean active power (hourly average). NaN for zero records, partial sums, large negatives, low-coverage minute hours."),
    ("power_w_raw", "W", "Raw W (hourly era) or mean of all raw minutes (minute era), before any rule. Never changed."),
    ("apparent_power_va, current_a", "VA, A", "Clean apparent power (Pa) and current (I), same rules as power_w."),
    ("counter_wh / counter_wh_raw", "Wh", "Clean (valid readings only) and raw hourly mean of the Er counter, after sign correction for the clean one."),
    ("segment", "id", "Counter segment; a new segment starts after a real reset. Energy is never computed across segments."),
    ("temp_c, hum_pct, lum_lux", "degC, %, lux", "Zone-level indoor environment. NaN if Temp = Hum = 0 (missing), Temp outside 0-50 C, Hum outside 5-95 %."),
    ("occupancy", "0-1", "Raw 'Pres' = presence (0/1), not pressure. Hourly mean = share of the hour occupied. NaN if env missing."),
    ("source_rows / complete_rows", "count", "Raw rows in the hour / rows whose counter was complete (minute era: devices all reported)."),
    ("n_zero_record, n_partial, n_reset, n_spike, n_neg_noise, n_neg_large", "count", "Number of raw rows in the hour with that problem."),
    ("flag_missing_hour", "0/1", "No raw row for this hour; the row was added to complete the hourly grid."),
    ("flag_zero_record", "0/1", "W, Pa, Er and Ea all exactly 0 (missing record written as zeros)."),
    ("flag_partial_sum", "0/1", "Hourly era: the row sums only part of the devices (counter dips and recovers). Minute era: >= 1 partial minute was excluded."),
    ("flag_counter_spike", "0/1", "Counter jumped up and fell back (corrupt reading)."),
    ("flag_counter_reset", "0/1", "Counter dropped and stayed low after this hour (real reset; energy not computed across it)."),
    ("flag_energy_implausible", "0/1", "Energy < 0 or > 3 x the series' 99.5th percentile power; set to NaN."),
    ("flag_neg_noise / flag_neg_large", "0/1", "Negative power between -5 and 0 W (set to 0) / below -5 W (set to NaN)."),
    ("reversed_sign", "0/1", "Whole series negative (reversed current clamp); all electrical columns multiplied by -1."),
    ("flag_low_coverage", "0/1", "Minute era: fewer than 10 complete minutes in the hour; power set to NaN."),
    ("flag_power_spike", "0/1", "Hampel filter: power far from the 25 h rolling median. Flag only, value kept."),
    ("flag_power_energy_mismatch", "0/1", "Energy and power x 1 h differ by more than 20 % (or 5 % of the series' peak). Flag only."),
    ("flag_env_missing", "0/1", "Temp = Hum = 0: environmental reading missing."),
    ("flag_temp_impossible", "0/1", "Temp outside 0-50 C (e.g. ~850 C in SW, Mar 2022): set to NaN."),
    ("flag_temp_extreme", "0/1", "Temp < 10 C or > 35 C but physically possible (Jan 2021 cold, Aug 2021 heat wave): kept."),
    ("flag_hum_invalid", "0/1", "Humidity outside 5-95 %: set to NaN."),
    ("flag_lum_day_zero", "0/1", "Lum = 0 between 10 and 16 h UTC (suspicious, kept; zeros at night are real darkness)."),
    ("series_excluded", "0/1", "Series not used at all (SE Projector: 100 % zeros)."),
]

HOURLY_COLS = ["timestamp_utc", "timestamp_local", "zone", "zone_code", "load_type", "n_devices", "era",
               "recommendation", "usable_for_model", "energy_wh_model", "energy_source", "energy_wh", "energy_method",
               "power_w", "apparent_power_va", "current_a", "power_w_raw", "counter_wh", "counter_wh_raw", "segment",
               "temp_c", "hum_pct", "lum_lux", "occupancy", "source_rows", "complete_rows",
               "flag_missing_hour", "flag_zero_record", "flag_partial_sum", "flag_counter_spike", "flag_counter_reset",
               "flag_energy_implausible", "flag_neg_noise", "flag_neg_large", "reversed_sign", "flag_low_coverage",
               "flag_power_spike", "flag_power_energy_mismatch", "flag_env_missing", "flag_temp_impossible",
               "flag_temp_extreme", "flag_hum_invalid", "flag_lum_day_zero", "series_excluded",
               "n_zero_record", "n_partial", "n_reset", "n_spike", "n_neg_noise", "n_neg_large"]

README = [
    "CeDInt floor 1 - cleaned hourly data (TBDA DataPack, Team B: Data Quality & Validation)",
    "",
    "WHAT THIS IS",
    "One row per hour x zone x load type, for 2020-04-02 to 2023-02-28 (era 'hourly') and 2025-08-18 to 2025-10-13 (era 'minute', aggregated to hours).",
    "Built from the 4 raw Storey1_<zone>_report_by_device.xlsx files with clean_cedint.py. Raw files are never edited.",
    "",
    "NOTHING IS DELETED",
    "Every raw value is kept (power_w_raw, counter_wh_raw, and the minute file). Problems get a 0/1 flag column.",
    "Only the clean columns (power_w, energy_wh, temp_c, ...) are set to empty when a rule says the raw value cannot be trusted.",
    "Hours without any raw row are ADDED (flag_missing_hour = 1) so every series has a complete hourly grid inside each era.",
    "",
    "HOW TO USE IT",
    "1. Forecast target: energy_wh_model (Wh per hour). Use rows with usable_for_model = 1.",
    "2. Check the recommendation per series in sheet Series_quality before using a series.",
    "3. Use timestamp_local for calendar features (hour, weekday, holidays). Timestamps in the raw data are UTC.",
    "4. Environmental data is per zone and is repeated on every load type of that zone. NE has no environmental sensors.",
    "5. 'occupancy' is the raw column 'Pres' (presence 0/1), NOT atmospheric pressure.",
    "6. Never interpolate across the 902-day gap (Mar 2023 - Aug 2025); treat the two eras as separate periods.",
    "",
    "FILES AND SHEETS",
"cedint_f1_hourly_clean.csv.gz   all zones in one long table (for Python / pandas)",
"cedint_f1_minute_2025_flagged.csv.gz   the raw 2025 minute rows with their counter status (complete / partial / zero_record ...)",
"CeDInt_F1_quality_and_anomalies.xlsx contains:",
    "Series_quality      per series and era: coverage, problems found, recommendation and reason",
    "Consistency_checks  F6.2 physical plausibility checks (power vs energy, apparent >= active, power factor, current vs apparent)",
    "Anomaly_summary     F7.2 number of anomaly events and hours per series and type",
    "Series_level_issues F7.2 problems that concern a whole series or zone",
    "Anomaly_log         every anomaly event with start and end hour (UTC)",
    "Data_dictionary     every column, unit and rule",
"Storey1_<zone>_cleaned_hourly.xlsx: README, Data_dictionary and one sheet per load type with the cleaned hourly data (same structure as the raw files)",
]


def write_outputs(H, qo, cons, ev, minute, out_dir):
    H = H[HOURLY_COLS].sort_values(["zone", "load_type", "timestamp_utc"])
    H.to_csv(os.path.join(out_dir, "cedint_f1_hourly_clean.csv.gz"), index=False, float_format="%.4f", compression="gzip")
    mcols = {"t": "timestamp_utc", "W": "W_raw", "Pa": "Pa_raw", "I": "I_raw", "Er": "Er_raw", "Ea": "Ea_raw",
             "W_s": "power_w_clean"}
    minute.rename(columns=mcols).to_csv(os.path.join(out_dir, "cedint_f1_minute_2025_flagged.csv.gz"),
                                        index=False, float_format="%.4f", compression="gzip")
    ev = ev.copy()
    env_types = ["env_missing", "temp_impossible", "temp_extreme"]
    is_env = ev["anomaly"].isin(env_types)
    env_ev = ev[is_env].sort_values("load_type").drop_duplicates(["zone", "anomaly", "start_utc", "end_utc"])
    env_ev["load_type"] = "(zone environment)"
    ev = pd.concat([ev[~is_env], env_ev]).sort_values(["zone", "load_type", "anomaly", "start_utc"])
    summ = ev.groupby(["zone", "load_type", "era", "anomaly"]).agg(events=("hours", "size"), hours=("hours", "sum"),
                                                                   first_utc=("start_utc", "min"), last_utc=("end_utc", "max")).reset_index()
    series_lvl = pd.DataFrame(SERIES_LEVEL, columns=["zone", "load_type", "issue", "evidence", "action"])
    dd = pd.DataFrame(DICTIONARY, columns=["column", "unit", "meaning / rule"])
    def fmt(xw, ws, df, width=14, freeze=(1, 0)):
        hdr = xw.book.add_format({"bold": True, "bg_color": "#E8EEF7", "text_wrap": True, "valign": "top"})
        ws.set_column(0, max(len(df.columns) - 1, 0), width)
        for j, c in enumerate(df.columns):
            ws.write(0, j, c, hdr)
        ws.freeze_panes(*freeze)
        ws.autofilter(0, 0, max(len(df), 1), max(len(df.columns) - 1, 0))

    readme = pd.DataFrame({"README": README})
    # (1) quality & anomaly workbook (small)
    path = os.path.join(out_dir, "CeDInt_F1_quality_and_anomalies.xlsx")
    with pd.ExcelWriter(path, engine="xlsxwriter") as xw:
        readme.to_excel(xw, sheet_name="README", index=False); xw.sheets["README"].set_column(0, 0, 140)
        for name, df, w in [("Series_quality", qo, 16), ("Consistency_checks", cons, 18),
                            ("Anomaly_summary", summ, 18), ("Series_level_issues", series_lvl, 45),
                            ("Anomaly_log", ev, 18), ("Data_dictionary", dd, 32)]:
            df.to_excel(xw, sheet_name=name, index=False)
            fmt(xw, xw.sheets[name], df, w)
        xw.sheets["Data_dictionary"].set_column(2, 2, 120)
        xw.sheets["Series_quality"].set_column(len(qo.columns) - 1, len(qo.columns) - 1, 75)
    # (2) one cleaned workbook per zone, one sheet per load type (same structure as the raw files)
    for z in ["NE", "NW", "SE", "SW"]:
        zp = os.path.join(out_dir, f"Storey1_{z}_cleaned_hourly.xlsx")
        with pd.ExcelWriter(zp, engine="xlsxwriter") as xw:
            readme.to_excel(xw, sheet_name="README", index=False); xw.sheets["README"].set_column(0, 0, 140)
            dd.to_excel(xw, sheet_name="Data_dictionary", index=False); fmt(xw, xw.sheets["Data_dictionary"], dd, 32)
            xw.sheets["Data_dictionary"].set_column(2, 2, 120)
            for l, df in H[H["zone"] == z].groupby("load_type"):
                sn = l.replace("&", "and").replace(".", "")[:31]
                df.to_excel(xw, sheet_name=sn, index=False)
                fmt(xw, xw.sheets[sn], df, 12, (1, 2))
                xw.sheets[sn].set_column(0, 1, 19)
    return path


# ---------------------------------------------------------------- main
if __name__ == "__main__":
    raw = load_raw(RAW_DIR)
    hourly, minute, ev, overview = [], [], [], []
    for (zone, sheet), d in raw.items():
        c = clean_series(zone, sheet, d)
        h = to_hourly(c)
        h.insert(1, "zone", zone); h.insert(2, "zone_code", "1" + zone)
        h.insert(3, "load_type", sheet); h.insert(4, "n_devices", int(d["n_devices"].iloc[0]))
        h["reversed_sign"] = c["reversed_sign"].iloc[0]
        h["series_excluded"] = int(bool(c["excluded"].iloc[0]))
        hourly.append(h)
        m = c[c["era"] == "minute"]
        if len(m):
            minute.append(m[["t", "zone", "load_type", "W", "Pa", "I", "Er", "Ea", "W_s", "counter_status",
                             "temp_c", "hum_pct", "lum_lux", "occupancy", "flag_env_missing",
                             "flag_temp_impossible", "flag_neg_noise", "flag_neg_large"]])
        ev += events(h, zone, sheet)
        print(f"done {zone} {sheet}: {len(h)} hourly rows")
    H = pd.concat(hourly, ignore_index=True)
    H["timestamp_local"] = H["timestamp_utc"].dt.tz_localize("UTC").dt.tz_convert("Europe/Madrid").dt.tz_localize(None)
    cons = consistency(H)
    qo = quality_overview(H, cons)
    usable = qo.set_index(["zone", "load_type", "era"])["recommendation"]
    H["recommendation"] = [usable[(z, l, e)] for z, l, e in zip(H["zone"], H["load_type"], H["era"])]
    H["usable_for_model"] = (H["recommendation"] != "Do not use").astype(int)
    H.loc[H["usable_for_model"] == 0, "energy_wh_model"] = np.nan
    H.loc[H["usable_for_model"] == 0, "energy_source"] = None
    cons.to_pickle(os.path.join(OUT_DIR, "consistency.pkl"))
    qo.to_pickle(os.path.join(OUT_DIR, "quality.pkl"))
    H.to_pickle(os.path.join(OUT_DIR, "hourly_clean.pkl"))
    MIN = pd.concat(minute, ignore_index=True)
    MIN.to_pickle(os.path.join(OUT_DIR, "minute_flagged.pkl"))
    EV = pd.DataFrame(ev)
    EV.to_pickle(os.path.join(OUT_DIR, "events.pkl"))
    print("writing deliverables ...")
    print("wrote", write_outputs(H, qo, cons, EV, MIN, OUT_DIR))
    print("hourly rows:", len(H))


