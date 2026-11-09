# Diseño — fechas de `TimeStampedModel` con la hora de la transacción

Fecha: 2026-11-09T01:22:26 · TASK-API-0485.

## Contrato (odoo19c)

- `Cursor.now()` devuelve *"the transaction's timestamp NOW() AT TIME ZONE
  'UTC'"*, consultado una vez y memorizado (`odoo/sql_db.py:271-278`).
- `create` fija `create_date` y `write_date` con `cr.now()`
  (`odoo/orm/models.py:4803-4805`); `write` fija `write_date` con
  `cr.now()` (`:4396`).
- Consecuencia: todo lo creado o escrito en una misma transacción lleva la
  misma fecha, y un `write` en la transacción del `create` no mueve
  `write_date`.

## Aquí (medido en el código)

`TimeStampedModel` (`src/addons/base/models/timestamped_mixin.py`) declara
`created_at = DateTimeField(auto_now_add=True)` y
`updated_at = DateTimeField(auto_now=True)`: Django fija la hora de cada
`pre_save` (`timezone.now()`), distinta en cada guardado de la misma
transacción. No existe porte de `cr.now()` (`grep -rn "def now(self" src` → 0).

## Casos (prueba `tests/unit/orm/test_timestamped_transaction_now.py`)

| Caso | Esperado |
|---|---|
| dentro de un `atomic`, crear y luego escribir | `updated_at == created_at` |
| dentro de un `atomic`, dos altas | misma `created_at` |
| la fecha es la de PostgreSQL `now()` de esa transacción | igual a `SELECT now()` |

## Corrección propuesta

Un `transaction_now()` que memorice `SELECT now()` por transacción de la
conexión (equivalente de `cr.now()`), y que los dos campos de
`TimeStampedModel` lo usen en su `pre_save` en vez de `timezone.now()`.
La memoria se invalida al cerrar la transacción (`on_commit`/rollback):
hay que medir dónde engancharlo sin crear un segundo mecanismo si
`orm.environments` ya tiene el ciclo de vida de la transacción.

## RED medido

Los tres casos fallan: en una misma transacción `updated_at` avanza 15 ms
tras el `create`, dos altas difieren en 14 ms, y la fecha no es la de
`SELECT now()`.

## Riesgo a medir con la suite

Bajo `pytest-django` cada prueba es una transacción: con la corrección, sus
filas comparten fecha. Cualquier prueba o código que ordene por `created_at`
y espere el orden de alta (`get_latest_by = 'created_at'`) quedará con
empates. La referencia tiene el mismo comportamiento y ordena por `id`
cuando necesita el orden de alta.

## Decisión de mecanismo

No se memoriza por bloque `atomic`: un `@transaction.atomic` usado como
decorador reutiliza el mismo objeto `Atomic` en cada llamada, y la clave
serviría la fecha de una transacción anterior. PostgreSQL ya resuelve la
memoria: `now()` es constante dentro de la transacción. Los dos campos
preguntan `SELECT now()` en su `pre_save` y comparten el valor dentro del
mismo guardado (una consulta por `save`, no dos). El coste se mide con la
duración de la suite completa.

## Verde y control (medidos)

`TransactionDateTimeField` en `timestamped_mixin.py` (`pre_save` con
`transaction_now`, deconstruido como `DateTimeField`): 3 de 3 en verde, y
`makemigrations --check --dry-run` → «No changes detected». Anular la rama de
`pre_save` tumba exactamente los tres casos. La suite completa mide el
efecto sobre consumidores que ordenan por `created_at`.

## Efecto medido sobre los consumidores (suite completa)

12226 passed, 2 failed (más los 5 errores multidb conocidos), los dos
previstos:

- `test_account_journal_debit_sequence::test_timestamped` comparaba con
  `timezone.now()` tomado a media prueba; ahora compara con
  `transaction_now()`, que es el contrato.
- `admin/logs` ordenaba por `-created_at`; la referencia ordena `ir.logging`
  por `id DESC` (`base/models/ir_logging.py:8`) y el `Meta.ordering` local ya
  era `['-id']`. Corregido el controlador.

## Sucesor abierto (TASK-API-0485)

`git grep -n "order_by(['\"]-\?created_at['\"]" -- src addons ':!*tests*'`:
21 usos en 15 archivos; `get_latest_by|.latest(|.earliest(`: 49. Ninguno
falló en la suite, pero cada uno puede empatar entre filas de una misma
transacción. Se revisan contra el `_order` de su modelo en la referencia,
uno por modelo, no en bloque.

