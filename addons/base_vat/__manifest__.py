# Adaptado de Odoo Community `base_vat/__manifest__.py` (LGPL-3, odoo19c:) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Validación de identificador fiscal',
    'version': '1.0',
    'category': 'Accounting/Accounting',
    'summary': (
        'Validador por país del identificador fiscal de ResPartner — en '
        'México, el RFC con su dígito verificador'
    ),
    # `depends` MEDIDO contra los imports reales, y ahora coincide con la
    # referencia (`odoo19c: __manifest__.py:37` declara ['account']).
    #
    # El comentario anterior decía que aquí bastaba `base` porque «el addon
    # sólo le cuelga su validador»: era cierto cuando este paquete tenía 18
    # líneas. Con los cuatro archivos portados ya no lo es —
    # `models/res_country.py` resuelve `account.AccountFiscalPosition` para
    # `has_foreign_fiscal_position` (`odoo19c: res_country.py:14-24`), y
    # `models/res_partner.py` bloquea cuatro símbolos contra
    # `account.res.partner._check_vat`.
    #
    # No introduce ciclo, medido: `grep -c base_vat addons/account/__manifest__.py`
    # da 0, y ningún manifiesto del árbol declara `base_vat` como dependencia.
    'depends': [
        'account',  # AccountFiscalPosition; y el hogar de los hooks de `vat`
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
