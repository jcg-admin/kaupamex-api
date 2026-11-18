# Unidad por petición: un `IntegrityError` llega como error de usuario

Creado: 2026-11-18T10:52:50 (UTC). TASK-API-0485, ítem del plan
`request-unit-of-work-integrity-0485`. Referencia: odoo-tools `abe4040ec1`,
Odoo 19 Community. Continúa `request-unit-of-work.md`.

## La prosa heredada, validada

| Afirmación del plan o del diseño previo | Medido | Veredicto |
|---|---|---|
| la obligación se llama `odoo/service/model.py::_as_validation_error` | `grep -rn _as_validation_error odoo19c:odoo` → 0 | **falso**: no existe. La traducción vive en línea dentro de `retrying` (`odoo19c: odoo/service/model.py:207-214`) |
| «un `IntegrityError` llega como **400**» (`request-unit-of-work.md`, RED) | `ValidationError(UserError)` (`odoo19c: odoo/exceptions.py:119`); `UserError.http_status = 422` (`:15`); el despachador http devuelve `werkzeug_default_exceptions[exc.http_status](exc.args[0])` (`odoo19c: odoo/http.py:2534-2538`) | **falso**: llega como **422** con el mensaje |

## El contrato de la fuente

`odoo19c: odoo/service/model.py:184-214`:

1. `IntegrityError` entra en el mismo `except` que las faltas de
   concurrencia: se revierte, `transaction.reset()`, `reset_changes()`.
2. **No se reintenta**: antes de mirar si es reintentable, se busca el
   modelo cuya `_table` es `exc.diag.table_name` (si ninguno, `env['base']`)
   y se lanza `ValidationError(_("The operation cannot be completed: %s",
   model._sql_error_to_message(exc)))` encadenado al original.
3. El despachador lo convierte en la respuesta de su `http_status` (422)
   con el mensaje como cuerpo (`http.py:2534-2538`).

Vale igual si el `IntegrityError` sale de la vista o del `env.cr.flush()`
posterior (`model.py:188-190`): los dos están dentro del `try`.

## Este árbol

`UnitOfWorkMiddleware` (`src/addons/base/models/ir_http.py`) ya revierte y
llama a `reset_changes()` en los dos caminos, pero el `IntegrityError`:

- **de la vista**: DRF no lo maneja (`drf_exception_handler` → `None`) y
  Django lo convierte en 500; el middleware lo ve por `process_exception`;
- **del volcado o del COMMIT**: escapa del `atomic` y del middleware → 500.

## Decisión

En el middleware, tras revertir, un `IntegrityError` —anotado por
`process_exception` o atrapado del bloque— se traduce y responde:

- el modelo: el de `apps.get_models()` cuyo `Meta.db_table` es el
  `table_name` del diagnóstico (`_database_error`, en `__cause__`) y que
  declara `_sql_error_to_message`; si ninguno, `orm.models.BaseModel`
  (≙ `env['base']`: `base` aquí es abstracto y sin el método);
- el mensaje: `_("The operation cannot be completed: %s", ...)`;
- la respuesta: `JsonResponse({'detail': mensaje, 'codigo_error':
  'VALIDATION_ERROR'}, status=422)` — el 422 de la fuente con el cuerpo del
  contrato de error de este árbol (`codigo_error`, `backend-drf`
  `exceptions.md`);
- no se reintenta, como la fuente.

## RED

1. vista que viola una restricción única → 422, cuerpo con
   «The operation cannot be completed», `reset_changes` una vez, sin fila;
2. el mismo conflicto en el volcado posterior a la vista → 422;
3. control: una `SerializationFailure` sigue reintentándose (sin cambio).

## Lo que esta unidad no cierra

El prompt del plan nombra también «comandos de gestión en su unidad» y «hora
de transacción del CRM bajo la unidad». Ninguno es obligación de este ítem
(`obligations` sólo lista `retrying`) y los dos tienen su propio diseño
(`registry-cursor-unit-of-work.md`, `crm-transaction-time-shared-read.md`).
Se miden al cerrar: si no tienen ítem aceptado, se registran como sucesor.

## Ejecución (2026-11-18)

Símbolos en `src/addons/base/models/ir_http.py`:

- `_integrity_error_model` ≙ el recorrido del registro de
  `odoo19c: odoo/service/model.py:208` (cae en `BaseModel`);
- `_integrity_error_response` ≙ `odoo19c: odoo/service/model.py:213` más
  el 422 de `odoo19c: odoo/http.py:2536`;
- `UnitOfWorkMiddleware.__call__` traduce en sus dos salidas de reversión:
  el `except` (la excepción subió por la cadena, o salió del volcado o del
  COMMIT) y la respuesta fallida anotada por `process_exception` (el
  manejador real de Django ya la convirtió en 500).

Pruebas en `tests/integration/test_orm/test_request_unit_of_work.py`:
`test_an_integrity_error_of_the_view_answers_422`,
`test_an_integrity_error_of_the_final_flush_answers_422` y
`test_through_the_real_handler_an_integrity_error_answers_422`.

Anulaciones, cada una medida por separado:

| Se retira | Caen |
|---|---|
| la traducción en el `except` | las dos primeras, ni una más (2 de 12) |
| la traducción tras `process_exception` | sólo la tercera (1 de 12) |

**Lo que la medición corrigió.** La primera versión de la segunda prueba
escribía `color=-1` con `write` dentro de la vista, suponiendo que el
volcado lo aplazaba. Una sonda lo desmintió: la vista nunca devolvió, porque
un `write` de este ORM ejecuta en el acto. La prueba medía otra vez la
salida de la vista. Ahora sustituye `Transaction.flush` por uno que inserta
una fila que viola la restricción, así que el error nace en el volcado del
middleware.

**Divergencia de conteo, sin efecto.** En la fuente, el `ValidationError`
lanzado dentro del `except` interno pasa por el `except Exception` externo
de `retrying`, así que `reset_changes()` se llama dos veces
(`odoo19c: odoo/service/model.py:197` y `:235`). Aquí se llama una vez. La
operación es idempotente: vacía las marcas de cambio.

Consumidores derivados (`grep -rlE "UnitOfWorkMiddleware|ir_http" tests/`):
544 passed.
