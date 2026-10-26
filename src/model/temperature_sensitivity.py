"""Temperature sensitivity regression model.

Estimates the cooling sensitivity of India's electricity demand (MW per °C)
above cooling balance point using daily aggregated peak demand met from Grid-India
joined with multi-city weather reanalysis, controlling for weekday, month, and year fixed effects.

Methodology:
- Single full-sample model: Evaluated on all daily observations (725 days).
- Hinge function: Evaluates cooling degree days CDD = max(T - threshold, 0) across 22.0°C to 28.0°C.
- Baseline Controls: Fits Controls-Only OLS (intercept + weekday, month, year dummies) on all observations.
- Full Model: Fits OLS with hinge term + controls, computing White's Heteroskedasticity-Consistent (HC1) robust SEs.
- Stated Selection: 25.0°C is chosen a priori as a standard cooling base temperature for power systems analysis; candidate thresholds from 22.0°C to 28.0°C are evaluated for sensitivity.
"""

from __future__ import annotations

import sqlite3
from typing import Any
import numpy as np
import pandas as pd

from src.utils.config import DB_PATH
from src.utils.logging import get_logger

log = get_logger(__name__)


def fit_ols_hc1(X_df: pd.DataFrame, y_series: pd.Series) -> dict[str, Any]:
    """Fit OLS regression with White's Heteroskedasticity-Consistent (HC1) robust covariance."""
    X_mat = X_df.values
    y_vec = y_series.values
    n, p = X_mat.shape

    beta, _, _, _ = np.linalg.lstsq(X_mat, y_vec, rcond=None)
    preds = X_mat @ beta
    resid = y_vec - preds
    sse = float(np.sum(resid**2))
    sst = float(np.sum((y_vec - np.mean(y_vec)) ** 2))
    r2 = 1.0 - (sse / sst) if sst > 0 else 0.0
    rmse = float(np.sqrt(sse / n))

    df_resid = max(1, n - p)
    bread = np.linalg.pinv(X_mat.T @ X_mat)
    # White's HC1 adjustment: (n / (n - p)) * bread @ (X' diag(e^2) X) @ bread
    meat = X_mat.T @ (resid[:, None] ** 2 * X_mat)
    cov_hc1 = (n / df_resid) * (bread @ meat @ bread)
    se_hc1 = np.sqrt(np.maximum(0.0, np.diag(cov_hc1)))

    aic = float(n * np.log(sse / n) + 2 * p)
    bic = float(n * np.log(sse / n) + p * np.log(n))

    return {
        "beta": beta,
        "se_hc1": se_hc1,
        "r2": r2,
        "sse": sse,
        "rmse": rmse,
        "aic": aic,
        "bic": bic,
        "n": n,
        "p": p,
    }


