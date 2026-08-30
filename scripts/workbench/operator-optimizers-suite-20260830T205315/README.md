# Suite completa del porte de optimizadores de operador

Par de ejecuciones de la suite entera alrededor del arreglo de la tupla
estrecha de colecciones (H-API-960).

| Ejecución | Sitios repuntados | Resultado | Reloj |
|---|---|---|---|
| `suite-before-the-collection-fix-20260830T205315.log` | 2 de 4 (`domains.py`, `fields.py`) | **3 failed**, 7682 passed, 4 skipped | 371.28 s |
| `suite-after-the-collection-fix-20260830T210058.log` | 4 de 4 (+ `fields_properties.py`, mixin) | **0 failed**, 7685 passed, 4 skipped | 370.18 s |

Los 3 casos del delta son `TestSearchByProperty` — los tres que dependen
de que el compilador de propiedades reconozca un `OrderedSet` como
colección. El par **es** el control: la primera ejecución no es un fallo
del porte, es la medición que destapó los dos sitios que el censo inicial
no había visto.

*Métrica:* casos `passed`/`failed`/`skipped` que pytest publica al cierre.
*Ciega a:* lo que declara `manifest.json` en `blind_to` — el modo frío, el
orden entre workers, y todo comportamiento sin caso escrito.
