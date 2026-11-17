"""
CeDInt floor 1 - energy dashboard (TBDA DataPack, backlog T36 / F8.1)

Works with the clean dataset and any predictions file in the agreed format
(timestamp_utc, zone, load_type, model, split, y_true, y_pred).

Run:  python -m streamlit run T36_dashboard_app.py -- --data . --pred All_Zones_GBM_predictions.csv
"""
import argparse, os, sys
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ------------------------------------------------------------------ settings
p = argparse.ArgumentParser()
p.add_argument("--data", default=".", help="folder containing cleaned dataset")
p.add_argument("--pred", default="reference_baseline_predictions.csv.gz", help="predictions file (agreed format)")
args, _ = p.parse_known_args(sys.argv[1:])

ZONE_COLOR = {"NE": "#0284C7", "NW": "#EA580C", "SE": "#0D9488", "SW": "#4F46E5"}
ACTUAL, FORECAST = "#0F172A", "#EA580C"
REC_COLOR = {"Use": "#0D9488", "Use with caution": "#F59E0B", "Do not use": "#E11D48"}
TEMPLATE = dict(
    template="simple_white",
    font=dict(family="Inter, system-ui, -apple-system, Segoe UI, sans-serif", size=13, color="#0F172A"),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
)

st.set_page_config(page_title="CeDInt Energy Dashboard", page_icon="⚡", layout="wide")

