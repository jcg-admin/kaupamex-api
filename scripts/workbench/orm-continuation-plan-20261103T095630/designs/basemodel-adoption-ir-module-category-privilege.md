# Adopción de BaseModel: ir.module.category + res.groups.privilege — análisis previo (basemodel-adoption-0397)

Estado: **implementado el 2026-11-26** (sección «Implementación», al final).
El primer intento, del 2026-11-25, se revirtió sin commit; lo medido entonces
queda abajo como el punto de partida.

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

## Implementación (2026-11-26)

Cambio de base: `IrModuleCategory(models.BaseModel, TimeStampedModel)` y
`ResGroupsPrivilege(BaseModel, TimeStampedModel)`; sin migración
(`./kaupamex-bin makemigrations base --check --dry-run` → sin cambios).

Funciones cuyo cuerpo cambia, con su referencia y su prueba:

- `ResGroups._compute_full_name` lee el privilegio bajo `sudo()`, como el
  `zip(self, self.sudo())` de `odoo19c: odoo/addons/base/models/res_groups.py:123-129`.
  Prueba: `tests/unit/base/test_category_privilege_basemodel.py::test_full_name_reads_the_privilege_for_a_user_who_cannot`.
- `ResGroups._get_view_group_hierarchy` construye `privilege_ids` de cada
  categoría con `sorted`/`filtered` sobre el recordset, como
  `category.privilege_ids.sorted(...).filtered(...).ids` de `odoo19c: res_groups.py:353-359`;
  las tres claves de `groups` se parten en líneas de 79. Prueba:
  `tests/integration/base/test_res_groups_port.py::TestTheViewHierarchy`.
- `IrModuleCategory._check_parent_not_circular` recorre `while current:`: el
  `Many2one` vacío es un recordset vacío. Referencia: `_check_parent_not_circular`
  (`odoo19c: odoo/addons/base/models/ir_module.py:102-105`). Prueba: toda carga
  de categorías por XML (`addons/auto_backup/security/user_groups.xml:18` rehusaba).

Consumidores portados (las pruebas de la fuente corren como superusuario; la
instalación de producción ya corre como `SUPERUSER_ID`, `src/modules/loading.py:261`):

- `sudo()` en el instalador de prueba de `test_mail_groups_data.py` y
  `test_website_security_groups.py`, en las dos de `TestTheViewHierarchy`
  y en las dos de `test_load.py`; fixture elevado (`_elevated`, el patrón de
  `tests/unit/analytic/`) en `test_module_catalog_database.py` y
  `test_module_category_tree.py`.
- Sujeto «modelo de Django sin BaseModel»: `res.partner` (FK `parent`, reverso
  `children`, indexado) en `test_one2many.py::TestItResolvesToTheDjangoReverse`
  y en `test_index_method.py`.
- Deuda de estilo pagada: el gate fija cada sentencia por su posición en el
  módulo, así que el `import` nuevo de `test_res_groups_port.py` convertía en
  nuevas sus diez líneas largas heredadas; se partieron.

Subconjunto derivado (26 archivos más `test_one2many.py` y
`test_index_method.py`, `-n 4`): **265 passed**.

## Anulaciones

- Sin el `sudo()` de `_compute_full_name`: cae exactamente
  `test_full_name_reads_the_privilege_for_a_user_who_cannot` (1 de 3).
- `ResGroupsPrivilege` de vuelta a `TimeStampedModel`: cae exactamente
  `test_category_and_privilege_are_basemodel[ResGroupsPrivilege]` (1 de 3).

Ambas restauradas y verificadas con `cmp`.

## F2 sobre `2285f76a`: dos consumidores fuera del subconjunto

El F2 se detuvo (`maxfail=1`) con 4664 passed, 1 failed y 1 error, los dos de
la misma clase que ya se portó: `test_auto_backup_basemodel_acl.py` instala el
manifiesto con `load_data` sin superusuario (la escritura de la categoría se
rehúsa) y `test_res_users_has_group.py::TestSeededCatalog::test_both_privileges_are_wired`
lee `group.privilege.name` sin usuario. El patrón del subconjunto derivado no
nombraba `.privilege` ni `load_data`; se amplió a
`\.privilege\b|res\.groups\.privilege|ResGroupsPrivilege|ir\.module\.category|IrModuleCategory|load_data\(|_security_data|security\.xml|user_groups\.xml`
(46 archivos): 404 passed, 1 failed, 3 errors, sólo esos dos archivos. Con el
instalador y la lectura bajo `sudo()`, los dos dan 48 passed.
