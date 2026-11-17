"""Aplica la unidad 4 (purchase-line-qty-received-0122) al modelo.

Se ejecuta desde la raíz de kaupamex-api cuando el árbol está libre del gate.
Cada ancla se exige única; si no lo es, no se toca nada.
"""
import pathlib
import sys

PATH = pathlib.Path('addons/purchase/models/purchase_order_line.py')
text = PATH.read_text()

FIELDS_ANCHOR = ('    #: ≙ los related de la fuente '
                 '(``odoo19c: :38,54,85-90,105``), sin\n')
FIELDS = '''\
    #: ≙ ``qty_received_method``/``qty_received``/``qty_received_manual``
    #: (``odoo19c: :60-65``). Las cantidades son ``Float(digits='Product
    #: Unit')`` en la fuente y aquí ``Decimal`` de cuatro decimales, como
    #: ``product_qty``. ``purchase_stock`` añade el método ``stock_moves``.
    qty_received_method = fields.Selection(
        [('manual', 'Manual')], string='Received Qty Method',
        compute='_compute_qty_received_method', store=True,
        max_length=16, null=True, blank=True,
        help_text='According to product configuration, the received '
                  'quantity can be automatically computed by mechanism:\\n'
                  '  - Manual: the quantity is set manually on the line\\n'
                  '  - Stock Moves: the quantity comes from confirmed '
                  'pickings\\n')
    qty_received = fields.Monetary(
        'Received Qty', max_digits=16, decimal_places=4,
        compute='_compute_qty_received', inverse='_inverse_qty_received',
        compute_sudo=True, store=True, readonly=False,
        null=True, blank=True)
    qty_received_manual = fields.Monetary(
        'Manual Received Qty', max_digits=16, decimal_places=4,
        copy=False, null=True, blank=True)
    #: ≙ ``qty_received_at_date`` (``odoo19c: :70-74``): sin columna,
    #: depende del contexto ``accrual_entry_date``.
    qty_received_at_date = fields.Monetary(
        'Received', max_digits=16, decimal_places=4,
        compute='_compute_qty_received_at_date')
'''

METHODS_ANCHOR = '    def _prepare_base_line_for_taxes_computation(self):\n'
METHODS = '''    @api.depends('product_id', 'product_id.product_tmpl.type')
    def _compute_qty_received_method(self):
        """≙ ``odoo19c: :218-224``."""
        for line in self:
            if line.product_id and line.product_id.type in [
                    'consu', 'service']:
                line.qty_received_method = 'manual'
            else:
                line.qty_received_method = False

    @api.depends('qty_received_method', 'qty_received_manual')
    def _compute_qty_received(self):
        """≙ ``odoo19c: :226-231``."""
        received_qties = self._prepare_qty_received()
        for line in self:
            if not line.qty_received or line in received_qties:
                line.qty_received = received_qties[line]

    @api.depends('qty_received')
    @api.depends_context('accrual_entry_date')
    def _compute_qty_received_at_date(self):
        """≙ ``odoo19c: :233-242``."""
        if not self._date_in_the_past():
            for line in self:
                line.qty_received_at_date = line.qty_received
            return
        received_quantities = self._prepare_qty_received()
        for line in self:
            line.qty_received_at_date = received_quantities[line]

    def _prepare_qty_received(self):
        """≙ ``odoo19c: :244-251``. ``Decimal`` en vez de ``float``."""
        received_qties = defaultdict(Decimal)
        for line in self:
            if line.qty_received_method == 'manual':
                received_qties[line] = line.qty_received_manual or Decimal('0')
            else:
                received_qties[line] = Decimal('0')
        return received_qties

    @api.onchange('qty_received')
    def _inverse_qty_received(self):
        """≙ ``odoo19c: :253-263``. Con método ``manual`` el valor escrito va
        a ``qty_received_manual``; sin él, ésta queda en cero porque la
        cantidad la calcula otro mecanismo."""
        for line in self:
            if line.qty_received_method == 'manual':
                line.qty_received_manual = line.qty_received
            else:
                line.qty_received_manual = Decimal('0')

    @api.model
    def _date_in_the_past(self):
        """≙ ``odoo19c: :707-712``."""
        if 'accrual_entry_date' not in self.env.context:
            return False
        accrual_date = fields.Date.from_string(
            self.env.context['accrual_entry_date'])
        return bool(accrual_date) and accrual_date < fields.Date.today()

'''

IMPORT_ANCHOR = 'from decimal import Decimal\n'
IMPORT = 'from collections import defaultdict\nfrom decimal import Decimal\n'

for anchor in (FIELDS_ANCHOR, METHODS_ANCHOR, IMPORT_ANCHOR):
    if text.count(anchor) != 1:
        sys.exit(f'ancla no única ({text.count(anchor)}): {anchor!r}')
text = text.replace(IMPORT_ANCHOR, IMPORT)
text = text.replace(FIELDS_ANCHOR, FIELDS + FIELDS_ANCHOR)
text = text.replace(METHODS_ANCHOR, METHODS + METHODS_ANCHOR)
PATH.write_text(text)
print('unidad 4 aplicada a', PATH)
