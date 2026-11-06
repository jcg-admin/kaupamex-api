# test_multidb_isolation sobre una base desechable — TASK-API-0496

## Pregunta

Los cinco tests de `tests/integration/company/test_multidb_isolation.py` dan
ERROR en toda suite contra la QA compartida. ¿Es un defecto o es el ambiente?

## El guard, que no se toca

`_require_disposable_default` (`test_multidb_isolation.py:32-37`) rehúsa una
base por defecto que no empiece por `orm_bootstrap_`/`kaupamex_ci_` o cuyo
nombre no coincida con `CI_DATABASE_DISPOSABLE`. Es la misma política que
`scripts/check_ci_database.py` aplica a `make ci-verify`.

## El procedimiento autorizado, y por qué no el harness de Docker

`docs/ci-local.md` pide una base y un rol exclusivos con CREATEDB. Su harness
de Cloud (`scripts/evidence/orm-bootstrap-compute-20261021T210528/probes/
qa_context.py`) crea ambos con `docker exec` sobre el contenedor
`kaupamex-postgres-cloud`; en esta VM el daemon de Docker no corre y el
contenedor no existe. El mismo documento dice que Docker «no se necesita en un
runner con PostgreSQL ya provisionado», que es este caso: clúster nativo 16.15
y el rol exclusivo de esta VM, `orm_x2hokp`, con CREATEDB.

`run_isolation_on_disposable_database.py`:

1. genera `orm_bootstrap_<12 hex>` y comprueba que no existe;
2. entrega a Django ese nombre como base por defecto y de prueba, y el mismo en
   `CI_DATABASE_DISPOSABLE`; las credenciales salen de `src/.env` sin
   imprimirse;
3. ejecuta `check_ci_database.py` (tiene que dar PASS) y luego
   `pytest <archivo> --create-db -v`, con presupuesto propio;
4. comprueba el dueño de la base en `pg_database` y elimina sólo esa base y
   las `company_*` que aparecieron durante la ejecución.

## Resultado

| | |
|---|---|
| base | `orm_bootstrap_dd69fa895c09` — no existía antes; dueño `orm_x2hokp` |
| guard | `check_ci_database.py` exit 0 |
| pytest | **5 passed**, exit 0, 1787 s |
| limpieza | base eliminada; 0 bases `company_*` restantes |
| stack | Python 3.13.18 · Django 6.0.5 · psycopg 3.3.4 · pytest 7.4.4 · PostgreSQL 16.15 |

`outputs/record.json` lo guarda completo; `outputs/pytest_isolation.log` y
`outputs/junit_isolation.xml` son la salida de pytest.

**Los cinco errores eran del ambiente.** El código de producción y el de la
prueba no cambiaron entre la suite que da ERROR y esta ejecución.

## Controles negativos: el guard sigue rehusando la QA compartida

| Control | Resultado |
|---|---|
| `check_ci_database.py` contra `orm_x2hokp_qa` | `BLOCKED`, exit 2 |
| el primer test contra la QA compartida | ERROR: «Isolation fixture requires an explicitly owned disposable default», exit 1 |

## Primer intento

El primer intento se ejecutó bajo `timeout 1200` y se cortó a los 20 min,
aprovisionando la segunda base de empresa; el primer test ya había pasado
(`outputs/first_attempt_*`). El corte impidió la limpieza: quedaron la base
`orm_bootstrap_5e954768332b` y dos `company_*_db` consecutivas. Se eliminaron
por nombre explícito tras comprobar su dueño, sin sesiones activas. El runner
ahora da a pytest un presupuesto propio y limpia en `finally`, también las
`company_*` que aparecen durante la ejecución.

## Ciega a

- otros runners: la duración (≈ 30 min, casi todo en migrar tres bases) es de
  esta VM;
- la suite completa contra una base desechable (`make ci-verify`): es el
  contrato de TASK-API-0478, de otro owner;
- en una suite contra la QA compartida estos cinco siguen dando ERROR, por
  diseño del guard: ese ERROR significa «no ejecutado en un ambiente válido»,
  no un defecto.
