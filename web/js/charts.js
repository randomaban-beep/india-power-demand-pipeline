/**
 * @file charts.js
 * ECharts visualisations for India power analytics, reading design tokens dynamically from CSS variables.
 */

const chartInstances = new Map();

/**
 * Retrieve current computed color token values from CSS root.
 * @returns {Record<string, string>}
 */
export function getThemeTokens() {
  const styles = getComputedStyle(document.documentElement);
  return {
    textPrimary: styles.getPropertyValue('--text-primary').trim() || '#0F1B2D',
    textSecondary: styles.getPropertyValue('--text-secondary').trim() || '#475569',
    textMuted: styles.getPropertyValue('--text-muted').trim() || '#64748B',
    borderColor: styles.getPropertyValue('--border-color').trim() || '#E2E8F0',
    chartGrid: styles.getPropertyValue('--chart-grid').trim() || 'rgba(15, 27, 45, 0.08)',
    chartAxis: styles.getPropertyValue('--chart-axis').trim() || 'rgba(15, 27, 45, 0.45)',
    tooltipBg: styles.getPropertyValue('--chart-tooltip-bg').trim() || '#FFFFFF',
    tooltipBorder: styles.getPropertyValue('--chart-tooltip-border').trim() || '#E2E8F0',
    tooltipText: styles.getPropertyValue('--chart-tooltip-text').trim() || '#0F1B2D',
    accentSaffron: styles.getPropertyValue('--accent-saffron').trim() || '#F59F00',
    accentBlue: styles.getPropertyValue('--accent-blue').trim() || '#2B6CB0',
    accentTeal: styles.getPropertyValue('--accent-teal').trim() || '#009E73',
    accentCoral: styles.getPropertyValue('--accent-coral').trim() || '#D55E00',
    accentPurple: styles.getPropertyValue('--accent-purple').trim() || '#795290',
    bgSurface: styles.getPropertyValue('--bg-surface').trim() || '#FFFFFF',
  };
}

/**
 * Initialize or retrieve an existing ECharts instance attached to a DOM container.
 * @param {string} containerId
 * @returns {any}
 */
function getOrCreateChart(containerId) {
  const el = document.getElementById(containerId);
  if (!el) return null;

  let chart = chartInstances.get(containerId);
  if (!chart || chart.isDisposed()) {
    chart = window.echarts.init(el, null, { renderer: 'canvas' });
    chartInstances.set(containerId, chart);

    const resizeObserver = new ResizeObserver(() => {
      chart.resize();
    });
    resizeObserver.observe(el);
  }
  return chart;
}

/**
 * Resize all active chart instances.
 */
export function resizeAllCharts() {
  for (const chart of chartInstances.values()) {
    if (chart && !chart.isDisposed()) {
      chart.resize();
    }
  }
}

/**
 * Common tooltip styling configuration across all charts.
 * @param {Record<string, string>} tokens
 * @returns {object}
 */
function baseTooltip(tokens) {
  return {
    trigger: 'axis',
    backgroundColor: tokens.tooltipBg,
    borderColor: tokens.tooltipBorder,
    borderWidth: 1,
    textStyle: {
      color: tokens.tooltipText,
      fontFamily: 'Inter, sans-serif',
      fontSize: 12,
    },
    extraCssText: 'box-shadow: 0 4px 12px rgba(0,0,0,0.15); border-radius: 8px;',
  };
}

/**
 * Display an informative message when a filtered slice contains no observations.
 * @param {any} chart
 * @param {Record<string, string>} tokens
 * @param {string} title
 */
function renderEmptyState(chart, tokens, title = 'No data available for the selected filter range') {
  chart.setOption({
    title: {
      text: title,
      subtext: 'Try selecting a broader date window or clicking "All" in the filter bar above',
      left: 'center',
      top: 'middle',
      textStyle: { color: tokens.textSecondary, fontSize: 13, fontWeight: 500 },
      subtextStyle: { color: tokens.textMuted, fontSize: 11 },
    },
    legend: { show: false },
    xAxis: { show: false },
    yAxis: { show: false },
    series: [],
  }, true);
}

