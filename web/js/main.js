/**
 * @file main.js
 * Application controller coordinating filter state, section rendering, theme switching, and interactive events.
 */

import * as api from './api.js';
import * as charts from './charts.js';

const state = {
  filters: {
    from: '',
    to: '',
    seasons: [],
    duckSeason: 'Summer',
    tempFeature: 'avg_temperature_c',
  },
  summary: null,
  summaryBounds: {
    minDate: '2021-05-07',
    maxDate: '2026-10-24',
  },
  rampsData: [],
  rampsSort: { col: 'abs_ramp_1h_mw', asc: false },
};

/**
 * Initialize theme state based on stored preference or operating system defaults.
 */
function initTheme() {
  const storedTheme = localStorage.getItem('theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const theme = storedTheme || (prefersDark ? 'dark' : 'light');

  applyTheme(theme);

  const toggleBtn = document.getElementById('theme-toggle-btn');
  if (toggleBtn) {
    toggleBtn.addEventListener('click', () => {
      const current = document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
      const next = current === 'dark' ? 'light' : 'dark';
      applyTheme(next);
      localStorage.setItem('theme', next);
    });
  }

  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    if (!localStorage.getItem('theme')) {
      applyTheme(e.matches ? 'dark' : 'light');
    }
  });
}

/**
 * Apply theme attribute to document and trigger chart color restyling.
 * @param {'light'|'dark'} theme
 */
function applyTheme(theme) {
  if (theme === 'dark') {
    document.documentElement.setAttribute('data-theme', 'dark');
  } else {
    document.documentElement.removeAttribute('data-theme');
  }
  setTimeout(() => {
    refreshAllCharts();
  }, 50);
}

/**
 * Smoothly animate numerical counter values.
 * @param {HTMLElement} el
 * @param {number} target
 * @param {string} suffix
 * @param {number} decimals
 */
function animateValue(el, target, suffix = '', decimals = 0) {
  if (!el || target === null || target === undefined || isNaN(target)) return;

  const duration = 1000;
  const startTime = performance.now();
  const startVal = 0;

  function update(currentTime) {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const easeOutQuad = 1 - (1 - progress) * (1 - progress);
    const current = startVal + (target - startVal) * easeOutQuad;

    const formatted = decimals > 0 ? current.toFixed(decimals) : Math.round(current).toLocaleString();
    el.textContent = `${formatted}${suffix}`;

    if (progress < 1) {
      requestAnimationFrame(update);
    } else {
      const finalFormatted = decimals > 0 ? target.toFixed(decimals) : Math.round(target).toLocaleString();
      el.textContent = `${finalFormatted}${suffix}`;
    }
  }

  requestAnimationFrame(update);
}

/**
 * Render executive summary KPI cards.
 * @param {any} s
 */
function renderSummaryKPIs(s) {
  const peakValEl = document.getElementById('kpi-peak-val');
  const peakDateEl = document.getElementById('kpi-peak-date');
  const latestPeakValEl = document.getElementById('kpi-latest-peak-val');
  const latestPeakDateEl = document.getElementById('kpi-latest-peak-date');
  const reShareValEl = document.getElementById('kpi-re-share-val');
  const reShareSubEl = document.getElementById('kpi-re-share-sub');
  const recordsValEl = document.getElementById('kpi-records-val');
  const recordsSubEl = document.getElementById('kpi-records-sub');
  const healthBadgeEl = document.getElementById('kpi-health-badge');

  if (peakValEl) animateValue(peakValEl, s.record_peak_mw);
  if (peakDateEl) peakDateEl.textContent = s.record_peak_date ? `Set on ${s.record_peak_date}` : 'Grid-India record';

  if (latestPeakValEl) animateValue(latestPeakValEl, s.latest_psp_peak_mw);
  if (latestPeakDateEl) latestPeakDateEl.textContent = s.latest_psp_date ? `Reported ${s.latest_psp_date}` : 'Latest daily PSP';

  if (reShareValEl) animateValue(reShareValEl, s.latest_re_share_pct, '%', 1);
  if (reShareSubEl) reShareSubEl.textContent = `Avg ${s.avg_re_share_pct || 15.0}% across window`;

  if (recordsValEl) animateValue(recordsValEl, s.total_hourly_records);
  if (recordsSubEl) recordsSubEl.textContent = `${s.total_report_count} daily PSP reports loaded`;

  if (healthBadgeEl && s.last_pipeline_run) {
    healthBadgeEl.textContent = `${s.last_pipeline_run.stage.toUpperCase()}: ${s.last_pipeline_run.status.toUpperCase()}`;
    healthBadgeEl.className = s.last_pipeline_run.status === 'ok' ? 'badge badge-pass' : 'badge badge-fail';
  }
}

