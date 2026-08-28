"""Contrato de ``AccountAnalyticPlan`` / ``AccountAnalyticApplicability``.

**Por qué la mayoría de estos tests NO usan ``pytest.mark.django_db``.**
No es que falte la tabla —``analytic`` entra en ``LOCAL_APPS`` por el grafo
de addons y tiene sus cinco migraciones aplicadas—, sino que la lógica que
ejercen es **Python pura**: cycle-detection, ``complete_name``/``root`` y
``_get_score`` no tocan la base. Construir árboles en memoria (instancias
sin persistir, con ``pk`` explícito donde la jerarquía lo necesita) los mide
igual y sin el costo de la transacción por test.

> **Corregido:** este docstring afirmaba que el addon *"no está en
> ``INSTALLED_APPS`` ni tiene migración"* y que *"sin tabla, cualquier
> ``.save()``/query real fallaría"*. Las tres afirmaciones son falsas contra
> el árbol: ``LOCAL_APPS`` se **deriva** de ``modules.module_graph``, y
> ``account_analytic_plan`` existe en la base. Era estado heredado que
> desalentaba escribir aquí un test con base, que es justo lo que el control
> de la migración 0005 necesita.
"""
import pytest
from django.core.exceptions import ValidationError

from addons.analytic.models import AccountAnalyticPlan, AccountAnalyticApplicability


def _plan(pk, name, parent=None, **kwargs):
    plan = AccountAnalyticPlan(pk=pk, name=name, **kwargs)
    if parent is not None:
        plan.parent = parent
    return plan


class TestHierarchy:
    def test_complete_name_joins_ancestors_with_slash(self):
        root = _plan(1, 'Marketing')
        child = _plan(2, 'Digital', parent=root)
        grandchild = _plan(3, 'SEM', parent=child)
        assert grandchild.complete_name == 'Marketing / Digital / SEM'

    def test_complete_name_of_root_is_its_own_name(self):
        root = _plan(1, 'Marketing')
        assert root.complete_name == 'Marketing'

    def test_root_property_returns_topmost_ancestor(self):
        root = _plan(1, 'Marketing')
        child = _plan(2, 'Digital', parent=root)
        grandchild = _plan(3, 'SEM', parent=child)
        assert grandchild.root is root
        assert child.root is root
        assert root.root is root

    def test_account_count_and_children_count_default_zero_unsaved(self):
        # Sin pk persistido no hay filas relacionadas reales; el acceso
        # requeriria DB (reverse FK manager) — no se ejercen aquí.
        plan = AccountAnalyticPlan(name='Solo')
        assert plan.name == 'Solo'


class TestHierarchyCycleProtection:
    """``clean()`` -> ``_reject_hierarchy_cycle`` (Odoo no valida esto —
    la referencia depende del ``_parent_store``/UI para evitarlo; aquí es
    una invariante explícita, igual que ``hr.HrDepartment``)."""

    def test_self_as_own_parent_is_rejected(self):
        plan = _plan(1, 'A')
        plan.parent = plan
        with pytest.raises(ValidationError) as exc:
            plan.clean()
        assert exc.value.message_dict['parent'] == ['ANALYTIC_PLAN_CYCLE']

    def test_indirect_cycle_is_rejected(self):
        root = _plan(1, 'A')
        child = _plan(2, 'B', parent=root)
        root.parent = child  # A -> B -> A
        with pytest.raises(ValidationError) as exc:
            child.clean()
        assert exc.value.message_dict['parent'] == ['ANALYTIC_PLAN_CYCLE']

    def test_normal_hierarchy_does_not_raise(self):
        root = _plan(1, 'A')
        child = _plan(2, 'B', parent=root)
        child.clean()  # no debe lanzar


class TestApplicabilityScore:
    """``_get_score`` (odoo19c: analytic_plan.py líneas 446-455) — Python
    puro, portado verbatim salvo el acceso a ``company_id`` (atributo FK
    crudo de Django, misma semántica que el ``id`` booleano de Odoo)."""

    def test_no_kwargs_no_company_gives_zero(self):
        rule = AccountAnalyticApplicability(
            business_domain='general', applicability='mandatory',
        )
        assert rule._get_score() == 0

    def test_company_set_and_company_id_kwarg_adds_half_point(self):
        rule = AccountAnalyticApplicability(
            pk=1, business_domain='general', applicability='mandatory',
            company_id=7,
        )
        assert rule._get_score(company_id=7) == 0.5

    def test_matching_business_domain_adds_one_point(self):
        rule = AccountAnalyticApplicability(
            business_domain='general', applicability='mandatory',
        )
        assert rule._get_score(business_domain='general') == 1

    def test_mismatching_business_domain_subtracts_one_point(self):
        rule = AccountAnalyticApplicability(
            business_domain='general', applicability='mandatory',
        )
        assert rule._get_score(business_domain='other') == -1

    def test_combines_company_bonus_and_domain_match(self):
        rule = AccountAnalyticApplicability(
            pk=1, business_domain='general', applicability='mandatory',
            company_id=7,
        )
        assert rule._get_score(company_id=7, business_domain='general') == 1.5


class TestApplicabilityRequiredFields:
    def test_clean_rejects_missing_business_domain(self):
        rule = AccountAnalyticApplicability(applicability='optional')
        with pytest.raises(ValidationError) as exc:
            rule.clean()
        assert 'business_domain' in exc.value.message_dict

    def test_clean_rejects_missing_applicability(self):
        rule = AccountAnalyticApplicability(business_domain='general')
        with pytest.raises(ValidationError) as exc:
            rule.clean()
        assert 'applicability' in exc.value.message_dict

    def test_clean_passes_with_both_fields(self):
        rule = AccountAnalyticApplicability(
            business_domain='general', applicability='optional',
        )
        rule.clean()  # no debe lanzar
