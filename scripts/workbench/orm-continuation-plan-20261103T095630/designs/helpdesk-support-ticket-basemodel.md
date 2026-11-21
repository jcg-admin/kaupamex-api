# helpdesk-support-ticket-basemodel-0397 — `support.ticket` como `BaseModel`

Unidad hija de `basemodel-adoption-0397`, grupo `helpdesk` (la única clase de
la app fuera de `BaseModel`, medido con `apps.get_models()`).

## Referencia y estado

`support.ticket` es un modelo propio del L0. Su forma —qué mixins componen un
ticket— se adopta de `helpdesk.ticket`
(`odoo19e: helpdesk/models/helpdesk_ticket.py:36`), que es **OEEL-1**: no hay
contraparte en Community 19 cuyo código portar, y los campos son del L0
(DEC-KX-03, reimplementación nativa). La única obligación ORM aplicable es la
del programa: todo modelo con `_name` es un `BaseModel`
(`odoo19c: odoo/orm/models.py:334`, `:7046`, `:7049`), así que `env[name]`
devuelve un recordset.

## Cambio

- `SupportTicket` hereda de `models.BaseModel` delante de sus mixins
  (`MailThread`, `MailActivityMixin`, `TimeStampedModel`,
  `SoftDeleteModel`), como `ProductPricelist`.
- `helpdesk` sale de `PENDING` en `tests/unit/orm/test_basemodel_reach.py`.
- Los consumidores (vistas DRF, comando de cierre, señales) se recorren: un
  `BaseModel` conserva su gestor de Django, así que el cambio debería ser de
  base de clase; lo que el recorrido destape se corrige en el mismo pase.

Prueba: `tests/unit/helpdesk/test_support_ticket_basemodel.py`, más
`tests/integration/helpdesk/` y `tests/unit/orm/test_basemodel_reach.py`.

## Lo que destapó el recorrido de consumidores

Un `BaseModel` rechaza los atributos públicos que la clase no declara: es el
`__slots__` de la fuente (`odoo19c: odoo/orm/models.py:362`). La cola
administrativa ponía dos con `annotate()` sobre cada fila, y los dos fallaban
al materializar el registro:

- `replies_count` pasa a ser un campo calculado no almacenado del modelo,
  con `_compute_replies_count`, que cuenta las respuestas de todo el
  recordset con una sola consulta agrupada. Es la forma que la fuente da a
  sus contadores; la vista de lista deja de anotar.
- `first_response_at` sólo hacía falta como expresión de consulta: la
  anotación de `_annotate_first_response` se llama ahora
  `first_response_date`, y el export CSV
  (`AdminSupportTicketExportCSVView.get`) lee sus filas con `.values()`, que
  sigue siendo una sola consulta y no escribe nada sobre el registro. El
  correo del comprador se lee por la columna del contacto
  (`user__partner_id__email`), porque `email` de `res.users` se delega por
  `_inherits` y no tiene columna propia.

Pruebas: `tests/integration/helpdesk/test_support_endpoints.py` (cola, métricas
y export) y `tests/unit/helpdesk/test_support_ticket_basemodel.py`.
