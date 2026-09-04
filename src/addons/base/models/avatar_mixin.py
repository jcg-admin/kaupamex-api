"""Modelo abstracto ``avatar.mixin`` — avatar con retrato generado.

Adaptación fiel de Odoo ``odoo/addons/base/models/avatar_mixin.py``
(``odoo-tools@bf077302``, ``odoo19c:``).

**Qué hace la referencia.** Hereda ``image.mixin`` y añade cinco campos
``avatar_*`` **computados**: si el registro tiene imagen, el avatar es esa
imagen; si no, genera un SVG con la inicial del nombre sobre un color derivado
por hash; y si tampoco hay nombre, devuelve un PNG gris de relleno.

**Qué cambia aquí.** Los cinco ``avatar_*`` no se persisten —en la referencia
tampoco: son ``compute`` sin ``store``—, así que son propiedades. El resto es
literal, incluida ``get_hsl_from_seed``: mismo hash SHA-512, mismos cortes de
dígitos y mismos rangos (matiz completo, saturación 40-70 %, luminosidad 45 %).
Se copia el algoritmo, no una aproximación, para que un mismo nombre produzca
el mismo color que allá.

``_avatar_name_field`` sigue siendo el punto de extensión: un modelo cuyo
nombre no esté en ``name`` lo redeclara.

No se porta ``_get_avatar_128_access_token``: depende de
``limited_field_access_token`` e ``ir_binary._find_record``, que son el
mecanismo de Odoo para servir binarios saltándose derechos de acceso. Aquí los
binarios los sirve Django con el storage y el gate de capacidad de la vista.
"""
from base64 import b64encode
from hashlib import sha512
from html import escape as html_escape

from django.db import models

from addons.base.models.image_mixin import ImageMixin

# Ruta del PNG de relleno, homóloga de ``base/static/img/avatar_grey.png``.
_PLACEHOLDER_PATH = 'base/static/img/avatar_grey.png'


def get_hsl_from_seed(seed):
    """Color estable derivado de una semilla — verbatim de la referencia.

    Los cortes del hash y los rangos son los de allá: matiz sobre los 360°
    completos, saturación entre 40 % y 70 % ("colorful result but not too
    flashy", dice el comentario original) y luminosidad fija en 45 % ("not too
    bright and not too dark").
    """
    hashed_seed = sha512(seed.encode()).hexdigest()
    hue = int(hashed_seed[0:2], 16) * 360 / 255
    sat = int(hashed_seed[2:4], 16) * ((70 - 40) / 255) + 40
    lig = 45
    return f'hsl({hue:.0f}, {sat:.0f}%, {lig:.0f}%)'


class AvatarMixin(ImageMixin):
    """Avatar: la imagen del registro, o un retrato generado (``avatar.mixin``).

    Los cinco ``avatar_*`` son derivados, no columnas — igual que el
    ``compute`` sin ``store`` de la referencia.
    """

    #: Campo del que sale la inicial y la semilla del color. Un modelo cuyo
    #: nombre viva en otro campo redeclara este atributo, como allá.
    _avatar_name_field = 'name'

    class Meta:
        abstract = True

    def _compute_avatar(self, image_field):
        """El avatar de un tamaño: la imagen si existe, si no el retrato."""
        image = getattr(self, image_field, None)
        if image:
            return image
        if self.pk and getattr(self, self._avatar_name_field, None):
            return self._avatar_generate_svg()
        return b64encode(self._avatar_get_placeholder())

    @property
    def avatar_1920(self):
        """≙ ``_compute_avatar_1920`` (``odoo19c: base/models/avatar_mixin.py``)."""
        return self._compute_avatar('image_1920')

    @property
    def avatar_1024(self):
        """≙ ``_compute_avatar_1024`` (``odoo19c: base/models/avatar_mixin.py``)."""
        return self._compute_avatar('image_1024')

    @property
    def avatar_512(self):
        """≙ ``_compute_avatar_512`` (``odoo19c: base/models/avatar_mixin.py``)."""
        return self._compute_avatar('image_512')

    @property
    def avatar_256(self):
        """≙ ``_compute_avatar_256`` (``odoo19c: base/models/avatar_mixin.py``)."""
        return self._compute_avatar('image_256')

    @property
    def avatar_128(self):
        """≙ ``_compute_avatar_128`` (``odoo19c: base/models/avatar_mixin.py``)."""
        return self._compute_avatar('image_128')

    def _avatar_generate_svg(self):
        """SVG de 180×180 con la inicial sobre el color de la semilla.

        La semilla es ``nombre + timestamp de creación``, como en la
        referencia: dos registros homónimos creados en instantes distintos no
        comparten color.
        """
        name = getattr(self, self._avatar_name_field) or ''
        initial = html_escape(name[0].upper())
        created = getattr(self, 'created_at', None)
        bgcolor = get_hsl_from_seed(name + str(created.timestamp() if created else ''))
        return b64encode((
            "<?xml version='1.0' encoding='UTF-8' ?>"
            "<svg height='180' width='180' xmlns='http://www.w3.org/2000/svg' "
            "xmlns:xlink='http://www.w3.org/1999/xlink'>"
            f"<rect fill='{bgcolor}' height='180' width='180'/>"
            f"<text fill='#ffffff' font-size='96' text-anchor='middle' x='90' "
            f"y='125' font-family='sans-serif'>{initial}</text>"
            "</svg>"
        ).encode())

    def _avatar_get_placeholder_path(self):
        return _PLACEHOLDER_PATH

    def _avatar_get_placeholder(self):
        """PNG gris de relleno; b'' si el archivo no está desplegado."""
        try:
            with open(self._avatar_get_placeholder_path(), 'rb') as fh:
                return fh.read()
        except OSError:
            # La referencia falla si falta el asset; aquí el avatar es
            # decorativo y no debe tumbar una respuesta. El vacío es
            # observable por el consumidor.
            return b''
