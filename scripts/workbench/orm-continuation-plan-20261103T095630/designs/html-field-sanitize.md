# Diseño: el saneo del campo `Html`

Unidad `html-field-sanitize-0397` (TASK-API-0397), sucesora declarada en
`designs/tools-mail-html-sanitizer.md`. Depende de
`tools-mail-html-sanitizer-0397`, que porta `html_sanitize` y `html_normalize`.

## Contrato medido en la referencia

`odoo19c: odoo/orm/fields_textual.py:545-697`, clase `Html`:

| Pieza | Líneas | Qué hace |
|---|---|---|
| diez atributos `sanitize*` y `strip_*` con sus defaults | 563-575 | `sanitize=True` por defecto: todo campo HTML se sanea salvo que diga lo contrario |
| `_get_attrs` | 576-598 | `sanitize='email_outgoing'` es un atajo: activa el saneo con `sanitize_tags`, `sanitize_attributes` y `sanitize_conditional_comments` en `False` y salida `xml`; `translate=True` con saneo pasa a `html_translate` |
| `_related_*` y `_description_*` | 600-612 | propiedades que leen los atributos |
| `convert_to_column`, `convert_to_cache`, `_convert` | 614-682 | sanea al escribir y al asignar; con `sanitize_overridable`, un usuario de `base.group_sanitize_override` escribe sin sanear, y uno sin el grupo no puede guardar un valor que el saneo cambiaría (`UserError`) |
| `convert_to_record`, `convert_to_read` | 684-695 | devuelven `Markup` |

Uso medido en la referencia: 16 `fields.Html(... sanitize=False ...)` fuera de
pruebas, y `sanitize_overridable=True` en `hr_job`, `product_template`,
`product_public_category`, `forum_forum`, `survey_survey` y
`gamification_karma_rank`.

## Dónde engancha aquí

Nuestras dos rutas de escritura llaman a `Field.pre_save`: `Model.save()` y
el volcado de `BaseModel` (`_persist_columns`, `src/orm/models.py:5443`,
*"el valor de cada columna lo da `Field.pre_save(row, False)`"*). Por eso el
saneo de `_convert` va en `Html.pre_save`, que tiene el registro y puede leer
el valor original de la base para la rama `sanitize_overridable`.

- `Html.__init__` acepta los diez atributos de la fuente con sus defaults y
  aplica el atajo `email_outgoing` de `_get_attrs`.
- `Html.pre_save` ≙ `_convert` sobre el valor de la fila.
- `deconstruct` sigue devolviendo `TextField` sin los atributos de saneo: no
  son de la columna, así que no generan migración.

## Fuera de esta unidad, con su sucesor

- `convert_to_cache` (sanear al asignar, antes de escribir): nuestro
  descriptor de Django no tiene ese punto; el valor se sanea al guardar. Se
  declara en el docstring de `Html`.
- `translate=True` → `html_translate`: depende de TASK-GEN-0060.
- `convert_to_record`/`convert_to_read` → `Markup`: lectura del campo; unidad
  sucesora `html-field-markup-0397`.

## Pruebas

`tests/unit/orm/test_html_field_sanitize.py`, sobre un campo `Html` real del
árbol: saneo por defecto al guardar, `sanitize=False` conserva, el atajo
`email_outgoing` conserva los comentarios condicionales, y las dos ramas de
`sanitize_overridable`.
