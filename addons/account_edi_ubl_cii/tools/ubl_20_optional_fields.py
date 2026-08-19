r"""Campos opcionales de PEPPOL declarados como campos de estudio (``x_studio_*``).

Adaptación de ``odoo19c: addons/account_edi_ubl_cii/tools/ubl_20_optional_fields.py``
(``odoo-tools@622ddc2a``, LGPL-3, 91 líneas) — atribución y aviso de licencia
preservados (DEC-KX-03).

**Porte verbatim: 7 constantes, 0 símbolos ejecutables de módulo.** Cada
entrada declara ``path`` (la ruta de nodos UBL donde se inyecta el valor),
``attrs`` (un invocable que produce el ``dict`` que ``dict_to_xml``
serializa) y ``supported_types`` (los tipos de campo admitidos).

Los ``lambda`` de ``attrs`` **no** caen bajo la regla de "``default=``
siempre función nombrada": esa regla protege al serializador de migraciones
de Django, y estos invocables no son ``default=`` de ningún campo — son
accesores que ``_import_optional_fields`` invoca en tiempo de ejecución.
Se conservan verbatim.

Los campos ``x_studio_*`` son **campos de estudio**: los declara el
usuario final sobre ``account.move``/``account.move.line``, no este addon.
``account_edi_ubl.py`` los lee con ``getattr`` defensivo y salta los que
no existan, así que la ausencia del mecanismo de campos personalizados en
este árbol no bloquea nada: el bucle sencillamente no encuentra ninguno.
"""

PEPPOL_COMMON_OPTIONAL_FIELDS = {
    "x_studio_peppol_tax_point_date": {
        "path": ["cbc:TaxPointDate"],
        "attrs": lambda invoice: {
            "_text": invoice.x_studio_peppol_tax_point_date,
        },
        'supported_types': ['date'],
    },
    "x_studio_peppol_contract_document_reference_id": {
        "path": ["cac:ContractDocumentReference", "cbc:ID"],
        "attrs": lambda invoice: {
            '_text': invoice.x_studio_peppol_contract_document_reference_id,
        },
        'supported_types': ['char', 'text'],
    },
    "x_studio_peppol_despatch_document_reference_id": {
        "path": ["cac:DespatchDocumentReference", "cbc:ID"],
        "attrs": lambda invoice: {
            '_text': invoice.x_studio_peppol_despatch_document_reference_id,
        },
        'supported_types': ['char', 'text'],
    },
    "x_studio_peppol_accounting_cost": {
        "path": ["cbc:AccountingCost"],
        "attrs": lambda invoice: {
            '_text': invoice.x_studio_peppol_accounting_cost,
        },
        'supported_types': ['char', 'text'],
    },
    "x_studio_peppol_order_reference_id": {
        "path": ["cac:OrderReference", "cbc:ID"],
        "attrs": lambda invoice: {
            '_text': invoice.x_studio_peppol_order_reference_id,
        },
        'supported_types': ['char', 'text'],
    },
    "x_studio_peppol_invoice_period_start_date": {
        "path": ["cac:InvoicePeriod", "cbc:StartDate"],
        "attrs": lambda invoice: {
            '_text': invoice.x_studio_peppol_invoice_period_start_date,
        },
        'supported_types': ['date'],
    },
    "x_studio_peppol_invoice_period_end_date": {
        "path": ["cac:InvoicePeriod", "cbc:EndDate"],
        "attrs": lambda invoice: {
            '_text': invoice.x_studio_peppol_invoice_period_end_date,
        },
        'supported_types': ['date'],
    },
}

PEPPOL_INVOICE_OPTIONAL_FIELDS = {
    **PEPPOL_COMMON_OPTIONAL_FIELDS,
    "x_studio_peppol_project_reference_id": {
        "path": ["cac:ProjectReference", "cbc:ID"],
        "attrs": lambda invoice: {
            '_text': invoice.x_studio_peppol_project_reference_id,
        },
        'supported_types': ['char', 'text'],
    },
}

PEPPOL_CREDIT_NOTE_OPTIONAL_FIELDS = {
    **PEPPOL_COMMON_OPTIONAL_FIELDS,
}

PEPPOL_COMMON_OPTIONAL_LINE_FIELDS = {
    "x_studio_peppol_order_line_reference_id": {
        "path": ["cac:OrderLineReference", "cbc:LineID"],
        "attrs": lambda line: {
            '_text': line.x_studio_peppol_order_line_reference_id,
        },
        'supported_types': ['char', 'text'],
    },
    "x_studio_peppol_buyers_item_id": {
        "path": ["cac:Item", "cac:BuyersItemIdentification", "cbc:ID"],
        "attrs": lambda line: {
            '_text': line.x_studio_peppol_buyers_item_id,
        },
        'supported_types': ['char', 'text'],
    },
}

PEPPOL_INVOICE_OPTIONAL_LINE_FIELDS = {
    **PEPPOL_COMMON_OPTIONAL_LINE_FIELDS,
}

PEPPOL_CREDIT_NOTE_OPTIONAL_LINE_FIELDS = {
    **PEPPOL_COMMON_OPTIONAL_LINE_FIELDS,
}
