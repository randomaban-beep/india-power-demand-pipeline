"""Open-Meteo Historical & Recent Weather Ingest Module.

Fetches hourly weather variables (temperature, relative humidity, wind speed)
for major Indian demand centres from Open-Meteo Archive API and seamlessly supplements
the most recent days using Open-Meteo Forecast API with past_days.
"""

from __future__ import annotations

import datetime as dt
from typing import Any
from sqlalchemy import text

from src.utils.config import CITIES
from src.utils.db import get_engine, init_db
from src.utils.logging import get_logger
from src.utils.http import get

log = get_logger(__name__)

ARCHIVE_API_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_API_URL = "https://api.open-meteo.com/v1/forecast"


def validate_hourly(data: dict[str, Any]) -> None:
    """Reject missing, truncated, duplicate or malformed hourly API arrays."""
    keys = ("time", "temperature_2m", "relative_humidity_2m", "wind_speed_10m")
    if any(not isinstance(data.get(key), list) for key in keys):
        raise ValueError("Weather response is missing required hourly arrays")
    count = len(data["time"])
    if not count or any(len(data[key]) != count for key in keys):
        raise ValueError("Weather hourly arrays must be non-empty and equal length")
    timestamps = [dt.datetime.fromisoformat(t) for t in data["time"]]
    if any(t.minute or t.second or t.tzinfo is not None for t in timestamps):
        raise ValueError("Weather timestamps must be aligned hours in local IST")
    if any(b - a != dt.timedelta(hours=1) for a, b in zip(timestamps, timestamps[1:])):
        raise ValueError("Weather timestamps must be unique consecutive hours")
    for key in keys[1:]:
        if any(v is not None and (isinstance(v, bool) or not isinstance(v, (int, float))) for v in data[key]):
            raise ValueError(f"Weather {key} contains a nonnumeric value")


def create_raw_weather_table() -> None:
    """Create raw_weather table if not exists."""
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS raw_weather (
                city             TEXT NOT NULL,
                timestamp_ist    TEXT NOT NULL,
                temperature_2m   REAL,
                relative_humidity_2m REAL,
                wind_speed_10m   REAL,
                ingested_at      TEXT NOT NULL,
                PRIMARY KEY (city, timestamp_ist)
            );
        """)
        )
        conn.commit()


def fetch_city_weather_archive(
    city: str, lat: float, lon: float, start_date: str, end_date: str
) -> list[dict[str, Any]]:
    """Fetch hourly weather records for one city from Archive API."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m",
        "timezone": "Asia/Kolkata",
    }
    resp = get(ARCHIVE_API_URL, params=params, timeout=45)
    resp.raise_for_status()
    data = resp.json().get("hourly", {})
    validate_hourly(data)

    times = data.get("time", [])
    temps = data.get("temperature_2m", [])
    humids = data.get("relative_humidity_2m", [])
    winds = data.get("wind_speed_10m", [])

    records = []
    for t, temp, rh, ws in zip(times, temps, humids, winds):
        records.append(
            {
                "city": city,
                "timestamp_ist": t,
                "temperature_2m": temp,
                "relative_humidity_2m": rh,
                "wind_speed_10m": ws,
            }
        )
    return records


