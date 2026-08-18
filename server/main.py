from __future__ import annotations

import datetime as dt
from pathlib import Path
import re
import time
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from server import queries
from src.utils.config import ROOT_DIR

app = FastAPI(
    title="India Power Demand & Weather Pipeline API",
    description="Operational analytics and econometric sensitivity API for India electricity demand, renewables, and weather.",
    version="2.0.0",
)

app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CACHE_TTL_SECONDS = 30.0
_IN_MEMORY_CACHE: dict[str, tuple[float, Any]] = {}


def get_cached_response(cache_key: str) -> Any | None:
    """Retrieve unexpired payload from in-memory cache if available."""
    if cache_key in _IN_MEMORY_CACHE:
        timestamp, data = _IN_MEMORY_CACHE[cache_key]
        if time.time() - timestamp < CACHE_TTL_SECONDS:
            return data
        del _IN_MEMORY_CACHE[cache_key]
    return None


def set_cached_response(cache_key: str, data: Any) -> None:
    """Store serializable payload in in-memory cache with eviction for old items."""
    now = time.time()
    if len(_IN_MEMORY_CACHE) > 200:
        expired_keys = [k for k, (t, _) in _IN_MEMORY_CACHE.items() if now - t >= CACHE_TTL_SECONDS]
        for k in expired_keys:
            _IN_MEMORY_CACHE.pop(k, None)
    _IN_MEMORY_CACHE[cache_key] = (now, data)


def validate_iso_date(date_str: str | None, param_name: str) -> str | None:
    """Ensure date parameter conforms strictly to YYYY-MM-DD representation."""
    if not date_str:
        return None
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        raise HTTPException(status_code=422, detail=f"Invalid {param_name} date '{date_str}'. Expected format YYYY-MM-DD.")
    try:
        dt.date.fromisoformat(date_str)
    except ValueError as err:
        raise HTTPException(status_code=422, detail=f"Invalid calendar date for {param_name}: {err}") from err
    return date_str


def parse_validated_seasons(seasons: str | None) -> list[str] | None:
    """Validate and parse seasons parameter string into verified seasonal list."""
    try:
        return queries.parse_seasons_param(seasons)
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err)) from err


@app.get("/api/summary")
def get_summary() -> dict[str, Any]:
    """Return top-level headline operational indicators and pipeline audit status."""
    cache_key = "summary"
    cached = get_cached_response(cache_key)
    if cached is not None:
        return cached

    result = queries.get_summary_metrics()
    set_cached_response(cache_key, result)
    return result


@app.get("/api/daily-demand")
def get_daily_demand(
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    seasons: str | None = Query(None),
) -> list[dict[str, Any]]:
    """Return daily average and peak power demand with 7-day rolling baseline."""
    valid_from = validate_iso_date(from_date, "from")
    valid_to = validate_iso_date(to_date, "to")
    valid_seasons = parse_validated_seasons(seasons)

    cache_key = f"daily_demand:{valid_from}:{valid_to}:{seasons}"
    cached = get_cached_response(cache_key)
    if cached is not None:
        return cached

    result = queries.get_daily_demand(valid_from, valid_to, valid_seasons)
    set_cached_response(cache_key, result)
    return result


@app.get("/api/monthly-peaks")
def get_monthly_peaks(
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    seasons: str | None = Query(None),
) -> list[dict[str, Any]]:
    """Return monthly maximum demand records and year-over-year escalation percentages."""
    valid_from = validate_iso_date(from_date, "from")
    valid_to = validate_iso_date(to_date, "to")
    valid_seasons = parse_validated_seasons(seasons)

    cache_key = f"monthly_peaks:{valid_from}:{valid_to}:{seasons}"
    cached = get_cached_response(cache_key)
    if cached is not None:
        return cached

    result = queries.get_monthly_peaks(valid_from, valid_to, valid_seasons)
    set_cached_response(cache_key, result)
    return result


@app.get("/api/temp-demand")
def get_temp_demand(
    feature: str = Query("avg_temperature_c"),
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    seasons: str | None = Query(None),
) -> dict[str, Any]:
    """Return sampled hourly temperature versus demand observations with 1C median bins."""
    valid_from = validate_iso_date(from_date, "from")
    valid_to = validate_iso_date(to_date, "to")
    valid_seasons = parse_validated_seasons(seasons)

    if feature not in queries.VALID_FEATURES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid feature '{feature}'. Valid features are: {', '.join(sorted(queries.VALID_FEATURES))}",
        )

    cache_key = f"temp_demand:{feature}:{valid_from}:{valid_to}:{seasons}"
    cached = get_cached_response(cache_key)
    if cached is not None:
        return cached

    result = queries.get_temp_vs_demand(feature, valid_from, valid_to, valid_seasons)
    set_cached_response(cache_key, result)
    return result


