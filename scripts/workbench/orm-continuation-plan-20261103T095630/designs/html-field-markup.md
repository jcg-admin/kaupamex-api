# Diseño: el campo `Html` entrega `Markup`

Unidad `html-field-markup-0397`, sucesora declarada en
`designs/html-field-sanitize.md`. Depende de `html-field-sanitize-0485`.

## Contrato medido en la referencia

`odoo19c: odoo/orm/fields_textual.py:684-694`:

| Pieza | Qué hace |
|---|---|
| `Html.convert_to_record` | el valor de caché, decodificado si es `bytes`, envuelto en `Markup` (vacío queda vacío) |
| `Html.convert_to_read` | lo mismo sobre el valor de `read()` |

`Markup` es una subclase de `str`: compara igual, se serializa en JSON igual,
y declara `__html__`, por lo que un motor de plantillas lo trata como seguro.
Es la intención de la fuente: el valor ya pasó por el saneo al escribirse.

## Dónde engancha aquí

`FieldDescriptor.__get__` (`src/orm/fields.py`) entrega el valor ordinario
almacenado sin `convert_to_record`, salvo `JSONField` exacto. `Html` necesita
la misma rama: la lectura de una columna ya cargada pasa por
`Html.convert_to_record`. `convert_to_read` cubre `read()`.

## Consecuencia declarada

Una plantilla de Django que pinte un campo `Html` ya no lo escapa
(`conditional_escape` respeta `__html__`), como QWeb en la fuente. Medido: ninguna plantilla propia del árbol pinta un campo `Html`
(`grep` de `{{ … body|note|description|body_html }}` sobre `*.html` sólo
encuentra plantillas de Django y DRF en `.venv`).

## Pruebas

`tests/unit/orm/test_html_field_markup.py`: lectura de un campo `Html`
guardado da `Markup` igual al texto; vacío da `False`/vacío como la fuente;
`read()` da `Markup`.