def compute_temperature_sensitivity(conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Compute temperature sensitivity using full-sample hinge regression with controls and HC1 robust SEs."""
    close_conn = False
    if conn is None:
        conn = sqlite3.connect(DB_PATH)
        close_conn = True

    try:
        df = pd.read_sql(
            """
            SELECT report_date, year_str, month_str, weekday_str, max_demand_met_mw, daily_mean_temp_c 
            FROM mart_daily_weather_demand 
            WHERE daily_mean_temp_c IS NOT NULL AND max_demand_met_mw IS NOT NULL
            ORDER BY report_date;
        """,
            conn,
        )

        if df.empty or len(df) < 25:
            log.warning("Insufficient data in mart_daily_weather_demand for regression")
            return {
                "slope_mw_per_c": 0,
                "se_hc1": 0.0,
                "ci_lower": 0,
                "ci_upper": 0,
                "r2": 0.0,
                "r2_ctrl": 0.0,
                "r2_full": 0.0,
                "delta_r2": 0.0,
                "n_days": 0,
                "n_total": 0,
                "temp_min_c": 0.0,
                "temp_max_c": 0.0,
                "threshold_choice_c": 25.0,
                "threshold_criterion": "A priori selection of 25.0°C cooling base with sensitivity analysis across 22.0°C to 28.0°C",
                "thresholds": [],
            }

        total_obs = len(df)
        temp_min_all = float(df["daily_mean_temp_c"].min())
        temp_max_all = float(df["daily_mean_temp_c"].max())

        # Baseline controls-only model on ALL observations (725 days)
        d_week = pd.get_dummies(df["weekday_str"], prefix="w", drop_first=True, dtype=float)
        d_month = pd.get_dummies(df["month_str"], prefix="m", drop_first=True, dtype=float)
        d_year = pd.get_dummies(df["year_str"], prefix="y", drop_first=True, dtype=float)

        X_ctrl = pd.concat(
            [pd.Series(1.0, index=df.index, name="intercept"), d_week, d_month, d_year], axis=1
        )
        fit_ctrl = fit_ols_hc1(X_ctrl, df["max_demand_met_mw"])
        r2_ctrl = float(fit_ctrl["r2"])

        # Candidate thresholds from 22.0°C to 28.0°C evaluated on the SAME full sample
        candidate_thresholds = [22.0, 23.0, 24.0, 25.0, 26.0, 27.0, 28.0]
        threshold_results = []

        for t in candidate_thresholds:
            # Full-sample hinge term: max(T - threshold, 0)
            cooling_deg = np.maximum(0.0, df["daily_mean_temp_c"].values - t)
            n_days_above = int((df["daily_mean_temp_c"] >= t).sum())

            X_full = pd.concat(
                [
                    pd.Series(1.0, index=df.index, name="intercept"),
                    pd.Series(cooling_deg, index=df.index, name="cooling_deg"),
                    d_week,
                    d_month,
                    d_year,
                ],
                axis=1,
            )

            fit_full = fit_ols_hc1(X_full, df["max_demand_met_mw"])

            slope = float(fit_full["beta"][1])
            se_slope = float(fit_full["se_hc1"][1])
            ci_lower = slope - 1.96 * se_slope
            ci_upper = slope + 1.96 * se_slope
            r2_full = float(fit_full["r2"])
            delta_r2 = r2_full - r2_ctrl

            threshold_results.append(
                {
                    "threshold_c": t,
                    "n_days_above": n_days_above,
                    "n_obs": total_obs,
                    "slope_mw_per_c": round(slope, 1),
                    "se_hc1": round(se_slope, 1),
                    "ci_lower": round(ci_lower, 1),
                    "ci_upper": round(ci_upper, 1),
                    "r2_ctrl": round(r2_ctrl, 4),
                    "r2_full": round(r2_full, 4),
                    "delta_r2": round(delta_r2, 4),
                    "aic": round(fit_full["aic"], 1),
                    "rmse": round(fit_full["rmse"], 1),
                }
            )

        # Baseline chosen threshold: 25.0°C
        choice = next((r for r in threshold_results if r["threshold_c"] == 25.0), threshold_results[0])

        return {
            "slope_mw_per_c": int(round(choice["slope_mw_per_c"])),
            "se_hc1": choice["se_hc1"],
            "ci_lower": int(round(choice["ci_lower"])),
            "ci_upper": int(round(choice["ci_upper"])),
            "r2": choice["r2_full"],
            "r2_ctrl": choice["r2_ctrl"],
            "r2_full": choice["r2_full"],
            "delta_r2": choice["delta_r2"],
            "n_days": choice["n_days_above"],
            "n_total": total_obs,
            "temp_min_c": round(temp_min_all, 1),
            "temp_max_c": round(temp_max_all, 1),
            "threshold_choice_c": 25.0,
            "threshold_criterion": "A priori selection of 25.0°C cooling base with full-sample hinge sensitivity across 22.0°C to 28.0°C",
            "thresholds": threshold_results,
        }
    finally:
        if close_conn:
            conn.close()


if __name__ == "__main__":
    res = compute_temperature_sensitivity()
    print("Full-Sample Hinge Model Results:", res)