@app.get("/api/heatmap")
def get_heatmap(
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    seasons: str | None = Query(None),
) -> list[dict[str, Any]]:
    """Return average demand matrix across months and hours of the day."""
    valid_from = validate_iso_date(from_date, "from")
    valid_to = validate_iso_date(to_date, "to")
    valid_seasons = parse_validated_seasons(seasons)

    cache_key = f"heatmap:{valid_from}:{valid_to}:{seasons}"
    cached = get_cached_response(cache_key)
    if cached is not None:
        return cached

    result = queries.get_demand_heatmap(valid_from, valid_to, valid_seasons)
    set_cached_response(cache_key, result)
    return result


@app.get("/api/sensitivity")
def get_sensitivity() -> dict[str, Any]:
    """Return full-sample hinge regression temperature sensitivity model parameters."""
    cache_key = "sensitivity"
    cached = get_cached_response(cache_key)
    if cached is not None:
        return cached

    result = queries.get_sensitivity_analysis()
    set_cached_response(cache_key, result)
    return result


@app.get("/api/duck-curve")
def get_duck_curve(
    season: str = Query("All"),
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
) -> dict[str, Any]:
    """Return diurnal generation profile and dusk ramping inflection metrics."""
    valid_from = validate_iso_date(from_date, "from")
    valid_to = validate_iso_date(to_date, "to")

    try:
        result = queries.get_duck_curve_profile(season, valid_from, valid_to)
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err)) from err

    return result


@app.get("/api/re-share")
def get_re_share(
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    seasons: str | None = Query(None),
) -> list[dict[str, Any]]:
    """Return monthly average renewable penetration and technology breakdown."""
    valid_from = validate_iso_date(from_date, "from")
    valid_to = validate_iso_date(to_date, "to")
    valid_seasons = parse_validated_seasons(seasons)

    cache_key = f"re_share:{valid_from}:{valid_to}:{seasons}"
    cached = get_cached_response(cache_key)
    if cached is not None:
        return cached

    result = queries.get_monthly_re_share(valid_from, valid_to, valid_seasons)
    set_cached_response(cache_key, result)
    return result


@app.get("/api/anomalies")
def get_anomalies(
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    seasons: str | None = Query(None),
) -> dict[str, Any]:
    """Return daily z-scores and segmented operational versus data-quality outliers."""
    valid_from = validate_iso_date(from_date, "from")
    valid_to = validate_iso_date(to_date, "to")
    valid_seasons = parse_validated_seasons(seasons)

    cache_key = f"anomalies:{valid_from}:{valid_to}:{seasons}"
    cached = get_cached_response(cache_key)
    if cached is not None:
        return cached

    result = queries.get_demand_anomalies(valid_from, valid_to, valid_seasons)
    set_cached_response(cache_key, result)
    return result


@app.get("/api/ramps")
def get_ramps(
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    seasons: str | None = Query(None),
) -> list[dict[str, Any]]:
    """Return top 10 hourly net-load ramping events with official peak cross-check."""
    valid_from = validate_iso_date(from_date, "from")
    valid_to = validate_iso_date(to_date, "to")
    valid_seasons = parse_validated_seasons(seasons)

    cache_key = f"ramps:{valid_from}:{valid_to}:{seasons}"
    cached = get_cached_response(cache_key)
    if cached is not None:
        return cached

    result = queries.get_top_net_load_ramps(valid_from, valid_to, valid_seasons, limit=10)
    set_cached_response(cache_key, result)
    return result


@app.get("/api/health")
def get_health() -> dict[str, Any]:
    """Return comprehensive data quality assertions, pipeline execution audit, and table volumes."""
    cache_key = "health"
    cached = get_cached_response(cache_key)
    if cached is not None:
        return cached

    result = queries.get_pipeline_health()
    set_cached_response(cache_key, result)
    return result


@app.get("/api/export/{name}.csv")
def export_csv(
    name: str,
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    seasons: str | None = Query(None),
) -> Response:
    """Stream parameterised CSV text export for analytical data marts."""
    valid_from = validate_iso_date(from_date, "from")
    valid_to = validate_iso_date(to_date, "to")
    valid_seasons = parse_validated_seasons(seasons)

    try:
        csv_text = queries.export_table_csv(name, valid_from, valid_to, valid_seasons)
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err)) from err

    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{name}.csv"'},
    )


@app.get("/favicon.ico")
def favicon() -> Response:
    """Return lightweight lightning favicon to suppress browser 404s."""
    svg_icon = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="90">&#9889;</text></svg>'
    return Response(content=svg_icon, media_type="image/svg+xml")


web_dir = ROOT_DIR / "web"
web_dir.mkdir(parents=True, exist_ok=True)
app.mount("/", StaticFiles(directory=str(web_dir), html=True), name="web")
