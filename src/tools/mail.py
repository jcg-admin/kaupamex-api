"""``tools.mail`` — espejo de ``odoo/tools/mail.py`` (sólo símbolos con consumidor).

Archivo separado de ``tools/misc.py`` a propósito: en la referencia
``single_email_re`` vive en ``odoo/tools/mail.py:722``, no en ``misc`` — y
este árbol no agrupa lo que la referencia mantiene separado.

Adaptado de Odoo Community ``odoo/tools/mail.py`` (LGPL-3) — atribución y
aviso de licencia preservados (DEC-KX-03).
"""
import base64
import email.utils
import html as htmllib
import itertools
import re
from email.utils import getaddresses as orig_getaddresses

import idna
from lxml import etree

# ``single_email_re`` — ¿el string ES un (1) email y nada más?
#
# Porte verbatim de ``odoo/tools/mail.py:722``. Decisión de equivalencia
# (2026-08-02): Django trae ``django.core.validators.validate_email``, que es
# el validador **rico** (IDN, literales IP, mensajes de error) y sigue siendo
# la herramienta para VALIDAR un email de entrada. Este regex cumple otro rol
# en los call-sites portados: un check barato de FORMA ("¿el login parece un
# email?" → copiarlo al campo email al crear el usuario federado,
# ``auth_ldap/models/res_company_ldap.py:216``). Cambiarlo por el validador
# de Django alteraría qué logins se consideran email (p. ej. IDN pasa en
# Django y no aquí) — se preserva el comportamiento de la referencia y se
# deja la validación rica donde toca: los serializers DRF (``EmailField``).
single_email_re = re.compile(
    r"""^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,63}$""", re.VERBOSE)


def is_html_empty(html_content) -> bool:
    """≙ ``is_html_empty`` (``odoo19c: odoo/tools/mail.py:490-503``).

    Un HTML está vacío si sólo trae etiquetas de formato o nada. El caso
    célebre es el ``<p style="…"><br></p>`` que insertan los editores web: el
    campo no está vacío para el motor, pero para el usuario sí.

    Los dos regex se portan **verbatim**: el primero reconoce iconos de fuente
    (``fa``, ``fab``, ``fad``, ``far``, ``oi``), que sí son contenido aunque no
    tengan texto; el segundo retira las etiquetas de formato antes de mirar si
    queda algo.
    """
    if not html_content:
        return True
    icon_re = (r'<\s*(i|span)\b(\s+[A-Za-z_-][A-Za-z0-9-_]*'
               r'(\s*=\s*[\'"][^"\']*[\'"])?)*\s*\bclass\s*=\s*'
               r'["\'][^"\']*\b(fa|fab|fad|far|oi)\b')
    tag_re = (r'<\s*\/?(?:p|div|section|span|br|b|i|font)\b'
              r'(?:(\s+[A-Za-z_-][A-Za-z0-9-_]*(\s*=\s*[\'"][^"\']*[\'"]))*)'
              r'(?:\s*>|\s*\/\s*>)')
    text_content = htmllib.unescape(re.sub(tag_re, '', html_content))
    return not bool(text_content.strip()) and not re.search(icon_re, html_content)


