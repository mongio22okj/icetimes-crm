// Tailwind v4 uses OKLCh tokens that don't flow into ApexCharts' color prop,
// so we resolve theme-aware hex values here.
function themeColors() {
  const dark = document.documentElement.classList.contains('dark');
  return {
    muted:  dark ? '#94a3b8' : '#64748b', // slate-400 / slate-500
    border: dark ? '#1e293b' : '#e2e8f0', // slate-800 / slate-200
    fg:     dark ? '#f8fafc' : '#0f172a', // slate-50  / slate-900
  };
}

function revenueChart() {
  return {
    range: '7d',
    chart: null,
    async init() {
      await this.load(this.range);
      this._themeObserver = new MutationObserver(() => this.load(this.range));
      this._themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    },
    async load(range) {
      this.range = range;
      const res = await fetch(`/charts/revenue/?range=${range}`);
      const data = await res.json();
      // Back-compat: older payload shape is [[...]]; new shape is [{name,data}, ...].
      // Per-series `type` makes Revenue render as an area (with gradient) and
      // Orders as a clean line on the secondary axis.
      const series = (data.series || []).map((s, i) => {
        const obj = Array.isArray(s) ? { name: `Series ${i + 1}`, data: s } : s;
        return { ...obj, type: obj.name === 'Orders' ? 'line' : 'area' };
      });
      const c = themeColors();
      const opts = {
        chart: {
          height: 320,
          toolbar: { show: false },
          animations: { enabled: true },
          fontFamily: 'inherit',
          foreColor: c.muted,
        },
        series,
        xaxis: {
          categories: data.categories,
          labels: { style: { colors: c.muted, fontSize: '12px' } },
          axisBorder: { color: c.border },
          axisTicks: { color: c.border },
        },
        yaxis: [
          {
            seriesName: 'Revenue',
            labels: {
              style: { colors: c.muted, fontSize: '12px' },
              formatter: v => '$' + Math.round(v).toLocaleString(),
            },
          },
          {
            seriesName: 'Orders',
            opposite: true,
            labels: { style: { colors: c.muted, fontSize: '12px' } },
          },
        ],
        colors: ['#16a34a', '#0891b2'],
        stroke: { curve: 'smooth', width: [3, 2.5] },
        fill: {
          type: 'gradient',
          gradient: {
            shadeIntensity: 1,
            opacityFrom: 0.35,
            opacityTo: 0.05,
            stops: [0, 100],
          },
        },
        grid: {
          borderColor: c.border,
          strokeDashArray: 4,
          padding: { left: 8, right: 8 },
        },
        dataLabels: { enabled: false },
        legend: {
          show: true,
          position: 'top',
          horizontalAlign: 'right',
          markers: { size: 6, strokeWidth: 0, offsetX: -4 },
          itemMargin: { horizontal: 8 },
          labels: { colors: c.muted },
        },
        markers: { size: 0, strokeWidth: 0, hover: { size: 5 } },
        tooltip: {
          theme: document.documentElement.classList.contains('dark') ? 'dark' : 'light',
          shared: true,
          intersect: false,
        },
      };
      if (this.chart) {
        this.chart.updateOptions(opts);
      } else {
        this.chart = new ApexCharts(document.querySelector('#revenue-chart'), opts);
        this.chart.render();
      }
    },
  };
}
window.revenueChart = revenueChart;

