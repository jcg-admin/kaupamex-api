"""``ir.attachment`` extendido por ``html_editor`` — la imagen vista por el editor.

Adaptación de ``odoo19c: addons/html_editor/models/ir_attachment.py``
(86 líneas, LGPL-3 — copia + adaptación con atribución, DEC-KX-03).

**9 símbolos en la fuente: 8 portados, 1 bloqueado con sucesor.** Una
constante, cinco campos, tres métodos.

Qué hace
========

El editor no manipula archivos: manipula **URL de imagen**. Este archivo es lo
que traduce un adjunto a las tres cosas que el editor necesita — la URL para
pintarlo, su tamaño real para no deformarlo, y el enlace al original sin
recortar para poder volver atrás.

Qué pieza de este stack cubre cada delegación de la fuente
==========================================================

===============================  =====================================
Fuente delega en                 Aquí lo cubre
===============================  =====================================
``compute`` sin ``store``        **django** — ``property``, la forma que
                                 ``extend_model(propiedades=…)`` fija
``odoo.tools.image``             **cpython + Pillow** — el par
(``base64_to_image``)            ``Image.open``/``verify`` (ver la
                                 divergencia 2)
``_read_format``                 **django** — un ``dict`` explícito con
                                 la misma lista de campos
``ir.attachment.datas``          **django** — ``FileField`` (así lo
(base64 en la fuente)            declara ``base``: sin el filestore de
                                 la referencia)
===============================  =====================================

Divergencia 1 — el enlace al original, detenido con su arista
==============================================================

BLOQUEADO por ``src/addons/base/migrations`` — el campo es de un modelo de
otra app y su ``AddField`` aterriza en la migración de ``base``, que está
fuera de los archivos de este puerto. Sucesor: declararlo desde ``base`` (o
autorizar a este puerto a escribir la migración de ``base``).

La fuente declara ``original_id = fields.Many2one('ir.attachment', …)``: el
enlace de una imagen recortada/optimizada a su original. Aquí **no se
instala**, y el motivo es medido, no de comodidad:

- ``ir.attachment`` lo declara el addon ``base``, bajo ``src/addons/base/``.
- El autodetector de Django emite el ``AddField`` de un campo **en la app
  dueña del modelo**, así que su migración aterrizaría en
  ``src/addons/base/migrations/`` — fuera de los archivos que este puerto
  tiene asignados. El precedente del árbol lo confirma:
  ``hr_recruitment_skills`` cuelga ``skill_ids`` sobre ``hr.HrApplicant`` y su
  migración vive en ``addons/hr_recruitment/migrations/``, no en la del addon
  que lo cuelga.
- Instalar el campo **sin** su columna no es media medida: es una avería. La
  base de pruebas es compartida, y cada ``IrAttachment.objects…`` pasaría a
  seleccionar una columna inexistente — reventando a todo el que la use.

**Sucesor nombrado:** declarar ``original_id`` sobre ``base.IrAttachment`` y
generar su migración en ``src/addons/base/migrations/``. Se reporta al
orquestador como el sucesor de esta divergencia.

**Cómo queda el código mientras tanto, sin mentir.** Los dos consumidores del
campo viven en ``controllers/main.py`` (``get_image_info`` lo lee,
``modify_image`` lo escribe) y hablan con él a través de las dos funciones de
costura de este módulo — :func:`original_attachment_of` y
:func:`set_original_attachment` — que devuelven ``None`` y no hacen nada
mientras el campo no exista, y pasan a leer y escribir el campo real en cuanto
el sucesor lo instale, **sin tocar a los consumidores**.

Divergencia 2 — ``base64_to_image`` no tiene hogar en este árbol
================================================================

La fuente importa ``odoo.tools.image.base64_to_image``. Su hogar aquí sería
``src/tools/image.py``, que **no existe** — el árbol resuelve el manejo de
imagen en ``src/addons/base/models/image_mixin.py`` (``_resize``) y en
``src/tools/barcode.py``, los dos con ``PIL.Image`` directo.

``src/tools`` está fuera de los archivos de este puerto, así que la conversión
va aquí como función privada :func:`_attachment_to_image`, con el mismo
contrato de la fuente: devuelve una imagen abierta o levanta. Se reporta al
orquestador como sucesor: mover ``base64_to_image``/``image_process`` a
``src/tools/image.py``, el sitio que la referencia les da, y hacer que este
archivo y ``tools.py`` lo importen de ahí.

Censo símbolo a símbolo
=======================

===============================  ==========  =========================
Símbolo de la fuente             Estado      Nota
===============================  ==========  =========================
``SUPPORTED_IMAGE_MIMETYPES``    portado     verbatim
``local_url``                    portado     ``property``
``image_src``                    portado     ``property``
``image_width``                  portado     ``property``
``image_height``                 portado     ``property``
``original_id``                  detenido    divergencia 1, con arista
``_compute_local_url``           portado     nombre y guion bajo verbatim
``_compute_image_src``           portado     ídem
``_compute_image_size``          portado     ídem; devuelve el par
``_get_media_info``              portado     ``_read_format`` → dict
``_can_bypass_rights_on_media_dialog``  portado  enganche, como allá
===============================  ==========  =========================
"""
from urllib.parse import quote

