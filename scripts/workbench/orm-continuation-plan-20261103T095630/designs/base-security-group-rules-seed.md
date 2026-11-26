# Sembrar reglas de `base` con grupos y permisos (habilitador de basemodel-adoption-0397)

## Por qué

Los modelos de `base` que quedan fuera de `BaseModel` y llevan reglas en la
fuente —`ir.filters`, `ir.default`, `ir.embedded.actions`, `ir.ui.view.custom`,
`res.device`, `res.device.log`, `properties.base.definition`— las declaran
**por grupo** y con permisos por operación en
`odoo19c: odoo/addons/base/security/base_security.xml` (26 `ir.rule`; p. ej.
`ir_filters_employee_rule`, `:86-95`: `[('user_ids','in',[False,user.id])]`
para `base.group_user`). El motor ya las evalúa como la fuente —globales con
AND, de grupo con OR (`src/addons/base/models/ir_rule.py:31-38`, `:406-428`)—
y `IrRule` declara `groups` y los cuatro `perm_*` (`:208-227`). Lo que falta es
**sembrarlas**: `base_security._seed` sólo escribe la regla multicompañía
global (`src/addons/base/security/base_security.py:37-46`).

GapClass: B (habilitador con ruta correcta disponible). ExecuteNow: yes.

## Search Existing

- `src/addons/base/security/base_security.py::_seed` — dueño de las reglas de
  `base`; lo reutilizan `addons/sale/security/ir_rules.py` y
  `addons/sale_subscription/security/ir_rules.py`. Sólo admite
  `(nombre, modelo)` y dominio multicompañía fijo. → **EXTEND**.
- El cargador XML (`src/tools/convert.py::_tag_record`) siembra reglas con
  grupos para los addons con `security/*.xml` (crm, account, fleet…). `base`
  no carga datos por XML: su ACL y sus reglas las siembran migraciones
  (`ir_model_access.py`, docstring). Llevar `base` al cargador cambiaría su
  arranque entero; se descarta para esta unidad.

## Diseño

`_seed(IrRule, rules, using)` acepta, además de la tupla actual, una entrada
`dict` con las claves del registro de la fuente: `name`, `model`,
`domain_force`, `groups` (identificadores externos, `'base.group_user'`), y
`perm_read`/`perm_write`/`perm_create`/`perm_unlink` (por defecto `True`, como
el campo). Idempotente por `name`: `get_or_create` y, para los grupos, `set`
sobre los resueltos por `IrModelData`. Las tuplas existentes siguen igual, así
que `sale` y `sale_subscription` no cambian.

Cada regla de un modelo entra **en la unidad que adopta ese modelo**, con su
migración de datos (el patrón de `0122_seed_derived_acl`): sembrarla antes no
filtra nada, porque un modelo de Django no pasa por `ir.rule`, y sembrarla
después de adoptar deja el modelo con ACL pero sin el acotamiento por fila de
la fuente.

## Pruebas

- Una regla de grupo sembrada queda con sus grupos y sus permisos.
- La entrada en tupla sigue sembrando la regla multicompañía global.
- Sembrar dos veces no duplica ni cambia grupos.
- Anulación: sin el `set` de grupos, la regla queda global y cae la prueba de
  grupos.
