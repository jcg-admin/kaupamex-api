# ir.module.module, grupo B: recorridos de dependencias, `has_iap` y borrado

Sucesora de `designs/ir-module-group-a.md`. TASK-API-0397.

## Contrato medido en la referencia

`odoo19c: odoo/addons/base/models/ir_module.py`:

- `:532-555` `downstream_dependencies(self, known_deps=None, exclude_states=('uninstalled', 'uninstallable', 'to remove'))`:
  recordset de varios registros; vacío devuelve `self`; SQL sobre
  `ir_module_module_dependency` y `ir_module_module`; excluye `known_deps.ids
  or self.ids`; recursa sólo sobre lo nuevo (`missing_mods`).
- `:557-580` `upstream_dependencies(self, known_deps=None, exclude_states=('installed', 'uninstallable', 'to remove'))`:
  el simétrico.
- `:326` `has_iap = fields.Boolean(compute='_compute_has_iap')`, y
  `:333-335` `_compute_has_iap`.
- `:337-341` `_unlink_except_installed` (`@api.ondelete(at_uninstall=False)`).
- `:343-345` `unlink`: limpia la caché `stable` y delega.

## Lo que el puerto tenía y diverge

`downstream_dependencies`/`upstream_dependencies` se apoyaban en un
`_walk_dependencies` propio: sin `known_deps`, sólo para un registro
(`self.name`), con un queryset de Django como resultado y, en `upstream`, sin
`'to remove'` en los estados excluidos. Se portan los dos métodos de la fuente
y se retira `_walk_dependencies`.

El consumidor `_request_module_change` lee el resultado con
`.values_list('name', flat=True)`; pasa a `.mapped('name')`.

Conducta de la fuente que cambia un caso existente de
`tests/integration/base/test_ir_module_dependencies.py`: en un ciclo, la
fuente sólo excluye `known_deps.ids or self.ids` en cada nivel, así que el
módulo de origen puede volver a aparecer por la arista que cierra el ciclo.
El caso `test_a_module_never_reaches_itself` afirmaba lo contrario; se
corrige a la conducta de la fuente, citándola.

## Pruebas (RED)

`tests/unit/base/test_ir_module_group_b.py`: recordset de varios registros,
`known_deps`, defaults, `has_iap`, rechazo al borrar un módulo instalado y
borrado de uno desinstalado.
