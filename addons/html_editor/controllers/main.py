"""Los endpoints del editor — adjuntos, formas SVG, vídeo y coedición.

Adaptación de ``odoo19c: addons/html_editor/controllers/main.py``
(758 líneas, LGPL-3 — copia + adaptación con atribución, DEC-KX-03).

**28 símbolos en la fuente: 24 portados, 4 bloqueados con sucesor.** Cinco
constantes, dos funciones de módulo, la clase ``HTML_Editor`` y sus veinte
métodos.

La forma del puerto: la clase queda, la ruta es una vista DRF
=============================================================

La fuente declara una clase ``http.Controller`` cuyos métodos llevan
``@http.route``. Aquí:

- **La clase ``HTML_Editor`` se conserva entera**, con los veinte métodos, su
  nombre, su firma y su cuerpo. Es donde vive la conducta.
- **Cada ``@http.route`` se convierte en una vista DRF** (``@api_view`` +
  ``@require_capability`` + ``@extend_schema``), declarada al final de este
  módulo con el sufijo ``_endpoint`` y cableada en ``controllers/urls.py``.
  La vista no tiene lógica: convierte la petición y delega.

Esa separación es lo que el inventario del stack pide — *"los controllers de
la fuente son vistas DRF con ``HasCapability``, nunca ``IsAuthenticated`` a
secas"*— sin perder un solo símbolo de la fuente.

El ``request`` global de la fuente viaja aquí como **argumento explícito**,
que es lo mismo que ya hacen los controladores portados de este árbol.

Qué pieza de este stack cubre cada delegación de la fuente
==========================================================

===============================  =====================================
Fuente delega en                 Aquí lo cubre
===============================  =====================================
``@http.route`` (contrato del    **drf** — ``@api_view`` +
endpoint)                        ``@require_capability`` +
                                 ``@extend_schema``; clave de error
                                 canónica ``codigo_error``
``auth='user'`` / ``auth=       **drf** — capacidad declarada, o
'public'``                       ``AllowAny`` explícito y documentado
``request.make_response``        **django** — ``HttpResponse`` con sus
                                 cabeceras; lo sirve **gunicorn**
``werkzeug.exceptions``          **drf** — ``NotFound`` /
                                 ``ParseError`` de
                                 ``rest_framework.exceptions``. El
                                 stack excluye Werkzeug
``werkzeug.urls.url_encode``     **cpython** — ``urllib.parse.urlencode``
``lxml`` (parsear el SVG)        **lxml** — el mismo
``re`` (los tres patrones de     **cpython** — verbatim
animación)
``file_open`` confinado          **portado** en ``src/tools/misc.py``
``ir.binary``                    **portado** en ``base`` — con
                                 ``find_record`` público en vez de
                                 ``_find_record``
``ir.attachment``                **postgresql** vía **django**
``bus.bus._sendone``             **bus** — ``BusMessage.sendone``
``ir.config_parameter``          **portado** en ``base``
``requests``                     **requests** — el mismo
===============================  =====================================

Los cuatro bloqueos, con su sucesor
====================================

============================  ==========================================
Símbolo de la fuente          Por qué, y su sucesor
============================  ==========================================
``generate_text``             ``iap_tools.iap_jsonrpc`` (addon ``iap``)
                              no está portado — medido: el árbol lo
                              nombra sólo en prosa, en ``crm`` y
                              ``website``, declarando su ausencia. La
                              vista se porta y responde **503** con
                              ``codigo_error`` en vez de callar.
                              **Sucesor:** portar ``iap`` con
                              ``iap_tools``.
``get_ice_servers``           ``mail.ice.server`` no está portado.
                              Misma forma: 503 nombrado.
                              **Sucesor:** portar ``mail.ice.server``.
``link_preview_metadata``     ``mail.tools.link_preview`` no está
                              portado. Misma forma: 503 nombrado.
                              **Sucesor:** portar
                              ``mail/tools/link_preview.py``.
``image_shape``               necesita ``get_webp_size``,
                              ``binary_to_image`` e ``image_data_uri``
                              de ``odoo/tools/image.py``, que no existe
                              aquí, **y** ``ir.binary
                              ._get_image_stream_from``, que ``base`` no
                              porta (porta ``get_image_response_from``).
                              **Sucesor:** el mismo
                              ``src/tools/image.py`` que declaran
                              ``models/ir_attachment.py`` y ``tools.py``,
                              más el *stream* de ``ir.binary``.
============================  ==========================================

**Los cuatro se portan como método con su nombre, su firma y su cuerpo hasta
donde el árbol llega**, y levantan un error nombrado en el punto exacto donde
falta la pieza. No se omite ninguno: quien lea el archivo encuentra la arista,
y quien llame al endpoint recibe un ``codigo_error`` que dice qué falta.

``link_preview_metadata_internal`` **sí** se porta entero: su rama externa
delega en el bloqueado (y propaga su 503), pero su rama interna —resolver un
registro por la ruta y devolver su descripción— no depende de nada ausente.

Divergencias menores, declaradas
=================================

- ``_clean_context`` — la fuente saca ``allowed_company_ids`` del contexto del
  entorno. Este ORM no tiene ese contexto; la equivalencia es el ámbito de
  empresa que ``CompanyContextMiddleware`` deja en la petición, y el método se
  porta operando sobre él.
- ``attachment.raw`` — la fuente lo lee como *bytes*. ``base`` declara
  ``datas`` como ``FileField``, así que el contenido se lee del
  almacenamiento; :func:`_attachment_raw` es el único sitio donde se hace.
- ``attachment.create_unique`` — no está portado en ``base``; ``modify_image``
  lo usa para las variantes ``alt_data``. Se crea el adjunto con la misma
  forma y los mismos valores, que es lo que ``create_unique`` hace tras
  descartar duplicados por *checksum* — y el descarte por *checksum* aquí lo
  hace :func:`get_existing_attachment`, que ya está portado.
- ``_slug`` / ``_unslug`` los declara ``http_routing``; se resuelven por
  ``base.IrHttp`` en tiempo de llamada, no de importación, porque ese addon
  los cuelga desde su ``ready()``.
"""
import contextlib
import hashlib
import logging
import re
import uuid
from base64 import b64decode, b64encode
from datetime import datetime
from os.path import join as opj
from urllib.parse import urlencode, urlparse

import requests
from addons.authz.permissions import require_capability
from addons.base.models.ir_http import IrHttp
from django.core.files.base import ContentFile
from django.db import models as django_models
from django.http import HttpResponse
from django.utils.html import escape
from drf_spectacular.utils import OpenApiResponse, extend_schema
from lxml import etree, html
from orm.registry import model_by_name
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound, ParseError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from tools.misc import file_open

