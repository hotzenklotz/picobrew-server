await Promise.all(['sl-select', 'sl-option'].map(name => customElements.whenDefined(name)));

const grid = document.getElementById('recipe-grid');
const cards = [...grid.querySelectorAll('.recipe-card')];
const search = document.getElementById('recipe-search');
const status = document.getElementById('recipe-status');
const sort = document.getElementById('recipe-sort');
const results = document.getElementById('recipe-results');
const empty = document.getElementById('no-results');
const collator = new Intl.Collator(undefined, { sensitivity: 'base', numeric: true });

/** Apply search, availability and sort controls, then update the visible recipe count. */
function updateLibrary() {
  const terms = search.value.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  cards.sort((a, b) => {
    const byName = collator.compare(a.dataset.name, b.dataset.name);
    if (sort.value === 'abv') {
      const abvA = Number.parseFloat(a.dataset.abv);
      const abvB = Number.parseFloat(b.dataset.abv);
      return (Number.isFinite(abvB) ? abvB : -Infinity) - (Number.isFinite(abvA) ? abvA : -Infinity) || byName;
    }
    return sort.value === 'name-desc' ? -byName : byName;
  });
  let visible = 0;
  for (const card of cards) {
    const matchesText = terms.every(term => card.dataset.search.toLocaleLowerCase().includes(term));
    card.hidden = !matchesText || (status.value !== 'all' && card.dataset.status !== status.value);
    if (!card.hidden) visible++;
    grid.append(card);
  }
  results.textContent = `Showing ${visible} of ${cards.length} recipe${cards.length === 1 ? '' : 's'}`;
  empty.hidden = visible !== 0;
  grid.hidden = visible === 0;
}
search.addEventListener('input', updateLibrary);
status.addEventListener('sl-change', updateLibrary);
sort.addEventListener('sl-change', updateLibrary);
document.getElementById('clear-filters').addEventListener('click', () => {
  search.value = '';
  status.value = 'all';
  updateLibrary();
  search.focus();
});
for (const button of document.querySelectorAll('[data-open-recipe]')) {
  button.addEventListener('click', async () => {
    await Promise.all(['sl-dialog', 'sl-tab-group', 'sl-tab', 'sl-tab-panel'].map(name => customElements.whenDefined(name)));
    document.getElementById(button.dataset.openRecipe).show();
  });
}
updateLibrary();
