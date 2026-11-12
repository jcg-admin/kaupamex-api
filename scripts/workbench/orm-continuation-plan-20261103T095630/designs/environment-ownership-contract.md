# Contrato de propiedad del Environment: transacción, volcado y alias

Creado: 2026-11-12T10:10:08 (UTC). Referencia: odoo-tools `abe4040ec1`,
Odoo 19 Community (`odoo19c`). Origen: el fallo de ci-multidb `f77418eb`
(11 passed / 1 failed, evidencia en `outputs/gates/ci-multidb-f77418eb/`,
commit `2d574be0`) y la instrucción operativa del ejecutor, §3 y §5.

## 1. El contrato de la fuente

En Odoo 19 el dueño de todo estado de escritura es **el cursor del entorno
del recordset**. No hay entorno activo global: cada operación recibe
`self.env` y lee de ahí.

| Operación (firma real) | Dueño que lee la fuente | Cita |
|---|---|---|
| `Environment._recompute_all(self) -> None` | `self.transaction.tocompute` | `odoo/orm/environments.py:368` |
| `Environment.flush_all(self) -> None` | `self._recompute_all()`, `self._field_dirty`, `self[model].flush_model()` | `:380-390` |
| `BaseModel.flush_model(self, fnames=None)` | `self._recompute_model`, `self.env._field_dirty` | `odoo/orm/models.py:6353` |
| `BaseModel.flush_recordset(self, fnames=None)` | `self._recompute_recordset`, `self.env._field_dirty`, `self._ids` | `:6367` |
| `BaseModel._flush(self)` | `self.env._field_dirty.pop`, `self.env.cache` | `:6387` |
| `BaseModel._write(self, vals)` / `_write_multi(self, vals_list)` | `self.env.cr` (UPDATE) | `:4520`, `:4524` |
| `BaseModel.modified(self, fnames, create=False, before=False)` | `self.env.add_to_compute`, `self.env.transaction` | `:6756` |
| `_recompute_model` / `_recompute_recordset` / `_recompute_field(field, ids=None)` | `self.env.records_to_compute` | `:6920`, `:6934`, `:6948` |
| `Cursor.now(self) -> datetime` | memoria `self._now` del cursor | `odoo/sql_db.py:271-278` |

Consecuencia: dos entornos sobre cursores distintos no comparten caché,
marcas de suciedad, cola de recómputo ni hora de transacción, y ninguna de
esas operaciones consulta otro entorno que el suyo.

## 2. Cómo lo materializa este árbol

| Concepto de la fuente | Aquí | Dónde |
|---|---|---|
| cursor | conexión de Django, nombrada por su **alias** | `Environment.cr`, `Environment.db_alias` |
| `cr.transaction` | `Transaction` colgada de la conexión (`orm_transaction`) | `_connection_transaction(alias)` |
| registro | `Registry(db_alias)` | `Environment.registry` |
| caché, `_field_dirty`, `tocompute`, `protected` | atributos de esa `Transaction` | `Environment.cache` y demás vistas |
| `cr.now()` | `SELECT now()` sobre la conexión del alias | `transaction_now(using)` |
| fin del cursor | corte `close` → descarta la transacción; `commit`/`rollback`/`savepoint_rollback` → la vacían | `_CURSOR_CUTS`, `_wrap_cursor_cut` |

**La diferencia que crea el riesgo.** Allá todo método recibe `self.env`.
Aquí una parte del motor no recibe entorno y lo **resuelve del canal
ambiental**: `get_transaction()` (alias del canal `_cr`), `env()` (entorno
activo), `Model.objects.none()` y `_from_ids(env(), ...)` (recordset en el
entorno activo). Un entorno con alias propio (`_using`) que no sea el activo
recibe entonces el trabajo **en la transacción de otro**. Ése es el fallo de
`f77418eb`: `init_models` volcaba el entorno de una base sin entrar en él y
el recálculo y la escritura leían la de `default`.

## 3. La regla: selección, propagación y restauración

1. **Selección.** El dueño de una operación es `self.env` del recordset que
   la recibe; su base es `self.env.db_alias`. Para una clase de Django sin
   `BaseModel` (`flush_model(AccountAccount, ...)`) el dueño es el entorno
   activo, que es el único que esa llamada nombra.
