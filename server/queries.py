from __future__ import annotations

from contextlib import closing
import csv
import io
import math
import sqlite3
from typing import Any

import pandas as pd

from src.model.temperature_sensitivity import compute_temperature_sensitivity
from src.utils.config import get_db_path

VALID_SEASONS = {"Winter", "Summer", "Monsoon", "Post-Monsoon"}
VALID_FEATURES = {"avg_temperature_c", "delhi_temp_c", "mumbai_temp_c"}
SEASON_MONTHS = {
    "Winter": [12, 1, 2],
    "Summer": [3, 4, 5],
    "Monsoon": [6, 7, 8, 9],
    "Post-Monsoon": [10, 11],
}


def get_connection() -> sqlite3.Connection:
    """Establish a read-only SQLite database connection using row mapping."""
    db_file = get_db_path()
    conn = sqlite3.connect(db_file.resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def parse_seasons_param(seasons_str: str | None) -> list[str] | None:
    """Validate and parse a comma-separated string of meteorological seasons."""
    if not seasons_str or seasons_str.strip().lower() in ("all", ""):
        return None
    parsed = [s.strip() for s in seasons_str.split(",") if s.strip()]
    for s in parsed:
        if s not in VALID_SEASONS:
            raise ValueError(f"Invalid season '{s}'. Valid values are: {', '.join(sorted(VALID_SEASONS))}")
    return parsed


def build_filter_clause(
    date_col: str,
    season_col: str | None,
    from_date: str | None,
    to_date: str | None,
    seasons: list[str] | None,
) -> tuple[str, list[Any]]:
    """Construct parameterised SQL WHERE clauses and bound arguments."""
    clauses: list[str] = []
    params: list[Any] = []

    if from_date:
        clauses.append(f"{date_col} >= ?")
        params.append(from_date)
    if to_date:
        clauses.append(f"{date_col} <= ?")
        params.append(to_date)
    if seasons and season_col:
        placeholders = ", ".join(["?"] * len(seasons))
        clauses.append(f"{season_col} IN ({placeholders})")
        params.extend(seasons)

    where_str = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where_str, params


def get_summary_metrics() -> dict[str, Any]:
    """Retrieve top-level KPI metrics across operational reports and high-resolution telemetry."""
    with closing(get_connection()) as conn:
        latest_psp = conn.execute("""
            SELECT max_demand_met_mw, report_date, res_share_pct
            FROM stg_daily_psp
            WHERE max_demand_met_mw IS NOT NULL
            ORDER BY report_date DESC
            LIMIT 1;
        """).fetchone()

        record_psp = conn.execute("""
            SELECT max_demand_met_mw, report_date
            FROM stg_daily_psp
            WHERE max_demand_met_mw IS NOT NULL
            ORDER BY max_demand_met_mw DESC
            LIMIT 1;
        """).fetchone()

        avg_re_row = conn.execute("""
            SELECT AVG(res_share_pct) AS avg_re_share
            FROM stg_daily_psp
            WHERE res_share_pct IS NOT NULL;
        """).fetchone()

        telemetry_bounds = conn.execute("""
            SELECT MIN(timestamp_ist) AS window_start, MAX(timestamp_ist) AS window_end, COUNT(*) AS record_count
            FROM mart_temp_vs_demand;
        """).fetchone()

        total_reports = conn.execute("""
            SELECT COUNT(*) AS report_count
            FROM stg_daily_psp;
        """).fetchone()[0]

        last_run = conn.execute("""
            SELECT run_at, stage, source, status, message
            FROM pipeline_runs

            ORDER BY id DESC
            LIMIT 1;
        """).fetchone()

        return {
            "latest_psp_peak_mw": float(latest_psp["max_demand_met_mw"])
            if latest_psp and latest_psp["max_demand_met_mw"] is not None
            else None,
            "latest_psp_date": latest_psp["report_date"] if latest_psp else None,
            "latest_re_share_pct": float(round(latest_psp["res_share_pct"], 2))
            if latest_psp and latest_psp["res_share_pct"] is not None
            else None,
            "record_peak_mw": float(record_psp["max_demand_met_mw"])
            if record_psp and record_psp["max_demand_met_mw"] is not None
            else None,
            "record_peak_date": record_psp["report_date"] if record_psp else None,
            "avg_re_share_pct": float(round(avg_re_row["avg_re_share"], 2))
            if avg_re_row and avg_re_row["avg_re_share"] is not None
            else None,
            "hourly_window_start": telemetry_bounds["window_start"] if telemetry_bounds else None,
            "hourly_window_end": telemetry_bounds["window_end"] if telemetry_bounds else None,
            "total_hourly_records": int(telemetry_bounds["record_count"]) if telemetry_bounds else 0,
            "total_report_count": int(total_reports),
            "last_pipeline_run": dict(last_run) if last_run else None,
        }


def get_daily_demand(
    from_date: str | None = None,
    to_date: str | None = None,
    seasons: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Retrieve daily demand aggregates alongside 7-day rolling baseline averages."""
    where_str, params = build_filter_clause("date_ist", "season", from_date, to_date, seasons)
    query = f"""
        WITH unified_days AS (
            SELECT
                date_ist,
                season,
                weekday_name,
                avg_daily_demand_mw,
                peak_daily_demand_mw
            FROM mart_anomaly_days
            UNION ALL
            SELECT
                report_date AS date_ist,
                CASE
                    WHEN CAST(strftime('%m', report_date) AS INT) IN (12, 1, 2) THEN 'Winter'
                    WHEN CAST(strftime('%m', report_date) AS INT) IN (3, 4, 5) THEN 'Summer'
                    WHEN CAST(strftime('%m', report_date) AS INT) IN (6, 7, 8, 9) THEN 'Monsoon'
                    ELSE 'Post-Monsoon'
                END AS season,
                CASE CAST(strftime('%w', report_date) AS INT)
                    WHEN 0 THEN 'Sunday'
                    WHEN 1 THEN 'Monday'
                    WHEN 2 THEN 'Tuesday'
                    WHEN 3 THEN 'Wednesday'
                    WHEN 4 THEN 'Thursday'
                    WHEN 5 THEN 'Friday'
                    ELSE 'Saturday'
                END AS weekday_name,
                ROUND(energy_met_mu * 1000.0 / 24.0, 1) AS avg_daily_demand_mw,
                max_demand_met_mw AS peak_daily_demand_mw
            FROM stg_daily_psp
            WHERE report_date NOT IN (SELECT date_ist FROM mart_anomaly_days)
              AND max_demand_met_mw IS NOT NULL
        ),
        windowed AS (
            SELECT
                date_ist,
                season,
                weekday_name,
                avg_daily_demand_mw,
                peak_daily_demand_mw,
                AVG(avg_daily_demand_mw) OVER (
                    ORDER BY julianday(date_ist)
                    RANGE BETWEEN 6 PRECEDING AND CURRENT ROW
                ) AS rolling_7d_avg_mw
            FROM unified_days
        )
        SELECT
            date_ist AS date,
            season,
            weekday_name,
            ROUND(avg_daily_demand_mw, 1) AS avg_mw,
            ROUND(peak_daily_demand_mw, 1) AS peak_mw,
            ROUND(rolling_7d_avg_mw, 1) AS rolling_avg_mw
        FROM windowed
        {where_str}
        ORDER BY date_ist ASC;
    """
    with closing(get_connection()) as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_monthly_peaks(
    from_date: str | None = None,
    to_date: str | None = None,
    seasons: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Retrieve monthly maximum demand met and year-over-year expansion rates."""
    clauses: list[str] = []
    params: list[Any] = []

    if from_date:
        clauses.append("year_month >= ?")
        params.append(from_date[:7])
    if to_date:
        clauses.append("year_month <= ?")
        params.append(to_date[:7])
    if seasons:
        allowed_months: list[int] = []
        for s in seasons:
            allowed_months.extend(SEASON_MONTHS.get(s, []))
        if allowed_months:
            placeholders = ", ".join(["?"] * len(allowed_months))
            clauses.append(f"CAST(month_num AS INTEGER) IN ({placeholders})")
            params.extend(allowed_months)

    where_str = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    query = f"""
        WITH all_monthly AS (
            SELECT
                year,
                month_num,
                year_month,
                peak_demand_mw,
                avg_demand_mw
            FROM mart_monthly_peak_demand
            UNION ALL
            SELECT
                CAST(strftime('%Y', report_date) AS INT) AS year,
                CAST(strftime('%m', report_date) AS INT) AS month_num,
                substr(report_date, 1, 7) AS year_month,
                MAX(max_demand_met_mw) AS peak_demand_mw,
                ROUND(AVG(energy_met_mu * 1000.0 / 24.0), 1) AS avg_demand_mw
            FROM stg_daily_psp
            WHERE substr(report_date, 1, 7) NOT IN (SELECT year_month FROM mart_monthly_peak_demand)
              AND max_demand_met_mw IS NOT NULL
            GROUP BY year, month_num, year_month
        ),
        ranked AS (
            SELECT
                m.year,
                m.month_num,
                m.year_month,
                ROUND(m.peak_demand_mw, 1) AS peak_demand_mw,
                ROUND(m.avg_demand_mw, 1) AS avg_demand_mw,
                DENSE_RANK() OVER (PARTITION BY m.year ORDER BY m.peak_demand_mw DESC) AS peak_rank_in_year,
                ROUND(prev.peak_demand_mw, 1) AS prev_year_peak_mw,
                CASE
                    WHEN prev.peak_demand_mw IS NOT NULL AND prev.peak_demand_mw > 0
                    THEN ROUND(((m.peak_demand_mw - prev.peak_demand_mw) / prev.peak_demand_mw) * 100.0, 2)
                    ELSE NULL
                END AS yoy_peak_growth_pct
            FROM all_monthly m
            LEFT JOIN all_monthly prev
                ON prev.year = m.year - 1
               AND CAST(prev.month_num AS INTEGER) = CAST(m.month_num AS INTEGER)
        )
        SELECT
            year,
            month_num,
            year_month,
            peak_demand_mw,
            avg_demand_mw,
            peak_rank_in_year,
            prev_year_peak_mw,
            yoy_peak_growth_pct
        FROM ranked
        {where_str}
        ORDER BY year_month ASC;
    """
    with closing(get_connection()) as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_temp_vs_demand(
    feature: str = "avg_temperature_c",
    from_date: str | None = None,
    to_date: str | None = None,
    seasons: list[str] | None = None,
    sample_limit: int = 6000,
) -> dict[str, Any]:
    """Retrieve temperature versus demand observations alongside median values grouped by 1°C bins."""
    if feature not in VALID_FEATURES:
        raise ValueError(f"Invalid feature '{feature}'. Must be one of {sorted(VALID_FEATURES)}")

    where_str, params = build_filter_clause("date_ist", "season", from_date, to_date, seasons)
    if where_str:
        where_str += f" AND demand_mw IS NOT NULL AND {feature} IS NOT NULL"
    else:
        where_str = f"WHERE demand_mw IS NOT NULL AND {feature} IS NOT NULL"

    count_query = f"SELECT COUNT(*) FROM mart_temp_vs_demand {where_str};"
    points_query = f"""
        SELECT
            timestamp_ist,
            date_ist,
            hour_ist,
            season,
            ROUND({feature}, 2) AS temp_c,
            ROUND(demand_mw, 1) AS demand_mw
        FROM mart_temp_vs_demand
        {where_str}
        ORDER BY timestamp_ist ASC;
    """

    with closing(get_connection()) as conn:
        total_matching = conn.execute(count_query, params).fetchone()[0]
        if total_matching == 0:
            return {
                "feature": feature,
                "total_points": 0,
                "sampled_points": 0,
                "points": [],
                "median_bins": [],
            }

        rows = conn.execute(points_query, params).fetchall()
        df = pd.DataFrame([dict(r) for r in rows])

        if len(df) > sample_limit:
            step = math.ceil(len(df) / sample_limit)
            sampled_df = df.iloc[::step].copy()
        else:
            sampled_df = df.copy()

        bins_grouped = df.groupby(df["temp_c"].round().astype(int))
        median_bins: list[dict[str, Any]] = []
        for temp_val, grp in bins_grouped:
            median_bins.append(
                {
                    "temp_bin_c": int(temp_val),
                    "median_demand_mw": float(round(grp["demand_mw"].median(), 1)),
                    "count": int(len(grp)),
                }
            )
        median_bins.sort(key=lambda x: x["temp_bin_c"])

        return {
            "feature": feature,
            "total_points": int(total_matching),
            "sampled_points": int(len(sampled_df)),
            "points": sampled_df.to_dict(orient="records"),
            "median_bins": median_bins,
        }


def get_demand_heatmap(
    from_date: str | None = None,
    to_date: str | None = None,
    seasons: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Retrieve mean power demand broken down by calendar month and hour of day."""
    where_str, params = build_filter_clause("date_ist", "season", from_date, to_date, seasons)
    if where_str:
        where_str += " AND demand_mw IS NOT NULL"
    else:
        where_str = "WHERE demand_mw IS NOT NULL"

    query = f"""
        SELECT
            CAST(strftime('%m', timestamp_ist) AS INT) AS month,
            hour_ist AS hour,
            ROUND(AVG(demand_mw), 1) AS avg_demand_mw,
            COUNT(*) AS sample_count
        FROM mart_temp_vs_demand
        {where_str}
        GROUP BY month, hour
        ORDER BY month ASC, hour ASC;
    """
    with closing(get_connection()) as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_sensitivity_analysis() -> dict[str, Any]:
    """Retrieve full-sample hinge cooling regression estimates and candidate threshold sensitivities."""
    with closing(get_connection()) as conn:
        return compute_temperature_sensitivity(conn)


def get_duck_curve_profile(
    season: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
) -> dict[str, Any]:
    """Compute diurnal generation and net load profiles alongside evening ramping inflection metrics."""
    seasons_list = None
    if season and season.strip().lower() != "all":
        if season not in VALID_SEASONS:
            raise ValueError(f"Invalid season '{season}'. Must be one of {sorted(VALID_SEASONS)} or 'All'")
        seasons_list = [season]

    where_str, params = build_filter_clause("date_ist", "season", from_date, to_date, seasons_list)
    if where_str:
        where_str += " AND demand_mw IS NOT NULL"
    else:
        where_str = "WHERE demand_mw IS NOT NULL"

    query = f"""
        SELECT
            hour_ist AS hour,
            ROUND(AVG(demand_mw), 1) AS demand_mw,
            ROUND(AVG(solar_mw), 1) AS solar_mw,
            ROUND(AVG(wind_mw), 1) AS wind_mw,
            ROUND(AVG(net_load_mw), 1) AS net_load_mw,
            ROUND(AVG(re_penetration_pct), 2) AS re_penetration_pct
        FROM mart_net_load_profile
        {where_str}
        GROUP BY hour_ist
        ORDER BY hour_ist ASC;
    """
    with closing(get_connection()) as conn:
        rows = conn.execute(query, params).fetchall()
        profile = [dict(r) for r in rows]

        if not profile:
            return {
                "season": season or "All",
                "solar_peak_mw": None,
                "solar_peak_hour": None,
                "net_load_trough_mw": None,
                "net_load_trough_hour": None,
                "evening_peak_mw": None,
                "evening_peak_hour": None,
                "trough_to_peak_ramp_mw": None,
                "hourly_profile": [],
            }

        solar_peak_entry = max(profile, key=lambda x: x["solar_mw"] if x["solar_mw"] is not None else 0.0)
        daylight_hours = [x for x in profile if 9 <= x["hour"] <= 16 and x["net_load_mw"] is not None]
        net_load_trough_entry = (
            min(daylight_hours, key=lambda x: x["net_load_mw"])
            if daylight_hours
            else min(
                (x for x in profile if x["net_load_mw"] is not None),
                key=lambda x: x["net_load_mw"],
                default={"hour": None, "net_load_mw": None},
            )
        )
        evening_hours = [x for x in profile if 18 <= x["hour"] <= 23 and x["net_load_mw"] is not None]
        evening_peak_entry = (
            max(evening_hours, key=lambda x: x["net_load_mw"])
            if evening_hours
            else max(
                (x for x in profile if x["net_load_mw"] is not None),
                key=lambda x: x["net_load_mw"],
                default={"hour": None, "net_load_mw": None},
            )
        )

        ramp_mw = None
        if evening_peak_entry["net_load_mw"] is not None and net_load_trough_entry["net_load_mw"] is not None:
            ramp_mw = round(evening_peak_entry["net_load_mw"] - net_load_trough_entry["net_load_mw"], 1)

        return {
            "season": season or "All",
            "solar_peak_mw": solar_peak_entry["solar_mw"],
            "solar_peak_hour": solar_peak_entry["hour"],
            "net_load_trough_mw": net_load_trough_entry["net_load_mw"],
            "net_load_trough_hour": net_load_trough_entry["hour"],
            "evening_peak_mw": evening_peak_entry["net_load_mw"],
            "evening_peak_hour": evening_peak_entry["hour"],
            "trough_to_peak_ramp_mw": ramp_mw,
            "hourly_profile": profile,
        }


def get_monthly_re_share(
    from_date: str | None = None,
    to_date: str | None = None,
    seasons: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Retrieve monthly average renewable generation share and capacity contribution."""
    where_net, params_net = build_filter_clause("date_ist", "season", from_date, to_date, seasons)
    if where_net:
        where_net += " AND demand_mw IS NOT NULL"
    else:
        where_net = "WHERE demand_mw IS NOT NULL"

    where_psp, params_psp = build_filter_clause("report_date", None, from_date, to_date, None)
    if where_psp:
        where_psp += " AND res_share_pct IS NOT NULL"
    else:
        where_psp = "WHERE res_share_pct IS NOT NULL"

    if seasons:
        months = [m for season in seasons for m in SEASON_MONTHS[season]]
        where_psp += (
            " AND CAST(strftime('%m', report_date) AS INTEGER) IN (" + ",".join("?" for _ in months) + ")"
        )
        params_psp.extend(months)
    params = params_net + params_psp
    query = f"""
        WITH net_monthly AS (
            SELECT
                strftime('%Y-%m', timestamp_ist) AS year_month,
                ROUND(AVG(re_penetration_pct), 2) AS avg_re_share_pct,
                ROUND(AVG(solar_mw), 1) AS avg_solar_mw,
                ROUND(AVG(wind_mw), 1) AS avg_wind_mw,
                ROUND(AVG(demand_mw), 1) AS avg_demand_mw
            FROM mart_net_load_profile
            {where_net}
            GROUP BY year_month
        ),
        psp_monthly AS (
            SELECT
                substr(report_date, 1, 7) AS year_month,
                ROUND(AVG((solar_gen_mu + wind_gen_mu) * 100.0 / NULLIF(energy_met_mu, 0)), 2) AS avg_re_share_pct,
                ROUND(AVG(solar_gen_mu * 1000.0 / 24.0), 1) AS avg_solar_mw,
                ROUND(AVG(wind_gen_mu * 1000.0 / 24.0), 1) AS avg_wind_mw,
                ROUND(AVG(energy_met_mu * 1000.0 / 24.0), 1) AS avg_demand_mw
            FROM stg_daily_psp
            {where_psp}
              AND substr(report_date, 1, 7) NOT IN (SELECT year_month FROM net_monthly)
            GROUP BY year_month
        ),
        combined AS (
            SELECT * FROM net_monthly
            UNION ALL
            SELECT * FROM psp_monthly
        )
        SELECT
            year_month,
            avg_re_share_pct,
            avg_solar_mw,
            avg_wind_mw,
            avg_demand_mw
        FROM combined
        ORDER BY year_month ASC;
    """
    with closing(get_connection()) as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_demand_anomalies(
    from_date: str | None = None,
    to_date: str | None = None,
    seasons: list[str] | None = None,
) -> dict[str, Any]:
    """Retrieve normalized demand deviation scores alongside classified real and data-quality anomalies."""
    where_str, params = build_filter_clause("date_ist", "season", from_date, to_date, seasons)
    query = f"""
        SELECT
            date_ist AS date,
            season,
            weekday_name,
            ROUND(avg_daily_demand_mw, 1) AS avg_demand_mw,
            ROUND(peak_daily_demand_mw, 1) AS peak_demand_mw,
            ROUND(baseline_avg_mw, 1) AS baseline_avg_mw,
            ROUND(baseline_std_mw, 1) AS baseline_std_mw,
            ROUND(z_score, 2) AS z_score,
            is_real_anomaly,
            is_dq_anomaly,
            is_anomaly,
            anomaly_type
        FROM mart_anomaly_days
        {where_str}
        ORDER BY date_ist ASC;
    """
    with closing(get_connection()) as conn:
        rows = conn.execute(query, params).fetchall()
        data = [dict(r) for r in rows]
        total_anomalies = sum(1 for d in data if d.get("is_anomaly") == 1)
        real_anomalies = sum(1 for d in data if d.get("is_real_anomaly") == 1)
        dq_anomalies = sum(1 for d in data if d.get("is_dq_anomaly") == 1)

        return {
            "total_days": len(data),
            "anomalies_count": total_anomalies,
            "real_count": real_anomalies,
            "dq_count": dq_anomalies,
            "data": data,
        }


def get_top_net_load_ramps(
    from_date: str | None = None,
    to_date: str | None = None,
    seasons: list[str] | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Retrieve top 1-hour net-load ramping events cross-referenced with Grid-India daily peak demand."""
    clauses: list[str] = []
    params: list[Any] = []

    if from_date:
        clauses.append("r.date_ist >= ?")
        params.append(from_date)
    if to_date:
        clauses.append("r.date_ist <= ?")
        params.append(to_date)
    if seasons:
        placeholders = ", ".join(["?"] * len(seasons))
        clauses.append(f"a.season IN ({placeholders})")
        params.extend(seasons)

    where_str = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    query = f"""
        SELECT
            r.timestamp_ist,
            r.date_ist,
            r.hour_ist,
            a.season,
            ROUND(r.demand_mw, 1) AS demand_mw,
            ROUND(r.solar_mw, 1) AS solar_mw,
            ROUND(r.wind_mw, 1) AS wind_mw,
            ROUND(r.net_load_mw, 1) AS net_load_mw,
            ROUND(r.ramp_1h_mw, 1) AS ramp_1h_mw,
            ROUND(r.abs_ramp_1h_mw, 1) AS abs_ramp_1h_mw,
            ROUND(p.max_demand_met_mw, 1) AS grid_india_peak_mw
        FROM mart_net_load_ramps r
        LEFT JOIN mart_anomaly_days a ON r.date_ist = a.date_ist
        LEFT JOIN stg_daily_psp p ON r.date_ist = p.report_date
        {where_str}
        ORDER BY r.abs_ramp_1h_mw DESC
        LIMIT ?;
    """
    params.append(limit)

    with closing(get_connection()) as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_pipeline_health() -> dict[str, Any]:
    """Retrieve automated test status records, execution audit history, and database layer volume."""
    with closing(get_connection()) as conn:
        checks_rows = conn.execute("""
            SELECT id, checked_at, check_name, table_name, status, details
            FROM data_quality_checks
            WHERE id IN (SELECT MAX(id) FROM data_quality_checks GROUP BY check_name)
            ORDER BY check_name ASC;
        """).fetchall()

        runs_rows = conn.execute("""
            SELECT id, run_at, stage, source, rows_fetched, rows_inserted, duration_s, status, message
            FROM pipeline_runs
            ORDER BY id DESC
            LIMIT 12;
        """).fetchall()

        table_rows = conn.execute("""
            SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';
        """).fetchall()

        table_counts: dict[str, int] = {}
        for t in table_rows:
            t_name = t[0]
            try:
                cnt = conn.execute(f"SELECT COUNT(*) FROM {t_name};").fetchone()[0]
                table_counts[t_name] = cnt
            except Exception:
                table_counts[t_name] = 0

        return {
            "checks": [dict(r) for r in checks_rows],
            "runs": [dict(r) for r in runs_rows],
            "table_counts": table_counts,
        }


def export_table_csv(
    name: str,
    from_date: str | None = None,
    to_date: str | None = None,
    seasons: list[str] | None = None,
) -> str:
    """Generate formatted CSV text for filtered analytical table exports."""
    valid_exports = {
        "daily-demand": ("mart_anomaly_days", "date_ist", "season"),
        "anomalies": ("mart_anomaly_days", "date_ist", "season"),
        "ramps": ("mart_net_load_ramps", "date_ist", None),
        "monthly-peaks": ("mart_monthly_peak_demand", "year_month", None),
    }

    if name not in valid_exports:
        raise ValueError(
            f"Invalid export name '{name}'. Valid exports are: {', '.join(sorted(valid_exports))}"
        )

    table_name, date_col, season_col = valid_exports[name]

    if name == "daily-demand":
        records = get_daily_demand(from_date, to_date, seasons)
    elif name == "anomalies":
        res = get_demand_anomalies(from_date, to_date, seasons)
        records = res["data"]
    elif name == "ramps":
        records = get_top_net_load_ramps(from_date, to_date, seasons, limit=50)
    elif name == "monthly-peaks":
        records = get_monthly_peaks(from_date, to_date, seasons)
    else:
        records = []

    if not records:
        return ""

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(records[0].keys()))
    writer.writeheader()
    writer.writerows(records)
    return output.getvalue()
