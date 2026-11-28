# `ir.model.data` sobre `BaseModel`: `create`, `write`, `unlink`, `copy_data`

Unidad previa de `designs/ir-module-terp-create.md`. TASK-API-0397.
Referencia medida en `odoo-tools@abe4040ec1`.

## Por qué ahora

`ir.module.module.create` (`odoo19c: odoo/addons/base/models/ir_module.py:771-783`)
termina con `self.env['ir.model.data'].create(module_metadata_list)`: una
llamada de ORM con una lista de dicts. Hoy `IrModelData` hereda de
`models.CopyMixin, TimeStampedModel`. No es `BaseModel`, así que
`env['ir.model.data']` devuelve la clase de Django
(`orm/environments.py:993-995`) y esa clase no tiene `create(vals_list)`. Su
docstring declara que `create` y `write` «colapsan en `save`». Esa divergencia
es justo la que impide portar al consumidor verbatim. Clase A: bloquea la
unidad siguiente.

## Contrato medido en la referencia

`odoo19c: odoo/addons/base/models/ir_model.py`:

- `:2218` `class IrModelData(models.Model)`.
- `:2313-2318` `copy_data(self, default=None)` sobre el recordset:
  `vals_list = super().copy_data(default=default)`, y por cada
  `(model, vals)` añade a `name` un sufijo `"_%04x"` aleatorio.
- `:2320-2325` `@api.model_create_multi create(vals_list)`: llama a
  `super().create`, y vacía `groups` si algún `vals['model'] == 'res.groups'`.
- `:2327-2332` `write(vals)`: `clear_cache()` (la familia `default`, la de
  `_xmlid_lookup`), luego `super().write`; vacía `groups` si
  `vals.get('model') == 'res.groups'`.
- `:2334-2339` `unlink()`: `clear_cache()`, vacía `groups` si algún registro
  existente tiene `model == 'res.groups'`, luego `super().unlink()`.

## Defecto heredado, medido

`IrModelData.save` (`ir_model.py:3208`) y `_clear_caches_after_unlink`
(`:3621`) comparan `self.model == 'base.ResGroups'`. La identidad que guardan
las filas es `registry.identity_of(ResGroups)` y vale `'res.groups'`. Medido
con `python -c "... identity_of(ResGroups)"` → `res.groups`. Por eso el vaciado
de `groups` nunca se dispara. La fuente compara con `'res.groups'`. Se corrige
en esta unidad (Cláusula 2).

## Lo que esta unidad hace

1. `class IrModelData(models.BaseModel, TimeStampedModel)`. Es la misma forma
   que `IrModule`. `CopyMixin` sale: `BaseModel` trae su propio
   `copy`/`copy_data` de recordset (`orm/models.py:9551`, `:9652`).
2. Porta `copy_data(default=None)` con la firma y el cuerpo de la fuente. La
   versión actual tiene la firma de `CopyMixin`, de un registro y con `seen`.
3. Porta `create`, `write` y `unlink` verbatim sobre `self.env.registry`.
4. `save`, `delete` y el `post_delete` siguen siendo el camino de Django
   (`objects.create`, `QuerySet.delete`), con la comparación corregida a
   `'res.groups'`.

## Pruebas (RED)

`tests/unit/base/test_ir_model_data_crud.py`:

- `env['ir.model.data'].create([...])` devuelve un recordset con las filas
  pedidas.
- `create` de una fila con `model='res.groups'` vacía `groups`. Una fila de
  otro modelo no la vacía.
- `write` vacía `default`.
- `unlink` vacía `default`, y además `groups` si la fila apunta a `res.groups`.
- `copy_data` devuelve una lista con el sufijo `_xxxx` en `name`.
- `save()` por Django de una fila `res.groups` vacía `groups`. Esto prueba el
  defecto heredado.

Anulaciones: retirar cada vaciado y cada sufijo tiene que tumbar exactamente
su caso.

## Medido

| Símbolo | Cambio |
|---|---|
| `IrModelData` | base `BaseModel` |
| `IrModelData.copy_data` | firma y cuerpo de la fuente |
| `IrModelData.create` | nuevo, verbatim |
| `IrModelData.write` | nuevo, verbatim |
| `IrModelData.unlink` | nuevo, verbatim |
| `IrModelData.save` | comparación `'res.groups'` |
| `_clear_caches_after_unlink` | comparación `'res.groups'` |