/**
 * Populate static and dynamic sensitivity analysis values and candidate threshold table.
 */
async function loadSensitivitySection() {
  try {
    const data = await api.fetchSensitivity();
    const slopeValEl = document.getElementById('sens-slope-val');
    const slopeCiEl = document.getElementById('sens-ci-val');
    const r2FullEl = document.getElementById('sens-r2-full');
    const r2CtrlEl = document.getElementById('sens-r2-ctrl');
    const deltaR2El = document.getElementById('sens-delta-r2');
    const nDaysEl = document.getElementById('sens-ndays');

    if (slopeValEl) slopeValEl.textContent = `+${Number(data.slope_mw_per_c).toLocaleString()} MW/°C`;
    if (slopeCiEl) slopeCiEl.textContent = `95% CI: [${Number(data.ci_lower).toLocaleString()}, ${Number(data.ci_upper).toLocaleString()}] (HC1 SE: ${data.se_hc1})`;
    if (r2FullEl) r2FullEl.textContent = `${(data.r2_full * 100).toFixed(1)}% (R²=${data.r2_full.toFixed(4)})`;
    if (r2CtrlEl) r2CtrlEl.textContent = `${(data.r2_ctrl * 100).toFixed(1)}% (R²=${data.r2_ctrl.toFixed(4)})`;
    if (deltaR2El) deltaR2El.textContent = `+${(data.delta_r2 * 100).toFixed(1)}% (+${data.delta_r2.toFixed(4)})`;
    if (nDaysEl) nDaysEl.textContent = `${data.n_days} days ≥ 25°C out of ${data.n_total} total`;

    const tbody = document.getElementById('threshold-table-body');
    if (tbody && data.thresholds) {
      tbody.innerHTML = '';
      for (const t of data.thresholds) {
        const isSelected = t.threshold_c === 25.0;
        const tr = document.createElement('tr');
        if (isSelected) {
          tr.style.fontWeight = '700';
          tr.style.backgroundColor = 'var(--accent-saffron-subtle)';
        }
        tr.innerHTML = `
          <td>${t.threshold_c.toFixed(1)}°C ${isSelected ? '<span class="badge badge-pass">Base</span>' : ''}</td>
          <td class="num">${t.n_days_above}</td>
          <td class="num">${t.n_obs}</td>
          <td class="num">+${Number(t.slope_mw_per_c).toLocaleString()}</td>
          <td class="num">${t.se_hc1.toFixed(1)}</td>
          <td class="num">[${Number(t.ci_lower).toLocaleString()}, ${Number(t.ci_upper).toLocaleString()}]</td>
          <td class="num">${t.r2_ctrl.toFixed(4)}</td>
          <td class="num">${t.r2_full.toFixed(4)}</td>
          <td class="num">+${t.delta_r2.toFixed(4)}</td>
          <td class="num">${Number(t.aic).toLocaleString()}</td>
        `;
        tbody.appendChild(tr);
      }
    }
  } catch (err) {
    console.error('Failed to load sensitivity parameters:', err);
  }
}

/**
 * Fetch and populate pipeline reliability health check records, audit runs, and table counts.
 */
