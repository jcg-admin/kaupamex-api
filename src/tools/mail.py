"""``tools.mail`` — espejo de ``odoo/tools/mail.py`` (sólo símbolos con consumidor).

Archivo separado de ``tools/misc.py`` a propósito: en la referencia
``single_email_re`` vive en ``odoo/tools/mail.py:722``, no en ``misc`` — y
este árbol no agrupa lo que la referencia mantiene separado.

Adaptado de Odoo Community ``odoo/tools/mail.py`` (LGPL-3) — atribución y
aviso de licencia preservados (DEC-KX-03).
"""
import html as htmllib
import itertools
import re

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
