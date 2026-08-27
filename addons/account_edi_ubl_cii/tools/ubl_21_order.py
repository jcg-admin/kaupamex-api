r"""Estructura del documento ``Order`` de UBL 2.1, con sus nodos en orden.

Adaptación de ``odoo19c: addons/account_edi_ubl_cii/tools/ubl_21_order.py``
(``odoo-tools@622ddc2a``, LGPL-3, 42 líneas) — atribución y aviso de licencia
preservados (DEC-KX-03).

**Porte verbatim: 2 constantes, 0 símbolos ejecutables.** Misma divergencia
única que ``ubl_21_invoice.py``: la ruta del ``import``. La fuente no importa
``ubl_21_extensions`` aquí (el ``Order`` no lleva ``ext:UBLExtensions``), y
eso se conserva.
"""
from . import ubl_21_common as cac

OrderLine = {
    'cac:LineItem': {
        'cbc:ID': {},
        'cbc:UUID': {},
        'cbc:Note': {},
        'cbc:Quantity': {},
        'cbc:LineExtensionAmount': {},
        'cbc:TotalTaxAmount': {},
        'cac:AllowanceCharge': cac.AllowanceCharge,
        'cac:Price': cac.Price,
        'cac:Item': cac.Item,
        'cac:TaxTotal': cac.TaxTotal,
        'cac:ItemPriceExtension': cac.ItemPriceExtension,
    }
}

Order = {
    '_tag': 'Order',
    'cbc:CustomizationID': {},
    'cbc:ProfileID': {},
    'cbc:ID': {},
    'cbc:IssueDate': {},
    'cbc:OrderTypeCode': {},
    'cbc:Note': {},
    'cbc:DocumentCurrencyCode': {},
    'cac:ValidityPeriod': cac.Period,
    'cac:QuotationDocumentReference': cac.DocumentReference,
    'cac:OriginatorDocumentReference': cac.DocumentReference,
    'cac:BuyerCustomerParty': cac.CustomerParty,
    'cac:SellerSupplierParty': cac.SupplierParty,
    'cac:Delivery': cac.Delivery,
    'cac:PaymentTerms': cac.PaymentTerms,
    'cac:AllowanceCharge': cac.AllowanceCharge,
    'cac:TaxTotal': cac.TaxTotal,
    'cac:AnticipatedMonetaryTotal': cac.MonetaryTotal,
    'cac:OrderLine': OrderLine,
}
