"""Localize the inherited report failure without committing business data."""
import json
import argparse
from unittest.mock import patch
import sys
from pathlib import Path

import django
from django.db import transaction
from django.template import Context, Engine

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
parser = argparse.ArgumentParser()
parser.add_argument("--pipeline", action="store_true")
parser.add_argument("--result", type=Path)
arguments = parser.parse_args()
django.setup()

from addons.base.models.ir_ui_view import IrUiView
from addons.base.models import ir_actions_report as report_module
from addons.base.models.ir_actions_report import IrActionsReport, REPORT_TYPE_PDF
from tests.integration.base.test_report_engine import texto_impreso
from addons.base.report_template import interpret_descriptor
from addons.sale.models import SaleOrder
from addons.sale_stock.models.sale_order import SaleOrderDelivery
from tests.factories.order_factory import make_order

output = arguments.result or (Path(__file__).resolve().parents[1] / 'outputs' / (
    'incoterm-pipeline-resolution.json' if arguments.pipeline else 'incoterm-resolution.json'))
before = (SaleOrder.objects.count(), SaleOrderDelivery.objects.count(),
          IrActionsReport.objects.count())
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
    if arguments.pipeline:
        report = IrActionsReport.objects.create(
            name='Incoterm pipeline probe', report_name='sale.report_saleorder',
            model='sale.SaleOrder', report_type=REPORT_TYPE_PDF)
        selected = report._get_template_view(report.report_name)
        rendering_context = report._get_rendering_context(report, [fresh.pk], {})
        rendered = report._render_template(report.report_name, rendering_context)
        prepared = report._prepare_html(rendered, report_model=report.model)
        captures = []
        original_helper = report_module.run_helper

        def capture(helper, descriptor):
            captures.append({'helper': helper, 'notes': descriptor.get('notes'),
                             'body_keys': list(descriptor)})
            return original_helper(helper, descriptor)

        with patch.object(report_module, 'run_helper', side_effect=capture):
            content, extension = IrActionsReport._render(report, [fresh.pk])
        result['pipeline'] = {
            'selected_view_id': selected.pk if selected is not None else None,
            'render_method_module': report._render_template.__module__,
            'rendered_notes': [body.get('notes') for body in rendered['bodies']],
            'prepared_notes': [body.get('notes') for body in prepared[0]],
            'helper_payloads': captures,
            'pdf_extension': extension,
            'pdf_incoterm_present': 'Incoterm: FOB Veracruz' in texto_impreso(content),
        }
    transaction.set_rollback(True)
after = (SaleOrder.objects.count(), SaleOrderDelivery.objects.count(),
         IrActionsReport.objects.count())
assert after == before
result['business_row_counts_unchanged'] = True
output.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
