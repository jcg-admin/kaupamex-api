# Incidente: el subconjunto derivado de s5 falló sólo en su primera ejecución

Registrado 2026-11-10T23:42:59. Revisión del código bajo prueba: árbol de trabajo sobre
`555ac073` con los cambios de s5 (después publicados en `e302630b`).

## Las dos ejecuciones

| | Primera | Repetición |
|---|---|---|
| Ventana (UTC) | 23:06:47 → 23:11:27 | 23:14:59 → 23:20:43 |
| Mismo comando | `pytest -q --reuse-db -n 4` sobre 13 directorios derivados | ídem, con `-rfE` |
| Resultado | **1 failed, 6172 passed, 66 skipped, 27 errors** (280.60 s) | **6173 passed, 66 skipped, 0 errors** (344.45 s) |
| Proceso concurrente | ci-multidb de `555ac073` (`make ci-multidb` en worktree propio) | ninguno de prueba |
| Log conservado | sólo las 15 últimas líneas (`tail -15`) | completo |

Pruebas visibles con ERROR en la primera (las 14 que caben en esas 15
líneas): 9 de `tests/unit/orm/test_missing_recompute.py::MissingRecomputeRetryTests`
y 5 de `tests/unit/orm/test_relational_reconstruction_persistence.py::RelationalPersistenceTests`.
Las otras 13 y el FAILED **no se conservaron**.

## Bases, alias y fixtures

- Subconjunto: `orm_x2hokp_qa_gw0..gw3` (una por worker de xdist,
  `pytest-django` sufija `TEST.NAME`).
- ci-multidb: base desechable `orm_bootstrap_<hex>` creada con
  `--create-db`, y dos `company_<n>_db` del fixture
  `two_company_databases`; mismo rol `orm_x2hokp` y mismo servidor
  PostgreSQL 16 (`/var/run/postgresql:5432`).
- Ninguna base es común a los dos procesos. Las clases que fallaron son de
  tipo `TransactionTestCase`: su `flush` emite `post_migrate`, y con s5
  eso ejecuta `install_cycle` → `init_models` → `init` en la base del worker.

## Evidencia medida (log de PostgreSQL, `postgresql-16-main.log`)

*Métrica:* mensajes `ERROR`/`FATAL` distintos (normalizando el sufijo
`_gwN` y los números) dentro de cada ventana, con la fecha fijada.
*Ciega a:* errores del lado de Python que no lleguen al servidor (un
`timeout`, una excepción del fixture antes de conectar), y al detalle de
las 13 pruebas cuyo nombre no se conservó.

- 28 mensajes distintos en cada ventana, **idénticos**: ninguno exclusivo
  de la primera ejecución. Son violaciones de restricción que las pruebas
  provocan a propósito.
- En la ventana 1 hay actividad de `company_<n>_db` (8 líneas): es el
  ci-multidb.
- Checkpoint de 23:07:38 con `write=269.564 s`: E/S saturada durante la
  primera ejecución.
- Una primera comparación sin fijar la fecha mezcló días distintos y produjo
  falsos exclusivos; se descartó y se repitió con la fecha fijada.

## Causa

**No determinada.** Lo medido descarta una colisión de datos en PostgreSQL:
no hay bases compartidas ni errores exclusivos en el servidor. Lo que no se
puede atribuir es la excepción que cada prueba recibió, porque el log se
truncó. Queda una hipótesis por comprobar: contención de E/S y CPU entre los
dos procesos, agravada en la primera ejecución porque la vista
`hr_employee_public` se creaba por primera vez en cada `gwN` (hoy existe
en `orm_x2hokp_qa` y `gw0..3`, medido con `pg_class`).

**Condición de cierre:** repetir el subconjunto con las vistas retiradas de
`gw0..3` y **sin** ejecución concurrente, conservando el log entero; si
reaparece el error, la causa es la primera creación de la vista y no la
concurrencia.

## Prevención con el mecanismo existente

Desde el ci-multidb de `e302630b` los gates se ejecutan en serie: la cadena
espera el `EXIT=` del gate anterior antes de lanzar el siguiente. La
admisión de disco de `thyrox: bin/resource_admission` ya protegía el
ci-multidb; la serialización entre gates sobre el mismo servidor se ha hecho
con una espera por marcador, y el registro como dependencia
(`wait-jobs register --after-ok`) es la forma canónica que debe sustituirla.
Todo subconjunto en paralelo se ejecuta ahora con el log completo
(`-rfE`, sin `tail`).