async function loadHealthSection() {
  try {
    const health = await api.fetchHealth();

    const checksBody = document.getElementById('dq-checks-body');
    if (checksBody && health.checks) {
      checksBody.innerHTML = '';
      for (const c of health.checks) {
        const tr = document.createElement('tr');
        const badgeClass = c.status === 'PASS' ? 'badge badge-pass' : 'badge badge-fail';
        tr.innerHTML = `
          <td><code>${c.check_name}</code></td>
          <td><code>${c.table_name || 'staging'}</code></td>
          <td><span class="${badgeClass}">${c.status}</span></td>
          <td>${c.details || ''}</td>
        `;
        checksBody.appendChild(tr);
      }
    }

    const runsBody = document.getElementById('pipeline-runs-body');
    if (runsBody && health.runs) {
      runsBody.innerHTML = '';
      for (const r of health.runs) {
        const tr = document.createElement('tr');
        const badgeClass = r.status === 'ok' ? 'badge badge-pass' : 'badge badge-fail';
        tr.innerHTML = `
          <td>${r.run_at ? r.run_at.substring(0, 19).replace('T', ' ') : ''}</td>
          <td><code>${r.stage}</code></td>
          <td><code>${r.source}</code></td>
          <td><span class="${badgeClass}">${r.status}</span></td>
          <td class="num">${r.rows_inserted !== null ? Number(r.rows_inserted).toLocaleString() : '-'}</td>
          <td class="num">${r.duration_s !== null ? r.duration_s.toFixed(2) + 's' : '-'}</td>
          <td>${r.message || ''}</td>
        `;
        runsBody.appendChild(tr);
      }
    }

    const tableCountsEl = document.getElementById('table-counts-pills');
    if (tableCountsEl && health.table_counts) {
      tableCountsEl.innerHTML = '';
      for (const [tbl, count] of Object.entries(health.table_counts)) {
        const pill = document.createElement('div');
        pill.className = 'stat-pill';
        pill.innerHTML = `
          <span class="stat-pill-label">${tbl}</span>
          <span class="stat-pill-val">${Number(count).toLocaleString()}</span>
        `;
        tableCountsEl.appendChild(pill);
      }
    }
  } catch (err) {
    console.error('Failed to load health metrics:', err);
  }
}

/**
 * Re-render the ramps table using current sort state.
 */
function renderRampsTable() {
  const tbody = document.getElementById('ramps-table-body');
  if (!tbody) return;

  const { col, asc } = state.rampsSort;
  const sorted = [...state.rampsData].sort((a, b) => {
    let va = a[col];
    let vb = b[col];
    if (va === null || va === undefined) return 1;
    if (vb === null || vb === undefined) return -1;
    if (typeof va === 'string') {
      return asc ? va.localeCompare(vb) : vb.localeCompare(va);
    }
    return asc ? va - vb : vb - va;
  });

  tbody.innerHTML = '';
  if (!sorted.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="empty-state">No net-load ramps match the selected criteria.</td></tr>';
    return;
  }

  for (const r of sorted) {
    const tr = document.createElement('tr');
    const sign = r.ramp_1h_mw > 0 ? '+' : '';
    const peakVal = r.grid_india_peak_mw !== null ? Number(r.grid_india_peak_mw).toLocaleString() : 'Unarchived';
    tr.innerHTML = `
      <td><code>${r.timestamp_ist}</code></td>
      <td class="num">${Number(r.demand_mw).toLocaleString()}</td>
      <td class="num">${Number(r.solar_mw).toLocaleString()}</td>
      <td class="num">${Number(r.wind_mw).toLocaleString()}</td>
      <td class="num">${Number(r.net_load_mw).toLocaleString()}</td>
      <td class="num" style="font-weight:700">${sign}${Number(r.ramp_1h_mw).toLocaleString()}</td>
      <td class="num">${peakVal}</td>
    `;
    tbody.appendChild(tr);
  }
}

/**
 * Load all operational analytics sections and update charts according to current filter state.
 */
