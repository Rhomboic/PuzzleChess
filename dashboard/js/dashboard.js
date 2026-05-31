// ── Config ────────────────────────────────────────────────────────────────────

const IS_LOCAL = ['localhost', '127.0.0.1', '::1', '[::]'].includes(location.hostname) || location.hostname === '';
const S3_BASE  = IS_LOCAL
  ? 'results/'
  : 'https://puzzlechess-results-673981388599.s3.us-west-1.amazonaws.com/runs/';

// Known models: label/provider/tier + a qualitative analysis write-up per model.
const MODEL_META = {
  'claude-haiku-4-5': {
    label: 'Claude Haiku 4.5', provider: 'claude', tier: 'Fast / Cheap',
    analysis: `
      <div class="method-section"><h3>Profile</h3>
      <p>Same accuracy as GPT-4.1 Mini (1.7%) but ~8× slower and far less disciplined: only <strong>45% format compliance</strong> despite burning ~900 output tokens per puzzle. Solves a few mate-in-1s and essentially nothing longer.</p></div>
      <div class="method-section"><h3>What stands out</h3>
      <p>It reasons at length but rarely converges, and it frequently drifts out of clean UCI into algebraic notation, prose, or the wrong number of moves, so even when the idea is reasonable, the answer is unusable. The weakest cost/benefit in the field: verbose without payoff.</p></div>`,
  },
  'claude-sonnet-4-6': {
    label: 'Claude Sonnet 4.6', provider: 'claude', tier: 'Mid',
    analysis: `
      <div class="method-section"><h3>Profile</h3>
      <p>Ties GPT-4.1 on accuracy (6%) with the highest format compliance of any model except o3 (<strong>91%</strong>). Slow (~24s) and verbose (~1,180 output tokens).</p></div>
      <div class="method-section"><h3>What stands out</h3>
      <p>The most <strong>disciplined output</strong> among the non-reasoning models: when it answers, it's clean UCI of the right length. But the extra deliberation buys format reliability, not more solutions. It lands the same accuracy as GPT-4.1 at ~30× the latency.</p></div>`,
  },
  'claude-opus-4-7': {
    label: 'Claude Opus 4.7', provider: 'claude', tier: 'Flagship',
    analysis: `
      <div class="method-section"><h3>Profile</h3>
      <p>Highest accuracy of the five non-reasoning models (<strong>8.3%</strong>), yet the <strong>lowest format compliance (36%)</strong> and the highest token use (~1,775), which drags its composite score (0.19) to near the bottom.</p></div>
      <div class="method-section"><h3>What stands out</h3>
      <p>The clearest case of <strong>capability undercut by output</strong>. It finds more mates than any other non-reasoning model, but routinely spills repeated or loose moves instead of a single clean line, so the eval can't credit work it actually did. A sharp illustration that raw ability does not equal usable output.</p></div>`,
  },
  'gpt-4.1-mini': {
    label: 'GPT-4.1 Mini', provider: 'openai', tier: 'Fast / Cheap',
    analysis: `
      <div class="method-section"><h3>Profile</h3>
      <p>The cheapest, fastest model (~1s, ~95 output tokens). Solves only the simplest puzzles (~8% of mate-in-1s, essentially 0% beyond) with solid format compliance (84%).</p></div>
      <div class="method-section"><h3>What stands out</h3>
      <p>The capability <strong>floor</strong>: fast and well-behaved, but no real multi-move search. It can occasionally pattern-match a one-move mate; anything requiring lookahead collapses.</p></div>`,
  },
  'gpt-4.1': {
    label: 'GPT-4.1', provider: 'openai', tier: 'Mid',
    analysis: `
      <div class="method-section"><h3>Profile</h3>
      <p>Best of the non-reasoning models on composite score (0.36), driven by speed and format discipline: sub-second responses, just ~25 output tokens, 87% format compliance. 25% on mate-in-1, tapering to ~0 by mate-in-3.</p></div>
      <div class="method-section"><h3>What stands out</h3>
      <p>The most <strong>efficient</strong> model in the field: terse, fast, clean. But efficiency is the whole story. It answers quickly and correctly formats, it just can't search deep. Excellent cost/latency, hard capability ceiling.</p></div>`,
  },
  'o3': {
    label: 'o3', provider: 'openai', tier: 'Reasoning',
    analysis: `
      <div class="method-section"><h3>Profile</h3>
      <p>A different class entirely: <strong>71% accuracy</strong> vs. single digits for every other model, with 92% format compliance. It degrades <em>gracefully</em> along difficulty (mate-in-1 95% down to mate-in-5 50%; beginner 83% down to expert 56%) where the others flatline near 0%. The cost is latency (~104s per puzzle) and price.</p></div>
      <div class="method-section"><h3>What stands out: it knows when it's stuck</h3>
      <p>o3 has a failure mode the others don't: when it genuinely can't find a forced mate, it <strong>says so</strong> ("I'm sorry, I can't solve this") instead of inventing a plausible-looking wrong line. Its misses are mostly explicit refusals or last-move near-misses, not confident hallucinations. That calibration is a real qualitative edge the accuracy number alone doesn't capture: a more honest, safer behavior.</p></div>`,
  },
};

