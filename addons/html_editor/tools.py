"""Utilidades del editor — vídeo incrustado e historia divergente.

Adaptación de ``odoo19c: addons/html_editor/tools.py``
(247 líneas, LGPL-3 — copia + adaptación con atribución, DEC-KX-03).

**9 símbolos en la fuente, 9 portados, 0 ausentes.** Cuatro constantes de
módulo y cinco funciones.

Las dos mitades del archivo
===========================

1. **Vídeo incrustado.** Cinco plataformas —YouTube, Vimeo, Dailymotion,
   Instagram, Facebook— con su expresión regular y las reglas de sus
   parámetros de reproducción. Pegar una URL de vídeo en el editor produce un
   ``<iframe>``, y esto es lo que sabe convertir una en el otro.
2. **``handle_history_divergence``.** La guarda de coedición: si dos personas
   editaron el mismo campo desde historias distintas, la segunda escritura se
   rechaza en vez de pisar en silencio lo de la primera.

Qué pieza de este stack cubre cada delegación de la fuente
==========================================================

===============================  =====================================
Fuente delega en                 Aquí lo cubre
===============================  =====================================
``re`` (las cinco expresiones)   **cpython** — verbatim
``werkzeug.urls.url_encode``     **cpython** — ``urllib.parse.urlencode``.
                                 El inventario excluye Werkzeug
                                 (servimos con **gunicorn**); ``urlencode``
                                 produce el mismo par ``k=v&k=v``
``urllib.parse``                 **cpython** — el mismo
``requests``                     **requests** — el mismo
``markupsafe.Markup``            **markupsafe** — el mismo (es la
                                 dependencia de Jinja2, no de Werkzeug:
                                 no entra en la exclusión del stack)
``odoo.tools.image``             **Pillow** — ver la divergencia 2
(``image_process``)
``request.env['bus.bus']``       **bus** — ``BusMessage.sendone``, con el
``._sendone``                    canal serializado por
                                 ``models.ir_websocket``
``ValidationError`` de Odoo      **django** — el de
                                 ``django.core.exceptions``
===============================  =====================================

Divergencia 1 — el canal del bus es una cadena
==============================================

Igual que en ``models/ir_websocket.py``, y por el mismo motivo: ``bus`` porta
``sendone(target: str, …)``. La tupla de la fuente se compone con
:func:`~addons.html_editor.models.ir_websocket.editor_collaboration_channel`,
que es el **único** sitio donde se arma — este archivo la importa en vez de
repetir el formato.

Divergencia 2 — ``image_process`` no tiene hogar en este árbol
===============================================================

Su sitio es ``odoo/tools/image.py`` = ``src/tools/image.py``, que no existe;
``src/tools`` está fuera de los archivos de este puerto. Aquí se porta lo que
``get_video_thumbnail`` necesita de él —validar que el contenido descargado
**es** una imagen y devolverlo normalizado— como :func:`_image_process`
privado.

**Sucesor nombrado** (compartido con ``models/ir_attachment.py``): crear
``src/tools/image.py`` con ``image_process``, ``base64_to_image``,
``image_data_uri``, ``binary_to_image`` y ``get_webp_size``, que son los cinco
símbolos de ese módulo que este addon consume, y que este archivo y
``controllers/main.py`` los importen de ahí. Se reporta al orquestador.

Divergencia 3 — ``record.env.context.get('install_module')``
=============================================================

Este ORM no tiene contexto de entorno. La guarda de la fuente —*no manejes la
divergencia durante la instalación de un módulo*— se conserva como el
argumento ``install_module=False`` de :func:`handle_history_divergence`, que
es el mismo dato hecho explícito. El cargador de datos que instale un addon lo
pasa en ``True``; nadie más lo toca.
"""
import contextlib
import io
import logging
import re
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from addons.bus.models.bus import BusMessage
from django.core.exceptions import ValidationError
from markupsafe import Markup
from PIL import Image, UnidentifiedImageError

from addons.html_editor.models.ir_websocket import (
    EDITOR_COLLABORATION,
    editor_collaboration_channel,
)

logger = logging.getLogger(__name__)