def html2plaintext(html, body_id=None, encoding='utf-8', include_references=True) -> str:
    """≙ ``html2plaintext`` (``odoo19c: odoo/tools/mail.py:539-619``).

    Convierte HTML a texto plano conservando el énfasis en marcas ASCII
    (``*negrita*``, ``/cursiva/``) y numerando los enlaces e imágenes al pie,
    que es lo que espera un cuerpo de correo o una descripción de albarán.

    :param body_id: id de la etiqueta donde empieza el cuerpo, si no es
        ``<body>``.
    :param include_references: con ``False`` no se numeran enlaces ni imágenes.

    Procedencia del algoritmo, preservada de la fuente: (c) Fry-IT,
    www.fry-it.com, 2007 — http://www.peterbe.com/plog/html2plaintext
    """
    if not (html and html.strip()):
        return ''

    if isinstance(html, bytes):
        html = html.decode(encoding)
    else:
        assert isinstance(html, str), f"expected str got {html.__class__.__name__}"

    tree = etree.fromstring(html, parser=etree.HTMLParser())

    if body_id is not None:
        source = tree.xpath('//*[@id=%s]' % (body_id,))
    else:
        source = tree.xpath('//body')
    if len(source):
        tree = source[0]

    url_index = []
    linkrefs = itertools.count(1)
    if include_references:
        for link in tree.findall('.//a'):
            if url := link.get('href'):
                link.tag = 'span'
                link.text = f'{link.text} [{next(linkrefs)}]'
                url_index.append(url)

        for img in tree.findall('.//img'):
            if src := img.get('src'):
                img.tag = 'span'
                if src.startswith('data:'):
                    img_name = None     # imagen en base64: no tiene nombre
                else:
                    img_name = re.search(r'[^/]+(?=\.[a-zA-Z]+(?:\?|$))', src)
                img.text = '%s [%s]' % (img_name[0] if img_name else 'Image',
                                        next(linkrefs))
                url_index.append(src)

    html = etree.tostring(tree, encoding='unicode')
    # El \r se convierte en &#13; al serializar; hay que retirarlo.
    html = html.replace('&#13;', '')

    html = html.replace('<strong>', '*').replace('</strong>', '*')
    html = html.replace('<b>', '*').replace('</b>', '*')
    html = html.replace('<h3>', '*').replace('</h3>', '*')
    html = html.replace('<h2>', '**').replace('</h2>', '**')
    html = html.replace('<h1>', '**').replace('</h1>', '**')
    html = html.replace('<em>', '/').replace('</em>', '/')
    html = html.replace('<tr>', '\n')
    html = html.replace('</p>', '\n')
    html = re.sub(r'<br\s*/?>', '\n', html)
    html = re.sub('<.*?>', ' ', html)
    html = html.replace(' ' * 2, ' ')
    html = html.replace('&gt;', '>')
    html = html.replace('&lt;', '<')
    html = html.replace('&amp;', '&')
    html = html.replace('&nbsp;', '\N{NO-BREAK SPACE}')

    html = '\n'.join([x.strip() for x in html.splitlines()])
    html = html.replace('\n' * 2, '\n')

    if url_index:
        html += '\n\n'
        for i, url in enumerate(url_index, start=1):
            html += f'[{i}] {url}\n'

    return html.strip()


# ---------------------------------------------------------------------------
# Direcciones de correo — ``odoo19c: odoo/tools/mail.py:719-1002``.
#
# Se portan seis símbolos y una guarda de versión. Su consumidor en este pase
# es ``ResPartner.email_formatted``, pero la referencia los usa en todo el
# stack de correo: son la respuesta a *"¿el mismo buzón escrito de dos formas
# compara igual?"*, que es lo que decide si el sistema manda dos veces, una o
# ninguna.
# ---------------------------------------------------------------------------

#: ≙ ``email_re`` (``odoo19c: odoo/tools/mail.py:719``), verbatim. Encuentra
#: direcciones DENTRO de un texto; su hermano ``single_email_re`` (arriba)
#: pregunta si el texto ES una y nada más.
email_re = re.compile(r"""([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,63})""",
                      re.VERBOSE)

#: ≙ ``email_addr_escapes_re`` (``:726``), verbatim. La barra y la comilla son
#: los dos caracteres que hay que escapar dentro de un nombre entrecomillado
#: (RFC 2822 §3.4); sin escapar, una comilla en el nombre parte la cabecera.
email_addr_escapes_re = re.compile(r'[\\"]')


# ≙ la guarda de ``:56-61``, con su comentario verbatim: *"disable strict mode
# when present: we rely on original non-strict parsing, and we know that it
# isn't reliable, that ok."* La referencia elige el parseo laxo a propósito —
# un correo capturado por una persona no cumple el RFC y aun así hay que
# entenderlo. El `hasattr` es porque el argumento sólo existe desde
# CPython 3.11.4 (cfr. python/cpython@4a153a1).
if hasattr(email.utils, 'supports_strict_parsing'):
    def getaddresses(fieldvalues):
        return orig_getaddresses(fieldvalues, strict=False)
