"""Administración de bases por empresa — adaptación de ``odoo19c:
addons/web/controllers/database.py`` (LGPL-3, ``odoo-tools@622ddc2a``).

La referencia gestiona **multi-DB por password maestro**: un servidor Odoo
sirve N bases y un ``master_pwd`` compartido autoriza crear/duplicar/soltar/
respaldar/restaurar cualquiera de ellas, sin importar quién esté autenticado.
Este backend adapta esa superficie al modelo **DB-per-company** de la
plataforma (SOL-091, Palanca B — ``service/db.py``, ya construido): una base
``company_<N>_db`` por tenant L1, y el gate de autorización es la capacidad
``platform.provision`` (DEC-11) — no un secreto compartido.

Correspondencia con la referencia (``odoo-tools@622ddc2a``)
===========================================================

===================================  ========================================
Referencia                           Aquí
===================================  ========================================
``create`` (``:71``, ``http``,       ``POST /api/v2/web/database/create/``
``auth='none'``, master_pwd)         ``platform.provision`` — ``company_id``
-----------------------------------  ----------------------------------------
``duplicate`` (``:94``, master_pwd)  ``POST /api/v2/web/database/duplicate/``
                                      ``platform.provision`` — ``source_
                                      company_id`` + ``target_company_id``
-----------------------------------  ----------------------------------------
``drop`` (``:111``, master_pwd)      ``POST /api/v2/web/database/drop/``
                                      ``platform.provision`` — ``company_id``
-----------------------------------  ----------------------------------------
``list`` (``:178``, jsonrpc,         ``GET /api/v2/web/database/``
``auth='none'``, sin password)       ``platform.view``
===================================  ========================================

Lo que esta adaptación NO porta
================================

``selector`` / ``manager`` / ``_render_template`` (``:59``, ``:65``, ``:30``).
Renderizan la página HTML de gestión de bases vía QWeb
(``database_manager.qweb.html`` + fragments). Este backend es API-only (DRF +
JSON) — no hay motor de plantillas server-side cableado para esta superficie.
El consumidor de los cuatro endpoints de arriba sería un panel nativo en
``ui/`` (no construido aún), no una página renderizada por el servidor.
``_render_template`` sólo existía para alimentar a ``selector``/``manager``:
sin ellas no tiene función.

``backup`` / ``restore`` (``:126``, ``:150``). Volcado/restauración completos
de una base (con filestore) ya tienen mecanismo operativo propio en este
proyecto: ``db: scripts/backup_postgres.sh`` (``pg_dump -Fc`` + verificación
``pg_restore --list`` + SHA-256) y su contraparte de restauración manual.
Exponer un dump/restore completo por HTTP duplicaría ese tooling y añadiría
riesgo (transferencia de binarios grandes, acción irreversible) sin que
ningún consumidor lo requiera hoy — divergencia de mecanismo declarada
(``porte-completo-no-parcial.md``, desenlace 1), no una omisión silenciosa.

``change_password`` (``:169``). Cambia el ``master_pwd`` compartido que
autoriza `toda` la gestión multi-DB. Ese concepto no tiene análogo aquí: el
gate de esta superficie es la capacidad ``platform.provision`` (DEC-11),
que se administra por asignación de rol (``RoleCapability``), no por un
secreto que rotar. No hay nada que "cambiar" — el mecanismo completo se
resuelve de otra forma.

Tres divergencias declaradas sobre los cuatro endpoints portados
==================================================================

1. **Identidad por ``company_id``, nunca por nombre de base crudo.** La
   referencia recibe el nombre de la base como string libre (``name``,
   ``new_name``) validado sólo contra ``DBNAME_PATTERN``. Aquí los cuatro
   endpoints reciben el ``id`` de una fila ``ResCompany`` existente y derivan
   el alias con ``company_db_alias(company.id)`` — un string arbitrario del
   cliente nunca llega a ``CREATE``/``DROP DATABASE``. Guard adicional sobre
   la referencia, mismo criterio que ``migrate_all_company_databases``
   (``service/db.py``) ya aplicó al no abortar el loop ante un fallo parcial.
2. **``list`` gated con ``platform.view`` (la referencia es ``auth='none'``,
   sin password).** En un servidor Odoo el nombre de la base es un dato
   operativo; aquí el nombre de la base **es** la identidad del tenant
   (``company_<N>_db``), dato sensible en un modelo multi-company — exponerlo
   sin autenticar filtraría el tamaño y la existencia de la plataforma.
3. **``create``/``duplicate``/``drop`` gated con ``platform.provision``
   (DEC-11), no con ``master_pwd``.** Es el mismo criterio de
   ``sale_subscription/controllers/views.py::CompanyViewSet`` (alta/baja de
   tenants L0): escritura sensible por capacidad, no por secreto compartido.
   ``platform.provision`` está marcada ``is_sensitive=True`` en el catálogo
   (``sale_subscription/security/authz_catalog.py``), así que
   ``HasCapability`` exige sesión elevada fresca (DEC-12) automáticamente.
"""
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from drf_spectacular.utils import OpenApiResponse, extend_schema

