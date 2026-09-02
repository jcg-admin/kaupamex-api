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
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from addons.authz.permissions import HasCapability
from addons.base.models.ir_module import IrModule
from addons.base.models.res_users import ResUsers, ResUsersLog
from addons.base_setup.controllers.serializers import (
    BaseSetupDataSerializer,
    SiteSettingsSerializer,
)
from orm.environments import sudo

#: ≙ ``LIMIT 10`` de la consulta de ``base_setup_data`` (``odoo19c:
#: controllers/main.py:40``) — cuántos usuarios pending se listan.
PENDING_USERS_LIMIT = 10


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


class BaseSetupDataView(APIView):
    """≙ ``BaseSetup.base_setup_data`` (``odoo19c: controllers/main.py:10-51``).

    El panel de arranque: cuántos usuarios internos active_users hay, cuántos de
    ellos **nunca han entrado**, y quiénes son los diez últimos.

    Divergencias declaradas
    =======================

    - **La ruta y el transporte.** La fuente declara
      ``@http.route('/base_setup/data', type='jsonrpc', auth='user')``; aquí
      la superficie es REST y vive bajo el prefijo del addon
      (``/api/v2/config/``), como el resto de este controlador.
    - **El gate.** La fuente comprueba
      ``has_group('base.group_erp_manager')`` y levanta ``AccessError``. Aquí
      la autorización es por CAPACIDAD (DEC-11) y el análogo declarado del
      grupo de administración de ajustes es ``settings.edit`` — la misma que
      ya gatea :class:`SiteSettingsView`. Es fail-closed: sin capacidad, 403.
    - **Las tres consultas van por el ORM, no por ``cr.execute``.** La fuente
      baja a SQL crudo porque su ORM no sabe expresar el ``NOT EXISTS``; el de
      Django sí (``~Exists(...)``), así que el rodeo no tiene motivo. La
      población es la misma.
    - **``share=false`` se filtra en Python.** ``ResUsers.share`` aquí es una
      **propiedad** —la negación de ``_is_internal()``
      (``src/addons/base/models/res_users.py:1842``)—, no una columna, así que
      no puede viajar al ``WHERE``. Misma población, distinto sitio de
      evaluación.
    - **``action_pending_users`` NO se emite** —
      BLOQUEADO por ``res.users._action_show`` — razón: el método no existe en
      este árbol (medido: ``grep -rn "def _action_show" src/`` → 0), y su hogar
      es ``base``, no este addon: portarlo aquí sería el defecto de sitio que
      :ref:`h-api-568` registra. Sucesor: tarea **#456**, que porta
      ``_action_show`` sobre ``res.users`` junto con el resto de acciones de
      ese archivo.
    """

    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'settings.edit'

    @extend_schema(
        summary='Panel de arranque: usuarios active_users y pending',
        tags=['config'],
        responses={200: BaseSetupDataSerializer},
    )
    def get(self, request):
        with sudo():
            active_users = [user for user in ResUsers.objects.filter(active=True)
                       if not user.share]
            with_access = set(
                ResUsersLog.objects.values_list('user_id', flat=True))
        pending = [user for user in active_users if user.pk not in with_access]
        pending.sort(key=lambda user: user.pk, reverse=True)
        return Response(BaseSetupDataSerializer({
            'active_users': len(active_users),
            'pending_count': len(pending),
            'pending_users': [[user.pk, user.login]
                              for user in pending[:PENDING_USERS_LIMIT]],
        }).data)


class BaseSetupDemoActiveView(APIView):
    """≙ ``BaseSetup.base_setup_is_demo`` (``odoo19c: controllers/main.py:53-59``).

    Comentario de la fuente, verbatim: *"We assume that if there's at least one
    module with demo data active, then the db was initialized with demo=True or
    it has been force-activated by the `Load demo data` button in the settings
    dashboard."*

    Divergencia: la fuente la declara ``auth='user'`` a secas. DEC-11 no admite
    una vista sin capacidad declarada —``IsAuthenticated`` solo **salta** el
    modelo de capacidades—, así que se gatea con ``settings.edit``, que es la
    del panel al que este dato pertenece. El gate es más estrecho que el de la
    fuente, nunca más ancho.
    """

    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'settings.edit'

    @extend_schema(
        summary='¿La base tiene datos de demostración active_users?',
        tags=['config'],
        responses={200: OpenApiTypes.BOOL},
    )
    def get(self, request):
        return Response(bool(IrModule.objects.filter(demo=True).count()))
