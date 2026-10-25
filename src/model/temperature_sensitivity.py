"""Temperature sensitivity regression model.

Estimates the cooling sensitivity of India's electricity demand (MW per °C)
above cooling balance point using daily aggregated peak demand met from Grid-India
joined with multi-city weather reanalysis, controlling for weekday, month, and year fixed effects.
"""

from __future__ import annotations

import sqlite3
from typing import Any
import numpy as np
import pandas as pd

from src.utils.config import DB_PATH
from src.utils.logging import get_logger

log = get_logger(__name__)


def fit_controlled_ols(df_subset: pd.DataFrame, col_x: str, col_y: str) -> dict[str, Any]:
    """Fit ordinary least squares with categorical controls for weekday, month, and year."""
    dummies_weekday = pd.get_dummies(df_subset["weekday_str"], prefix="w", drop_first=True, dtype=float)
    dummies_month = pd.get_dummies(df_subset["month_str"], prefix="m", drop_first=True, dtype=float)
    dummies_year = pd.get_dummies(df_subset["year_str"], prefix="y", drop_first=True, dtype=float)
    
    X = pd.concat([df_subset[[col_x]], dummies_weekday, dummies_month, dummies_year], axis=1)
    X.insert(0, "intercept", 1.0)
    
    X_mat = X.values
    y_vec = df_subset[col_y].values
    
    n, p = X_mat.shape
    beta, residuals, rank, s = np.linalg.lstsq(X_mat, y_vec, rcond=None)
    
    preds = X_mat @ beta
    resid = y_vec - preds
    sse = np.sum(resid ** 2)
    sst = np.sum((y_vec - np.mean(y_vec)) ** 2)
    r2 = 1.0 - (sse / sst) if sst > 0 else 0.0
    
    df_resid = n - p
    sigma2 = sse / df_resid if df_resid > 0 else 0.0
    cov_beta = np.linalg.pinv(X_mat.T @ X_mat) * sigma2
    se_beta = np.sqrt(np.maximum(0.0, np.diag(cov_beta)))
    
    slope = float(beta[1])
    se_slope = float(se_beta[1])
    ci_lower = slope - 1.96 * se_slope
    ci_upper = slope + 1.96 * se_slope
    aic = float(n * np.log(sse / n) + 2 * p)
    
    return {
        "slope": slope,
        "se": se_slope,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "r2": r2,
        "aic": aic,
        "n": n
    }


def compute_temperature_sensitivity(conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Compute temperature sensitivity with controls and threshold justification."""
    close_conn = False
    if conn is None:
        conn = sqlite3.connect(DB_PATH)
        close_conn = True

    try:
        df = pd.read_sql("""
            SELECT report_date, year_str, month_str, weekday_str, max_demand_met_mw, daily_mean_temp_c 
            FROM mart_daily_weather_demand 
            WHERE daily_mean_temp_c IS NOT NULL AND max_demand_met_mw IS NOT NULL
        """, conn)

        if df.empty or len(df) < 20:
            log.warning("Insufficient data in mart_daily_weather_demand for regression")
            return {
                "slope_mw_per_c": 0,
                "ci_lower": 0,
                "ci_upper": 0,
                "r2": 0.0,
                "n_days": 0,
                "temp_min_c": 0.0,
                "temp_max_c": 0.0,
                "thresholds": []
            }

        temp_min = float(df["daily_mean_temp_c"].min())
        temp_max = float(df["daily_mean_temp_c"].max())

        # Compare candidate thresholds (22°C to 27°C)
        threshold_results = []
        for t in [22.0, 23.0, 24.0, 25.0, 26.0, 27.0]:
            df_warm = df[df["daily_mean_temp_c"] >= t].copy()
            if len(df_warm) < 25:
                continue
            df_warm["cooling_deg"] = df_warm["daily_mean_temp_c"] - t
            fit = fit_controlled_ols(df_warm, "cooling_deg", "max_demand_met_mw")
            threshold_results.append({
                "threshold_c": t,
                "n_days": fit["n"],
                "slope_mw_per_c": round(fit["slope"], 1),
                "ci_lower": round(fit["ci_lower"], 1),
                "ci_upper": round(fit["ci_upper"], 1),
                "r2": round(fit["r2"], 4),
                "aic": round(fit["aic"], 1)
            })

        # Baseline balance point at 25.0°C
        df_25 = df[df["daily_mean_temp_c"] >= 25.0].copy()
        df_25["cooling_deg"] = df_25["daily_mean_temp_c"] - 25.0
        fit_25 = fit_controlled_ols(df_25, "cooling_deg", "max_demand_met_mw")

        return {
            "slope_mw_per_c": int(round(fit_25["slope"])),
            "ci_lower": int(round(fit_25["ci_lower"])),
            "ci_upper": int(round(fit_25["ci_upper"])),
            "r2": round(fit_25["r2"], 4),
            "n_days": fit_25["n"],
            "temp_min_c": round(temp_min, 1),
            "temp_max_c": round(temp_max, 1),
            "threshold_choice_c": 25.0,
            "thresholds": threshold_results
        }
    finally:
        if close_conn:
            conn.close()


if __name__ == "__main__":
    res = compute_temperature_sensitivity()
    print("Temperature Sensitivity Results:", res)
