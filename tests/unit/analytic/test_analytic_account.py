"""Contrato de ``AccountAnalyticAccount``.

Ver el docstring de ``test_analytic_plan.py`` para por qué estos tests NO
usan ``pytest.mark.django_db`` — el addon no tiene tabla todavía. Se cubren
``__str__`` (``_compute_display_name`` simplificado) y los "related" sin
columna (``root_plan``, ``color``); ``credit``/``debit``/``balance``
requieren el reverse manager ``lines`` (query real) y quedan fuera de este
corte, igual que ``clean()`` (usa ``self.lines.exclude(...)``).
"""
from addons.analytic.models import AccountAnalyticAccount, AccountAnalyticPlan
from addons.base.models import ResPartner


def _plan(pk, name, color=1):
    return AccountAnalyticPlan(pk=pk, name=name, color=color)


class TestDisplayName:
    """``__str__`` — fiel a ``_compute_display_name`` (odoo19c: líneas
    104-112), simplificado a ``partner.name`` (ver docstring de
    ``models/analytic_account.py``)."""

    def test_name_only(self):
        acct = AccountAnalyticAccount(name='Campaña Q3', plan=_plan(1, 'Marketing'))
        assert str(acct) == 'Campaña Q3'

    def test_with_code_prefixes_name(self):
        acct = AccountAnalyticAccount(
            name='Campaña Q3', code='CMP-Q3', plan=_plan(1, 'Marketing'),
        )
        assert str(acct) == '[CMP-Q3] Campaña Q3'

    def test_with_partner_appends_partner_name(self):
        acct = AccountAnalyticAccount(
            name='Campaña Q3', plan=_plan(1, 'Marketing'),
            partner=ResPartner(pk=1, name='Acme Corp'),
        )
        assert str(acct) == 'Campaña Q3 - Acme Corp'

    def test_with_code_and_partner(self):
        acct = AccountAnalyticAccount(
            name='Campaña Q3', code='CMP-Q3', plan=_plan(1, 'Marketing'),
            partner=ResPartner(pk=1, name='Acme Corp'),
        )
        assert str(acct) == '[CMP-Q3] Campaña Q3 - Acme Corp'


class TestRelatedProperties:
    """``root_plan``/``color`` — Odoo ``related=`` sin columna propia
    (``@property``, ver docstring del módulo)."""

    def test_root_plan_of_a_child_plan_account(self):
        root = _plan(1, 'Marketing', color=3)
        child = AccountAnalyticPlan(pk=2, name='Digital', color=5)
        child.parent = root
        acct = AccountAnalyticAccount(name='Ads', plan=child)
        assert acct.root_plan is root

    def test_color_delegates_to_plan_color(self):
        plan = _plan(1, 'Marketing', color=7)
        acct = AccountAnalyticAccount(name='Ads', plan=plan)
        assert acct.color == 7
