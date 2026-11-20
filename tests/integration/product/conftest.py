"""Las pruebas de ``product`` corren como superusuario.

≙ ``TransactionCase`` de la fuente, que construye su entorno con
``SUPERUSER_ID``. Desde que ``product.attribute.value`` es ``BaseModel``,
leer sus campos pasa por la ACL de la fuente
(``odoo19c: addons/product/security/ir.model.access.csv``), que sólo da
permisos a ``base.group_user`` y a ``group_product_manager``. Una prueba que
mide la ACL redefine este fixture. Precedente:
``tests/unit/fleet/conftest.py``.
"""
import pytest

from orm.environments import Environment
from orm.utils import SUPERUSER_ID


@pytest.fixture(autouse=True)
def superuser_env(db):
    environment = Environment(None, SUPERUSER_ID, {})
    with environment:
        yield environment