function trafficChart() {
  return {
    chart: null,
    _opts: null,
    init() {
      const dataEl = document.getElementById('traffic-sources-data');
      this._sources = dataEl ? JSON.parse(dataEl.textContent) : [];
      this.render();
      new MutationObserver(() => this.render())
        .observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    },
    render() {
      const sources = this._sources;
      const total = sources.reduce((sum, s) => sum + Number(s.value || 0), 0);
      const totalLabel = total >= 1000 ? (total / 1000).toFixed(1).replace(/\.0$/, '') + 'K' : String(total);
      const c = themeColors();
      const opts = {
        chart: { type: 'donut', height: 180, toolbar: { show: false }, fontFamily: 'inherit' },
        series: sources.map(s => s.value),
        labels: sources.map(s => s.label),
        colors: ['#16a34a', '#0891b2', '#6366f1', '#d97706'],
        legend: { show: false },
        plotOptions: {
          pie: {
            donut: {
              size: '72%',
              labels: {
                show: true,
                name: { show: true, offsetY: 20, color: c.muted, fontSize: '11px' },
                value: { show: true, offsetY: -15, fontSize: '22px', fontWeight: 700, color: c.fg },
                total: {
                  show: true,
                  label: 'Total',
                  fontSize: '11px',
                  color: c.muted,
                  formatter: () => totalLabel,
                },
              },
            },
          },
        },
        stroke: { width: 0 },
        dataLabels: { enabled: false },
      };
      if (this.chart) {
        this.chart.updateOptions(opts);
      } else {
        this.chart = new ApexCharts(document.querySelector('#traffic-chart'), opts);
        this.chart.render();
      }
    },
  };
}
window.trafficChart = trafficChart;

// ── Dashboard variant chart factories ────────────────────────────────
// Each factory follows the same shape: read JSON payload from a
// json_script element, render an ApexCharts instance, and re-render on
// theme toggle so muted/border/foreground colors stay correct.

const VARIANT_PALETTE = ['#16a34a', '#0891b2', '#6366f1', '#d97706', '#be185d'];

function _readJSON(id) {
  const el = document.getElementById(id);
  return el ? JSON.parse(el.textContent) : null;
}

function _onThemeChange(cb) {
  new MutationObserver(cb).observe(document.documentElement,
    { attributes: true, attributeFilter: ['class'] });
}

function _baseAxis(c) {
  return {
    labels: { style: { colors: c.muted, fontSize: '12px' } },
    axisBorder: { color: c.border },
    axisTicks: { color: c.border },
  };
}

// Analytics: views + visitors over time (dual area)
function pageViewsChart() {
  return {
    chart: null,
    init() { this.render(); _onThemeChange(() => this.render()); },
    render() {
      const data = _readJSON('page-views-data');
      const c = themeColors();
      const opts = {
        chart: { type: 'area', height: 320, toolbar: { show: false },
                 fontFamily: 'inherit', foreColor: c.muted },
        series: [
          { name: 'Page Views', data: data.views },
          { name: 'Unique Visitors', data: data.visitors },
        ],
        xaxis: { categories: data.categories, ..._baseAxis(c) },
        yaxis: { labels: { style: { colors: c.muted, fontSize: '12px' },
                           formatter: v => v >= 1000 ? (v / 1000).toFixed(0) + 'K' : v } },
        colors: [VARIANT_PALETTE[0], VARIANT_PALETTE[1]],
        stroke: { curve: 'smooth', width: 2.5 },
        fill: { type: 'gradient',
                gradient: { opacityFrom: 0.35, opacityTo: 0.05, stops: [0, 100] } },
        grid: { borderColor: c.border, strokeDashArray: 4 },
        dataLabels: { enabled: false },
        legend: { position: 'top', horizontalAlign: 'right',
                  labels: { colors: c.muted } },
        tooltip: { theme: document.documentElement.classList.contains('dark') ? 'dark' : 'light',
                   shared: true, intersect: false },
      };
      if (this.chart) { this.chart.updateOptions(opts); }
      else { this.chart = new ApexCharts(document.querySelector('#page-views-chart'), opts);
             this.chart.render(); }
    },
  };
}
window.pageViewsChart = pageViewsChart;

// Analytics: revenue by category (horizontal bar)
function categoryRevenueChart() {
  return {
    chart: null,
    init() { this.render(); _onThemeChange(() => this.render()); },
    render() {
      const data = _readJSON('category-revenue-data');
      const c = themeColors();
      const opts = {
        chart: { type: 'bar', height: 260, toolbar: { show: false },
                 fontFamily: 'inherit', foreColor: c.muted },
        series: [{ name: 'Revenue', data: data.map(d => d.revenue) }],
        xaxis: { categories: data.map(d => d.category), ..._baseAxis(c),
                 labels: { ..._baseAxis(c).labels,
                           formatter: v => '$' + (v / 1000).toFixed(0) + 'K' } },
        colors: [VARIANT_PALETTE[0]],
        plotOptions: { bar: { horizontal: true, borderRadius: 4, barHeight: '60%' } },
        dataLabels: { enabled: false },
        grid: { borderColor: c.border, strokeDashArray: 4 },
        tooltip: { theme: document.documentElement.classList.contains('dark') ? 'dark' : 'light',
                   y: { formatter: v => '$' + v.toLocaleString() } },
      };
      if (this.chart) { this.chart.updateOptions(opts); }
      else { this.chart = new ApexCharts(document.querySelector('#category-revenue-chart'), opts);
             this.chart.render(); }
    },
  };
}
window.categoryRevenueChart = categoryRevenueChart;