/**
 * Render daily demand time series with peak and rolling baseline.
 * @param {string} containerId
 * @param {Array<{ date: string, avg_mw: number, peak_mw: number, rolling_avg_mw: number }>} data
 */
export function renderDailyDemandChart(containerId, data) {
  const chart = getOrCreateChart(containerId);
  if (!chart) return;

  const tokens = getThemeTokens();
  if (!data || data.length === 0) {
    renderEmptyState(chart, tokens);
    return;
  }

  const dates = data.map((d) => d.date);
  const avgVals = data.map((d) => d.avg_mw);
  const peakVals = data.map((d) => d.peak_mw);
  const rollingVals = data.map((d) => d.rolling_avg_mw);

  const option = {
    title: { show: false },
    tooltip: baseTooltip(tokens),
    legend: {
      data: ['Daily Peak Met', 'Daily Average', '7-Day Rolling Baseline'],
      textStyle: { color: tokens.textSecondary, fontSize: 12 },
      top: 4,
      left: 'center',
      type: 'scroll',
    },
    grid: {
      top: 68,
      left: 68,
      right: 28,
      bottom: 42,
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: dates,
      boundaryGap: false,
      axisLine: { lineStyle: { color: tokens.chartAxis } },
      axisLabel: {
        color: tokens.textMuted,
        fontFamily: 'SFMono-Regular, monospace',
        fontSize: 11,
      },
    },
    yAxis: {
      type: 'value',
      name: 'Power (MW)',
      nameTextStyle: { color: tokens.textMuted, fontSize: 11, align: 'left', padding: [0, 0, 6, 0] },
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: tokens.chartGrid } },
      axisLabel: {
        color: tokens.textMuted,
        fontFamily: 'SFMono-Regular, monospace',
        formatter: (v) => `${(v / 1000).toFixed(0)}k`,
      },
    },
    series: [
      {
        name: 'Daily Peak Met',
        type: 'line',
        data: peakVals,
        showSymbol: false,
        lineStyle: { width: 1.5, color: tokens.accentSaffron },
        itemStyle: { color: tokens.accentSaffron },
      },
      {
        name: 'Daily Average',
        type: 'line',
        data: avgVals,
        showSymbol: false,
        lineStyle: { width: 1.5, color: tokens.accentBlue },
        itemStyle: { color: tokens.accentBlue },
      },
      {
        name: '7-Day Rolling Baseline',
        type: 'line',
        data: rollingVals,
        showSymbol: false,
        lineStyle: { width: 2, color: tokens.accentTeal, type: 'dashed' },
        itemStyle: { color: tokens.accentTeal },
      },
    ],
  };

  chart.setOption(option, true);
}

/**
 * Render monthly peak demand bar chart with year-over-year escalation line.
 * @param {string} containerId
 * @param {Array<{ year_month: string, peak_demand_mw: number, yoy_peak_growth_pct: number }>} data
 */
