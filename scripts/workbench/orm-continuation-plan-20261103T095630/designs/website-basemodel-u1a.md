# website-basemodel-u1a-0397 — `website.configurator.feature`, `website.route` y `website.rewrite` sobre `BaseModel`

Fecha: 2026-11-22T13:09:58. Unidad U1a de la adopción de `website`
(paraguas `basemodel-adoption-0397`, TASK-API-0397). Depende de
`website-security-groups-0397` (U0), que trajo sus filas de ACL.

## Referencia

- `odoo19c: addons/website/models/website_configurator_feature.py:9-13` —
  cabecera de `website.configurator.feature`.
- `odoo19c: addons/website/models/website_rewrite.py:13-17` — cabecera de
  `website.route`; `:38-57` `_refresh` crea con `self.create(tocreate)` y
  retira con `find.unlink()`.
- `odoo19c: addons/website/models/website_rewrite.py:60-62` — cabecera de
  `website.rewrite`; `:90-131` `_check_url_to` como
  `@api.constrains('url_to', 'url_from', 'redirect_type')`; `:132-135`
  `_compute_display_name` sobre el recordset; `:137-157` `create`, `write` y
  `unlink`, que invalidan el routing si el tipo antes o después es 308/404.

## Estado heredado (consumidor en `b483fa63`)

| Contrato | Consumidor | Clase |
|---|---|---|
| los tres son `BaseModel` | derivan de `TimeStampedModel` | DIVERGENT |
| atributos de clase | ya verbatim (medido en el informe y en el código) | ALIGNED |
| `create`/`write`/`unlink` de `website.rewrite` | `save()`/`delete()` (`website_rewrite.py:354-382`) | DIVERGENT |
| `_check_url_to` como restricción | llamado a mano desde `save()` | DIVERGENT |
| `_compute_display_name` sobre el recordset | sobre una fila, con `return` | DIVERGENT |

Medido en el ORM de este árbol: `BaseModel.write` escribe cada registro con
`RecordLoaderMixin.write`, que termina en `save(update_fields=...)`
(`src/orm/models.py:3190`), pero `BaseModel.unlink` borra con
`rows.delete()` (`:9119`), un borrado de queryset que no llama al
`delete()` de cada instancia. Adoptar `BaseModel` sin portar `unlink` haría
que borrar un rewrite 308/404 dejara de invalidar el routing, en silencio.

Consumidores: fuera de los propios modelos sólo `website.py:1882` (lee
`website.rewrite` con `objects.filter`, sin cambio de semántica).

## Cambio

1. Las tres clases derivan de `(models.BaseModel, TimeStampedModel)`.
2. `website.rewrite`: `create(vals_list)`, `write(vals)` y `unlink()` con la
   forma de la fuente; `_check_url_to` pasa a `@api.constrains` y recorre el
   recordset; `_compute_display_name` con `@api.depends('redirect_type')`
   sobre el recordset. Se retiran `save()` y `delete()`.
3. `website.route._refresh` crea con `create` y retira con `unlink`, como
   la fuente.

## Símbolos, referencia y prueba

Prueba: `tests/unit/website/test_website_basemodel_u1a.py`.

| Símbolo | Referencia | Prueba |
|---|---|---|
| `WebsiteConfiguratorFeature` | `odoo19c: addons/website/models/website_configurator_feature.py:9-13` | `test_the_three_models_are_base_models` |
| `WebsiteRoute`, `WebsiteRoute._refresh` | `odoo19c: addons/website/models/website_rewrite.py:38-57` | `test_refresh_creates_and_unlinks_routes` |
| `WebsiteRewrite.create`, `WebsiteRewrite.write`, `WebsiteRewrite.unlink` | `odoo19c: addons/website/models/website_rewrite.py:137-157` | `test_unlinking_a_308_invalidates_the_routing`, `test_writing_into_a_404_invalidates_the_routing` |
| `WebsiteRewrite._check_url_to` | `odoo19c: addons/website/models/website_rewrite.py:90-131` | `test_url_to_slash_is_rejected` |
| `WebsiteRewrite._compute_display_name` | `odoo19c: addons/website/models/website_rewrite.py:132-135` | `test_display_name_joins_type_and_name` |

## Control

Con `unlink` retirado (vuelve el borrado de queryset de `BaseModel`) cae
`test_unlinking_a_308_invalidates_the_routing`.

## Medido al ejecutar (antes de integrar)

- `_invalidate_routing` llamaba a `get_resolver.cache_clear()`. En Django 6
  `get_resolver` es una función sin `cache_clear` (la caché vive en
  `_get_cached_resolver`): el primer 308 creado por el ORM reventó con
  `AttributeError`. Defecto heredado que ningún test alcanzaba; se limpia
  con `django.urls.clear_url_caches()`, la API pública.
- `test_url_to_slash_is_rejected` usaba un 301; la regla de `'/'` es sólo
  del 308 (`odoo19c: addons/website/models/website_rewrite.py:103-110`).
- La primera anulación (sin `unlink`) **no discriminaba**, por dos causas:
  1. `unlink` empieza con `flush_all`; el `write` diferido del registro
     recién creado (308) también invalidaba. El test vuelca antes de medir.
  2. El espía era un `mock.patch.object` sobre `WebsiteRewrite`. Los
     colectores de métodos marcados (`orm.registry.ondelete_methods`)
     buscan en la clase atributos con `_ondelete`; un doble de
     `unittest.mock` responde a cualquiera y el borrado lo llamaba como
     comprobación `@api.ondelete`. El test registra con una función.
  Con las dos corregidas, sin `unlink` cae exactamente
  `test_unlinking_a_308_invalidates_the_routing`.