// CRM: pipeline value bar + count line (mixed)
function pipelineChart() {
  return {
    chart: null,
    init() { this.render(); _onThemeChange(() => this.render()); },
    render() {
      const data = _readJSON('pipeline-data');
      const c = themeColors();
      const opts = {
        chart: { type: 'line', height: 320, toolbar: { show: false },
                 fontFamily: 'inherit', foreColor: c.muted, stacked: false },
        series: [
          { name: 'Pipeline Value', type: 'column', data: data.value },
          { name: 'Deals', type: 'line', data: data.count },
        ],
        xaxis: { categories: data.categories, ..._baseAxis(c) },
        yaxis: [
          { labels: { style: { colors: c.muted },
                      formatter: v => '$' + (v / 1000).toFixed(0) + 'K' } },
          { opposite: true, labels: { style: { colors: c.muted } } },
        ],
        colors: [VARIANT_PALETTE[0], VARIANT_PALETTE[1]],
        plotOptions: { bar: { borderRadius: 4, columnWidth: '55%' } },
        stroke: { width: [0, 3], curve: 'smooth' },
        markers: { size: [0, 4] },
        grid: { borderColor: c.border, strokeDashArray: 4 },
        dataLabels: { enabled: false },
        legend: { position: 'top', horizontalAlign: 'right',
                  labels: { colors: c.muted } },
        tooltip: { theme: document.documentElement.classList.contains('dark') ? 'dark' : 'light',
                   shared: true, intersect: false },
      };
      if (this.chart) { this.chart.updateOptions(opts); }
      else { this.chart = new ApexCharts(document.querySelector('#pipeline-chart'), opts);
             this.chart.render(); }
    },
  };
}
window.pipelineChart = pipelineChart;

// Generic donut factory — used for deal-stages, plans, order-status
function _donutFactory(targetId, dataId) {
  return {
    chart: null,
    init() { this.render(); _onThemeChange(() => this.render()); },
    render() {
      const data = _readJSON(dataId);
      const c = themeColors();
      const total = data.reduce((s, d) => s + Number(d.value || 0), 0);
      const opts = {
        chart: { type: 'donut', height: 260, fontFamily: 'inherit',
                 toolbar: { show: false } },
        series: data.map(d => d.value),
        labels: data.map(d => d.name),
        colors: VARIANT_PALETTE,
        legend: { position: 'bottom', labels: { colors: c.muted },
                  markers: { size: 6, strokeWidth: 0 },
                  itemMargin: { horizontal: 8, vertical: 4 } },
        plotOptions: {
          pie: {
            donut: { size: '68%', labels: {
              show: true,
              name: { show: true, color: c.muted, fontSize: '11px' },
              value: { show: true, fontSize: '20px', fontWeight: 700, color: c.fg,
                       formatter: v => Number(v).toLocaleString() },
              total: { show: true, label: 'Total', color: c.muted, fontSize: '11px',
                       formatter: () => total.toLocaleString() },
            } } },
        },
        stroke: { width: 0 },
        dataLabels: { enabled: false },
      };
      if (this.chart) { this.chart.updateOptions(opts); }
      else { this.chart = new ApexCharts(document.querySelector(targetId), opts);
             this.chart.render(); }
    },
  };
}
function dealStagesChart()   { return _donutFactory('#deal-stages-chart',  'deal-stages-data'); }
function plansChart()        { return _donutFactory('#plans-chart',        'plans-data'); }
function orderStatusChart()  { return _donutFactory('#order-status-chart', 'order-status-data'); }
window.dealStagesChart  = dealStagesChart;
window.plansChart       = plansChart;
window.orderStatusChart = orderStatusChart;