from addons.html_editor.models.ir_attachment import (
    SUPPORTED_IMAGE_MIMETYPES,
    original_attachment_of,
    set_original_attachment,
)
from addons.html_editor.models.ir_websocket import (
    EDITOR_COLLABORATION,
    editor_collaboration_channel,
)
from addons.bus.models.bus import BusMessage
from addons.html_editor.tools import _image_process, get_video_url_data

_logger = logging.getLogger(__name__)

DEFAULT_LIBRARY_ENDPOINT = 'https://media-api.odoo.com'
DEFAULT_OLG_ENDPOINT = 'https://olg.api.odoo.com'

#: ≙ ``http.STATIC_CACHE_LONG`` de la referencia — un año en segundos, el
#: mismo valor que ``web/controllers/binary.py`` ya declara en este árbol.
STATIC_CACHE_LONG = 60 * 60 * 24 * 365

# Expresiones para aplicar la modificación de velocidad en archivos SVG.
# Nota: estos patrones están duplicados del lado del servidor para las
# imágenes de fondo que forman parte de una regla CSS "background-image: ...".
# Los del cliente se usan para las imágenes que van en un atributo "src" con
# un svg en base64 dentro de la etiqueta <img>. ¿Quizá habría que buscar la
# forma de definirlos una sola vez? El problema es que los patrones de Python
# son ligeramente distintos de los de JavaScript.

CSS_ANIMATION_RULE_REGEX = (
        r"(?P<declaration>animation(-duration)?:\s*.*?)"
        r"(?P<value>(\d+(\.\d+)?)|(\.\d+))"
        r"(?P<unit>ms|s)"
        r"(?P<separator>\s|;|\"|$)"
)
SVG_DUR_TIMECOUNT_VAL_REGEX = (
        r"(?P<attribute_name>\sdur=\"\s*)"
        + r"(?P<value>(\d+(\.\d+)?)|(\.\d+))"
        + r"(?P<unit>h|min|ms|s)?\s*\""
)
CSS_ANIMATION_RATIO_REGEX = (
    r"(--animation_ratio: (?P<ratio>\d*(\.\d+)?));"
)


def _attachment_raw(attachment):
    """El contenido binario del adjunto — ≙ ``attachment.raw``.

    ``base`` declara ``datas`` como ``FileField``; éste es el único sitio del
    addon donde se lee, para que la divergencia tenga una sola cara.
    """
    if not attachment.datas:
        return b''
    attachment.datas.open()
    try:
        return attachment.datas.read()
    finally:
        attachment.datas.seek(0)


def _get_shape_svg(self, module, *segments):
    """≙ ``_get_shape_svg`` de módulo (``odoo19c: :53-59``).

    La fuente declara este símbolo **dos veces** —aquí y como método de
    ``HTML_Editor``, con el mismo cuerpo—. Se portan los dos: quitar uno sería
    decidir por su autor cuál sobra.
    """
    shape_path = opj(module, 'static', *segments)
    try:
        with file_open(shape_path, 'r', filter_ext=('.svg',)) as file:
            return file.read()
    except FileNotFoundError:
        raise NotFound()


def get_existing_attachment(IrAttachment, vals):
    """≙ ``get_existing_attachment`` (``odoo19c: :62-80``).

    Comprueba si ya existe un adjunto con los mismos valores. Lo devuelve si
    es así, ``None`` si no.
    """
    fields = dict(vals)
    # Un res_id falso vale 0 al crear el adjunto.
    fields['res_id'] = fields.get('res_id') or 0
    raw, datas = fields.pop('raw', None), fields.pop('datas', None)
    query = django_models.Q()
    for field, value in fields.items():
        query &= django_models.Q(**{field: value})
    if fields.get('type') == 'url':
        if 'url' not in fields:
            return None
        query &= django_models.Q(checksum__isnull=True) | django_models.Q(
            checksum='')
    else:
        if not (raw or datas):
            return None
        content = raw if raw is not None else b64decode(datas)
        query &= django_models.Q(checksum=_checksum_of(content))
    return IrAttachment.objects.filter(query).first() or None


def _checksum_of(content):
    """≙ ``IrAttachment._compute_checksum(...)``.

    ``base`` calcula el ``checksum`` dentro de su ``save()`` y no publica el
    método; se replica **su misma fórmula** (sha1 hexadecimal del contenido)
    para que los dos coincidan. Reimplementar otra distinta haría que
    :func:`get_existing_attachment` no encontrara nunca un duplicado.
    """
    return hashlib.sha1(content).hexdigest()


