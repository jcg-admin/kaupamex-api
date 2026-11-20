"""Fixtures compartidas de los flujos de venta e inventario.

Todo lo que crea un ``stock.move`` necesita una empresa activa: la fuente
declara ``company_id`` **requerido** con
``default=lambda self: self.env.company`` (``odoo19c: addons/stock/models/
stock_move.py:35-38``), y allá ``env.company`` siempre resuelve porque el
sistema nunca corre sin empresa. Aquí ``get_current_company()`` devuelve
``None`` mientras nadie la active, así que el contexto de prueba la establece
igual que lo haría una petición real.
"""

import pytest

from addons.base.models import ResCompany
from orm.environments import set_current_company
from orm.environments import Environment
from orm.utils import SUPERUSER_ID


@pytest.fixture(autouse=True)
def active_company(db):
    """Activa una empresa durante toda la prueba y la limpia al salir."""
    company = ResCompany.objects.create(code='test_sale', name='Test Sale')
    set_current_company(company.pk)
    yield company
    set_current_company(None)


@pytest.fixture(autouse=True)
def superuser_env(db):
    """≙ ``TransactionCase`` de la fuente, que construye su entorno con
    ``SUPERUSER_ID``: los modelos de producto son ``BaseModel`` y leerlos
    pasa por la ACL. Una prueba que mide la ACL redefine este fixture.
    Precedente: ``tests/unit/fleet/conftest.py``."""
    environment = Environment(None, SUPERUSER_ID, {})
    with environment:
        yield environment