## Conciliación pedida por el ejecutor (2026-11-09, segunda pasada)

**Estado de partida, medido.** Los dos fallos de la suite completa
(`full-ts-20261109T014856`, EXIT=1: `test_timestamped` y
`test_admin_lists_ir_logging`) se corrigieron en `94930e21`. La suite completa
sobre `e064fa7b` (desciende de `94930e21`) dio 12228 passed, 0 failed, 5
errores multidb ambientales; multidb aprobó sobre `f7cbd1fe` (incluye
`94930e21`). Ninguna prueba viva al empezar.

**Contrato de la referencia, ampliado.**

| Eje | odoo19c | Aquí con `SELECT now()` |
|---|---|---|
| transacción | `cr.now()` memorizado (`sql_db.py:271-278`) | `now()` de PostgreSQL, constante en la transacción |
| savepoint / `atomic` anidado | no reinicia `_now` (sólo `commit`/`rollback`, `:560-576`) | `now()` no cambia en un savepoint: igual |
| tras `commit`/`rollback` | `_now = None`: fecha nueva | nueva transacción, `now()` nuevo: igual |
| alta: `create_date` == `write_date` | los dos de un mismo `cr.now()` (`models.py:4803-4805`) | **riesgo**: dos `SELECT now()`; en autocommit (fuera de `atomic`) son dos transacciones y pueden diferir |
| ordenamiento | los modelos que necesitan orden de alta ordenan por `id` (`ir_logging.py:8`) | 21 `order_by` + 49 `latest`/`earliest` por revisar |

**Corrección del riesgo.** Una sola consulta por guardado: el primer campo
consulta `now()` y el segundo reutiliza el valor dentro del mismo `save`. Se
prueba simulando el autocommit (un `transaction_now` que devuelve valores
crecientes), sin `django_db(transaction=True)`, que trunca toda la base QA
compartida al terminar.

### Implementación y controles de la segunda pasada

`TimeStampedModel.save` delimita una lectura de reloj (`SAVE_NOW`) que
comparten las dos fechas del guardado, y `_write_alias` resuelve la base de
escritura (`using` de `save`, `_state.db` o `router.db_for_write`). 7 casos:

| Anulación | Cae |
|---|---|
| sin reutilizar la lectura | `test_one_insert_takes_both_dates_from_one_clock_reading` |
| alias = `_state.db` (era `None` en el INSERT) | `test_the_clock_is_read_on_the_row_database` |
| la lectura no se limpia entre guardados | `test_a_later_save_reads_the_clock_again` (la primera versión, sobre `create`+`write`, no discriminaba: eran dos instancias distintas) |

## Consumidores, revisados uno a uno

**Corrección de una cifra propia.** El «49» de `latest`/`earliest`
(H-API-1191) salió de un `git grep` con el punto sin escapar: `.latest(`
también cazaba `_latest(`. Con `\.latest(\|\.earliest(`: **0** llamadas en
producción; `get_latest_by` sólo en `TimeStampedModel.Meta`. Cambiar esa
opción genera una migración por cada modelo heredero (la opción viaja en
`AlterModelOptions`) sin un consumidor que lo pida: no se toca, y se anota.

**Restas y comparaciones de fechas.** Dos:
- `helpdesk/controllers/main.py:509` resta fechas de dos filas distintas
  (respuesta y ticket): misma semántica que la referencia con `create_date`.
- `purchase_stock/models/stock.py:678` filtra `updated_at >= written_after`.
  La referencia fija `written_after = self.env.cr.now()`
  (`stock/models/stock_orderpoint.py:343`): con fechas de transacción la línea
  escrita en la misma transacción cumple la igualdad, que con fechas de reloj
  podía fallar. Nadie fija hoy `written_after` aquí (`git grep "written_after="`
  → 0): cuando se porte `action_replenish` tiene que usar `transaction_now`.

**Ordenamientos por `created_at`.** 21 en producción; 2 ya desempatan por
`id` (`mass_mailing/controllers/subscribers.py:67`,
`mass_mailing/services.py:180`). Los 19 restantes no tienen orden determinista
entre filas de una misma transacción. Corrección de este pase: desempatar por
`id` en la misma dirección, que es el desempate que la referencia usa en sus
`_order` (`'..., id desc'`). Alinear el criterio principal con el `_order` de
cada modelo es otra pasada, por modelo.