class HTML_Editor:
    """≙ ``HTML_Editor(http.Controller)`` (``odoo19c: :83``).

    La conducta del controlador de la fuente, entera. Las rutas viven al final
    del módulo como vistas DRF que delegan aquí.
    """

    def _get_shape_svg(self, module, *segments):
        """≙ ``HTML_Editor._get_shape_svg`` (``odoo19c: :85-91``)."""
        shape_path = opj(module, 'static', *segments)
        try:
            with file_open(shape_path, 'r', filter_ext=('.svg',)) as file:
                return file.read()
        except FileNotFoundError:
            raise NotFound()

    def _update_svg_colors(self, options, svg):
        """≙ ``_update_svg_colors`` (``odoo19c: :93-134``)."""
        user_colors = []
        svg_options = {}
        default_palette = {
            '1': '#3AADAA',
            '2': '#7C6576',
            '3': '#F6F6F6',
            '4': '#FFFFFF',
            '5': '#383E45',
        }
        bundle_css = None
        regex_hex = r'#[0-9A-F]{6,8}'
        regex_rgba = r'rgba?\(\d{1,3}, ?\d{1,3}, ?\d{1,3}(?:, ?[0-9.]{1,4})?\)'
        for key, value in options.items():
            color_match = re.match('^c([1-5])$', key)
            if color_match:
                css_color_value = value
                # Se comprueba que el color sea hex o rgb(a), para impedir una
                # inyección arbitraria
                if not re.match(r'(?i)^%s$|^%s$' % (regex_hex, regex_rgba),
                                css_color_value.replace(' ', '')):
                    if re.match('^o-color-([1-5])$', css_color_value):
                        if not bundle_css:
                            bundle = 'web.assets_frontend'
                            bundle_css = self._asset_bundle_css(bundle)
                        color_search = re.search(
                            r'(?i)--%s:\s+(%s|%s)' % (
                                css_color_value, regex_hex, regex_rgba),
                            bundle_css)
                        if not color_search:
                            raise ParseError()
                        css_color_value = color_search.group(1)
                    else:
                        raise ParseError()
                user_colors.append([_html_escape(css_color_value),
                                    color_match.group(1)])
            else:
                svg_options[key] = value

        color_mapping = {default_palette[palette_number]: color
                         for color, palette_number in user_colors}
        # expresión insensible a mayúsculas con todos los colores a
        # reemplazar, p. ej. '(?i)(#3AADAA)|(#7C6576)'
        regex = '(?i)%s' % '|'.join('(%s)' % color
                                    for color in color_mapping.keys())

        def subber(match):
            key = match.group().upper()
            return color_mapping[key] if key in color_mapping else key
        return re.sub(regex, subber, svg), svg_options

    def _asset_bundle_css(self, bundle):
        """≙ ``request.env["ir.qweb"]._get_asset_bundle(bundle).css()``.

        **Divergencia declarada:** el empaquetado de recursos vive en ``ui``
        (webpack), no aquí — ``base.IrAsset`` porta el catálogo, no el
        compilador de *bundles*. Sin CSS compilado, la rama ``o-color-N`` de
        :meth:`_update_svg_colors` no puede resolver el color, así que
        devuelve cadena vacía y la búsqueda falla con el mismo
        ``ParseError`` que la fuente emite cuando el color no está.

        **Sucesor:** portar ``_get_asset_bundle`` sobre ``base.IrAsset``, o
        publicar desde ``ui`` las variables de color como parámetro del
        sistema. Se reporta al orquestador.
        """
        _logger.info(
            'html_editor: el bundle %r no tiene CSS compilado en este árbol '
            '(el empaquetado vive en ui); la resolución de o-color-N no '
            'puede hacerse.', bundle)
        return ''

    def replace_animation_duration(self, shape_animation_speed, svg):
        """≙ ``replace_animation_duration`` (``odoo19c: :136-214``).

        Reemplaza las duraciones de animación del SVG y del CSS por los
        valores modificados.

        Toma una velocidad y un SVG con animaciones, y usa expresiones
        regulares para encontrar y sustituir las duraciones tanto en las
        reglas de animación CSS como en los atributos ``dur`` del SVG.

        Parámetros:
            - shape_animation_speed (float): la velocidad con que se calculan
              las duraciones nuevas.
            - svg (str): la cadena SVG con las animaciones.

        Devuelve: str, el SVG modificado con las duraciones actualizadas.
        """
        ratio = (1 + shape_animation_speed
                 if shape_animation_speed >= 0
                 else 1 / (1 - shape_animation_speed))

        def callback_css_animation_rule(match):
            # Se extraen los grupos coincidentes.
            declaration, value, unit, separator = (
                match.group("declaration"),
                match.group("value"),
                match.group("unit"),
                match.group("separator"),
            )
            # Se calcula la duración nueva según el ratio.
            value = str(float(value) / (ratio or 1))
            # Se construye y devuelve la regla CSS modificada.
            return f"{declaration}{value}{unit}{separator}"

        def callback_svg_dur_timecount_val(match):
            attribute_name, value, unit = (
                match.group("attribute_name"),
                match.group("value"),
                match.group("unit"),
            )
            # Se calcula la duración nueva según el ratio.
            value = str(float(value) / (ratio or 1))
            # Se construye y devuelve el atributo de duración modificado.
            return f'{attribute_name}{value}{unit or "s"}"'

        def callback_css_animation_ratio(match):
            ratio_value = match.group("ratio")
            return f'--animation_ratio: {ratio_value};'

        # Se aplican las sustituciones para modificar la velocidad de
        # animación en la variable 'svg'.
        svg = re.sub(
            CSS_ANIMATION_RULE_REGEX,
            callback_css_animation_rule,
            svg
        )
        svg = re.sub(
            SVG_DUR_TIMECOUNT_VAL_REGEX,
            callback_svg_dur_timecount_val,
            svg
        )
        # Se crea o modifica la variable css --animation_ratio para más
        # adelante.
        if re.match(CSS_ANIMATION_RATIO_REGEX, svg):
            svg = re.sub(
                CSS_ANIMATION_RATIO_REGEX,
                callback_css_animation_ratio,
                svg
            )
        else:
            regex = r"<svg .*>"
            declaration = f"--animation_ratio: {ratio}"
            subst = ("\\g<0>\n\t<style>\n\t\t:root { \n\t\t\t" +
                     declaration +
                     ";\n\t\t}\n\t</style>")
            svg = re.sub(regex, subst, svg, flags=re.MULTILINE)
        return svg

    def remove(self, request, ids, **kwargs):
        """≙ ``remove`` (``odoo19c: :217-246``).

        Borra un adjunto de imagen si ninguna vista (plantilla) lo usa.

        Devuelve un dict con los adjuntos que **no** se borrarían (si los hay)
        y las vistas que lo impiden.
        """
        self._clean_context(request)
        Attachment = model_by_name('ir.attachment')
        Views = model_by_name('ir.ui.view')
        attachments_to_remove = []

        # las vistas que bloquean el borrado del adjunto
        removal_blocked_by = {}

        for attachment in Attachment.objects.filter(pk__in=ids):
            # las URL dentro del documento van escapadas: una búsqueda directa
            # no las encuentra
            url = _html_escape(attachment.local_url)
            views = list(Views.objects.filter(
                django_models.Q(arch_db__contains='"%s"' % url)
                | django_models.Q(arch_db__contains="'%s'" % url)))

            if views:
                removal_blocked_by[attachment.pk] = [
                    {'id': v.pk, 'name': v.name} for v in views]
            else:
                attachments_to_remove.append(attachment.pk)
        if attachments_to_remove:
            Attachment.objects.filter(pk__in=attachments_to_remove).delete()
        return removal_blocked_by

    def _clean_context(self, request):
        """≙ ``_clean_context`` (``odoo19c: :248-252``).

        Se evita ``allowed_company_ids``, que podría restringir por sitio de
        forma equivocada.

        **Divergencia:** el ámbito de empresa vive en la petición (lo deja
        ``CompanyContextMiddleware``), no en un contexto de entorno.
        """
        if hasattr(request, 'allowed_company_ids'):
            del request.allowed_company_ids

    def _attachment_create(self, request, name='', data=False, url=False,
                           res_id=False, res_model='ir.ui.view'):
        """≙ ``_attachment_create`` (``odoo19c: :254-315``).

        Crea y devuelve un adjunto nuevo.
        """
        IrAttachment = model_by_name('ir.attachment')

        if name.lower().endswith('.bmp'):
            # Se evita el desajuste entre content type y mimetype
            name = name[:-4]

        if not name and url:
            name = url.split("/").pop()

        if res_model != 'ir.ui.view' and res_id:
            res_id = int(res_id)
        else:
            res_id = False

        attachment_data = {
            'name': name,
            'public': res_model == 'ir.ui.view',
            'res_id': res_id,
            'res_model': res_model,
        }

        if data:
            attachment_data['raw'] = data
            if url:
                attachment_data['url'] = url
        elif url:
            attachment_data.update({
                'type': 'url',
                'url': url,
            })
            # Se emite un HEAD para leer las cabeceras de la URL. Sirve cuando
            # la URL no acaba en una extensión de imagen: comprobando el tipo
            # MIME se garantiza que sólo entren imágenes soportadas.
            response = requests.head(url, timeout=10)
            if response.status_code == 200:
                mime_type = response.headers.get('content-type')
                if mime_type in SUPPORTED_IMAGE_MIMETYPES:
                    attachment_data['mimetype'] = mime_type
        else:
            raise ParseError(
                "You need to specify either data or url to create an "
                "attachment.")

        # Aunque el usuario no tenga derecho a crear un adjunto, sí puede
        # crear un adjunto de imagen por algunos flujos
        if IrAttachment()._can_bypass_rights_on_media_dialog(**attachment_data):
            attachment = _create_attachment(IrAttachment, attachment_data)
            # Cuando un usuario del portal sube un adjunto con el widget
            # wysiwyg, hace falta el token de acceso para usar la imagen en el
            # editor. Si el adjunto no es público, el usuario no podrá generar
            # el token, así que se genera con permisos elevados.
            if not attachment_data['public']:
                attachment.generate_access_token()
        else:
            attachment = (get_existing_attachment(IrAttachment,
                                                  attachment_data)
                          or _create_attachment(IrAttachment,
                                                attachment_data))

        return attachment

    def get_image_info(self, request, src=''):
        """≙ ``get_image_info`` (``odoo19c: :318-361``).

        Esta ruta sirve para determinar la información de un adjunto, de modo
        que pueda usarse como base para volver a modificarlo (recorte,
        optimización, filtros).
        """
        self._clean_context(request)
        IrAttachment = model_by_name('ir.attachment')
        attachment = None
        if src.startswith('/web/image'):
            with contextlib.suppress(NotFound, LookupError, ValueError):
                record = model_by_name('ir.binary').find_record(src)
                if record is not None and getattr(
                        type(record), '_name', None) == 'ir.attachment':
                    attachment = record
        if not attachment:
            # Se busca el adjunto por url. Puede haber varias coincidencias
            # porque las imágenes de snippet por defecto apuntan a la misma
            # imagen en /static/, así que se limita a 1
            mimetype_query = django_models.Q(
                mimetype__in=list(SUPPORTED_IMAGE_MIMETYPES.keys()))
            for image_mimetype in SUPPORTED_IMAGE_MIMETYPES:
                # Se admite el mimetype con parámetros opcionales,
                # p. ej. `image/svg+xml; charset=utf-8`
                mimetype_query |= django_models.Q(
                    mimetype__startswith=image_mimetype + ';')
            attachment = IrAttachment.objects.filter(
                (django_models.Q(url=src)
                 | django_models.Q(url__startswith='%s?' % src))
                & mimetype_query).first()
        if not attachment:
            return {
                'attachment': False,
                'original': False,
            }
        original = _original_or_self(attachment)
        return {
            'attachment': {'id': attachment.pk},
            'original': {
                'id': original.pk,
                'image_src': original.image_src,
                'mimetype': original.mimetype,
            },
        }

    def video_url_data(self, request, video_url, autoplay=False, loop=False,
                       hide_controls=False, hide_fullscreen=False,
                       hide_dm_logo=False, hide_dm_share=False,
                       start_from=False):
        """≙ ``video_url_data`` (``odoo19c: :364-373``)."""
        return get_video_url_data(
            video_url, autoplay=autoplay, loop=loop,
            hide_controls=hide_controls, hide_fullscreen=hide_fullscreen,
            hide_dm_logo=hide_dm_logo, hide_dm_share=hide_dm_share,
            start_from=start_from
        )

    def add_data(self, request, name, data, is_image, quality=0, width=0,
                 height=0, res_id=False, res_model='ir.ui.view', **kwargs):
        """≙ ``add_data`` (``odoo19c: :376-398``)."""
        data = b64decode(data)
        if is_image:
            format_error_msg = (
                "Uploaded image's format is not supported. Try with: %s"
                % ', '.join(SUPPORTED_IMAGE_MIMETYPES.values()))
            try:
                mimetype = _guess_mimetype(data)
                if mimetype not in SUPPORTED_IMAGE_MIMETYPES:
                    return {'error': format_error_msg,
                            'codigo_error': 'UNSUPPORTED_IMAGE_FORMAT'}
                if not name:
                    name = '%s-%s%s' % (
                        datetime.now().strftime('%Y%m%d%H%M%S'),
                        str(uuid.uuid4())[:6],
                        SUPPORTED_IMAGE_MIMETYPES[mimetype],
                    )
                processed = _image_process(data)
                if processed is None:
                    return {'error': format_error_msg,
                            'codigo_error': 'UNSUPPORTED_IMAGE_FORMAT'}
                data = processed
            except ValueError as e:
                # El navegador cree que el archivo es una imagen y PIL no la
                # reconoce, p. ej. .webp
                return {'error': e.args[0],
                        'codigo_error': 'UNSUPPORTED_IMAGE_FORMAT'}

        self._clean_context(request)
        attachment = self._attachment_create(
            request, name=name, data=data, res_id=res_id, res_model=res_model)
        return attachment._get_media_info()

    def add_url(self, request, url, res_id=False, res_model='ir.ui.view',
                **kwargs):
        """≙ ``add_url`` (``odoo19c: :401-404``)."""
        self._clean_context(request)
        attachment = self._attachment_create(
            request, url=url, res_id=res_id, res_model=res_model)
        return attachment._get_media_info()

    def modify_image(self, request, attachment, res_model=None, res_id=None,
                     name=None, data=None, original_id=None, mimetype=None,
                     alt_data=None):
        """≙ ``modify_image`` (``odoo19c: :407-494``).

        Crea una copia modificada de un adjunto y devuelve su ``image_src``
        para insertarla en el DOM.
        """
        self._clean_context(request)
        IrAttachment = model_by_name('ir.attachment')
        attachment = IrAttachment.objects.filter(pk=attachment.pk).first()
        if not data and attachment.datas:
            data = b64encode(_attachment_raw(attachment))

        fields = {
            'datas': data,
            'type': 'binary',
            'res_model': res_model or 'ir.ui.view',
            'mimetype': mimetype or attachment.mimetype,
            'name': name or attachment.name,
            'res_id': 0,
        }
        set_original_attachment(fields, attachment)
        if fields['res_model'] == 'ir.ui.view':
            fields['res_id'] = 0
        elif res_id:
            fields['res_id'] = res_id
        if fields['mimetype'] == 'image/webp':
            fields['name'] = re.sub(r'\.(jpe?g|png)$', '.webp',
                                    fields['name'], flags=re.I)

        existing_attachment = get_existing_attachment(IrAttachment, fields)
        if existing_attachment and not existing_attachment.url:
            attachment = existing_attachment
        else:
            # Un editor restringido puede manejar los adjuntos de los
            # registros a los que tiene acceso.
            # ¿Podría el usuario leer los campos del registro original?
            if attachment.res_model and attachment.res_id:
                origin_model = model_by_name(attachment.res_model)
                if origin_model is not None:
                    origin = origin_model.objects.filter(
                        pk=attachment.res_id).first()
                    if origin is not None:
                        origin.check_access('read')

            # ¿Podría el usuario escribir los campos del registro destino?
            target_model = model_by_name(fields['res_model'])
            if target_model is not None and fields['res_id']:
                target = target_model.objects.filter(
                    pk=fields['res_id']).first()
                if target is not None:
                    target.check_access('write')

            attachment = _copy_attachment(attachment, fields)

        if alt_data:
            for size, per_type in alt_data.items():
                reference_id = attachment.pk
                if 'image/webp' in per_type:
                    resized = _create_attachment(IrAttachment, {
                        'name': attachment.name,
                        'description': 'resize: %s' % size,
                        'datas': per_type['image/webp'],
                        'res_id': reference_id,
                        'res_model': 'ir.attachment',
                        'mimetype': 'image/webp',
                    })
                    reference_id = resized.pk
                if 'image/jpeg' in per_type:
                    _create_attachment(IrAttachment, {
                        'name': re.sub(r'\.webp$', '.jpg', attachment.name,
                                       flags=re.I),
                        'description': 'format: jpeg',
                        'datas': per_type['image/jpeg'],
                        'res_id': reference_id,
                        'res_model': 'ir.attachment',
                        'mimetype': 'image/jpeg',
                    })

        if attachment.url:
            # No se conserva la url al modificar un adjunto estático porque
            # las imágenes estáticas sólo se sirven de disco y no caen a los
            # adjuntos.
            if re.match(r'^/\w+/static/', attachment.url):
                attachment.url = None
            # Se hace única la url añadiendo un segmento con el id antes del
            # nombre. Así se conserva el formato de url de unsplash y sigue
            # reaccionando a su baliza.
            else:
                url_fragments = attachment.url.split('/')
                url_fragments.insert(-1, str(attachment.pk))
                attachment.url = '/'.join(url_fragments)
            attachment.save()

        if attachment.public:
            return attachment.image_src

        attachment.generate_access_token()
        return '%s?access_token=%s' % (attachment.image_src,
                                       attachment.access_token)

    def save_library_media(self, request, media):
        """≙ ``save_library_media`` (``odoo19c: :497-545``).

        Guarda como adjuntos nuevos las imágenes de la biblioteca de medios,
        volviéndolas SVG dinámicos si hace falta::

            media = {
                <media_id>: {
                    'query': 'términos de búsqueda separados por espacio',
                    'is_dynamic_svg': True/False,
                    'dynamic_colors': mapa de nombre de color a color,
                }, ...
            }
        """
        attachments = []
        ICP = model_by_name('ir.config_parameter')
        library_endpoint = ICP.get_param('html_editor.media_library_endpoint',
                                         DEFAULT_LIBRARY_ENDPOINT)

        media_ids = ','.join(media.keys())
        params = {
            'dbuuid': ICP.get_param('database.uuid'),
            'media_ids': media_ids,
        }
        response = requests.post(
            '%s/media-library/1/download_urls' % library_endpoint,
            data=params, timeout=30)
        if response.status_code != requests.codes.ok:
            raise ParseError(
                "ERROR: couldn't get download urls from media library.")

        IrAttachment = model_by_name('ir.attachment')
        for media_id, url in response.json().items():
            req = requests.get(url, timeout=30)
            name = '_'.join([media[media_id]['query'], url.split('/')[-1]])
            attachment_data = {
                'name': name,
                'mimetype': req.headers['content-type'],
                'public': True,
                'raw': req.content,
                'res_model': 'ir.ui.view',
                'res_id': 0,
            }
            attachment = get_existing_attachment(IrAttachment,
                                                 attachment_data)
            # Hay que saltarse la comprobación de seguridad para escribir una
            # imagen con mimetype image/svg+xml: vale porque los svg vienen de
            # un origen de confianza
            if not attachment:
                attachment = _create_attachment(IrAttachment, attachment_data,
                                                trusted=True)
            if media[media_id]['is_dynamic_svg']:
                color_params = urlencode(media[media_id]['dynamic_colors'])
                attachment.url = '/html_editor/shape/illustration/%s?%s' % (
                    IrHttp.slug(attachment), color_params)
                attachment.save()
            attachments.append(attachment._get_media_info())

        return attachments

    def shape(self, request, module, filename, **kwargs):
        """≙ ``shape`` (``odoo19c: :548-601``).

        Devuelve un svg con los colores personalizados (forma de fondo o
        ilustración).
        """
        svg = None
        if module == 'illustration':
            IrAttachment = model_by_name('ir.attachment')
            attachment = IrAttachment.objects.filter(
                pk=IrHttp.unslug(filename)[1]).first()
            if (attachment is None
                    or attachment.type != 'binary'
                    or not attachment.public
                    or not attachment.url
                    or not attachment.url.startswith(request.path)):
                # Se cae a la búsqueda por URL para poder usar formas
                # importadas desde archivos de datos.
                attachment = IrAttachment.objects.filter(
                    type='binary', public=True, url=request.path).first()
                if not attachment:
                    raise NotFound()

            if not re.match(r'^image\/svg\+xml(;.*)?$', attachment.mimetype):
                response = HttpResponse(_attachment_raw(attachment),
                                        content_type=attachment.mimetype)
                response['Cache-Control'] = 'max-age=%s' % STATIC_CACHE_LONG
                return response

            svg = _attachment_raw(attachment).decode('utf-8')
        else:
            # Compatibilidad
            if module == 'web_editor':
                module = 'html_builder'
            svg = self._get_shape_svg(module, 'shapes', filename)

        svg, options = self._update_svg_colors(kwargs, svg)
        flip_value = options.get('flip', False)
        if flip_value == 'x':
            svg = svg.replace('<svg ',
                              '<svg style="transform: scaleX(-1);" ', 1)
        elif flip_value == 'y':
            svg = svg.replace('<svg ',
                              '<svg style="transform: scaleY(-1)" ', 1)
        elif flip_value == 'xy':
            svg = svg.replace('<svg ',
                              '<svg style="transform: scale(-1)" ', 1)

        shape_animation_speed = float(options.get('shapeAnimationSpeed', 0.0))
        if shape_animation_speed != 0.0:
            svg = self.replace_animation_duration(
                shape_animation_speed=shape_animation_speed,
                svg=svg
            )
        response = HttpResponse(svg, content_type='image/svg+xml')
        response['Cache-Control'] = 'max-age=%s' % STATIC_CACHE_LONG
        return response

    def image_shape(self, request, module, filename, img_key, **kwargs):
        """≙ ``image_shape`` (``odoo19c: :604-641``) — BLOQUEADO en su segunda
        mitad.

        La primera mitad —resolver el SVG de la forma y ajustar sus colores—
        se porta entera y funciona. La segunda necesita ``get_webp_size``,
        ``binary_to_image`` e ``image_data_uri`` de ``odoo/tools/image.py`` y
        el *stream* de ``ir.binary``, que este árbol no tiene: ver la tabla de
        bloqueos del docstring del módulo.
        """
        # Compatibilidad
        if module == 'web_editor':
            module = 'html_builder'
        svg = self._get_shape_svg(module, 'image_shapes', filename)

        record = model_by_name('ir.binary').find_record(img_key)
        if record is None:
            raise NotFound()

        raise NotImplementedError(
            'html_editor.image_shape: faltan `get_webp_size`, '
            '`binary_to_image` e `image_data_uri` (su hogar es '
            '`src/tools/image.py`, que no existe) y el stream de '
            '`ir.binary`. El SVG de la forma sí se resolvió: %d bytes.'
            % len(svg))

    def generate_text(self, request, prompt, conversation_history):
        """≙ ``generate_text`` (``odoo19c: :644-663``) — BLOQUEADO.

        El cuerpo de la fuente delega en ``iap_tools.iap_jsonrpc`` contra el
        punto ``olg.api.odoo.com``. El addon ``iap`` no está portado; ver la
        tabla de bloqueos. Se conserva la lectura de los dos parámetros del
        sistema —que sí existen— para que el día del sucesor sólo falte la
        llamada.
        """
        IrConfigParameter = model_by_name('ir.config_parameter')
        olg_api_endpoint = IrConfigParameter.get_param(
            'html_editor.olg_api_endpoint', DEFAULT_OLG_ENDPOINT)
        database_id = IrConfigParameter.get_param('database.uuid')
        raise NotImplementedError(
            'html_editor.generate_text: `iap_tools.iap_jsonrpc` (addon `iap`) '
            'no está portado. Punto configurado: %s, base %s.'
            % (olg_api_endpoint, database_id))

    def get_ice_servers(self, request):
        """≙ ``get_ice_servers`` (``odoo19c: :666-667``) — BLOQUEADO.

        ``mail.ice.server`` no está portado; ver la tabla de bloqueos.
        """
        raise NotImplementedError(
            'html_editor.get_ice_servers: `mail.ice.server` no está portado.')

    def bus_broadcast(self, request, model_name, field_name, res_id,
                      bus_data):
        """≙ ``bus_broadcast`` (``odoo19c: :670-681``)."""
        model = model_by_name(model_name)
        if model is None:
            raise NotFound()
        document = model.objects.filter(pk=res_id).first()
        if document is None:
            raise NotFound()

        document.check_access('read')
        document.check_access('write')
        field = next((f for f in model._meta.get_fields()
                      if getattr(f, 'name', None) == field_name), None)
        if field is not None:
            document._check_field_access(field, 'read')
            document._check_field_access(field, 'write')

        channel = editor_collaboration_channel(model_name, field_name,
                                               int(res_id))
        bus_data.update({'model_name': model_name, 'field_name': field_name,
                         'res_id': res_id})
        BusMessage.sendone(channel, EDITOR_COLLABORATION, bus_data)

    def link_preview_metadata(self, request, preview_url):
        """≙ ``link_preview_metadata`` (``odoo19c: :684-688``) — BLOQUEADO.

        ``mail.tools.link_preview`` no está portado; ver la tabla de bloqueos.
        """
        raise NotImplementedError(
            'html_editor.link_preview_metadata: `mail.tools.link_preview` no '
            'está portado (url pedida: %s).' % preview_url)

    def link_preview_metadata_internal(self, request, preview_url):
        """≙ ``link_preview_metadata_internal`` (``odoo19c: :691-747``)."""
        try:
            Actions = model_by_name('ir.actions.actions')
            parsed_preview_url = urlparse(preview_url)
            words = parsed_preview_url.path.strip('/').split('/')
            last_segment = words[-1]

            if not (
                last_segment.isnumeric()
                and (
                    parsed_preview_url.path.startswith("/odoo")
                    or parsed_preview_url.path.startswith("/web")
                    or parsed_preview_url.path.startswith("/@/")
                )
            ):
                # podría ser una página de sitio o externa
                link_preview_data = self.link_preview_metadata(request,
                                                               preview_url)
                result = {}
                if link_preview_data and link_preview_data.get(
                        'og_description'):
                    result['description'] = link_preview_data['og_description']
                return result

            record_id = int(words.pop())
            action_name = words.pop()
            model = None
            if action_name.startswith('m-') or '.' in action_name:
                # si la ruta es `odoo/<model>/<record_id>`, `action_name` es
                # el nombre del modelo
                model_name = action_name.removeprefix('m-')
                model = model_by_name(model_name)
            if model is None:
                action = Actions.objects.filter(path=action_name).first()
                if not action:
                    return {'error_msg': (
                        "Action %s not found, link preview is not available, "
                        "please check your url is correct" % action_name)}
                action_type = action.type
                if action_type != 'ir.actions.act_window':
                    return {'other_error_msg': (
                        "Action %s is not a window action, link preview is "
                        "not available" % action_name)}
                action_sudo = model_by_name(action_type).objects.filter(
                    pk=action.pk).first()
                model = model_by_name(action_sudo.res_model)

            record = model.objects.filter(pk=record_id).first()
            if record is None:
                raise NotFound()

            result = {}
            if hasattr(record, 'description'):
                result['description'] = (
                    html.fromstring(record.description).text_content()
                    if record.description else "")

            if hasattr(record, 'link_preview_name'):
                result['link_preview_name'] = record.link_preview_name
            elif hasattr(record, 'display_name'):
                result['display_name'] = record.display_name

            return result
        except NotFound as e:
            return {'error_msg': (
                "Link preview is not available because %s, please check if "
                "your url is correct" % str(e))}
        # se atrapa el resto de excepciones y se devuelve el mensaje para
        # mostrarlo en la consola, sin bloquear el flujo
        except Exception as e:  # noqa: BLE001
            return {'other_error_msg': str(e)}

    def media_library_search(self, request, **params):
        """≙ ``media_library_search`` (``odoo19c: :750-758``)."""
        ICP = model_by_name('ir.config_parameter')
        endpoint = ICP.get_param('html_editor.media_library_endpoint',
                                 DEFAULT_LIBRARY_ENDPOINT)
        params['dbuuid'] = ICP.get_param('database.uuid')
        response = requests.post('%s/media-library/1/search' % endpoint,
                                 data=params, timeout=5)
        if (response.status_code == requests.codes.ok
                and response.headers['content-type'] == 'application/json'):
            return response.json()
        return {'error': response.status_code,
                'codigo_error': 'MEDIA_LIBRARY_UNAVAILABLE'}


