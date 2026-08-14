# Forma propia: no adapta un addon de la referencia. Implementa el MISMO
# patrón que `base_iban` (dispatcher de validación de cuenta bancaria por
# país) para la CLABE mexicana, que la referencia no cubre en Community.
{
    'name': 'Validación de cuenta bancaria (CLABE)',
    'version': '1.0',
    'category': 'Accounting/Accounting',
    'summary': (
        'validate_clabe: los 18 dígitos de la Clave Bancaria Estandarizada '
        'con su dígito verificador mod-10 ponderado, y el despacho por país'
    ),
    # `depends` MEDIDO da VACÍO, y es correcto: `validators.py` es aritmética
    # pura sobre una cadena y no importa ningún modelo. Se declara `base` de
    # todas formas porque el addon existe para servir a `ResPartnerBank`, que
    # vive allí — igual que hace `base_iban`, su hermano de patrón.
    'depends': [
        'base',  # ResPartnerBank — el destinatario del validador
    ],
    # Eje propio: la CLABE no tiene addon de referencia del que heredar
    # licencia (DEC-KX-03).
    'license': 'propio',
    'application': False,
    'installable': True,
    'auto_install': False,
}
