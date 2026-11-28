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

## Medido

| Símbolo | Archivo | Fuente |
|---|---|---|
| `IrModule.downstream_dependencies` | `src/addons/base/models/ir_module.py` | `odoo19c: odoo/addons/base/models/ir_module.py:532-555` |
| `IrModule.upstream_dependencies` | ídem | `odoo19c: odoo/addons/base/models/ir_module.py:557-580` |
| `IrModule.has_iap` y `IrModule._compute_has_iap` | ídem | `odoo19c: odoo/addons/base/models/ir_module.py:326,333-335` |
| `IrModule._unlink_except_installed` | ídem | `odoo19c: odoo/addons/base/models/ir_module.py:337-341` |
| `IrModule.unlink` | ídem | `odoo19c: odoo/addons/base/models/ir_module.py:343-345` |
| `IrModule._request_module_change`: lee el resultado con `mapped('name')` | ídem | `odoo19c: odoo/addons/base/models/ir_module.py:532-555` |
| `IrModule._walk_dependencies`: retirado | ídem | — (sin contraparte en la fuente) |
| fixture `empty_module_catalog`: borra bajo `module_uninstall` | `tests/conftest.py` | `odoo19c: odoo/orm/decorators.py:139-149` |

Los `IN %s` con tupla de la fuente son `= ANY(%s)` y `<> ALL(%s)` con lista:
psycopg 3 no adapta tuplas (cabecera de `_field_condition_to_sql` en
`orm/fields.py`).

Medido al ejecutar, y corrige tres expectativas escritas antes de medir:

- El `JOIN ir_module_module m ON (d.module_id=m.id)` (`:544`, `:569`) sólo
  alcanza módulos con dependencias propias: hacia arriba nunca aparece un
  módulo sin `depends`, como `base`. Corrige
  `test_upstream_reaches_only_modules_with_dependencies` (antes esperaba
  `base`) y dos casos del grupo B.
- `m.id NOT IN known_deps.ids or self.ids` (`:548`) deja fuera a `self` en el
  primer nivel: `(a | b).downstream_dependencies()` no devuelve `b`.
- En un ciclo vuelve el origen (`:573-574`):
  `test_a_cycle_brings_the_origin_back` sustituye a
  `test_a_module_never_reaches_itself`, que afirmaba lo contrario.

`TestWalkDependencies` corre como `SUPERUSER_ID`, el entorno de las pruebas de
la fuente: los dos métodos leen por `self.env`.

El fixture `empty_module_catalog` vaciaba el catálogo con un `delete()` que
ahora pasa por `_unlink_except_installed`. Vaciar módulos instalados es lo que
hace la desinstalación, así que borra bajo `module_uninstall`, el equivalente
de `MODULE_UNINSTALL_FLAG` que `orm.models._run_ondelete_on_delete` ya lee.

Pruebas: `tests/unit/base/test_ir_module_group_b.py` (8 casos; RED 7 de 8, el
octavo es el control del borrado permitido) y
`tests/integration/base/test_ir_module_dependencies.py`.

Anulación (copias restauradas y comparadas con `cmp`), cada pieza aparte:
sin excluir `known_deps.ids or self.ids` en `downstream` cae el caso del
recordset (1 de 33); sin la guarda de `_unlink_except_installed`, el del
rechazo (1 de 33); con `has_iap` siempre falso, el de `has_iap` (1 de 33); sin
`module_uninstall` en el fixture, los 24 casos que lo usan dan error de
preparación.
