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
3. **Los controladores no cambian — corregido tras medir.** La primera
   versión de este diseño los elevaba con `sudo()`. Medido con el control
   de anulación: el controlador público responde 200 con y sin la
   elevación, porque `AccessQuerySet` no comprueba la ACL al iterar por el
   gestor (`StaticPage.objects.get(...)`); la comprueban los métodos del ORM
   (`create`, `write`, `fetch`, `search` — `src/orm/models.py`
   `check_access`). Los controladores de `StaticPage` usan el gestor, así
   que un `sudo()` ahí sería un mecanismo sin efecto medible. La elevación
   entra cuando pasen a consultar por el ORM, que es la forma de la fuente
   (`ir_http.py:300`).
4. `page.versions` sigue siendo gestor: `StaticPageVersion` no tiene `_name`.

## Símbolos, referencia y prueba

Prueba: `tests/unit/website/test_website_basemodel_u2.py`.

| Símbolo | Referencia | Prueba |
|---|---|---|
| `StaticPage` sobre `BaseModel` | análogo `odoo19c: addons/website/models/website_page.py:29` | `test_static_page_is_a_base_model` |
| fila `access_settings_static_page_designer` | `odoo19c: addons/website/security/ir.model.access.csv:12` | `test_only_the_designer_group_has_access` |
| el controlador público sigue sirviendo | `odoo19c: addons/website/models/ir_http.py:300` (allí elevado; aquí consulta por el gestor) | `test_the_public_page_still_serves` |
| `PENDING` sin `website` | `tests/unit/orm/test_basemodel_reach.py:48` | `test_the_pending_apps_are_exactly_the_measured_ones` |

*Ciega a:* el resto de controladores que consumen `StaticPage` a través de
`Website._search_with_fuzzy`; sus pruebas entran en el subconjunto derivado.

## Control de anulación

- Fila de ACL retirada del CSV: cae sólo
  `test_only_the_designer_group_has_access`. La prueba borra antes la fila
  que dejó una carga anterior; sin ese borrado la anulación no discriminaba
  (la base reutilizada ya la tenía).
- `sudo()` retirado del controlador público: no cae nada — por eso no se
  añade (punto 3).
