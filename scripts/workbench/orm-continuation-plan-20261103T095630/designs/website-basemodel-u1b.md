# website-basemodel-u1b-0397 — `website`, `website.menu` y `website.page` sobre `BaseModel`

Fecha: 2026-11-22T14:56:48. Unidad U1b de la adopción de `website` (paraguas
`basemodel-adoption-0397`, TASK-API-0397). Depende de U0 y de U1a.

## Referencia

- `odoo19c: addons/website/models/website.py:435-451` —
  `_unlink_except_default_website` (`@api.ondelete`) y `unlink`
  (`_remove_attachments_on_website_unlink`, `companies._compute_website_id`).
- `odoo19c: addons/website/models/website_menu.py:163-177` — `unlink`
  (`clear_cache('templates')`, arrastra los menús de igual `url` bajo el
  menú principal) y `_unlink_except_master_tags` (`@api.ondelete`).
- `odoo19c: addons/website/models/website_page.py:148-162` — `unlink`:
  borra la vista que ninguna otra página usa y que no tiene hijas.

## Estado heredado (consumidor en `5f18868a`)

| Contrato | Consumidor | Clase |
|---|---|---|
| los tres son `BaseModel` | `TimeStampedModel` (y mixins en `website.page`) | DIVERGENT |
| `unlink` de los tres | `delete()` (`website.py:1377`, `website_menu.py:350`, `website_page.py:508`) | DIVERGENT |

Medido en U1a: `BaseModel.unlink` borra por queryset y no llama al
`delete()` de la instancia. Pasar los tres a `BaseModel` sin portar
`unlink` haría que borrar un sitio, un menú o una página se saltara esa
lógica en silencio.

Seis accesores inversos pasan a recordset cuando sus dos extremos son
`BaseModel`: `Website.menus`, `Website.pages`, `Website.rewrites`,
`WebsiteMenu.child`, `WebsitePage.menu_ids` y `WebsiteRoute.rewrites`.
Usos de API de gestor sobre ellos, verificados en el código:
`website_menu.py:317` (`child.filter(...).exists()`),
`website_menu.py:409`, `website.py:2130` y `:2142` (`child.all()`), y
`website_page.py:557` (`menu_ids.update(route=...)`).

## Cambio

1. Las tres clases añaden `models.BaseModel` a sus bases.
2. `unlink` en las tres con la forma de la fuente; se retiran sus
   `delete()`.
3. Los cinco usos de API de gestor sobre accesores que pasan a recordset se
   escriben con API de recordset (`filtered`, iteración, `write`).
4. El `save()` de los tres sigue corriendo: `BaseModel.write` y
   `create` terminan en él (medido en U1a).
5. `test_basemodel_reach.py`: `website` sigue en `PENDING` hasta U2
   (`settings.static.page`).

## Símbolos, referencia y prueba

Prueba: `tests/unit/website/test_website_basemodel_u1b.py`.

| Símbolo | Referencia | Prueba |
|---|---|---|
| `Website`, `Website.unlink`, `Website._unlink_except_default_website` | `odoo19c: addons/website/models/website.py:435-451` | `test_the_three_models_are_base_models` |
| `WebsiteMenu`, `WebsiteMenu.unlink` | `odoo19c: addons/website/models/website_menu.py:163-177` | `test_unlinking_a_menu_bumps_the_menu_epoch` |
| `WebsitePage`, `WebsitePage.unlink` | `odoo19c: addons/website/models/website_page.py:148-162` | `test_unlinking_a_page_unlinks_its_lonely_view` |

## Control de anulación (medido antes del commit de código)

Suite `tests/unit/website/test_website_basemodel_u1b.py`: 6 passed. Cada
guarda retirada por separado, restaurada desde copia y verificada con `cmp`:

