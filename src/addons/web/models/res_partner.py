"""``res.partner`` extendido por ``web`` — descarga de vCard.

Adaptación de ``odoo19c: addons/web/models/res_partner.py``
(``odoo-tools@622ddc2a``, 98 líneas, LGPL-3 — atribución y aviso de licencia
preservados, DEC-KX-03). Extiende ``res.partner`` (portado en
``base/models/res_partner.py``, H-API-119) con la construcción de la vCard
(RFC 6350) de un contacto — lo que descarga el botón "vCard" de la ficha.

Medición símbolo-por-símbolo (``re.findall(r'^\\s{4}def (\\w+)', ref)``,
mismo criterio que ``porte-completo-no-parcial.md``): **2** métodos de
``ResPartner`` (``_build_vcard``, ``_get_vcard_file``). Las tres clases
``V*Proxy`` del módulo no cuentan — son adaptadores internos de la librería
``vobject``, no miembros de ``ResPartner``. **2 portados** (con divergencia
de mecanismo declarada abajo), **0 ausentes**.

Divergencia de mecanismo — sin ``vobject``
===========================================

La referencia serializa con ``vobject`` (``import vobject.vcard``), que no
está en ``pyproject.toml`` — no es un mecanismo del ORM que Django no tenga
(``porte-completo-no-parcial.md`` exige construir esos), es una librería de
serialización de texto de terceros. El formato vCard 3.0 (RFC 6350) es texto
plano con reglas de escape simples: se construye aquí a mano
(``_vcard_escape`` + ``_build_vcard``), sin agregar la dependencia, y
produce exactamente los mismos ocho campos que la referencia puebla
(``N``, ``FN``, ``ADR``, ``EMAIL``, ``TEL``, ``URL``, ``ORG``, ``TITLE``,
``PHOTO``) — mismos datos de origen, mismas condiciones de "si existe".

``self.complete_name`` no existe aquí
======================================

La referencia usa ``self.name or self.complete_name or ''`` como respaldo
del nombre para forma (`N`) y nombre formateado (`FN`). ``complete_name`` es
un ``compute`` que ``base/models/res_partner.py`` (docstring, sección de
campos excluidos) ya declaró fuera de este árbol junto con
``display_name``/``email_formatted``/``company_type``. Como ``name`` es
requerido en este modelo (``base/models/res_partner.py:66-69``, sin
``blank=True``), el respaldo es inalcanzable en la referencia misma para un
registro válido — se porta como ``self.name`` solo, sin el ``or`` muerto.

El avatar no es siempre base64 — divergencia de ``AvatarMixin``
===================================================================

La referencia asume que ``self.avatar_512`` es SIEMPRE base64 (Binary field
de Odoo) y hace ``b64decode(self.avatar_512)`` sin mirar la rama.
``AvatarMixin._compute_avatar`` (``avatar_mixin.py:68-74``) aquí devuelve dos
formas distintas según haya o no imagen real cargada: un ``ImageFieldFile``
del storage de Django (NO es base64: es el archivo) cuando el registro tiene
``image_512``, o bytes base64 (``b64encode(...)``, líneas 74 y 105) cuando
genera el SVG de iniciales o cae al placeholder gris. ``_avatar_raw_bytes``
distingue las dos ramas antes de construir el campo ``PHOTO`` — b64decode
sin distinguir rompería con un ``ImageFieldFile`` real.
"""
from base64 import b64decode, b64encode

from orm.method_chain import chain_method

from addons.base.models.res_partner import ResPartner


def _vcard_escape(value):
    """Escapa ``,`` ``;`` ``\\`` y saltos de línea — RFC 6350 §3.4.

    Los mismos cuatro caracteres que exige la gramática ``TEXT`` del
    estándar; el orden importa (``\\`` primero, o se escaparía dos veces).
    """
    return (
        (value or '')
        .replace('\\', '\\\\')
        .replace(',', '\\,')
        .replace(';', '\\;')
        .replace('\n', '\\n')
    )