# ------------------------------------------------------------------ custom styling
st.markdown("""
<style>
.stApp { background-color: #F8FAFC; }
.block-container { padding-top: 1.5rem; padding-bottom: 2.5rem; max-width: 1400px; }
section[data-testid="stSidebar"] { background-color: #FFFFFF; border-right: 1px solid #E2E8F0; }

.hero-banner {
    background: linear-gradient(120deg, #0F172A 0%, #115E59 65%, #0D9488 100%);
    padding: 1.4rem 1.8rem;
    border-radius: 14px;
    color: #FFFFFF;
    margin-bottom: 1.25rem;
    box-shadow: 0 4px 14px rgba(15, 23, 42, 0.08);
}
.hero-banner h1 { color: #FFFFFF !important; font-size: 1.75rem; font-weight: 700; margin: 0; padding: 0; }
.hero-banner p { color: #CBD5E1; margin: 0.35rem 0 0 0; font-size: 0.95rem; }

div[data-testid="stMetric"] {
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-left: 4px solid #0F766E;
    padding: 14px 18px;
    border-radius: 10px;
    box-shadow: 0 2px 6px rgba(15, 23, 42, 0.04);
}
[data-testid="stMetricLabel"] {
    font-size: 0.78rem; font-weight: 600; color: #64748B; text-transform: uppercase; letter-spacing: 0.04em;
}
[data-testid="stMetricValue"] { font-size: 1.55rem; font-weight: 700; color: #0F172A; }

div[data-baseweb="tab-list"] {
    gap: 8px; background-color: #FFFFFF; padding: 6px 10px; border-radius: 10px;
    border: 1px solid #E2E8F0; margin-bottom: 1rem;
}
button[data-baseweb="tab"] { font-size: 0.95rem; font-weight: 600; border-radius: 7px; padding: 8px 16px; }

.decision-box {
    background-color: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-left: 5px solid #0284C7;
    padding: 1rem 1.3rem;
    border-radius: 10px;
    margin: 0.8rem 0 1.2rem 0;
    box-shadow: 0 2px 6px rgba(15, 23, 42, 0.03);
}
.decision-box h4 { margin: 0 0 0.4rem 0; color: #0F172A; font-size: 1.02rem; }
.decision-box p { margin: 0.25rem 0; color: #334155; font-size: 0.92rem; line-height: 1.45; }
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------ domain helpers
def model_family(name):
    n = str(name).lower()
    if "naive" in n:
        return "Benchmark (Naive)"
    if "blend" in n or "hybrid" in n or "ensemble" in n:
        return "Hybrid (Time-Series + Drivers)"
    if any(k in n for k in ["chronos", "sarimax", "arima", "prophet"]):
        return "Univariate (History only)"
    return "Multivariate (Weather + Drivers)"


def evaluate_target(load_type, m, is_daily=False):
    lt = str(load_type)
    cv, nmbe, mae = m["CV_RMSE"], m["NMBE"], m["MAE"]
    if np.isnan(cv):
        return "N/A", "Insufficient data"
    if "RACK" in lt or "Emerg" in lt:
        ok = cv <= 15
        return ("✓ On target (≤ 15%)" if ok else "⚠ Above 15% target"), "Constant base-load target: CV(RMSE) ≤ 15%"
    if "Plugs" in lt:
        ok = cv <= 30
        return ("✓ On target (≤ 30%)" if ok else "⚠ Above 30% target"), "Office equipment target: CV(RMSE) ≤ 30%"
    if "HVAC" in lt:
        ok = (cv <= 50) and (abs(nmbe) <= 10)
        return ("✓ On target (≤ 50%)" if ok else "⚠ Outside HVAC band"), "HVAC target: CV(RMSE) 30–50% & |NMBE| ≤ 10%"
    if "Lighting" in lt:
        unit = "kWh/day" if is_daily else "Wh/h"
        return f"Daily MAE: {mae:,.2f} {unit}", "Lighting judged on daily energy MAE & switch-on timing"
    ok = (cv <= 30) and (abs(nmbe) <= 10)
    return ("✓ Within ASHRAE 14" if ok else "⚠ Above reference"), "ASHRAE 14 reference: CV(RMSE) ≤ 30% & |NMBE| ≤ 10%"


def operational_guidance(load_type, m, skill):
    lt = str(load_type)
    if "HVAC" in lt:
        action = "Pre-cool or pre-heat the zone ahead of peak tariff hours and align chiller/boiler schedules with forecasted outdoor temperature."
    elif "Lighting" in lt:
        action = "Verify automated twilight/occupancy schedules and flag unexpected evening or holiday lighting loads."
    elif "Plugs" in lt:
        action = "Identify standby phantom loads left running over weekends/holidays and schedule smart-plug power-downs."
    elif "RACK" in lt or "Emerg" in lt:
        action = "Monitor continuous base-load stability to detect server cooling anomalies or hardware degradation early."
    else:
        action = "Use day-ahead floor totals to optimize tariff contracting and facility maintenance windows."

    if pd.notna(m["NMBE"]) and abs(m["NMBE"]) > 10:
        direction = "over-predicting" if m["NMBE"] < 0 else "under-predicting"
        loop = (f"<b>Bias alert (NMBE {m['NMBE']:+.1f}%):</b> Systematic level shift detected ({direction}). "
                f"<i>Next step:</i> Apply rolling-window recalibration to adapt to recent occupancy/equipment changes.")
    elif pd.notna(skill) and skill <= 0:
        loop = ("<b>Skill alert:</b> Model does not beat the naive yesterday baseline on this slice. "
                "<i>Next step:</i> Combine time-series history with weather/calendar drivers via the Hybrid Blend model.")
    else:
        loop = ("<b>Closed-loop value:</b> Forecast beats naive baseline with controlled bias. "
                "<i>Next step:</i> Feed daily residuals back into weekly drift monitoring and multi-day (T37) planning.")
    return action, loop


# ------------------------------------------------------------------ data
@st.cache_data(show_spinner="Loading clean dataset …")
def load_clean(folder):
    cols = ["timestamp_utc", "timestamp_local", "zone", "load_type", "n_devices", "era", "recommendation",
            "usable_for_model", "energy_wh_model", "temp_c", "hum_pct", "lum_lux", "occupancy",
            "is_holiday", "is_weekend", "flag_missing_hour", "series_excluded"]
    df = pd.read_csv(os.path.join(folder, "cedint_f1_hourly_clean.csv.gz"), usecols=cols,
                     parse_dates=["timestamp_utc", "timestamp_local"], low_memory=False)
    df["energy"] = df["energy_wh_model"].where(df["usable_for_model"] == 1)
    df["date"] = df["timestamp_local"].dt.floor("D")
    df["hour"] = df["timestamp_local"].dt.hour
    df["series"] = df["zone"] + " · " + df["load_type"]
    return df


@st.cache_data(show_spinner=False)
def load_quality(folder):
    path = os.path.join(folder, "CeDInt_F1_quality_and_anomalies.xlsx")
    if not os.path.exists(path):
        return None, None
    return (pd.read_excel(path, sheet_name="Series_quality"),
            pd.read_excel(path, sheet_name="Series_level_issues"))


@st.cache_data(show_spinner="Loading forecasts …")
def load_pred(src):
    p = pd.read_csv(src, parse_dates=["timestamp_utc"])
    need = {"timestamp_utc", "zone", "load_type", "model", "split", "y_true", "y_pred"}
    missing = need - set(p.columns)
    if missing:
        raise ValueError(f"predictions file misses columns: {sorted(missing)}")
    return p


def metrics(y, yhat):
    y, yhat = np.asarray(y, float), np.asarray(yhat, float)
    ok = ~np.isnan(y) & ~np.isnan(yhat)
    y, yhat = y[ok], yhat[ok]
    if len(y) == 0 or y.mean() == 0:
        return dict(n=len(y), MAE=np.nan, RMSE=np.nan, CV_RMSE=np.nan, NMBE=np.nan)
    e = y - yhat
    rmse = np.sqrt((e ** 2).mean())
    return dict(n=len(y), MAE=np.abs(e).mean(), RMSE=rmse, CV_RMSE=100 * rmse / y.mean(), NMBE=100 * e.sum() / (len(y) * y.mean()))


def daily(df):
    g = df.groupby(["date", "zone", "load_type", "series"]).agg(energy=("energy", "sum"), hours=("energy", "count")).reset_index()
    g.loc[g["hours"] < 20, "energy"] = np.nan
    g["kwh"] = g["energy"] / 1000
    return g


if not os.path.exists(os.path.join(args.data, "cedint_f1_hourly_clean.csv.gz")):
    st.error(f"Clean dataset not found in '{args.data}'. Run clean_cedint.py first or pass --data <folder>.")
    st.stop()
df = load_clean(args.data)
quality, issues = load_quality(args.data)

# ------------------------------------------------------------------ sidebar filters
st.sidebar.title("Filters")
period = st.sidebar.radio("Period", ["2020–2023 (hourly)", "2025 (minute → hourly)"], index=0)
era = "hourly" if period.startswith("2020") else "minute"
d_era = df[(df["era"] == era) & (df["series_excluded"] == 0)]
dmin, dmax = d_era["date"].min().date(), d_era["date"].max().date()
dr = st.sidebar.date_input("Date range", (dmin, dmax), min_value=dmin, max_value=dmax)
if isinstance(dr, tuple) and len(dr) == 2:
    d_era = d_era[(d_era["date"] >= pd.Timestamp(dr[0])) & (d_era["date"] <= pd.Timestamp(dr[1]))]
zones = st.sidebar.multiselect("Zones", ["NE", "NW", "SE", "SW"], default=["NE", "NW", "SE", "SW"])
loads_all = sorted(d_era["load_type"].unique())
default_loads = [l for l in ["HVAC", "Lighting", "Plugs & Sockets"] if l in loads_all]
loads = st.sidebar.multiselect("Load types", loads_all, default=default_loads)
sel = d_era[d_era["zone"].isin(zones) & d_era["load_type"].isin(loads)]
st.sidebar.caption("Only hours rated usable by Team B are shown. Times in Madrid local time.")

# ------------------------------------------------------------------ header
st.markdown("""
<div class="hero-banner">
    <h1>⚡ CeDInt floor 1 · Day-Ahead Energy Forecaster</h1>
    <p>TBDA DataPack (backlog T36 / F8.1) · 24h-ahead predictions, model family comparison, operational decisions & data quality.</p>
</div>
""", unsafe_allow_html=True)

tab_over, tab_cons, tab_drv, tab_fc, tab_q = st.tabs(
    ["Overview", "Consumption", "Drivers", "Forecast vs actual", "Data quality"])

# ------------------------------------------------------------------ 1 overview
with tab_over:
    if sel.empty:
        st.info("No data for this selection.")
    else:
        tot_mwh = sel["energy"].sum() / 1e6
        days = sel["date"].nunique()
        usable = sel["energy"].notna().mean()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Energy in selection", f"{tot_mwh:,.1f} MWh")
        c2.metric("Average per day", f"{tot_mwh * 1000 / max(days, 1):,.0f} kWh")
        c3.metric("Series shown", f"{sel['series'].nunique()}")
        c4.metric("Hours with valid data", f"{usable:.0%}")

        left, right = st.columns([1.2, 1])
        by = (sel.groupby(["zone", "load_type"])["energy"].sum() / 1e6).reset_index(name="MWh")
        fig = px.bar(by, x="load_type", y="MWh", color="zone", barmode="group",
                     color_discrete_map=ZONE_COLOR, labels={"load_type": "", "MWh": "Energy (MWh)", "zone": "Zone"})
        fig.update_layout(title="Energy by load type and zone", height=380, legend_title_text="Zone", **TEMPLATE)
        fig.update_traces(hovertemplate="%{x} · %{fullData.name}<br>%{y:,.2f} MWh<extra></extra>")
        left.plotly_chart(fig, use_container_width=True)

        share = (sel.groupby("load_type")["energy"].sum() / sel["energy"].sum() * 100).sort_values()
        fig = go.Figure(go.Bar(x=share.values, y=share.index, orientation="h", marker_color="#0F766E",
                               text=[f"{v:.0f} %" for v in share.values], textposition="outside",
                               hovertemplate="%{y}: %{x:.1f} %<extra></extra>"))
        fig.update_layout(title="Share of energy by load type", height=380, xaxis_title="% of selection",
                          xaxis_range=[0, max(share.max() * 1.2, 1)], **TEMPLATE)
        right.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------------ 2 consumption
with tab_cons:
    if sel.empty:
        st.info("No data for this selection.")
    else:
        dd = daily(sel)
        agg = st.radio("Show", ["Per zone (sum of selected load types)", "Per series"], horizontal=True)
        if agg.startswith("Per zone"):
            z = dd.groupby(["date", "zone"])["kwh"].sum(min_count=1).reset_index()
            fig = px.line(z, x="date", y="kwh", color="zone", color_discrete_map=ZONE_COLOR,
                          labels={"date": "", "kwh": "Energy per day (kWh)", "zone": "Zone"})
        else:
            fig = px.line(dd, x="date", y="kwh", color="series",
                          labels={"date": "", "kwh": "Energy per day (kWh)", "series": "Series"})
        fig.update_traces(line_width=1.4)
        fig.update_layout(title="Daily energy", height=380, hovermode="x unified", **TEMPLATE)
        st.plotly_chart(fig, use_container_width=True)

        a, b = st.columns(2)
        prof = sel.assign(day=np.where(sel["is_holiday"] == 1, "Holiday",
                                       np.where(sel["is_weekend"] == 1, "Weekend", "Working day")))
        pr = prof.groupby(["day", "hour"])["energy"].mean().reset_index()
        fig = px.line(pr, x="hour", y="energy", color="day", markers=True,
                      color_discrete_map={"Working day": "#0284C7", "Weekend": "#EA580C", "Holiday": "#0D9488"},
                      labels={"hour": "Hour of day (local)", "energy": "Average energy per hour (Wh)", "day": ""})
        fig.update_layout(title="Average daily profile (all selected series together)", height=360, **TEMPLATE)
        a.plotly_chart(fig, use_container_width=True)

        mon = sel.assign(month=sel["timestamp_local"].dt.to_period("M").dt.to_timestamp())
        mm = (mon.groupby(["month", "zone"])["energy"].sum() / 1000).reset_index(name="kWh")
        fig = px.bar(mm, x="month", y="kWh", color="zone", color_discrete_map=ZONE_COLOR,
                     labels={"month": "", "kWh": "Energy per month (kWh)", "zone": "Zone"})
        fig.update_layout(title="Monthly energy by zone", height=360, bargap=0.15, **TEMPLATE)
        b.plotly_chart(fig, use_container_width=True)
        st.caption("Days with fewer than 20 valid hours are left out of the daily line. Monthly bars only add valid hours, so months with gaps look lower.")

# ------------------------------------------------------------------ 3 drivers
with tab_drv:
    series_opts = sorted(sel["series"].unique())
    if not series_opts:
        st.info("No data for this selection.")
    else:
        s = st.selectbox("Series", series_opts, index=series_opts.index("NW · HVAC") if "NW · HVAC" in series_opts else 0, key="drv_series")
        g = sel[sel["series"] == s]
        if g["temp_c"].notna().sum() == 0:
            st.warning("This zone has no indoor environmental sensors (NE). Use outdoor weather as a driver instead.")
        else:
            dg = g.groupby("date").agg(kwh=("energy", lambda x: x.sum() / 1000 if x.count() >= 20 else np.nan),
                                       temp=("temp_c", "mean"), occ=("occupancy", "mean"),
                                       lux=("lum_lux", "mean"), hum=("hum_pct", "mean")).dropna(subset=["kwh"])
            c = st.columns(3)
            for col, (var, label) in zip(c, [("temp", "Mean indoor temperature (°C)"), ("occ", "Share of hours occupied"),
                                             ("lux", "Mean light level (lux)")]):
                d2 = dg.dropna(subset=[var])
                r = d2["kwh"].corr(d2[var], method="spearman") if len(d2) > 10 else np.nan
                fig = px.scatter(d2, x=var, y="kwh", opacity=0.45, labels={var: label, "kwh": "Energy per day (kWh)"})
                fig.update_traces(marker=dict(size=6, color="#0F766E"),
                                  hovertemplate=f"{label}: %{{x:.2f}}<br>%{{y:.1f}} kWh<extra></extra>")
                fig.update_layout(title=f"Spearman r = {r:.2f}" if pd.notna(r) else "", height=330, **TEMPLATE)
                col.plotly_chart(fig, use_container_width=True)
            st.caption("One dot per day. Spearman r measures how strongly energy rises or falls with the driver (−1 to +1). "
                       "Correlation is not causation: occupancy and light both peak during working hours.")

# ------------------------------------------------------------------ 4 forecast vs actual
with tab_fc:
    up = st.file_uploader("Upload predictions file (combined models, Chronos, GBM, Blend, etc.)", type=["csv", "gz"])
    src = up if up is not None else (args.pred if os.path.exists(args.pred) else None)
    if src is None:
        st.info("No predictions file yet. Run make_reference_baseline.py, or upload a predictions file.")
    else:
        try:
            pdf = load_pred(src)
        except Exception as e:
            st.error(str(e)); st.stop()

        a, b, c, d = st.columns([1.2, 1, 1.2, 1])
        model = a.selectbox("Model", sorted(pdf["model"].unique()))
        known = ["validation", "test_2023", "test_2025", "train"]
        split = b.selectbox("Period", [x for x in known if x in pdf["split"].unique()] +
                            sorted(set(pdf["split"].unique()) - set(known)))
        pm = pdf[(pdf["model"] == model) & (pdf["split"] == split)].copy()
        pm["series"] = pm["zone"] + " · " + pm["load_type"]
        sopts = sorted(pm["series"].unique())
        s = c.selectbox("Series", sopts, index=sopts.index("NW · HVAC") if "NW · HVAC" in sopts else 0, key="fc_series")
        res_mode = d.radio("Resolution", ["Hourly (Wh)", "Daily 24h sum (kWh)"], horizontal=True)
        is_daily = res_mode.startswith("Daily")

        ps = pm[pm["series"] == s].sort_values("timestamp_utc").copy()
        load_selected = ps["load_type"].iloc[0] if not ps.empty else ""

        # Compute baseline reference (naive_day) if present in file for Skill Score
        naive_sub = pdf[(pdf["model"] == "naive_day") & (pdf["split"] == split) &
                        (pdf["zone"] + " · " + pdf["load_type"] == s)].sort_values("timestamp_utc")

        if is_daily:
            ps["day"] = ps["timestamp_utc"].dt.floor("D")
            ps = ps.groupby("day", as_index=False).agg(y_true=("y_true", "sum"), y_pred=("y_pred", "sum"), n_h=("y_true", "count"))
            ps = ps[ps["n_h"] >= 20].rename(columns={"day": "timestamp_utc"})
            ps["y_true"] /= 1000.0
            ps["y_pred"] /= 1000.0
            if not naive_sub.empty:
                naive_sub["day"] = naive_sub["timestamp_utc"].dt.floor("D")
                naive_sub = naive_sub.groupby("day", as_index=False).agg(y_true=("y_true", "sum"), y_pred=("y_pred", "sum"), n_h=("y_true", "count"))
                naive_sub = naive_sub[naive_sub["n_h"] >= 20].rename(columns={"day": "timestamp_utc"})
                naive_sub["y_true"] /= 1000.0
                naive_sub["y_pred"] /= 1000.0

        m = metrics(ps["y_true"], ps["y_pred"])
        skill = np.nan
        if not naive_sub.empty:
            merged_n = pd.merge(ps[["timestamp_utc", "y_true", "y_pred"]], naive_sub[["timestamp_utc", "y_pred"]],
                                on="timestamp_utc", suffixes=("", "_naive"))
            if len(merged_n) > 0:
                rmse_m = metrics(merged_n["y_true"], merged_n["y_pred"])["RMSE"]
                rmse_n = metrics(merged_n["y_true"], merged_n["y_pred_naive"])["RMSE"]
                if rmse_n > 0:
                    skill = 1.0 - (rmse_m / rmse_n)

        target_status, target_help = evaluate_target(load_selected, m, is_daily=is_daily)
        unit_label = "kWh" if is_daily else "Wh"

        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Model Family", model_family(model).split(" ")[0], help=model_family(model))
        k2.metric("CV(RMSE)", f"{m['CV_RMSE']:.1f} %", help=target_help)
        k3.metric("NMBE (Bias)", f"{m['NMBE']:+.1f} %", help="Systematic bias target: between −10% and +10%")
        k4.metric(f"MAE ({unit_label})", f"{m['MAE']:,.1f}")
        k5.metric("Skill vs Naive" if pd.notna(skill) else "Load Target",
                  f"{skill:+.2f}" if pd.notna(skill) else target_status,
                  help="Skill Score > 0 beats yesterday's naive forecast. " + target_help)

        # Customer Value & Closed-Loop Operational Box
        action_txt, loop_txt = operational_guidance(load_selected, m, skill)
        st.markdown(f"""
        <div class="decision-box">
            <h4>🎯 Customer Value & Operational Decision · {s} ({target_status})</h4>
            <p><b>Recommended action:</b> {action_txt}</p>
            <p>{loop_txt}</p>
        </div>
        """, unsafe_allow_html=True)

        if not is_daily:
            weeks = ps["timestamp_utc"].dt.to_period("W").dt.start_time.drop_duplicates().tolist()
            if weeks:
                wk = st.select_slider("Week", options=weeks, value=weeks[min(2, len(weeks) - 1)],
                                      format_func=lambda d: d.strftime("%d %b %Y"))
                pw = ps[(ps["timestamp_utc"] >= wk) & (ps["timestamp_utc"] < wk + pd.Timedelta(days=7))]
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=pw["timestamp_utc"], y=pw["y_true"], name="Actual", line=dict(color=ACTUAL, width=2.2)))
                fig.add_trace(go.Scatter(x=pw["timestamp_utc"], y=pw["y_pred"], name="Forecast", line=dict(color=FORECAST, width=2.2, dash="dot")))
                fig.update_layout(title=f"{s} · one week hourly profile (UTC)", height=380, yaxis_title="Energy per hour (Wh)",
                                  hovermode="x unified", legend=dict(orientation="h", y=1.1), **TEMPLATE)
                st.plotly_chart(fig, use_container_width=True)
        else:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=ps["timestamp_utc"], y=ps["y_true"], name="Actual (Daily)", line=dict(color=ACTUAL, width=2.2)))
            fig.add_trace(go.Scatter(x=ps["timestamp_utc"], y=ps["y_pred"], name="Forecast (Daily)", line=dict(color=FORECAST, width=2.2, dash="dot")))
            fig.update_layout(title=f"{s} · daily 24h aggregated energy (kWh) — timing errors average out", height=380,
                              yaxis_title="Energy per day (kWh)", hovermode="x unified", legend=dict(orientation="h", y=1.1), **TEMPLATE)
            st.plotly_chart(fig, use_container_width=True)

        # Compare every model on the same series and period (distinguishing model families)
        if pdf["model"].nunique() > 1:
            st.subheader(f"Model family comparison · {s} · {split}")
            sp = pdf[(pdf["split"] == split) & (pdf["zone"] + " · " + pdf["load_type"] == s)].copy()
            if is_daily:
                sp["day"] = sp["timestamp_utc"].dt.floor("D")
                sp = sp.groupby(["model", "day"], as_index=False).agg(y_true=("y_true", "sum"), y_pred=("y_pred", "sum"), n_h=("y_true", "count"))
                sp = sp[sp["n_h"] >= 20].rename(columns={"day": "timestamp_utc"})
                sp["y_true"] /= 1000.0
                sp["y_pred"] /= 1000.0

            common = sp.groupby("timestamp_utc")["model"].nunique()
            common = common[common == sp["model"].nunique()].index
            same_hours = st.checkbox("Only timestamps that every model forecast (fair comparison)", value=len(common) > 0)
            if same_hours:
                sp = sp[sp["timestamp_utc"].isin(common)]

            naive_ref = sp[sp["model"] == "naive_day"].set_index("timestamp_utc")["y_pred"] if "naive_day" in sp["model"].values else None
            cmp_rows = []
            for mod, g in sp.groupby("model"):
                r = metrics(g["y_true"], g["y_pred"])
                sk = np.nan
                if naive_ref is not None:
                    g_idx = g.set_index("timestamp_utc")
                    common_idx = g_idx.index.intersection(naive_ref.index)
                    if len(common_idx) > 0:
                        rn = metrics(g_idx.loc[common_idx, "y_true"], naive_ref.loc[common_idx])["RMSE"]
                        if rn > 0:
                            sk = 1.0 - (r["RMSE"] / rn)
                st_lbl, _ = evaluate_target(load_selected, r, is_daily=is_daily)
                r.update(model=mod, family=model_family(mod), Skill=sk, Status=st_lbl)
                cmp_rows.append(r)

            cmp = pd.DataFrame(cmp_rows).sort_values("CV_RMSE")
            color_map_fam = {
                "Benchmark (Naive)": "#94A3B8",
                "Univariate (History only)": "#0284C7",
                "Multivariate (Weather + Drivers)": "#0F766E",
                "Hybrid (Time-Series + Drivers)": "#EA580C",
            }
            fig = px.bar(cmp, x="CV_RMSE", y="model", color="family", orientation="h",
                         color_discrete_map=color_map_fam, text=cmp["CV_RMSE"].map(lambda v: f"{v:.1f} %"),
                         labels={"CV_RMSE": "CV(RMSE) % (lower is better)", "model": "", "family": "Model Architecture"})
            fig.update_traces(textposition="outside")
            fig.update_layout(height=80 + 40 * len(cmp), xaxis_range=[0, max(cmp["CV_RMSE"].max(), 30) * 1.18],
                              yaxis=dict(autorange="reversed"), margin=dict(t=40), **TEMPLATE)
            st.plotly_chart(fig, use_container_width=True)

            st.dataframe(cmp[["model", "family", "n", "CV_RMSE", "NMBE", "MAE", "Skill", "Status"]]
                         .rename(columns={"family": "Model Family", "CV_RMSE": "CV(RMSE) %", "NMBE": "NMBE %",
                                          "MAE": f"MAE ({unit_label})", "n": "points", "Skill": "Skill vs Naive"})
                         .style.format({"CV(RMSE) %": "{:.1f}", "NMBE %": "{:+.1f}", f"MAE ({unit_label})": "{:,.1f}",
                                        "Skill vs Naive": "{:+.2f}"}, na_rep="—"),
                         use_container_width=True, hide_index=True)
            st.caption("Distinguishing Univariate (time-series pattern) vs Multivariate (weather/occupancy drivers) vs Hybrid Blend avoids comparing apples and pears.")

        rows = []
        for (z, l), g in pm.groupby(["zone", "load_type"]):
            if is_daily:
                g = g.assign(day=g["timestamp_utc"].dt.floor("D")).groupby("day", as_index=False).agg(
                    y_true=("y_true", "sum"), y_pred=("y_pred", "sum"), n_h=("y_true", "count"))
                g = g[g["n_h"] >= 20]
                g["y_true"] /= 1000.0
                g["y_pred"] /= 1000.0
            r = metrics(g["y_true"], g["y_pred"])
            st_lbl, _ = evaluate_target(l, r, is_daily=is_daily)
            r.update(series=f"{z} · {l}", Target_Check=st_lbl)
            rows.append(r)
        tab = pd.DataFrame(rows)[["series", "n", "CV_RMSE", "NMBE", "MAE", "Target_Check"]]
        st.subheader(f"All series for {model} ({split} · {'Daily' if is_daily else 'Hourly'})")
        st.dataframe(tab.rename(columns={"CV_RMSE": "CV(RMSE) %", "NMBE": "NMBE %", "MAE": f"MAE ({unit_label})",
                                         "n": "points", "Target_Check": "Load-Specific Target"})
                     .style.format({"CV(RMSE) %": "{:.1f}", "NMBE %": "{:+.1f}", f"MAE ({unit_label})": "{:,.1f}"}),
                     use_container_width=True, hide_index=True)

# ------------------------------------------------------------------ 5 data quality
with tab_q:
    if quality is None:
        st.info("Quality workbook not found in the data folder.")
    else:
        q = quality[quality["era"] == era].copy()
        q["series"] = q["zone"] + " · " + q["load_type"]
        cnt = q["recommendation"].value_counts()
        c1, c2, c3 = st.columns(3)
        c1.metric("✓ Use", int(cnt.get("Use", 0)))
        c2.metric("! Use with caution", int(cnt.get("Use with caution", 0)))
        c3.metric("✕ Do not use", int(cnt.get("Do not use", 0)))
        fig = px.bar(q.sort_values("pct_valid_energy"), x="pct_valid_energy", y="series", orientation="h",
                     color="recommendation", color_discrete_map=REC_COLOR,
                     labels={"pct_valid_energy": "Hours with a valid energy value", "series": "", "recommendation": ""})
        fig.update_layout(title="Usable hours per series", height=560, xaxis_tickformat=".0%", xaxis_range=[0, 1.02], **TEMPLATE)
        fig.add_vline(x=0.8, line_dash="dot", line_color="#94A3B8", annotation_text="80 % = Use", annotation_position="top")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(q[["series", "recommendation", "reason", "pct_valid_energy", "power_vs_energy_pass"]]
                     .rename(columns={"pct_valid_energy": "valid hours", "power_vs_energy_pass": "power ≈ energy"})
                     .style.format({"valid hours": "{:.0%}", "power ≈ energy": "{:.0%}"}),
                     use_container_width=True, hide_index=True)
        if issues is not None:
            st.subheader("Known sensor and meter problems")
            st.dataframe(issues, use_container_width=True, hide_index=True)