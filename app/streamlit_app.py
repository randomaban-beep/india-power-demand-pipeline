"""Interactive Streamlit dashboard for India Power Demand & Weather Pipeline.

Organized into 5 tabs:
1. Overview: KPI cards, daily demand trend, monthly peaks
2. Weather & Demand: Temperature vs demand scatter with city filter, hourly heatmap
3. Renewables: Duck curve diurnal profiles, renewable penetration trends
4. Anomalies & Ramps: Flagged anomaly days, largest ramping events, sortable table
5. Pipeline Health: Layer row counts, automated quality assertion results
"""

from __future__ import annotations

import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.utils.config import DB_PATH

st.set_page_config(
    page_title="India Power Demand & Weather Pipeline",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_db_connection() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH, check_same_thread=False)


conn = get_db_connection()

# Sidebar
st.sidebar.title("⚡ India Power Analytics")
st.sidebar.markdown(
    "Automated pipeline analyzing grid demand met, renewable penetration, and weather elasticity."
)
st.sidebar.divider()
st.sidebar.info(
    "**Data Stack:**\n"
    "- Grid-India NLDC Daily Reports\n"
    "- Mendeley SCADA Telemetry\n"
    "- Open-Meteo ERA5 Reanalysis\n"
    "- SQLite (`data/energy.db`)"
)

# App Title & Header
st.title("⚡ India Electricity Demand & Weather Analytics")
st.markdown(
    "Explore how temperature extremes, solar expansion, and seasonal variations shape the world's 3rd largest power grid."
)

# Navigation Tabs
tab_overview, tab_weather, tab_re, tab_anom, tab_health = st.tabs([
    "📈 Overview",
    "🌡️ Weather & Demand",
    "☀️ Renewables & Duck Curve",
    "🚨 Anomalies & Ramps",
    "🩺 Pipeline Health"
])


