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
