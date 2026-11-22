# website-security-groups-0397 — los grupos y la ACL de `website`

Fecha: 2026-11-22T12:22:53. Unidad U0 de la adopción de `website` sobre `BaseModel`
(paraguas `basemodel-adoption-0397`, TASK-API-0397). Investigación:
informe de solo lectura de un subagente, verificado aquí punto por punto.

## Referencia

- `odoo19c: addons/website/security/website_security.xml:3-24` — el
  privilegio `res_groups_privilege_website` (categoría
  `base.module_category_website`) y los grupos
  `group_website_restricted_editor` y `group_website_designer`, que implica
  al primero y a `base.group_sanitize_override`, lo implica
  `base.group_system` y nace con `base.user_root` y `base.user_admin`.
- `odoo19c: addons/website/security/website_security.xml:94-104` —
  `website_page_controller_expose`, implicado por `base.group_public` y
  `base.group_portal`.
- `odoo19c: addons/website/security/ir.model.access.csv` — 49 filas.

## Estado heredado (consumidor en `da5c0620`)

| Contrato | Consumidor | Clase |
|---|---|---|
| grupos de `website` | ninguno; sólo nombrados en prosa (`ir_ui_view.py:189`, `website_page.py:361`) | ABSENT |
| `security/ir.model.access.csv` en `data` | no hay `addons/website/security/` ni clave `data` | ABSENT |

Prosa heredada medida:

- El informe decía que `base.module_category_website` no existe. Falso: la
  deriva la migración `base/0090` de la categoría del manifiesto
  (`Website/Website`); medido en `orm_x2hokp_qa`,
  `ir_model_data` la tiene (`res_id` 2733). El grep estático no la ve.
- `base.user_admin` sí falta (0 filas); `base.group_sanitize_override`
  existe.
- El comentario de `depends` del manifiesto dice que el modelo `website`
  «todavía no está portado»; `addons/website/models/website.py:654` lo
  declara. Se corrige.

## Cambio

1. `addons/website/security/website_security.xml`: el privilegio, los dos
   grupos y `website_page_controller_expose` con sus implicaciones. Sin
   `base.user_admin` en `user_ids`, porque este árbol no lo siembra.
2. `addons/website/security/ir.model.access.csv`: las 16 filas cuyos
   modelos existen aquí (`website` 4, `website.menu` 4,
   `website.rewrite` 2, `website.page` 1, `website.route` 1,
   `website.configurator.feature` 1, `ir.ui.view` 2, `ir.asset` 1), copia
   fiel. Las otras 33 nombran modelos de `website` no portados
   (`website.controller.page`, `website.seo.metadata`, `website.visitor`,
   `website.page.properties`, `website.page.properties.base`,
   `website.track`, `website.snippet.filter`, `website.robots`,
   `website.technical.page`, `website.custom_blocked_third_party_domains` y
   los `theme.*`); entran con la unidad que porte cada modelo.
3. El manifiesto declara `data`: primero el XML, después el CSV.

## Fuera de esta unidad (sucesoras)

- Las `ir.rule` de `website_security.xml:25-91,106-111`: filtran por
  campos de `website.menu`, `website.page` e `ir.ui.view`
  (`group_ids`, `website_published`, `visibility`) cuya presencia hay que
  medir — sucesora **`website-ir-rules-0397`**.
- `base.user_admin` en `group_website_designer` cuando la base lo siembre.
- Las filas de `website_sale` que se omitieron por faltar estos grupos
  (`addons/website_sale/security/res_groups.xml:2-18`) — sucesora
  **`website-sale-website-groups-0397`**.
- U1 (los seis modelos con contraparte a `BaseModel`) y U2
  (`settings.static.page`, propio).

## Símbolos, referencia y prueba

Prueba: `tests/unit/website/test_website_security_groups.py`.

| Símbolo | Referencia | Prueba |
|---|---|---|
| `group_website_designer`, `group_website_restricted_editor`, `res_groups_privilege_website` | `odoo19c: addons/website/security/website_security.xml:3-24` | `test_the_designer_group_implies_the_restricted_editor`, `test_system_implies_the_designer` |
| `website_page_controller_expose` | `odoo19c: addons/website/security/website_security.xml:94-104` | `test_public_implies_the_controller_expose_group` |
| `ir.model.access.csv` | `odoo19c: addons/website/security/ir.model.access.csv` | `test_the_acl_rows_of_the_ported_models_are_loaded` |
| `__manifest__` (`data`) | `odoo19c: addons/website/__manifest__.py` | `test_the_acl_rows_of_the_ported_models_are_loaded` |