export function renderMonthlyPeaksChart(containerId, data) {
  const chart = getOrCreateChart(containerId);
  if (!chart) return;

  const tokens = getThemeTokens();
  if (!data || data.length === 0) {
    renderEmptyState(chart, tokens);
    return;
  }

  const months = data.map((d) => d.year_month);
  const peakVals = data.map((d) => d.peak_demand_mw);
  const yoyVals = data.map((d) => d.yoy_peak_growth_pct);

  const option = {
    title: { show: false },
    tooltip: {
      ...baseTooltip(tokens),
      formatter: (params) => {
        let res = `<div style="font-weight:600;margin-bottom:4px">${params[0].axisValue}</div>`;
        for (const p of params) {
          const val = p.seriesName.includes('Growth')
            ? `${p.value !== null && p.value !== undefined ? Number(p.value).toFixed(1) : 'N/A'}%`
            : `${Number(p.value).toLocaleString()} MW`;
          res += `<div style="display:flex;justify-content:space-between;gap:12px">
            <span>${p.marker} ${p.seriesName}:</span>
            <span style="font-family:monospace;font-weight:700">${val}</span>
          </div>`;
        }
        return res;
      },
    },
    legend: {
      data: ['Monthly Peak Demand', 'YoY Growth Rate'],
      textStyle: { color: tokens.textSecondary, fontSize: 12 },
      top: 4,
      left: 'center',
      type: 'scroll',
    },
    grid: {
      top: 68,
      left: 68,
      right: 68,
      bottom: 45,
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: months,
      axisLine: { lineStyle: { color: tokens.chartAxis } },
      axisLabel: {
        color: tokens.textMuted,
        fontFamily: 'SFMono-Regular, monospace',
        fontSize: 10,
        rotate: 45,
      },
    },
    yAxis: [
      {
        type: 'value',
        name: 'Peak Demand (MW)',
        nameTextStyle: { color: tokens.textMuted, fontSize: 11, align: 'left', padding: [0, 0, 6, 0] },
        splitLine: { lineStyle: { color: tokens.chartGrid } },
        axisLabel: {
          color: tokens.textMuted,
          fontFamily: 'SFMono-Regular, monospace',
          formatter: (v) => `${(v / 1000).toFixed(0)}k`,
        },
      },
      {
        type: 'value',
        name: 'YoY Growth (%)',
        nameTextStyle: { color: tokens.textMuted, fontSize: 11, align: 'right', padding: [0, 0, 6, 0] },
        splitLine: { show: false },
        axisLabel: {
          color: tokens.textMuted,
          fontFamily: 'SFMono-Regular, monospace',
          formatter: '{value}%',
        },
      },
    ],
    series: [
      {
        name: 'Monthly Peak Demand',
        type: 'bar',
        data: peakVals,
        itemStyle: {
          color: new window.echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: tokens.accentBlue },
            { offset: 1, color: 'rgba(43, 108, 176, 0.35)' },
          ]),
          borderRadius: [4, 4, 0, 0],
        },
      },
      {
        name: 'YoY Growth Rate',
        type: 'line',
        yAxisIndex: 1,
        data: yoyVals,
        showSymbol: true,
        symbolSize: 6,
        lineStyle: { width: 2, color: tokens.accentSaffron },
        itemStyle: { color: tokens.accentSaffron },
      },
    ],
  };

  chart.setOption(option, true);
}

/**
 * Render temperature versus power demand scatter plot alongside 1°C binned median trend.
 * @param {string} containerId
 * @param {any} arg1
 * @param {any} [arg2]
 * @param {string} [arg3]
 */