from addons.authz.permissions import require_capability
from addons.base.models import ResCompany
from orm.routers import company_db_alias
from service.db import (
    DatabaseExists,
    DatabaseManagementDisabled,
    drop_database,
    duplicate_database,
    list_company_db_names,
    provision_company_database,
)

_TAGS = ['web-database']
_CAP_VIEW = 'platform.view'
_CAP_PROVISION = 'platform.provision'

# ``company_<N>_db`` -> ``N``, para enriquecer ``database_list`` con el
# ``company_id`` dueño de cada base sin depender del orden de ``list_company_
# db_names`` (que sólo filtra por forma, no conoce la fila).
_COMPANY_ID_FROM_ALIAS_PREFIX = 'company_'
_COMPANY_ID_FROM_ALIAS_SUFFIX = '_db'


def _company_id_from_alias(alias):
    """``'company_5_db'`` -> ``5``; ``None`` si el alias no tiene esa forma."""
    if not (alias.startswith(_COMPANY_ID_FROM_ALIAS_PREFIX)
            and alias.endswith(_COMPANY_ID_FROM_ALIAS_SUFFIX)):
        return None
    middle = alias[len(_COMPANY_ID_FROM_ALIAS_PREFIX):-len(_COMPANY_ID_FROM_ALIAS_SUFFIX)]
    return int(middle) if middle.isdigit() else None


def _get_company_or_404(company_id):
    """``ResCompany`` por id, o ``None`` — el llamador arma el 404."""
    if not isinstance(company_id, int):
        return None
    return ResCompany.objects.filter(pk=company_id).first()


@extend_schema(
    tags=_TAGS,
    summary='Listar las bases company_<N>_db provisionadas',
    responses={200: OpenApiResponse(
        description='[{db_name, company_id, company_code}, ...]')},
)
@api_view(['GET'])
@require_capability(_CAP_VIEW)
def database_list(request):
    """≙ ``/web/database/list`` — sin ``db_filter`` por host: consola L0,
    cross-company por definición (mismo criterio que ``CompanyViewSet``)."""
    names = list_company_db_names()
    ids = [cid for cid in (_company_id_from_alias(n) for n in names) if cid is not None]
    codes_by_id = dict(
        ResCompany.objects.filter(pk__in=ids).values_list('id', 'code'))
    return Response([
        {
            'db_name': name,
            'company_id': _company_id_from_alias(name),
            'company_code': codes_by_id.get(_company_id_from_alias(name)),
        }
        for name in names
    ])


