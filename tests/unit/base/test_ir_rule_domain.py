"""``ir.rule`` devuelve ``Domain``, como la referencia.

≙ ``_compute_domain`` (``odoo19c: odoo/addons/base/models/ir_rule.py:141-173``)
y la regla de ``:164``. Diseño en ``designs/ir-rule-domain.md`` del Workbench.

*Métrica:* el tipo devuelto y las filas que el mismo ``Domain`` deja pasar por
el compilador de Django y por el de SQL.
*Ciega a:* la memoización, que cubren las pruebas de ``test_ir_rule.py``.
"""
import pytest

from addons.base.models import ResCompany
from addons.base.models.ir_rule import IrRule
from addons.base.models.res_groups import ResGroups
from orm.domains import Domain

pytestmark = pytest.mark.django_db

MODEL = 'base.ResCompany'
_CODES = ('alfa', 'beta', 'gama')


@pytest.fixture
def companies(db):
    for code in _CODES:
        ResCompany.objects.create(code=code, name=code.title())


def _rule(name, domain='', groups=()):
    rule = IrRule.objects.create(name=name, model_name=MODEL,
                                 domain_force=domain)
    if groups:
        rule.groups.set(groups)
    return rule


def _codes_by_django(domain):
    return set(ResCompany.objects.filter(code__in=_CODES)
               .filter(domain._to_q(ResCompany))
               .values_list('code', flat=True))


def test_without_rules_the_domain_is_true(companies):
    domain = IrRule._compute_domain(MODEL, mode='read')
    assert isinstance(domain, Domain)
    assert domain.is_true()


def test_an_empty_rule_builds_true(companies):
    rule = _rule('empty')
    assert rule._build_domain({}) == Domain.TRUE


def test_a_rule_builds_its_domain(companies):
    rule = _rule('no gama', "[('code', '!=', 'gama')]")
    assert rule._build_domain({}) == Domain([('code', '!=', 'gama')])


def test_globals_are_and_and_groups_are_or(companies):
    first = ResGroups.objects.create(name='g1')
    second = ResGroups.objects.create(name='g2')
    _rule('global', "[('code', '!=', 'gama')]")
    _rule('alfa', "[('code', '=', 'alfa')]", groups=[first])
    _rule('gama', "[('code', '=', 'gama')]", groups=[second])
    domain = IrRule._compute_domain(MODEL, mode='read',
                                    group_ids=(first.pk, second.pk))
    assert isinstance(domain, Domain)
    assert _codes_by_django(domain) == {'alfa'}