# Para detectar si es una URL válida o no
valid_url_regex = r'^(http://|https://|//)[a-z0-9]+([\-\.]{1}[a-z0-9]+)*\.[a-z]{2,5}(:[0-9]{1,5})?(/.*)?$'

# Expresiones para unos cuantos servicios de vídeo de uso extendido
player_regexes = {
    'youtube': r'^(?:(?:https?:)?//)?(?:www\.|m\.)?(?:youtu\.be/|youtube(-nocookie)?\.com/(?:embed/|v/|shorts/|live/|watch\?v=|watch\?.+&v=))((?:\w|-){11})\S*$',
    'vimeo': r'//(player.)?vimeo.com/([a-z]*/)?(?P<id>[^/\?]+)(?:/(?P<hash>[^/\?]+))?(?:\?(?P<params>[^\s]+))?$',
    'dailymotion': r'(https?:\/\/)(www\.)?(dailymotion\.com\/(embed\/video\/|embed\/|video\/|hub\/.*#video=)|geo\.dailymotion\.com\/player\.html\?video=|dai\.ly\/)(?P<id>[A-Za-z0-9]{6,7})',
    'instagram': r'(?:(.*)instagram.com|instagr\.am)/p/(.[a-zA-Z0-9-_\.]*)',
    "facebook": r'^(?:(?:https?:)?//)?(?:www\.)?facebook\.com(?:/(?:[^/]+/)?videos/|/watch/?\?v=|/reel/|/plugins/video\.php\?[^ ]*?href=.*?(?:videos|reel)%2[Ff])(?P<id>\d+)',
}


def _model_name(record):
    """El ``_name`` del modelo del registro — ≙ ``record._name``.

    Con respaldo al *label* de Django para un modelo que no lo declare. Se
    escribe como función y no como ``getattr(..., default)`` porque el
    ``default`` de ``getattr`` se **evalúa siempre**: con un registro cuyo
    tipo no tenga ``_meta`` —un doble de prueba— la forma corta levanta
    ``AttributeError`` aunque el ``_name`` esté ahí. Medido al escribir su
    caso.
    """
    name = getattr(type(record), '_name', None)
    if name is not None:
        return name
    return type(record)._meta.label


def _image_process(content):
    """Valida y normaliza el contenido descargado — ≙ ``image_process``.

    Ver la divergencia 2. La fuente llama a ``image_process(content)`` sin más
    argumentos, cuyo efecto con la firma por defecto es exactamente éste:
    comprobar que el contenido es una imagen que Pillow reconoce y devolverla
    re-serializada en su propio formato. Devuelve ``None`` si no lo es, que es
    lo que ``get_video_thumbnail`` necesita para caer a su rama vacía.
    """
    try:
        image = Image.open(io.BytesIO(content))
        image.load()
    except (UnidentifiedImageError, OSError, ValueError):
        logger.warning("El contenido descargado no es una imagen válida.")
        return None
    out = io.BytesIO()
    image.save(out, image.format)
    return out.getvalue()


def get_video_source_data(video_url):
    """≙ ``get_video_source_data`` (``odoo19c: :34-58``).

    Calcula la fuente válida, el id del documento y la coincidencia de la
    expresión regular a partir de la URL dada (o ``None`` si la URL no vale).
    """
    if not video_url:
        return None

    if re.search(valid_url_regex, video_url):
        youtube_match = re.search(player_regexes['youtube'], video_url)
        if youtube_match:
            return ('youtube', youtube_match[2], youtube_match)
        vimeo_match = re.search(player_regexes['vimeo'], video_url)
        if vimeo_match:
            return ('vimeo', vimeo_match.group('id'), vimeo_match)
        dailymotion_match = re.search(player_regexes['dailymotion'], video_url)
        if dailymotion_match:
            return ('dailymotion', dailymotion_match.group("id"),
                    dailymotion_match)
        instagram_match = re.search(player_regexes['instagram'], video_url)
        if instagram_match:
            return ('instagram', instagram_match[2], instagram_match)
        facebook_match = re.search(player_regexes["facebook"], video_url)
        if facebook_match:
            return ("facebook", facebook_match.group("id"), facebook_match)
    return None