from addons.base.models.ir_attachment import IrAttachment
from django.core.exceptions import ValidationError
from orm.model_classes import extend_model
from PIL import Image, UnidentifiedImageError

SUPPORTED_IMAGE_MIMETYPES = {
    'image/gif': '.gif',
    'image/jpe': '.jpe',
    'image/jpeg': '.jpeg',
    'image/jpg': '.jpg',
    'image/png': '.png',
    'image/svg+xml': '.svg',
    'image/webp': '.webp',
}

#: ≙ ``_inherit = "ir.attachment"`` (``odoo19c: :20``).
#:
#: **Se nombra por el par de Django, no por el nombre punteado**, y no es una
#: preferencia: ``src/addons/base/models/ir_attachment.py`` **no declara**
#: ``_name`` en su clase ``IrAttachment`` (sí lo declaran sus hermanas de
#: ``ir_ui_view.py``), así que ``resolve_model_key('ir.attachment')`` levanta
#: ``LookupError``. El par ``('base', 'IrAttachment')`` designa el mismo
#: destino y no depende de esa declaración.
#:
#: **Es un hueco de** ``atributos-de-clase-de-modelo.md``: la clase de la
#: referencia declara ``_name = 'ir.attachment'`` y ``_description``, y el
#: puerto de ``base`` no los lleva. Vive en ``src/addons/base`` y por tanto
#: fuera de los archivos de este puerto; se reporta al orquestador como
#: sucesor. En cuanto ``base`` lo declare, esta constante puede volver al
#: nombre punteado sin tocar nada más.
_inherit = ('base', 'IrAttachment')


def original_attachment_of(attachment):
    """El adjunto original de ``attachment`` — ≙ leer ``original_id``.

    Costura de la divergencia 1: hoy devuelve ``None`` porque el campo no está
    instalado; el día que el sucesor lo declare, este cuerpo pasa a
    ``attachment.original_id`` y ningún consumidor cambia.
    """
    return getattr(attachment, 'original_id', None)


def set_original_attachment(values, original):
    """Anota el original en el ``dict`` de valores — ≙ escribir ``original_id``.

    Costura de la divergencia 1. Mientras el campo no exista, **no** siembra la
    clave: hacerlo reventaría el ``copy`` que la consume.
    """
    if any(f.name == 'original_id' for f in IrAttachment._meta.get_fields()):
        values['original_id'] = original.pk if original is not None else None
    return values


def _attachment_to_image(attachment):
    """Abre el contenido del adjunto como imagen — ≙ ``base64_to_image``.

    Ver la divergencia 2. La fuente recibe base64 porque su ``datas`` lo es;
    aquí ``datas`` es un ``FileField`` (así lo declara ``base``), de modo que
    el contenido se lee del almacenamiento.

    :raises ValidationError: cuando el contenido no es una imagen que Pillow
        reconozca — ≙ el ``UserError`` que la fuente atrapa en
        ``_compute_image_size``.
    """
    if not attachment.datas:
        raise ValidationError('El adjunto no tiene contenido.')
    try:
        attachment.datas.open()
        image = Image.open(attachment.datas)
        image.load()
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise ValidationError(str(error))
    finally:
        if attachment.datas:
            attachment.datas.seek(0)
    return image


def _compute_local_url(self):
    """≙ ``_compute_local_url`` (``odoo19c: :27-32``)."""
    if self.url:
        return self.url
    return '/web/image/%s?unique=%s' % (self.pk, self.checksum)


