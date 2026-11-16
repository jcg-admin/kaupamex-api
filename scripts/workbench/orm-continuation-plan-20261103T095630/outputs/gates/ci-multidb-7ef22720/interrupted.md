# Ejecución interrumpida por reclamo del contenedor

Medido el 2026-11-16T23:24:58.

- `boot_id` al lanzar: `2340d74b-dc41-4fe9-a0f9-943424169975`
  (`intent.json`); tras el reclamo: `168c02a4-7c8c-40d6-84bb-63c6a39f4d86`,
  arranque `2026-11-16 23:21:31` UTC.
- Al morir: 1 passed (`test_domain_write_without_any_company_alias_lands_in_default`),
  aprovisionando la primera base de empresa. Sin `record.json`.
- El `Monitor` de la sesión emitía un latido cada 10 min; el último,
  `latido 23:19:33 tests=1 boot=2340d74b`, llegó 1 min 58 s antes del
  arranque nuevo. Es una observación contra la hipótesis de
  `.claude/rules/local-work-validation.md` (H-THYROX-682) de que un
  `Monitor` que emite evita el reclamo.
- PostgreSQL no volvió solo: `pg_ctlcluster 16 main start` (`Removed stale
  pid file`).
- `--reclaim` retiró sólo lo declarado en `intent.json` y del rol de la
  ejecución: `orm_bootstrap_1be3a29afe3c` y `company_246592168084467_db`;
  la segunda base no llegó a existir (`reclaimed.json`).

No prueba ni refuta la migración `0116`: murió antes del `post_migrate` de
la base de empresa.
