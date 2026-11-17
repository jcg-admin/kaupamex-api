import importlib

from django.apps import AppConfig


class PurchaseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.purchase'
    verbose_name = 'Compras (purchase)'

    def ready(self):
        # Cuelga lo que ``purchase`` extiende en ResCompany (po_lock,
        # po_double_validation, po_double_validation_amount) — ≙
        # ``purchase/models/res_company.py``. ``importlib.import_module`` es
        # la excepción #4 sancionada para ``ready()``.
        importlib.import_module(
            f'{self.name}.models.res_company'
        ).apply_purchase_extensions()
        # ≙ ``purchase/models/res_partner.py``: el comprador del proveedor.
        importlib.import_module(
            f'{self.name}.models.res_partner'
        ).apply_purchase_partner_extensions()
        # ≙ ``purchase/models/account_invoice.py``: el vínculo de la línea de
        # factura con la línea de compra.
        importlib.import_module(
            f'{self.name}.models.account_invoice'
        ).apply_account_move_line_extensions()
        # ≙ ``purchase/models/product.py``: lo que cuelga en ``product`` y el
        # aviso de compra de la línea de factura.
        importlib.import_module(
            f'{self.name}.models.product'
        ).apply_purchase_product_extensions()
