"""
CeDInt floor 1 - energy dashboard prototype (TBDA DataPack, backlog T36 / F8.1)

Works today with the clean dataset and the reference (naive) forecasts; Team D's forecasts can be
added later by uploading a predictions file in the agreed format
(timestamp_utc, zone, load_type, model, split, y_true, y_pred).

Run:  streamlit run dashboard_app.py -- --data cleaned --pred reference_baseline_predictions.csv.gz
"""
import argparse, os, sys
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ------------------------------------------------------------------ settings
p = argparse.ArgumentParser()
p.add_argument("--data", default="cleaned", help="output folder of clean_cedint.py")
p.add_argument("--pred", default="reference_baseline_predictions.csv.gz", help="predictions file (agreed format)")
args, _ = p.parse_known_args(sys.argv[1:])

ZONE_COLOR = {"NE": "#2a78d6", "NW": "#eb6834", "SE": "#1baf7a", "SW": "#6250d6"}
ACTUAL, FORECAST = "#2a78d6", "#eb6834"
REC_COLOR = {"Use": "#0ca30c", "Use with caution": "#fab219", "Do not use": "#d03b3b"}
TEMPLATE = dict(template="simple_white", font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif", size=13))

st.set_page_config(page_title="CeDInt Energy Dashboard", page_icon="⚡", layout="wide")
st.markdown("""<style>
.block-container {padding-top: 1.6rem; max-width: 1400px;}
[data-testid="stMetricValue"] {font-size: 1.7rem;}
</style>""", unsafe_allow_html=True)


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
    g.loc[g["hours"] < 20, "energy"] = np.nan          # a day needs >= 20 valid hours
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
st.title("CeDInt floor 1 · Energy dashboard")
st.caption("Prototype (backlog T36 / F8.1). Consumption, drivers, forecast vs actual and data quality for the four zones of floor 1.")

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
        fig = go.Figure(go.Bar(x=share.values, y=share.index, orientation="h", marker_color="#2a78d6",
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
                      color_discrete_map={"Working day": "#2a78d6", "Weekend": "#eb6834", "Holiday": "#1baf7a"},
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
        s = st.selectbox("Series", series_opts, index=series_opts.index("NW · HVAC") if "NW · HVAC" in series_opts else 0)
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
                fig.update_traces(marker=dict(size=6, color="#2a78d6"),
                                  hovertemplate=f"{label}: %{{x:.2f}}<br>%{{y:.1f}} kWh<extra></extra>")
                fig.update_layout(title=f"Spearman r = {r:.2f}" if pd.notna(r) else "", height=330, **TEMPLATE)
                col.plotly_chart(fig, use_container_width=True)
            st.caption("One dot per day. Spearman r measures how strongly energy rises or falls with the driver (−1 to +1). "
                       "Correlation is not causation: occupancy and light both peak during working hours.")

# ------------------------------------------------------------------ 4 forecast vs actual
with tab_fc:
    up = st.file_uploader("Upload a predictions file from Team D (CSV in the agreed format)", type=["csv", "gz"])
    src = up if up is not None else (args.pred if os.path.exists(args.pred) else None)
    if src is None:
        st.info("No predictions file yet. Run make_reference_baseline.py, or upload Team D's file.")
    else:
        try:
            pdf = load_pred(src)
        except Exception as e:
            st.error(str(e)); st.stop()
        if up is None:
            st.caption("Showing the reference forecasts (naive_day = same hour yesterday, naive_week = same hour last week). "
                       "These are the bar every real model must beat.")
        a, b, c = st.columns(3)
        model = a.selectbox("Model", sorted(pdf["model"].unique()))
        split = b.selectbox("Period", [x for x in ["validation", "test_2023", "test_2025", "train"] if x in pdf["split"].unique()])
        pm = pdf[(pdf["model"] == model) & (pdf["split"] == split)].copy()
        pm["series"] = pm["zone"] + " · " + pm["load_type"]
        sopts = sorted(pm["series"].unique())
        s = c.selectbox("Series", sopts, index=sopts.index("NW · HVAC") if "NW · HVAC" in sopts else 0)
        ps = pm[pm["series"] == s].sort_values("timestamp_utc")
        m = metrics(ps["y_true"], ps["y_pred"])
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("CV(RMSE)", f"{m['CV_RMSE']:.1f} %", help="ASHRAE 14 hourly limit: ≤ 30 %")
        k2.metric("NMBE", f"{m['NMBE']:+.1f} %", help="ASHRAE 14 hourly limit: between −10 % and +10 %")
        k3.metric("MAE", f"{m['MAE']:,.1f} Wh")
        ok = (m["CV_RMSE"] <= 30) and (abs(m["NMBE"]) <= 10)
        k4.metric("ASHRAE 14", "✓ pass" if ok else "✕ fail")

        weeks = ps["timestamp_utc"].dt.to_period("W").dt.start_time.drop_duplicates().tolist()
        if weeks:
            wk = st.select_slider("Week", options=weeks, value=weeks[min(2, len(weeks) - 1)],
                                  format_func=lambda d: d.strftime("%d %b %Y"))
            pw = ps[(ps["timestamp_utc"] >= wk) & (ps["timestamp_utc"] < wk + pd.Timedelta(days=7))]
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=pw["timestamp_utc"], y=pw["y_true"], name="Actual", line=dict(color=ACTUAL, width=2)))
            fig.add_trace(go.Scatter(x=pw["timestamp_utc"], y=pw["y_pred"], name="Forecast", line=dict(color=FORECAST, width=2, dash="dot")))
            fig.update_layout(title=f"{s} · one week (UTC)", height=380, yaxis_title="Energy per hour (Wh)",
                              hovermode="x unified", legend=dict(orientation="h", y=1.1), **TEMPLATE)
            st.plotly_chart(fig, use_container_width=True)

        rows = []
        for (z, l), g in pm.groupby(["zone", "load_type"]):
            r = metrics(g["y_true"], g["y_pred"]); r.update(series=f"{z} · {l}"); rows.append(r)
        tab = pd.DataFrame(rows)[["series", "n", "CV_RMSE", "NMBE", "MAE"]]
        tab["ASHRAE 14"] = np.where((tab["CV_RMSE"] <= 30) & (tab["NMBE"].abs() <= 10), "✓ pass", "✕ fail")
        st.subheader("All series for this model and period")
        st.dataframe(tab.rename(columns={"CV_RMSE": "CV(RMSE) %", "NMBE": "NMBE %", "MAE": "MAE (Wh)", "n": "hours"})
                     .style.format({"CV(RMSE) %": "{:.1f}", "NMBE %": "{:+.1f}", "MAE (Wh)": "{:,.1f}"}),
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
        fig.add_vline(x=0.8, line_dash="dot", line_color="#898781", annotation_text="80 % = Use", annotation_position="top")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(q[["series", "recommendation", "reason", "pct_valid_energy", "power_vs_energy_pass"]]
                     .rename(columns={"pct_valid_energy": "valid hours", "power_vs_energy_pass": "power ≈ energy"})
                     .style.format({"valid hours": "{:.0%}", "power ≈ energy": "{:.0%}"}),
                     use_container_width=True, hide_index=True)
        if issues is not None:
            st.subheader("Known sensor and meter problems")
            st.dataframe(issues, use_container_width=True, hide_index=True)
