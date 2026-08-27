r"""Estructura del documento ``DebitNote`` de UBL 2.1, con sus nodos en orden.

Adaptación de ``odoo19c: addons/account_edi_ubl_cii/tools/ubl_21_debit_note.py``
(``odoo-tools@622ddc2a``, LGPL-3, 64 líneas) — atribución y aviso de licencia
preservados (DEC-KX-03).

**Porte verbatim: 2 constantes, 0 símbolos ejecutables.** Misma divergencia
única que ``ubl_21_invoice.py``: la ruta del ``import``.
"""
from . import ubl_21_common as cac
from . import ubl_21_extensions as ext

DebitNoteLine = {
    'cbc:ID': {},
    'cbc:UUID': {},
    'cbc:Note': {},
    'cbc:DebitedQuantity': {},
    'cbc:LineExtensionAmount': {},
    'cbc:FreeOfChargeIndicator': {},
    'cac:InvoicePeriod': cac.Period,
    'cac:OrderLineReference': cac.OrderLineReference,
    'cac:BillingReference': cac.BillingReference,
    'cac:DocumentReference': cac.DocumentReference,
    'cac:PricingReference': cac.PricingReference,
    'cac:PaymentTerms': cac.PaymentTerms,
    'cac:TaxTotal': cac.TaxTotal,
    'cac:AllowanceCharge': cac.AllowanceCharge,
    'cac:Item': cac.Item,
    'cac:Price': cac.Price,
    'cac:ItemPriceExtension': cac.ItemPriceExtension,
}

DebitNote = {
    '_tag': 'DebitNote',
    'ext:UBLExtensions': ext.UBLExtensions,
    'cbc:UBLVersionID': {},
    'cbc:CustomizationID': {},
    'cbc:ProfileID': {},
    'cbc:ProfileExecutionID': {},
    'cbc:ID': {},
    'cbc:CopyIndicator': {},
    'cbc:UUID': {},
    'cbc:IssueDate': {},
    'cbc:IssueTime': {},
    'cbc:Note': {},
    'cbc:DocumentCurrencyCode': {},
    'cbc:TaxCurrencyCode': {},
    'cbc:PricingCurrencyCode': {},
    'cbc:LineCountNumeric': {},
    'cac:InvoicePeriod': cac.Period,
    'cac:DiscrepancyResponse': cac.DiscrepancyResponse,
    'cac:OrderReference': cac.OrderReference,
    'cac:BillingReference': cac.BillingReference,
    'cac:AdditionalDocumentReference': cac.DocumentReference,
    'cac:Signature': cac.Signature,
    'cac:AccountingSupplierParty': cac.SupplierParty,
    'cac:AccountingCustomerParty': cac.CustomerParty,
    'cac:SellerSupplierParty': cac.SupplierParty,
    'cac:PrepaidPayment': cac.PrepaidPayment,
    'cac:AllowanceCharge': cac.AllowanceCharge,
    'cac:Delivery': cac.Delivery,
    'cac:PaymentMeans': cac.PaymentMeans,
    'cac:PaymentTerms': cac.PaymentTerms,
    'cac:TaxExchangeRate': cac.ExchangeRate,
    'cac:PricingExchangeRate': cac.ExchangeRate,
    'cac:PaymentExchangeRate': cac.ExchangeRate,
    'cac:TaxTotal': cac.TaxTotal,
    'cac:RequestedMonetaryTotal': cac.MonetaryTotal,
    'cac:DebitNoteLine': DebitNoteLine,
}
