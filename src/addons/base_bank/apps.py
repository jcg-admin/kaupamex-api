from django.apps import AppConfig


class BaseBankConfig(AppConfig):
    """App de feature opcional: validación de cuenta bancaria (DEC-01).

    Adaptación nativa de ``base_iban`` de Odoo (LGPL-3), que agrega
    ``check_iban`` (validación de número IBAN con su dígito verificador
    mod-97) a ``res.partner.bank``. Aquí se expone un validador por país
    (MX = CLABE, la Clave Bancaria Estandarizada de 18 dígitos con su
    dígito verificador mod-10 ponderado). Es un módulo ``base_*`` —
    cimiento del cluster ``account_*`` (bank / payment / L0 billing:
    una ``Company`` que cobra o paga por SPEI necesita una CLABE bien
    formada).
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.base_bank'
    verbose_name = 'Base — Validación de cuenta bancaria (IBAN/CLABE)'