else:
    getaddresses = orig_getaddresses


def email_split_tuples(text):
    """≙ ``email_split_tuples`` (``odoo19c: odoo/tools/mail.py:741-785``).

    Docstring de la fuente, verbatim: *"Return a list of (name, email) address
    tuples found in ``text``. Note that text should be an email header or a
    stringified email list as it may give broader results than expected on
    actual text."*

    Los dos rodeos son de la fuente y cada uno responde a una entrada real:

    - ``_parse_based_on_spaces`` — con ``'Ana ana@x.mx'`` (sin comillas)
      ``getaddresses`` devuelve ``('', 'Ana ana@x.mx')``. Reintenta cambiando
      espacios por comas para separar el nombre del buzón.
    - el caso de ``'@dominio.com'`` — una dirección sin parte local pasa el
      filtro del ``@`` y no es una dirección; ahí manda ``email_re``.
    """
    def _parse_based_on_spaces(pair):
        name, addr = pair
        if not name and addr and ' ' in addr:
            inside_pairs = getaddresses([addr.replace(' ', ',')])
            name_parts, found_email = [], False
            for inner in inside_pairs:
                if inner[1] and '@' not in inner[1]:
                    name_parts.append(inner[1])
                if inner[1] and '@' in inner[1]:
                    found_email = inner[1]
            if found_email:
                name, addr = ' '.join(name_parts), found_email
        return (name, addr)

    if not text:
        return []

    # pares válidos, descartando los que el parseo no supo leer: getaddresses
    # devuelve '' al fallar, y a veces una cadena sin '@' — que el addr-spec
    # del RFC 2822 exige.
    valid_pairs = [
        (addr[0], addr[1]) for addr in getaddresses([text])
        if addr[1] and '@' in addr[1]
    ]
    # caso borde: una dirección que empieza por '@' (ver test_email_split)
    if any(pair[1].startswith('@') for pair in valid_pairs):
        filtered = [found for found in email_re.findall(text)
                    if found and not found.startswith('@')]
        if filtered:
            valid_pairs = [('', found) for found in filtered]

    return list(map(_parse_based_on_spaces, valid_pairs))


def email_split(text):
    """≙ ``email_split`` (``:788-790``).

    Docstring de la fuente, verbatim: *"Return a list of the email addresses
    found in ``text``"*.
    """
    return [addr for (name, addr) in email_split_tuples(text)]


def _normalize_email(email_address):
    """≙ ``_normalize_email`` (``:860-889``).

    **La parte local se baja sólo si es ASCII**, y no es una inconsistencia.
    El docstring de la fuente lo razona: el RFC 5322 §3.4.1 la declara
    sensible a mayúsculas, *"however most main providers do consider the
    local-part as case insensitive"*; pero con SMTP-UTF8 esa suposición deja
    de valer para una parte local internacional. Bajar la ASCII y respetar la
    que no lo es es la única regla que no rompe ninguno de los dos mundos.

    El dominio se baja **siempre**: en un dominio la mayúscula es un error de
    captura, no un dato (IDNA lo asume igual).
    """
    local_part, at, domain = email_address.rpartition('@')
    try:
        local_part.encode('ascii')
    except UnicodeEncodeError:
        pass
    else:
        local_part = local_part.lower()
    return local_part + at + domain.lower()


def email_normalize(text, strict=True):
    """≙ ``email_normalize`` (``:812-846``).

    Devuelve **``False``** —no cadena vacía— cuando no encuentra una
    dirección, que es lo que la fuente promete y lo que sus llamadores
    distinguen.

    :param strict: si ``True`` (el valor de la fuente desde la 14) el texto
        debe traer **una** dirección; con dos, no se devuelve ninguna. Es
        deliberado: mezclar dos buzones en uno es peor que no responder.
        Con ``False`` gana la primera encontrada.
    """
    emails = email_split(text)
    if not emails or (strict and len(emails) != 1):
        return False
    return _normalize_email(emails[0])


