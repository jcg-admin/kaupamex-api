"""Descarga de vCard — adaptación de ``odoo19c:
addons/web/controllers/vcard.py``, licencia LGPL-3 (``web/__manifest__.py``,
``odoo-tools@622ddc2a``) — copia + adaptación con atribución (DEC-KX-03).

Cierra la tarea **#397** (auditoría ``check_mirrored_roots.py``, hueco de
porte de ``controllers/vcard.py``, 13 archivos / 22 ``def`` del addon raíz
``web``). El primitivo del que depende YA está portado —
``ResPartner._get_vcard_file()`` (``addons/web/models/res_partner.py``,
colgado sobre ``base.ResPartner`` vía ``WebConfig._EXTENSIONES``)— este
archivo es su primer consumidor HTTP.

Medición símbolo-por-símbolo (``re.findall(r'^\\s{4}def (\\w+)', ref)``, mismo
criterio que ``porte-completo-no-parcial.md``, sobre la clase única
``Partner``): **1** método (``download_vcard``). **1 portado**, **0
ausentes**.

Correspondencia con la referencia (``odoo-tools@622ddc2a``)
===========================================================

=================================  ==========================================
Referencia                          Aquí
=================================  ==========================================
``Partner.download_vcard``          ``download_vcard()`` — ``GET
(``:17``, ``auth="user"``)          /api/v2/web/vcard/download/``
=================================  ==========================================

Tres divergencias declaradas
================================

1. **Sin ``partner`` por converter de URL.** La referencia acepta un único
   contacto vía ``<model("res.partner"):partner>`` (``/web/partner/vcard``)
   además de ``partner_ids`` por query param. Este árbol no tiene
   convertidores de URL por modelo (mecanismo de ``werkzeug``/Odoo, no de
   Django); ``partner_ids`` con un único id cubre el mismo caso — no hay
   pérdida funcional, sólo una vía de entrada menos.
2. **Sin la ruta ``/web_enterprise/...``.** Rama de Enterprise
   (``odoo19e:``), fuera del alcance de Community (DEC-KX-03).
3. **``vobject`` no se comprueba aquí.** La referencia valida
   ``importlib.util.find_spec('vobject')`` antes de servir porque delega la
   serialización en esa librería. ``_get_vcard_file`` (``res_partner.py``)
   ya declaró que este árbol construye el vCard a mano, sin ``vobject`` —
   la comprobación no tiene qué proteger aquí.
"""
import io
import zipfile

from django.http import HttpResponse
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from addons.authz.permissions import require_capability
from addons.base.models.res_partner import ResPartner
from addons.web.controllers.export import _content_disposition

#: ≙ ``web.content.view`` de ``binary.py`` — deliberadamente amplia (lee PII
#: de contacto de cualquier ``res.partner``), mismo criterio de esta capa.
_VCARD_CAPABILITY = 'web.vcard.download'


@extend_schema(
    tags=['web'],
    summary='Descargar vCard de uno o varios contactos',
    parameters=[
        OpenApiParameter(
            'partner_ids', str, required=True,
            description='IDs separados por coma. Uno solo → .vcf; varios → '
                        '.zip con un .vcf por contacto.'),
    ],
    responses={
        200: OpenApiResponse(description='text/vcard o application/zip'),
        404: OpenApiResponse(description='sin contactos con esos ids'),
    },
)
@api_view(['GET'])
@require_capability(_VCARD_CAPABILITY)
def download_vcard(request):
    """≙ ``Partner.download_vcard`` de la referencia — ``GET
    /api/v2/web/vcard/download/?partner_ids=1,2,3``.

    Un contacto → ``.vcf`` suelto; varios → ``.zip`` con un ``.vcf`` por
    contacto, igual que la referencia.
    """
    raw_ids = request.query_params.get('partner_ids', '')
    partner_ids = [int(pid) for pid in raw_ids.split(',') if pid.isdigit()]
    if not partner_ids:
        return Response(
            {'codigo_error': 'PARTNER_IDS_REQUIRED'},
            status=status.HTTP_400_BAD_REQUEST)

    partners = list(ResPartner.objects.filter(pk__in=partner_ids))
    if not partners:
        return Response(
            {'codigo_error': 'PARTNER_NOT_FOUND'},
            status=status.HTTP_404_NOT_FOUND)

    if len(partners) > 1:
        return _zip_response(partners)
    return _vcf_response(partners[0])


def _vcf_response(partner):
    """Un ``.vcf`` suelto — ≙ la rama de un solo contacto de la referencia."""
    content = partner._get_vcard_file()
    filename = f'{partner.name or partner.email}.vcf'
    response = HttpResponse(content, content_type='text/vcard')
    response['Content-Disposition'] = _content_disposition(filename)
    return response


def _zip_response(partners):
    """Un ``.zip`` con un ``.vcf`` por contacto — ≙ la rama multi-contacto de
    la referencia."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        for partner in partners:
            content = partner._get_vcard_file()
            archive.writestr(f'{partner.name or partner.email}.vcf', content)

    response = HttpResponse(buffer.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = _content_disposition('Contacts.zip')
    return response
