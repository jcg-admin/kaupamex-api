# El preflight migra por el alias que el router admite

Creado: 2026-11-20T15:30:49 (UTC). TASK-API-0485 (infraestructura del gate). Unidad
`gate-preflight-migrate-through-default-0485`.

- `scripts/gate_preflight.py::connection_for` abre la base del worker bajo el
  alias `preflight_<nombre>`; `prepare_database` llama `migrate` con ese alias.
- `src/orm/routers.py:178-187` (`allow_migrate`) sólo deja migrar `default` y
  `company_<N>_db`. Para cualquier otro alias devuelve `False`.
- Django, con `allow_migrate` en `False`, salta las operaciones y registra la
  migración como aplicada en `django_migrations`.
- Medido: sobre `orm_x2hokp_qa_gw0`, `migrate product 0043` + `migrate` por
  ese alias dejó `product.0044` con `applied` nuevo (14:49:09) y el esquema
  intacto (`default_extra_price` siguió nullable). Por `default` con
  `DB_QA_NAME`, la misma secuencia sí cambió el esquema.
- Consecuencia: una migración pendiente en una base de worker quedaría
  marcada sin columnas; el F2 fallaría después por columna ausente.
- Origen del episodio: las bases de worker conservaban una versión anterior de
  `product/0044` (regenerada tras aplicarse); el preflight sólo mira
  migraciones pendientes y no ve una aplicada cuyo contenido cambió.
Sucesores: `gate-preflight-migrate-through-default` (migrar con el alias que
el router admite) y detectar en el preflight una migración aplicada cuyo
estado difiere del modelo (makemigrations --check por base no lo ve).

## Decisión

- `prepare_database(name)` migra por el alias que el router admite: un
  `manage.py migrate --settings=config.settings.testing` en subproceso con
  `DB_QA_NAME=<name>` (es como se migraron a mano las cuatro bases el
  2026-11-20 y el esquema sí cambió). `pending_migrations` sigue leyendo por
  el alias `preflight_<name>` (lectura: el router no interviene).
- La prueba actual (`test_preparation_migrates_only_a_database_with_pending_migrations`)
  sustituye `call_command` y sólo afirma el alias: es verde con y sin el
  defecto (sub-patrón D). La nueva afirma que el comando corre con
  `DB_QA_NAME` igual a la base y sin `--database`, y una segunda prueba fija
  la premisa: `router.allow_migrate('preflight_x', 'product')` es `False`.
- Anulación: volver a `call_command(..., database=alias)` hace caer la
  prueba del entorno.

## Símbolos que cambia

- `scripts/gate_preflight.py::prepare_database`: migra en un subproceso
  (`manage.py migrate` con `DB_QA_NAME=<nombre>`), por el alias `default`
  que `allow_migrate` admite; el conteo de pendientes sigue leyendo por
  `preflight_<nombre>`.
- `tests/unit/scripts/test_gate_preflight.py`: la prueba de preparación deja
  de sustituir `call_command` por un registro de alias.

Sin contraparte en la referencia: es infraestructura del gate (clase E del
flujo de referencia).

## Medido tras el arreglo

- `tests/unit/scripts/test_gate_preflight.py`: 13 pruebas verdes. Anulación:
  devuelto `prepare_database` a `call_command(..., database=alias)`, cae
  exactamente `test_preparation_migrates_only_a_database_with_pending_migrations`
  (1 failed, 12 passed).
- En la base real: con `product.0044` desaplicada en `orm_x2hokp_qa_gw0`
  (0 de las 3 columnas medidas, 0 filas en `django_migrations`),
  `gate_preflight.py --prepare --workers 4` informó «1 migraciones
  aplicadas» en `gw0` y la base quedó con las 3 columnas y la fila de
  `0044`.

## Lo que no cierra

El preflight sigue sin ver una migración aplicada cuyo contenido cambió
después (el origen del episodio). Sucesor:
`gate-preflight-applied-migration-drift-0485`.
