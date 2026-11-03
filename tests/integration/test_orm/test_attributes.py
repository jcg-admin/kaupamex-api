"""Porte de ``odoo19c: odoo/addons/test_orm/tests/test_attributes.py``.

Revisión de referencia: ``odoo-tools@abe4040ec1``. Un registro de la fuente
no admite atributos que su modelo no declare: ``BaseModel`` declara
``__slots__`` (``odoo19c: odoo/orm/models.py:362``) y sin ``__dict__`` la
asignación de un nombre desconocido levanta ``AttributeError``.

``create`` entrega el recordset de ``BaseModel`` a los modelos que derivan
de él (``DefaultGetMixin._create_result``), y ``BaseModel.__setattr__`` rechaza
el nombre que el modelo no declara.
"""

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def test_we_cannot_add_attributes(env):
    instance = env['test_orm.category'].create({'name': 'Foo'})

    with pytest.raises(AttributeError):
        instance.unknown = 42