// CRM: lead sources (vertical bar)
function leadSourcesChart() {
  return {
    chart: null,
    init() { this.render(); _onThemeChange(() => this.render()); },
    render() {
      const data = _readJSON('lead-sources-data');
      const c = themeColors();
      const opts = {
        chart: { type: 'bar', height: 260, toolbar: { show: false },
                 fontFamily: 'inherit', foreColor: c.muted },
        series: [{ name: 'Leads', data: data.map(d => d.leads) }],
        xaxis: { categories: data.map(d => d.source), ..._baseAxis(c) },
        yaxis: { labels: { style: { colors: c.muted } } },
        colors: [VARIANT_PALETTE[2]],
        plotOptions: { bar: { borderRadius: 4, columnWidth: '55%' } },
        dataLabels: { enabled: false },
        grid: { borderColor: c.border, strokeDashArray: 4 },
        tooltip: { theme: document.documentElement.classList.contains('dark') ? 'dark' : 'light' },
      };
      if (this.chart) { this.chart.updateOptions(opts); }
      else { this.chart = new ApexCharts(document.querySelector('#lead-sources-chart'), opts);
             this.chart.render(); }
    },
  };
}
window.leadSourcesChart = leadSourcesChart;

// eCommerce: daily sales (3 series area)
function dailySalesChart() {
  return {
    chart: null,
    init() { this.render(); _onThemeChange(() => this.render()); },
    render() {
      const data = _readJSON('daily-sales-data');
      const c = themeColors();
      const opts = {
        chart: { type: 'area', height: 320, toolbar: { show: false },
                 fontFamily: 'inherit', foreColor: c.muted },
        series: [
          { name: 'Revenue', data: data.map(d => d.revenue) },
          { name: 'Profit',  data: data.map(d => d.profit) },
          { name: 'Orders',  data: data.map(d => d.orders) },
        ],
        xaxis: { categories: data.map(d => d.date), ..._baseAxis(c),
                 labels: { ..._baseAxis(c).labels, rotate: 0,
                           formatter: (v, _, opts) => opts && opts.i % 5 === 0 ? v : '' } },
        yaxis: [
          { labels: { style: { colors: c.muted },
                      formatter: v => '$' + v.toLocaleString() } },
          { show: false },
          { opposite: true, labels: { style: { colors: c.muted } } },
        ],
        colors: [VARIANT_PALETTE[0], VARIANT_PALETTE[1], VARIANT_PALETTE[3]],
        stroke: { curve: 'smooth', width: 2.5 },
        fill: { type: 'gradient',
                gradient: { opacityFrom: 0.3, opacityTo: 0.0, stops: [0, 100] } },
        grid: { borderColor: c.border, strokeDashArray: 4 },
        dataLabels: { enabled: false },
        legend: { position: 'top', horizontalAlign: 'right',
                  labels: { colors: c.muted } },
        tooltip: { theme: document.documentElement.classList.contains('dark') ? 'dark' : 'light',
                   shared: true, intersect: false },
      };
      if (this.chart) { this.chart.updateOptions(opts); }
      else { this.chart = new ApexCharts(document.querySelector('#daily-sales-chart'), opts);
             this.chart.render(); }
    },
  };
}
window.dailySalesChart = dailySalesChart;

// eCommerce: sales by category (treemap-ish bar)
function categorySalesChart() {
  return {
    chart: null,
    init() { this.render(); _onThemeChange(() => this.render()); },
    render() {
      const data = _readJSON('category-sales-data');
      const c = themeColors();
      const opts = {
        chart: { type: 'bar', height: 300, toolbar: { show: false },
                 fontFamily: 'inherit', foreColor: c.muted },
        series: [{ name: 'Revenue', data: data.map((d, i) => ({
          x: d.category, y: d.revenue, fillColor: VARIANT_PALETTE[i % VARIANT_PALETTE.length],
        })) }],
        xaxis: _baseAxis(c),
        yaxis: { labels: { style: { colors: c.muted },
                           formatter: v => '$' + (v / 1000).toFixed(0) + 'K' } },
        plotOptions: { bar: { borderRadius: 4, columnWidth: '55%',
                              distributed: true } },
        legend: { show: false },
        dataLabels: { enabled: false },
        grid: { borderColor: c.border, strokeDashArray: 4 },
        tooltip: { theme: document.documentElement.classList.contains('dark') ? 'dark' : 'light',
                   y: { formatter: v => '$' + v.toLocaleString() } },
      };
      if (this.chart) { this.chart.updateOptions(opts); }
      else { this.chart = new ApexCharts(document.querySelector('#category-sales-chart'), opts);
             this.chart.render(); }
    },
  };
}
window.categorySalesChart = categorySalesChart;