export function renderTempDemandChart(containerId, arg1, arg2, arg3) {
  const chart = getOrCreateChart(containerId);
  if (!chart) return;

  const tokens = getThemeTokens();

  let rawPoints = [];
  let rawBins = [];
  let feature = 'avg_temperature_c';

  if (Array.isArray(arg1)) {
    rawPoints = arg1;
    rawBins = Array.isArray(arg2) ? arg2 : [];
    if (typeof arg3 === 'string') feature = arg3;
  } else if (arg1 && typeof arg1 === 'object') {
    rawPoints = arg1.points || [];
    rawBins = arg1.median_bins || arg1.bins || [];
    if (typeof arg2 === 'string') feature = arg2;
  }

  if (!rawPoints || rawPoints.length === 0) {
    renderEmptyState(chart, tokens);
    return;
  }

  const scatterData = rawPoints.map((p) => {
    if (Array.isArray(p)) return p;
    return [p.temp_c !== undefined ? p.temp_c : p.temperature_c, p.demand_mw];
  });

  const binCurveData = rawBins.map((b) => {
    if (Array.isArray(b)) return b;
    const temp = b.temp_bin_c !== undefined ? b.temp_bin_c : b.temp_bin;
    return [temp, b.median_demand_mw];
  });

  const option = {
    title: { show: false },
    tooltip: {
      ...baseTooltip(tokens),
      trigger: 'item',
      formatter: (params) => {
        if (params.seriesName === '1°C Median Demand') {
          return `<strong>1°C Bin: ${params.value[0]}°C</strong><br/>Median Demand: ${Number(params.value[1]).toLocaleString()} MW`;
        }
        return `Temp: ${params.value[0]}°C<br/>Demand: ${Number(params.value[1]).toLocaleString()} MW`;
      },
    },
    legend: {
      data: ['Hourly Telemetry', '1°C Median Demand'],
      textStyle: { color: tokens.textSecondary, fontSize: 12 },
      top: 4,
      left: 'center',
      type: 'scroll',
    },
    grid: {
      top: 68,
      left: 68,
      right: 28,
      bottom: 45,
      containLabel: true,
    },
    xAxis: {
      type: 'value',
      name: 'Temperature (°C)',
      nameLocation: 'middle',
      nameGap: 30,
      nameTextStyle: { color: tokens.textMuted, fontSize: 11 },
      splitLine: { lineStyle: { color: tokens.chartGrid } },
      axisLabel: {
        color: tokens.textMuted,
        fontFamily: 'SFMono-Regular, monospace',
        formatter: '{value}°C',
      },
    },
    yAxis: {
      type: 'value',
      name: 'Demand (MW)',
      nameTextStyle: { color: tokens.textMuted, fontSize: 11, align: 'left', padding: [0, 0, 6, 0] },
      splitLine: { lineStyle: { color: tokens.chartGrid } },
      axisLabel: {
        color: tokens.textMuted,
        fontFamily: 'SFMono-Regular, monospace',
        formatter: (v) => `${(v / 1000).toFixed(0)}k`,
      },
    },
    series: [
      {
        name: 'Hourly Telemetry',
        type: 'scatter',
        symbolSize: 4,
        data: scatterData,
        itemStyle: {
          color: 'rgba(43, 108, 176, 0.28)',
        },
      },
      {
        name: '1°C Median Demand',
        type: 'line',
        data: binCurveData,
        showSymbol: true,
        symbolSize: 6,
        lineStyle: { width: 3, color: tokens.accentCoral },
        itemStyle: { color: tokens.accentCoral },
        z: 10,
      },
    ],
  };

  chart.setOption(option, true);
}

/**
 * Render 12x24 seasonal heatmap of power demand by month and hour of day.
 * @param {string} containerId
 * @param {any} data
 */
