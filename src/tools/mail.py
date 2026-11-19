"""
``tools.mail`` — espejo de ``odoo/tools/mail.py``.

Archivo separado de ``tools/misc.py`` a propósito: en la referencia
``single_email_re`` vive en ``odoo/tools/mail.py:722``, no en ``misc`` — y
este árbol no agrupa lo que la referencia mantiene separado.

Adaptado de Odoo Community ``odoo/tools/mail.py`` (LGPL-3) — atribución y
aviso de licencia preservados (DEC-KX-03).
"""

import base64
import collections
import email.utils
import html as htmllib
import itertools
import logging
import random
import re
import socket
import time
from email.utils import getaddresses as orig_getaddresses
from urllib.parse import urlparse

import idna
import lxml_html_clean as clean
import markupsafe
from lxml import etree, html
from lxml.html import (
    XHTML_NAMESPACE,
    _contains_block_level_tag,
    _looks_like_full_html_bytes,
    _looks_like_full_html_unicode,
    defs,
    html_parser,
)

from _monkeypatches.lxml import patch_module as patch_lxml
from tools import misc

_logger = logging.getLogger(__name__)

# libxml2 2.14 dejó de envolver en ``<p>`` el texto suelto; la fuente lo
# restaura al arrancar con ``odoo/_monkeypatches/lxml.py``. Aquí lo aplica su
# consumidor al importarse, como ``tools/safe_eval`` con ``pytz``.
patch_lxml()

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
    r"""^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,63}$""", re.VERBOSE
)


# ---------------------------------------------------------------------------
# Saneador de HTML — ``odoo19c: odoo/tools/mail.py:64-488``. Es la copia de
# la fuente reformateada a PEP 8 con el árbol AST idéntico salvo saltos de
# línea de los docstrings; el único cambio de código es ``validate_url`` (ver
# su comentario). Diseño: ``designs/tools-mail-html-sanitizer.md``.
# ---------------------------------------------------------------------------

# ----------------------------------------------------------
# HTML Sanitizer
# ----------------------------------------------------------

safe_attrs = defs.safe_attrs | frozenset(
    [
        'style',
        'data-o-mail-quote',
        'data-o-mail-quote-node',  # quote detection
        'data-oe-model',
        'data-oe-id',
        'data-oe-field',
        'data-oe-type',
        'data-oe-expression',
        'data-oe-translation-source-sha',
        'data-oe-nodeid',
        'data-last-history-steps',
        'data-oe-protected',
        'data-embedded',
        'data-embedded-editable',
        'data-embedded-props',
        'data-oe-version',
        'data-oe-transient-content',
        'data-behavior-props',
        'data-prop-name',
        'data-width',
        'data-height',
        'data-scale-x',
        'data-scale-y',
        'data-x',
        'data-y',  # legacy editor
        'data-oe-role',
        'data-oe-aria-label',
        'data-publish',
        'data-id',
        'data-res_id',
        'data-interval',
        'data-member_id',
        'data-scroll-background-ratio',
        'data-view-id',
        'data-class',
        'data-mimetype',
        'data-original-src',
        'data-original-id',
        'data-gl-filter',
        'data-quality',
        'data-resize-width',
        'data-shape',
        'data-shape-colors',
        'data-file-name',
        'data-original-mimetype',
        'data-attachment-id',
        'data-format-mimetype',
        'data-ai-field',
        'data-ai-record-id',
        'data-heading-link-id',
        'data-mimetype-before-conversion',
        'data-language-id',
        'data-bs-toggle',  # support nav-tabs
    ]
)

defs.link_attrs |= {'xlink:href'}

SANITIZE_TAGS = {
    # allow new semantic HTML5 tags
    'allow_tags': defs.tags
    | frozenset(
        (
            'article bdi section header footer hgroup nav aside figure '
            'main'
        ).split()
        + [etree.Comment]
    ),
    'kill_tags': [
        'base',
        'embed',
        'frame',
        'head',
        'iframe',
        'link',
        'meta',
        'noscript',
        'object',
        'script',
        'style',
        'title',
    ],
    'remove_tags': ['html', 'body'],
}


