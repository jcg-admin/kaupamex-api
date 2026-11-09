# Bases residuales — reconciliación pendiente (2026-11-09)

Directiva del ejecutor: no eliminar `orm_bootstrap_b42418e0a4d4` ni las
`company_*_db` de procedencia no demostrada; determinar propietario,
sesiones, creador, claims y política antes de cualquier limpieza.

Medido en solo lectura (`pg_database`, `pg_stat_activity`, `pg_stat_file`),
2026-11-09 ~20:40Z:

| Base | Propietario | Creada (`PG_VERSION`) | Tamaño | Sesiones |
|---|---|---|---|---|
| `orm_bootstrap_b42418e0a4d4` | `orm_x2hokp` (rol QA del clon) | 19:20:13Z | 43 MB | 0 |
| `company_201103761692838_db` | `orm_x2hokp` | 19:31:11Z | 43 MB | 0 |
| `company_201103761692839_db` | `orm_x2hokp` | 19:46:21Z | 25 MB | 0 |

Procedencia:

- `orm_bootstrap_b42418e0a4d4`: nombre que sólo forma
  `scripts/run_multidb_isolation.py` (`'orm_bootstrap_' + secrets.token_hex(6)`),
  creada 4 s después del arranque de `make ci-multidb` sobre `c338a12a`
  (19:20:09Z). Esa ejecución murió con el reclamo del contenedor
  (`boot_id` cambió; arranque 19:45:20Z) antes de su limpieza
  (`drop_created`). **Inferido** por nombre y hora; sin traza en el log del
  servidor ni en `.claude/coordination/claims.jsonl`.
- `company_…838_db` / `company_…839_db`: ids consecutivos, que es la pareja
  que crea `tests/integration/company/test_multidb_isolation.py`
  (`_COMPANY_A_ID = secrets.randbits(48)`, `_COMPANY_B_ID = _COMPANY_A_ID + 1`):
  **una sola** ejecución de esa prueba. Cuál, no está demostrado: la hora de
  la segunda (19:46:21Z) es posterior al arranque de la máquina y el servidor
  estaba detenido cuando se comprobó después del reclamo. Sin traza en el log
  ni en los claims.

Política: el ejecutor de multidb borra sólo lo que creó en su propia
ejecución (`drop_created`, con comprobación de propietario); no hay política
para restos de una ejecución interrumpida.

**Decisión: se conservan las tres.** No se puede demostrar que pertenecen
exclusivamente a una ejecución terminada. No interfieren: cada ejecución
nueva usa nombres aleatorios (la de `c338a12a` relanzada terminó con
`pytest_exit 0`). Un intento previo de borrar la primera fue rechazado por el
control de permisos de la sesión y no se repitió.

Obligación de reconciliación: decidir con el ejecutor una política de restos
de ejecuciones interrumpidas (p. ej. que `run_multidb_isolation.py` registre
cada base creada en un archivo de la ejecución antes de crearla, para que una
limpieza posterior pueda demostrar la procedencia).
