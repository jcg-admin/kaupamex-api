"""``ir.actions.server.history`` es ``BaseModel``, como en la fuente.

``class IrActionsServerHistory(models.Model)``
(``odoo19c: odoo/addons/base/models/ir_actions.py:503``): todo modelo con
``_name`` es ``BaseModel``, así que la ACL sembrada
(``access_ir_actions_server_history_group_system``) y la API de recordset le
aplican.
"""

import models
import pytest

from addons.base.models.ir_actions import IrActionsServerHistory

pytestmark = [pytest.mark.unit]


def test_server_action_history_is_basemodel():
    """Hereda ``BaseModel`` además de las columnas de auditoría."""
    assert issubclass(IrActionsServerHistory, models.BaseModel)