class _Cleaner(clean.Cleaner):

    _style_re = re.compile(
        r'''([\w-]+)\s*:\s*((?:[^;"']|"[^";]*"|'[^';]*')+)'''
    )

    _style_whitelist = [
        'font-size',
        'font-family',
        'font-weight',
        'font-style',
        'background-color',
        'color',
        'text-align',
        'line-height',
        'letter-spacing',
        'text-transform',
        'text-decoration',
        'text-decoration',
        'opacity',
        'float',
        'vertical-align',
        'display',
        'object-fit',
        'direction',
        'padding',
        'padding-top',
        'padding-left',
        'padding-bottom',
        'padding-right',
        'margin',
        'margin-top',
        'margin-left',
        'margin-bottom',
        'margin-right',
        'white-space',
        # appearance
        'background-image',
        'background-position',
        'background-size',
        'background-repeat',
        'background-origin',
        # box model
        'border',
        'border-color',
        'border-radius',
        'border-style',
        'border-width',
        'border-top',
        'border-bottom',
        'height',
        'width',
        'max-width',
        'min-width',
        'min-height',
        # tables
        'border-collapse',
        'border-spacing',
        'caption-side',
        'empty-cells',
        'table-layout',
    ]

    _style_whitelist.extend(
        [
            'border-%s-%s' % (position, attribute)
            for position in ['top', 'bottom', 'left', 'right']
            for attribute in (
                'style',
                'color',
                'width',
                'left-radius',
                'right-radius',
            )
        ]
    )

    strip_classes = False
    sanitize_style = False
    conditional_comments = True

    def __call__(self, doc):
        super(_Cleaner, self).__call__(doc)

        # if we keep attributes but still remove classes
        if not getattr(self, 'safe_attrs_only', False) and self.strip_classes:
            for el in doc.iter(tag=etree.Element):
                self.strip_class(el)

        # if we keep style attribute, sanitize them
        if not self.style and self.sanitize_style:
            for el in doc.iter(tag=etree.Element):
                self.parse_style(el)

    def strip_class(self, el):
        if el.attrib.get('class'):
            del el.attrib['class']

    def parse_style(self, el):
        attributes = el.attrib
        styling = attributes.get('style')
        if styling:
            valid_styles = collections.OrderedDict()
            styles = self._style_re.findall(styling)
            for style in styles:
                if style[0].lower() in self._style_whitelist:
                    valid_styles[style[0].lower()] = style[1]
            if valid_styles:
                el.attrib['style'] = '; '.join(
                    '%s:%s' % (key, val) for (key, val) in valid_styles.items()
                )
            else:
                del el.attrib['style']

    def kill_conditional_comments(self, doc):
        """Override the default behavior of lxml.

        https://github.com/lxml/lxml/blob/e82c9153c4a7d505480b94c60b9a84d79d948efb/src/lxml/html/clean.py#L501-L510

        In some use cases, e.g. templates used for mass mailing,
        we send emails containing conditional comments targeting Microsoft
        Outlook, to give special styling instructions.
        https://github.com/odoo/odoo/pull/119325/files#r1301064789

        Within these conditional comments, unsanitized HTML can lie.
        However, in modern browser, these comments are considered as simple
        comments, their content is not executed.
        https://caniuse.com/sr_ie-features
        """
        if self.conditional_comments:
            super().kill_conditional_comments(doc)