async function loadAnalyticsSections() {
  const queryFilters = {};
  if (state.filters.from) queryFilters.from = state.filters.from;
  if (state.filters.to) queryFilters.to = state.filters.to;
  if (state.filters.seasons.length > 0) {
    queryFilters.seasons = state.filters.seasons.join(',');
  }

  updateExportLinks(queryFilters);
  updateActiveFilterIndicator();

  try {
    const dailyData = await api.fetchDailyDemand(queryFilters);
    charts.renderDailyDemandChart('chart-daily-demand', dailyData);
  } catch (err) {
    console.error('Daily demand fetch failed:', err);
  }

  try {
    const peaksData = await api.fetchMonthlyPeaks(queryFilters);
    charts.renderMonthlyPeaksChart('chart-monthly-peaks', peaksData);
  } catch (err) {
    console.error('Monthly peaks fetch failed:', err);
  }

  try {
    const tempDemandData = await api.fetchTempDemand(state.filters.tempFeature, queryFilters);
    charts.renderTempDemandChart(
      'chart-temp-demand',
      tempDemandData.points || [],
      tempDemandData.median_bins || [],
      state.filters.tempFeature
    );
  } catch (err) {
    console.error('Temperature vs demand fetch failed:', err);
  }

  try {
    const heatmapData = await api.fetchHeatmap(queryFilters);
    charts.renderHeatmapChart('chart-heatmap', heatmapData);
  } catch (err) {
    console.error('Heatmap fetch failed:', err);
  }

  try {
    const duckData = await api.fetchDuckCurve(state.filters.duckSeason, {
      from: queryFilters.from,
      to: queryFilters.to,
    });
    charts.renderDuckCurveChart('chart-duck-curve', duckData);

    const solarPeakEl = document.getElementById('duck-solar-peak');
    const netTroughEl = document.getElementById('duck-net-trough');
    const evePeakEl = document.getElementById('duck-eve-peak');
    const rampEl = document.getElementById('duck-ramp-req');

    if (solarPeakEl) solarPeakEl.textContent = duckData.solar_peak_mw !== null ? `${Number(duckData.solar_peak_mw).toLocaleString()} MW (@ ${duckData.solar_peak_hour}:00)` : '-';
    if (netTroughEl) netTroughEl.textContent = duckData.net_load_trough_mw !== null ? `${Number(duckData.net_load_trough_mw).toLocaleString()} MW (@ ${duckData.net_load_trough_hour}:00)` : '-';
    if (evePeakEl) evePeakEl.textContent = duckData.evening_peak_mw !== null ? `${Number(duckData.evening_peak_mw).toLocaleString()} MW (@ ${duckData.evening_peak_hour}:00)` : '-';
    if (rampEl) rampEl.textContent = duckData.trough_to_peak_ramp_mw !== null ? `+${Number(duckData.trough_to_peak_ramp_mw).toLocaleString()} MW` : '-';
  } catch (err) {
    console.error('Duck curve fetch failed:', err);
  }

  try {
    const reShareData = await api.fetchReShare(queryFilters);
    charts.renderReShareChart('chart-re-share', reShareData);
  } catch (err) {
    console.error('Renewable share fetch failed:', err);
  }

  try {
    const anomalyRes = await api.fetchAnomalies(queryFilters);
    charts.renderAnomaliesChart('chart-anomalies', anomalyRes.data || []);

    const totalAnoEl = document.getElementById('ano-total-count');
    const realAnoEl = document.getElementById('ano-real-count');
    const dqAnoEl = document.getElementById('ano-dq-count');
    if (totalAnoEl) totalAnoEl.textContent = anomalyRes.anomalies_count || 0;
    if (realAnoEl) realAnoEl.textContent = anomalyRes.real_count || 0;
    if (dqAnoEl) dqAnoEl.textContent = anomalyRes.dq_count || 0;
  } catch (err) {
    console.error('Anomalies fetch failed:', err);
  }

  try {
    const rampsData = await api.fetchRamps(queryFilters);
    state.rampsData = rampsData;
    renderRampsTable();
  } catch (err) {
    console.error('Ramps fetch failed:', err);
  }
}

/**
 * Re-render all charts with newly computed theme tokens.
 */
