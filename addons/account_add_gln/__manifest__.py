# Adaptado de Odoo Community `account_add_gln/__manifest__.py` (LGPL-3,
# odoo19c:) — atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'GLN del contacto',
    'version': '1.0',
    'category': 'Accounting/Accounting',
    'summary': (
        'Añade el Global Location Number (GS1) a ResPartner, el identificador '
        'que exige el intercambio electrónico de documentos'
    ),
    # `depends` MEDIDO da ['base'] y la referencia declara ['account']. La
    # divergencia es de HOGAR, no de alcance: allí el campo se declara sobre
    # la vista contable del partner, así que el addon cuelga de `account`;
    # aquí el terminal es `ResPartner`, que vive en `base`. Se declaran los
    # dos: `account` porque el GLN sólo tiene sentido en el eje de
    # facturación, y ése es el encuadre que la referencia fija.
    'depends': [
        'base',     # ResPartner — el modelo que este addon extiende
        'account',  # el eje que da sentido al identificador (fidelidad a la ref)
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
