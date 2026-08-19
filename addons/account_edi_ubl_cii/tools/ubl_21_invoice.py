r"""Estructura del documento ``Invoice`` de UBL 2.1, con sus nodos en orden.

Adaptación de ``odoo19c: addons/account_edi_ubl_cii/tools/ubl_21_invoice.py``
(``odoo-tools@622ddc2a``, LGPL-3, 74 líneas) — atribución y aviso de licencia
preservados (DEC-KX-03).

**Porte verbatim: 2 constantes, 0 símbolos ejecutables.** Se pasa como
argumento ``template`` a :func:`addons.account.tools.dict_to_xml.dict_to_xml`
para forzar el orden de los nodos.

Única divergencia: la ruta del ``import``. La fuente escribe
``import odoo.addons.account_edi_ubl_cii.tools.ubl_21_common as cac``; en este
árbol el paquete raíz es ``addons`` (no ``odoo.addons``), así que la forma
equivalente es un import relativo del mismo paquete.
"""
from . import ubl_21_common as cac
from . import ubl_21_extensions as ext

InvoiceLine = {
    'cbc:ID': {},
    'cbc:UUID': {},
    'cbc:Note': {},
    'cbc:InvoicedQuantity': {},
    'cbc:LineExtensionAmount': {},
    'cbc:FreeOfChargeIndicator': {},
    'cac:InvoicePeriod': cac.Period,
    'cac:OrderLineReference': cac.OrderLineReference,
    'cac:BillingReference': cac.BillingReference,
    'cac:DocumentReference': cac.DocumentReference,
    'cac:PricingReference': cac.PricingReference,
    'cac:PaymentTerms': cac.PaymentTerms,
    'cac:AllowanceCharge': cac.AllowanceCharge,
    'cac:TaxTotal': cac.TaxTotal,
    'cac:WithholdingTaxTotal': cac.TaxTotal,
    'cac:Item': cac.Item,
    'cac:Price': cac.Price,
    'cac:ItemPriceExtension': cac.ItemPriceExtension,
}

Invoice = {
    '_tag': 'Invoice',
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
    'cbc:DueDate': {},
    'cbc:InvoiceTypeCode': {},
    'cbc:Note': {},
    'cbc:TaxPointDate': {},
    'cbc:DocumentCurrencyCode': {},
    'cbc:TaxCurrencyCode': {},
    'cbc:PricingCurrencyCode': {},
    'cbc:AccountingCost': {},
    'cbc:LineCountNumeric': {},
    'cbc:BuyerReference': {},
    'cac:InvoicePeriod': cac.Period,
    'cac:OrderReference': cac.OrderReference,
    'cac:BillingReference': cac.BillingReference,
    'cac:DespatchDocumentReference': cac.DocumentReference,
    'cac:OriginatorDocumentReference': cac.DocumentReference,
    'cac:ContractDocumentReference': cac.DocumentReference,
    'cac:AdditionalDocumentReference': cac.DocumentReference,
    'cac:ProjectReference': {'cbc:ID': {}},
    'cac:Signature': cac.Signature,
    'cac:AccountingSupplierParty': cac.SupplierParty,
    'cac:AccountingCustomerParty': cac.CustomerParty,
    'cac:SellerSupplierParty': cac.SupplierParty,
    'cac:Delivery': cac.Delivery,
    'cac:PaymentMeans': cac.PaymentMeans,
    'cac:PaymentTerms': cac.PaymentTerms,
    'cac:PrepaidPayment': cac.PrepaidPayment,
    'cac:AllowanceCharge': cac.AllowanceCharge,
    'cac:TaxExchangeRate': cac.ExchangeRate,
    'cac:PricingExchangeRate': cac.ExchangeRate,
    'cac:PaymentExchangeRate': cac.ExchangeRate,
    'cac:TaxTotal': cac.TaxTotal,
    'cac:WithholdingTaxTotal': cac.TaxTotal,
    'cac:LegalMonetaryTotal': cac.MonetaryTotal,
    'cac:InvoiceLine': InvoiceLine,
}
