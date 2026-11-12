# Hora de transacción del CRM: una sola lectura por guardado

Creado: 2026-11-12T11:57:42 (UTC). TASK-API-0485. Continúa
`timestamped-transaction-now.md` y la unidad `d0beaedf` («Date CRM leads
with the transaction time»). Origen: §6 de la instrucción operativa
(validar `record_transaction_now`).

## Contrato de la fuente

`Cursor.now()` (`odoo19c: odoo/sql_db.py:271-278`) lee
`now() AT TIME ZONE 'UTC'` **una vez por transacción** y lo memoriza en
`self._now`; `commit()` y `rollback()` lo vacían (`:560-576`). Las fechas que
`crm.lead` fija con `self.env.cr.now()` (`date_open`,
`date_last_stage_update`, `date_conversion`, el `now` de `write` y de
`copy_data`) coinciden así con `create_date`/`write_date`, que `_create` y
`_write_multi` toman del mismo `cr.now()` (`models.py:4803-4805`). En dos
transacciones distintas, los valores difieren.

## Lo que hace este árbol (medido)

| Pieza | Lectura de `now()` |
|---|---|
| `create_date`/`write_date` (`TransactionDateTimeField.pre_save`) | **una por guardado**: `SAVE_NOW` en la instancia, vaciado por `TransactionClockSaveMixin.save` (`src/orm/fields_temporal.py:584-619`) |
| `record_transaction_now(record)` (`d0beaedf`) | **una por llamada**: `SELECT now()` sobre el alias de escritura, sin consultar `SAVE_NOW` |

Dentro de un `atomic`, `now()` de PostgreSQL es constante y las dos
coinciden. En autocommit —el modo de las peticiones, porque `DATABASES` no
declara `ATOMIC_REQUESTS`— cada `SELECT now()` es su propia transacción:
`date_open` (calculado en `save`, antes del INSERT) y `create_date`
(`pre_save`) salen de dos transacciones y difieren por microsegundos. La
fuente no puede producir esa diferencia.

## Corrección (unidad siguiente)

`record_transaction_now(record)` reutiliza `record.__dict__[SAVE_NOW]` si el
guardado de ese registro ya lo leyó y, si no, lo lee y lo deja ahí **sólo
mientras el guardado está en curso** (marca `SAVE_USING` presente), de modo
que `pre_save` reutiliza la misma lectura. Fuera de un guardado, una llamada
sigue leyendo `now()` de su transacción, como `cr.now()` sobre un cursor sin
memoria previa.

## Pruebas (RED antes de implementar)

- en autocommit, un `crm.lead` creado con usuario tiene `date_open ==
  create_date` y `date_last_stage_update == create_date`;
- dentro de un `atomic`, dos guardados devuelven el mismo `now()` (constante
  de PostgreSQL), y en dos `atomic` sucesivos difieren;
- la escritura de un lead fija `date_last_stage_update == write_date` al
  cambiar de etapa;
- el valor es consciente de zona (UTC) y de precisión de microsegundos,
  igual que la columna `timestamptz`;
- anulación: sin reutilizar `SAVE_NOW`, cae la igualdad en autocommit.
