/**
 * @file api.js
 * Asynchronous HTTP client wrapper for the FastAPI operational analytics endpoints.
 */

const API_BASE = '/api';

/**
 * Serialize a parameters dictionary into a URL query string.
 * @param {Record<string, any>} params
 * @returns {string}
 */
function buildQueryString(params = {}) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== '') {
      query.set(key, String(value));
    }
  }
  const serialized = query.toString();
  return serialized ? `?${serialized}` : '';
}

/**
 * Execute HTTP GET request with error handling and JSON decoding.
 * @template T
 * @param {string} endpoint
 * @param {Record<string, any>} params
 * @returns {Promise<T>}
 */
async function apiGet(endpoint, params = {}) {
  const url = `${API_BASE}${endpoint}${buildQueryString(params)}`;
  const response = await fetch(url, {
    signal: AbortSignal.timeout(30000),
    headers: {
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    let errorDetail = `HTTP ${response.status} ${response.statusText}`;
    try {
      const errorJson = await response.json();
      if (errorJson && errorJson.detail) {
        errorDetail = errorJson.detail;
      }
    } catch (_) {

    }
    const error = new Error(errorDetail);
    error.status = response.status;
    throw error;
  }

  return response.json();
}

/**
 * Fetch top-level executive KPIs and pipeline refresh metadata.
 * @returns {Promise<any>}
 */
export async function fetchSummary() {
  return apiGet('/summary');
}

/**
 * Fetch daily average and peak power demand with 7-day rolling baseline.
 * @param {{ from?: string, to?: string, seasons?: string }} filters
 * @returns {Promise<Array<any>>}
 */
export async function fetchDailyDemand(filters = {}) {
  return apiGet('/daily-demand', filters);
}

/**
 * Fetch monthly maximum demand records and year-over-year growth metrics.
 * @param {{ from?: string, to?: string, seasons?: string }} filters
 * @returns {Promise<Array<any>>}
 */
export async function fetchMonthlyPeaks(filters = {}) {
  return apiGet('/monthly-peaks', filters);
}

/**
 * Fetch sampled temperature versus demand observations alongside 1C median bins.
 * @param {string} feature
 * @param {{ from?: string, to?: string, seasons?: string }} filters
 * @returns {Promise<any>}
 */
export async function fetchTempDemand(feature = 'avg_temperature_c', filters = {}) {
  return apiGet('/temp-demand', { feature, ...filters });
}

/**
 * Fetch average demand matrix across months and hours of the day.
 * @param {{ from?: string, to?: string, seasons?: string }} filters
 * @returns {Promise<Array<any>>}
 */
export async function fetchHeatmap(filters = {}) {
  return apiGet('/heatmap', filters);
}

/**
 * Fetch full-sample hinge regression temperature sensitivity parameters.
 * @returns {Promise<any>}
 */
export async function fetchSensitivity() {
  return apiGet('/sensitivity');
}

/**
 * Fetch diurnal net-load generation profile and dusk inflection metrics.
 * @param {string} season
 * @param {{ from?: string, to?: string }} filters
 * @returns {Promise<any>}
 */
export async function fetchDuckCurve(season = 'All', filters = {}) {
  return apiGet('/duck-curve', { season, ...filters });
}

/**
 * Fetch monthly renewable generation share and capacity contribution.
 * @param {{ from?: string, to?: string, seasons?: string }} filters
 * @returns {Promise<Array<any>>}
 */
export async function fetchReShare(filters = {}) {
  return apiGet('/re-share', filters);
}

/**
 * Fetch normalized demand deviation z-scores and segmented anomaly records.
 * @param {{ from?: string, to?: string, seasons?: string }} filters
 * @returns {Promise<any>}
 */
export async function fetchAnomalies(filters = {}) {
  return apiGet('/anomalies', filters);
}

/**
 * Fetch top 10 hourly net-load ramping events with official peak cross-check.
 * @param {{ from?: string, to?: string, seasons?: string }} filters
 * @returns {Promise<Array<any>>}
 */
export async function fetchRamps(filters = {}) {
  return apiGet('/ramps', filters);
}

/**
 * Fetch automated test status records, execution audit runs, and database volume.
 * @returns {Promise<any>}
 */
export async function fetchHealth() {
  return apiGet('/health');
}

/**
 * Generate parameterised download URL for CSV export.
 * @param {string} name
 * @param {Record<string, any>} filters
 * @returns {string}
 */
export function getExportUrl(name, filters = {}) {
  return `${API_BASE}/export/${encodeURIComponent(name)}.csv${buildQueryString(filters)}`;
}
