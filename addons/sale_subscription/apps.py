"""AppConfig — addons.sale_subscription (billing recurrente L0).

Reimplementación nativa del patrón ``sale_subscription`` de la referencia
(Enterprise, OEEL-1 → sin copia de código, DEC-KX-03): el addon extiende los
modelos del núcleo (aquí ``base.ResCompany`` vía el análogo de ``_inherit``)
y aporta los modelos propios del eje de suscripción de módulos por compañía
(DEC-KX-05). Ver ``__manifest__.py`` y ``analisis-disolucion-platform``.
"""
from django.apps import AppConfig


class SaleSubscriptionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.sale_subscription'
    verbose_name = 'Suscripciones (billing recurrente L0)'
