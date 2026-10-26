"""Localize the inherited report failure without committing business data."""
import json
import sys
from pathlib import Path

import django
from django.db import transaction
from django.template import Context, Engine

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
django.setup()

from addons.base.models.ir_ui_view import IrUiView
from addons.base.report_template import interpret_descriptor
from addons.sale.models import SaleOrder
from addons.sale_stock.models.sale_order import SaleOrderDelivery
from tests.factories.order_factory import make_order

output = Path(__file__).resolve().parents[1] / 'outputs/incoterm-resolution.json'
before = (SaleOrder.objects.count(), SaleOrderDelivery.objects.count())
with transaction.atomic():
    order = make_order()
    SaleOrderDelivery.objects.create(order=order, incoterm_location='FOB Veracruz')
    fresh = SaleOrder.objects.get(pk=order.pk)
    direct = fresh.delivery.incoterm_location
    engine = Engine(autoescape=False)
    expression = engine.from_string('{{ docs.delivery.incoterm_location }}').render(
        Context({'docs': fresh}))
    conditional = engine.from_string(
        '{% if docs.delivery.incoterm_location %}Incoterm: '
        '{{ docs.delivery.incoterm_location }}{% endif %}').render(
            Context({'docs': fresh}))
    view = IrUiView.objects.get(key='sale.report_saleorder', mode='primary')
    arch = view._get_combined_arch()
    result = {
        'direct': direct,
        'template_expression': expression,
        'template_conditional': conditional,
        'extension_rows': list(IrUiView.objects.filter(
            key='sale_stock.report_saleorder_incoterm').values(
                'active', 'mode', 'inherit_id_id')),
        'combined_incoterm_nodes': len(arch.xpath('.//field[@name="incoterm"]')),
        'rendered_notes': interpret_descriptor(arch, {'docs': fresh}).get('notes'),
        'scope': 'Owned PostgreSQL transaction; report failure localization, no ORM or business implementation acceptance',
    }
    assert direct == expression == 'FOB Veracruz'
    assert conditional == 'Incoterm: FOB Veracruz'
    transaction.set_rollback(True)
after = (SaleOrder.objects.count(), SaleOrderDelivery.objects.count())
assert after == before
result['business_row_counts_unchanged'] = True
output.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
