# ORM contract history audit

Consumer evidence recorded through Thyrox session.job_runs and workbench.manifest.
This is direct Codex analysis, not a task executed by a local model.

Run from the API root with ODOO_TOOLS set to the authorized reference root,
UV_CACHE_DIR set to the cloud cache and PYTHONPATH=src:

```
uv run --frozen python scripts/evidence/orm-contract-history-audit-20261019T220449/outputs/check_plain_field_assignment.py
```

The manifest instrument is the source path relative to this run, as required
by native checkWorkbench. The initial command-shaped declaration was rejected
by that verifier and is preserved in the append-only manifest. The corrected
source-path declaration supersedes it.

The command exits 1 because the protected
plain-field assignment does not dispatch like the original Odoo Field.__set__.
The source is retained in outputs/check_plain_field_assignment.py.

Historical instruments were reused before adding that narrow discriminating
comparison. No product ORM code or Provider capability was implemented.

Results: native stack probe 21/14/159 declarations (19/14/155 unique names),
with 27 unique names now on BaseModel outside its four measured carriers.
The ordinary cache/cardinality probes pass; manual __dict__ injection in the
previous audit is a separate precondition. Registry support instruments have
28 passing controls but do not prove persistence. Native job metadata has
15 passing Provider tests. The historical ID access probe was BLOCKED because
CaptureQueriesContext requires a connection; its later ID-setter probe passes.

Limits: no production schema inspected, no PostgreSQL CRUD acceptance, no
full Odoo runtime, no global ORM completion. The attached instruction is
analysis-only. Official task states and resource labels remain unchanged.

The historical full baseline log is retained in its original run; it ended
with 321 failed, 10247 passed, 30 skipped, 1 xfailed and 43 errors (exit 1).
That old result is not a current baseline or an isolated root cause.