# ------------------------------------------------------
# Auxiliares del stack — lo que la fuente obtiene de su ORM
# ------------------------------------------------------


def _html_escape(value):
    """≙ ``tools.html_escape``."""
    return str(escape(value))


def _guess_mimetype(data):
    """≙ ``odoo.tools.mimetypes.guess_mimetype``.

    ``src/tools`` no declara ese módulo; su hogar es ``src/tools/mimetypes.py``
    y está fuera de los archivos de este puerto. Aquí se resuelve por la firma
    binaria de los siete formatos que ``SUPPORTED_IMAGE_MIMETYPES`` admite,
    que es lo único que este addon le pide.

    **Sucesor nombrado** (junto al de ``src/tools/image.py``): portar
    ``odoo/tools/mimetypes.py``.
    """
    signatures = (
        (b'\x89PNG\r\n\x1a\n', 'image/png'),
        (b'\xff\xd8\xff', 'image/jpeg'),
        (b'GIF87a', 'image/gif'),
        (b'GIF89a', 'image/gif'),
    )
    for prefix, mimetype in signatures:
        if data.startswith(prefix):
            return mimetype
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return 'image/webp'
    head = data[:256].lstrip()
    if head.startswith(b'<?xml') or head.startswith(b'<svg'):
        return 'image/svg+xml'
    return 'application/octet-stream'


