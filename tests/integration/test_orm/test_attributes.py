"""Porte de ``odoo19c: odoo/addons/test_orm/tests/test_attributes.py``.

Revisión de referencia: ``odoo-tools@abe4040ec1``. Un registro de la fuente
no admite atributos que su modelo no declare: ``BaseModel`` declara
``__slots__`` (``odoo19c: odoo/orm/models.py:362``) y sin ``__dict__`` la
asignación de un nombre desconocido levanta ``AttributeError``.

**Mitad roja persistida.** ``BaseModel.__setattr__`` ya rechaza el nombre
sobre una fila y sobre el recordset nativo
(``tests/unit/orm/test_base_model_recordset.py``), pero ``create`` todavía
devuelve un ``QuerySet`` (``orm.utils.browse``), y el ``QuerySet`` admite
cualquier atributo. Sucesor: TASK-API-0397, H-API-1123. ``strict=True`` hace
que la prueba falle el día que el contrato se cumpla, y entonces se retira
la marca.
"""

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


@pytest.mark.xfail(strict=True, reason='create devuelve QuerySet: H-API-1123')
def test_we_cannot_add_attributes(env):
    instance = env['test_orm.category'].create({'name': 'Foo'})

    with pytest.raises(AttributeError):
        instance.unknown = 42
