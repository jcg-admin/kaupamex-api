"""Asignación y caché de etiquetas mediante los consumidores reales."""
import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from addons.base.models.ir_config_parameter import SystemParameter
from addons.base.models.res_partner import ResPartner
from addons.purchase_requisition.models import PurchaseOrderGroup
from orm.environments import context_scope, transaction_scope


pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def test_generic_named_compute_assigns_and_preserves_direct_return():
    parameter = SystemParameter.objects.create(key='fixture.assignment.label', value='x')
    with transaction_scope():
        assert parameter._compute_display_name() == 'fixture.assignment.label'
        assert parameter.__dict__['display_name'] == 'fixture.assignment.label'
        assert parameter.display_name == 'fixture.assignment.label'


def test_generic_nameless_record_assigns_its_technical_identity():
    group = PurchaseOrderGroup.objects.create()
    with transaction_scope():
        assert group.display_name == f'purchase.order.group,{group.pk}'
        assert group.display_name == f'purchase.order.group,{group.pk}'


def test_generic_label_is_invalidated_when_its_name_changes():
    parameter = SystemParameter.objects.create(key='fixture.assignment.before', value='x')
    with transaction_scope():
        assert parameter.display_name == 'fixture.assignment.before'
        parameter.key = 'fixture.assignment.after'
        parameter.save(update_fields=['key'])
        assert parameter.display_name == 'fixture.assignment.after'


def test_explicit_label_wins_until_its_dependency_is_modified():
    parameter = SystemParameter.objects.create(key='fixture.assignment.explicit', value='x')
    with transaction_scope():
        parameter.display_name = 'Etiqueta explícita'
        assert parameter.display_name == 'Etiqueta explícita'
        parameter.key = 'fixture.assignment.changed'
        parameter.save(update_fields=['key'])
        assert parameter.display_name == 'fixture.assignment.changed'


def test_explicit_constructor_label_is_preserved():
    parameter = SystemParameter.objects.create(key='fixture.assignment.constructor', value='x')
    with transaction_scope():
        loaded = SystemParameter(
            pk=parameter.pk, key=parameter.key, value='x',
            display_name='Etiqueta de constructor',
        )
        assert loaded.display_name == 'Etiqueta de constructor'


def test_ordinary_constructor_value_keeps_django_null_semantics():
    parameter = SystemParameter(key='fixture.assignment.null', value=None)
    assert parameter.value is None


def test_ordinary_assignment_defers_sql_until_save():
    parameter = SystemParameter.objects.create(key='fixture.assignment.no-sql', value='x')
    with transaction_scope():
        assert parameter.display_name == 'fixture.assignment.no-sql'
        with CaptureQueriesContext(connection) as queries:
            parameter.key = 'fixture.assignment.saved'
        assert not any(q['sql'].lstrip().upper().startswith(
            ('UPDATE ', 'INSERT ', 'DELETE ')) for q in queries)
        assert SystemParameter.objects.filter(pk=parameter.pk).values_list(
            'key', flat=True).get() == 'fixture.assignment.no-sql'
        parameter.save(update_fields=['key'])
        assert SystemParameter.objects.filter(pk=parameter.pk).values_list(
            'key', flat=True).get() == 'fixture.assignment.saved'


def test_partner_compute_assigns_and_preserves_direct_return():
    partner = ResPartner.objects.create(name='Etiqueta asignada')
    with transaction_scope():
        assert partner._compute_display_name() == 'Etiqueta asignada'
        assert partner.__dict__['display_name'] == 'Etiqueta asignada'
        assert partner.display_name == 'Etiqueta asignada'


def test_partner_same_record_uses_each_context_bucket():
    partner = ResPartner.objects.create(name='Contacto', email='context@example.test')
    with transaction_scope():
        assert partner.display_name == 'Contacto'
        with context_scope(show_email=True):
            assert partner.display_name == 'Contacto <context@example.test>'
            assert partner.display_name == 'Contacto <context@example.test>'
        assert partner.display_name == 'Contacto'
        with context_scope(partner_show_db_id=True):
            assert partner.display_name == f'Contacto ({partner.pk})'
        assert partner.display_name == 'Contacto'


def test_partner_label_is_invalidated_after_email_change():
    partner = ResPartner.objects.create(name='Contacto', email='before@example.test')
    with transaction_scope(), context_scope(show_email=True):
        assert partner.display_name == 'Contacto <before@example.test>'
        partner.email = 'after@example.test'
        partner.save(update_fields=['email'])
        assert partner.display_name == 'Contacto <after@example.test>'


def test_partner_company_visibility_has_its_own_context_bucket():
    company = ResPartner.objects.create(name='Empresa', is_company=True)
    partner = ResPartner.objects.create(name='Contacto', parent=company)
    with transaction_scope():
        assert partner.display_name == 'Empresa, Contacto'
        with context_scope(partner_display_name_hide_company=True):
            assert partner.display_name == 'Contacto'
        assert partner.display_name == 'Empresa, Contacto'


def test_return_without_assignment_is_still_rejected(monkeypatch):
    partner = ResPartner.objects.create(name='No aceptar sólo retorno')
    monkeypatch.setattr(ResPartner, '_compute_display_name', lambda record: 'retorno')
    with transaction_scope(), pytest.raises(ValueError, match='failed to assign'):
        partner.display_name


def test_compute_exception_is_not_silenced(monkeypatch):
    partner = ResPartner.objects.create(name='Error explícito')

    def fail(record):
        raise RuntimeError('fallo del consumidor')

    monkeypatch.setattr(ResPartner, '_compute_display_name', fail)
    with transaction_scope(), pytest.raises(RuntimeError, match='fallo del consumidor'):
        partner.display_name