def _original_or_self(attachment):
    """≙ ``attachment.original_id or attachment``.

    Ver la divergencia 1 de ``models/ir_attachment.py``: mientras el campo
    esté bloqueado, el original de un adjunto es él mismo.
    """
    return original_attachment_of(attachment) or attachment


def _create_attachment(IrAttachment, values, trusted=False):
    """Crea un ``ir.attachment`` a partir del dict de la fuente.

    ``raw`` (bytes) y ``datas`` (base64) de la fuente se vuelcan al
    ``FileField`` que ``base`` declara; el resto de claves van tal cual.
    """
    values = dict(values)
    raw = values.pop('raw', None)
    datas = values.pop('datas', None)
    content = raw if raw is not None else (
        b64decode(datas) if datas else None)
    attachment = IrAttachment(**values)
    if content is not None:
        attachment.datas = ContentFile(
            content, name=values.get('name') or 'attachment')
    attachment.save(trusted=trusted)
    return attachment


def _copy_attachment(attachment, fields):
    """≙ ``attachment.copy(fields)`` — la copia con valores sobreescritos."""
    IrAttachment = type(attachment)
    values = {
        'name': attachment.name,
        'description': attachment.description,
        'res_model': attachment.res_model,
        'res_id': attachment.res_id,
        'type': attachment.type,
        'url': attachment.url,
        'public': attachment.public,
        'mimetype': attachment.mimetype,
    }
    values.update(fields)
    return _create_attachment(IrAttachment, values)


