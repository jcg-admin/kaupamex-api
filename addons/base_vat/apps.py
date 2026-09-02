import importlib

from django.apps import AppConfig


class BaseVatConfig(AppConfig):
    """App de feature opcional: validación de identificador fiscal (DEC-01).

    Adaptación de ``base_vat`` de Odoo (LGPL-3, ``odoo19c:``), que agrega
    ``check_vat`` a ``res.partner`` con un método por país (``check_vat_XX``).
    Es un módulo ``base_*`` — cimiento del cluster ``account_*`` (la
    facturación necesita un identificador bien formado del emisor y del
    receptor).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.base_vat'
    verbose_name = 'Base — Validación de identificador fiscal (VAT/RFC)'

    def ready(self):
        """Aplica los cuatro bloques de extensión — ≙ los cuatro ``_inherit``.

        Los módulos se traen con ``importlib.import_module`` y no con un
        ``import`` al top: importarlos ahí levantaría ``AppRegistryNotReady``
        porque declaran modelos ajenos al arrancar. Es la excepción #4 de
        ``no-lazy-imports.md`` — una llamada de función, no un statement.
        """
        partner = importlib.import_module(f'{self.name}.models.res_partner')
        company = importlib.import_module(f'{self.name}.models.res_company')
        country = importlib.import_module(f'{self.name}.models.res_country')
        settings = importlib.import_module(
            f'{self.name}.models.res_config_settings')
        company.apply_base_vat_res_company_extensions()
        country.apply_base_vat_res_country_extensions()
        settings.apply_base_vat_res_config_settings_extensions()
        partner.apply_base_vat_extensions()