def _avatar_raw_bytes(self):
    """Bytes crudos del avatar — imagen real del storage, o SVG/placeholder.

    Ver la sección "El avatar no es siempre base64" del docstring del
    módulo: ``avatar_512`` puede ser un ``ImageFieldFile`` (imagen real,
    ``.read()`` da los bytes tal cual) o bytes base64 (SVG generado o
    placeholder, hay que decodificar). Devuelve ``b''`` si no hay nada que
    fotografiar (mismo comportamiento decorativo que
    ``AvatarMixin._avatar_get_placeholder`` documenta para su propio vacío).
    """
    avatar = self.avatar_512
    if not avatar:
        return b''
    if hasattr(avatar, 'read'):
        avatar.open('rb')
        try:
            return avatar.read()
        finally:
            avatar.close()
    return b64decode(avatar)


def _build_vcard(self):
    """≙ ``_build_vcard`` (``odoo19c: web/models/res_partner.py:45-91``).

    Construye el texto vCard 3.0 completo del contacto — nombre, dirección,
    email, teléfono, sitio web, empresa, puesto y foto — cada campo sólo si
    hay dato, igual que la referencia. Devuelve ``str`` (la referencia
    devuelve el objeto ``vobject.vCard``; aquí no hay ese objeto intermedio,
    ver la divergencia de mecanismo del docstring del módulo).
    """
    lines = ['BEGIN:VCARD', 'VERSION:3.0']

    name = self.name
    lines.append(f'N:{_vcard_escape(name)};;;;')
    lines.append(f'FN:{_vcard_escape(name)}')

    if self.street or self.city or self.zip or self.state or self.country:
        region = self.state.name if self.state else ''
        country = self.country.name if self.country else ''
        lines.append(
            'ADR;TYPE=work:;;{};{};{};{};{}'.format(
                _vcard_escape(self.street), _vcard_escape(self.city),
                _vcard_escape(region), _vcard_escape(self.zip),
                _vcard_escape(country),
            )
        )

    if self.email:
        lines.append(f'EMAIL;TYPE=INTERNET:{_vcard_escape(self.email)}')

    if self.phone:
        lines.append(f'TEL;TYPE=work:{_vcard_escape(self.phone)}')

    if self.website:
        lines.append(f'URL:{_vcard_escape(self.website)}')

    if self.commercial_company_name:
        lines.append(f'ORG:{_vcard_escape(self.commercial_company_name)}')

    if self.function:
        lines.append(f'TITLE:{_vcard_escape(self.function)}')

    photo = _avatar_raw_bytes(self)
    if photo:
        lines.append(
            'PHOTO;ENCODING=b;TYPE=JPEG:' + b64encode(photo).decode()
        )

    lines.append('END:VCARD')
    return '\r\n'.join(lines)


def _get_vcard_file(self):
    """≙ ``_get_vcard_file`` (``odoo19c: web/models/res_partner.py:93-97``).

    Serializa a bytes con terminador ``\\r\\n`` (RFC 6350 §3.2) — la
    referencia llama ``vcard.serialize().encode()``, que produce el mismo
    formato; aquí ``_build_vcard`` ya arma el texto completo, así que basta
    codificar.
    """
    vcard = _build_vcard(self)
    if vcard:
        return vcard.encode()
    return False


def apply_web_extensions():
    """Cuelga la construcción de vCard sobre ``base.ResPartner`` — ≙ ``_inherit``.

    Se invoca desde ``WebConfig.ready()`` (pendiente de sumar
    ``'addons.web.models.res_partner'`` a ``WebConfig._EXTENSIONES`` — fase
    de consolidación, junto con el resto de extensiones del batch), cuando
    el registro de modelos ya está poblado y ``setattr`` sobre
    ``base.ResPartner`` no rompe con ``AppRegistryNotReady``. Mismo patrón
    que ``ir_http.py::apply_web_extensions``.
    """
    chain_method(ResPartner, '_build_vcard', _build_vcard)
    chain_method(ResPartner, '_get_vcard_file', _get_vcard_file)