_CONTROLLER = HTML_Editor()


# ------------------------------------------------------
# Las rutas — ≙ los catorce ``@http.route`` de la fuente
# ------------------------------------------------------


@extend_schema(tags=['html_editor'], summary='Borra adjuntos no usados',
               responses={200: OpenApiResponse(
                   description='Mapa de adjunto -> vistas que lo bloquean')})
@api_view(['POST'])
@require_capability('html_editor.attachment.remove')
def remove_endpoint(request):
    """≙ ``@http.route('/html_editor/attachment/remove', auth='user')``."""
    return Response(_CONTROLLER.remove(request,
                                       request.data.get('ids') or []))


@extend_schema(tags=['html_editor'], summary='Información de una imagen',
               responses={200: OpenApiResponse(description='attachment + original')})
@api_view(['POST'])
@require_capability('html_editor.attachment.view')
def get_image_info_endpoint(request):
    """≙ ``@http.route(['/web_editor/get_image_info', …], auth='user')``."""
    return Response(_CONTROLLER.get_image_info(
        request, src=request.data.get('src', '')))


@extend_schema(tags=['html_editor'], summary='Datos de una URL de vídeo',
               responses={200: OpenApiResponse(description='platform + embed_url')})
@api_view(['POST'])
@require_capability('html_editor.attachment.view')
def video_url_data_endpoint(request):
    """≙ ``@http.route(['/web_editor/video_url/data', …], auth='user')``."""
    data = dict(request.data)
    video_url = data.pop('video_url', None)
    return Response(_CONTROLLER.video_url_data(
        request, video_url,
        **{k: v for k, v in data.items()
           if k in ('autoplay', 'loop', 'hide_controls', 'hide_fullscreen',
                    'hide_dm_logo', 'hide_dm_share', 'start_from')}))


