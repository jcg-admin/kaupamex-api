# TASK-API-0420 — acceptance continuation, not reimplementation

Consumer baseline79bc956e; functional8aca3900 preserved. Historical admission, PostgreSQL JSON model and seven new tests not replayed. Provider9b13f2d7; native resolve_store_dir(create=False), connect_readonly and mapping_from_store/lookup used, store hash unchanged (task-readonly.json).

Native commands in probes/acceptance_checks.py: uv run --frozen python src/manage.py check exit0; makemigrations --check --dry-run exit1. Real least privilege CONNECT-only QA role, read-only session and scoped HBA entry cleaned; no .env edits, migrations or table creation. E010 absent from both. Pending migrations concern timezone choices only: base0087_alter_respartner_tz and resource0003_alter_resourcecalendar_tz_alter_resourceresource_tz. No files generated. These source models are unchanged by JSON commit; global migration acceptance remains false, no claim of baseline replay. No timezone fix added.

CI39554071093/job119069611117 failed on head79bc956e. Full log obtained from gh api repos/jcg-admin/kaupamex-api/actions/jobs/119069611117/logs; compressed full log and raw SHA/bytes in outputs/ci-result.json. 10624 errors mostly common setup res_users missing; all7 JSON tests error at setup, do not count as executed/accepted. Existing H-API-1120 (historical646) owns infrastructure debt; no new TASK per error. No protection bypass. PR109 OPEN, not merged.

Existing focused3 compute/inverse/precompute failures are characterized in adjacent0419 run; known before either change and retained. JSON bounded verification remains valid; global CI, migration acceptance and integration pending.