def fetch_city_weather_recent(city: str, lat: float, lon: float, past_days: int = 7) -> list[dict[str, Any]]:
    """Fetch recent days from Forecast API to cover archive latency."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "past_days": past_days,
        "forecast_days": 1,
        "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m",
        "timezone": "Asia/Kolkata",
    }
    resp = get(FORECAST_API_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json().get("hourly", {})
    validate_hourly(data)

    times = data.get("time", [])
    temps = data.get("temperature_2m", [])
    humids = data.get("relative_humidity_2m", [])
    winds = data.get("wind_speed_10m", [])

    now_ist = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=5, minutes=30)
    now_str = now_ist.strftime("%Y-%m-%dT%H:%M")

    records = []
    for t, temp, rh, ws in zip(times, temps, humids, winds):
        if t <= now_str:
            records.append(
                {
                    "city": city,
                    "timestamp_ist": t,
                    "temperature_2m": temp,
                    "relative_humidity_2m": rh,
                    "wind_speed_10m": ws,
                }
            )
    return records


def get_latest_city_weather_date(city: str) -> dt.date | None:
    """Find the newest recorded date for a given city in raw_weather."""
    engine = get_engine()
    with engine.connect() as conn:
        res = conn.execute(
            text("SELECT MAX(timestamp_ist) FROM raw_weather WHERE city = :city"), {"city": city}
        ).scalar()
        if res:
            return dt.date.fromisoformat(res[:10])
    return None


def ingest_weather(start_date: str | None = None, end_date: str | None = None) -> int:
    """Ingest weather records up to yesterday across all configured cities."""
    init_db()
    create_raw_weather_table()
    engine = get_engine()

    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).date()
    yesterday = today - dt.timedelta(days=1)
    if end_date is None:
        end_date = yesterday.isoformat()
    dt.date.fromisoformat(end_date)
    if start_date:
        dt.date.fromisoformat(start_date)
        if start_date > end_date:
            raise ValueError("Weather start_date must be on or before end_date")

    now_iso = dt.datetime.now(dt.timezone.utc).isoformat()
    total_inserted = 0

    for city, coords in CITIES.items():
        if start_date is not None:
            city_start_date = start_date
        else:
            latest_d = get_latest_city_weather_date(city)
            if latest_d is not None:
                city_start_date = (latest_d - dt.timedelta(days=7)).isoformat()
            else:
                city_start_date = "2021-09-01"

        if city_start_date > end_date:
            city_start_date = end_date

        log.info("Fetching weather for %s (%s to %s)...", city, city_start_date, end_date)
        try:
            records: list[dict[str, Any]] = []
            archive_end = (today - dt.timedelta(days=5)).isoformat()
            if city_start_date <= archive_end:
                records = fetch_city_weather_archive(
                    city, coords["lat"], coords["lon"], city_start_date, min(end_date, archive_end)
                )

            recent_records = (
                fetch_city_weather_recent(city, coords["lat"], coords["lon"], past_days=7)
                if end_date > archive_end
                else []
            )
            rec_map = {r["timestamp_ist"]: r for r in records}
            for r in recent_records:
                if (
                    r["timestamp_ist"] <= f"{end_date}T23:00"
                    and r["timestamp_ist"] >= f"{city_start_date}T00:00"
                ):
                    rec_map[r["timestamp_ist"]] = r

            final_records = list(rec_map.values())
            if not final_records:
                raise RuntimeError(
                    f"No weather records retrieved for {city} between {city_start_date} and {end_date}"
                )

            with engine.connect() as conn:
                conn.execute(
                    text("""
                    INSERT INTO raw_weather (
                        city, timestamp_ist, temperature_2m, relative_humidity_2m,
                        wind_speed_10m, ingested_at
                    ) VALUES (
                        :city, :timestamp_ist, :temperature_2m, :relative_humidity_2m,
                        :wind_speed_10m, :ingested_at
                    )
                    ON CONFLICT(city, timestamp_ist) DO UPDATE SET
                        temperature_2m=excluded.temperature_2m,
                        relative_humidity_2m=excluded.relative_humidity_2m,
                        wind_speed_10m=excluded.wind_speed_10m,
                        ingested_at=excluded.ingested_at;
                """),
                    [{**rec, "ingested_at": now_iso} for rec in final_records],
                )
                conn.commit()

            total_inserted += len(final_records)
            log.info("Loaded %d weather rows for %s", len(final_records), city)
        except Exception as e:
            log.error("Failed to fetch weather for %s: %s", city, e)
            raise RuntimeError(f"Open-Meteo weather fetch failed for {city}: {e}") from e

    log.info("Open-Meteo weather ingest complete: %d total rows", total_inserted)
    return total_inserted


if __name__ == "__main__":
    ingest_weather()
