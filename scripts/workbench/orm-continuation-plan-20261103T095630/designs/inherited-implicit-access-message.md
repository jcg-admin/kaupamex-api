# Acceso implícito por un campo heredado — diseño

Fecha: 2026-11-09T04:42:52

**Referencia.** `odoo-tools@abe4040ec1a45beee90fb694e4eae4453e46b389`, Odoo 19 Community.

## Contrato derivado

- `Field._compute_related` (`odoo/orm/fields.py:696-712`): un `AccessError` levantado al
  recorrer la cadena se relanza con el mensaje original más el párrafo
  `"\n\nImplicitly accessed through '%(document_kind)s' (%(document_model)s)."`,
  donde `document_kind = env['ir.model']._get(records._name).name` y
  `document_model = records._name`.
- `BaseModel.write` (`odoo/orm/models.py:4500-4510`): lo mismo cuando el inverso de un campo
  `inherited` levanta `AccessError` al escribir el padre.
- Prueba de la referencia: `odoo/addons/test_access_rights/tests/test_feedback.py:388-395`.

## Medido en el proceso aislado

Observación: `reference/observations/inherited-implicit-access-message.json`
(driver de procedencia `reference/provenance/probe_implicit_access_message.py`, ejecutado una vez por
`reference_process.run_script`).

| Escenario | Párrafo de la referencia |
|---|---|
| child forbidden inherited | `Implicitly accessed through 'test_orm.related_inherits' (test_orm.related_inherits).` |
| child forbidden inherited related | ídem |
| users inherited street | `Implicitly accessed through 'User' (res.users).` |
| write without parent access inherited | ídem al primero |
| child forbidden own key / through key, direct forbidden | ninguno |

## Kaupamex

La lectura de un campo heredado pasa por el `__getattr__` que instala `apply_inherits`
(`src/orm/inherits.py`), y la escritura por su `__setattr__` y su `save`. Ahí se
envuelve el `AccessError` con el mismo párrafo. La descripción sale de `ir.model._get`
en modo `sudo`, como el `_get` "sudoed" de la referencia, y si no hay fila se usa el nombre técnico.
El texto se emite con `tools.translate._` y la cadena fuente verbatim.

RED: `red/implicit-access-paragraph.txt` (4 escenarios difieren).
Controles previstos: retirar el envoltorio de lectura (caen 3) y el de escritura (cae 1).

## Separación (3.2.14-C.2)

La prueba `tests/unit/orm/test_contract_access_on_read_reference.py` compara el párrafo propio
contra la observación del Workbench; no amplía el ejecutor heredado `reference_access_on_read.py`.

## Verificación

- Antes, 4 escenarios difieren (RED). Después, los 5 casos pasan.
- Control de lectura: caen los escenarios de lectura. Control de escritura: cae `write without parent access inherited`.
- Respaldo de la descripción: `_description`, que es lo que `ir.model` refleja (`ir_model.py:429`), cuando el modelo no tiene fila.