const TIERS      = ['beginner', 'intermediate', 'advanced', 'expert'];
const MATE_TYPES = ['mateIn1', 'mateIn2', 'mateIn3', 'mateIn4', 'mateIn5'];

const C_ACCENT = '#00d4ff';
const C_PURPLE = '#7c3aed';
const C_BORDER = '#2a2a2a';
const C_TEXT   = '#888';

Chart.defaults.color = C_TEXT;
Chart.defaults.borderColor = C_BORDER;
Chart.defaults.font.family = 'Inter';

// Infer provider for models not in MODEL_META (e.g. a newly-run model) from the
// name, so the table/charts still color and label them correctly.
function modelProvider(key) {
  if (MODEL_META[key]) return MODEL_META[key].provider;
  return /claude/i.test(key) ? 'claude' : 'openai';
}

function modelColor(key) {
  return modelProvider(key) === 'claude' ? C_PURPLE : C_ACCENT;
}

function pct(v)  { return (v * 100).toFixed(1) + '%'; }
function ms(v)   { return v >= 1000 ? (v / 1000).toFixed(1) + 's' : Math.round(v) + 'ms'; }
function slug(k) { return k.replace(/\./g, '-'); }

// ── Fetch helpers ─────────────────────────────────────────────────────────────

// Manifest maps model -> list of available modes, e.g.
// { "claude-opus-4-8": ["regular","reasoning"], "o3": ["reasoning"] }.
// Tolerates the legacy flat-array form (every entry treated as regular).
async function fetchManifest() {
  try {
    const res = await fetch(S3_BASE + 'manifest.json');
    if (!res.ok) return {};
    const data = await res.json();
    if (Array.isArray(data)) {
      const obj = {};
      data.forEach(m => { obj[m] = ['regular']; });
      return obj;
    }
    return data;
  } catch {
    return {};
  }
}

function resultsFile(key, mode) {
  return mode === 'reasoning'
    ? `${key}_reasoning_results.json`
    : `${key}_results.json`;
}

