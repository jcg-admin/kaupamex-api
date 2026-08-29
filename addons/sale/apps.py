import importlib

from django.apps import AppConfig


class SaleConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'addons.sale'
    verbose_name       = 'Ventas (sale.order)'

    def ready(self):
        # Cuelga lo que ``sale`` extiende en ResCompany (quotation_validity_
        # days, tarea #256) ANTES del resolutor de audiencia: la orden lee
        # ese campo al calcular su vigencia, así que tiene que existir en el
        # registro de modelos primero. ``importlib.import_module`` es la
        # excepción #4 sancionada para ``ready()``.
        importlib.import_module(f'{self.name}.models.res_company') \
            .apply_sale_extensions()
        # Lo que ``sale`` cuelga sobre la familia analitica: el ``so_line``
        # de ``account.analytic.line`` y el ``selection_add`` de
        # ``business_domain`` — ≙ ``sale/models/analytic.py`` de la fuente.
        importlib.import_module(f'{self.name}.models.analytic') \
            .apply_sale_analytic_extensions()
        # La bandera de descuento por linea de pedido: dos metodos sobre
        # ``product.pricelist.item`` — ≙ ``sale/models/product_pricelist_item.py``.
        importlib.import_module(f'{self.name}.models.product_pricelist_item') \
            .apply_sale_pricelist_item_extensions()
        # ``so_reference_type`` sobre la pasarela de pago: qué comunicación ve
        # el cliente en su estado de cuenta — ≙ ``sale/models/payment_provider.py``.
        importlib.import_module(f'{self.name}.models.payment_provider') \
            .apply_sale_payment_provider_extensions()
        # ``attached_on_sale`` sobre el documento de producto: dónde se comparte
        # con el cliente — ≙ ``sale/models/product_document.py``.
        importlib.import_module(f'{self.name}.models.product_document') \
            .apply_sale_product_document_extensions()
        # Los cinco simbolos que ``sale`` cuelga sobre el parametro de sistema:
        # encender un parametro enciende su cron — ≙ ``sale/models/ir_config_parameter.py``.
        importlib.import_module(f'{self.name}.models.ir_config_parameter') \
            .apply_sale_config_parameter_extensions()
        # Bloque medido de ``sale/models/ir_actions_report.py``: sus tres
        # bloqueos estan citados en el propio archivo; su sucesor es la #982.
        importlib.import_module(f'{self.name}.models.ir_actions_report') \
            .apply_sale_report_extensions()
        # Inscribe el resolutor de audiencia "compradores de un producto" en
        # el registro de ``mail`` (T-035).
        importlib.import_module(f'{self.name}.audience')
