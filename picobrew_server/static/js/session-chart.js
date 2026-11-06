// Temperature chart for one brew session: step bands, reset markers, a crosshair
// tooltip and live updates while the machine is still brewing. No dependencies,
// so the page works on a server without internet access.

const SVG_NS = 'http://www.w3.org/2000/svg';
const GAP_MS = 5 * 60 * 1000; // break the line where the machine stopped reporting
const STORAGE_KEY = 'picobrew.sessionChart.hidden';

const container = document.getElementById('session-chart');
const legend = document.getElementById('chart-legend');
const initial = JSON.parse(document.getElementById('session-data').textContent);

const state = {
  session: initial.session,
  steps: initial.steps,
  errors: initial.errors,
  sensors: initial.sensors,
  unit: initial.unit,
  lastId: initial.last_id,
  t: [],
  stepId: [],
  values: Object.fromEntries(initial.sensors.map(s => [s.key, []])),
  hidden: loadHidden(),
  hoverIndex: null,
};
appendReadings(initial.readings);

const timeFormat = new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' });
const numberFormat = new Intl.NumberFormat(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 });

function loadHidden() {
  try {
    return new Set(JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]'));
  } catch {
    return new Set();
  }
}

function saveHidden() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...state.hidden]));
  } catch {
    // Storage may be unavailable (private mode); the toggle still works for this page.
  }
}

function appendReadings(readings) {
  state.t.push(...readings.t);
  state.stepId.push(...readings.step_id);
  for (const sensor of state.sensors) state.values[sensor.key].push(...readings[sensor.key]);
}

function el(name, attributes = {}, parent = null) {
  const node = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
  if (parent) parent.append(node);
  return node;
}

function formatTemperature(value) {
  return value == null ? '—' : `${numberFormat.format(value)}${state.unit}`;
}

function formatElapsed(ms) {
  const minutes = Math.max(0, Math.round(ms / 60000));
  return `${Math.floor(minutes / 60)}:${String(minutes % 60).padStart(2, '0')}`;
}

function niceStep(span, target) {
  const raw = span / Math.max(target, 1);
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  return [1, 2, 5, 10].map(m => m * magnitude).find(step => step >= raw) ?? 10 * magnitude;
}

function stepName(id) {
  return state.steps.find(step => step.id === id)?.name ?? '';
}

function visibleSensors() {
  return state.sensors.filter((sensor, index) => !state.hidden.has(sensor.key) && index < 8);
}

// -------- Legend --------
function renderLegend() {
  legend.replaceChildren();
  state.sensors.forEach((sensor, index) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'legend-item';
    button.style.setProperty('--series-color', `var(--series-${index + 1})`);
    button.setAttribute('aria-pressed', String(!state.hidden.has(sensor.key)));
    const key = document.createElement('span');
    key.className = 'legend-key';
    key.setAttribute('aria-hidden', 'true');
    const label = document.createElement('span');
    label.textContent = sensor.label;
    button.append(key, label);
    button.title = `Sensor ${sensor.index}`;
    button.addEventListener('click', () => {
      if (state.hidden.has(sensor.key)) state.hidden.delete(sensor.key);
      else if (visibleSensors().length > 1) state.hidden.add(sensor.key);
      saveHidden();
      renderLegend();
      render();
    });
    legend.append(button);
  });
}

// -------- Chart --------
let tooltip;
let crosshair;
let scales;