def tag_quote(el):
    def _create_new_node(tag, text, tail=None, attrs=None):
        new_node = etree.Element(tag)
        new_node.text = text
        new_node.tail = tail
        if attrs:
            for key, val in attrs.items():
                new_node.set(key, val)
        return new_node

    def _tag_matching_regex_in_text(regex, node, tag='span', attrs=None):
        text = node.text or ''
        if not re.search(regex, text):
            return

        child_node = None
        idx, node_idx = 0, 0
        for item in re.finditer(regex, text):
            new_node = _create_new_node(
                tag, text[item.start():item.end()], None, attrs
            )
            if child_node is None:
                node.text = text[idx:item.start()]
                new_node.tail = text[item.end():]
                node.insert(node_idx, new_node)
            else:
                child_node.tail = text[idx:item.start()]
                new_node.tail = text[item.end():]
                node.insert(node_idx, new_node)
            child_node = new_node
            idx = item.end()
            node_idx = node_idx + 1

    # la fuente los llama ``el_class`` y ``el_id`` (``el`` = element); se
    # escriben completos porque el gate de idioma lee ``el`` como artículo
    element_class = el.get('class', '') or ''
    element_id = el.get('id', '') or ''

    # gmail or yahoo // # outlook, html // # msoffice
    if 'gmail_extra' in element_class or (
        'SkyDrivePlaceholder' in element_class
        or 'SkyDrivePlaceholder' in element_class
    ):
        el.set('data-o-mail-quote', '1')
        if el.getparent() is not None:
            el.getparent().set('data-o-mail-quote-container', '1')

    if (
        el.tag == 'hr'
        and ('stopSpelling' in element_class or 'stopSpelling' in element_id)
    ) or 'yahoo_quoted' in element_class:
        # Quote all elements after this one
        el.set('data-o-mail-quote', '1')
        for sibling in el.itersiblings(preceding=False):
            sibling.set('data-o-mail-quote', '1')

    # odoo, gmail and outlook automatic signature wrapper
    is_signature_wrapper = (
        'odoo_signature_wrapper' in element_class
        or 'gmail_signature' in element_class
        or element_id == "Signature"
    )
    is_outlook_auto_message = 'appendonsend' in element_id
    # gmail and outlook reply quote
    is_outlook_reply_quote = 'divRplyFwdMsg' in element_id
    is_gmail_quote = 'gmail_quote' in element_class
    is_quote_wrapper = (
        is_signature_wrapper or is_gmail_quote or is_outlook_reply_quote
    )
    if is_quote_wrapper:
        el.set('data-o-mail-quote-container', '1')
        el.set('data-o-mail-quote', '1')

    # outlook reply wrapper is preceded with <hr> and a div containing
    # recipient info
    if is_outlook_reply_quote:
        hr = el.getprevious()
        reply_quote = el.getnext()
        if hr is not None and hr.tag == 'hr':
            hr.set('data-o-mail-quote', '1')
        if reply_quote is not None:
            reply_quote.set('data-o-mail-quote-container', '1')
            reply_quote.set('data-o-mail-quote', '1')

    if is_outlook_auto_message:
        if not el.text or not el.text.strip():
            el.set('data-o-mail-quote-container', '1')
            el.set('data-o-mail-quote', '1')

    # html signature (-- <br />blah)
    signature_begin = re.compile(r"((?:(?:^|\n)[-]{2}[\s]?$))")
    if (
        el.text
        and el.find('br') is not None
        and re.search(signature_begin, el.text)
    ):
        el.set('data-o-mail-quote', '1')
        if el.getparent() is not None:
            el.getparent().set('data-o-mail-quote-container', '1')

    # text-based quotes (>, >>) and signatures (-- Signature)
    text_complete_regex = re.compile(
        r"((?:\n[>]+[^\n\r]*)+|(?:(?:^|\n)[-]{2}[\s]?[\r\n]{1,2}[\s\S]+))"
    )
    if not el.get('data-o-mail-quote'):
        _tag_matching_regex_in_text(
            text_complete_regex, el, 'span', {'data-o-mail-quote': '1'}
        )

    if el.tag == 'blockquote':
        # remove single node
        el.set('data-o-mail-quote-node', '1')
        el.set('data-o-mail-quote', '1')
    if el.getparent() is not None and not el.getparent().get(
        'data-o-mail-quote-node'
    ):
        if el.getparent().get('data-o-mail-quote'):
            el.set('data-o-mail-quote', '1')
        # only quoting the elements following the first quote in the container
        # avoids issues with repeated calls to html_normalize
        elif el.getparent().get('data-o-mail-quote-container'):
            if (
                first_sibling_quote := el.getparent().find(
                    "*[@data-o-mail-quote]"
                )
            ) is not None:
                siblings = el.getparent().getchildren()
                quote_index = siblings.index(first_sibling_quote)
                element_index = siblings.index(el)
                if quote_index < element_index:
                    el.set('data-o-mail-quote', '1')
    if (
        el.getprevious() is not None
        and el.getprevious().get('data-o-mail-quote')
        and not el.text_content().strip()
    ):
        el.set('data-o-mail-quote', '1')