# ==============================================================================
# TAB 1: OVERVIEW
# ==============================================================================
with tab_overview:
    # Query latest KPIs dynamically from newest daily data (stg_daily_psp)
    latest_psp_df = pd.read_sql("""
        SELECT 
            report_date as latest_date,
            max_demand_met_mw as latest_peak,
            evening_peak_mw as latest_evening_peak,
            energy_met_mu as latest_energy_met,
            res_share_pct as latest_re_share
        FROM stg_daily_psp 
        ORDER BY report_date DESC LIMIT 1
    """, conn)
    
    if not latest_psp_df.empty:
        latest_psp = latest_psp_df.iloc[0]
        latest_date = latest_psp['latest_date']
        latest_peak = int(latest_psp['latest_peak']) if pd.notnull(latest_psp['latest_peak']) else 0
        latest_re = f"{latest_psp['latest_re_share']:.1f}%" if pd.notnull(latest_psp['latest_re_share']) else "N/A"
    else:
        latest_date = "N/A"
        latest_peak = 0
        latest_re = "N/A"

    all_time_peak = conn.execute(
        "SELECT MAX(max_demand_met_mw), report_date FROM stg_daily_psp WHERE max_demand_met_mw IS NOT NULL"
    ).fetchone()
    all_time_val = int(all_time_peak[0]) if all_time_peak and all_time_peak[0] else latest_peak
    all_time_dt = all_time_peak[1] if all_time_peak and all_time_peak[1] else latest_date
    
    last_run_time = conn.execute(
        "SELECT MAX(run_at) FROM pipeline_runs WHERE status = 'ok'"
    ).fetchone()[0] or "N/A"

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(f"Latest Daily Peak ({latest_date})", f"{latest_peak:,} MW", "From Daily PSP")
    col2.metric("All-Time Grid Peak", f"{all_time_val:,} MW", f"Recorded {all_time_dt}")
    col3.metric("Latest Renewable Share", latest_re, "Solar + Wind")
    col4.metric("Pipeline Freshness", str(last_run_time)[:16].replace("T", " "), "Daily CI Active")

    st.divider()

    col_left, col_right = st.columns([1.5, 1])

    with col_left:
        st.subheader("Daily Demand Trajectory (MW)")
        df_daily = pd.read_sql("""
            SELECT date_ist, ROUND(AVG(demand_mw), 0) as avg_demand, MAX(demand_mw) as peak_demand
            FROM stg_hourly_demand
            GROUP BY date_ist
            ORDER BY date_ist
        """, conn)
        df_daily["date"] = pd.to_datetime(df_daily["date_ist"])
        df_daily["7d_rolling"] = df_daily["avg_demand"].rolling(7, min_periods=1).mean()

        fig_daily = go.Figure()
        fig_daily.add_trace(go.Scatter(
            x=df_daily["date"], y=df_daily["avg_demand"],
            mode="lines", name="Daily Average", line=dict(color="#56B4E9", width=1.5), opacity=0.6
        ))
        fig_daily.add_trace(go.Scatter(
            x=df_daily["date"], y=df_daily["7d_rolling"],
            mode="lines", name="7-Day Moving Avg", line=dict(color="#0072B2", width=2.5)
        ))
        fig_daily.update_layout(
            hovermode="x unified",
            xaxis_title="Date",
            yaxis_title="Demand (MW)",
            margin=dict(l=0, r=0, t=20, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_daily, use_container_width=True)

    with col_right:
        st.subheader("Monthly Peak Load (MW)")
        df_peak = pd.read_sql("""
            SELECT year, month_num, peak_demand_mw
            FROM mart_monthly_peak_demand
            ORDER BY month_num, year
        """, conn)
        month_map = {"01":"Jan","02":"Feb","03":"Mar","04":"Apr","05":"May","06":"Jun",
                     "07":"Jul","08":"Aug","09":"Sep","10":"Oct","11":"Nov","12":"Dec"}
        df_peak["month"] = df_peak["month_num"].map(month_map)

        fig_peak = px.bar(
            df_peak, x="month", y="peak_demand_mw", color="year",
            barmode="group", color_discrete_sequence=px.colors.qualitative.Safe
        )
        fig_peak.update_layout(
            xaxis_title="Month",
            yaxis_title="Peak Demand (MW)",
            margin=dict(l=0, r=0, t=20, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_peak, use_container_width=True)


# ==============================================================================
# TAB 2: WEATHER & DEMAND
# ==============================================================================
with tab_weather:
    st.subheader("Temperature vs Electricity Demand Sensitivity")
    st.markdown("Assess how cooling load drives power demand above the 25°C balance point.")

    # Controlled sensitivity call
    from src.model.temperature_sensitivity import compute_temperature_sensitivity
    sens = compute_temperature_sensitivity(conn)
    
    col_k1, col_k2, col_k3, col_k4 = st.columns(4)
    col_k1.metric("Controlled Slope (>25°C)", f"+{sens['slope_mw_per_c']:,} MW / °C", "Daily OLS Model")
    col_k2.metric("95% Confidence Interval", f"[{sens['ci_lower']:,}, {sens['ci_upper']:,}]", "MW / °C")
    col_k3.metric("Model R-squared", f"{sens['r2']:.2f}", f"N = {sens['n_days']} Days")
    col_k4.metric("Threshold Balance Point", f"{sens['threshold_choice_c']}°C", "Justified via AIC")

    city_col = st.selectbox(
        "Select Temperature Feature",
        options=[
            ("avg_temperature_c", "National Weighted Average (6 Cities)"),
            ("delhi_temp_c", "Delhi NCT"),
            ("mumbai_temp_c", "Mumbai"),
        ],
        format_func=lambda x: x[1]
    )[0]

    df_weather = pd.read_sql(f"""
        SELECT {city_col} as temp_c, demand_mw, season, avg_humidity_pct
        FROM mart_temp_vs_demand
        WHERE {city_col} IS NOT NULL
    """, conn)

    col_w1, col_w2 = st.columns([1.4, 1])

    with col_w1:
        fig_scatter = px.scatter(
            df_weather, x="temp_c", y="demand_mw", color="season",
            color_discrete_map={"Summer":"#D55E00","Monsoon":"#009E73","Post-Monsoon":"#E69F00","Winter":"#0072B2"},
            opacity=0.35, title="Hourly Temperature (°C) vs Demand (MW)"
        )
        # Add 25°C vertical guideline
        fig_scatter.add_vline(x=25, line_dash="dash", line_color="gray", annotation_text="Cooling Base 25°C")
        fig_scatter.update_layout(xaxis_title="Temperature (°C)", yaxis_title="Demand (MW)")
        st.plotly_chart(fig_scatter, use_container_width=True)

    with col_w2:
        st.subheader("Diurnal Demand Heatmap")
        df_heat = pd.read_sql("""
            SELECT CAST(strftime('%m', timestamp_ist) AS INTEGER) AS month, hour_ist, ROUND(AVG(demand_mw), 0) as avg_d
            FROM stg_hourly_demand
            GROUP BY month, hour_ist
        """, conn)
        pivot_heat = df_heat.pivot(index="hour_ist", columns="month", values="avg_d")
        month_labels = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
        pivot_heat.columns = [month_labels[c-1] for c in pivot_heat.columns]

        fig_heat = px.imshow(
            pivot_heat, labels=dict(x="Month", y="Hour of Day (IST)", color="Demand (MW)"),
            color_continuous_scale="Viridis", aspect="auto"
        )
        fig_heat.update_layout(yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig_heat, use_container_width=True)


# ==============================================================================
# TAB 3: RENEWABLES & DUCK CURVE
# ==============================================================================
with tab_re:
    st.subheader("Solar & Wind Reshaping Diurnal Net Load (Duck Curve)")
    
    selected_season = st.radio("Select Season:", ["Summer", "Monsoon", "Post-Monsoon", "Winter"], horizontal=True)

    df_duck = pd.read_sql(f"""
        SELECT hour_ist, ROUND(AVG(demand_mw), 0) as gross_demand,
               ROUND(AVG(solar_mw), 0) as solar,
               ROUND(AVG(wind_mw), 0) as wind,
               ROUND(AVG(net_load_mw), 0) as net_load
        FROM mart_net_load_profile
        WHERE season = '{selected_season}'
        GROUP BY hour_ist
        ORDER BY hour_ist
    """, conn)

    fig_duck = go.Figure()
    fig_duck.add_trace(go.Scatter(
        x=df_duck["hour_ist"], y=df_duck["gross_demand"],
        mode="lines+markers", name="Gross Demand (MW)", line=dict(color="#0072B2", width=3)
    ))
    fig_duck.add_trace(go.Scatter(
        x=df_duck["hour_ist"], y=df_duck["net_load"],
        mode="lines+markers", name="Net Load (Demand - RE)", line=dict(color="#D55E00", width=3, dash="dash")
    ))
    fig_duck.add_trace(go.Scatter(
        x=df_duck["hour_ist"], y=df_duck["solar"],
        mode="lines", name="Solar Generation", fill="tozeroy", line=dict(color="#F0E442", width=1)
    ))

    fig_duck.update_layout(
        xaxis_title="Hour of Day (IST)",
        yaxis_title="Power (MW)",
        hovermode="x unified",
        margin=dict(l=0, r=0, t=30, b=0)
    )
    st.plotly_chart(fig_duck, use_container_width=True)

    st.subheader("Renewable Penetration Over Time")
    df_re_time = pd.read_sql("""
        SELECT date_ist, ROUND((SUM(solar_mw + wind_mw) / SUM(demand_mw)) * 100.0, 2) as re_pct
        FROM stg_hourly_demand
        GROUP BY date_ist
        ORDER BY date_ist
    """, conn)
    fig_re = px.area(
        df_re_time, x="date_ist", y="re_pct",
        color_discrete_sequence=["#009E73"],
        labels={"date_ist": "Date", "re_pct": "Variable RE Share (%)"}
    )
    fig_re.update_layout(margin=dict(l=0, r=0, t=20, b=0))
    st.plotly_chart(fig_re, use_container_width=True)


# ==============================================================================
# TAB 4: ANOMALIES & RAMPS
# ==============================================================================
with tab_anom:
    st.subheader("Grid Anomalies & Maximum 1-Hour Ramps")
    col_a1, col_a2 = st.columns([1.5, 1])

    with col_a1:
        st.markdown("**Flagged Anomaly Days (±2 Standard Deviations from Baseline)**")
        df_anom = pd.read_sql("""
            SELECT date_ist, season, weekday_name, avg_daily_demand_mw, peak_daily_demand_mw, z_score, anomaly_type
            FROM mart_anomaly_days
            WHERE is_anomaly = 1
            ORDER BY ABS(z_score) DESC
        """, conn)
        st.dataframe(df_anom, use_container_width=True, height=280)

    with col_a2:
        st.markdown("**Largest 1-Hour Net Load Ramps (MW)**")
        df_ramps = pd.read_sql("""
            SELECT timestamp_ist, abs_ramp_1h_mw as ramp_mw, demand_mw, solar_mw
            FROM mart_net_load_ramps
            ORDER BY abs_ramp_1h_mw DESC
            LIMIT 10
        """, conn)
        st.dataframe(df_ramps, use_container_width=True, height=280)


# ==============================================================================
# TAB 5: PIPELINE HEALTH
# ==============================================================================
with tab_health:
    st.subheader("Pipeline Health & Audit Suite")
    
    col_h1, col_h2 = st.columns(2)
    with col_h1:
        st.markdown("**Automated Data Quality Check Results**")
        df_checks = pd.read_sql("""
            SELECT check_name, status, details, checked_at
            FROM data_quality_checks
            ORDER BY id DESC
            LIMIT 7
        """, conn)
        st.dataframe(df_checks, use_container_width=True)

    with col_h2:
        st.markdown("**Recent Pipeline Execution Runs**")
        df_runs = pd.read_sql("""
            SELECT run_at, stage, source, rows_inserted, duration_s, status, trigger, message
            FROM pipeline_runs
            ORDER BY id DESC
            LIMIT 6
        """, conn)
        st.dataframe(df_runs, use_container_width=True)

    st.markdown("**Database Table Storage Footprint**")
    table_sizes = pd.DataFrame([
        {"Table": "raw_weather", "Rows": conn.execute("SELECT COUNT(*) FROM raw_weather").fetchone()[0]},
        {"Table": "stg_hourly_weather", "Rows": conn.execute("SELECT COUNT(*) FROM stg_hourly_weather").fetchone()[0]},
        {"Table": "raw_hourly_demand", "Rows": conn.execute("SELECT COUNT(*) FROM raw_hourly_demand").fetchone()[0]},
        {"Table": "stg_hourly_demand", "Rows": conn.execute("SELECT COUNT(*) FROM stg_hourly_demand").fetchone()[0]},
        {"Table": "mart_temp_vs_demand", "Rows": conn.execute("SELECT COUNT(*) FROM mart_temp_vs_demand").fetchone()[0]},
        {"Table": "mart_net_load_profile", "Rows": conn.execute("SELECT COUNT(*) FROM mart_net_load_profile").fetchone()[0]},
        {"Table": "data_quality_checks", "Rows": conn.execute("SELECT COUNT(*) FROM data_quality_checks").fetchone()[0]},
    ])
    st.dataframe(table_sizes, use_container_width=True)
