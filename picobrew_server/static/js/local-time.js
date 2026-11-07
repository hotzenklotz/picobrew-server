// Show server-rendered timestamps in the browser's time zone, the same clock the
// session chart uses. The server's text stays as the fallback without JavaScript.

const FORMATS = {
  datetime: { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' },
  time: { hour: '2-digit', minute: '2-digit' },
  'time-seconds': { hour: '2-digit', minute: '2-digit', second: '2-digit' },
};
const formatters = Object.fromEntries(
  Object.entries(FORMATS).map(([name, options]) => [name, new Intl.DateTimeFormat(undefined, options)]),
);

export function localizeTimes(root = document) {
  for (const node of root.querySelectorAll('time[data-format][datetime]')) {
    const formatter = formatters[node.dataset.format];
    const moment = new Date(node.getAttribute('datetime'));
    if (formatter && !Number.isNaN(moment.getTime())) node.textContent = formatter.format(moment);
  }
}

localizeTimes();