def _compute_image_src(self):
    """≙ ``_compute_image_src`` (``odoo19c: :34-59``).

    La fuente lo declara ``@api.depends('mimetype', 'url', 'name')``; aquí es
    una ``property``, así que la dependencia se resuelve al leer y el decorador
    no tiene receptor.
    """
    # Sólo se añade un src para las imágenes soportadas.
    if not self.mimetype or self.mimetype.split(';')[0] not in SUPPORTED_IMAGE_MIMETYPES:
        return False

    if self.type == 'url':
        if self.url.startswith('/'):
            # URL local
            return self.url
        name = quote(self.name)
        return '/web/image/%s-redirect/%s' % (self.pk, name)

    # Se añade unique a las URL para el control de caché.
    unique = (self.checksum or '')[:8]
    if self.url:
        # Para los adjuntos por url, unique rompe la caché. Hoy no
        # aprovechan las cabeceras max-age.
        separator = '&' if '?' in self.url else '?'
        return '%s%sunique=%s' % (self.url, separator, unique)
    name = quote(self.name)
    return '/web/image/%s-%s/%s' % (self.pk, unique, name)


def _compute_image_size(self):
    """≙ ``_compute_image_size`` (``odoo19c: :61-70``).

    **Divergencia de forma:** la fuente escribe los dos campos calculados del
    registro; aquí devuelve el par ``(ancho, alto)`` y las dos ``property``
    toman su mitad. Un método no puede escribir dos ``property`` distintas.
    """
    try:
        image = _attachment_to_image(self)
    except ValidationError:
        return 0, 0
    return image.width, image.height


def _image_width(self):
    """≙ el campo calculado ``image_width`` (``odoo19c: :24``)."""
    return self._compute_image_size()[0]


def _image_height(self):
    """≙ el campo calculado ``image_height`` (``odoo19c: :25``)."""
    return self._compute_image_size()[1]


def _get_media_info(self):
    """≙ ``_get_media_info`` (``odoo19c: :72-75``).

    Devuelve un dict con los valores que el diálogo de medios necesita.

    **Divergencia de mecanismo:** la fuente usa ``_read_format`` sobre un
    conjunto de registros. Aquí ``self`` es una instancia y no hay
    ``_read_format`` en el árbol, así que el dict se construye con **la misma
    lista de campos**, en el mismo orden. Lo que ``_read_format`` aporta y aquí
    no hace falta es el aplanado de un ``Many2one`` a ``(id, display_name)``:
    el único relacional de la lista es ``original_id``, hoy bloqueado.
    """
    original = original_attachment_of(self)
    return {
        'id': self.pk,
        'name': self.name,
        'description': self.description,
        'mimetype': self.mimetype,
        'checksum': self.checksum,
        'url': self.url,
        'type': self.type,
        'res_id': self.res_id,
        'res_model': self.res_model,
        'public': self.public,
        'access_token': self.access_token,
        'image_src': self.image_src,
        'image_width': self.image_width,
        'image_height': self.image_height,
        'original_id': original.pk if original is not None else False,
    }


def _can_bypass_rights_on_media_dialog(self, **attachment_data):
    """≙ ``_can_bypass_rights_on_media_dialog`` (``odoo19c: :77-86``).

    Este método está pensado para sobreescribirse, por ejemplo para permitir
    crear un adjunto de imagen aunque el usuario no tenga permiso de crear
    adjuntos:

    - un usuario del portal subiendo una imagen al foro (salta la acl);
    - un usuario no administrador subiendo una imagen de unsplash (salta la
      comprobación binario/url).
    """
    return False


def apply_html_editor_extensions():
    """Cuelga las cuatro ``property`` y los métodos — ≙ ``_inherit``.

    La llama ``HtmlEditorConfig.ready()``. ``original_id`` **no** entra: ver
    la divergencia 1 del docstring del módulo.
    """
    # El par se escribe **literal**, no ``*_inherit``: ``extend_model`` es una
    # declaración de qué se instala y sobre qué clase, y un desempaquetado la
    # vuelve ilegible para el recorrido estático de ``check_porte_completo``,
    # que entonces publica ``CLASE AUSENTE`` sobre un porte que sí está. La
    # constante ``_inherit`` sigue arriba porque es donde se documenta el
    # destino; aquí manda la forma que se puede leer sin ejecutar.
    extend_model(
        'base', 'IrAttachment',
        propiedades={
            'local_url': _compute_local_url,
            'image_src': _compute_image_src,
            'image_width': _image_width,
            'image_height': _image_height,
        },
        metodos={
            '_compute_local_url': _compute_local_url,
            '_compute_image_src': _compute_image_src,
            '_compute_image_size': _compute_image_size,
            '_get_media_info': _get_media_info,
            '_can_bypass_rights_on_media_dialog':
                _can_bypass_rights_on_media_dialog,
        },
    )