function render() {
  container.replaceChildren();
  tooltip = null;
  if (state.t.length === 0) {
    const empty = document.createElement('p');
    empty.className = 'chart-empty';
    empty.textContent =
      state.session.status === 'in_progress'
        ? 'Waiting for the first temperature reading…'
        : 'This session has no temperature readings.';
    container.append(empty);
    return;
  }

  const width = Math.max(container.clientWidth, 280);
  const narrow = width < 560;
  const height = narrow ? 280 : 380;
  const margin = { top: 30, right: narrow ? 14 : 104, bottom: 32, left: 46 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const sensors = visibleSensors();

  const start = Math.min(state.session.started_at ?? state.t[0], state.t[0]);
  const end = Math.max(state.t.at(-1), start + 60000);
  let min = Infinity;
  let max = -Infinity;
  for (const sensor of sensors) {
    for (const value of state.values[sensor.key]) {
      if (value == null) continue;
      min = Math.min(min, value);
      max = Math.max(max, value);
    }
  }
  if (!Number.isFinite(min)) [min, max] = [0, 100];
  const yStep = niceStep(Math.max(max - min, 5), narrow ? 4 : 6);
  const yMin = Math.floor(min / yStep) * yStep;
  const yMax = Math.max(Math.ceil(max / yStep) * yStep, yMin + yStep);
  const x = t => margin.left + ((t - start) / (end - start)) * plotWidth;
  const y = v => margin.top + (1 - (v - yMin) / (yMax - yMin)) * plotHeight;
  scales = { x, y, start, end, margin, plotWidth, plotHeight, width, height };

  const svg = el('svg', {
    viewBox: `0 0 ${width} ${height}`,
    width,
    height,
    role: 'img',
    'aria-label': describeChart(sensors, start, end),
  });

  // Step bands sit behind everything and alternate a faint wash.
  const bands = el('g', { class: 'chart-bands' }, svg);
  state.steps.forEach((step, index) => {
    const next = state.steps[index + 1];
    const x0 = x(Math.max(step.started_at, start));
    const x1 = x(Math.min(next ? next.started_at : end, end));
    if (x1 - x0 < 0.5) return;
    if (index % 2 === 1) el('rect', { x: x0, y: margin.top, width: x1 - x0, height: plotHeight, class: 'chart-band' }, bands);
    if (index > 0) el('line', { x1: x0, x2: x0, y1: margin.top - 22, y2: margin.top + plotHeight, class: 'chart-step-line' }, bands);
    const room = Math.floor((x1 - x0 - 8) / 6.5);
    if (room >= 3) {
      const name = step.name || 'Step';
      const label = el('text', { x: x0 + 4, y: margin.top - 10, class: 'chart-step-label' }, bands);
      label.textContent = name.length > room ? `${name.slice(0, room - 1)}…` : name;
    }
  });

  // Recessive grid and axes.
  const grid = el('g', { class: 'chart-grid' }, svg);
  for (let value = yMin; value <= yMax + 1e-9; value += yStep) {
    el('line', { x1: margin.left, x2: margin.left + plotWidth, y1: y(value), y2: y(value) }, grid);
    const label = el('text', { x: margin.left - 8, y: y(value) + 4, class: 'chart-axis-label', 'text-anchor': 'end' }, grid);
    label.textContent = `${Math.round(value * 10) / 10}°`;
  }
  const minuteOptions = [1, 2, 5, 10, 15, 30, 60, 90, 120, 180, 240, 360];
  const span = (end - start) / 60000;
  const tickMinutes = minuteOptions.find(m => span / m <= plotWidth / 70) ?? 720;
  for (let minutes = 0; minutes * 60000 <= end - start; minutes += tickMinutes) {
    const tx = x(start + minutes * 60000);
    const label = el('text', { x: tx, y: height - 10, class: 'chart-axis-label', 'text-anchor': 'middle' }, grid);
    label.textContent = minutes === 0 ? '0:00 h' : formatElapsed(minutes * 60000);
  }
  el('line', { x1: margin.left, x2: margin.left + plotWidth, y1: margin.top + plotHeight, y2: margin.top + plotHeight, class: 'chart-baseline' }, grid);

  // Reset reports, drawn as critical markers across the plot.
  for (const error of state.errors) {
    if (error.reported_at < start || error.reported_at > end) continue;
    const ex = x(error.reported_at);
    const marker = el('g', { class: 'chart-error' }, svg);
    el('line', { x1: ex, x2: ex, y1: margin.top, y2: margin.top + plotHeight }, marker);
    el('path', { d: `M${ex - 5},${margin.top} h10 l-5,7 z` }, marker);
    el('title', {}, marker).textContent = `${error.label} at ${timeFormat.format(error.reported_at)}`;
  }

  // One 2px line per sensor, split where readings stop for a while.
  const lines = el('g', { class: 'chart-lines' }, svg);
  for (const sensor of sensors) {
    const values = state.values[sensor.key];
    let d = '';
    let previous = null;
    for (let i = 0; i < state.t.length; i++) {
      const value = values[i];
      if (value == null) {
        previous = null;
        continue;
      }
      const command = previous === null || state.t[i] - state.t[previous] > GAP_MS ? 'M' : 'L';
      d += `${command}${x(state.t[i]).toFixed(1)},${y(value).toFixed(1)}`;
      previous = i;
    }
    el('path', { d, class: 'chart-line', stroke: `var(--series-${state.sensors.indexOf(sensor) + 1})` }, lines);
  }

  if (!narrow) renderDirectLabels(svg, sensors);

  crosshair = el('g', { class: 'chart-crosshair', visibility: 'hidden' }, svg);
  el('line', { y1: margin.top, y2: margin.top + plotHeight }, crosshair);
  for (const sensor of sensors) {
    el('circle', { r: 4, 'data-key': sensor.key, fill: `var(--series-${state.sensors.indexOf(sensor) + 1})` }, crosshair);
  }

  const overlay = el('rect', { x: margin.left, y: 0, width: plotWidth, height, class: 'chart-overlay' }, svg);
  overlay.addEventListener('pointermove', event => {
    const bounds = svg.getBoundingClientRect();
    const time = start + ((event.clientX - bounds.left - margin.left) / plotWidth) * (end - start);
    showIndex(nearestIndex(time));
  });
  overlay.addEventListener('pointerleave', () => showIndex(null));

  container.append(svg);
  tooltip = document.createElement('div');
  tooltip.className = 'chart-tooltip';
  tooltip.hidden = true;
  container.append(tooltip);
  if (state.hoverIndex != null) showIndex(Math.min(state.hoverIndex, state.t.length - 1));
}

function renderDirectLabels(svg, sensors) {
  const last = state.t.length - 1;
  const labels = sensors
    .map(sensor => {
      const values = state.values[sensor.key];
      let i = last;
      while (i >= 0 && values[i] == null) i--;
      return i < 0 ? null : { sensor, value: values[i], y: scales.y(values[i]) };
    })
    .filter(Boolean)
    .sort((a, b) => a.y - b.y);
  // Nudge labels apart so close temperatures stay readable.
  for (let i = 1; i < labels.length; i++) labels[i].y = Math.max(labels[i].y, labels[i - 1].y + 15);
  const overflow = labels.length ? labels.at(-1).y - (scales.margin.top + scales.plotHeight) : 0;
  if (overflow > 0) labels.forEach(label => (label.y -= overflow));
  const group = el('g', { class: 'chart-direct-labels' }, svg);
  const x0 = scales.margin.left + scales.plotWidth + 8;
  for (const label of labels) {
    el('line', { x1: x0, x2: x0 + 10, y1: label.y, y2: label.y, stroke: `var(--series-${state.sensors.indexOf(label.sensor) + 1})` }, group);
    const text = el('text', { x: x0 + 14, y: label.y + 4 }, group);
    text.textContent = label.sensor.label;
  }
}

function describeChart(sensors, start, end) {
  const wort = state.values[state.sensors[0].key].filter(v => v != null);
  const range = wort.length ? `, ${state.sensors[0].label} between ${formatTemperature(Math.min(...wort))} and ${formatTemperature(Math.max(...wort))}` : '';
  return `Temperatures of ${sensors.map(s => s.label).join(', ')} over ${formatElapsed(end - start)} hours, ${state.t.length} readings${range}.`;
}

function nearestIndex(time) {
  let low = 0;
  let high = state.t.length - 1;
  while (low < high) {
    const mid = (low + high) >> 1;
    if (state.t[mid] < time) low = mid + 1;
    else high = mid;
  }
  return low > 0 && time - state.t[low - 1] < state.t[low] - time ? low - 1 : low;
}

function showIndex(index) {
  state.hoverIndex = index;
  if (!tooltip || !crosshair) return;
  if (index == null) {
    crosshair.setAttribute('visibility', 'hidden');
    tooltip.hidden = true;
    return;
  }
  const { x, y, start, margin, plotWidth } = scales;
  const cx = x(state.t[index]);
  crosshair.setAttribute('visibility', 'visible');
  const line = crosshair.querySelector('line');
  line.setAttribute('x1', cx);
  line.setAttribute('x2', cx);
  for (const dot of crosshair.querySelectorAll('circle')) {
    const value = state.values[dot.dataset.key][index];
    dot.setAttribute('visibility', value == null ? 'hidden' : 'visible');
    if (value != null) {
      dot.setAttribute('cx', cx);
      dot.setAttribute('cy', y(value));
    }
  }

  tooltip.replaceChildren();
  const heading = document.createElement('p');
  heading.className = 'chart-tooltip-heading';
  heading.textContent = `${formatElapsed(state.t[index] - start)} h · ${timeFormat.format(state.t[index])}`;
  tooltip.append(heading);
  const step = stepName(state.stepId[index]);
  if (step) {
    const stepLine = document.createElement('p');
    stepLine.className = 'chart-tooltip-step';
    stepLine.textContent = step;
    tooltip.append(stepLine);
  }
  const list = document.createElement('dl');
  for (const sensor of visibleSensors()) {
    const row = document.createElement('div');
    row.style.setProperty('--series-color', `var(--series-${state.sensors.indexOf(sensor) + 1})`);
    const value = document.createElement('dd');
    value.textContent = formatTemperature(state.values[sensor.key][index]);
    const label = document.createElement('dt');
    label.textContent = sensor.label;
    row.append(value, label);
    list.append(row);
  }
  tooltip.append(list);
  tooltip.hidden = false;
  const left = cx + 14 + tooltip.offsetWidth > margin.left + plotWidth ? cx - 14 - tooltip.offsetWidth : cx + 14;
  tooltip.style.left = `${Math.max(0, left)}px`;
  tooltip.style.top = `${margin.top}px`;
}

container.tabIndex = 0;
container.addEventListener('keydown', event => {
  if (state.t.length === 0) return;
  const last = state.t.length - 1;
  const current = state.hoverIndex ?? last;
  const jump = event.shiftKey ? 10 : 1;
  const moves = {
    ArrowLeft: Math.max(0, current - jump),
    ArrowRight: Math.min(last, current + jump),
    Home: 0,
    End: last,
  };
  if (event.key in moves) {
    event.preventDefault();
    showIndex(moves[event.key]);
  } else if (event.key === 'Escape') {
    showIndex(null);
  }
});
container.addEventListener('focus', () => {
  if (state.hoverIndex == null && state.t.length) showIndex(state.t.length - 1);
});
container.addEventListener('blur', () => showIndex(null));

let renderedWidth = 0;
new ResizeObserver(() => {
  if (Math.abs(container.clientWidth - renderedWidth) < 2) return;
  renderedWidth = container.clientWidth;
  render();
}).observe(container);

// -------- Live updates --------
let pollTimer = null;

function schedulePoll(seconds) {
  clearTimeout(pollTimer);
  if (seconds && !document.hidden) pollTimer = setTimeout(poll, seconds * 1000);
}

async function poll() {
  let pollSeconds = initial.poll_seconds;
  try {
    const response = await fetch(`${location.pathname.replace(/\/$/, '')}/data.json?after=${state.lastId}`, {
      headers: { Accept: 'application/json' },
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const update = await response.json();
    appendReadings(update.readings);
    Object.assign(state, { session: update.session, steps: update.steps, errors: update.errors, lastId: update.last_id });
    // Fragments are rendered by the same server-side templates as the initial page.
    document.getElementById('session-summary').innerHTML = update.html.summary;
    document.getElementById('session-steps').innerHTML = update.html.steps;
    document.getElementById('session-errors').innerHTML = update.html.errors;
    document.getElementById('session-status').innerHTML = update.html.status;
    render();
    pollSeconds = update.poll_seconds;
  } catch (error) {
    console.warn('Could not refresh the brew session', error);
  }
  initial.poll_seconds = pollSeconds;
  schedulePoll(pollSeconds);
}

document.addEventListener('visibilitychange', () => {
  if (document.hidden) clearTimeout(pollTimer);
  else if (initial.poll_seconds) poll();
});

renderLegend();
schedulePoll(initial.poll_seconds);
