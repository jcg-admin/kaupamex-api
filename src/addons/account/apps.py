"""AppConfig — addons.account.

Fiel al addon ``account`` de Odoo (18/19): libro mayor de doble entrada. Núcleo
portado como paquete ``models/`` (un archivo por modelo). Datos de negocio
per-empresa (no plano de control): NO va en ``MULTIDB_CONTROL_PLANE_APPS``;
enruta a la BD de la ``company`` bajo N>1.

Depende de ``base`` (moneda), ``company`` (empresa) y ``users`` (party). Cross-app
``_inherit`` de Odoo (res.partner/res.company/res.currency) → FK/RELATED
(DEC-SALE-01).
"""
from django.apps import AppConfig


class AccountConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.account'
    label = 'account'
    verbose_name = 'Contabilidad (libro mayor de doble entrada)'
