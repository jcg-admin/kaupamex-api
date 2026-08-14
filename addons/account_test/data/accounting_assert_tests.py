r"""Datos semilla — ``data/accounting_assert_test_data.xml`` de la referencia.

Adaptación de ``addons/account_test/data/accounting_assert_test_data.xml``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, ``odoo19c:``,
LGPL-3 — atribución y aviso de licencia preservados, DEC-KX-03).

Seis registros activos; se portan los seis
================================================

La referencia declara OCHO ``<record>``, pero DOS (``account_test_04``,
``account_test_08``) están comentados en el propio XML con
``<!-- TODO: rewrite test since the model of reconciliation has changed -->``
y ``<!-- TODO account.period has been removed -->`` — **nunca estuvieron
activos** en la referencia. No portarlos no es una omisión de este porte:
es reproducir fielmente que la referencia misma los desactivó. Los seis que
SÍ están activos (``account_test_01``, ``_03``, ``_05``, ``_05_2``, ``_06``,
``_07``) se portan todos — conteo: ``grep -c "<record model=" ...xml`` da 8,
``grep -c "<!--.*record model="`` da 2 → 6 activos, 6 portados.

Drift de la referencia preservado a propósito (tres registros)
====================================================================

``account_test_05``, ``_05_2`` y ``_06`` referencian la tabla
``account_invoice`` — modelo fusionado en ``account.move`` desde Odoo ~10;
medido en ``odoo19c: addons/account/models/*.py``:
``grep -rn "_table_query\|_auto = False" | grep -i invoice`` → **0 hits**. Ni
siquiera en Odoo 19 real existe esa tabla: ejecutar estos tres tests ahí
también fallaría. Se portan VERBATIM (dato fiel a la fuente, aunque la
fuente esté rota) — no se inventa una migración de esas consultas a
``account_move`` porque eso sería reemplazar el dato de la referencia por
uno nuestro, no portarlo.

``account_test_06`` tiene, además, una línea ``from odoo import _`` dentro
de ``code_exec`` — un ``IMPORT_FROM`` que el propio ``safe_eval`` de Odoo
(``_BLACKLIST``, ``odoo/tools/safe_eval.py:78-86``) **también** bloquea. Es
decir: este registro semilla, tal como lo distribuye la referencia, nunca
pudo ejecutarse ni siquiera en Odoo real — segundo defecto de la misma
fila, independiente del primero (``account_invoice``). Se preserva
verbatim por la misma razón: es el dato de la fuente, roto y todo.

``account_test_03`` SÍ diverge del texto de la referencia
================================================================

La consulta original agrupa/compara por ``ml.date``
(``account_move_line.date``). Esa columna existe en ``odoo19c:
account_move_line.py:69`` pero **no** en nuestro
``account/models/account_move_line.py`` — declarado DEFERIDO ahí (propio
docstring de ese archivo: *"amount_residual / reconciled ... quedan
DEFERIDOS"*, y ``date`` con ellos). Agregarla requeriría migrar
``account/`` — fuera de este alcance ("no tocar ningún otro addon"). Se
retira la comparación de fecha y se conserva el invariante central del
test (balance por asiento = 0); ver el comentario inline en
``account_test_03`` abajo para el detalle exacto del recorte.
"""

