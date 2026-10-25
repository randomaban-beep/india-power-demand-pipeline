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
 * Render daily demand time series with peak and rolling baseline.
 * @param {string} containerId
 * @param {Array<{ date: string, avg_mw: number, peak_mw: number, rolling_avg_mw: number }>} data
 */
export function renderDailyDemandChart(containerId, data) {
  const chart = getOrCreateChart(containerId);
  if (!chart) return;

  const tokens = getThemeTokens();
  const dates = data.map((d) => d.date);
  const avgVals = data.map((d) => d.avg_mw);
  const peakVals = data.map((d) => d.peak_mw);
  const rollingVals = data.map((d) => d.rolling_avg_mw);

  const option = {
    tooltip: baseTooltip(tokens),
    legend: {
      data: ['Daily Peak Met', 'Daily Average', '7-Day Rolling Baseline'],
      textStyle: { color: tokens.textSecondary, fontSize: 12 },
      top: 0,
    },
    grid: {
      top: 40,
      left: 55,
      right: 20,
      bottom: 40,
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
      nameTextStyle: { color: tokens.textMuted, fontSize: 11 },
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
  const months = data.map((d) => d.year_month);
  const peakVals = data.map((d) => d.peak_demand_mw);
  const yoyVals = data.map((d) => d.yoy_peak_growth_pct);

  const option = {
    tooltip: {
      ...baseTooltip(tokens),
      formatter: (params) => {
        let res = `<div style="font-weight:600;margin-bottom:4px">${params[0].axisValue}</div>`;
        for (const p of params) {
          const val = p.seriesName.includes('Growth')
            ? `${p.value !== null ? p.value.toFixed(1) : 'N/A'}%`
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
      top: 0,
    },
    grid: {
      top: 40,
      left: 55,
      right: 55,
      bottom: 40,
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
        nameTextStyle: { color: tokens.textMuted, fontSize: 11 },
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
        nameTextStyle: { color: tokens.textMuted, fontSize: 11 },
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
          color: tokens.accentBlue,
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
 * Render temperature vs demand scatter with median-per-1C bin trend line.
 * @param {string} containerId
 * @param {Array<{ temp_c: number, demand_mw: number }>} points
 * @param {Array<{ temp_bin_c: number, median_demand_mw: number }>} medianBins
 * @param {string} featureName
 */
export function renderTempDemandChart(containerId, points, medianBins, featureName) {
  const chart = getOrCreateChart(containerId);
  if (!chart) return;

  const tokens = getThemeTokens();
  const scatterPoints = points.map((p) => [p.temp_c, p.demand_mw]);
  const trendPoints = medianBins.map((b) => [b.temp_bin_c, b.median_demand_mw]);

  const option = {
    tooltip: {
      trigger: 'item',
      backgroundColor: tokens.tooltipBg,
      borderColor: tokens.tooltipBorder,
      textStyle: { color: tokens.tooltipText, fontSize: 12 },
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
      top: 0,
    },
    grid: {
      top: 40,
      left: 55,
      right: 20,
      bottom: 40,
      containLabel: true,
    },
    xAxis: {
      type: 'value',
      name: 'Temperature (°C)',
      nameLocation: 'middle',
      nameGap: 28,
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
      nameTextStyle: { color: tokens.textMuted, fontSize: 11 },
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
        data: scatterPoints,
        symbolSize: 4,
        itemStyle: {
          color: tokens.accentBlue,
          opacity: 0.25,
        },
      },
      {
        name: '1°C Median Demand',
        type: 'line',
        data: trendPoints,
        showSymbol: true,
        symbolSize: 8,
        lineStyle: { width: 3, color: tokens.accentSaffron },
        itemStyle: { color: tokens.accentSaffron },
      },
    ],
  };

  chart.setOption(option, true);
}

/**
 * Render diurnal demand matrix heatmap by calendar month and hour of day.
 * @param {string} containerId
 * @param {Array<{ month: number, hour: number, avg_demand_mw: number }>} data
 */
export function renderHeatmapChart(containerId, data) {
  const chart = getOrCreateChart(containerId);
  if (!chart) return;

  const tokens = getThemeTokens();
  const hours = Array.from({ length: 24 }, (_, i) => `${i}:00`);
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

  const matrixData = data.map((item) => [item.hour, item.month - 1, Math.round(item.avg_demand_mw)]);
  const vals = data.map((d) => d.avg_demand_mw);
  const minVal = vals.length ? Math.floor(Math.min(...vals)) : 100000;
  const maxVal = vals.length ? Math.ceil(Math.max(...vals)) : 220000;

  const option = {
    tooltip: {
      position: 'top',
      backgroundColor: tokens.tooltipBg,
      borderColor: tokens.tooltipBorder,
      textStyle: { color: tokens.tooltipText, fontSize: 12 },
      formatter: (params) => {
        const h = hours[params.value[0]];
        const m = months[params.value[1]];
        return `<strong>${m} @ ${h} IST</strong><br/>Avg Demand: ${Number(params.value[2]).toLocaleString()} MW`;
      },
    },
    grid: {
      top: 20,
      left: 55,
      right: 90,
      bottom: 40,
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
      axisLabel: { color: tokens.textMuted, fontSize: 11 },
    },
    visualMap: {
      min: minVal,
      max: maxVal,
      calculable: true,
      orient: 'vertical',
      right: 0,
      top: 'center',
      inRange: {
        color: ['#1A365D', '#2B6CB0', '#F8FAFC', '#F59F00', '#C05621'],
      },
      textStyle: {
        color: tokens.textMuted,
        fontFamily: 'SFMono-Regular, monospace',
        fontSize: 10,
      },
      formatter: (v) => `${(v / 1000).toFixed(0)}k`,
    },
    series: [
      {
        name: 'Hourly Demand',
        type: 'heatmap',
        data: matrixData,
        label: { show: false },
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

/**
 * Render diurnal net-load duck curve with gross demand, solar, wind, and net load.
 * @param {string} containerId
 * @param {any} duckCurveData
 */
export function renderDuckCurveChart(containerId, duckCurveData) {
  const chart = getOrCreateChart(containerId);
  if (!chart) return;

  const tokens = getThemeTokens();
  const profile = duckCurveData.hourly_profile || [];
  const hours = profile.map((d) => `${d.hour}:00`);
  const demandVals = profile.map((d) => d.demand_mw);
  const netLoadVals = profile.map((d) => d.net_load_mw);
  const solarVals = profile.map((d) => d.solar_mw);
  const windVals = profile.map((d) => d.wind_mw);

  const option = {
    tooltip: baseTooltip(tokens),
    legend: {
      data: ['Gross Demand', 'Net Load', 'Solar Generation', 'Wind Generation'],
      textStyle: { color: tokens.textSecondary, fontSize: 12 },
      top: 0,
    },
    grid: {
      top: 40,
      left: 55,
      right: 20,
      bottom: 40,
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: hours,
      axisLine: { lineStyle: { color: tokens.chartAxis } },
      axisLabel: {
        color: tokens.textMuted,
        fontFamily: 'SFMono-Regular, monospace',
        fontSize: 11,
        interval: 1,
      },
    },
    yAxis: {
      type: 'value',
      name: 'Power (MW)',
      nameTextStyle: { color: tokens.textMuted, fontSize: 11 },
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
        data: demandVals,
        showSymbol: false,
        lineStyle: { width: 2, color: tokens.accentBlue, type: 'dashed' },
        itemStyle: { color: tokens.accentBlue },
      },
      {
        name: 'Net Load',
        type: 'line',
        data: netLoadVals,
        showSymbol: false,
        lineStyle: { width: 3, color: tokens.textPrimary },
        itemStyle: { color: tokens.textPrimary },
      },
      {
        name: 'Solar Generation',
        type: 'line',
        data: solarVals,
        showSymbol: false,
        areaStyle: { color: 'rgba(245, 159, 0, 0.25)' },
        lineStyle: { width: 2, color: tokens.accentSaffron },
        itemStyle: { color: tokens.accentSaffron },
      },
      {
        name: 'Wind Generation',
        type: 'line',
        data: windVals,
        showSymbol: false,
        lineStyle: { width: 1.5, color: tokens.accentTeal },
        itemStyle: { color: tokens.accentTeal },
      },
    ],
  };

  chart.setOption(option, true);
}

/**
 * Render monthly renewable penetration share chart.
 * @param {string} containerId
 * @param {Array<{ year_month: string, avg_re_share_pct: number, avg_solar_mw: number, avg_wind_mw: number }>} data
 */
export function renderReShareChart(containerId, data) {
  const chart = getOrCreateChart(containerId);
  if (!chart) return;

  const tokens = getThemeTokens();
  const months = data.map((d) => d.year_month);
  const reShareVals = data.map((d) => d.avg_re_share_pct);
  const solarVals = data.map((d) => d.avg_solar_mw);
  const windVals = data.map((d) => d.avg_wind_mw);

  const option = {
    tooltip: baseTooltip(tokens),
    legend: {
      data: ['RE Penetration (%)', 'Solar Average (MW)', 'Wind Average (MW)'],
      textStyle: { color: tokens.textSecondary, fontSize: 12 },
      top: 0,
    },
    grid: {
      top: 40,
      left: 55,
      right: 55,
      bottom: 40,
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
        nameTextStyle: { color: tokens.textMuted, fontSize: 11 },
        splitLine: { lineStyle: { color: tokens.chartGrid } },
        axisLabel: {
          color: tokens.textMuted,
          fontFamily: 'SFMono-Regular, monospace',
          formatter: '{value}%',
        },
      },
      {
        type: 'value',
        name: 'Average Generation (MW)',
        nameTextStyle: { color: tokens.textMuted, fontSize: 11 },
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
        data: reShareVals,
        showSymbol: true,
        symbolSize: 6,
        lineStyle: { width: 3, color: tokens.accentSaffron },
        itemStyle: { color: tokens.accentSaffron },
      },
      {
        name: 'Solar Average (MW)',
        type: 'bar',
        yAxisIndex: 1,
        stack: 'RE',
        data: solarVals,
        itemStyle: { color: 'rgba(245, 159, 0, 0.7)' },
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

/**
 * Render demand anomaly detection scatter with +2sigma and -2sigma decision boundaries.
 * @param {string} containerId
 * @param {Array<any>} anomalyData
 */
export function renderAnomaliesChart(containerId, anomalyData) {
  const chart = getOrCreateChart(containerId);
  if (!chart) return;

  const tokens = getThemeTokens();
  const normalPoints = [];
  const realAnomalies = [];
  const dqGlitches = [];

  for (const d of anomalyData) {
    if (d.z_score === null || d.z_score === undefined) continue;
    const pt = [d.date, d.z_score, d.avg_demand_mw, d.peak_demand_mw, d.anomaly_type];
    if (d.is_dq_anomaly === 1) {
      dqGlitches.push(pt);
    } else if (d.is_real_anomaly === 1) {
      realAnomalies.push(pt);
    } else {
      normalPoints.push(pt);
    }
  }

  const option = {
    tooltip: {
      trigger: 'item',
      backgroundColor: tokens.tooltipBg,
      borderColor: tokens.tooltipBorder,
      textStyle: { color: tokens.tooltipText, fontSize: 12 },
      formatter: (params) => {
        const val = params.value;
        return `<strong>${val[0]}</strong><br/>
          Z-Score: ${val[1]}<br/>
          Avg Demand: ${Number(val[2]).toLocaleString()} MW<br/>
          Classification: ${params.seriesName}`;
      },
    },
    legend: {
      data: ['Normal Operating Days', 'Real Demand Anomalies (±2σ)', 'Data-Quality Glitches'],
      textStyle: { color: tokens.textSecondary, fontSize: 12 },
      top: 0,
    },
    grid: {
      top: 40,
      left: 55,
      right: 20,
      bottom: 40,
      containLabel: true,
    },
    xAxis: {
      type: 'time',
      axisLine: { lineStyle: { color: tokens.chartAxis } },
      axisLabel: {
        color: tokens.textMuted,
        fontFamily: 'SFMono-Regular, monospace',
        fontSize: 11,
      },
    },
    yAxis: {
      type: 'value',
      name: 'Demand Z-Score (σ)',
      nameTextStyle: { color: tokens.textMuted, fontSize: 11 },
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
        data: normalPoints,
        symbolSize: 4,
        itemStyle: { color: tokens.textMuted, opacity: 0.35 },
      },
      {
        name: 'Real Demand Anomalies (±2σ)',
        type: 'scatter',
        data: realAnomalies,
        symbolSize: 10,
        itemStyle: { color: tokens.accentSaffron, borderColor: '#FFFFFF', borderWidth: 1 },
      },
      {
        name: 'Data-Quality Glitches',
        type: 'scatter',
        data: dqGlitches,
        symbolSize: 10,
        symbol: 'diamond',
        itemStyle: { color: tokens.accentCoral, borderColor: '#FFFFFF', borderWidth: 1 },
      },
      {
        type: 'line',
        markLine: {
          silent: true,
          lineStyle: { type: 'dashed', color: tokens.accentCoral, width: 1.5 },
          data: [{ yAxis: 2 }, { yAxis: -2 }],
          label: {
            formatter: (p) => `${p.value}σ Threshold`,
            color: tokens.textMuted,
            fontSize: 10,
            fontFamily: 'SFMono-Regular, monospace',
          },
        },
      },
    ],
  };

  chart.setOption(option, true);
}