2. **Propagación.** Toda **entrada pública** que recibe un entorno y delega
   en código que resuelve el canal ambiental **activa ese entorno** con
   `with self.env:` (o `with self:` en `Environment`) antes de delegar.
   Entradas cubiertas hoy: `Environment.flush_all`, `flush_model`,
   `flush_recordset`. La escritura de columnas recibe el alias explícito
   (`_write_rows(model, ids, vals_list, using)`), no lo infiere.
3. **Restauración.** `Environment.__enter__` apila un marco de tokens de
   `ContextVar` por entrada y `__exit__` lo devuelve en orden LIFO, también
   con excepción (lo garantiza el `with`). Dos `with` anidados sobre el mismo
   entorno —`__new__` agrupa por ejes— tienen marcos distintos.
4. **Prohibido.** Sustituir en silencio el entorno de la operación por el
   activo; añadir `with self.env` local en otra entrada sin pasar por esta
   tabla; usar `router.db_for_read` para elegir la base de una escritura.

## 4. `_flush` es primitiva interna (§5)

Medido (`grep -rnE "(^|[^.a-z_])_flush\(" src addons`): sus únicos
llamadores de producción son `flush_model` (dos llamadas) y `flush_recordset`
(una), `src/orm/models.py`. Los tres corren dentro del `with` de la regla 3,
así que su precondición —**ser invocada con el entorno dueño activo**— se
cumple por construcción. Las pruebas que la llaman directamente
(`test_missing_recompute.py`, `test_flush_manager_contract.py`) lo hacen en
el entorno por defecto, que es el activo. No se añade guarda defensiva: no
hay llamador fuera de alcance que la exija. Si aparece uno, se corrige la
frontera (entrada pública con `with`), no `_flush`.

## 5. El ciclo del `default_env` en las pruebas

`Transaction.flush` vuelca como `default_env` (`environments.py:589-598`). La
fuente abre un cursor por caso de prueba, así que el `default_env` que un
caso fija muere con su cursor. Aquí la transacción cuelga de la conexión, que
pytest-django conserva entre pruebas: un `default_env` cuyo usuario creó la
prueba sobrevivía a su `rollback`. Mientras `flush_all` no entraba en su
entorno el defecto no se veía; al entrar (§3.2), la prueba siguiente escribió
`write_uid` con un usuario inexistente (suite integral del lote 3,
`TestTheTransactionFlush`). Corrección: `release_test_transaction` en
`tests/conftest.py` restaura el `default_env` previo o descarta la
transacción creada por la prueba. En producción `CONN_MAX_AGE` es 0: el
corte `close` de fin de petición descarta la transacción.

## 6. Hora de transacción del CRM (§6)

`record_transaction_now(record)` = `transaction_now(_write_alias(record))`:
alias de escritura del registro (`using` explícito de `save`, `_state.db` o
`router.db_for_write`), nunca `db_for_read`, y expuesto a los addons por la
fachada `addons.base.models.timestamped_mixin`.

Diferencias medidas con `Cursor.now()`: la fuente devuelve
`now() AT TIME ZONE 'UTC'` (sin zona) y la memoriza en el cursor; aquí
`SELECT now()` devuelve `timestamptz` (mismo instante, con zona, coherente con
`USE_TZ=True`) y la constancia la da PostgreSQL dentro de una transacción.
Fuera de `atomic` (autocommit) cada llamada es su propia transacción.

## 7. Obligaciones abiertas de esta unidad

| Obligación | Estado |
|---|---|
| Pruebas de dos entornos sobre la misma base, dos bases, ids coincidentes, anidamiento, excepción y restauración, recómputos pendientes, volcado parcial y total, varias escrituras, rollback y savepoint (§4) | pendiente; diseño de casos en esta tabla, RED antes de código |
| Igualdad exacta de `record_transaction_now` con `create_date`/`write_date` en una transacción, distinta entre transacciones, restauración de contexto (§6) | pendiente |
| Barrido de entradas públicas que delegan en el canal ambiental (`modified`, `recompute`, `_write`) contra la regla 3 | pendiente |
| ci-multidb sobre la revisión final integrada y la variante con alias anulado | pendiente tras integrar el lote |
