"""``decimal.precision`` es ``BaseModel``, como en la fuente.

``class DecimalPrecision(models.Model)``
(``odoo19c: odoo/addons/base/models/decimal_precision.py:9``): la ACL sembrada
(``access_decimal_precision_config``, ``group_system``) le aplica a la API de
recordset. ``precision_get`` lee por el gestor, que no filtra por la ACL, como
el SQL crudo de la fuente (``:23-27``).
"""

import models
import pytest

from addons.base.models.decimal_precision import DecimalPrecision

pytestmark = [pytest.mark.unit]


def test_decimal_precision_is_basemodel():
    """Hereda ``BaseModel``, que ya lleva el mixin de carga."""
    assert issubclass(DecimalPrecision, models.BaseModel)
