# Diseño: el saneo de las propiedades `*_html`

Unidad `properties-html-sanitize-0397`, sucesora declarada en
`designs/html-field-sanitize.md` y en `designs/tools-mail-html-sanitizer.md`.
Depende de `tools-mail-html-sanitizer-0397` (`html_sanitize`).

## Contrato medido en la referencia

`odoo19c: odoo/orm/fields_properties.py`:

| Pieza | Líneas | Qué hace |
|---|---|---|
| `Properties.HTML_SANITIZE_OPTIONS` | 70-78 | las opciones del saneo de una propiedad HTML |
| rama `validate` de `Properties.convert_to_cache` | 156-163 | sanea con esas opciones toda propiedad cuyo nombre acaba en `_html` |
| `PropertiesDefinition.convert_to_cache`, `default` HTML | 1036-1037 | sanea el `default` de una definición `html` |

## La prosa heredada que esta unidad corrige

`src/orm/fields_properties.py` (docstring de `convert_to_cache`) declara
«DIVERGENCIA DECLARADA en `validate`: […] el saneo de HTML vive en la capa
UI (`dompurify`) —la misma decisión que `fields_textual.Html` ya declara—».
Desde `html-field-sanitize-0397` el campo `Html` sanea, así que la premisa
de esa divergencia es falsa y la rama se porta.

## Pruebas

Porte de `test_properties_field_html` (`odoo19c:
odoo/addons/test_orm/tests/test_properties.py:829-897`) sobre
`test_orm.message`/`test_orm.discussion`, en
`tests/unit/orm/test_properties_html_sanitize.py`.