def email_normalize_all(text):
    """≙ ``email_normalize_all`` (``:848-858``).

    Docstring de la fuente, verbatim: *"Tool method allowing to extract email
    addresses from a text input and returning normalized version of all found
    emails. If no email is found, a void list is returned."*
    """
    emails = email_split(text)
    return list(filter(None, [_normalize_email(addr) for addr in emails]))


def parse_contact_from_email(text):
    """≙ ``parse_contact_from_email`` (``odoo19c: odoo/tools/mail.py:1031-1056``).

    Docstring de la fuente, verbatim: *"Parse contact name and email (given by
    text) in order to find contact information, able to populate records like
    partners, leads, ... Supported syntax:*

      * ``Raoul <raoul@grosbedon.fr>``
      * ``"Raoul le Grand" <raoul@grosbedon.fr>``
      * ``Raoul raoul@grosbedon.fr`` *(strange fault tolerant support from
        df40926d2a57c101a3e2d221ecfd08fbb4fea30e now supported directly in
        'email_split_tuples')*

    *Otherwise: default, text is set as name.*

    :return: name, email (normalized if possible)

    El caso por defecto es la mitad que importa: un texto que no parsea **es
    el nombre**, no un vacío. Devolver ``('', '')`` ahí dejaría al llamador
    creando filas sin nada legible.

    ``strict=False`` en la normalización es de la fuente: aquí ya se aisló una
    dirección, así que el modo estricto —que rechaza cuando hay dos— no tiene
    nada que proteger, y su ``or email`` conserva la original cuando no se
    puede normalizar.
    """
    if not text or not text.strip():
        return '', ''
    split_results = email_split_tuples(text)
    name, email = split_results[0] if split_results else ('', '')

    if email:
        email_normalized = email_normalize(email, strict=False) or email
    else:
        name, email_normalized = text, ''

    return name, email_normalized


def formataddr(pair, charset='utf-8'):
    """≙ ``formataddr`` (``:961-1002``).

    Docstring de la fuente, verbatim: *"Pretty format a 2-tuple of the form
    (realname, email_address). If the first element of pair is falsy then only
    the email address is returned. Set the charset to ascii to get a RFC-2822
    compliant email. The realname will be base64 encoded (if necessary) and
    the domain part of the email will be punycode encoded (if necessary). The
    local part is left unchanged thus require the SMTPUTF8 extension when
    there are non-ascii characters."*

    Las tres ramas, y qué protege cada una:

    - **el dominio** que no cabe en el charset se codifica con IDNA (RFC 5890)
      — un dominio con acento no viaja en una cabecera;
    - **el nombre** que no cabe se codifica en base64 (RFC 2047). Con el
      ``utf-8`` por defecto casi todo cabe, así que esta rama es la del
      ``charset='ascii'`` que pide una cabecera estrictamente conforme;
    - **el nombre que sí cabe** se escapa: una comilla sin escapar dentro de
      un nombre entrecomillado parte la cabecera en dos.
    """
    name, address = pair
    local, _at, domain = address.rpartition('@')

    try:
        domain.encode(charset)
    except UnicodeEncodeError:
        # rfc5890 — nombres de dominio internacionalizados (IDNA)
        domain = idna.encode(domain).decode('ascii')

    if name:
        try:
            name.encode(charset)
        except UnicodeEncodeError:
            # rfc2047 — texto no ASCII en una cabecera MIME
            name = base64.b64encode(name.encode('utf-8')).decode('ascii')
            return f"=?utf-8?b?{name}?= <{local}@{domain}>"
        else:
            # rfc2822 §3.4 — escapar barra y comilla dentro del nombre
            name = email_addr_escapes_re.sub(r'\\\g<0>', name)
            return f'"{name}" <{local}@{domain}>'
    return f"{local}@{domain}"