// SaaS: MRR vs ARR area chart
function revenueGrowthChart() {
  return {
    chart: null,
    init() { this.render(); _onThemeChange(() => this.render()); },
    render() {
      const data = _readJSON('revenue-growth-data');
      const c = themeColors();
      const opts = {
        chart: { type: 'area', height: 320, toolbar: { show: false },
                 fontFamily: 'inherit', foreColor: c.muted },
        series: [
          { name: 'MRR', data: data.mrr },
          { name: 'ARR', data: data.arr },
        ],
        xaxis: { categories: data.categories, ..._baseAxis(c) },
        yaxis: { labels: { style: { colors: c.muted },
                           formatter: v => '$' + (v / 1000).toFixed(0) + 'K' } },
        colors: [VARIANT_PALETTE[0], VARIANT_PALETTE[1]],
        stroke: { curve: 'smooth', width: 2.5 },
        fill: { type: 'gradient',
                gradient: { opacityFrom: 0.3, opacityTo: 0.0, stops: [0, 100] } },
        grid: { borderColor: c.border, strokeDashArray: 4 },
        dataLabels: { enabled: false },
        legend: { position: 'top', horizontalAlign: 'right',
                  labels: { colors: c.muted } },
        tooltip: { theme: document.documentElement.classList.contains('dark') ? 'dark' : 'light',
                   shared: true, intersect: false },
      };
      if (this.chart) { this.chart.updateOptions(opts); }
      else { this.chart = new ApexCharts(document.querySelector('#revenue-growth-chart'), opts);
             this.chart.render(); }
    },
  };
}
window.revenueGrowthChart = revenueGrowthChart;

// SaaS: monthly user growth (vertical bar)
function userGrowthChart() {
  return {
    chart: null,
    init() { this.render(); _onThemeChange(() => this.render()); },
    render() {
      const data = _readJSON('user-growth-data');
      const c = themeColors();
      const opts = {
        chart: { type: 'bar', height: 260, toolbar: { show: false },
                 fontFamily: 'inherit', foreColor: c.muted },
        series: [{ name: 'New users', data: data.new }],
        xaxis: { categories: data.categories, ..._baseAxis(c) },
        yaxis: { labels: { style: { colors: c.muted } } },
        colors: [VARIANT_PALETTE[0]],
        plotOptions: { bar: { borderRadius: 4, columnWidth: '55%' } },
        dataLabels: { enabled: false },
        grid: { borderColor: c.border, strokeDashArray: 4 },
        tooltip: { theme: document.documentElement.classList.contains('dark') ? 'dark' : 'light' },
      };
      if (this.chart) { this.chart.updateOptions(opts); }
      else { this.chart = new ApexCharts(document.querySelector('#user-growth-chart'), opts);
             this.chart.render(); }
    },
  };
}
window.userGrowthChart = userGrowthChart;

function statSparkline(data, color) {
  return {
    chart: null,
    init() {
      const opts = {
        chart: {
          type: 'area',
          height: 40,
          sparkline: { enabled: true },
          animations: { enabled: false },
        },
        series: [{ data }],
        colors: [color || '#16a34a'],
        stroke: { curve: 'smooth', width: 2 },
        fill: {
          type: 'gradient',
          gradient: { opacityFrom: 0.4, opacityTo: 0.0, stops: [0, 100] },
        },
        tooltip: { enabled: false },
      };
      this.chart = new ApexCharts(this.$refs.spark, opts);
      this.chart.render();
    },
  };
}
window.statSparkline = statSparkline;