@extend_schema(
    tags=_TAGS,
    summary='Provisionar la base de una empresa (idempotente)',
    request=OpenApiResponse(description='{company_id: int}'),
    responses={
        200: OpenApiResponse(description='{db_name, created: false} — ya existía, sólo se migró'),
        201: OpenApiResponse(description='{db_name, created: true}'),
        400: OpenApiResponse(description='COMPANY_ID_REQUIRED'),
        404: OpenApiResponse(description='COMPANY_NOT_FOUND'),
        503: OpenApiResponse(description='DATABASE_MANAGEMENT_DISABLED'),
    },
)
@api_view(['POST'])
@require_capability(_CAP_PROVISION)
def database_create(request):
    """≙ ``/web/database/create`` — sin ``lang``/``login``/``password`` de
    admin: el "inicializar" de este ORM es ``migrate`` (``provision_company_
    database``), no sembrar un usuario admin dentro de la base nueva."""
    company_id = request.data.get('company_id')
    company = _get_company_or_404(company_id)
    if company is None:
        if company_id is None:
            return Response(
                {'codigo_error': 'COMPANY_ID_REQUIRED',
                 'detail': 'company_id es obligatorio.'},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {'codigo_error': 'COMPANY_NOT_FOUND',
             'detail': 'No existe una company con ese id.'},
            status=status.HTTP_404_NOT_FOUND)

    try:
        db_name, created = provision_company_database(
            company_db_alias(company.id))
    except DatabaseManagementDisabled as exc:
        return Response(
            {'codigo_error': 'DATABASE_MANAGEMENT_DISABLED', 'detail': str(exc)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE)

    return Response(
        {'db_name': db_name, 'created': created},
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


@extend_schema(
    tags=_TAGS,
    summary='Duplicar la base de una empresa a otra empresa (staging/demo)',
    request=OpenApiResponse(
        description='{source_company_id: int, target_company_id: int}'),
    responses={
        200: OpenApiResponse(description='{db_name}'),
        400: OpenApiResponse(description='COMPANY_ID_REQUIRED'),
        404: OpenApiResponse(
            description='SOURCE_COMPANY_NOT_FOUND | TARGET_COMPANY_NOT_FOUND | SOURCE_DATABASE_NOT_FOUND'),
        409: OpenApiResponse(description='TARGET_DATABASE_ALREADY_EXISTS'),
        503: OpenApiResponse(description='DATABASE_MANAGEMENT_DISABLED'),
    },
)
@api_view(['POST'])
@require_capability(_CAP_PROVISION)
def database_duplicate(request):
    """≙ ``/web/database/duplicate`` — ``new_name`` de la referencia es aquí
    ``target_company_id``: el destino es siempre la base de una empresa
    existente (fila ``ResCompany`` ya creada, aún sin base propia), nunca un
    nombre de base libre — cierra la superficie de ataque de un string sin
    dueño llegando a ``CREATE DATABASE ... TEMPLATE``."""
    source_id = request.data.get('source_company_id')
    target_id = request.data.get('target_company_id')
    if not isinstance(source_id, int) or not isinstance(target_id, int):
        return Response(
            {'codigo_error': 'COMPANY_ID_REQUIRED',
             'detail': 'source_company_id y target_company_id son obligatorios.'},
            status=status.HTTP_400_BAD_REQUEST)

    source_company = _get_company_or_404(source_id)
    if source_company is None:
        return Response(
            {'codigo_error': 'SOURCE_COMPANY_NOT_FOUND',
             'detail': 'No existe una company origen con ese id.'},
            status=status.HTTP_404_NOT_FOUND)
    target_company = _get_company_or_404(target_id)
    if target_company is None:
        return Response(
            {'codigo_error': 'TARGET_COMPANY_NOT_FOUND',
             'detail': 'No existe una company destino con ese id.'},
            status=status.HTTP_404_NOT_FOUND)

    try:
        db_name = duplicate_database(
            company_db_alias(source_company.id),
            company_db_alias(target_company.id))
    except DatabaseManagementDisabled as exc:
        return Response(
            {'codigo_error': 'DATABASE_MANAGEMENT_DISABLED', 'detail': str(exc)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except DatabaseExists as exc:
        return Response(
            {'codigo_error': 'TARGET_DATABASE_ALREADY_EXISTS', 'detail': str(exc)},
            status=status.HTTP_409_CONFLICT)
    except ValueError as exc:
        return Response(
            {'codigo_error': 'SOURCE_DATABASE_NOT_FOUND', 'detail': str(exc)},
            status=status.HTTP_404_NOT_FOUND)

    return Response({'db_name': db_name})


@extend_schema(
    tags=_TAGS,
    summary='Soltar la base de una empresa',
    request=OpenApiResponse(description='{company_id: int}'),
    responses={
        204: OpenApiResponse(description='Base soltada (o ya no existía)'),
        400: OpenApiResponse(description='COMPANY_ID_REQUIRED'),
        404: OpenApiResponse(description='COMPANY_NOT_FOUND'),
        503: OpenApiResponse(description='DATABASE_MANAGEMENT_DISABLED'),
    },
)
@api_view(['POST'])
@require_capability(_CAP_PROVISION)
def database_drop(request):
    """≙ ``/web/database/drop`` — idempotente como ``drop_database``: soltar
    una base que ya no existe es 204, no 404 (mismo criterio que ``session_
    logout``: deshacer lo que ya está deshecho no es un error)."""
    company_id = request.data.get('company_id')
    company = _get_company_or_404(company_id)
    if company is None:
        if company_id is None:
            return Response(
                {'codigo_error': 'COMPANY_ID_REQUIRED',
                 'detail': 'company_id es obligatorio.'},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {'codigo_error': 'COMPANY_NOT_FOUND',
             'detail': 'No existe una company con ese id.'},
            status=status.HTTP_404_NOT_FOUND)

    try:
        drop_database(company_db_alias(company.id))
    except DatabaseManagementDisabled as exc:
        return Response(
            {'codigo_error': 'DATABASE_MANAGEMENT_DISABLED', 'detail': str(exc)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE)

    return Response(status=status.HTTP_204_NO_CONTENT)