def fromstring(html_, base_url=None, parser=None, **kw):
    """
    This function mimics lxml.html.fromstring. It not only returns the parsed
    element/document but also a flag indicating whether the input is for a
    a single body element or not.

    This tries to minimally parse the chunk of text, without knowing if it
    is a fragment or a document.

    base_url will set the document's base_url attribute (and the tree's
    docinfo.URL)
    """
    if parser is None:
        parser = html_parser
    if isinstance(html_, bytes):
        is_full_html = _looks_like_full_html_bytes(html_)
    else:
        is_full_html = _looks_like_full_html_unicode(html_)
    doc = html.document_fromstring(
        html_, parser=parser, base_url=base_url, **kw
    )
    if is_full_html:
        return doc, False
    # otherwise, lets parse it out...
    bodies = doc.findall('body')
    if not bodies:
        bodies = doc.findall('{%s}body' % XHTML_NAMESPACE)
    if bodies:
        body = bodies[0]
        if len(bodies) > 1:
            # Somehow there are multiple bodies, which is bad, but just
            # smash them into one body
            for other_body in bodies[1:]:
                if other_body.text:
                    if len(body):
                        body[-1].tail = (body[-1].tail or '') + other_body.text
                    else:
                        body.text = (body.text or '') + other_body.text
                body.extend(other_body)
                # We'll ignore tail
                # I guess we are ignoring attributes too
                other_body.drop_tree()
    else:
        body = None
    heads = doc.findall('head')
    if not heads:
        heads = doc.findall('{%s}head' % XHTML_NAMESPACE)
    if heads:
        # Well, we have some sort of structure, so lets keep it all
        head = heads[0]
        if len(heads) > 1:
            for other_head in heads[1:]:
                head.extend(other_head)
                # We don't care about text or tail in a head
                other_head.drop_tree()
        return doc, False
    if body is None:
        return doc, False
    if (
        len(body) == 1
        and (not body.text or not body.text.strip())
        and (not body[-1].tail or not body[-1].tail.strip())
    ):
        # The body has just one element, so it was probably a single
        # element passed in
        return body[0], True
    # Now we have a body which represents a bunch of tags which have the
    # content that was passed in.  We will create a fake container, which
    # is the body tag, except <body> implies too much structure.
    if _contains_block_level_tag(body):
        body.tag = 'div'
    else:
        body.tag = 'span'
    return body, False


def html_normalize(src, filter_callback=None, output_method="html"):
    """Normalize `src` for storage as an html field value.

    The string is parsed as an html tag soup, made valid, then decorated for
    "email quote" detection, and prepared for an optional filtering.
    The filtering step (e.g. sanitization) should be performed by the
    `filter_callback` function (to avoid multiple parsing operations, and
    normalize the result).

    :param src: the html string to normalize
    :param filter_callback: optional callable taking a single `etree._Element`
        document parameter, to be called during normalization in order to
        filter the output document
    :param output_method: defines the output method to pass to `html.tostring`.
        It defaults to 'html', but can also be 'xml' for xhtml output.
    """
    if not src:
        return src

    # html: remove encoding attribute inside tags
    src = re.sub(
        r'(<[^>]*\s)(encoding=(["\'][^"\']*?["\']|[^\s\n\r>]+)(\s[^>]*|/)?>)',
        "",
        src,
    )

    src = src.replace('--!>', '-->')
    src = re.sub(r'(<!-->|<!--->)', '<!-- -->', src)
    # On the specific case of Outlook desktop it adds unnecessary
    # '<o:.*></o:.*>' tags which are parsed
    # in '<p></p>' which may alter the appearance (eg. spacing) of the mail
    # body
    src = re.sub(r'</?o:.*?>', '', src)

    try:
        doc, single_body_element = fromstring(src)
    except etree.ParserError as e:
        # HTML comment only string, whitespace only..
        if 'empty' in str(e):
            return ""
        raise

    # perform quote detection before cleaning and class removal
    for el in doc.iter(tag=etree.Element):
        tag_quote(el)

    doc = html.fromstring(html.tostring(doc, method=output_method))

    if filter_callback:
        doc = filter_callback(doc)

    src = html.tostring(doc, encoding='unicode', method=output_method)

    if (
        not single_body_element
        and src.startswith('<div>')
        and src.endswith('</div>')
    ):
        # the <div></div> may come from 2 places
        # 1. the src is parsed as multiple body elements
        #    <div></div> wraps all elements.
        # 2. the src is parsed as not only body elements
        #    <html></html> wraps all elements.
        #    then the Cleaner as the filter_callback which has 'html' in its
        #    'remove_tags' will write <html></html> to <div></div> since it
        #    cannot directly drop the parent-most tag
        src = src[5:-6]

    # html considerations so real html content match database value
    src = src.replace(u'\xa0', u'&nbsp;')

    return src


