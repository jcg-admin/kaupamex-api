"""Extensión de ``res.company`` — el análogo nativo de ``_inherit``.

En la referencia un addon extiende un modelo del núcleo declarando
``_inherit = 'res.company'`` en su propio ``models/res_company.py``
(precedente medido: ``odoo19c: auth_ldap/models/res_company.py:8``). Django
no distribuye el *esquema* entre apps (la migración pertenece al app_label
del modelo), pero los **métodos** sí se aportan desde el addon dueño del
comportamiento: este módulo los asigna sobre ``ResCompany`` al importarse,
igual que ``_inherit`` los aporta al cargar el addon.

Los métodos existen sólo con ``sale_subscription`` instalado — exactamente
la semántica de ``_inherit``.
"""
from django.utils import timezone

from addons.base.models import ResCompany, ResCurrency
from addons.sale_subscription.data.res_company_data import SYSTEM_COMPANY_CODE


def active_module_codes(self, now=None):
    """Set de ``Module.code`` con suscripción **activa** (L1-a).

    El resolver de authz compone: caps L2 filtradas por
    ``c.module in company.active_module_codes()``. Lee el reverso
    ``subscriptions`` que declara ``CompanyModuleSubscription``.
    """
    if now is None:
        now = timezone.now()
    codes = set()
    for sub in self.subscriptions.select_related('module').all():
        if sub.is_active(now):
            codes.add(sub.module.code)
    return codes


def get_system(cls):
    """La compañía de sistema del operador (``is_system``), sembrándola si falta."""
    company = cls.objects.filter(code=SYSTEM_COMPANY_CODE).first()
    if company is not None:
        return company
    return cls.create_company(
        'Kaupamex (plataforma)', currency=_seed_currency(),
        code=SYSTEM_COMPANY_CODE, status=cls.Status.ACTIVE, is_system=True)


def _seed_currency():
    """MXN — la moneda de la semilla (``res_currency_data.xml`` la declara)."""
    currency, _ = ResCurrency.objects.get_or_create(
        name='MXN', defaults={'symbol': '$'})
    return currency


ResCompany.active_module_codes = active_module_codes
ResCompany.get_system = classmethod(get_system)
