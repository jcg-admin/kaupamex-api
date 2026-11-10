# TASK-API-0513 — `_get_placeholder_filename` en todo modelo

Referencia: odoo-tools `abe4040ec1a45beee90fb694e4eae4453e46b389`.

## Contrato

- `BaseModel._get_placeholder_filename(self, field)`
  (`odoo19c: odoo/orm/models.py:6999-7004`): devuelve `False`; un modelo
  lo sobrescribe para dar la ruta de su imagen de relleno.
- `ir.binary._get_image_stream_from` lo llama **directo** sobre el
  registro cuando no hay marcador explícito
  (`odoo19c: odoo/addons/base/models/ir_binary.py:212-213`).
- Consumidores en la fuente: `product.product`, `product.template`
  (cierran con `super()`), y aquí `onboarding.onboarding.step`.

## Estado de este árbol

- El método no existe en ninguna base: `ir_binary.py:267` lo busca con
  `getattr(record, '_get_placeholder_filename', None)`.
- `onboarding_onboarding_step.py:293-310` declara la divergencia: *"Aquí
  ese eslabón no existe … devolver None cede al default"*.

## Decisión

El registro de `ir_binary` puede ser un modelo de Django sin recordset, así
que el método se cuelga de `django.db.models.Model` como los métodos de
motor (`_flush`, `modified`, …), no sólo de `BaseModel`. Con la base en su
sitio: `ir_binary` lo llama directo y el paso de onboarding cierra con
`super()`, retirando su divergencia.

## Casos (RED)

1. Un modelo de Django sin sobrescritura devuelve `False`.
2. Un recordset de `BaseModel` devuelve `False`.
3. El paso de onboarding devuelve su ruta para `step_image` y, para otro
   campo, lo que da la base (`False`).

Anulación prevista: retirar el método de la base tumba 1, 2 y la mitad de
3 (el `super()`); la ruta de `step_image` no depende de él.

## RED, GREEN, anulación y regresión (2026-11-10)

- RED sobre `051ca50e`: `3 failed` — `AttributeError` en el modelo de
  Django y en el recordset; el paso de onboarding devolvía `None`.
- GREEN: `3 passed`.
- Anulación: sin la asignación a `Model` caen exactamente los 3 (el 3 por
  el `super()`); restaurada y verificada con `cmp`.
- Regresión derivada (`onboarding`, `base` unitarias e integración,
  `mail`, `html_editor`): `1 failed, 2844 passed`. El fallo era la
  expectativa congelada de la divergencia retirada
  (`test_any_other_field_falls_back_to_the_default` exigía `None`); se
  ajusta a la referencia (`False`) y queda `26 passed` en su archivo.