async function fetchModel(key, mode) {
  try {
    const res = await fetch(`${S3_BASE}${resultsFile(key, mode)}`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

// ── Tab system ────────────────────────────────────────────────────────────────

function createTab(key, label, pending) {
  const btn = document.createElement('button');
  btn.className = 'tab-btn' + (pending ? ' pending' : '');
  btn.dataset.tab = slug(key);
  btn.textContent = label;
  btn.addEventListener('click', () => switchTab(slug(key)));
  document.getElementById('tabs-bar').appendChild(btn);
}

function createPanel(key) {
  const div = document.createElement('div');
  div.id = 'panel-' + slug(key);
  div.className = 'tab-panel';
  document.getElementById('panels').appendChild(div);
  return div;
}

function switchTab(tabKey) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  const btn = document.querySelector(`[data-tab="${tabKey}"]`);
  const panel = document.getElementById('panel-' + tabKey);
  if (btn) btn.classList.add('active');
  if (panel) panel.classList.add('active');
}

// ── Overview charts ───────────────────────────────────────────────────────────

function totalRunTime(data) {
  const ms = data.puzzles.reduce((sum, p) => sum + p.latency_ms, 0);
  const h  = Math.floor(ms / 3600000);
  const m  = Math.floor((ms % 3600000) / 60000);
  const s  = Math.floor((ms % 60000) / 1000);
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

function buildOverview(loadedModels) {
  const panel = document.getElementById('panel-overview');
  panel.innerHTML = `
    <details class="section card methodology">
      <summary>
        <span class="card-title" style="display:inline;cursor:pointer">Methodology</span>
        <span class="method-toggle">▸</span>
      </summary>
      <div class="method-body">

        <div class="method-section">
          <h3>Dataset</h3>
          <p>300 puzzles sampled from the <a href="https://database.lichess.org/#puzzles" target="_blank">Lichess open puzzle database</a> (~6M puzzles). Filtered for checkmate puzzles only, evenly distributed across <strong>5 mate types</strong> (mateIn1 to mateIn5) by <strong>4 difficulty tiers</strong> (15 puzzles each = 300 total).</p>
          <div class="method-grid">
            <div class="method-item"><span class="method-label">Beginner</span><span class="method-val">&lt; 1200 Elo</span></div>
            <div class="method-item"><span class="method-label">Intermediate</span><span class="method-val">1200 to 1600 Elo</span></div>
            <div class="method-item"><span class="method-label">Advanced</span><span class="method-val">1600 to 2000 Elo</span></div>
            <div class="method-item"><span class="method-label">Expert</span><span class="method-val">2000+ Elo</span></div>
          </div>
        </div>

        <div class="method-section">
          <h3>Puzzle Format</h3>
          <p>Each puzzle is presented as a FEN board position with the opponent's setup move already applied. The model must output the full mating sequence in <strong>UCI notation</strong> (e.g. <code>e2e4 d7d5 f1b5</code>), including both its own moves and the opponent's forced responses.</p>
        </div>

        <div class="method-section">
          <h3>Eval Metrics</h3>
          <div class="method-grid">
            <div class="method-item"><span class="method-label">Accuracy</span><span class="method-val">Exact match of full move sequence (binary)</span></div>
            <div class="method-item"><span class="method-label">Valid Ratio</span><span class="method-val">Share of predicted moves that are legal in the position (validated with python-chess)</span></div>
            <div class="method-item"><span class="method-label">Format Compliance</span><span class="method-val">Output was the right number of well-formed UCI moves, capturing both notation (e.g. e2e4, not Rxf8#) and sequence length</span></div>
            <div class="method-item"><span class="method-label">Latency</span><span class="method-val">Wall clock time of the API call</span></div>
          </div>
        </div>

        <div class="method-section">
          <h3>Composite Score Formula</h3>
          <div class="formula">
            score = 0.45 × correct + 0.35 × valid_ratio + 0.10 × (1 − norm_latency) + 0.10 × format_followed
          </div>
          <p style="margin-top:10px;font-size:12px;color:var(--text-muted)">Correctness is the dominant signal. Valid ratio gives partial credit for legal but incorrect sequences. Latency is normalized against a 30s cap. Format compliance rewards models that follow output instructions.</p>
        </div>

        <div class="method-section">
          <h3>Infrastructure</h3>
          <p>Each model runs in its own Docker container on <strong>AWS ECS Fargate</strong> in parallel. Results are written to S3 as JSON. API keys are stored in <strong>AWS Secrets Manager</strong> and injected at runtime. Infrastructure provisioned via <strong>Terraform</strong>.</p>
        </div>

      </div>
    </details>

    <div class="section card">
      <div class="card-title">Model Comparison</div>
      <div class="table-wrap">
        <table>
          <thead><tr>
            <th>Model</th><th>Accuracy</th><th>Avg Score</th>
            <th>Valid Ratio</th><th>Format Compliance</th><th>Avg Latency</th><th>Output Tokens</th><th>Total Run Time</th>
          </tr></thead>
          <tbody id="overview-tbody"></tbody>
        </table>
      </div>
    </div>
    <div class="section card">
      <div class="card-title">Accuracy by Model</div>
      <div class="card-desc">% of puzzles where the model found the exact correct mating sequence</div>
      <div class="chart-wrap"><canvas id="chart-accuracy"></canvas></div>
    </div>
    <div class="grid-2 section">
      <div class="card"><div class="card-title">Avg Score by Model</div><div class="card-desc">Weighted composite: 0.45× correct + 0.35× valid ratio + 0.10× latency + 0.10× format</div><div class="chart-wrap"><canvas id="chart-score"></canvas></div></div>
      <div class="card"><div class="card-title">Valid Move Rate</div><div class="card-desc">% of predicted moves that are actually legal in the position (checked with python-chess)</div><div class="chart-wrap"><canvas id="chart-valid"></canvas></div></div>
    </div>
    <div class="grid-2 section">
      <div class="card"><div class="card-title">Latency vs Accuracy</div><div class="card-desc">Speed vs correctness tradeoff — closer to top-left is better</div><div class="chart-wrap"><canvas id="chart-scatter"></canvas></div></div>
      <div class="card"><div class="card-title">Format Compliance Rate</div><div class="card-desc">% of puzzles where the model followed UCI output format instructions</div><div class="chart-wrap"><canvas id="chart-format"></canvas></div></div>
    </div>

    <div class="section card">
      <div class="card-title">Total Benchmark Run Time (300 puzzles)</div>
      <div class="card-desc">Total wall-clock API time to complete the full benchmark — sum of all 300 puzzle latencies</div>
      <div class="chart-wrap"><canvas id="chart-runtime"></canvas></div>
    </div>
  `;

  const tbody = document.getElementById('overview-tbody');

  // Only the models present in the current mode, sorted by accuracy. No "pending"
  // rows: under the mode toggle a model simply isn't shown in a mode it lacks.
  const tableKeys = Object.keys(loadedModels)
    .sort((a, b) => loadedModels[b].summary.overall_accuracy - loadedModels[a].summary.overall_accuracy);

  tableKeys.forEach(key => {
    const meta = MODEL_META[key] || { label: key, provider: modelProvider(key) };
    const data = loadedModels[key];
    const s = data?.summary;
    const badgeClass = meta.provider === 'claude' ? 'badge-claude' : 'badge-openai';
    const provider = meta.provider === 'claude' ? 'Anthropic' : 'OpenAI';

    tbody.innerHTML += `<tr class="${data ? '' : 'pending-row'}">
      <td><span class="model-name">${meta.label}</span><span class="badge ${data ? badgeClass : 'badge-pending'}">${data ? provider : 'Pending'}</span></td>
      <td>${s ? pct(s.overall_accuracy) : '—'}</td>
      <td>${s ? s.avg_score.toFixed(3) : '—'}</td>
      <td>${s ? pct(s.avg_valid_ratio) : '—'}</td>
      <td>${s ? pct(s.format_compliance_rate ?? 0) : '—'}</td>
      <td>${s ? ms(s.avg_latency_ms) : '—'}</td>
      <td>${s ? Math.round(s.avg_output_tokens) : '—'}</td>
      <td>${data ? totalRunTime(data) : '—'}</td>
    </tr>`;
  });

  // Sort by accuracy descending so bar order is stable across loads
  const active = Object.entries(loadedModels)
    .sort((a, b) => b[1].summary.overall_accuracy - a[1].summary.overall_accuracy);
  if (active.length === 0) return;

  const labels = active.map(([k]) => MODEL_META[k]?.label || k);
  const colors = active.map(([k]) => modelColor(k));

  new Chart(document.getElementById('chart-accuracy'), {
    type: 'bar',
    data: { labels, datasets: [{ label: 'Accuracy', data: active.map(([,d]) => +(d.summary.overall_accuracy * 100).toFixed(1)), backgroundColor: colors.map(c => c + '33'), borderColor: colors, borderWidth: 2, borderRadius: 4 }] },
    options: { responsive: true, plugins: { legend: { display: false } }, scales: { y: { ticks: { callback: v => v + '%' }, grid: { color: C_BORDER } }, x: { grid: { display: false } } } }
  });

  new Chart(document.getElementById('chart-score'), {
    type: 'bar',
    data: { labels, datasets: [{ label: 'Avg Score', data: active.map(([,d]) => +d.summary.avg_score.toFixed(3)), backgroundColor: colors.map(c => c + '33'), borderColor: colors, borderWidth: 2, borderRadius: 4 }] },
    options: { responsive: true, plugins: { legend: { display: false } }, scales: { y: { min: 0, max: 1, grid: { color: C_BORDER } }, x: { grid: { display: false } } } }
  });

  new Chart(document.getElementById('chart-scatter'), {
    type: 'scatter',
    data: {
      datasets: active.map(([k, d]) => ({
        label: MODEL_META[k]?.label || k,
        data: [{ x: +(d.summary.avg_latency_ms / 1000).toFixed(2), y: +(d.summary.overall_accuracy * 100).toFixed(1) }],
        backgroundColor: modelColor(k) + '99', borderColor: modelColor(k), pointRadius: 10, pointHoverRadius: 13,
      }))
    },
    options: {
      responsive: true,
      plugins: { legend: { position: 'bottom', labels: { boxWidth: 10, font: { size: 11 } } }, tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y}% @ ${ctx.parsed.x}s` } } },
      scales: { x: { title: { display: true, text: 'Avg Latency (s)', color: C_TEXT }, grid: { color: C_BORDER } }, y: { title: { display: true, text: 'Accuracy (%)', color: C_TEXT }, grid: { color: C_BORDER } } }
    }
  });

  new Chart(document.getElementById('chart-format'), {
    type: 'bar',
    data: { labels, datasets: [{ label: 'Format Compliance', data: active.map(([,d]) => +((d.summary.format_compliance_rate ?? 0) * 100).toFixed(1)), backgroundColor: colors.map(c => c + '33'), borderColor: colors, borderWidth: 2, borderRadius: 4 }] },
    options: { responsive: true, plugins: { legend: { display: false } }, scales: { y: { min: 0, max: 100, ticks: { callback: v => v + '%' }, grid: { color: C_BORDER } }, x: { grid: { display: false } } } }
  });

  new Chart(document.getElementById('chart-valid'), {
    type: 'bar',
    data: { labels, datasets: [{ label: 'Valid Move Rate', data: active.map(([,d]) => +((d.summary.avg_valid_ratio ?? 0) * 100).toFixed(1)), backgroundColor: colors.map(c => c + '33'), borderColor: colors, borderWidth: 2, borderRadius: 4 }] },
    options: { responsive: true, plugins: { legend: { display: false } }, scales: { y: { min: 0, max: 100, ticks: { callback: v => v + '%' }, grid: { color: C_BORDER } }, x: { grid: { display: false } } } }
  });

  // sort by total run time ascending
  const runtimeSorted = [...active].sort((a, b) =>
    a[1].puzzles.reduce((s, p) => s + p.latency_ms, 0) -
    b[1].puzzles.reduce((s, p) => s + p.latency_ms, 0)
  );

  new Chart(document.getElementById('chart-runtime'), {
    type: 'bar',
    data: {
      labels: runtimeSorted.map(([k]) => MODEL_META[k]?.label || k),
      datasets: [{
        label: 'Total Run Time (min)',
        data: runtimeSorted.map(([,d]) => +(d.puzzles.reduce((s, p) => s + p.latency_ms, 0) / 60000).toFixed(2)),
        backgroundColor: runtimeSorted.map(([k]) => modelColor(k) + '33'),
        borderColor: runtimeSorted.map(([k]) => modelColor(k)),
        borderWidth: 2,
        borderRadius: 4,
      }]
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        y: { ticks: { callback: v => v + 'm' }, grid: { color: C_BORDER } },
        x: { grid: { display: false } }
      }
    }
  });
}

// ── Per-model panel ───────────────────────────────────────────────────────────

function buildModelPanel(key, data) {
  const meta = MODEL_META[key] || { label: key, provider: modelProvider(key), tier: '' };
  const s = data.summary;
  const color = modelColor(key);
  const isClaude = modelProvider(key) === 'claude';
  const badgeStyle = isClaude
    ? 'background:rgba(124,58,237,0.15);color:#7c3aed'
    : 'background:rgba(0,212,255,0.15);color:#00d4ff';
  const provider = isClaude ? 'Anthropic' : 'OpenAI';
  const sk = slug(key);

  // Score distribution
  const buckets = Array(10).fill(0);
  data.puzzles.forEach(p => { buckets[Math.min(Math.floor(p.score * 10), 9)]++; });

  const panel = document.getElementById('panel-' + sk);
  panel.innerHTML = `
    <div class="model-header">
      <h2>${meta.label}</h2>
      <span style="${badgeStyle};border-radius:20px;padding:4px 12px;font-size:11px;font-weight:600;text-transform:uppercase">${provider} · ${meta.tier}</span>
    </div>
    <div class="stat-grid">
      <div class="stat-card"><div class="stat-label">Accuracy</div><div class="stat-value" style="color:${color}">${pct(s.overall_accuracy)}</div><div class="stat-sub">${Math.round(s.overall_accuracy * 300)} / 300 correct</div></div>
      <div class="stat-card"><div class="stat-label">Avg Score</div><div class="stat-value muted">${s.avg_score.toFixed(3)}</div><div class="stat-sub">weighted composite</div></div>
      <div class="stat-card"><div class="stat-label">Format Compliance</div><div class="stat-value" style="color:${color}">${pct(s.format_compliance_rate ?? 0)}</div><div class="stat-sub">followed UCI instructions</div></div>
      <div class="stat-card"><div class="stat-label">Valid Move Rate</div><div class="stat-value" style="color:${color}">${pct(s.avg_valid_ratio ?? 0)}</div><div class="stat-sub">predicted moves that are legal</div></div>
      <div class="stat-card"><div class="stat-label">Avg Latency</div><div class="stat-value muted">${ms(s.avg_latency_ms)}</div><div class="stat-sub">per puzzle</div></div>
    </div>
    ${meta.analysis ? `<details class="section card methodology" open>
      <summary>
        <span class="card-title" style="display:inline;cursor:pointer">Analysis</span>
        <span class="method-toggle">▸</span>
      </summary>
      <div class="method-body">${meta.analysis}</div>
    </details>` : ''}
    <div class="grid-2 section">
      <div class="card"><div class="card-title">Accuracy by Difficulty Tier</div><div class="card-desc">Does the model degrade on harder puzzles?</div><div class="chart-wrap"><canvas id="chart-${sk}-tier"></canvas></div></div>
      <div class="card"><div class="card-title">Accuracy by Mate Type</div><div class="card-desc">Does sequence length affect performance?</div><div class="chart-wrap"><canvas id="chart-${sk}-mate"></canvas></div></div>
    </div>
    <div class="section card"><div class="card-title">Score Distribution (300 puzzles)</div><div class="card-desc">Spread of composite scores across all puzzles — right-skewed = more correct answers</div><div class="chart-wrap"><canvas id="chart-${sk}-dist"></canvas></div></div>
  `;

  const barOpts = (horizontal) => ({
    type: 'bar',
    options: {
      indexAxis: horizontal ? 'y' : 'x',
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        [horizontal ? 'x' : 'y']: { ticks: { callback: v => v + '%' }, grid: { color: C_BORDER } },
        [horizontal ? 'y' : 'x']: { grid: { display: false } }
      }
    }
  });

  new Chart(document.getElementById(`chart-${sk}-tier`), {
    ...barOpts(true),
    data: { labels: TIERS.map(t => t.charAt(0).toUpperCase() + t.slice(1)), datasets: [{ label: 'Accuracy', data: TIERS.map(t => +((s.accuracy_by_tier[t] ?? 0) * 100).toFixed(1)), backgroundColor: color + '33', borderColor: color, borderWidth: 2, borderRadius: 4 }] }
  });

  new Chart(document.getElementById(`chart-${sk}-mate`), {
    ...barOpts(true),
    data: { labels: MATE_TYPES, datasets: [{ label: 'Accuracy', data: MATE_TYPES.map(t => +((s.accuracy_by_mate_type[t] ?? 0) * 100).toFixed(1)), backgroundColor: color + '33', borderColor: color, borderWidth: 2, borderRadius: 4 }] }
  });

  new Chart(document.getElementById(`chart-${sk}-dist`), {
    type: 'bar',
    data: { labels: ['0-.1','.1-.2','.2-.3','.3-.4','.4-.5','.5-.6','.6-.7','.7-.8','.8-.9','.9-1'], datasets: [{ label: 'Puzzles', data: buckets, backgroundColor: color + '44', borderColor: color, borderWidth: 1, borderRadius: 2 }] },
    options: { responsive: true, plugins: { legend: { display: false } }, scales: { y: { grid: { color: C_BORDER } }, x: { grid: { display: false }, ticks: { font: { size: 10 } } } } }
  });
}

function buildPendingPanel(key) {
  const meta = MODEL_META[key] || { label: key };
  const panel = document.getElementById('panel-' + slug(key));
  panel.innerHTML = `
    <div class="pending-card">
      <div style="font-size:32px">⏳</div>
      <p>${meta.label} hasn't completed its benchmark run yet.</p>
      <p style="margin-top:4px">Results will appear here automatically once uploaded to S3.</p>
    </div>
  `;
}

// ── Main ──────────────────────────────────────────────────────────────────────

const wait = ms => new Promise(r => setTimeout(r, ms));

async function dismissOverlay() {
  const overlay = document.getElementById('overlay');
  const stage = document.getElementById('overlay-stage');
  // Cross-fade the title into the icon, hold briefly, then fade the modal out.
  stage.classList.add('to-icon');
  await wait(650);
  overlay.classList.add('hidden');
  await wait(500);
  overlay.remove();
}

// Loaded results keyed by mode then model: LOADED.reasoning[key] / LOADED.regular[key].
const LOADED = { reasoning: {}, regular: {} };
let MANIFEST = {};
let currentMode = 'reasoning';

// Render the dashboard for one mode: rebuild tab bar, overview, and panels using
// only the models that have results in that mode.
function render(mode) {
  currentMode = mode;
  const loaded = LOADED[mode];
  const keys = Object.keys(loaded)
    .sort((a, b) => loaded[b].summary.overall_accuracy - loaded[a].summary.overall_accuracy);

  document.getElementById('tabs-bar').innerHTML = '';
  document.getElementById('panels').innerHTML = '';

  document.querySelectorAll('.mode-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.mode === mode);
  });

  const chip = document.getElementById('chip-models');
  if (chip) chip.innerHTML = `<strong>${keys.length}</strong> models`;

  createTab('overview', 'Overview', false);
  const overviewPanel = document.createElement('div');
  overviewPanel.id = 'panel-overview';
  overviewPanel.className = 'tab-panel';
  document.getElementById('panels').appendChild(overviewPanel);
  buildOverview(loaded);

  keys.forEach(key => {
    const meta = MODEL_META[key] || { label: key };
    createTab(key, meta.label || key, false);
    createPanel(key);
    buildModelPanel(key, loaded[key]);
  });

  switchTab('overview');
}

async function init() {
  // Show the title at least 500ms before the text->icon transition begins.
  const minTitleTime = wait(500);

  MANIFEST = await fetchManifest();

  // Fetch every (model, mode) result file the manifest advertises.
  const jobs = [];
  for (const [key, modes] of Object.entries(MANIFEST)) {
    for (const mode of modes) {
      jobs.push((async () => {
        const data = await fetchModel(key, mode);
        if (data) LOADED[mode][key] = data;
      })());
    }
  }
  await Promise.all(jobs);

  // Default to whichever mode has data (prefer reasoning).
  if (Object.keys(LOADED.reasoning).length === 0 && Object.keys(LOADED.regular).length > 0) {
    currentMode = 'regular';
  }

  await minTitleTime;
  await dismissOverlay();

  document.querySelectorAll('.mode-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      if (btn.dataset.mode !== currentMode) render(btn.dataset.mode);
    });
  });

  render(currentMode);
}

document.addEventListener('DOMContentLoaded', init);
