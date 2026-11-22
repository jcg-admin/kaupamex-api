# U2 — `settings.static.page` sobre `BaseModel`

Unidad de `basemodel-adoption-0397`. Tras U1a y U1b, el único modelo con
`_name` de la app `website` fuera de `BaseModel` es `settings.static.page`
(`addons/website/models/static_page.py:31`). Al adoptarlo, `website` sale de
`PENDING` en `tests/unit/orm/test_basemodel_reach.py`.

## Referencia

Modelo **propio del L0**, sin contraparte: `grep -rnE "static[._]page"` sobre
`odoo19c: addons` y `odoo19c: odoo` → 0 modelos (lo declara ya
`static_page.py:41-43`). La forma la fija su análogo, `website.page`, que el
propio modelo cita para el mixin buscable:

- ACL: `odoo19c: addons/website/security/ir.model.access.csv:12` —
  `access_website_page_designer`, sólo `group_website_designer`, 1/1/1/1.
  Ninguna fila para público ni portal.
- Lectura pública: siempre elevada —
  `odoo19c: addons/website/models/ir_http.py:300`
  (`request.env['website.page'].sudo()`) y
  `odoo19c: addons/website/models/website_page.py:472,477`
  (`self.sudo().search_fetch(...)`).

## Decisión

1. `StaticPage(models.BaseModel, WebsiteSearchableMixin, TimeStampedModel)`.
   El modelo no sobreescribe `save`/`delete` (medido: `grep -nE "def
   (save|create|write|delete|unlink)\b"` → vacío), así que no hay CRUD que
   traducir.
2. Fila de ACL análoga a la de `website.page`:
   `access_settings_static_page_designer,Static Page Manager,
   model_settings_static_page,group_website_designer,1,1,1,1`, sin filas
   públicas — como la fuente.
3. Los controladores (`addons/website/controllers/main.py`) leen y escriben
   el modelo dentro de `sudo()`: las vistas públicas como
   `ir_http.py:300`; las de administración **después** de su
   `HasCapability`, que es la autorización de este árbol (mismo patrón que
   `base_setup/controllers/main.py:136`). Sin la elevación, un comprador
   autenticado recibiría 403 de la ACL aunque su capacidad lo autorice.
4. `page.versions` sigue siendo gestor: `StaticPageVersion` no tiene `_name`.

## Símbolos, referencia y prueba

Prueba: `tests/unit/website/test_website_basemodel_u2.py`.

| Símbolo | Referencia | Prueba |
|---|---|---|
| `StaticPage` sobre `BaseModel` | análogo `odoo19c: addons/website/models/website_page.py:29` | `test_static_page_is_a_base_model` |
| fila `access_settings_static_page_designer` | `odoo19c: addons/website/security/ir.model.access.csv:12` | `test_only_the_designer_group_has_access` |
| lecturas públicas elevadas en `controllers/main.py` | `odoo19c: addons/website/models/ir_http.py:300` | `test_the_public_list_serves_without_acl_rights` |
| `PENDING` sin `website` | `tests/unit/orm/test_basemodel_reach.py:48` | `test_the_pending_apps_are_exactly_the_measured_ones` |

*Ciega a:* el resto de controladores que consumen `StaticPage` a través de
`Website._search_with_fuzzy`; sus pruebas entran en el subconjunto derivado.
