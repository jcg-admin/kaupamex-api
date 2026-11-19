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
pruebas, y `sanitize_overridable=True` en extensiones de addons web:
`website_hr_recruitment` (`hr.job`), `website_sale` (`product.template`,
`product.public.category`), `website_forum`, `survey`, `gamification`,
`website_slides`, `website_partner` y los de eventos. La versión anterior de
esta línea decía «en `hr_job`»: la declaración de `hr` (`odoo19c:
addons/hr/models/hr_job.py:24`) lleva sólo `sanitize_attributes=False`; la
saneable por grupo es la de `website_hr_recruitment`.

De esos addons, este árbol tiene sólo `website_sale`, y no declara ningún
`fields.Html` (medido con `grep -rnE "= fields.Html" addons/<addon>`). Por
eso ninguna declaración de aquí lleva `sanitize_overridable`, y la rama se
prueba sobre un campo suelto.

Y cuatro atajos estáticos (`:699-702`): `escape = markup_escape`,
`is_empty = is_html_empty`, `to_plaintext = html2plaintext`,
`from_plaintext = plaintext2html`, más `type = 'html'` y
`_column_type = ('text', 'text')` (`:562-563`).

Obligaciones del inventario que cierra, con su clave
(`src/orm/fields_textual.py::Html.<símbolo>`, TASK de alcance
TASK-API-0485): la clase, los diez atributos, `_get_attrs`, `_convert`,
`convert_to_column`, `convert_to_cache`, las doce propiedades `_related_*`
y `_description_*`, los cuatro atajos, `type` y `_column_type`.

## Las declaraciones del árbol que llevan opciones en la fuente

Medido con un recorrido AST de nuestras 37 declaraciones `fields.Html`
contra su contraparte (fuera `translate`, que es TASK-GEN-0060):

| Campo | Opciones de la fuente |
|---|---|
| `website.Website.custom_code_head`, `custom_code_footer` | `sanitize=False` |
| `website.Website.robots_txt` | `sanitize=False` |
| `digest.DigestTip.tip_description` | `sanitize=False` |
| `mail.MailMessage.body`, `mail.MailActivity.note` | `sanitize_style=True` |
| `mail.MailTemplate.body_html` | `sanitize='email_outgoing'` |
| `mass_mailing.MailingMailing.body_html` | `sanitize='email_outgoing'` (`odoo19c: addons/mass_mailing/models/mailing.py:115-117`) |
| `hr.HrJob.description` | `sanitize_attributes=False` |
| `base.ServerActionHistoryWizard.code_diff` | `sanitize_tags=False` |

Sin ellas, el saneo por defecto cambiaría la conducta de esos campos
respecto a la fuente; van en la misma unidad que el mecanismo.

## Dónde engancha aquí

`BaseModel.write` convierte cada valor con `field.convert_to_cache(value,
self, validate)` (`src/orm/models.py:9951`), igual que la fuente; por eso
`Html.convert_to_cache` y `Html.convert_to_column` llaman a `_convert`, con los
nombres y el cuerpo de la fuente. Un modelo de Django que no es `BaseModel`
escribe con `Model.save()`, que no pasa por `convert_to_cache`, así que
`Html.pre_save` también llama a `_convert` (el saneo es idempotente: lo
prueba la fuente en `test_basic_sanitizer`). Para el registro y el usuario,
`_convert` usa `env()` cuando la fila no lleva `env`.

- `Html.__init__` acepta los diez atributos de la fuente con sus defaults y
  aplica el atajo `email_outgoing` de `_get_attrs`.
- `Html.pre_save` ≙ `_convert` sobre el valor de la fila.
- `deconstruct` sigue devolviendo `TextField` sin los atributos de saneo: no
  son de la columna, así que no generan migración.

## Lo que el porte añade fuera de `Html`

Funciones nuevas en `src/orm/fields_textual.py`: `Html._sanitize_attrs`
(el atajo de `_get_attrs`, compartido con el campo suelto), `_user_has_group`
(`record.env.user.has_group`, `:631`), `_record_description`
(`record._description`, `:663`) y `_StoredRow.__getattr__`. Prueba de las
cuatro: `tests/unit/orm/test_html_field_sanitize.py`.

- **El valor original en `pre_save`.** La fuente lee `record[self.name]`
  dentro de `write`, cuando todavía es el valor anterior. En `pre_save` el
  atributo ya trae el nuevo, así que `_StoredRow` lee la columna de la fila
  guardada; una fila que se crea no tiene valor anterior.
- **El color del diff** (`:654-661`) lee `COLOR_PATTERN`, `ColoredFormatter`
  y los colores de `odoo19c: odoo/netsvc.py:101-170`. Se porta ese bloque en
  `src/netsvc.py`, el sitio espejo; el resto de `netsvc` queda declarado en su
  docstring con su condición de cierre.
- **La prosa heredada que esta unidad vuelve falsa:** el `help_text` de
  `mail.MailMessage.body` decía «saneo en capa UI» (migración
  `mail/0012_mailmessage_body_help_text`), el comentario de `code_diff` decía
  que no había saneador, y la cabecera de `orm/fields_textual.py` decía que el
  saneo no iba en el campo.

## Fuera de esta unidad, con su sucesor

- `translate=True` → `html_translate`: depende de TASK-GEN-0060.
- `convert_to_record`/`convert_to_read` → `Markup`: lectura del campo; unidad
  sucesora `html-field-markup-0397`.
- `get_trans_terms` (`:696-698`): su `super()` es `BaseString.get_trans_terms`,
  no portado (TASK-GEN-0060).
- `fields_properties.validate` sanea las propiedades `*_html` con
  `html_sanitize`; hoy su prosa lo declara divergencia de UI. Unidad sucesora
  `properties-html-sanitize-0397`.

## Pruebas

`tests/unit/orm/test_html_field_sanitize.py`, sobre un campo `Html` real del
árbol: saneo por defecto al guardar, `sanitize=False` conserva, el atajo
`email_outgoing` conserva los comentarios condicionales, y las dos ramas de
`sanitize_overridable`.
