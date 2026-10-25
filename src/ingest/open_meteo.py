"""Open-Meteo Historical Weather Ingest Module.

Fetches hourly weather variables (temperature, relative humidity, wind speed)
for major Indian demand centres from Open-Meteo Archive API and stores in raw_weather table.
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

API_URL = "https://archive-api.open-meteo.com/v1/archive"


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


def fetch_city_weather(
    city: str,
    lat: float,
    lon: float,
    start_date: str,
    end_date: str
) -> list[dict[str, Any]]:
    """Fetch hourly weather records for one city."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m",
        "timezone": "Asia/Kolkata",
    }
    resp = requests.get(API_URL, params=params, timeout=30)
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


def ingest_weather(start_date: str = "2022-01-01", end_date: str = "2022-12-31") -> int:
    """Ingest weather records for all configured cities into raw_weather."""
    init_db()
    create_raw_weather_table()
    engine = get_engine()
    
    now_iso = dt.datetime.now(dt.timezone.utc).isoformat()
    total_inserted = 0

    for city, coords in CITIES.items():
        log.info("Fetching weather for %s (%s to %s)...", city, start_date, end_date)
        try:
            records = fetch_city_weather(city, coords["lat"], coords["lon"], start_date, end_date)
            # Batch insert
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
                """), [{**rec, "ingested_at": now_iso} for rec in records])
                conn.commit()
            total_inserted += len(records)
            log.info("Loaded %d weather rows for %s", len(records), city)
        except Exception as e:
            log.error("Failed to fetch weather for %s: %s", city, e)

    log.info("Open-Meteo weather ingest complete: %d total rows", total_inserted)
    return total_inserted


if __name__ == "__main__":
    ingest_weather(start_date="2022-01-01", end_date="2022-12-31")