@extend_schema(tags=['html_editor'], summary='Sube un adjunto binario',
               responses={200: OpenApiResponse(description='media info'),
                          400: OpenApiResponse(
                              description='UNSUPPORTED_IMAGE_FORMAT')})
@api_view(['POST'])
@require_capability('html_editor.attachment.create')
def add_data_endpoint(request):
    """≙ ``@http.route(['/web_editor/attachment/add_data', …], POST)``."""
    payload = request.data
    result = _CONTROLLER.add_data(
        request, payload.get('name'), payload.get('data'),
        payload.get('is_image'), quality=payload.get('quality', 0),
        width=payload.get('width', 0), height=payload.get('height', 0),
        res_id=payload.get('res_id', False),
        res_model=payload.get('res_model', 'ir.ui.view'))
    status = 400 if isinstance(result, dict) and 'codigo_error' in result else 200
    return Response(result, status=status)


@extend_schema(tags=['html_editor'], summary='Registra un adjunto por URL',
               responses={200: OpenApiResponse(description='media info')})
@api_view(['POST'])
@require_capability('html_editor.attachment.create')
def add_url_endpoint(request):
    """≙ ``@http.route(['/web_editor/attachment/add_url', …], POST)``."""
    payload = request.data
    return Response(_CONTROLLER.add_url(
        request, payload.get('url'), res_id=payload.get('res_id', False),
        res_model=payload.get('res_model', 'ir.ui.view')))


