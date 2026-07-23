"""AppConfig — addons.observability (DEC-12): addon net-new, sin analogo Odoo.

``addons.observability`` aloja telemetria de requests HTTP (``RequestLog``,
DEC-LOG-01..08) que no tiene equivalente en ``odoo/addons/base`` ni en ningun
otro addon fiel del arbol: Odoo no modela "una fila por request HTTP" como
capa de negocio -- es un concern de infraestructura propio de este proyecto.
Por eso es la **excepcion deliberada** (DEC-12) a la regla de portacion fiel
Odoo/pretix que gobierna el resto de ``addons/``: los demas addons son o
adaptaciones de un modulo Odoo real, o quedan ausentes por no aplicar;
``observability`` es el **unico** addon legitimamente net-new del arbol.

Contenido: ``RequestLog`` (antes en ``core.models``, movido aqui en el slice 3
de ``adoptar-arquitectura-server-service-odoo``, DEC-08) + su
``RequestLogMiddleware`` (antes ``core.middleware.request_log``).

``addons.observability`` vive en el **plano de control** (base ``default``):
``RequestLog`` es telemetria global de la instancia (una fila por request
HTTP), no per-empresa -- por eso su app_label ``observability`` se registra
en ``MULTIDB_CONTROL_PLANE_APPS`` junto a ``base``, igual que ``SystemParameter``
e ``IrLogging``.
"""
from django.apps import AppConfig


class ObservabilityConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.observability'
    label = 'observability'
    verbose_name = 'Observability (telemetria HTTP request, net-new DEC-12)'