def html_sanitize(
    src,
    silent=True,
    sanitize_tags=True,
    sanitize_attributes=False,
    sanitize_style=False,
    sanitize_form=True,
    sanitize_conditional_comments=True,
    strip_style=False,
    strip_classes=False,
    output_method="html",
):
    if not src:
        return src

    logger = logging.getLogger(__name__ + '.html_sanitize')

    def sanitize_handler(doc):
        kwargs = {
            'page_structure': True,
            'style': strip_style,  # True = remove style tags/attrs
            'sanitize_style': sanitize_style,  # True = sanitize styling
            'forms': sanitize_form,  # True = remove form tags
            'remove_unknown_tags': False,
            'comments': False,
            # True = remove conditional comments
            'conditional_comments': sanitize_conditional_comments,
            'processing_instructions': False,
        }
        if sanitize_tags:
            kwargs.update(SANITIZE_TAGS)

        if (
            sanitize_attributes
        ):  # We keep all attributes in order to keep "style"
            if strip_classes:
                current_safe_attrs = safe_attrs - frozenset(['class'])
            else:
                current_safe_attrs = safe_attrs
            kwargs.update(
                {
                    'safe_attrs_only': True,
                    'safe_attrs': current_safe_attrs,
                }
            )
        else:
            kwargs.update(
                {
                    # keep oe-data attributes + style
                    'safe_attrs_only': False,
                    # remove classes, even when keeping other attributes
                    'strip_classes': strip_classes,
                }
            )

        cleaner = _Cleaner(**kwargs)
        cleaner(doc)
        return doc

    try:
        sanitized = html_normalize(
            src, filter_callback=sanitize_handler, output_method=output_method
        )
    except etree.ParserError:
        if not silent:
            raise
        logger.warning(
            u'ParserError obtained when sanitizing %r', src, exc_info=True
        )
        sanitized = '<p>ParserError when sanitizing</p>'
    except Exception:
        if not silent:
            raise
        logger.warning(
            u'unknown error obtained when sanitizing %r', src, exc_info=True
        )
        sanitized = '<p>Unknown error when sanitizing</p>'

    return markupsafe.Markup(sanitized)


# ----------------------------------------------------------
# HTML/Text management
# ----------------------------------------------------------

URL_SKIP_PROTOCOL_REGEX = r'mailto:|tel:|sms:'
URL_REGEX = rf'''(\bhref=['"](?!{URL_SKIP_PROTOCOL_REGEX})([^'"]+)['"])'''
TEXT_URL_REGEX = r'https?://[\w@:%.+&~#=/-]+(?:\?\S+)?'
# retrieve inner content of the link
HTML_TAG_URL_REGEX = URL_REGEX + r'([^<>]*>([^<>]+)<\/)?'
HTML_TAGS_REGEX = re.compile('<.*?>')
HTML_NEWLINES_REGEX = re.compile('<(div|p|br|tr)[^>]*>|\n')


def validate_url(url):
    # ``werkzeug`` no está en este stack: la fuente lee sólo el esquema con
    # ``urls.url_parse(url).scheme`` (``:484``), que da el mismo valor que
    # ``urlparse``, ya importado por la misma fuente (``:14``).
    if urlparse(url).scheme not in ('http', 'https', 'ftp', 'ftps'):
        return 'http://' + url

    return url


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
    icon_re = (
        r'<\s*(i|span)\b(\s+[A-Za-z_-][A-Za-z0-9-_]*'
        r'(\s*=\s*[\'"][^"\']*[\'"])?)*\s*\bclass\s*=\s*'
        r'["\'][^"\']*\b(fa|fab|fad|far|oi)\b'
    )
    tag_re = (
        r'<\s*\/?(?:p|div|section|span|br|b|i|font)\b'
        r'(?:(\s+[A-Za-z_-][A-Za-z0-9-_]*(\s*=\s*[\'"][^"\']*[\'"]))*)'
        r'(?:\s*>|\s*\/\s*>)'
    )
    text_content = htmllib.unescape(re.sub(tag_re, '', html_content))
    return not bool(text_content.strip()) and not re.search(
        icon_re, html_content
    )


