"""Distingue el contrato genérico compute del Consumer sin modificar código productivo."""
import json
from pathlib import Path
from unittest.mock import patch

import django

django.setup()

from addons.base.models.ir_config_parameter import SystemParameter
from addons.product.models.product_product import ProductProduct
from addons.product.models.product_template import ProductTemplate

run = Path(__file__).resolve().parent.parent
results = {}
parameter = SystemParameter(pk=1, key='contract.fixture', value='x')
template = ProductTemplate(pk=1, name='Contract Fixture')
product = ProductProduct(pk=1, product_tmpl=template)
manager_type = type(product.product_template_attribute_values)
with patch.object(manager_type, 'all', return_value=[]):
    for name, record in [('generic_display_name', parameter), ('product_display_name', product)]:
        method = type(record)._compute_display_name
        returned = method(record)
        try:
            observed = record.display_name
        except Exception as error:
            results[name] = {'returned': returned, 'read_status': 'FAIL',
                             'exception': type(error).__name__, 'message': str(error)}
        else:
            results[name] = {'returned': returned, 'read_status': 'PASS', 'observed': observed}
        # Control: conservar cálculo, cambiar sólo la asignación que exige el descriptor.
        def assign_value(self, compute=method):
            self.display_name = compute(self)
        with patch.object(type(record), '_compute_display_name', assign_value):
            assigned = record.display_name
            assert assigned == returned
            results[name]['assignment_control'] = {'status': 'PASS', 'value': assigned}
assert all(row['read_status']=='FAIL' and row['exception']=='ValueError' for row in results.values())
results['classification'] = 'Generic DisplayNameMixin and the ProductProduct override both return instead of assigning. Field descriptor enforces assignment. Not an isolated product-only defect; no production fix in this probe.'
(run/'outputs/compute-boundary.json').write_text(json.dumps(results, indent=2)+'\n')
print(json.dumps(results, indent=2))