export function renderDemandHeatmap(containerId, data) {
  const chart = getOrCreateChart(containerId);
  if (!chart) return;

  const tokens = getThemeTokens();
  const hours = Array.from({ length: 24 }, (_, i) => `${i}:00`);
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

  let matrixData = [];
  let minD = Infinity;
  let maxD = -Infinity;

  if (Array.isArray(data)) {
    for (const item of data) {
      const h = item.hour;
      const m = (item.month || 1) - 1;
      const val = Math.round(item.avg_demand_mw || 0);
      matrixData.push([h, m, val]);
      if (val < minD) minD = val;
      if (val > maxD) maxD = val;
    }
  } else if (data && Array.isArray(data.matrix)) {
    matrixData = data.matrix;
    minD = data.min_demand_mw || 100000;
    maxD = data.max_demand_mw || 250000;
  }

  if (matrixData.length === 0) {
    renderEmptyState(chart, tokens);
    return;
  }

  if (minD === Infinity) minD = 100000;
  if (maxD === -Infinity) maxD = 250000;

  const option = {
    title: { show: false },
    tooltip: {
      ...baseTooltip(tokens),
      position: 'top',
      formatter: (params) => {
        const h = hours[params.value[0]];
        const m = months[params.value[1]];
        const val = Number(params.value[2]).toLocaleString();
        return `<strong>${m} at ${h}</strong><br/>Avg Demand: ${val} MW`;
      },
    },
    grid: {
      top: 36,
      left: 65,
      right: 75,
      bottom: 35,
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: hours,
      splitArea: { show: true },
      axisLine: { lineStyle: { color: tokens.chartAxis } },
      axisLabel: {
        color: tokens.textMuted,
        fontFamily: 'SFMono-Regular, monospace',
        fontSize: 10,
        interval: 1,
      },
    },
    yAxis: {
      type: 'category',
      data: months,
      splitArea: { show: true },
      axisLine: { lineStyle: { color: tokens.chartAxis } },
      axisLabel: {
        color: tokens.textMuted,
        fontFamily: 'Inter, sans-serif',
        fontSize: 11,
      },
    },
    visualMap: {
      min: minD,
      max: maxD,
      calculable: true,
      orient: 'vertical',
      right: '1%',
      top: 'center',
      itemWidth: 12,
      inRange: {
        color: [
          '#1A365D',
          '#2B6CB0',
          '#4299E1',
          '#F6E05E',
          '#ED8936',
          '#C53030',
        ],
      },
      textStyle: {
        color: tokens.textMuted,
        fontSize: 10,
        fontFamily: 'SFMono-Regular, monospace',
      },
      formatter: (val) => `${(val / 1000).toFixed(0)}k`,
    },
    series: [
      {
        name: 'Demand Heatmap',
        type: 'heatmap',
        data: matrixData,
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowColor: 'rgba(0, 0, 0, 0.5)',
          },
        },
      },
    ],
  };

  chart.setOption(option, true);
}
export const renderHeatmapChart = renderDemandHeatmap;

/**
 * Render 24-hour diurnal profile of gross demand and net load (Duck Curve).
 * @param {string} containerId
 * @param {any} data
 */
export function renderDuckCurveChart(containerId, data) {
  const chart = getOrCreateChart(containerId);
  if (!chart) return;

  const tokens = getThemeTokens();
  const profile = data ? (data.hourly_profile || (Array.isArray(data) ? data : [])) : [];
  if (!profile || profile.length === 0) {
    renderEmptyState(chart, tokens);
    return;
  }

  const hours = profile.map((p) => `${p.hour}:00`);
  const gross = profile.map((p) => p.demand_mw !== undefined ? p.demand_mw : p.gross_demand_mw);
  const net = profile.map((p) => p.net_load_mw);
  const solar = profile.map((p) => p.solar_mw);
  const wind = profile.map((p) => p.wind_mw);

  const option = {
    title: { show: false },
    tooltip: baseTooltip(tokens),
    legend: {
      data: ['Gross Demand', 'Net Load', 'Solar Generation', 'Wind Generation'],
      textStyle: { color: tokens.textSecondary, fontSize: 12 },
      top: 4,
      left: 'center',
      type: 'scroll',
    },
    grid: {
      top: 68,
      left: 68,
      right: 28,
      bottom: 42,
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: hours,
      boundaryGap: false,
      axisLine: { lineStyle: { color: tokens.chartAxis } },
      axisLabel: {
        color: tokens.textMuted,
        fontFamily: 'SFMono-Regular, monospace',
        fontSize: 10,
        interval: 1,
      },
    },
    yAxis: {
      type: 'value',
      name: 'Power (MW)',
      nameTextStyle: { color: tokens.textMuted, fontSize: 11, align: 'left', padding: [0, 0, 6, 0] },
      splitLine: { lineStyle: { color: tokens.chartGrid } },
      axisLabel: {
        color: tokens.textMuted,
        fontFamily: 'SFMono-Regular, monospace',
        formatter: (v) => `${(v / 1000).toFixed(0)}k`,
      },
    },
    series: [
      {
        name: 'Gross Demand',
        type: 'line',
        data: gross,
        showSymbol: false,
        lineStyle: { width: 2.5, color: tokens.accentBlue },
        itemStyle: { color: tokens.accentBlue },
      },
      {
        name: 'Net Load',
        type: 'line',
        data: net,
        showSymbol: false,
        lineStyle: { width: 2.5, color: tokens.accentSaffron },
        itemStyle: { color: tokens.accentSaffron },
        areaStyle: {
          color: new window.echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(245, 159, 0, 0.22)' },
            { offset: 1, color: 'rgba(245, 159, 0, 0.02)' },
          ]),
        },
      },
      {
        name: 'Solar Generation',
        type: 'line',
        data: solar,
        showSymbol: false,
        lineStyle: { width: 1.5, color: tokens.accentTeal, type: 'dashed' },
        itemStyle: { color: tokens.accentTeal },
      },
      {
        name: 'Wind Generation',
        type: 'line',
        data: wind,
        showSymbol: false,
        lineStyle: { width: 1.5, color: tokens.accentPurple, type: 'dotted' },
        itemStyle: { color: tokens.accentPurple },
      },
    ],
  };

  chart.setOption(option, true);
}