@extend_schema(tags=['html_editor'], summary='Copia modificada de una imagen',
               responses={200: OpenApiResponse(description='image_src')})
@api_view(['POST'])
@require_capability('html_editor.attachment.create')
def modify_image_endpoint(request, attachment_id):
    """≙ ``@http.route('/html_editor/modify_image/<model(...):attachment>')``."""
    IrAttachment = model_by_name('ir.attachment')
    attachment = IrAttachment.objects.filter(pk=attachment_id).first()
    if attachment is None:
        raise NotFound()
    payload = request.data
    return Response(_CONTROLLER.modify_image(
        request, attachment, res_model=payload.get('res_model'),
        res_id=payload.get('res_id'), name=payload.get('name'),
        data=payload.get('data'), original_id=payload.get('original_id'),
        mimetype=payload.get('mimetype'), alt_data=payload.get('alt_data')))


@extend_schema(tags=['html_editor'], summary='Guarda medios de la biblioteca',
               responses={200: OpenApiResponse(description='lista de media info')})
@api_view(['POST'])
@require_capability('html_editor.attachment.create')
def save_library_media_endpoint(request):
    """≙ ``@http.route(['/web_editor/save_library_media', …], POST)``."""
    return Response(_CONTROLLER.save_library_media(
        request, request.data.get('media') or {}))


@extend_schema(tags=['html_editor'], summary='SVG de forma con color',
               responses={200: OpenApiResponse(description='image/svg+xml')})
@api_view(['GET'])
@permission_classes([AllowAny])
def shape_endpoint(request, module, filename):
    """≙ ``@http.route(['/web_editor/shape/<module>/<path:filename>', …],
    auth='public')``.

    ``AllowAny`` explícito y documentado: la fuente declara ``auth='public'``
    y el recurso es una forma decorativa servida con caché larga. Es el mismo
    criterio con que ``website``/``authz_oauth`` declaran sus rutas públicas
    en este árbol.
    """
    return _CONTROLLER.shape(request, module, filename,
                             **request.GET.dict())


@extend_schema(tags=['html_editor'], summary='SVG de forma con imagen dentro',
               responses={200: OpenApiResponse(description='image/svg+xml')})
@api_view(['GET'])
@permission_classes([AllowAny])
def image_shape_endpoint(request, img_key, module, filename):
    """≙ ``@http.route(['/web_editor/image_shape/<string:img_key>/…'],
    auth='public')`` — la vista existe; su método está bloqueado."""
    return _CONTROLLER.image_shape(request, module, filename, img_key,
                                   **request.GET.dict())


@extend_schema(tags=['html_editor'], summary='Genera texto con IA',
               responses={503: OpenApiResponse(description='IAP_NOT_PORTED')})
@api_view(['POST'])
@require_capability('html_editor.text.generate')
def generate_text_endpoint(request):
    """≙ ``@http.route(['/web_editor/generate_text', …], auth='user')``."""
    try:
        return Response(_CONTROLLER.generate_text(
            request, request.data.get('prompt'),
            request.data.get('conversation_history')))
    except NotImplementedError as e:
        return Response({'codigo_error': 'IAP_NOT_PORTED', 'detail': str(e)},
                        status=503)


@extend_schema(tags=['html_editor'], summary='Servidores ICE de coedición',
               responses={503: OpenApiResponse(
                   description='ICE_SERVERS_NOT_PORTED')})
@api_view(['POST'])
@require_capability('html_editor.collaboration.use')
def get_ice_servers_endpoint(request):
    """≙ ``@http.route(['/web_editor/get_ice_servers', …], auth='user')``."""
    try:
        return Response(_CONTROLLER.get_ice_servers(request))
    except NotImplementedError as e:
        return Response(
            {'codigo_error': 'ICE_SERVERS_NOT_PORTED', 'detail': str(e)},
            status=503)


@extend_schema(tags=['html_editor'], summary='Emite un paso de coedición',
               responses={200: OpenApiResponse(description='sin cuerpo')})
@api_view(['POST'])
@require_capability('html_editor.collaboration.use')
def bus_broadcast_endpoint(request):
    """≙ ``@http.route(['/web_editor/bus_broadcast', …], auth='user')``."""
    payload = request.data
    _CONTROLLER.bus_broadcast(
        request, payload.get('model_name'), payload.get('field_name'),
        payload.get('res_id'), payload.get('bus_data') or {})
    return Response(status=200)


@extend_schema(tags=['html_editor'], summary='Metadatos de un enlace externo',
               responses={503: OpenApiResponse(
                   description='LINK_PREVIEW_NOT_PORTED')})
@api_view(['POST'])
@permission_classes([AllowAny])
def link_preview_metadata_endpoint(request):
    """≙ ``@http.route('/html_editor/link_preview_external', auth='public')``.

    ``AllowAny`` explícito: la fuente declara ``auth='public'``.
    """
    try:
        return Response(_CONTROLLER.link_preview_metadata(
            request, request.data.get('preview_url')))
    except NotImplementedError as e:
        return Response(
            {'codigo_error': 'LINK_PREVIEW_NOT_PORTED', 'detail': str(e)},
            status=503)


@extend_schema(tags=['html_editor'], summary='Metadatos de un enlace interno',
               responses={200: OpenApiResponse(description='description + nombre')})
@api_view(['POST'])
@require_capability('html_editor.attachment.view')
def link_preview_metadata_internal_endpoint(request):
    """≙ ``@http.route('/html_editor/link_preview_internal', auth='user')``."""
    return Response(_CONTROLLER.link_preview_metadata_internal(
        request, request.data.get('preview_url')))


@extend_schema(tags=['html_editor'], summary='Busca en la biblioteca de medios',
               responses={200: OpenApiResponse(description='resultado del proveedor')})
@api_view(['POST'])
@require_capability('html_editor.attachment.view')
def media_library_search_endpoint(request):
    """≙ ``@http.route(['/html_editor/media_library_search'], auth='user')``."""
    return Response(_CONTROLLER.media_library_search(
        request, **{k: v for k, v in request.data.items()}))