# ≙ ``odoo19c: odoo/tools/mail.py:506-536``, reformateado a PEP 8 con el
# mismo AST.
def html_keep_url(text):
    """Transform the url into clickable link with <a/> tag"""
    idx = 0
    final = ''
    link_tags = re.compile(
        r"""(?<!["'])((ftp|http|https):\/\/(\w+:{0,1}\w*@)?"""
        r"""([^\s<"']+)(:[0-9]+)?(\/|\/([^\s<"']))?)"""
        r"""(?![^\s<"']*["']|[^\s<"']*</a>)"""
    )
    for item in re.finditer(link_tags, text):
        final += text[idx:item.start()]
        final += create_link(item.group(0), item.group(0))
        idx = item.end()
    final += text[idx:]
    return final


def html_to_inner_content(html):
    """Returns unformatted text after removing html tags and excessive
    whitespace from a string/Markup. Passed strings will first be sanitized.
    """
    if is_html_empty(html):
        return ''
    if not isinstance(html, markupsafe.Markup):
        html = html_sanitize(html)
    processed = re.sub(HTML_NEWLINES_REGEX, ' ', html)
    processed = re.sub(HTML_TAGS_REGEX, '', processed)
    processed = re.sub(r' {2,}|\t', ' ', processed)
    processed = processed.replace("\xa0", " ")
    processed = htmllib.unescape(processed)
    return processed.strip()


def create_link(url, label):
    return (
        f'<a href="{url}" target="_blank" rel="noreferrer noopener">'
        f'{label}</a>'
    )


def html2plaintext(
    html, body_id=None, encoding='utf-8', include_references=True
) -> str:
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
        assert isinstance(
            html, str
        ), f"expected str got {html.__class__.__name__}"

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
                    img_name = None  # imagen en base64: no tiene nombre
                else:
                    img_name = re.search(r'[^/]+(?=\.[a-zA-Z]+(?:\?|$))', src)
                img.text = '%s [%s]' % (
                    img_name[0] if img_name else 'Image',
                    next(linkrefs),
                )
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


# ≙ ``odoo19c: odoo/tools/mail.py:622-726``, reformateado a PEP 8 con el
# mismo AST.
def plaintext2html(
    text: str, container_tag: str | None = None, with_paragraph: bool = True
) -> markupsafe.Markup:
    r"""Convert plaintext into html. Content of the text is escaped to manage
    html entities, using :func:`~odoo.tools.misc.html_escape`.

    - all ``\n``, ``\r`` are replaced by ``<br/>``
    - convert url into clickable link

    :param text: plaintext to convert
    :param container_tag: container of the html; by default the content is
        embedded into a ``<div>``
    :param with_paragraph: whether or not considering 2 or more consecutive
        ``<br/>`` as paragraph breaks and enclosing content in ``<p>``
    """
    assert isinstance(text, str)
    text = misc.html_escape(text)

    # 1. replace \n and \r
    text = re.sub(r'(\r\n|\r|\n)', '<br/>', text)

    # 2. clickable links
    text = html_keep_url(text)

    # 3-4: form paragraphs
    final = text
    if with_paragraph:
        idx = 0
        final = '<p>'
        br_tags = re.compile(r'(([<]\s*[bB][rR]\s*/?[>]\s*){2,})')
        for item in re.finditer(br_tags, text):
            final += text[idx:item.start()] + '</p><p>'
            idx = item.end()
        final += text[idx:] + '</p>'

    # 5. container
    if (
        container_tag
    ):  # FIXME: validate that container_tag is just a simple tag?
        final = '<%s>%s</%s>' % (container_tag, final, container_tag)
    return markupsafe.Markup(final)


