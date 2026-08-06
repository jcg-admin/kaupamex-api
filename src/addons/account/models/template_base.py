"""Plantilla **base** — lo que toda empresa recibe, tenga el plan que tenga.

Adaptación fiel de las plantillas sin código de ``odoo19c:
account/models/chart_template.py`` (addon **LGPL-3**, copia con atribución por
DEC-KX-03). Allá son métodos del ``AbstractModel`` decorados con
``@template(model=...)`` **sin** primer argumento; su resolutor recorre
``[None] + parents`` (``chart_template.py:813``), así que lo que se declara sin
código aplica a todos los planes y se resuelve **primero** — un plan concreto
puede sobreescribir un campo suelto sin repetir la tabla.

Por qué los diarios viven aquí y no en un CSV de plan: un diario de ventas no
es una particularidad de la contabilidad mexicana ni de la genérica. Es lo que
hace falta para **asentar**, y sin él un plan cargado es un catálogo de cuentas
que no puede emitir una factura.
"""
from addons.account.models.chart_template import template
from tools.translate import _


@template(model='account.journal')
def get_account_journal():
    """Los seis diarios por defecto — ≙ ``_get_account_journal``.

    Los códigos son los de la referencia. El de banco es el único que allá se
    deja en blanco porque su ORM lo genera: ``_get_next_journal_default_code``
    (``odoo19c: account/models/account_journal.py:883``) compone el prefijo
    ``BNK`` con el primer número libre, así que en una empresa nueva da
    ``BNK1``. Aquí se escribe ese valor: nuestro ``AccountJournal`` declara
    ``code`` con ``UniqueConstraint(company, code)``, y dejarlo vacío haría
    colisionar dos diarios en blanco en cuanto hubiera un segundo.

    Tres campos de la referencia no se portan porque el modelo no los tiene:
    ``sequence`` y ``show_on_dashboard`` (ordenación y visibilidad del tablero
    de Odoo, que aquí no existe) y ``color``. Ninguno participa en el asiento.
    """
    return {
        'sale': {
            'name': _('Ventas'),
            'type': 'sale',
            'code': 'INV',
        },
        'purchase': {
            'name': _('Compras'),
            'type': 'purchase',
            'code': 'BILL',
        },
        'general': {
            'name': _('Operaciones varias'),
            'type': 'general',
            'code': 'MISC',
        },
        'exch': {
            'name': _('Diferencia de cambio'),
            'type': 'general',
            'code': 'EXCH',
        },
        'caba': {
            'name': _('Impuestos con criterio de caja'),
            'type': 'general',
            'code': 'CABA',
        },
        'bank': {
            'name': _('Banco'),
            'type': 'bank',
            'code': 'BNK1',
        },
    }


@template(model='account.reconcile.model')
def get_account_reconcile_model():
    """Las dos reglas de conciliación por defecto — ≙ ``_get_account_reconcile_model``.

    También base, y por el mismo motivo que los diarios: una transferencia
    interna y una comisión bancaria aparecen en el extracto de cualquier
    empresa, no de una localización concreta.

    La referencia expresa las líneas hijas con ``Command.create({...})``, la
    forma con la que su ORM distingue crear de enlazar. Aquí una lista de
    diccionarios bajo el nombre de la relación ya significa «crear estas
    hijas» — es lo que el cargador hace con ``repartition_line_ids`` del CSV,
    así que no hace falta un envoltorio que sólo diga «create».
    """
    return {
        'internal_transfer_reco': {
            'name': _('Transferencias internas'),
            'line_ids': [{
                'amount_type': 'percentage',
                'amount_string': '100',
                'label': _('Transferencias internas'),
            }],
        },
        'bank_fees_reco': {
            'name': _('Comisiones bancarias'),
            'match_label': 'contains',
            'match_label_param': 'Bank Fees',
            'line_ids': [{
                'amount_type': 'percentage',
                'amount_string': '100',
                'label': _('Comisiones bancarias'),
            }],
        },
    }
