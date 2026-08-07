"""Streaming de binarios — adaptación de ``odoo19c:
addons/web/controllers/binary.py``, licencia LGPL-3 (``web/__manifest__.py``,
``odoo-tools@622ddc2a``) — copia + adaptación con atribución (DEC-KX-03).

Completa el addon ``web`` contra H-API-369 / DEC-FW-04 (junto con
``home.py``, ``webmanifest.py``, ``session.py``, ``export.py`` y
``models.py``, ya portados). El helper de dominio que este controlador
expone por HTTP —``base.models.ir_binary.IrBinary``— **ya existía** sin
consumidor (ver su docstring: *"lo que los controladores /web/content y
/web/image devuelven"*); este archivo es su primer consumidor.

Medición símbolo-por-símbolo (``re.findall(r'^\\s{4}def (\\w+)', ref)``, mismo
criterio que ``porte-completo-no-parcial.md``, sobre la clase única
``Binary``): **7** métodos. **4 portados** (adaptados), **3 declarados
ausentes** con razón — no hay recorte silencioso.

Correspondencia con la referencia (``odoo-tools@622ddc2a``)
===========================================================

=============================  ===============================================
Referencia                     Aquí
=============================  ===============================================
``content_common`` (``:72``)   ``content_common`` — ``GET /api/v2/web/content/``
``content_image`` (``:185``)   ``content_image`` — ``GET /api/v2/web/image/``
``upload_attachment`` (``:220``) ``upload_attachment`` — ``POST
                                 /api/v2/web/binary/upload_attachment/``
``company_logo`` (``:263``)    ``company_logo`` — ``GET
                                 /api/v2/web/binary/company_logo/``
=============================  ===============================================

Cuatro divergencias declaradas sobre los cuatro endpoints portados
====================================================================

1. **Sin ``xmlid``.** La referencia acepta resolver por ``xmlid`` además de
   por ``model``+``id``. ``IrBinary.find_record`` ya declaró esa ausencia en
   su propio docstring: hay ``ir.model.data`` (H-API-141) pero no el cargador
   que puebla la tabla desde datos declarativos — no hay filas que resolver
   todavía. Se usa ``res_model``+``res_id`` (la vía que sí tiene datos).

2. **``res_model`` usa la convención ``app_label.ModelName`` del proyecto**
   (≙ ``request.env[model]`` de la referencia), la misma que
   ``export.py::_get_model`` — no el ``dominio.punto`` de Odoo. Default
   ``base.IrAttachment`` (≙ default ``model='ir.attachment'`` de la
   referencia) con ``field='datas'`` (≙ ``field='raw'`` — el campo binario de
   ``ir.attachment`` aquí se llama ``datas``, no ``raw``). Para cualquier otro
   modelo, ``field`` es obligatorio: no hay un nombre de campo binario
   universal entre modelos Django (``ir_binary.py`` no impone ninguno).

3. **Gate por capacidad, no por ACL de registro (DEC-11).** La referencia
   resuelve el acceso registro-por-registro vía ``_find_record`` +
   ``_can_return_content`` (grupos de seguridad de Odoo, con ``sudo()`` para
   los casos públicos). Ese mecanismo no se porta —igual que
   ``avatar_mixin.py`` ya declaró: *"aquí los binarios los sirve Django con
   el storage y el gate de capacidad de la vista"*—, así que
   ``content_common``/``content_image`` exigen sesión + la capacidad
   ``web.content.view`` en vez de ``auth='public'``. Sin ACL por registro,
   una lectura anónima de "cualquier modelo, cualquier id" sería la
   superficie de exfiltración que DEC-11 (fail-closed) prohíbe. Esta
   capacidad es deliberadamente amplia (lee cualquier campo binario de
   cualquier modelo con id válido) — quien la reciba debe ser un rol de
   back-office, no el cliente storefront anónimo.

4. **``download``/``unique``/``nocache`` se resuelven después de construir
   el ``FileResponse``, no como kwargs del constructor.** ``IrBinary.
   get_response_from``/``get_image_response_from`` fijan ``as_attachment=
   False`` siempre (ver su docstring — la referencia decide inline/adjunto
   por parámetro de la vista, no por el helper de dominio). Los helpers
   ``_apply_download_disposition``/``_apply_cache_headers`` de este módulo
   corrigen las cabeceras ya construidas, sin tocar
   ``base/models/ir_binary.py`` — archivo de otro addon, fuera de este slice.

``upload_attachment`` — misma superficie, transporte distinto
=================================================================

Reutiliza ``base.IrAttachment`` (ya portado, H-BASE-01 C-2). Diferencias
frente a la referencia:

- **Respuesta JSON pura, sin el ``<script>``/``postMessage`` de iframe.** La
  referencia arma ese HTML porque su cliente sube el archivo dentro de un
  ``<iframe>`` oculto (el truco clásico pre-``fetch``/``FormData`` para subir
  binarios sin recargar la página) y necesita comunicar el resultado al
  padre via ``window.top``. Un cliente REST (``fetch``/``XMLHttpRequest``
  con ``multipart/form-data``) no tiene ese problema — no hay iframe que
  romper, así que no hay callback que armar. ``clean(name)`` existía sólo
  para blindar ese ``<script>`` inline contra inyección; sin script no hay
  vector que blindar (JSON ya escapa el string).
- **``AccessError`` por archivo no se distingue de otros errores.** La
  referencia captura ``AccessError`` aparte porque ``Model.create`` corre con
  el ACL de Odoo por registro. Aquí la autorización ya se resolvió en el
  gate de la vista (``web.attachment.create``, punto 3 arriba) antes de
  llegar al ``for``; un fallo dentro del loop es de datos (adjunto
  corrupto, ``IOError`` del storage), no de permisos — se reporta bajo el
  mismo mensaje genérico que la referencia usa para "Something horrible
  happened".

``company_logo`` — simplificado a compañía explícita o de sesión
====================================================================

La referencia resuelve la compañía por ``dbname`` (multi-DB) + ``kw
['company']`` opcional, con reserva final al logo genérico de Odoo si no hay
``dbname``. Este backend es de una sola base: la resolución colapsa a
``company`` (query param) → compañía de la sesión autenticada
(``request.user.company``) → **404** si ninguna aplica. NO cae a la compañía
de sistema (``ResCompany.get_system()``, ``sale_subscription``): acoplar
``web`` —el shell del cliente, el addon con menos dependencias del árbol— a
un addon L1-a de facturación por un fallback de branding sería la
dependencia inversa que el resto de este addon evita. Mismo vacío que
``CompanyContextMiddleware`` ya declara: *"El resolutor subdominio→compañía
... es una capa futura"* — hasta que exista, sin sesión ni ``company``
explícito el logo es DESCONOCIDO, no una compañía adivinada.

``crop``/``dbname`` de ``content_image``/``company_logo`` respectivamente no
se portan por las mismas razones ya cerradas en ``ir_binary.py`` (crop) y
arriba (dbname).

Tres ausentes, con razón — no hay recorte silencioso
========================================================

**1. ``content_filestore`` (``:53``).** Detecta un servidor mal configurado
con ``--x-sendfile`` (NGINX debía interceptar ``/web/filestore`` y no lo
hizo) y sólo emite un log de diagnóstico + 404. Este stack no tiene modo
``x-sendfile``: los binarios los sirve el storage de Django (local o
``django-storages``) vía ``FileResponse``/``MEDIA_URL``, nunca un ``alias``
de NGINX que Odoo espera interceptar antes de llegar aquí. Divergencia de
mecanismo (desenlace 1, ``porte-completo-no-parcial.md``), no una laguna.

**2. ``content_assets`` (``:93``).** Sirve *bundles* CSS/JS generados por
``ir.qweb``/``ir.asset`` (concatenación + minificación server-side de los
``static/`` de los addons instalados). Misma causa raíz ya medida por
``home.py``/``webmanifest.py`` en este mismo addon: **0** directorios
``static/`` en los 78 addons, **0** motor de *asset bundling* — el frontend
(``kaupamex-ui``) es una SPA compilada por Webpack y servida por Apache
(``config/urls.py:199-242``), con su propio *bundling* ya resuelto en el
build de ``ui/``. No hay ``ir.asset`` que bundlear aquí.

**3. ``get_fonts`` (``:312``).** Sirve las fuentes TTF/OTF/WOFF de
``web/static/fonts/sign`` para el widget de firma manuscrita del addon
``sign`` de Odoo. ``find src/addons -maxdepth 1 -iname '*sign*'`` → sólo
``authz_signup`` (alta de cuenta, nada que ver con firmas electrónicas);
**0** directorios ``static/fonts/`` en el árbol (misma medición que
``content_assets``). Sin addon de firma ni activos de fuente que servir, no
hay qué envolver — divergencia de mecanismo, no omisión.
"""
import logging

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from addons.authz.permissions import require_capability
from addons.base.models import IrAttachment, ResCompany
from addons.base.models.ir_binary import IrBinary, RecordNotFound
from tools.misc import str2bool

