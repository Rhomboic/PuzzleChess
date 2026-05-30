// ── Data ─────────────────────────────────────────────────────────────────────

const MODELS = {
  'gpt-4.1-mini': {
    label: 'GPT-4.1 Mini',
    provider: 'openai',
    tier: 'Fast / Cheap',
    accuracy: 0.0167,
    avg_score: 0.2704,
    avg_valid_ratio: 0.238,
    format_compliance_rate: 0.8433,
    avg_latency_ms: 1420,
    avg_input_tokens: 252,
    avg_output_tokens: 95,
    accuracy_by_tier: { beginner: 0.04, intermediate: 0.0133, advanced: 0.0133, expert: 0.0 },
    accuracy_by_mate_type: { mateIn1: 0.0833, mateIn2: 0.0, mateIn3: 0.0, mateIn4: 0.0, mateIn5: 0.0 },
    score_dist: [33, 132, 54, 30, 8, 38, 0, 0, 0, 5],
  },
  'gpt-4.1': {
    label: 'GPT-4.1',
    provider: 'openai',
    tier: 'Mid',
    accuracy: 0.0633,
    avg_score: 0.3552,
    avg_valid_ratio: 0.4064,
    format_compliance_rate: 0.87,
    avg_latency_ms: 751,
    avg_input_tokens: 252,
    avg_output_tokens: 25,
    accuracy_by_tier: { beginner: 0.12, intermediate: 0.0533, advanced: 0.04, expert: 0.04 },
    accuracy_by_mate_type: { mateIn1: 0.25, mateIn2: 0.0333, mateIn3: 0.0167, mateIn4: 0.0167, mateIn5: 0.0 },
    score_dist: [28, 70, 44, 60, 26, 53, 0, 0, 0, 19],
  },
  'claude-haiku-4-5': {
    label: 'Claude Haiku 4.5',
    provider: 'claude',
    tier: 'Fast / Cheap',
    accuracy: 0.0167,
    avg_score: 0.1759,
    avg_valid_ratio: 0.147,
    format_compliance_rate: 0.4467,
    avg_latency_ms: 8330,
    avg_input_tokens: 270,
    avg_output_tokens: 899,
    accuracy_by_tier: { beginner: 0.0533, intermediate: 0.0133, advanced: 0.0, expert: 0.0 },
    accuracy_by_mate_type: { mateIn1: 0.0833, mateIn2: 0.0, mateIn3: 0.0, mateIn4: 0.0, mateIn5: 0.0 },
    score_dist: [144, 78, 43, 7, 5, 18, 0, 0, 0, 5],
  },
  'claude-sonnet-4-6': { label: 'Claude Sonnet 4.6', provider: 'claude', tier: 'Mid', pending: true },
  'claude-opus-4-7':   { label: 'Claude Opus 4.7',   provider: 'claude', tier: 'Flagship', pending: true },
  'o3':                { label: 'o3',                 provider: 'openai', tier: 'Reasoning', pending: true },
};

const TIERS     = ['beginner', 'intermediate', 'advanced', 'expert'];
const MATE_TYPES = ['mateIn1', 'mateIn2', 'mateIn3', 'mateIn4', 'mateIn5'];

const C_ACCENT  = '#00d4ff';
const C_PURPLE  = '#7c3aed';
const C_GREEN   = '#10b981';
const C_MUTED   = '#555';
const C_BORDER  = '#2a2a2a';
const C_TEXT    = '#888';

Chart.defaults.color = C_TEXT;
Chart.defaults.borderColor = C_BORDER;
Chart.defaults.font.family = 'Inter';

function pct(v)  { return (v * 100).toFixed(1) + '%'; }
function ms(v)   { return v >= 1000 ? (v/1000).toFixed(1) + 's' : Math.round(v) + 'ms'; }
function modelColor(m) { return MODELS[m].provider === 'openai' ? C_ACCENT : C_PURPLE; }

// ── Tab switching ─────────────────────────────────────────────────────────────

function initTabs() {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const target = btn.dataset.tab;
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById('panel-' + target).classList.add('active');
    });
  });
}

// ── Overview charts ───────────────────────────────────────────────────────────

