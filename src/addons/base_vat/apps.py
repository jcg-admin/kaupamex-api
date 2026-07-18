from django.apps import AppConfig


class BaseVatConfig(AppConfig):
    """App de feature opcional: validación de identificador fiscal (DEC-01).

    Adaptación nativa de ``base_vat`` de Odoo (LGPL-3), que agrega
    ``check_vat`` a ``res.partner`` con un método por país
    (``check_vat_XX``). Aquí se expone un validador por país (MX = RFC) que se
    engancha en el campo ``Company.tax_id``. Es un módulo ``base_*`` — cimiento
    del cluster ``account_*`` (facturación/CFDI necesita un RFC bien formado
    del emisor y del receptor).
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.base_vat'
    verbose_name = 'Base — Validación de identificador fiscal (VAT/RFC)'
