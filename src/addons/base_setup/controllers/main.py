"""Superficie de ajustes generales — ``base_setup``.

``/api/v2/config/settings/`` (GET + PATCH, capacidad ``settings``). Porte de
la capa HTTP del ex-addon ``settings_app`` (retirado en ``api@115d219`` por
no declarar modelos propios).

**Por qué ``base_setup`` y no ``base``** (medido en las dos poblaciones,
``odoo-tools@622ddc2a``): la referencia separa dos cosas que es fácil
confundir —

- ``base`` **declara** el modelo abstracto: ``_name = 'res.config.settings'``
  en ``odoo19c:`` y ``odoo18c: odoo/addons/base/models/res_config.py``
  (mismo símbolo en ambas).
- ``base_setup`` (LGPL-3 en ambas) **sirve** la superficie de ajustes:
  ``controllers/main.py`` + ``models/res_config_settings.py`` +
  ``views/res_config_settings_views.xml``. 19c añade ``controllers/kpi.py``;
  el resto del layout es idéntico.

*Métrica:* addons que extienden los ajustes con sus campos vía
``_inherit = 'res.config.settings'`` → **117** en ``odoo19c:``, **113** en
``odoo18c:``. *Ciega a:* extensiones declaradas con otra forma sintáctica
(``_inherit`` en lista) — el grep exigió la cadena exacta.

El almacén ya no es una tabla: la ex-``SiteSettings`` mezclaba diez dominios
en un esquema (10 razones para cambiar). Hoy cada ajuste es una clave con el
prefijo de su dominio dueño, y el formulario los compone — la forma de la
referencia. Ver :ref:`h-api-265`.

Ninguna de las claves lleva ``company`` todavía: el destino per-company está
bloqueado por el resolutor ausente (UC-PLT-06, ver el modelo). Por eso NO
pasa por el canal del dato (``ir.rule`` / ``RuleScopedManager``) — no hay
fila que acotar por compañía; y el canal de elevación (``su``) tampoco se
usa: el gate es la capacidad ``settings``, sensible en el catálogo de
``base``.
"""
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from addons.authz.permissions import HasCapability
from addons.base_setup.controllers.serializers import SiteSettingsSerializer


class SiteSettingsView(APIView):
    """GET/PATCH ``/api/v2/config/settings/`` — UC-CFG-03.

    El formulario no tiene fila: ``read_current()`` compone el estado desde
    los tres destinos y ``apply()`` lo devuelve a ellos.
    """

    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'settings.edit'

    @extend_schema(
        summary='Obtener configuración global del sitio (UC-CFG-03)',
        tags=['config'],
        responses={200: SiteSettingsSerializer},
    )
    def get(self, request):
        return Response(SiteSettingsSerializer.read_current())

    @extend_schema(
        summary='Actualizar configuración global del sitio (UC-CFG-03)',
        tags=['config'],
        request=SiteSettingsSerializer,
        responses={200: SiteSettingsSerializer},
    )
    def patch(self, request):
        serializer = SiteSettingsSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(SiteSettingsSerializer.apply(dict(serializer.validated_data)))
