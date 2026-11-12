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

## Precondición medida 2026-11-12T14:05:18 (UTC): el ámbito del guardado empieza antes del mixin

Orden de resolución de `save` en `CrmLead` (medido con `__mro__`):
`CrmLead → TransactionClockSaveMixin → RecordLoaderMixin →
CheckCompanyMixin → Model`. `CrmLead.save` lee la hora en
`addons/crm/models/crm_lead.py:1284` (`now = record_transaction_now(self)`)
**antes** de llamar a `super().save`, y `TransactionClockSaveMixin.save`
vacía `SAVE_NOW` al empezar (`src/orm/fields_temporal.py:610-619`). La
corrección de arriba —reutilizar `SAVE_NOW` sólo con `SAVE_USING`
presente— no alcanza esa lectura: `SAVE_USING` todavía no existe.

El ámbito correcto es el **guardado más externo** de la instancia, el
equivalente de la transacción del cursor en la fuente. Corrección revisada:

1. `TransactionClockSaveMixin.__init_subclass__` envuelve el `save` que
   cada subclase declare con un contador de profundidad por instancia
   (`SAVE_DEPTH`): la entrada más externa abre el ámbito y la salida más
   externa vacía `SAVE_NOW`, `SAVE_USING` y `LOG_ACCESS_EXPLICIT`;
2. `record_transaction_now` y `pre_save` reutilizan `SAVE_NOW` y lo fijan
   mientras el ámbito esté abierto; fuera de él leen `now()` cada vez;
3. RED adicional: en autocommit, `now` de `CrmLead.save` y `write_date`
   del mismo guardado coinciden al cambiar de etapa.

## Causa raíz medida 2026-11-12T14:05:51 (UTC): la petición no tiene transacción

La sección anterior acota el ámbito al guardado, y tampoco alcanza: los
cómputos almacenados que fechan (`_compute_date_open`,
`_compute_date_last_stage_update`) pueden ejecutarse en el volcado
(`flush_all`) posterior al `save` —la prueba existente
`tests/unit/crm/test_lead_dates_and_recurring.py` vuelca después de
`create`—, y en autocommit ese volcado es otra transacción.

En la fuente no existe escritura fuera de una transacción: cada llamada RPC
corre en `with registry.cursor() as cr` (`odoo19c: odoo/service/model.py:131-134`)
y cada petición HTTP en el cursor de su despacho; `cr.now()` es por eso la
hora de toda la unidad de trabajo. Aquí `src/config/settings/base.py` no
declara `ATOMIC_REQUESTS` en ninguna base ni hay un middleware que abra una
unidad de trabajo por petición (medido: `grep ATOMIC_REQUESTS
src/config/settings/*.py` → 0).

Conclusión: compartir la lectura de reloj dentro de un `save` corrige un
síntoma. La unidad que corresponde es la del **ciclo de la petición**, la
misma frontera que la de `signal_changes`/`reset_changes`
(`designs/registry-caches-per-database.md`, «Frontera abierta»): una unidad
de trabajo por petición, cron y comando, con COMMIT, `signal_changes()` al
terminar bien y `reset_changes()` al fallar. Dentro de ella `now()` de
PostgreSQL ya es constante y `record_transaction_now` coincide con
`create_date`/`write_date` sin memoria propia. Se unifican las dos en
`request-unit-of-work-0485`; esta sección sustituye a «Corrección revisada».
