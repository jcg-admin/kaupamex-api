# `attachment-record-access` — el adjunto hereda el acceso de su registro

Unidad del plan bajo TASK-API-0397, en estado `failed` por un bloqueo
registrado. Fuente: `odoo19c: odoo/addons/base/models/ir_attachment.py:42-58`
(`SECURITY_FIELDS`, `condition_values`), `:504-708` (`check`,
`_check_access`, `_inaccessible_comodel_records`, `_search`) y `:710-795`
(las comprobaciones de `write` y `create` sobre el registro adjuntado).

## El bloqueo, re-medido (2026-11-25)

La fila decía que faltaban tres cosas. Medido hoy:

| Precondición | Estado |
|---|---|
| `create_uid` en `ir.attachment` | **existe**: `LogAccessUserField` hacia `base.ResUsers`, por la inyección de `_log_access` (migraciones `0109`, `0110`, `0112`); `IrAttachment._meta.get_field('create_uid')` |
| `BaseModel.fetch` | existe (TASK-API-0399, `api@6f35a612`) |
| `condition_values` | es helper del propio `ir_attachment.py` (`:45-58`): entra en esta unidad |

Las demás primitivas que el contrato usa están en el puerto:
`_check_access`, `_filtered_access`, `_has_field_access`, `_as_query`,
`search_fetch` (`src/orm/models.py`), `map_conditions`, `optimize_full`,
`iter_conditions` (`src/orm/domains.py`), `is_system`
(`src/orm/environments.py`). La unidad queda **admisible**.

## Contrato

- `SECURITY_FIELDS = ('res_model', 'res_id', 'create_uid', 'public',
  'res_field')` y `condition_values(model, field_name, domain)`, verbatim.
- `_check_access(operation)`: sobre lo que la ACL de modelo deja pasar,
  `public` siempre legible; con `res_model` y `res_id`, el acceso del
  registro adjuntado (`create`/`unlink` se comprueban como `write`); sin
  registro, sólo el administrador del sistema y el creador; con `res_field`,
  además el acceso al campo.
- `_inaccessible_comodel_records`: rinde los `(res_model, res_id)` que el
  usuario no puede tocar, con las dos excepciones de la fuente (modelo
  inexistente → prohibido; el propio usuario en `res.users` → permitido).
- `_search`: añade `res_field = False` salvo que el dominio nombre `id` o
  `res_field`, y el dominio de seguridad (`public`, registro propio sin
  `res_id`, y por modelo el `res_id in` de lo que el comodelo deja ver).
- `write`/`create`: rehúsan si el `res_model`/`res_id` nuevos apuntan a un
  registro inaccesible.
- `check(mode, values)`: en desuso desde 19.0, se porta con su aviso.

## Casos (RED), `tests/integration/base/test_ir_attachment_record_access.py`

1. Un interno con acceso al modelo pero sin acceso al registro (regla de
   registro) no lee su adjunto: `AccessError`.
2. El mismo usuario sí lee el adjunto de un registro que ve.
3. Un adjunto `public` se lee aunque el registro no sea accesible.
4. Sin `res_id`, sólo su creador (y el sistema) lo lee.
5. `search` no devuelve los adjuntos de registros inaccesibles.
6. `write` que reasigna un adjunto a un registro inaccesible rehúsa.
7. `condition_values` devuelve los valores del `in` sobre el campo, y `None`
   sin restricción.

## Anulaciones previstas

- sin la rama del registro adjuntado en `_check_access`: caen 1 y 6;
- sin la rama del creador: cae 4;
- sin el dominio de seguridad en `_search`: cae 5.

## Implementación y anulaciones (2026-11-25)

| Símbolo | Referencia | Prueba |
|---|---|---|
| `condition_values`, `SECURITY_FIELDS` | `odoo19c: odoo/addons/base/models/ir_attachment.py:42-58` | `test_condition_values_reads_the_in_values` |
| `IrAttachment._check_access`, `check` | `odoo19c: ir_attachment.py:504-588` | casos 1-4 |
| `IrAttachment._inaccessible_comodel_records` | `odoo19c: ir_attachment.py:590-618` | casos 1 y 6 |
| `IrAttachment._search` | `odoo19c: ir_attachment.py:620-708` | caso 5 |
| `IrAttachment.write` | `odoo19c: ir_attachment.py:710-722` | caso 6 |
| `_accessible_ids` (helper del puerto) | divergencia de mecanismo: la fuente usa `_filtered_access` del recordset del comodelo; un comodelo de Django (p. ej. `res.company`) no tiene recordset y la misma evaluación la hace su `AccessQuerySet` | casos 1, 5 y 6 |

Dos lecturas del puerto: un `create_uid` vacío se lee `None` (allá recordset
vacío), así que la regla del creador lo trata como «no es el usuario»; y
`_search` es `classmethod`, como `BaseModel._search`.

Los casos de rechazo **no discriminaban** en su primera versión: comprobaban
fuera del `user_scope`, y el rechazo lo producía la ACL de modelo sin
usuario. Ahora cada comprobación corre dentro del alcance del usuario.

Anulaciones, restauradas con `cmp`: sin `_inaccessible_comodel_records` caen
los casos 1 y 6; sin la regla del creador cae el 4; sin el dominio de
seguridad de `_search` cae el 5.

## Fila del plan

Se incorpora como `attachment-record-access-0397`, con sus obligaciones y su
`verify` reales. La fila `attachment-record-access` queda como registro del
bloqueo anterior (su `verify` era `false`); esta la reemplaza.

## Addendum — `check` no se porta (2026-11-25)

El F2 de `c9254c39` paró en `test_no_system_check_blocks_migrate` y en el
comando de cron: `models.E020`, *"The 'IrAttachment.check()' class method is
currently overridden"*. Django reserva `Model.check()` como el
`classmethod` de sus system checks, así que un método de instancia con ese
nombre bloquea `migrate`. La fuente lo tiene en desuso desde 19.0
(`ir_attachment.py:506`, *"Since 19.0, use check_access"*). Se retira y se
declara divergencia de mecanismo; el contrato vigente, `check_access`, sí
está portado.