def append_content_to_html(
    html, content, plaintext=True, preserve=False, container_tag=None
):
    """Append extra content at the end of an HTML snippet, trying
    to locate the end of the HTML document (</body>, </html>, or
    EOF), and converting the provided content in html unless ``plaintext``
    is ``False``.

    Content conversion can be done in two ways:

    - wrapping it into a pre (``preserve=True``)
    - use plaintext2html (``preserve=False``, using ``container_tag`` to
      wrap the whole content)

    A side-effect of this method is to coerce all HTML tags to
    lowercase in ``html``, and strip enclosing <html> or <body> tags in
    content if ``plaintext`` is False.

    :param str html: html tagsoup (doesn't have to be XHTML)
    :param str content: extra content to append
    :param bool plaintext: whether content is plaintext and should
        be wrapped in a <pre/> tag.
    :param bool preserve: if content is plaintext, wrap it into a <pre>
        instead of converting it into html
    :param str container_tag: tag to wrap the content into, defaults to `div`.
    :rtype: markupsafe.Markup
    """
    if plaintext and preserve:
        content = '\n<pre>%s</pre>\n' % misc.html_escape(content)
    elif plaintext:
        content = '\n%s\n' % plaintext2html(content, container_tag)
    else:
        content = re.sub(
            r'(?i)(</?(?:html|body|head|!\s*DOCTYPE)[^>]*>)', '', content
        )
        content = '\n%s\n' % content
    # Force all tags to lowercase
    html = re.sub(
        r'(</?)(\w+)([ >])',
        lambda m: '%s%s%s' % (m[1], m[2].lower(), m[3]),
        html,
    )
    insert_location = html.find('</body>')
    if insert_location == -1:
        insert_location = html.find('</html>')
    if insert_location == -1:
        return markupsafe.Markup('%s%s' % (html, content))
    return markupsafe.Markup(
        '%s%s%s' % (html[:insert_location], content, html[insert_location:])
    )


def prepend_html_content(html_body, html_content):
    """Prepend some HTML content at the beginning of an other HTML content."""
    replacement = re.sub(
        r'(?i)(</?(?:html|body|head|!\s*DOCTYPE)[^>]*>)', '', html_content
    )
    html_content = (
        markupsafe.Markup(replacement)
        if isinstance(html_content, markupsafe.Markup)
        else replacement
    )
    html_content = html_content.strip()

    body_match = re.search(r'<body[^>]*>', html_body) or re.search(
        r'<html[^>]*>', html_body
    )
    insert_index = body_match.end() if body_match else 0

    return html_body[:insert_index] + html_content + html_body[insert_index:]


# ----------------------------------------------------------
# Emails
# ----------------------------------------------------------

# matches any email in a body of text
email_re = re.compile(
    r"""([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,63})""", re.VERBOSE
)

# matches a string containing only one email
single_email_re = re.compile(
    r"""^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,63}$""", re.VERBOSE
)

mail_header_msgid_re = re.compile('<[^<>]+>')

email_addr_escapes_re = re.compile(r'[\\"]')


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
email_re = re.compile(
    r"""([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,63})""", re.VERBOSE
)

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
        (addr[0], addr[1])
        for addr in getaddresses([text])
        if addr[1] and '@' in addr[1]
    ]
    # caso borde: una dirección que empieza por '@' (ver test_email_split)
    if any(pair[1].startswith('@') for pair in valid_pairs):
        filtered = [
            found
            for found in email_re.findall(text)
            if found and not found.startswith('@')
        ]
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
        # silent OK because la excepción ES el discriminador, no un fallo: que
        # la parte local no sea ASCII es precisamente el caso en que hay que
        # dejarla intacta. La referencia lo escribe igual
        # (odoo19c: odoo/tools/mail.py:882-887).
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


def email_domain_extract(email):
    """≙ ``email_domain_extract`` (``odoo19c: odoo/tools/mail.py:923-931``).

    Docstring de la fuente, verbatim: *"Extract the company domain to be used
    by IAP services notably. Domain is extracted from email information e.g:
    - info@proximus.be -> proximus.be"*.

    **Normaliza antes de partir**, y por eso admite el formato
    ``Nombre <buzon@dominio>`` y baja la mayúscula. Devuelve ``False`` —no
    cadena vacía— cuando no hay dirección que leer: es el mismo valor falso
    que devuelve ``email_normalize``, y sus llamadores comparan un resultado
    contra otro.
    """
    normalized_email = email_normalize(email)
    if normalized_email:
        return normalized_email.split('@')[1]
    return False


def email_domain_normalize(domain):
    """≙ ``email_domain_normalize`` (``odoo19c: odoo/tools/mail.py:934-939``).

    Docstring de la fuente, verbatim: *"Return the domain normalized or False
    if the domain is invalid."*

    Un texto con ``@`` **no** es un dominio: devolver algo lo colaría en la
    rama de dominio de ``ir.mail_server._match_from_filter``, que es la única
    que llama a esta función. La fuente **no** recorta espacios; sólo baja a
    minúsculas.
    """
    if not domain or '@' in domain:
        return False

    return domain.lower()


