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
      fields: [f('id', 'Expense ID'), f('date', 'Date', 'dateFormat'), f('categoryName', 'Category'), f('paidByName', 'Paid by'),
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

// ---- Bryntum: parenting time, expenses and payment windows on one read-only calendar ----------------------
const { Calendar } = await import('/static/vendor/bryntum/calendar.bundle.js');
const calEl = document.getElementById('cal');
const [y, m, d] = feed.calendar.today.split('-').map(Number);
const calendar = new Calendar({
  appendTo: calEl, mode: 'month', date: new Date(y, m - 1, d), readOnly: true, autoCreate: false,
  features: { drag: false, eventEdit: false, eventMenu: false, scheduleMenu: false },
  modes: { day: null, year: null },
  resources: feed.calendar.resources,
  events: feed.calendar.events.map(({ kind, state, ...e }) => ({
    ...e, cls: kind === 'pay-window' ? `between-pay-${state}` : `between-${kind}` })),
  listeners: {
    eventClick({ eventRecord }) {
      const id = eventRecord.get('expenseId');
      if (id) window.betweenMoney?.filterExpense(id);
    },
  },
});

function show(date, eventId) {
  const [yy, mm, dd] = date.split('-').map(Number);
  calendar.date = new Date(yy, mm - 1, dd);
  const rec = eventId && calendar.eventStore.getById(eventId);
  if (rec) {
    const base = rec.cls?.toString() ?? '';
    rec.cls = `${base} between-focus`;
    setTimeout(() => { rec.cls = base; }, 4000);
  }
  calEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
}
window.addEventListener('hashchange', () => {
  const m2 = location.hash.match(/^#cal=(\d{4}-\d{2}-\d{2})$/);
  if (m2) show(m2[1]);
});

// ---- Ledger guide: an AG Studio custom agent whose tools only read what Between already decided ------------
const fid = studioEl.dataset.fid;
const usd = (cents) => (cents == null ? null : `$${(cents / 100).toFixed(2)}`);  // formatting only

// AG Studio's adapter contract, over our own server proxy (/money/ai → Gemini chat completions).
function geminiAdapter(csrf) {
  return {
    executeTurn(request, options = {}) {
      let resolve;
      const complete = new Promise((res) => { resolve = res; });
      async function* stream() {
        let data;
        try {
          const r = await fetch(`/f/${fid}/money/ai`, {
            method: 'POST', credentials: 'same-origin', signal: options.signal,
            headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
            body: JSON.stringify({ input: request.input, instructions: request.instructions, tools: request.tools,
              toolChoice: request.toolChoice, responseFormat: request.responseFormat }),
          });
          data = await r.json();
        } catch {
          data = { status: 'failed', error: { message: "The guide couldn't be reached. The calendar and report still work." } };
        }
        if (data.status === 'failed') {  // show the reason in the chat rather than a silent failure
          data = { id: `r${Date.now()}`, createdAt: Date.now(), status: 'completed', output: [{ kind: 'output',
            type: 'message', role: 'assistant', id: `m${Date.now()}`, status: 'completed',
            content: [{ type: 'text', text: data.error?.message ?? 'The guide could not answer.', annotations: [] }] }] };
        }
        for (const item of data.output) {
          if (item.type === 'message') {
            const text = item.content.map((p) => p.text ?? '').join('');
            yield { type: 'TEXT_MESSAGE_START', messageId: item.id, role: 'assistant' };
            for (let i = 0; i < text.length; i += 40) yield { type: 'TEXT_MESSAGE_CONTENT', messageId: item.id, delta: text.slice(i, i + 40) };
            yield { type: 'TEXT_MESSAGE_END', messageId: item.id };
          } else if (item.type === 'function_call') {
            yield { type: 'TOOL_CALL_START', toolCallId: item.callId, toolCallName: item.name };
            yield { type: 'TOOL_CALL_ARGS', toolCallId: item.callId, delta: item.arguments };
            yield { type: 'TOOL_CALL_END', toolCallId: item.callId };
          }
        }
        resolve(data);  // complete resolves only once the stream is drained, as AG Studio expects
      }
      return { stream: stream(), complete };
    },
  };
}

const INSTRUCTIONS = "You help two parents read their own Between ledger. Every amount, share, due date and outcome " +
  "comes from Between's rules engine: get it with explain_expense or preview_expense, or from the ledger rows. Never " +
  "calculate or estimate an amount yourself. For every 'why', quote the clause and give its section and page. Say " +
  "'verified with PayPal' only when the payment's settled value is 'verified'. You cannot pay, approve, agree to " +
  "anything or change rules; tell the parent which Between page does that: asking for or giving consent in advance is " +
  "on the Home page, paying is on the expense's own page, rules are on the Rules page. When a date matters, call show_on_calendar. " +
  `The parents are ${feed.names.A} and ${feed.names.B}. Expense IDs are in the expenses table (Expense ID). ` +
  `Today is ${feed.asOf}.`;

function ledgerGuide(csrf) {
  const parents = [feed.names.A, feed.names.B];
  const role = (n) => (n === feed.names.B ? 'B' : 'A');
  return ({ api }) => S.createAiHarness(api, ({ tools: { studio } }) => {
    const explain = api.defineAiTool({
      name: 'explain_expense',
      description: "Between's stored decision for one expense: outcome, who owes whom, how much, the due date, the " +
        'PayPal state and the agreement clauses it cites, quoted word for word.',
      params: (s) => s.object({ expenseId: s.string({ description: 'Expense ID from the expenses table' }) }),
      execute: async ({ expenseId }, ctx) => {
        const r = await fetch(`/f/${fid}/money/expense/${encodeURIComponent(expenseId)}.json`, { signal: ctx.signal });
        if (!r.ok) return ctx.error('There is no expense with that ID in this family.');
        const d = await r.json();
        const who = d.owedBy ? `${d.names[d.owedBy]} owes ${d.names[d.owedTo]} ${usd(d.amountMinor)}` : 'Nothing is owed';
        return ctx.success(`${d.status}${d.reason ? ` (${d.reason})` : ''}. ${who}${d.dueOn ? `, due ${d.dueOn}` : ''}. ` +
          `Payment: ${d.payment.settled}. Clauses: ${d.cite.map((c) => `§${c.section} p.${c.page} "${c.quote}"`).join('; ')}`, d);
      },
    });
    const preview = api.defineAiTool({
      name: 'preview_expense',
      description: "What Between's rules engine would decide for a hypothetical expense, without saving anything: " +
        'outcome, who would owe whom and how much, the due date, and the clauses. Use it for any "what if" question.',
      params: (s) => s.object({
        category: s.enum(['medical', 'education', 'extracurricular', 'clothing', 'gifts', 'food']),
        amount: s.number({ description: 'Amount in US dollars, e.g. 450' }),
        date: s.string({ description: 'Date the cost is incurred, YYYY-MM-DD' }),
        paidBy: s.enum(parents),
      }),
      execute: async ({ category, amount, date, paidBy }, ctx) => {
        const csrfToken = csrf;
        const r = await fetch(`/f/${fid}/money/preview`, {
          method: 'POST', signal: ctx.signal, headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
          body: JSON.stringify({ category, amountMinor: Math.round(amount * 100), incurredOn: date, paidBy: role(paidBy) }),
        });
        if (!r.ok) return ctx.error('Between could not preview that: check the category, amount and date.');
        const d = await r.json();
        const who = d.owedBy ? `${feed.names[d.owedBy]} would owe ${feed.names[d.owedTo]} ${usd(d.amountMinor)}` : 'Nobody would owe anything yet';
        return ctx.success(`Engine outcome: ${d.status}${d.reason ? ` (${d.reason})` : ''}. ${who}` +
          `${d.dueOn ? `, due ${d.dueOn}` : ''}. Clauses: ${d.cite.map((c) => `§${c.section} p.${c.page} "${c.quote}"`).join('; ')}`, d);
      },
    });
    const showTool = api.defineAiTool({
      name: 'show_on_calendar',
      description: 'Move the parenting-time calendar on this page to a date, optionally highlighting one expense.',
      params: (s) => s.object({ date: s.string({ description: 'YYYY-MM-DD' }),
        expenseId: s.string({ description: 'Expense ID to highlight' }).optional() }),
      execute: async ({ date, expenseId }, ctx) => {
        if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return ctx.error('Use a YYYY-MM-DD date.');
        show(date, expenseId ? `e${expenseId}` : undefined);
        return ctx.success(`The calendar now shows ${date}.`);
      },
    });
    const builtIn = ['viewSchema', 'viewPage', 'executeQuery', 'addWidget'].filter((n) => typeof studio[n] === 'function').map((n) => studio[n]());
    const open = feed.obligations.find((o) => o.kind === 'pay-window' && ['open', 'overdue'].includes(o.state));
    return {
      agents: [S.directLlmRunner({ id: 'ledger-guide', adapter: geminiAdapter(csrf), instructions: () => INSTRUCTIONS,
        tools: () => [...builtIn, explain, preview, showTool] })],
      primary: 'ledger-guide',
      promptStarters: [
        ...(open ? [{ label: `Why ${usd(open.amountMinor)}?`, prompt: `Why does ${feed.names[open.owedBy]} owe ${usd(open.amountMinor)}, and by when?` }] : []),
        { label: 'What if…', prompt: `If ${feed.names.A} pays $450 for soccer camp on 14 December, what happens under our agreement?` },
        { label: "What's open?", prompt: "What's still open between us, and when is it due?" },
      ],
    };
  });
}

// ---- AG Studio: the year as a report ---------------------------------------------------------------------
if (S && feed.expenses.length) {
  if (studioEl.dataset.license) S.AgStudioLicenseManager.setLicenseKey(studioEl.dataset.license);
  // Literal values: charts draw on canvas and can't resolve CSS variables. A light report card in both colour schemes.
  const theme = S.studioTheme?.withParams({ fontFamily: '"Anek Latin", "Noto Sans", system-ui, sans-serif',
    accentColor: '#16505A' });
  // No filters are configured, so view mode drops the (empty) filters panel: on a phone it covered the report.
  const ai = studioEl.dataset.ai === '1';
  const panels = { edit: { left: ['ai'], right: ['filters', 'edit', 'data'] }, view: { left: ai ? ['ai'] : [], right: [] } };
  const props = { data: dataModel(), mode: 'view', initialState: await initialReport(), theme, panels };
  if (ai) props.ai = ledgerGuide(document.getElementById('csrf').value);
  const api = ai ? S.createStudioWithAi(studioEl, props) : S.createStudio(studioEl, props);
  main.classList.add('has-studio');
  const toggle = document.getElementById('studio-mode');
  toggle.hidden = false;
  toggle.addEventListener('click', () => {
    const editing = api.getProperty('mode') === 'edit';
    api.setProperty('mode', editing ? 'view' : 'edit');
    toggle.textContent = editing ? 'Edit report' : 'Done';
  });
  const clear = document.getElementById('studio-clear');
  // Calendar → report: focus every widget on one expense (and its windows, payments and clauses).
  function filterExpense(expenseId) {
    const st = api.getState();
    const page = expenseId ? [{ field: { id: 'expenses.id' }, model: { operator: 'isIn', value: [expenseId] } }] : [];
    api.setState({ ...st, pages: st.pages.map((p) => (p.id === st.selectedPageId ? { ...p, filter: { ...p.filter, page } } : p)) });
    clear.hidden = !expenseId;
    if (expenseId) studioEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
  clear.addEventListener('click', () => filterExpense(null));
  window.betweenMoney = { studio: api, calendar, feed, show, filterExpense };
} else {
  window.betweenMoney = { calendar, feed, show, filterExpense() {} };
}