| Anulación | Cae |
|---|---|
| `@api.ondelete` de `_unlink_except_default_website` comentado | sólo `test_the_default_website_cannot_be_unlinked` |
| `_bump_menu_epoch()` retirado de `WebsiteMenu.unlink` | sólo `test_unlinking_a_menu_bumps_the_menu_epoch` |
| `WebsitePage.unlink` renombrado | sólo `test_unlinking_a_page_unlinks_its_lonely_view` |

Contratos de recordset que la adopción cambió en las pruebas heredadas, con
la forma de la fuente: un Many2one nulo es un recordset vacío (falso), no
`None` (`_validate_parent_menu`); los accesores inversos son recordsets
(`list(site.menus)`, `page.menu_ids.mapped('route')`); el borrado de una
página es `unlink`; leer `website.menu`/`website` exige un usuario con ACL,
así que las dos pruebas sin usuario corren elevadas. `TestCoverage` mide
ahora los métodos **propios** de cada clase (`vars`), porque `getattr`
encontraba `delete`/`save` heredados de Django y no discriminaba.

## Funciones cuyo cuerpo cambia, con su referencia y su prueba

`scripts/check_reference_flow.py` exige que cada función de cuerpo cambiado
esté nombrada aquí antes del commit de código.

| Función | Referencia | Cambio | Prueba |
|---|---|---|---|
| `BaseModel.copy_data` (`src/orm/models.py`) | `odoo19c: odoo/orm/models.py:5406-5463` | `_fields` guarda cada Many2one bajo su nombre y bajo su `attname` (`website` y `website_id` son el mismo objeto). `copy_data` emitía las dos claves: el `default` sólo pisaba una y `create` tomaba el `False` de la otra; y la lista negra (`create_uid`, `parent_path`) dejaba pasar el alias (`create_uid_id`). Se recorre cada campo una vez, por su `name`, y `default` y lista negra se resuelven al nombre canónico. En la fuente cada campo tiene una sola clave | `test_copy_data_emits_each_field_once_and_honours_its_default` |
| `Website.copy_menu_hierarchy` y `copy_menu` | `odoo19c: addons/website/models/website.py:1147-1161` | `menu.copy({...})` como la fuente, en vez del clon campo a campo cuyo motivo («el ORM no trae `copy()`») dejó de ser cierto al adoptar `BaseModel`; recorre `for website in self` y no devuelve nada, como allá. `key` (campo propio y único) se fija en el `default` | `test_copy_menu_hierarchy_copies_the_template_tree` |
| `WebsiteMenu._validate_parent_menu` | `odoo19c: addons/website/models/website_menu.py:80-108` | el padre nulo es un recordset vacío: `while current_menu:` y `if parent_menu`, como la fuente; hijos y nietos sobre el recordset `child` | `test_hierarchy_deeper_than_two_levels_is_rejected`, `test_menu_with_children_cannot_hang_under_a_submenu`, `test_two_level_tree_is_valid` (`test_website_menu.py`) |
| `WebsiteMenu.get_tree` y `make_tree` | `odoo19c: addons/website/models/website_menu.py:266-287` | itera el recordset `node.child` (antes `.all()` del gestor) | `test_get_tree_serializes_the_site_menu` (`test_website_menu.py`) |
| `_canonical_field_name` (`src/orm/models.py`), nueva | sin contraparte: en `odoo19c: odoo/orm/models.py:5406-5463` cada campo tiene una sola clave en `_fields`; aquí resuelve un `attname` (`website_id`) al nombre del campo | `test_copy_data_emits_each_field_once_and_honours_its_default` |
| `_copy_data_blacklist` y `blacklist_given_fields` | `odoo19c: odoo/orm/models.py:5418-5434` | el FK de `_inherits` dado en `default` se reconoce por su nombre canónico (allí `parent_field in default`), y la lista negra se devuelve con nombres canónicos: una entrada por `attname` (`product_tmpl_id`) dejaba pasar el campo | `test_copy_data_emits_each_field_once_and_honours_its_default`; consumidores en el subconjunto derivado (`tests/unit/product`, 9767 passed) |