/**
 * Render monthly renewable energy generation penetration and capacity breakdown.
 * @param {string} containerId
 * @param {Array<{ year_month: string, avg_re_share_pct: number, avg_solar_mw: number, avg_wind_mw: number }>} data
 */
export function renderMonthlyReShareChart(containerId, data) {
  const chart = getOrCreateChart(containerId);
  if (!chart) return;

  const tokens = getThemeTokens();
  if (!data || data.length === 0) {
    renderEmptyState(chart, tokens);
    return;
  }

  const months = data.map((d) => d.year_month);
  const reShare = data.map((d) => d.avg_re_share_pct);
  const solarVals = data.map((d) => d.avg_solar_mw);
  const windVals = data.map((d) => d.avg_wind_mw);

  const option = {
    title: { show: false },
    tooltip: baseTooltip(tokens),
    legend: {
      data: ['RE Penetration (%)', 'Solar Average (MW)', 'Wind Average (MW)'],
      textStyle: { color: tokens.textSecondary, fontSize: 12 },
      top: 4,
      left: 'center',
      type: 'scroll',
    },
    grid: {
      top: 68,
      left: 68,
      right: 68,
      bottom: 45,
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: months,
      axisLine: { lineStyle: { color: tokens.chartAxis } },
      axisLabel: {
        color: tokens.textMuted,
        fontFamily: 'SFMono-Regular, monospace',
        fontSize: 10,
        rotate: 45,
      },
    },
    yAxis: [
      {
        type: 'value',
        name: 'Renewable Share (%)',
        nameTextStyle: { color: tokens.textMuted, fontSize: 11, align: 'left', padding: [0, 0, 6, 0] },
        splitLine: { lineStyle: { color: tokens.chartGrid } },
        axisLabel: {
          color: tokens.textMuted,
          fontFamily: 'SFMono-Regular, monospace',
          formatter: '{value}%',
        },
      },
      {
        type: 'value',
        name: 'Generation (MW)',
        nameTextStyle: { color: tokens.textMuted, fontSize: 11, align: 'right', padding: [0, 0, 6, 0] },
        splitLine: { show: false },
        axisLabel: {
          color: tokens.textMuted,
          fontFamily: 'SFMono-Regular, monospace',
          formatter: (v) => `${(v / 1000).toFixed(0)}k`,
        },
      },
    ],
    series: [
      {
        name: 'RE Penetration (%)',
        type: 'line',
        data: reShare,
        showSymbol: true,
        symbolSize: 6,
        lineStyle: { width: 2.5, color: tokens.accentCoral },
        itemStyle: { color: tokens.accentCoral },
      },
      {
        name: 'Solar Average (MW)',
        type: 'bar',
        yAxisIndex: 1,
        stack: 'RE',
        data: solarVals,
        itemStyle: { color: tokens.accentSaffron },
      },
      {
        name: 'Wind Average (MW)',
        type: 'bar',
        yAxisIndex: 1,
        stack: 'RE',
        data: windVals,
        itemStyle: { color: tokens.accentTeal },
      },
    ],
  };

  chart.setOption(option, true);
}
export const renderReShareChart = renderMonthlyReShareChart;