_logger = logging.getLogger(__name__)

_TAGS = ['web-binary']

#: ≙ ``platform.provision``/``platform.view`` de ``database.py`` — capacidad
#: propia de este archivo, deliberadamente amplia (divergencia 3 del
#: docstring del módulo).
_CAP_CONTENT_VIEW = 'web.content.view'
_CAP_ATTACHMENT_CREATE = 'web.attachment.create'

#: ≙ default ``model='ir.attachment'``/``field='raw'`` de la referencia
#: (divergencia 2 del docstring del módulo).
_DEFAULT_RES_MODEL = 'base.IrAttachment'
_DEFAULT_RES_FIELD = 'datas'

#: Verbatim ``odoo/http.py:338`` — un año, para ``unique=True``.
_STATIC_CACHE_LONG = 60 * 60 * 24 * 365

#: Tamaño máximo de ``ir.attachment.name`` (``base/models/ir_attachment.py``,
#: ``max_length=256``) — el nombre subido se recorta, no se rechaza: el
#: contenido del archivo es lo que importa, no la longitud de su etiqueta.
_ATTACHMENT_NAME_MAX_LENGTH = 256


# === Resolución de modelo/campo — común a content_common y content_image ===

def _resolve_model_and_field(params):
    """``(res_model, field)`` desde los query params, o ``(None, None)`` si
    falta ``field`` para un modelo que no sea el de adjuntos (divergencia 2).
    """
    res_model = params.get('res_model') or _DEFAULT_RES_MODEL
    field = params.get('field')
    if not field:
        field = _DEFAULT_RES_FIELD if res_model == _DEFAULT_RES_MODEL else None
    return res_model, field