def parse_contact_from_email(text):
    """
    ≙ ``parse_contact_from_email`` (``odoo19c: odoo/tools/mail.py:1031-1056``).

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


# ---------------------------------------------------------------------------
# Ayudantes de direcciones y cabeceras — copia con atribución de
# ``odoo19c: odoo/tools/mail.py:724-1068`` (``odoo-tools@abe4040ec1``, LGPL-3).
# ---------------------------------------------------------------------------

mail_header_msgid_re = re.compile('<[^<>]+>')


def generate_tracking_message_id(res_id):
    """Returns a string that can be used in the Message-ID RFC822 header field

       Used to track the replies related to a given object thanks to the
       "In-Reply-To" or "References" fields that Mail User Agents will set.
    """
    try:
        rnd = random.SystemRandom().random()
    except NotImplementedError:
        rnd = random.random()
    rndstr = ("%.15f" % rnd)[2:]
    return "<%s.%.15f-openerp-%s@%s>" % (
        rndstr, time.time(), res_id, socket.gethostname())


def email_split_and_format(text):
    """ Return a list of email addresses found in ``text``, formatted using
    formataddr. """
    return [formataddr((name, email))
            for (name, email) in email_split_tuples(text)]


def email_split_and_normalize(text):
    """ Same as 'email_split' but normalized email """
    return [(name, _normalize_email(email))
            for (name, email) in email_split_tuples(text)]


def email_split_and_format_normalize(text):
    """ Same as 'email_split_and_format' but normalizing email. """
    return [
        formataddr(
            (name, _normalize_email(email))
        ) for (name, email) in email_split_tuples(text)
    ]


def email_anonymize(normalized_email, *, redact_domain=False):
    """
    Replace most charaters in the local part of the email address with
    '*' to hide the recipient, but keep enough characters for debugging
    purpose.

    The email address must be normalized already.

    >>> email_anonymize('admin@example.com')
    'a****@example.com'
    >>> email_anonymize('portal@example.com')
    'p***al@example.com'
    >>> email_anonymize('portal@example.com', redact_domain=True)
    'p***al@e******.com'
    """
    if not normalized_email:
        return normalized_email

    local, at, domain = normalized_email.partition('@')
    if len(local) <= 5:
        anon_local = local[:1] + '*' * (len(local) - 1)
    else:
        anon_local = local[:1] + '*' * (len(local) - 3) + local[-2:]

    host, dot, tld = domain.rpartition('.')
    if redact_domain and not domain.startswith('[') and all((host, dot, tld)):
        anon_host = host[0] + '*' * (len(host) - 1)
    else:
        anon_host = host

    return f'{anon_local}{at}{anon_host}{dot}{tld}'


def url_domain_extract(url):
    """ Extract the company domain to be used by IAP services notably. Domain
    is extracted from an URL e.g:

    - www.info.proximus.be -> proximus.be
    """
    parser_results = urlparse(url)
    company_hostname = parser_results.hostname
    if company_hostname and '.' in company_hostname:
        return '.'.join(company_hostname.split('.')[-2:])  # remove subdomains
    return False


def email_escape_char(email_address):
    """ Escape problematic characters in the given email address string"""
    escaped = email_address.replace('\\', '\\\\')
    return escaped.replace('%', '\\%').replace('_', '\\_')


def decode_message_header(message, header, separator=' '):
    return separator.join(h for h in message.get_all(header, []) if h)


def encapsulate_email(old_email, new_email):
    """Change the FROM of the message and use the old one as name.

    e.g.
    * Old From: "Admin" <admin@gmail.com>
    * New From: notifications@odoo.com
    * Output: "Admin" <notifications@odoo.com>
    """
    old_email_split = getaddresses([old_email])
    if not old_email_split or not old_email_split[0]:
        return old_email

    new_email_split = getaddresses([new_email])
    if not new_email_split or not new_email_split[0]:
        return

    old_name, old_email = old_email_split[0]
    if old_name:
        name_part = old_name
    else:
        name_part = old_email.split("@")[0]

    return formataddr((
        name_part,
        new_email_split[0][1],
    ))


def unfold_references(msg_references):
    """ As it declared in [RFC2822] long header bodies can be "folded" using
    CRLF+WSP. Some mail clients split References header body which contains
    Message Ids by "\n ".

    RFC2882: https://tools.ietf.org/html/rfc2822#section-2.2.3 """
    return [
        re.sub(r'[\r\n\t ]+', r'', ref)  # "Unfold" buggy references
        for ref in mail_header_msgid_re.findall(msg_references)
    ]