/**
 * Render demand anomaly scatter plot with +/-2 sigma statistical bounds.
 * @param {string} containerId
 * @param {any} data
 */
export function renderAnomalyDaysChart(containerId, data) {
  const chart = getOrCreateChart(containerId);
  if (!chart) return;

  const tokens = getThemeTokens();
  const allDays = Array.isArray(data) ? data : (data && Array.isArray(data.data) ? data.data : (data && Array.isArray(data.all_days) ? data.all_days : []));

  if (!allDays || allDays.length === 0) {
    renderEmptyState(chart, tokens);
    return;
  }

  const normalPoints = [];
  const anomalyPoints = [];
  const glitchPoints = [];

  for (const d of allDays) {
    const pt = [d.date, d.z_score];
    if (d.is_dq_anomaly || d.is_glitch) {
      glitchPoints.push(pt);
    } else if (d.is_real_anomaly) {
      anomalyPoints.push(pt);
    } else {
      normalPoints.push(pt);
    }
  }

  const option = {
    title: { show: false },
    tooltip: {
      ...baseTooltip(tokens),
      trigger: 'item',
      formatter: (p) => {
        return `<strong>${p.value[0]}</strong><br/>${p.seriesName}: Z = ${Number(p.value[1]).toFixed(2)}`;
      },
    },
    legend: {
      data: ['Normal Operating Days', 'Real Demand Anomalies (±2σ)', 'Data-Quality Glitches'],
      textStyle: { color: tokens.textSecondary, fontSize: 12 },
      top: 4,
      left: 'center',
      type: 'scroll',
    },
    grid: {
      top: 68,
      left: 68,
      right: 28,
      bottom: 42,
      containLabel: true,
    },
    xAxis: {
      type: 'time',
      axisLine: { lineStyle: { color: tokens.chartAxis } },
      axisLabel: {
        color: tokens.textMuted,
        fontFamily: 'SFMono-Regular, monospace',
        fontSize: 10,
      },
    },
    yAxis: {
      type: 'value',
      name: 'Demand Z-Score (σ)',
      nameTextStyle: { color: tokens.textMuted, fontSize: 11, align: 'left', padding: [0, 0, 6, 0] },
      splitLine: { lineStyle: { color: tokens.chartGrid } },
      axisLabel: {
        color: tokens.textMuted,
        fontFamily: 'SFMono-Regular, monospace',
        formatter: '{value}σ',
      },
    },
    series: [
      {
        name: 'Normal Operating Days',
        type: 'scatter',
        symbolSize: 4,
        data: normalPoints,
        itemStyle: { color: 'rgba(43, 108, 176, 0.45)' },
      },
      {
        name: 'Real Demand Anomalies (±2σ)',
        type: 'scatter',
        symbolSize: 8,
        data: anomalyPoints,
        itemStyle: { color: tokens.accentSaffron },
      },
      {
        name: 'Data-Quality Glitches',
        type: 'scatter',
        symbolSize: 9,
        data: glitchPoints,
        itemStyle: { color: tokens.accentCoral },
      },
      {
        name: 'Threshold',
        type: 'line',
        markLine: {
          silent: true,
          lineStyle: { type: 'dashed', color: tokens.accentCoral, width: 1.5 },
          data: [{ yAxis: 2 }, { yAxis: -2 }],
          label: {
            formatter: (p) => `${p.value}σ Threshold`,
            color: tokens.textMuted,
            fontFamily: 'SFMono-Regular, monospace',
            fontSize: 10,
          },
        },
      },
    ],
  };

  chart.setOption(option, true);
}
export const renderAnomaliesChart = renderAnomalyDaysChart;
