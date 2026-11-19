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
  lxml_html_clean`). Se añade a `pyproject.toml`, como `pyOpenSSL`. Del
  módulo `clean` la fuente sólo usa `clean.Cleaner` (`:97`; medido con
  `grep -on "clean\.[A-Za-z_]*"`), que el paquete `lxml_html_clean` expone,
  así que el import se escribe `import lxml_html_clean as clean` y el resto
  del cuerpo queda igual. `defs`, `html_parser`, `XHTML_NAMESPACE`,
  `_contains_block_level_tag` y `_looks_like_full_html_*` siguen en
  `lxml.html`.
- `werkzeug.urls.url_parse` (`:484`): `werkzeug` no está en este stack. La
  única lectura es `.scheme`, que da igual con `urllib.parse.urlparse`, ya
  importado por la misma fuente (`:14`). Divergencia de mecanismo declarada en
  el docstring de `validate_url`.

## El parche de lxml que la fuente aplica al arrancar

Con lxml 6.1.1 y libxml2 2.14.6, `html.document_fromstring('yop')` deja el
texto suelto en `<body>` y `html_sanitize('yop')` da `<span>yop</span>`; la
prueba de la fuente espera `<p>yop</p>`
(`odoo19c: odoo/addons/base/tests/test_mail.py:50`). La fuente lo resuelve
en `patch_module` de `odoo19c: odoo/_monkeypatches/lxml.py:10-48`, que envuelve
`lxml.html.fromstring` y `document_fromstring` cuando
`LIBXML_VERSION >= (2, 14, 0)`. Se porta en `src/_monkeypatches/lxml.py` y lo
llama su consumidor, `tools/mail.py`, al importarse, como `tools/safe_eval`
con `pytz`, porque el cargador perezoso de la raíz no está portado. Prueba:
`test_basic_sanitizer` de `tests/unit/tools/test_mail_html_sanitizer.py`, que
cae sin la llamada.

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
