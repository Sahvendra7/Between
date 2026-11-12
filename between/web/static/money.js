// Money & Time: the family's year in AG Studio, from the server's authorised ledger feed.
// Every amount here was decided by Between's rules engine or read back from PayPal; this file computes nothing.
const studioEl = document.getElementById('studio');
const main = document.querySelector('main');
const feed = await (await fetch(studioEl.dataset.src, { credentials: 'same-origin' })).json();
const S = window.agStudio;
const name = (role) => (role ? feed.names[role] ?? role : '');

const f = (id, label, format = 'textFormat', extra = {}) => ({ id, name: label, format, ...extra });
const hidden = (id) => ({ id, name: id, format: 'textFormat', hide: true });

function dataModel() {
  const sources = [
    {
      id: 'expenses', description: 'One row per shared child expense. Amounts are what the paying parent spent.',
      data: feed.expenses,
      fields: [hidden('id'), f('date', 'Date', 'dateFormat'), f('categoryName', 'Category'), f('paidByName', 'Paid by'),
        f('amount', 'Amount', 'currencyFormat'), f('label', 'Status'), f('status', 'Outcome'), hidden('href')],
    },
    {
      id: 'windows',
      description: 'Pay windows: what one parent owes the other for an expense, from the request date to the due date, ' +
        'decided by Between\'s rules engine under the approved agreement. state: open, overdue, verified (PayPal ' +
        'confirmed the payment) or outside (synthetic history settled outside Between, never verified by PayPal).',
      data: feed.obligations.filter((o) => o.kind === 'pay-window').map((o) => ({
        ...o, owedByName: name(o.owedBy), owedToName: name(o.owedTo),
        openAmount: ['open', 'overdue'].includes(o.state) ? o.amount : 0 })),
      fields: [hidden('id'), hidden('expenseId'), f('start', 'Asked on', 'dateFormat'), f('end', 'Due', 'dateFormat'),
        f('owedByName', 'Owed by'), f('owedToName', 'Owed to'), f('amount', 'Owed', 'currencyFormat'),
        f('openAmount', 'Still open', 'currencyFormat'), f('state', 'State'), f('clause', 'Clause')],
    },
    {
      id: 'consents', description: 'Activity spending one parent asked the other to agree to in advance.',
      data: feed.obligations.filter((o) => o.kind === 'consent'),
      fields: [hidden('id'), f('start', 'Date', 'dateFormat'), f('category', 'Category'),
        f('amount', 'Up to', 'currencyFormat'), f('state', 'State')],
    },
    {
      id: 'payments',
      description: 'Payments between the parents. settled = verified means PayPal confirmed it; outside means synthetic ' +
        'history settled outside Between and never verified by PayPal.',
      data: feed.payments.map((p) => ({ ...p, payerName: name(p.payer), payeeName: name(p.payee),
        verifiedAmount: p.settled === 'verified' ? p.amount : 0, outsideAmount: p.settled === 'outside' ? p.amount : 0 })),
      fields: [hidden('id'), hidden('expenseId'), f('kind', 'Kind'), f('payerName', 'From'), f('payeeName', 'To'),
        f('amount', 'Paid', 'currencyFormat'), f('verifiedAmount', 'Verified with PayPal', 'currencyFormat'),
        f('outsideAmount', 'Settled outside Between', 'currencyFormat'), f('settled', 'Settled'),
        f('paypalStatus', 'PayPal status'), f('fee', 'PayPal fee', 'currencyFormat')],
    },
    {
      id: 'clauses', description: 'The agreement clauses each decision cites, quoted word for word.',
      data: feed.clauses,
      fields: [hidden('expenseId'), f('section', 'Section'), f('page', 'Page'), f('quote', 'Quote'), hidden('href')],
    },
    {
      id: 'caps', description: 'Annual caps per parent from the agreement, and how much of each is used this year.',
      data: feed.caps,
      fields: [f('categoryName', 'Category'), f('partyName', 'Parent'), f('cap', 'Cap', 'currencyFormat'),
        f('used', 'Used', 'currencyFormat'), f('left', 'Left', 'currencyFormat'), f('clause', 'Clause')],
    },
  ];
  const rel = (table, field) => ({ id: `${table}-${field}`, type: 'many-to-one',
    source: { tableId: table, fieldId: field }, target: { tableId: 'expenses', fieldId: 'id' } });
  const relationships = [rel('windows', 'expenseId'), rel('payments', 'expenseId'), rel('clauses', 'expenseId')];
  const dates = [...feed.expenses.map((e) => e.date), ...feed.obligations.map((o) => o.end)].filter(Boolean).sort();
  const calendars = [];
  if (dates.length) {
    calendars.push({ id: 'calendar', label: 'Calendar', fragments: ['year', 'quarter', 'month', 'week', 'day'],
      range: { from: { type: 'date', value: dates[0] }, to: { type: 'date', value: dates.at(-1) } } });
    relationships.push({ id: 'expenses-date-calendar', source: { tableId: 'expenses', fieldId: 'date' }, target: { calendarId: 'calendar' } },
      { id: 'windows-end-calendar', source: { tableId: 'windows', fieldId: 'end' }, target: { calendarId: 'calendar' } });
  }
  return {
    description: `Shared child expenses of one separated family for ${feed.asOf.slice(0, 4)}, in USD. Between's rules ` +
      'engine decided every share and due date from the agreement both parents approved; PayPal confirmed verified payments.',
    sources, relationships, calendars,
  };
}

async function initialReport() {
  try {
    const r = await fetch('/static/money_report.json');
    return r.ok ? await r.json() : undefined;
  } catch {
    return undefined;
  }
}

if (S && feed.expenses.length) {
  if (studioEl.dataset.license) S.AgStudioLicenseManager.setLicenseKey(studioEl.dataset.license);
  // Literal values: charts draw on canvas and can't resolve CSS variables. A light report card in both colour schemes.
  const theme = S.studioTheme?.withParams({ fontFamily: '"Anek Latin", "Noto Sans", system-ui, sans-serif',
    accentColor: '#16505A' });
  // No filters are configured, so view mode drops the (empty) filters panel: on a phone it covered the report.
  const panels = { edit: { left: ['ai'], right: ['filters', 'edit', 'data'] }, view: { left: [], right: [] } };
  const api = S.createStudio(studioEl, { data: dataModel(), mode: 'view', initialState: await initialReport(), theme, panels });
  main.classList.add('has-studio');
  const toggle = document.getElementById('studio-mode');
  toggle.hidden = false;
  toggle.addEventListener('click', () => {
    const editing = api.getProperty('mode') === 'edit';
    api.setProperty('mode', editing ? 'view' : 'edit');
    toggle.textContent = editing ? 'Edit report' : 'Done';
  });
  window.betweenMoney = { studio: api, feed };
}
