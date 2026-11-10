"""Contrato de TASK-GEN-0060 (b): ordenar por el texto del idioma activo.

Referencia: odoo-tools ``abe4040ec1``. ``_order_field_to_sql``
(``odoo19c: odoo/orm/models.py:5262-5322``) ordena por ``Field.to_sql``, que
para un campo traducible es el texto del idioma con respaldo
(``fields_textual.py:394-402``). ``hr.skill.type`` declara
``_order = "sequence, name"``
(``odoo19c: hr_skills/models/hr_skill_type.py:12``)
y ``_default_skill_type_id`` toma el primero de ese orden
(``hr_skills/models/hr_individual_skill_mixin.py:41-45``).

Sujeto: dos tipos con la misma secuencia y el orden de sus nombres invertido
entre ``en_US`` y ``es_MX``. Diseño: ``designs/translate-jsonb-storage.md``,
«Segunda unidad».
"""
import pytest
from django.db.migrations.writer import MigrationWriter

from addons.base.models import ResLang
from addons.hr_skills.models import HrSkillType
from addons.hr_skills.models.hr_individual_skill_mixin import (
    _default_skill_type,
)
from orm import registry
from orm.environments import context_scope
from orm.fields_textual import TranslatedValue
from orm.models import order_to_django

pytestmark = pytest.mark.django_db


@pytest.fixture
def two_types():
    """``Alpha``/``Beta`` en inglés, ``Zeta``/``Eta`` en español."""
    lang = ResLang.objects.get(code='es_MX')
    lang.active = True
    lang.save()
    HrSkillType.objects.all().delete()
    first = HrSkillType.objects.create(name='Alpha', sequence=1)
    second = HrSkillType.objects.create(name='Beta', sequence=1)
    first.update_field_translations('name', {'es_MX': 'Zeta'})
    second.update_field_translations('name', {'es_MX': 'Eta'})
    yield first, second
    registry.clear_cache('stable')


def test_default_ordering_follows_the_active_language(two_types):
    first, second = two_types
    assert list(HrSkillType.objects.all()) == [first, second]
    with context_scope(lang='es_MX'):
        assert list(HrSkillType.objects.all()) == [second, first]


def test_order_to_django_follows_the_active_language(two_types):
    first, second = two_types
    with context_scope(lang='es_MX'):
        rows = HrSkillType.objects.order_by(
            *order_to_django(HrSkillType, 'sequence, name'))
        assert list(rows) == [second, first]


def test_default_skill_type_takes_the_first_in_the_active_language(
        two_types):
    first, second = two_types
    assert _default_skill_type() == first.pk
    with context_scope(lang='es_MX'):
        assert _default_skill_type() == second.pk


def test_translated_value_survives_a_migration_round_trip():
    expression = TranslatedValue('name').asc()
    text, imports = MigrationWriter.serialize(expression)
    assert 'orm.fields_textual.TranslatedValue' in text
    namespace = {}
    exec('\n'.join(sorted(imports)), namespace)
    assert eval(text, namespace) == expression
