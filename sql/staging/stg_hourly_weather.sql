-- Staging clean hourly weather table
-- Business question: Standardize, clean, and aggregate city-level temperature, humidity, and wind across demand centres.

DROP TABLE IF EXISTS stg_hourly_weather;

CREATE TABLE stg_hourly_weather AS
WITH cleaned_city AS (
    SELECT
        city,
        timestamp_ist,
        date(timestamp_ist) AS date_ist,
        CAST(strftime('%H', timestamp_ist) AS INTEGER) AS hour_ist,
        -- Bounds check: temperature in India between -5°C and 55°C
        CASE 
            WHEN temperature_2m BETWEEN -5 AND 55 THEN temperature_2m
            ELSE NULL 
        END AS temperature_c,
        -- Humidity between 0 and 100%
        CASE 
            WHEN relative_humidity_2m BETWEEN 0 AND 100 THEN relative_humidity_2m 
            ELSE NULL 
        END AS humidity_pct,
        -- Wind speed positive and below 150 km/h
        CASE 
            WHEN wind_speed_10m BETWEEN 0 AND 150 THEN wind_speed_10m 
            ELSE NULL 
        END AS wind_speed_kmh
    FROM raw_weather
    WHERE timestamp_ist IS NOT NULL
)
SELECT
    timestamp_ist,
    date_ist,
    hour_ist,
    -- Unweighted multi-city average temperature
    ROUND(AVG(temperature_c), 2) AS avg_temperature_c,
    ROUND(MAX(temperature_c), 2) AS max_temperature_c,
    ROUND(MIN(temperature_c), 2) AS min_temperature_c,
    ROUND(AVG(humidity_pct), 2) AS avg_humidity_pct,
    ROUND(AVG(wind_speed_kmh), 2) AS avg_wind_speed_kmh,
    -- Also individual key city temperatures for city-specific analysis
    ROUND(AVG(CASE WHEN city = 'Delhi' THEN temperature_c END), 2) AS delhi_temp_c,
    ROUND(AVG(CASE WHEN city = 'Mumbai' THEN temperature_c END), 2) AS mumbai_temp_c,
    ROUND(AVG(CASE WHEN city = 'Chennai' THEN temperature_c END), 2) AS chennai_temp_c,
    ROUND(AVG(CASE WHEN city = 'Kolkata' THEN temperature_c END), 2) AS kolkata_temp_c,
    ROUND(AVG(CASE WHEN city = 'Bengaluru' THEN temperature_c END), 2) AS bengaluru_temp_c,
    ROUND(AVG(CASE WHEN city = 'Ahmedabad' THEN temperature_c END), 2) AS ahmedabad_temp_c
FROM cleaned_city
GROUP BY timestamp_ist, date_ist, hour_ist;

CREATE INDEX IF NOT EXISTS idx_stg_weather_ts ON stg_hourly_weather(timestamp_ist);
CREATE INDEX IF NOT EXISTS idx_stg_weather_date ON stg_hourly_weather(date_ist);
