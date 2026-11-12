// Parenting time, expenses and swap requests. Bryntum Calendar Community (MIT), vendored.
// Dragging across days only *asks*: it fills the server-rendered swap form, the parent confirms, and the
// server decides; nothing on the calendar itself is editable.
import { Calendar } from '/static/vendor/bryntum/calendar.bundle.js';

const el = document.getElementById('cal');
const form = document.getElementById('swap-form');
const data = await (await fetch(el.dataset.src, { credentials: 'same-origin' })).json();
const [y, m, d] = data.today.split('-').map(Number);
const iso = (dt) => `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, '0')}-${String(dt.getDate()).padStart(2, '0')}`;
const canSwap = Boolean(el.dataset.swaps && form);

window.betweenCalendar = new Calendar({
  appendTo: el, mode: 'month', date: new Date(y, m - 1, d),
  readOnly: !canSwap, autoCreate: false,
  features: { drag: { creatable: canSwap, draggable: false, resizable: false }, eventEdit: false, eventMenu: false, scheduleMenu: false },
  resources: data.resources,
  events: data.events.map(({ kind, ...e }) => ({ ...e, cls: `between-${kind}` })),
  modes: { day: null, year: null },
  listeners: {
    dragCreateEnd({ eventRecord }) {
      const start = new Date(eventRecord.startDate);
      const end = new Date(eventRecord.endDate);
      if (end.getHours() || end.getMinutes()) end.setDate(end.getDate() + 1);  // whole days only
      const last = new Date(end); last.setDate(last.getDate() - 1);
      if (window.confirm(`Ask ${el.dataset.other} for ${iso(start)} to ${iso(last)}? They can agree or decline.`)) {
        form.elements.start.value = iso(start);
        form.elements.end.value = iso(end);
        form.requestSubmit();
      }
      return false;  // the drawn block is only a proposal; the calendar reloads from the server
    }
  }
});
el.dataset.ready = 'yes';
