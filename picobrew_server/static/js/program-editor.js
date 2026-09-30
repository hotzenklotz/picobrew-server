// Load explicitly: an empty program only has selects inside an inert template,
// which the Shoelace autoloader cannot discover until after a step is added.
import '../shoelace/components/select/select.js';
import '../shoelace/components/option/option.js';

const form = document.getElementById('program-editor');
const list = document.getElementById('editor-steps');
const template = document.getElementById('editor-step-template');
const save = document.getElementById('save-program');
const feedback = document.getElementById('editor-feedback');
const starters = JSON.parse(document.getElementById('program-templates-data').textContent);
const starterPicker = document.getElementById('program-template');
const replacement = document.getElementById('template-replace-confirmation');
const warningPanel = document.getElementById('program-warnings');
const warningList = document.getElementById('program-warning-list');
const checkStatus = document.getElementById('program-check-status');
let pendingStarter = null;
let checkTimer;
let checkController;
let checkVersion = 0;
let shownWarnings = '';
let dirty = false;
let submitting = false;

function readRows() {
  return [...list.children].map(row => Object.fromEntries(
    ['name', 'temp', 'time', 'location', 'drain'].map(field => [field,
      field === 'location' ? row.querySelector('[data-location]').value : row.querySelector(`[name="step_${field}"]`).value,
    ])
  ));
}
function renderWarnings(warnings) {
  const serialized = JSON.stringify(warnings);
  if (serialized !== shownWarnings) {
    shownWarnings = serialized;
    warningList.replaceChildren(...warnings.map(warning => {
      const item = document.createElement('li');
      item.textContent = `${warning.step ? `Step ${warning.step}: ` : ''}${warning.message}`;
      return item;
    }));
  }
  warningPanel.hidden = warnings.length === 0;
  [...list.children].forEach((row, index) => {
    row.classList.toggle('has-warning', warnings.some(warning => warning.step === index + 1));
  });
  checkStatus.textContent = warnings.length || !list.children.length ? '' : 'No sequence warnings detected.';
}
function queueChecks() {
  clearTimeout(checkTimer);
  checkController?.abort();
  const version = ++checkVersion;
  if (!list.children.length) { renderWarnings([]); return; }
  checkTimer = setTimeout(async () => {
    checkController = new AbortController();
    try {
      const response = await fetch(form.dataset.checkUrl, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({rows:readRows()}), signal:checkController.signal,
      });
      if (!response.ok) throw new Error('Could not check program');
      const result = await response.json();
      if (version === checkVersion) renderWarnings(result.warnings);
    } catch (error) {
      if (error.name !== 'AbortError' && version === checkVersion) {
        checkStatus.textContent = 'Sequence checks are unavailable. Review the steps before saving.';
      }
    }
  }, 250);
}
function previewStarter() {
  const starter = starters.find(item => item.id === starterPicker.value);
  if (!starter) return;
  pendingStarter = null;
  replacement.hidden = true;
  document.getElementById('template-description').textContent = starter.description;
  document.getElementById('template-notes').replaceChildren(...starter.notes.map(note => {
    const item = document.createElement('li'); item.textContent = note; return item;
  }));
  document.getElementById('template-unavailable').hidden = !starter.unavailable;
  document.getElementById('template-unavailable').textContent = starter.unavailable;
  document.getElementById('apply-template').disabled = Boolean(starter.unavailable);
}
function applyStarter(starter) {
  const rows = starter.rows.map(values => {
    const row = template.content.firstElementChild.cloneNode(true);
    for (const [field, value] of Object.entries(values)) row.querySelector(`[name="step_${field}"]`).value = value;
    row.querySelector('[data-location]').value = values.location;
    return row;
  });
  list.replaceChildren(...rows);
  dirty = true;
  pendingStarter = null;
  replacement.hidden = true;
  refreshSteps();
  document.getElementById('template-applied').textContent = `${starter.label} filled ${rows.length} editable steps. Review the draft before saving.`;
}
starterPicker.addEventListener('sl-change', previewStarter);
document.getElementById('apply-template').addEventListener('click', () => {
  const starter = starters.find(item => item.id === starterPicker.value);
  if (!starter || starter.unavailable) return;
  if (list.children.length) {
    pendingStarter = starter;
    document.getElementById('template-replace-message').textContent = `Replace all ${list.children.length} steps in this draft with “${starter.label}”? Your BeerXML file changes only when you save.`;
    replacement.hidden = false;
    document.getElementById('keep-draft').focus();
  } else applyStarter(starter);
});
document.getElementById('keep-draft').addEventListener('click', () => {
  pendingStarter = null; replacement.hidden = true; document.getElementById('apply-template').focus();
});
document.getElementById('replace-draft').addEventListener('click', () => {
  if (pendingStarter) applyStarter(pendingStarter);
});
function refreshSteps() {
  const rows = [...list.children];
  rows.forEach((row, index) => {
    row.querySelectorAll('[data-step-number]').forEach(number => { number.textContent = index + 1; });
    const up = row.querySelector('[data-move="up"]');
    const down = row.querySelector('[data-move="down"]');
    up.disabled = index === 0;
    down.disabled = index === rows.length - 1;
    up.setAttribute('aria-label', `Move step ${index + 1} up`);
    down.setAttribute('aria-label', `Move step ${index + 1} down`);
    row.querySelector('[data-remove]').setAttribute('aria-label', `Remove step ${index + 1}`);
  });
  document.getElementById('editor-step-count').textContent = `· ${rows.length}`;
  document.getElementById('editor-empty').hidden = rows.length !== 0;
  save.disabled = rows.length === 0;
  queueChecks();
}
document.getElementById('add-step').addEventListener('click', () => {
  const row = template.content.firstElementChild.cloneNode(true);
  list.append(row);
  dirty = true;
  refreshSteps();
  row.querySelector('input').focus();
  feedback.textContent = `Step ${list.children.length} added.`;
});
list.addEventListener('click', event => {
  const control = event.target.closest('[data-move], [data-remove]');
  if (!control) return;
  const row = control.closest('.editor-step');
  const index = [...list.children].indexOf(row);
  if (control.hasAttribute('data-remove')) {
    row.remove();
    refreshSteps();
    const next = list.children[Math.min(index, list.children.length - 1)];
    (next?.querySelector('input') || document.getElementById('add-step')).focus();
    feedback.textContent = `Step ${index + 1} removed.`;
  } else {
    if (control.dataset.move === 'up' && row.previousElementSibling) {
      list.insertBefore(row, row.previousElementSibling);
    } else if (control.dataset.move === 'down' && row.nextElementSibling) {
      list.insertBefore(row.nextElementSibling, row);
    }
    refreshSteps();
    row.querySelector('input').focus();
    feedback.textContent = `Step moved to position ${[...list.children].indexOf(row) + 1}.`;
  }
  dirty = true;
});
form.addEventListener('input', event => {
  if (event.target.closest('.editor-step')) { dirty = true; queueChecks(); }
});
form.addEventListener('sl-change', event => {
  const row = event.target.closest('.editor-step');
  if (row) {
    const hidden = row.querySelector('[name="step_location"]');
    const value = row.querySelector('[data-location]').value;
    if (hidden.value !== value) dirty = true;
    hidden.value = value;
    queueChecks();
  }
});
form.querySelector('.editor-footer a').addEventListener('click', event => {
  // Cancel explicitly discards unsaved edits. Let its back link navigate
  // without the beforeunload guard, which some embedded browsers suppress.
  if (event.button === 0 && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) {
    dirty = false;
  }
});
form.addEventListener('submit', event => {
  // A native submit event runs after HTML/Shoelace validation. Disable only
  // after it is accepted, so invalid fields never leave the button stuck.
  if (submitting) { event.preventDefault(); return; }
  // Native hidden inputs follow DOM order even when custom select controls
  // reconnect after a move. Keep each location paired with its own step.
  for (const row of list.children) {
    row.querySelector('[name="step_location"]').value = row.querySelector('[data-location]').value;
  }
  submitting = true;
  save.disabled = true;
  save.textContent = 'Saving…';
  form.setAttribute('aria-busy', 'true');
});
window.addEventListener('beforeunload', event => {
  if (dirty && !submitting) { event.preventDefault(); event.returnValue = ''; }
});
window.addEventListener('pageshow', () => {
  submitting = false;
  save.textContent = 'Save program';
  form.removeAttribute('aria-busy');
  refreshSteps();
});
refreshSteps();
previewStarter();
renderWarnings(JSON.parse(document.getElementById('program-warnings-data').textContent));
