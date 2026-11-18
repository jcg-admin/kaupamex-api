# Adopción de `BaseModel`: `html_editor`

Creado: 2026-11-18T17:47:21 (UTC). TASK-API-0397, hija de `basemodel-adoption-0397`.
Referencia: odoo-tools `abe4040ec1`, Odoo 19 Community.

## El contrato de la fuente

- `Html_EditorConverterTest(models.Model)` y
  `Html_EditorConverterTestSub(models.Model)`
  (`odoo19c: addons/html_editor/models/test_models.py:6-8`, `:32-34`).
- `security/ir.model.access.csv`: dos filas, todo para
  `base.group_system`, una por modelo.

## La prosa heredada, validada

| Afirmación | Medido | Veredicto |
|---|---|---|
| `__manifest__.py`: «su equivalente en este árbol es `security/authz_catalog.py`» | el CSV de la fuente declara filas de `ir.model.access` sobre los dos modelos de prueba; `authz_catalog.py` declara códigos de capacidad de endpoints (`ModuleSpec`/`CapabilitySpec`) | **falso**: son dos autoridades distintas. El catálogo no sustituye al CSV |

## Este árbol

Los dos derivan de `TimeStampedModel`, con `_name` y `_description`
verbatim. No cargan el CSV.

## Decisión

Forma de `certificate`: base `(models.BaseModel, TimeStampedModel)`, CSV
fiel en `security/` y declarado en `data`, y el comentario del manifiesto
corregido. `authz_catalog.py` se conserva: es otra obligación.

## RED

1. Los dos son `BaseModel`.
2. Trinquete: `html_editor` sale de `PENDING`.
3. Las dos filas con sus identificadores externos.
4. Un usuario interno no lee `html_editor.converter.test`; uno de
   `group_system`, sí.

## Ejecución (2026-11-18)

Símbolos:

- `Html_EditorConverterTest` ≙ `odoo19c: addons/html_editor/models/test_models.py:6`
  y `Html_EditorConverterTestSub` ≙ `:32`: base
  `(models.BaseModel, TimeStampedModel)`.
- `addons/html_editor/security/ir.model.access.csv`, copia fiel, en `data`
  (`odoo19c: addons/html_editor/__manifest__.py:17-18`); el comentario del
  manifiesto que lo daba por sustituido queda corregido.

`makemigrations html_editor --dry-run`: «No changes detected».
RED: 6 fallos (los cuatro de la prueba nueva, dos del trinquete).
Consumidores: fuera de `tests/unit/html_editor/` ningún archivo de `tests/`
nombra estos modelos; `tests/unit/html_editor` entero y el trinquete: 160
passed.

**Anulación.** Con los dos modelos devueltos a `TimeStampedModel` caen 5 de
24: las dos de herencia, la de acceso y las dos del trinquete. Sobrevive la
de filas del CSV.