def get_video_url_data(video_url, autoplay=False, loop=False,
                       hide_controls=False, hide_fullscreen=False,
                       hide_dm_logo=False, hide_dm_share=False,
                       start_from=False):
    """≙ ``get_video_url_data`` (``odoo19c: :61-130``).

    Calcula el nombre de la plataforma, la ``embed_url``, el id del vídeo y
    sus parámetros a partir de la URL dada (o un mensaje de error si la URL no
    vale).
    """
    source = get_video_source_data(video_url)
    if source is None:
        return {'error': True, 'message': 'The provided url is invalid'}

    embed_url = video_url
    platform, video_id, platform_match = source

    params = {}
    if start_from == "00:00":
        start_from = "0"
    if platform == 'youtube':
        params['rel'] = 0
        params['autoplay'] = autoplay and 1 or 0
        if start_from:
            params["start"] = start_from.rstrip("s")
        if autoplay:
            params['mute'] = 1
            # La api js de youtube hace falta para el autoplay en móvil. Nota:
            # esto se añadió como arreglo; puede haber clientes antiguos con
            # vídeos en autoplay sin esto, que se reproducirán solos en
            # escritorio pero no en móvil (así que no hubo cambio de conducta
            # en estable; esto no debería migrarse).
            params['enablejsapi'] = 1
        if hide_controls:
            params['controls'] = 0
        if loop:
            params['loop'] = 1
            params['playlist'] = video_id
        if hide_fullscreen:
            params['fs'] = 0
        yt_extra = platform_match[1] or ''
        embed_url = (f"//www.youtube{yt_extra}.com/embed/{video_id}"
                     f"?{urlencode(params)}")
    elif platform == 'vimeo':
        params['autoplay'] = autoplay and 1 or 0
        # El parámetro "do not track" va siempre activo.
        params['dnt'] = 1
        if autoplay:
            params['muted'] = 1
            params['autopause'] = 0
        if hide_controls:
            params['controls'] = 0
        if loop:
            params['loop'] = 1
        groups = platform_match.groupdict()
        if groups.get('hash'):
            params['h'] = groups['hash']
        elif groups.get('params'):
            url_params = parse_qs(groups['params'])
            if 'h' in url_params:
                params['h'] = url_params['h'][0]
        embed_url = f"//player.vimeo.com/video/{video_id}?{urlencode(params)}"
        if start_from:
            embed_url = f"{embed_url}#t={start_from}"
    elif platform == 'dailymotion':
        if start_from:
            params["startTime"] = start_from.rstrip("s")
        embed_url = (f"//geo.dailymotion.com/player.html?video={video_id}"
                     f"&{urlencode(params)}")
    elif platform == 'instagram':
        embed_url = f'//www.instagram.com/p/{video_id}/embed/'
    elif platform == "facebook":
        embed_url = ("//facebook.com/plugins/video.php?href="
                     f"https://www.facebook.com/username/videos/{video_id}/")

    return {
        'platform': platform,
        'embed_url': embed_url,
        'video_id': video_id,
        'params': params
    }


def get_video_embed_code(video_url):
    """≙ ``get_video_embed_code`` (``odoo19c: :133-155``).

    Calcula el iframe válido e incrustable a partir de la URL dada (o ``None``
    si la URL no vale).
    """
    parsed_url = urlparse(video_url)
    query_params = parse_qs(parsed_url.query)
    param_name_mapping = {
        'autoplay': 'autoplay',
        'loop': 'loop',
        'hide_controls': 'controls',
        'hide_fullscreen': 'fs',
        'hide_dm_logo': 'ui-logo',
        'hide_dm_share': 'sharing-enable',
    }
    params = {
        func_param: (int(query_params[url_param][0])
                     if func_param == 'autoplay' else 1)
        for func_param, url_param in param_name_mapping.items()
        if url_param in query_params
    }
    data = get_video_url_data(video_url, **params)
    if 'error' in data:
        return None
    return Markup(
        '<iframe class="embed-responsive-item" src="%s" allow="accelerometer; '
        'autoplay; encrypted-media; gyroscope; picture-in-picture" '
        'allowFullScreen="true" frameborder="0"></iframe>') % data['embed_url']


