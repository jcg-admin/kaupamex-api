# export-properties-cursor-cache-0397 — la caché de propiedades de la exportación vive en env.cr.cache

Fecha: 2026-11-22T11:29:00. Primera unidad de la sucesora `cursor-cache-consumers-0397`
(`designs/cursor-cache.md`): con `env.cr.cache` portado en `892034dd`,
los sustitutos que se escribieron porque no existía dejan de tener razón.

## Referencia

- `odoo19c: odoo/orm/models.py:686-694` — `_export_rows` guarda
  `self.env.cr.cache['export_properties_cache']` en la llamada de primer
  nivel y la lee en las recursivas.
- `odoo19c: odoo/orm/models.py:875-876` — la llamada de primer nivel la
  retira al terminar.

## Estado heredado (consumidor en `81951988`)

| Contrato | Consumidor | Clase |
|---|---|---|
| la caché vive en `env.cr.cache` | `ContextVar` `_EXPORT_PROPERTIES_CACHE` (`src/orm/models.py:303-306`) | DIVERGENT |
| la de primer nivel la retira | `_EXPORT_PROPERTIES_CACHE.reset` | DIVERGENT |

Prosa heredada falsa: el docstring de `_export_rows` dice que «el `cr` de
este árbol es un alias, no un cursor con diccionario propio». Desde
`892034dd` `env.cr.cache` existe. Se corrige.

## Cambio

`_export_rows` escribe y lee `self.env.cr.cache['export_properties_cache']`
y la retira con `pop` al terminar la llamada de primer nivel, como la
fuente. Se retira el `ContextVar`.

## Símbolos, referencia y prueba

Prueba: `tests/unit/orm/test_export_properties_cursor_cache.py`.

| Símbolo | Referencia | Prueba |
|---|---|---|
| `BaseModel._export_rows` | `odoo19c: odoo/orm/models.py:686-694` | `test_the_recursive_call_reads_the_cursor_cache`, `test_the_toplevel_call_drops_it` |
| `_EXPORT_PROPERTIES_CACHE` (retirado) | `odoo19c: odoo/orm/models.py:875-876` | `test_the_toplevel_call_drops_it` |

## Casos de prueba

- durante la llamada recursiva que exporta `parent_id/name`,
  `env.cr.cache['export_properties_cache']` existe y es el diccionario que
  creó la llamada de primer nivel;
- al terminar `export_data` la clave ya no está.

Control: con la caché devuelta a un `ContextVar`, la recursiva no la
encuentra en `env.cr.cache` y cae el primer caso.
