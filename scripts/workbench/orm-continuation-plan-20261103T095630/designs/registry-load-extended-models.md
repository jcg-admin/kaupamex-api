# `Registry.load` nombra también los modelos que el módulo extiende

Creado: 2026-11-14T09:06:53 (UTC). TASK-API-0485.

## Contrato de la referencia (odoo-tools `abe4040ec1`)

- `Registry.load(module)` (`odoo/orm/registry.py:350-380`): *"return the
  names of the directly modified models"*; recorre
  `MetaModel._module_to_models__[module.name]`, que tiene **toda** clase del
  módulo, la que define un modelo y la que lo extiende con `_inherit`.
- `load_module_graph` (`odoo/modules/loading.py:187-194`): `model_names =
  registry.load(package)`, luego `registry.descendants(model_names, '_inherit',
  '_inherits')`, y `init_models` con `{'module': package.name}`. Así cada
  modelo que el módulo extiende recibe el identificador `<módulo>.model_<x>`
  (`ir.model._reflect_models`), y los CSV de seguridad lo nombran sin
  calificar (`model_hr_job` en `hr_recruitment`).

## Medido aquí (`1926ff23`)

- `Registry.load` (`src/orm/registry.py:2186`) devuelve sólo los modelos cuyo
  `app_label` es el módulo.
- `modules.loading.load_modules` no lo llama: filtra `registry.models` por
  `app_label` y no pasa por `descendants`.
- Las extensiones se declaran con `extend_model`, que ya conoce el addon que
  extiende (`calling_module()`) pero no lo registra.
- Consecuencia: 2 filas del CSV de `hr_recruitment` (`model_hr_job`) no tienen
  destino; la base no tiene `hr_recruitment.model_hr_job`.

## Decisión

1. `extend_model` anota en `orm.registry.MODELS_EXTENDED_BY_MODULE` el
   `_name` del modelo para el addon que lo extiende (≙ que la clase de
   extensión quede en `_module_to_models__` de su módulo).
2. `Registry.load` devuelve los del `app_label` más los extendidos.
3. `load_modules` toma sus modelos de `registry.load` y `descendants(...,
   '_inherit', '_inherits')`, como la fuente.

## Pruebas

`Registry.load('hr_recruitment')` incluye `hr.job`; tras `load_modules` existe
`hr_recruitment.model_hr_job`. Anulación: sin la anotación de `extend_model`
caen las dos.
