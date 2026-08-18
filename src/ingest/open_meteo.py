"""Open-Meteo Historical & Recent Weather Ingest Module.

Fetches hourly weather variables (temperature, relative humidity, wind speed)
for major Indian demand centres from Open-Meteo Archive API and seamlessly supplements
the most recent days using Open-Meteo Forecast API with past_days.
"""

from __future__ import annotations

import datetime as dt
from typing import Any
import requests
from sqlalchemy import text

from src.utils.config import CITIES
from src.utils.db import get_engine, init_db
from src.utils.logging import get_logger

log = get_logger(__name__)

ARCHIVE_API_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_API_URL = "https://api.open-meteo.com/v1/forecast"


def create_raw_weather_table() -> None:
    """Create raw_weather table if not exists."""
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS raw_weather (
                city             TEXT NOT NULL,
                timestamp_ist    TEXT NOT NULL,
                temperature_2m   REAL,
                relative_humidity_2m REAL,
                wind_speed_10m   REAL,
                ingested_at      TEXT NOT NULL,
                PRIMARY KEY (city, timestamp_ist)
            );
        """))
        conn.commit()


def fetch_city_weather_archive(
    city: str,
    lat: float,
    lon: float,
    start_date: str,
    end_date: str
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
    resp = requests.get(ARCHIVE_API_URL, params=params, timeout=45)
    resp.raise_for_status()
    data = resp.json().get("hourly", {})

    times = data.get("time", [])
    temps = data.get("temperature_2m", [])
    humids = data.get("relative_humidity_2m", [])
    winds = data.get("wind_speed_10m", [])

    records = []
    for t, temp, rh, ws in zip(times, temps, humids, winds):
        records.append({
            "city": city,
            "timestamp_ist": t,
            "temperature_2m": temp,
            "relative_humidity_2m": rh,
            "wind_speed_10m": ws,
        })
    return records


def fetch_city_weather_recent(
    city: str,
    lat: float,
    lon: float,
    past_days: int = 7
) -> list[dict[str, Any]]:
    """Fetch recent days from Forecast API to cover archive latency."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "past_days": past_days,
        "forecast_days": 1,
        "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m",
        "timezone": "Asia/Kolkata",
    }
    try:
        resp = requests.get(FORECAST_API_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json().get("hourly", {})

        times = data.get("time", [])
        temps = data.get("temperature_2m", [])
        humids = data.get("relative_humidity_2m", [])
        winds = data.get("wind_speed_10m", [])

        # Filter out future hours beyond current IST time
        now_ist = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=5, minutes=30)
        now_str = now_ist.strftime("%Y-%m-%dT%H:%M")

        records = []
        for t, temp, rh, ws in zip(times, temps, humids, winds):
            if t <= now_str:
                records.append({
                    "city": city,
                    "timestamp_ist": t,
                    "temperature_2m": temp,
                    "relative_humidity_2m": rh,
                    "wind_speed_10m": ws,
                })
        return records
    except Exception as e:
        log.warning("Forecast API fetch failed for %s: %s", city, e)
        return []


def ingest_weather(start_date: str = "2021-09-01", end_date: str | None = None) -> int:
    """Ingest weather records up to yesterday across all configured cities."""
    init_db()
    create_raw_weather_table()
    engine = get_engine()

    today = dt.date.today()
    yesterday = today - dt.timedelta(days=1)
    if end_date is None:
        end_date = yesterday.isoformat()

    now_iso = dt.datetime.now(dt.timezone.utc).isoformat()
    total_inserted = 0

    for city, coords in CITIES.items():
        log.info("Fetching weather for %s (%s to %s)...", city, start_date, end_date)
        try:
            # 1. Fetch from Archive API
            archive_end = (today - dt.timedelta(days=5)).isoformat()
            records = fetch_city_weather_archive(city, coords["lat"], coords["lon"], start_date, min(end_date, archive_end))

            # 2. Fetch last 7 days from Forecast API to ensure weather reaches yesterday
            recent_records = fetch_city_weather_recent(city, coords["lat"], coords["lon"], past_days=7)
            # Combine dicts keyed on timestamp
            rec_map = {r["timestamp_ist"]: r for r in records}
            for r in recent_records:
                if r["timestamp_ist"] <= f"{end_date}T23:00":
                    rec_map[r["timestamp_ist"]] = r

            final_records = list(rec_map.values())

            with engine.connect() as conn:
                conn.execute(text("""
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
                """), [{**rec, "ingested_at": now_iso} for rec in final_records])
                conn.commit()

            total_inserted += len(final_records)
            log.info("Loaded %d weather rows for %s", len(final_records), city)
        except Exception as e:
            log.error("Failed to fetch weather for %s: %s", city, e)

    log.info("Open-Meteo weather ingest complete: %d total rows", total_inserted)
    return total_inserted


if __name__ == "__main__":
    ingest_weather()