function buildOverviewCharts() {
  const active = Object.entries(MODELS).filter(([,m]) => !m.pending);
  const labels  = active.map(([,m]) => m.label);
  const colors  = active.map(([k]) => modelColor(k));

  // Accuracy bar
  new Chart(document.getElementById('chart-accuracy'), {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Accuracy',
        data: active.map(([,m]) => +(m.accuracy * 100).toFixed(1)),
        backgroundColor: colors.map(c => c + '33'),
        borderColor: colors,
        borderWidth: 2,
        borderRadius: 4,
      }]
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        y: { ticks: { callback: v => v + '%' }, grid: { color: C_BORDER } },
        x: { grid: { display: false } }
      }
    }
  });

  // Avg score bar
  new Chart(document.getElementById('chart-score'), {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Avg Score',
        data: active.map(([,m]) => +(m.avg_score).toFixed(3)),
        backgroundColor: colors.map(c => c + '33'),
        borderColor: colors,
        borderWidth: 2,
        borderRadius: 4,
      }]
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        y: { min: 0, max: 1, grid: { color: C_BORDER } },
        x: { grid: { display: false } }
      }
    }
  });

  // Latency vs Accuracy scatter
  new Chart(document.getElementById('chart-scatter'), {
    type: 'scatter',
    data: {
      datasets: active.map(([k, m]) => ({
        label: m.label,
        data: [{ x: m.avg_latency_ms / 1000, y: +(m.accuracy * 100).toFixed(1) }],
        backgroundColor: modelColor(k) + '99',
        borderColor: modelColor(k),
        pointRadius: 10,
        pointHoverRadius: 13,
      }))
    },
    options: {
      responsive: true,
      plugins: {
        legend: { position: 'bottom', labels: { boxWidth: 10, font: { size: 11 } } },
        tooltip: {
          callbacks: {
            label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y}% accuracy @ ${ctx.parsed.x.toFixed(1)}s`
          }
        }
      },
      scales: {
        x: { title: { display: true, text: 'Avg Latency (s)', color: C_TEXT }, grid: { color: C_BORDER } },
        y: { title: { display: true, text: 'Accuracy (%)', color: C_TEXT }, grid: { color: C_BORDER } }
      }
    }
  });

  // Format compliance bar
  new Chart(document.getElementById('chart-format'), {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Format Compliance',
        data: active.map(([,m]) => +(m.format_compliance_rate * 100).toFixed(1)),
        backgroundColor: colors.map(c => c + '33'),
        borderColor: colors,
        borderWidth: 2,
        borderRadius: 4,
      }]
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        y: { min: 0, max: 100, ticks: { callback: v => v + '%' }, grid: { color: C_BORDER } },
        x: { grid: { display: false } }
      }
    }
  });
}

// ── Per-model charts ──────────────────────────────────────────────────────────

function buildModelCharts(key) {
  const m = MODELS[key];
  if (m.pending) return;
  const color = modelColor(key);

  // Accuracy by tier
  new Chart(document.getElementById(`chart-${key}-tier`), {
    type: 'bar',
    data: {
      labels: TIERS.map(t => t.charAt(0).toUpperCase() + t.slice(1)),
      datasets: [{
        label: 'Accuracy',
        data: TIERS.map(t => +(m.accuracy_by_tier[t] * 100).toFixed(1)),
        backgroundColor: color + '33',
        borderColor: color,
        borderWidth: 2,
        borderRadius: 4,
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { callback: v => v + '%' }, grid: { color: C_BORDER } },
        y: { grid: { display: false } }
      }
    }
  });

  // Accuracy by mate type
  new Chart(document.getElementById(`chart-${key}-mate`), {
    type: 'bar',
    data: {
      labels: MATE_TYPES,
      datasets: [{
        label: 'Accuracy',
        data: MATE_TYPES.map(t => +(m.accuracy_by_mate_type[t] * 100).toFixed(1)),
        backgroundColor: color + '33',
        borderColor: color,
        borderWidth: 2,
        borderRadius: 4,
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { callback: v => v + '%' }, grid: { color: C_BORDER } },
        y: { grid: { display: false } }
      }
    }
  });

  // Score distribution
  new Chart(document.getElementById(`chart-${key}-dist`), {
    type: 'bar',
    data: {
      labels: ['0-0.1','0.1-0.2','0.2-0.3','0.3-0.4','0.4-0.5','0.5-0.6','0.6-0.7','0.7-0.8','0.8-0.9','0.9-1.0'],
      datasets: [{
        label: 'Puzzles',
        data: m.score_dist,
        backgroundColor: color + '44',
        borderColor: color,
        borderWidth: 1,
        borderRadius: 2,
      }]
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        y: { grid: { color: C_BORDER } },
        x: { grid: { display: false }, ticks: { font: { size: 10 } } }
      }
    }
  });
}

// ── Init ──────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  buildOverviewCharts();
  Object.keys(MODELS).forEach(k => buildModelCharts(k));
});
