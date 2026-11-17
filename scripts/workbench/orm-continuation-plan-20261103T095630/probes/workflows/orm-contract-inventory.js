export const meta = {
  name: 'orm-contract-inventory',
  description: 'Read-only inventory of Odoo 19 contracts vs the Kaupamex port, per plan unit, with adversarial cross-check',
  whenToUse: 'Inventory unread contract families before implementing them; rerun with only the changed units',
  phases: [
    { title: 'Research', detail: 'one agent per unit: reference contract + consumer state per obligation' },
    { title: 'Cross-check', detail: 'independent agent tries to refute each status against code' },
  ],
}

const RULES = `STRICTLY READ-ONLY. Do not create, edit or delete files. No git command that changes state (no checkout, restore, stash, add, commit). Do NOT connect to PostgreSQL and do NOT run psql, pytest, django, manage.py or uv run: a database gate is running and must not be disturbed. Only cat, sed -n, grep, rg, find, ls, git show/log/grep.
Reference tree (Odoo 19 Community) at revision ${args.sourceRev}: R=/home/user/odoo-tools/19.x/odoo-19.0/odoo-19.0/odoo-19.0
Consumer repo at revision ${args.consumerRev}: /home/user/kaupamex-api (local conventions: quantities are fields.Monetary(max_digits=16, decimal_places=4); Django FK names drop the _id suffix on Django comodels, e.g. move, product_tmpl, uom; context_scope replaces with_context on Django rows).
Statuses: SATISFIED (local symbol exists AND behaves like the source, shown by code), PARTIAL (exists, some behavior missing), ABSENT (no local symbol), DIVERGENT (local behavior contradicts the source on purpose, with a declared reason in code), UNVERIFIED (could not establish). A similar name is NOT satisfaction. Never mark DIVERGENT for something merely missing.`

const OBLIGATION = {
  type: 'object',
  properties: {
    symbol: { type: 'string' },
    kind: { type: 'string' },
    ref_location: { type: 'string' },
    local_symbol: { type: 'string' },
    local_location: { type: 'string' },
    status: { type: 'string', enum: ['SATISFIED', 'PARTIAL', 'ABSENT', 'DIVERGENT', 'UNVERIFIED'] },
    evidence: { type: 'string' },
    missing: { type: 'string' },
  },
  required: ['symbol', 'kind', 'ref_location', 'local_symbol', 'local_location', 'status', 'evidence', 'missing'],
}
const RESEARCH_SCHEMA = {
  type: 'object',
  properties: {
    unit: { type: 'string' },
    obligations: { type: 'array', items: OBLIGATION },
    dependencies: { type: 'array', items: { type: 'string' } },
    required_tests: { type: 'array', items: { type: 'string' } },
    unverified_assumptions: { type: 'array', items: { type: 'string' } },
    files_opened: { type: 'integer' },
  },
  required: ['unit', 'obligations', 'dependencies', 'required_tests', 'unverified_assumptions', 'files_opened'],
}
const CHECK_SCHEMA = {
  type: 'object',
  properties: {
    verdicts: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          symbol: { type: 'string' },
          confirmed: { type: 'boolean' },
          corrected_status: { type: 'string', enum: ['SATISFIED', 'PARTIAL', 'ABSENT', 'DIVERGENT', 'UNVERIFIED'] },
          reason: { type: 'string' },
        },
        required: ['symbol', 'confirmed', 'corrected_status', 'reason'],
      },
    },
  },
  required: ['verdicts'],
}

const results = await pipeline(
  args.units,
  (unit) => agent(`${RULES}

Role: contract researcher + port auditor for plan unit "${unit.id}" (canonical ${unit.task}).
Model: purchase.order.line. Source file: $R/addons/purchase/models/purchase_order_line.py (follow calls into other models as needed). Consumer file: /home/user/kaupamex-api/addons/purchase/models/purchase_order_line.py (and wherever the consumer defines the symbol).
For EACH of these obligations (all of them, none skipped): ${unit.obligations.join(', ')}
report: kind, reference file:line, the exact source semantics that a port must reproduce (decorators, depends, branches, side effects, consumers it calls), the local symbol and file:line or ABSENT, the status, evidence (file:line in both trees), and what is missing.
Also list the dependencies on other models/fields the unit needs (with local presence), the behaviors a discriminating test must cover, and anything you could not verify.`,
    { label: `research:${unit.id}`, phase: 'Research', schema: RESEARCH_SCHEMA, agentType: 'Explore', model: 'sonnet' }),
  (research, unit) => {
    if (!research) return null
    const claims = research.obligations.map(o => `- ${o.symbol}: ${o.status} | local ${o.local_symbol} @ ${o.local_location} | ref ${o.ref_location} | ${o.evidence}`).join('\n')
    return agent(`${RULES}

Role: adversarial cross-checker for plan unit "${unit.id}". Another agent produced the status claims below. Try to REFUTE each one by reading the code yourself at the cited locations (and searching for the symbol if the location is wrong). Default to confirmed=false if you cannot verify it from code. A SATISFIED claim needs the local code to actually do what the source does; a DIVERGENT claim needs a declared reason in the consumer code; an ABSENT claim is refuted if you find the symbol under any name that implements the same behavior.
Claims:
${claims}`,
      { label: `check:${unit.id}`, phase: 'Cross-check', schema: CHECK_SCHEMA, agentType: 'Explore', model: 'sonnet' })
      .then(check => ({ unit: unit.id, task: unit.task, research, check }))
  },
)

const report = []
for (const r of results.filter(Boolean)) {
  const verdicts = new Map((r.check?.verdicts || []).map(v => [v.symbol, v]))
  const rows = r.research.obligations.map(o => {
    const v = verdicts.get(o.symbol)
    let final
    if (!v) final = 'UNVERIFIED'
    else if (v.confirmed) final = o.status
    else final = v.corrected_status === 'DIVERGENT' ? 'UNVERIFIED' : v.corrected_status
    return { ...o, final_status: final, check_reason: v ? v.reason : 'no verdict' }
  })
  const declared = args.units.find(u => u.id === r.unit).obligations
  const covered = new Set(rows.map(x => x.symbol.split('.').pop()))
  const missingRows = declared.filter(s => !covered.has(s.split('.').pop()))
  for (const s of missingRows) rows.push({ symbol: s, final_status: 'UNVERIFIED', check_reason: 'not reported by research' })
  const counts = {}
  for (const x of rows) counts[x.final_status] = (counts[x.final_status] || 0) + 1
  report.push({ unit: r.unit, task: r.task, declared: declared.length, counts, rows,
    dependencies: r.research.dependencies, required_tests: r.research.required_tests,
    unverified_assumptions: r.research.unverified_assumptions })
}
const dropped = args.units.map(u => u.id).filter(id => !report.find(x => x.unit === id))
if (dropped.length) log(`units without a result (kept open, not counted as done): ${dropped.join(', ')}`)
return { sourceRev: args.sourceRev, consumerRev: args.consumerRev, report, dropped }
