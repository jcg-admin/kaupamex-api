"""``ir.model.inherit`` es ``BaseModel``, como en la fuente.

``class IrModelInherit(models.Model)``
(``odoo19c: odoo/addons/base/models/ir_model.py:1422``): todo modelo con
``_name`` es ``BaseModel``. Su ACL es la fila ``access_ir_model_inherit`` sin
grupo y con los cuatro permisos a cero (``ir.model.access.csv:13``): nadie lo
lee ni lo escribe salvo el propio registro, con privilegio.
"""

import models
import pytest

from addons.base.models.ir_model import IrModelInherit

pytestmark = [pytest.mark.unit]


def test_model_inherit_is_basemodel():
    """Hereda ``BaseModel``, que ya lleva el mixin de carga."""
    assert issubclass(IrModelInherit, models.BaseModel)
