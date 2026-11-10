// Read-only calendar of parenting time and expenses. Bryntum Calendar Community (MIT), vendored.
import { Calendar } from '/static/vendor/bryntum/calendar.bundle.js';

const el = document.getElementById('cal');
const data = await (await fetch(el.dataset.src, { credentials: 'same-origin' })).json();
const [y, m, d] = data.today.split('-').map(Number);
window.betweenCalendar = new Calendar({
  appendTo: el, readOnly: true, mode: 'month', date: new Date(y, m - 1, d),
  resources: data.resources,
  events: data.events.map(({ kind, ...e }) => ({ ...e, cls: `between-${kind}` })),
  modes: { day: null, year: null }
});
el.dataset.ready = 'yes';