function refreshAllCharts() {
  loadAnalyticsSections();
}

/**
 * Synchronize CSV export download URLs with current filter state.
 * @param {Record<string, string>} queryFilters
 */
function updateExportLinks(queryFilters) {
  const exportDailyBtn = document.getElementById('export-daily-btn');
  const exportRampsBtn = document.getElementById('export-ramps-btn');
  const exportAnomaliesBtn = document.getElementById('export-anomalies-btn');

  if (exportDailyBtn) exportDailyBtn.href = api.getExportUrl('daily-demand', queryFilters);
  if (exportRampsBtn) exportRampsBtn.href = api.getExportUrl('ramps', queryFilters);
  if (exportAnomaliesBtn) exportAnomaliesBtn.href = api.getExportUrl('anomalies', queryFilters);
}

/**
 * Update UI indicator dot reflecting active filter modifications.
 */
function updateActiveFilterIndicator() {
  const dot = document.getElementById('filter-active-dot');
  const text = document.getElementById('filter-active-text');
  const hasFilter = Boolean(state.filters.from || state.filters.to || state.filters.seasons.length > 0);

  if (dot) {
    dot.className = hasFilter ? 'indicator-dot active-filter' : 'indicator-dot';
  }
  if (text) {
    if (hasFilter) {
      const parts = [];
      if (state.filters.from || state.filters.to) {
        parts.push(`${state.filters.from || 'start'} → ${state.filters.to || 'latest'}`);
      }
      if (state.filters.seasons.length > 0) {
        parts.push(state.filters.seasons.join(', '));
      }
      text.textContent = `Filtered: ${parts.join(' | ')}`;
    } else {
      text.textContent = 'Full telemetry horizon';
    }
  }
}

/**
 * Set up user interactive controls including date pickers, season chips, and table sorting.
 */
