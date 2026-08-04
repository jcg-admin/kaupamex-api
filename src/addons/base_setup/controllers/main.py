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

Divergencia declarada: nuestro ``SiteSettings`` es un singleton monolítico
que mezcla ejes de varios dominios (impuestos, pago, stock, envío, contacto)
donde la referencia los reparte entre los 117/113 addons que heredan. Esa
redistribución NO se hace aquí — queda registrada como hallazgo.

El singleton no lleva ``company``: es config del sistema (L0), no per-company
(DEC-KX-05). Por eso NO pasa por el canal del dato (``ir.rule`` /
``RuleScopedManager``) — no hay fila que acotar por compañía; y el canal de
elevación (``su``) tampoco se usa: el gate es la capacidad ``settings``,
marcada sensible en el catálogo de ``base``.
"""
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from addons.authz.permissions import HasCapability
from addons.base_setup.controllers.serializers import SiteSettingsSerializer
from addons.base.models import SiteSettings


class SiteSettingsView(APIView):
    """GET/PATCH ``/api/v2/config/settings/`` — UC-CFG-03."""

    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'settings.edit'

    @extend_schema(
        summary='Obtener configuración global del sitio (UC-CFG-03)',
        tags=['config'],
        responses={200: SiteSettingsSerializer},
    )
    def get(self, request):
        return Response(SiteSettingsSerializer(SiteSettings.get_current()).data)

    @extend_schema(
        summary='Actualizar configuración global del sitio (UC-CFG-03)',
        tags=['config'],
        request=SiteSettingsSerializer,
        responses={200: SiteSettingsSerializer},
    )
    def patch(self, request):
        serializer = SiteSettingsSerializer(
            SiteSettings.get_current(), data=request.data, partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