def _resolve_res_id(params):
    """``int`` de ``res_id``, o ``None`` si falta o no es entero."""
    raw = params.get('res_id')
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _find_record_or_404(res_model, res_id):
    """``(record, error_response)`` — uno de los dos es ``None``."""
    try:
        return IrBinary.find_record(res_model, res_id), None
    except RecordNotFound:
        return None, Response(
            {'codigo_error': 'RECORD_NOT_FOUND',
             'detail': f'Sin registro para res_model={res_model}, res_id={res_id}.'},
            status=status.HTTP_404_NOT_FOUND)


# === Cabeceras — download/unique/nocache sobre el FileResponse ya construido
# (divergencia 4 del docstring del módulo) ===================================

def _apply_download_disposition(response, download):
    """Fuerza ``attachment`` en vez de ``inline`` cuando ``download`` es
    verdadero. ``FileResponse.set_headers`` (Django) calcula
    ``Content-Disposition`` en el constructor a partir de ``as_attachment``,
    que ``IrBinary`` fija siempre en ``False`` — se corrige la cabecera ya
    construida, no el helper de dominio."""
    if not download:
        return
    current = response.get('Content-Disposition', '')
    if current.startswith('inline'):
        response['Content-Disposition'] = 'attachment' + current[len('inline'):]
    elif not current:
        filename = getattr(response, 'filename', '') or ''
        if filename:
            response['Content-Disposition'] = f'attachment; filename="{filename}"'


def _apply_cache_headers(response, unique, nocache):
    """≙ ``send_file_kwargs['immutable']``/``['max_age']`` de la referencia,
    como cabecera ``Cache-Control`` cruda: Django no tiene un kwarg
    ``immutable`` nativo en ``FileResponse``. ``nocache`` gana sobre
    ``unique``, igual que allá (se evalúa después en la fuente)."""
    if nocache:
        response['Cache-Control'] = 'no-cache'
        return
    if unique:
        response['Cache-Control'] = f'public, max-age={_STATIC_CACHE_LONG}, immutable'


# === Vistas DRF ==============================================================

