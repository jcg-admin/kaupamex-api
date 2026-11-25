"""``report.paperformat`` e ``ir.asset`` son ``BaseModel``, como en la fuente.

``class ReportPaperformat(models.Model)``
(``odoo19c: odoo/addons/base/models/report_paperformat.py:165``) y
``class IrAsset(models.Model)``
(``odoo19c: odoo/addons/base/models/ir_asset.py:51``):
todo modelo con ``_name`` es ``BaseModel``, así que la ACL sembrada
(``paperformat_access_*``, ``access_ir_asset_group_system``) y la API de
recordset les aplican.
"""

import models
import pytest

from addons.base.models.ir_asset import IrAsset
from addons.base.models.report_paperformat import ReportPaperformat

pytestmark = [pytest.mark.unit]


@pytest.mark.parametrize('model', [ReportPaperformat, IrAsset])
def test_paperformat_and_asset_are_basemodel(model):
    """Cada uno hereda ``BaseModel``, no sólo el mixin de carga."""
    assert issubclass(model, models.BaseModel)