def get_video_thumbnail(video_url):
    """≙ ``get_video_thumbnail`` (``odoo19c: :158-183``).

    Calcula la miniatura válida a partir de la URL dada (o ``None`` si la URL
    no vale).
    """
    source = get_video_source_data(video_url)
    if source is None:
        return None

    response = None
    platform, video_id = source[:2]
    with contextlib.suppress(requests.exceptions.RequestException):
        if platform == 'youtube':
            response = requests.get(
                f'https://img.youtube.com/vi/{video_id}/0.jpg', timeout=10)
        elif platform == 'vimeo':
            res = requests.get(
                f'http://vimeo.com/api/oembed.json?url={video_url}',
                timeout=10)
            if res.ok:
                data = res.json()
                response = requests.get(data['thumbnail_url'], timeout=10)
        elif platform == 'dailymotion':
            response = requests.get(
                f'https://www.dailymotion.com/thumbnail/video/{video_id}',
                timeout=10)
        elif platform == 'instagram':
            response = requests.get(
                f'https://www.instagram.com/p/{video_id}/media/?size=t',
                timeout=10)

    if response and response.ok:
        return _image_process(response.content)
    return None


diverging_history_regex = 'data-last-history-steps="([0-9,]+)"'


# Este método debe llamarse en un contexto con permiso de escritura sobre el
# registro, porque escribe en el bus.
def handle_history_divergence(record, html_field_name, vals,
                              install_module=False):
    """≙ ``handle_history_divergence`` (``odoo19c: :188-247``).

    :param install_module: ≙ ``record.env.context.get('install_module')``.
        Ver la divergencia 3 del docstring del módulo.
    """
    # No se maneja la divergencia si el campo no viene en los valores.
    if html_field_name not in vals:
        return
    # No se maneja la divergencia en modo de instalación de módulo.
    if install_module:
        return
    incoming_html = vals[html_field_name]
    incoming_history_matches = re.search(diverging_history_regex,
                                         incoming_html or '')
    # Cuando no hay id de historia entrante significa que el valor no viene
    # del editor de odoo, o que la coedición no estaba activa. En project
    # podría venir del pad de colaboración. En ese caso no se manejan las
    # divergencias de historia.
    model_name = _model_name(record)
    channel = editor_collaboration_channel(model_name, html_field_name,
                                           record.pk)
    if incoming_history_matches is None:
        bus_data = {
            'model_name': model_name,
            'field_name': html_field_name,
            'res_id': record.pk,
            'notificationName': 'html_field_write',
            'notificationPayload': {'last_step_id': None},
        }
        BusMessage.sendone(channel, EDITOR_COLLABORATION, bus_data)
        return
    incoming_history_ids = incoming_history_matches[1].split(',')
    last_step_id = incoming_history_ids[-1]

    bus_data = {
        'model_name': model_name,
        'field_name': html_field_name,
        'res_id': record.pk,
        'notificationName': 'html_field_write',
        'notificationPayload': {'last_step_id': last_step_id},
    }
    BusMessage.sendone(channel, EDITOR_COLLABORATION, bus_data)

    if getattr(record, html_field_name):
        server_history_matches = re.search(
            diverging_history_regex, getattr(record, html_field_name) or '')
        # No se comprueban los documentos viejos sin data-last-history-steps.
        if server_history_matches:
            server_last_history_id = server_history_matches[1].split(',')[-1]
            if server_last_history_id not in incoming_history_ids:
                logger.warning(
                    'The document was already saved from someone with a '
                    'different history for model %r, field %r with id %r.',
                    model_name, html_field_name, record.pk)
                raise ValidationError(
                    'The document was already saved from someone with a '
                    'different history for model "%(model)s", field '
                    '"%(field)s" with id "%(id)d".' % {
                        'model': model_name,
                        'field': html_field_name,
                        'id': record.pk,
                    })

    # Se guarda sólo el último id.
    vals[html_field_name] = (
        incoming_html[0:incoming_history_matches.start(1)]
        + last_step_id
        + incoming_html[incoming_history_matches.end(1):])