@extend_schema(
    tags=_TAGS,
    summary='Servir el contenido binario de un campo de un registro',
    parameters=[
        OpenApiParameter(
            name='res_model', type=str, required=False,
            description="app_label.ModelName; default 'base.IrAttachment' "
                        "(≙ model='ir.attachment' de la referencia)."),
        OpenApiParameter(name='res_id', type=int, required=True),
        OpenApiParameter(
            name='field', type=str, required=False,
            description="Campo binario; default 'datas' sólo cuando "
                        "res_model es el de adjuntos — obligatorio en "
                        "cualquier otro modelo (divergencia 2)."),
        OpenApiParameter(name='filename', type=str, required=False),
        OpenApiParameter(name='filename_field', type=str, required=False),
        OpenApiParameter(name='mimetype', type=str, required=False),
        OpenApiParameter(name='download', type=bool, required=False),
        OpenApiParameter(name='unique', type=bool, required=False),
        OpenApiParameter(name='nocache', type=bool, required=False),
    ],
    responses={
        200: OpenApiResponse(description='El contenido binario (mimetype resuelto)'),
        400: OpenApiResponse(description='RES_ID_REQUIRED | FIELD_REQUIRED'),
        404: OpenApiResponse(description='RECORD_NOT_FOUND | FIELD_EMPTY'),
    },
)
@api_view(['GET'])
@require_capability(_CAP_CONTENT_VIEW)
def content_common(request):
    """≙ ``/web/content`` — ver divergencias 1-4 del docstring del módulo."""
    params = request.query_params
    res_model, field = _resolve_model_and_field(params)
    res_id = _resolve_res_id(params)
    if res_id is None:
        return Response(
            {'codigo_error': 'RES_ID_REQUIRED', 'detail': 'res_id es obligatorio.'},
            status=status.HTTP_400_BAD_REQUEST)
    if field is None:
        return Response(
            {'codigo_error': 'FIELD_REQUIRED',
             'detail': 'field es obligatorio para res_model != base.IrAttachment.'},
            status=status.HTTP_400_BAD_REQUEST)

    record, error = _find_record_or_404(res_model, res_id)
    if error is not None:
        return error

    response = IrBinary.get_response_from(
        record, field_name=field, filename=params.get('filename'),
        filename_field=params.get('filename_field', 'name'),
        mimetype=params.get('mimetype'))
    if response is None:
        return Response(
            {'codigo_error': 'FIELD_EMPTY',
             'detail': f'El campo {field} no tiene contenido.'},
            status=status.HTTP_404_NOT_FOUND)

    _apply_download_disposition(response, str2bool(params.get('download'), default=False))
    _apply_cache_headers(
        response,
        str2bool(params.get('unique'), default=False),
        str2bool(params.get('nocache'), default=False))
    return response


@extend_schema(
    tags=_TAGS,
    summary='Servir el contenido de un campo imagen, redimensionado',
    parameters=[
        OpenApiParameter(
            name='res_model', type=str, required=False,
            description="app_label.ModelName; default 'base.IrAttachment'."),
        OpenApiParameter(name='res_id', type=int, required=True),
        OpenApiParameter(
            name='field', type=str, required=False,
            description="Campo binario; default 'datas' (ver content_common)."),
        OpenApiParameter(name='filename', type=str, required=False),
        OpenApiParameter(name='filename_field', type=str, required=False),
        OpenApiParameter(name='mimetype', type=str, required=False),
        OpenApiParameter(name='width', type=int, required=False),
        OpenApiParameter(name='height', type=int, required=False),
        OpenApiParameter(name='download', type=bool, required=False),
        OpenApiParameter(name='unique', type=bool, required=False),
        OpenApiParameter(name='nocache', type=bool, required=False),
    ],
    responses={
        200: OpenApiResponse(description='image/* (o el marcador de posición)'),
        400: OpenApiResponse(description='RES_ID_REQUIRED | FIELD_REQUIRED'),
        404: OpenApiResponse(description='RECORD_NOT_FOUND'),
    },
)
@api_view(['GET'])
@require_capability(_CAP_CONTENT_VIEW)
def content_image(request):
    """≙ ``/web/image`` — usa ``IrBinary.get_image_response_from`` (respaldo
    a marcador de posición, redimensionado; ``crop``/``quality`` no se
    portan — ver docstring de ``ir_binary.py``)."""
    params = request.query_params
    res_model, field = _resolve_model_and_field(params)
    res_id = _resolve_res_id(params)
    if res_id is None:
        return Response(
            {'codigo_error': 'RES_ID_REQUIRED', 'detail': 'res_id es obligatorio.'},
            status=status.HTTP_400_BAD_REQUEST)
    if field is None:
        return Response(
            {'codigo_error': 'FIELD_REQUIRED',
             'detail': 'field es obligatorio para res_model != base.IrAttachment.'},
            status=status.HTTP_400_BAD_REQUEST)

    record, error = _find_record_or_404(res_model, res_id)
    if error is not None:
        return error

    def _to_int(name):
        try:
            return int(params.get(name, 0) or 0)
        except (TypeError, ValueError):
            return 0

    response = IrBinary.get_image_response_from(
        record, field_name=field, filename=params.get('filename'),
        filename_field=params.get('filename_field', 'name'),
        mimetype=params.get('mimetype'),
        width=_to_int('width'), height=_to_int('height'))

    _apply_download_disposition(response, str2bool(params.get('download'), default=False))
    _apply_cache_headers(
        response,
        str2bool(params.get('unique'), default=False),
        str2bool(params.get('nocache'), default=False))
    return response


