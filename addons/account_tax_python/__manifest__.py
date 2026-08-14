# Adaptado de Odoo Community `account_tax_python/__manifest__.py` (LGPL-3,
# odoo19c:) — atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Impuestos con fórmula',
    'version': '1.0',
    'category': 'Accounting/Accounting',
    'summary': (
        'El tipo de impuesto cuyo importe lo calcula una expresión evaluada '
        'en entorno acotado, no un porcentaje fijo'
    ),
    # `depends` MEDIDO da tres; la referencia declara sólo ['account'] porque
    # su ORM resuelve `product`/`uom` de forma transitiva. Aquí los dos son
    # imports de Python explícitos: la fórmula recibe el producto y la
    # cantidad con su unidad en el entorno de evaluación.
    'depends': [
        'account',  # AccountTax — el modelo que este addon extiende
        'product',  # Product — variable del entorno de la fórmula
        'uom',      # Uom — la cantidad que la fórmula recibe
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
