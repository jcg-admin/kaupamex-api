# Adaptado de Odoo `account_test/__manifest__.py` (LGPL-3,
# odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de, odoo19c:) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Accounting Consistency Tests',
    'version': '1.0',
    'category': 'Accounting/Accounting',
    'summary': 'Pruebas manuales de consistencia contable (Reporting → '
               'Accounting Tests): consultas SQL/Python guardadas que se '
               'ejecutan bajo demanda y devuelven las filas inconsistentes.',
    # `depends` MEDIDO contra los imports reales de este addon (no copiado de
    # la referencia, que declara solo `['account']` porque su vista cuelga
    # del menú `account.menu_finance_reports` — aquí no se porta menú, ver
    # docstring de `models/accounting_assert_test.py`). Este addon importa
    # `account.AccountMove`/`AccountMoveLine`/`AccountBankStatement`/
    # `AccountBankStatementLine` (`reconciled_inv()` + los datos semilla).
    'depends': [
        'account',
    ],
    # Licencia de la fuente de la que se adapta este addon, tal como su
    # manifest la declara (DEC-KX-03 punto 1): `account_test` en Odoo es
    # LGPL-3.
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    # La instalación es `INSTALLED_APPS` explícito (`config/settings/
    # base.py`, fuera de este alcance — ver `apps.py`), igual que
    # `account_debit_note`/`account_qr_code_sepa` lo declaran para el mismo
    # campo sin mecanismo real detrás en este ORM.
    'auto_install': False,
}
