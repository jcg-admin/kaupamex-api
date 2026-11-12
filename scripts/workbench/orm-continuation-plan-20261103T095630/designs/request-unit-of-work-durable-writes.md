# Escrituras que sobreviven al rollback de la unidad de trabajo por petición

Creado: 2026-11-12T19:01:55 (UTC). TASK-API-0485, unidad `request-unit-of-work-0485`.

## Causa medida

Con `UnitOfWorkMiddleware` un 4xx/5xx revierte la transacción de la
petición (`odoo/http.py:2267-2277`, `_serve_db`). Dos escritores del
consumidor viven dentro de esa transacción y se pierden con ella:

| Escritor | Qué se pierde | Prueba que lo mide |
|---|---|---|
| `addons/authz_audit/audit.py:audit_authz_event` | el `AuthzEvent` DENY de un 403 (DEC-07); 5 sitios de llamada | `test_reauth_session.py::test_sensitive_mutation_without_reauth_403` |
| `src/tools/logging_handlers.py:DatabaseLogHandler.emit` | la fila `ir.logging` del error que causó el rollback | (sin prueba hoy) |

En la fuente `ir_logging` se escribe con su **propio** cursor
(`odoo19c: odoo/netsvc.py`, `PostgreSQLHandler.emit`:
`sql_db.db_connect(dbname).cursor()`), así que sobrevive al rollback de la
petición. Aquí `DatabaseLogHandler` usa el ORM de la conexión compartida:
divergencia heredada que la unidad de trabajo vuelve dañina.

## Alternativas

1. **Cursor propio (`registry.cursor()`)**, igual que la fuente. Correcto
   en producción. En pruebas el `TestCursor` es un savepoint anidado en el
   `atomic` de la petición y se revierte con ella (igual que en
   `HttpCase` de la fuente): la prueba de DENY seguiría roja sin medir nada
   distinto de la topología de pruebas.
2. **Reescritura tras el rollback** (`cr.postrollback`,
   `odoo/sql_db.py` `BaseCursor.postrollback`): el escritor escribe en la
   transacción y además registra en la unidad de trabajo una retrollamada
   que repite la escritura si la unidad se revierte. Éxito: una fila. Fallo:
   el rollback borra la primera y la retrollamada la escribe en una
   transacción nueva, fuera del bloque revertido. Mismo resultado en
   pruebas y en producción.

## Decisión

Alternativa 2, con el nombre de la fuente: la unidad de trabajo expone
`postrollback` (`tools.misc.Callbacks`, la misma clase del cursor) y
`ir_http.request_postrollback()` lo devuelve, o `None` fuera de una
petición. `audit_authz_event` y `DatabaseLogHandler.emit` lo usan;
fuera de una petición escriben como hoy. El cursor propio del punto 1
queda como deuda de `DatabaseLogHandler` (paridad con `netsvc.py`),
no bloqueante tras este cambio.

## Pruebas

- RED: `test_sensitive_mutation_without_reauth_403` (ya roja).
- Nueva: un error 500 deja su fila `ir.logging`.
- Nueva: un 2xx con auditoría deja exactamente una fila (no duplicada).
- Anulación: sin ejecutar `postrollback` caen las dos primeras.
