"""``BaseModel._get_base_lang`` — ≙ ``odoo19c: odoo/orm/models.py:3704-3707``.
TASK-API-0485.

El idioma base de un registro es ``en_US`` salvo que un addon lo redefina
(``website`` lo hace), y la pregunta es sobre UN registro: ``ensure_one``.
"""
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def test_get_base_lang_defaults_to_us_english(env):
    record = env['test_orm.foo'].create({'value1': 1})
    assert record._get_base_lang() == 'en_US'


def test_get_base_lang_needs_one_record(env):
    one, two = env['test_orm.foo'].create([{'value1': 1}, {'value1': 2}])
    with pytest.raises(ValueError, match='Expected singleton'):
        (one | two)._get_base_lang()