@extend_schema(
    tags=_TAGS,
    summary='Subir uno o más archivos como ir.attachment vinculados a un registro',
    request={'multipart/form-data': OpenApiResponse(
        description='res_model, res_id, ufile (uno o más archivos)')},
    responses={
        201: OpenApiResponse(
            description='[{filename, mimetype, id, size} | {error}, ...]'),
        400: OpenApiResponse(
            description='RES_MODEL_REQUIRED | RES_ID_INVALID | UFILE_REQUIRED'),
    },
)
@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
@require_capability(_CAP_ATTACHMENT_CREATE)
def upload_attachment(request):
    """≙ ``/web/binary/upload_attachment`` — respuesta JSON pura, sin el
    ``<script>``/``postMessage`` de iframe de la referencia (ver docstring
    del módulo)."""
    res_model = (request.data.get('res_model') or '').strip()
    if not res_model:
        return Response(
            {'codigo_error': 'RES_MODEL_REQUIRED', 'detail': 'res_model es obligatorio.'},
            status=status.HTTP_400_BAD_REQUEST)
    try:
        res_id = int(request.data.get('res_id'))
    except (TypeError, ValueError):
        return Response(
            {'codigo_error': 'RES_ID_INVALID', 'detail': 'res_id debe ser un entero.'},
            status=status.HTTP_400_BAD_REQUEST)

    files = request.FILES.getlist('ufile')
    if not files:
        return Response(
            {'codigo_error': 'UFILE_REQUIRED', 'detail': 'ufile es obligatorio.'},
            status=status.HTTP_400_BAD_REQUEST)

    results = []
    for ufile in files:
        try:
            attachment = IrAttachment.objects.create(
                name=ufile.name[:_ATTACHMENT_NAME_MAX_LENGTH],
                res_model=res_model,
                res_id=res_id,
                mimetype=ufile.content_type or '',
                datas=ufile,
            )
        except Exception:
            _logger.exception('Fallo al subir el adjunto %s', ufile.name)
            results.append({'error': 'No fue posible subir el adjunto.'})
        else:
            results.append({
                'filename': attachment.name,
                'mimetype': attachment.mimetype,
                'id': attachment.pk,
                'size': attachment.file_size,
            })
    return Response(results, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=_TAGS,
    summary='Logotipo de una empresa (branding público)',
    parameters=[
        OpenApiParameter(
            name='company', type=int, required=False,
            description='id de ResCompany; sin él, la de la sesión '
                        'autenticada (request.user.company).'),
    ],
    responses={
        200: OpenApiResponse(description='image/*'),
        404: OpenApiResponse(description='Sin compañía resoluble (ver docstring)'),
    },
    auth=[],
)
@api_view(['GET'])
@permission_classes([AllowAny])
def company_logo(request):
    """≙ ``/web/binary/company_logo``, ``/logo``, ``/logo.png`` — resolución
    de compañía simplificada (divergencia declarada en el docstring del
    módulo, sección ``company_logo``)."""
    company_id = request.query_params.get('company')
    company = None
    if company_id:
        try:
            company = ResCompany.objects.filter(pk=int(company_id)).first()
        except ValueError:
            company = None
    elif getattr(request.user, 'is_authenticated', False):
        company = getattr(request.user, 'company', None)

    if company is None:
        return Response(status=status.HTTP_404_NOT_FOUND)

    return IrBinary.get_image_response_from(
        company, field_name='logo_web', filename='logo.png',
        default_mimetype='image/png')