function setupEventHandlers() {
  const fromInput = document.getElementById('filter-date-from');
  const toInput = document.getElementById('filter-date-to');

  if (fromInput) {
    fromInput.addEventListener('change', () => {
      state.filters.from = fromInput.value;
      clearQuickDateActive();
      loadAnalyticsSections();
    });
  }

  if (toInput) {
    toInput.addEventListener('change', () => {
      state.filters.to = toInput.value;
      clearQuickDateActive();
      loadAnalyticsSections();
    });
  }

  const quickBtns = document.querySelectorAll('.quick-btn');
  for (const btn of quickBtns) {
    btn.addEventListener('click', () => {
      const span = btn.getAttribute('data-span');
      for (const b of quickBtns) b.classList.remove('active');
      btn.classList.add('active');

      if (span === 'all') {
        state.filters.from = '';
        state.filters.to = '';
        if (fromInput) fromInput.value = '';
        if (toInput) toInput.value = '';
      } else {
        const maxD = new Date(state.summaryBounds.maxDate || '2026-10-24');
        const minD = new Date(maxD);
        if (span === '1y') minD.setFullYear(minD.getFullYear() - 1);
        if (span === '2y') minD.setFullYear(minD.getFullYear() - 2);

        const fromStr = minD.toISOString().substring(0, 10);
        const toStr = maxD.toISOString().substring(0, 10);
        state.filters.from = fromStr;
        state.filters.to = toStr;
        if (fromInput) fromInput.value = fromStr;
        if (toInput) toInput.value = toStr;
      }

      loadAnalyticsSections();
    });
  }

  function clearQuickDateActive() {
    for (const b of quickBtns) b.classList.remove('active');
  }

  const seasonChips = document.querySelectorAll('.season-chip');
  for (const chip of seasonChips) {
    chip.addEventListener('click', () => {
      const val = chip.getAttribute('data-season');
      if (val === 'All') {
        state.filters.seasons = [];
        for (const c of seasonChips) c.classList.remove('active');
        chip.classList.add('active');
      } else {
        const allChip = document.querySelector('.season-chip[data-season="All"]');
        if (allChip) allChip.classList.remove('active');

        chip.classList.toggle('active');
        const activeChips = Array.from(document.querySelectorAll('.season-chip.active'))
          .map((c) => c.getAttribute('data-season'))
          .filter((s) => s !== 'All');

        if (activeChips.length === 0) {
          if (allChip) allChip.classList.add('active');
          state.filters.seasons = [];
        } else {
          state.filters.seasons = activeChips;
        }
      }
      loadAnalyticsSections();
    });
  }

  const resetBtn = document.getElementById('filter-reset-btn');
  if (resetBtn) {
    resetBtn.addEventListener('click', () => {
      state.filters.from = '';
      state.filters.to = '';
      state.filters.seasons = [];
      if (fromInput) fromInput.value = '';
      if (toInput) toInput.value = '';
      clearQuickDateActive();
      const allQuick = document.querySelector('.quick-btn[data-span="all"]');
      if (allQuick) allQuick.classList.add('active');

      for (const c of seasonChips) c.classList.remove('active');
      const allChip = document.querySelector('.season-chip[data-season="All"]');
      if (allChip) allChip.classList.add('active');

      loadAnalyticsSections();
    });
  }

  const tempSelect = document.getElementById('temp-feature-select');
  if (tempSelect) {
    tempSelect.addEventListener('change', () => {
      state.filters.tempFeature = tempSelect.value;
      loadAnalyticsSections();
    });
  }

  const duckSeasonSelect = document.getElementById('duck-season-select');
  if (duckSeasonSelect) {
    duckSeasonSelect.addEventListener('change', () => {
      state.filters.duckSeason = duckSeasonSelect.value;
      loadAnalyticsSections();
    });
  }

  const rampHeaders = document.querySelectorAll('#ramps-table th[data-col]');
  for (const th of rampHeaders) {
    th.addEventListener('click', () => {
      const col = th.getAttribute('data-col');
      if (state.rampsSort.col === col) {
        state.rampsSort.asc = !state.rampsSort.asc;
      } else {
        state.rampsSort.col = col;
        state.rampsSort.asc = false;
      }
      for (const h of rampHeaders) {
        h.classList.remove('sorted-asc', 'sorted-desc');
      }
      th.classList.add(state.rampsSort.asc ? 'sorted-asc' : 'sorted-desc');
      renderRampsTable();
    });
  }

  const navLinks = document.querySelectorAll('.nav-link');
  const sections = document.querySelectorAll('.section');
  const observerOptions = {
    root: null,
    rootMargin: '-20% 0px -70% 0px',
    threshold: 0,
  };

  const observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (entry.isIntersecting) {
        const id = entry.target.getAttribute('id');
        for (const link of navLinks) {
          if (link.getAttribute('href') === `#${id}`) {
            link.classList.add('active');
          } else {
            link.classList.remove('active');
          }
        }
      }
    }
  }, observerOptions);

  for (const sec of sections) {
    observer.observe(sec);
  }

  const mobileToggle = document.getElementById('mobile-menu-toggle');
  const navList = document.querySelector('.nav-links');
  if (mobileToggle && navList) {
    mobileToggle.addEventListener('click', () => {
      navList.classList.toggle('open');
      const expanded = navList.classList.contains('open');
      mobileToggle.setAttribute('aria-expanded', String(expanded));
    });

    for (const link of navLinks) {
      link.addEventListener('click', () => {
        navList.classList.remove('open');
        if (mobileToggle) mobileToggle.setAttribute('aria-expanded', 'false');
      });
    }
  }
}

/**
 * Application boot sequence.
 */
async function init() {
  initTheme();
  setupEventHandlers();

  try {
    const summary = await api.fetchSummary();
    state.summary = summary;
    if (summary.latest_psp_date) {
      state.summaryBounds.maxDate = summary.latest_psp_date;
    }
    renderSummaryKPIs(summary);
  } catch (err) {
    console.error('Summary fetch failed:', err);
  }

  await Promise.all([
    loadSensitivitySection(),
    loadHealthSection(),
    loadAnalyticsSections(),
  ]);
}

window.addEventListener('DOMContentLoaded', init);
