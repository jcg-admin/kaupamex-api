# Diseño: el saneador de HTML de `tools/mail.py`

Unidad `tools-mail-html-sanitizer-0397` (TASK-API-0397). Inventario
regenerado en `029cb0e3`: 20 símbolos de `src/tools/mail.py` en `absent`.

## Contrato medido en la referencia

`odoo19c: odoo/tools/mail.py`, con sus líneas:

| Símbolo | Líneas | Qué hace |
|---|---|---|
| `SANITIZE_TAGS` | 88-95 | etiquetas y atributos que el saneo conserva o retira |
| `_Cleaner` | 97-174 | subclase de `lxml.html.clean.Cleaner`: `_style_re`, `_style_whitelist`, `conditional_comments`, `sanitize_style`, `strip_classes`, `__call__`, `strip_class`, `parse_style`, `kill_conditional_comments` |
| `tag_quote` | 176-280 | marca citas y firmas con `data-o-mail-quote` |
| `fromstring` | 282-350 | parser HTML que conserva un documento parcial |
| `html_normalize` | 352-414 | normaliza y aplica un filtro sobre el árbol |
| `html_sanitize` | 416-472 | el saneo, con sus diez banderas |
| `URL_SKIP_PROTOCOL_REGEX`, `URL_REGEX`, `TEXT_URL_REGEX`, `HTML_TAG_URL_REGEX`, `HTML_TAGS_REGEX`, `HTML_NEWLINES_REGEX` | 474-480 | constantes de URL |
| `validate_url` | 483-488 | antepone `http://` si el esquema no es web |
| `html_keep_url` | 506-517 | convierte URLs de texto en enlaces |
| `html_to_inner_content` | 519-533 | texto interior de un HTML |
| `create_link` | 535-536 | `<a>` con su etiqueta |
| `plaintext2html` | 622-658 | texto a HTML con párrafos |
| `append_content_to_html` | 660-701 | añade contenido al final del cuerpo |
| `prepend_html_content` | 703-726 | añade contenido al inicio del cuerpo |

`is_html_empty` y `html2plaintext` ya están portados (`src/tools/mail.py`).

## Dependencias

- `lxml_html_clean`: desde lxml 5.2 `lxml.html.clean` es un paquete aparte
  (medido: `ImportError: lxml.html.clean module is now a separate project
  lxml_html_clean`). Se añade a `pyproject.toml`, como `pyOpenSSL`. La fuente
  usa `clean.Cleaner` y `clean._is_javascript_scheme`; los dos los expone el
  paquete `lxml_html_clean`, así que el import se escribe
  `import lxml_html_clean as clean` y el resto del cuerpo queda igual.
- `werkzeug.urls.url_parse` (`:484`): `werkzeug` no está en este stack. La
  única lectura es `.scheme`, que da igual con `urllib.parse.urlparse`, ya
  importado por la misma fuente (`:14`). Divergencia de mecanismo declarada en
  el docstring de `validate_url`.

## Pruebas

Porte de `odoo19c: odoo/addons/base/tests/test_mail.py`: `TestSanitizer`
(`:27-398`) y la parte de `TestHtmlTools` (`:400-547`) que toca estos
símbolos, con sus fixtures de `mail_examples.py`. Destino:
`tests/unit/tools/test_mail_html_sanitizer.py` y
`tests/unit/tools/mail_examples.py`.

## Fuera de esta unidad, con su sucesor

- El saneo del campo `Html` (`odoo19c: odoo/orm/fields_textual.py:545-640`,
  `convert_to_column`/`convert_to_cache` con `sanitize`): hoy
  `fields_textual.Html` declara que el saneo vive en la UI. Unidad sucesora
  `html-field-sanitize-0397`, que llama a `html_sanitize`.
- `fields_properties.validate` sanea las propiedades `*_html` con
  `html_sanitize` (`odoo19c: odoo/orm/fields_properties.py`); misma sucesora.