#: Cada entrada ≙ un ``<record model="accounting.assert.test" id="...">``
#: de la referencia. ``xmlid`` es el ``id`` del ``<record>`` (sin el prefijo
#: de módulo — se arma en ``seed_accounting_assert_tests``, igual que
#: ``account_fleet.data.fleet_service_types``).
TESTS = [
    {
        'xmlid': 'account_test_01',
        'sequence': 1,
        'name': 'Test 1: General balance',
        'desc': 'Check the balance: Debit sum = Credit sum',
        'code_exec': '''sql="""SELECT
sum(debit)-sum(credit) as balance
FROM  account_move_line
"""
cr.execute(sql)
result=[]
res= cr.dictfetchall()
if res[0]['balance']!=0.0 and res[0]['balance'] is not None:
  result.append(_('* The difference of the balance is: '))
  result.append(res)
''',
    },
    {
        'xmlid': 'account_test_03',
        'sequence': 3,
        'name': 'Test 3: Movement lines',
        'desc': 'Check if movement lines of a posted entry are balanced',
        # Divergencia declarada (ver docstring del módulo): la referencia
        # agrega `am.date`/`ml.date`/`am.date as am_date`/`ml.date as
        # ml_date` al SELECT y GROUP BY, y su HAVING incluye
        # `or am.date!=ml.date`. `ml.date` no existe aquí — se retira esa
        # mitad, quedando el chequeo de balance (`sum(ml.debit-ml.credit)
        # <> 0`), que es el invariante que el nombre del test declara.
        'code_exec': '''order_columns=['am_date','am.id']
sql="""SELECT
  am.id as move_id,
  sum(ml.debit)-sum(ml.credit) as balance,
  am.date as am_date
FROM account_move am, account_move_line ml
WHERE
  ml.move_id = am.id
GROUP BY am.name, am.id, am.state, am.date
HAVING abs(sum(ml.debit-ml.credit)) <> 0
"""
cr.execute(sql)
res = cr.dictfetchall()
if res:
    res.insert(0,_('* The test failed for these movement lines:'))
result = res
''',
    },
    {
        'xmlid': 'account_test_05',
        'sequence': 5,
        'name': 'Test 5.1 : Payable and Receivable accountant lines of '
               'reconciled invoices',
        'desc': 'Check that reconciled invoice for Sales/Purchases has '
               'reconciled entries for Payable and Receivable Accounts',
        # Referencia `account_invoice` (tabla ausente, ver docstring del
        # módulo) — verbatim.
        'code_exec': '''res = []
cr.execute("SELECT distinct inv.number,inv.id from account_invoice inv, account_move m, account_move_line ml, account_account a where m.id=ml.move_id and ml.account_id=a.id and a.account_type in ('asset_receivable','liability_payable') and inv.move_id=m.id and ml.reconciled is true;")
records= cr.dictfetchall()
rec = [r['id'] for r in records]
res = reconciled_inv()
invoices = set(rec).difference(set(res))
result = [rec for rec in records if rec['id'] in invoices]
if result:
    result.insert(0,_('* Invoices that need to be checked: '))
''',
    },
    {
        'xmlid': 'account_test_05_2',
        'sequence': 6,
        'name': 'Test 5.2 : Reconcilied invoices and Payable/Receivable '
               'accounts',
        'desc': 'Check that reconciled account moves, that define Payable '
               'and Receivable accounts, are belonging to reconciled '
               'invoices',
        # Referencia `account_invoice` — verbatim.
        'code_exec': '''res = reconciled_inv()
result=[]
if res:
    cr.execute("SELECT distinct inv.number,inv.id from account_invoice inv, account_move_line ml, account_account a, account_move m where m.id=ml.move_id and inv.move_id=m.id and inv.id=inv.move_id and ml.reconciled is false and a.account_type in ('asset_receivable','liability_payable') and ml.account_id=a.id and inv.id in %s",(tuple(res),))
    records = cr.dictfetchall()
    result = [rec for rec in records]
    if result:
        result.insert(0,_('* Invoices that need to be checked: '))
''',
    },
    {
        'xmlid': 'account_test_06',
        'sequence': 7,
        'name': 'Test 6 : Invoices status',
        'desc': "Check that paid/reconciled invoices are not in 'Open' "
               'state',
        # Referencia `account_invoice` + `from odoo import _` (bloqueado
        # por safe_eval incluso en la referencia) — verbatim, ver
        # docstring del módulo.
        'code_exec': '''
from odoo import _
res = []
column_order = ['number','id','name','state']
if reconciled_inv():
  cr.execute("select inv.name,inv.state,inv.id,inv.number from account_invoice inv where inv.state!='paid' and id in %s", (tuple(reconciled_inv()),))
  res = cr.dictfetchall()
result = res
if result:
    result.insert(0,_('* Invoices that need to be checked: '))
''',
    },
    {
        'xmlid': 'account_test_07',
        'sequence': 8,
        'name': 'Test 7: Closing balance on bank statements',
        'desc': 'Check on bank statement that the Closing Balance = '
               'Starting Balance + sum of statement lines',
        'code_exec': '''column_order = ['name','difference']
cr.execute("SELECT s.balance_start+sum(m.amount)-s.balance_end_real as difference, s.name from account_bank_statement s inner join account_bank_statement_line m on m.statement_id=s.id group by s.id, s.balance_start, s.balance_end_real,s.name having abs(s.balance_start+sum(m.amount)-s.balance_end_real) > 0.000000001;")
result = cr.dictfetchall()
if result:
    result.insert(0,_('* Unbalanced bank statement that need to be checked: '))
''',
    },
]


def seed_accounting_assert_tests(apps, alias):
    """Crea (o respeta) los seis registros semilla + su identificador
    externo — idempotente por ``(module, name)`` de ``ir.model.data``,
    mismo criterio que ``account_fleet.data.seed_fleet_service_types``.

    Escribe sobre los modelos **históricos** (``apps.get_model``) porque
    corre dentro de una migración.
    """
    AccountingAssertTest = apps.get_model('account_test', 'AccountingAssertTest')
    IrModelData = apps.get_model('base', 'IrModelData')
    label = AccountingAssertTest._meta.label
    created = []

    for entry in TESTS:
        row = IrModelData.objects.using(alias).filter(
            module='account_test', name=entry['xmlid']).first()
        existing = None
        if row is not None:
            existing = AccountingAssertTest.objects.using(alias).filter(
                pk=row.res_id).first()
        if existing is None:
            existing = AccountingAssertTest.objects.using(alias).create(
                name=entry['name'],
                desc=entry['desc'],
                code_exec=entry['code_exec'],
                sequence=entry['sequence'],
                active=True,
            )
        IrModelData.objects.using(alias).update_or_create(
            module='account_test', name=entry['xmlid'],
            defaults={'model': label, 'res_id': existing.pk, 'noupdate': True},
        )
        created.append(existing)
    return created
