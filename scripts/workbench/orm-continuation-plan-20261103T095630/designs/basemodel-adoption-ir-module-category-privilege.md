# Adopción de BaseModel: ir.module.category + res.groups.privilege — análisis previo (basemodel-adoption-0397)

Estado: **no implementado**. Primer intento revertido sin commit el
2026-11-25; este documento guarda lo medido para que la unidad arranque de aquí.

## Referencia

- `odoo19c: odoo/addons/base/models/ir_module.py:76` — `class IrModuleCategory(models.Model)`.
- `odoo19c: odoo/addons/base/models/res_groups_privilege.py:4` — `class ResGroupsPrivilege(models.Model)`.
- ACL (`ir.model.access.csv:22-24`): `res.groups.privilege` lectura para
  `group_user` y total para `group_erp_manager`; `ir.module.category` lectura
  **sólo** para `group_erp_manager`.

## Lo que el cambio de base destapa

Un `BaseModel` comprueba la ACL al **leer un registro** —`check_access('read')`,
`src/orm/models.py:10627-10635`—, también cuando se llega a él recorriendo un
`Many2one` desde otro modelo (`ResGroups` → `privilege` → `category`) dentro del
alcance de un usuario. El gestor **no** filtra las consultas: una sonda de
2026-11-25 ejecutó, bajo un usuario sólo con `base.group_user`,
`IrCronTrigger.objects.filter(...)`, `IrCronProgress.objects.filter(...)`,
`cron._trigger(...)` y `cron._add_progress()` sobre los dos modelos ya
adoptados (ACL `group_system`), y los cuatro devolvieron filas sin error. (La
primera versión de este documento atribuía el rechazo al gestor; la sonda la
desmiente.) Con sólo cambiar las dos bases, el subconjunto derivado (26
archivos) dio **11 failed, 1 error** con
`PermissionDenied: No tiene permiso para consultar registros de «Application»`
y de «Privileges», y conjuntos vacíos donde se esperaba la fila:

- `tests/integration/base/test_res_groups_port.py` — `TestOrderByFullName` (2) y `TestTheViewHierarchy` (2).
- `tests/integration/base/test_module_catalog_database.py::test_refresh_populates_category_relation_and_preserves_manifest_path`.
- `tests/integration/base/test_module_category_tree.py::test_nested_path_creates_each_level_and_its_external_identity`.
- `tests/unit/orm/test_one2many.py::TestItResolvesToTheDjangoReverse` (2).
- `tests/unit/orm/test_load.py` — `test_a_second_load_of_the_same_external_id_updates`, `test_a_database_id_column_updates_that_record`.
- `tests/integration/mail/test_mail_groups_data.py::test_the_sales_manager_implies_the_canned_response_admin`.
- ERROR `tests/unit/website/test_website_security_groups.py::test_public_implies_the_controller_expose_group`.

La fuente lee estos modelos con privilegio donde un usuario cualquiera llega:
`_compute_full_name` itera `zip(self, self.sudo())` y lee
`group1.privilege_id.name` (`odoo19c: res_groups.py:123-129`), y la jerarquía
de grupos busca con `self.sudo().search([], order='id')` (`:366`). El porte
lee por el gestor sin `sudo`. **La unidad exige portar esas lecturas
privilegiadas en cada consumidor antes de cambiar la base**; cada fallo de la
lista se cierra con su contraparte de la fuente, no con un `sudo` genérico.

## Hallazgo lateral: la guarda de recursión de la categoría

`IrModuleCategory._check_parent_not_circular` recorre `while current is not
None`. Bajo `BaseModel` un `Many2one` vacío se lee como recordset vacío, no
`None`: en un alta, `current.pk` (None) es igual a `self.pk` (None) y la guarda
rehúsa toda categoría nueva («No se pueden crear categorías recursivas», al
parsear `addons/auto_backup/security/user_groups.xml:18`). La forma correcta
es la de la fuente, `self._has_cycle()` bajo `@api.constrains('parent_id')`
(`odoo19c: ir_module.py:102-105`), o como mínimo `while current:`.

## Condición de cierre

Portar las lecturas privilegiadas de `res_groups` (full name, jerarquía de
vista, definiciones), del refresco del catálogo y de `load`, cada una citando
su línea de la fuente; luego cambiar las dos bases y la guarda, y exigir el
subconjunto de los 26 archivos en verde más F2.
