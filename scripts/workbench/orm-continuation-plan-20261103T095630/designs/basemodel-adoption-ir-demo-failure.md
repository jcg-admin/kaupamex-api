# ir.demo_failure e ir.demo_failure.wizard como TransientModel

Unidad de `basemodel-adoption-0397` (TASK-API-0397). Mapa de consumidores
preparado por un subagente de sólo lectura y verificado contra la fuente.

## Fuente medida

`odoo19c: odoo/addons/base/models/ir_demo_failure.py:4-32`: los dos son
`models.TransientModel`.

- `ir.demo_failure` (`:4-13`): `_description = 'Demo failure'`;
  `module_id` (requerido), `error`, `wizard_id`.
- `ir.demo_failure.wizard` (`:16-32`): `_description = 'Demo Failure
  wizard'`; `failure_ids` One2many, `failures_count` calculado sin almacenar
  (`:23-26`) y `done()`, que devuelve `ir.module.module.next()` (`:28-31`).

ACL (`odoo19c: odoo/addons/base/security/ir.model.access.csv:128-129`):
`group_system`, 1,1,1,0 para los dos. Sin reglas.

## Puerto antes de la unidad

`src/addons/base/models/ir_demo_failure.py`: los dos heredan de
`TimeStampedModel`. Su docstring lo justifica con *«aquí `TransientModel` es
`managed = False` (sin tabla)»*, y **esa prosa ya no se sostiene**:
`TransientModel` declara tabla y su `_transient_vacuum`
(`src/orm/models_transient.py:1-32,117`). `failures_count` es una
propiedad; `done()` no se porta.

Consumidores: `src/modules/loading.py:189-191` escribe con
`failure.objects.using(using).create(...)` dentro de `env(su=True)`;
`tests/unit/modules/test_demo_failure_storage.py` y
`tests/unit/modules/test_loading_demo.py` (que parchea
`IrDemoFailure.objects.using`) y la migración `0089` lo usan.

## Cambio

1. Los dos derivan de `TransientModel`, con `_name` y `_description`.
2. `failures_count` como campo calculado sin almacenar.
3. Las dos filas de ACL y su siembra.
4. `done()` se porta, verbatim: devuelve
   `self.env['ir.module.module'].next()`. Para eso se porta antes
   `IrModuleModule.next` en `src/addons/base/models/ir_module.py`
   (`odoo19c: odoo/addons/base/models/ir_module.py:582-597`), que lanza la
   acción del paso abierto con `action_launch`. Las dos dependen de que
   `ir.actions.*` resuelva en el entorno, que es la unidad
   `designs/ir-actions-family-basemodel-and-inheritance.md`; esta unidad va
   **después** de aquélla, no en su lugar.

**Corregido por directiva del ejecutor (2026-11-26).** La versión anterior
declaraba `done()` pendiente porque `next()` no estaba portado. Eso
incumple `porte-completo-no-parcial.md`: la ausencia de una pieza de la
referencia no es un desenlace para el símbolo que la usa; se porta la
pieza.

## Controles previstos

- un fallo y su asistente se crean y el asistente cuenta sus fallos;
- el barrido transitorio los recoge;
- un usuario interno sin `group_system` no los lee;
- `loading.py` sigue registrando fallos.

Prueba: `tests/unit/base/test_ir_demo_failure_transient.py`.