## Derivación desde odoo-tools (3.2.14-C.1) — 2026-11-09T04:36:31

**Referencia.** `/home/user/odoo-tools/19.x/odoo-19.0/odoo-19.0/odoo-19.0`,
raíz Git `/home/user/odoo-tools`, revisión `abe4040ec1a45beee90fb694e4eae4453e46b389`,
`odoo/release.py:15` `version_info = (19, 0, 0, FINAL, 0, '')`. Enterprise en
`19.x/odoo19-enterprise-main/odoo19pro-main/odoo19pro-main` (OEEL-1, sólo lectura).

### Contrato de las columnas de acceso

| Caso | Referencia | Kaupamex |
|---|---|---|
| alta | `create_date`/`write_date` ← `cr.now()` (`odoo/orm/models.py:4801-4805`) | `TransactionDateTimeField.pre_save`, una lectura por guardado |
| escritura | `write_date` ← `cr.now()` (`:4394-4396`); computados (`:4534-4536`) | `auto_now` con la misma lectura |
| valor explícito | descartado salvo superusuario con el registro sin cargar (`:4387-4390`, `:4781-4784`) | `auto_now`/`auto_now_add` lo pisan; `sudo` no cambia el uid (no habilita) |
| reloj | `SELECT now() AT TIME ZONE 'UTC'`, memorizado (`odoo/sql_db.py:271-278`) | `SELECT now()` en la conexión del alias de escritura |
| reinicio | sólo `commit`/`rollback` (`sql_db.py:565,576`); no en savepoints | PostgreSQL `now()` = inicio de transacción; savepoint no lo cambia |
| sin `_log_access` | sin columnas (`models.py:283`, por defecto `_auto`) | sólo los modelos que heredan `TimeStampedModel` |

Ciega a: el modo autocommit de Django, donde cada `SELECT now()` es su propia
transacción (ya declarado arriba).

### Consumidores derivados uno a uno

- `ir.logging`: `_order = 'id DESC'` (`odoo/addons/base/models/ir_logging.py:8`). Ya aplicado en `94930e21`.
- Diario de notas de débito: `account.journal` sin `_log_access` → `_auto`; en el alta las dos fechas valen `cr.now()`. La prueba compara igualdad con la hora de la transacción (más estricta que la de reloj).
- **`res.users.log._gc_user_logs` — divergencia previa encontrada al derivar.** La referencia borra `log1` sólo si existe `log2` del mismo `create_uid` con `create_date` **estrictamente** mayor: conserva todas las filas empatadas en la fecha máxima. El puerto conservaba una por usuario, desempatando por id. Corregido a `Exists(created_at__gt=OuterRef)`; RED en `red/gc-user-logs-ties.txt`; controles: sin correlación cae 1, con `__gte` caen 3.
- **Desempate de las 22 consultas por `created_at`.** No se aplica en bloque: cada una está clasificada en `tests/unit/orm/test_created_at_orderings_tie_break.py::REGISTRY` con su fuente:
  - `reference-id` — crm.lead `'priority desc, id desc'` (`crm/models/crm_lead.py:87`), helpdesk.ticket `'priority desc, id desc'` (odoo19e `helpdesk/models/helpdesk_ticket.py:27`), mail.message `'id desc'` (`mail/models/mail_message.py:74`), payment.transaction `'id desc'` (`payment/models/payment_transaction.py:27`), rating.rating `'write_date desc, id desc'` (`rating/models/rating.py:15`), sale.order `'date_order desc, id desc'` (`sale/models/sale_order.py:38`);
  - `reference-untied` — `stock.quant._onchange_product_id` ordena `'create_date desc'` con `limit=1` sin desempate (`stock/models/stock_quant.py:985-987`): el puerto conserva esa forma literal;
  - `consumer` — modelos sin contraparte 1:1 (voucher, guía de envío, historial de búsqueda, colas FIFO, carrito, factura L0, suscriptores).
- Abierto, otra obligación: el orden **principal** de varias consultas difiere del `_order` de su referencia (crm, helpdesk `priority`; rating `write_date`; sale `date_order`). No se cambia aquí: altera contratos de interfaz del Consumer.
