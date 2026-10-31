"""Contrato vigente tras0417: la fachada construye un Field y compute asigna.

Los nueve casos históricos de0415 se conservan por responsabilidad: despacho,
valores distintos, campo sin columna, invocable, precedencias y defaults.
Las expectativas de fábrica NonStored y retorno de compute pertenecían a la
adaptación anterior; Odoo19Community exige asignar (Field.__get__:1736-1763).
La historia y el rojo previo permanecen en Git y en la evidencia AS IS.
"""
import pytest
from django.db import models
from django.apps import apps
from orm.models import DefaultGetMixin
from orm.environments import transaction_scope

import fields
from orm.fields import FieldDescriptor


class ComputeDispatchProbe(DefaultGetMixin, models.Model):
    label = fields.Char(compute='_compute_label')
    callable_label = fields.Char(
        compute=lambda record: setattr(record, 'callable_label', 'por invocable'))
    plain_label = fields.Char(store=False, default='del default')
    empty_label = fields.Char(store=False)
    company = fields.Many2one('base.ResCompany', on_delete=models.DO_NOTHING,
                             null=True, related_name='+')
    company_label = fields.Char(related='company_id.code', compute='_compute_label')

    class Meta:
        app_label = 'base'
        managed = False

    def _compute_label(self):
        self.label = 'calculado'


class TestTheDeclaredComputeIsDispatched:
    def test_the_read_returns_what_the_compute_produces(self):
        assert ComputeDispatchProbe().label == 'calculado'

    @pytest.mark.parametrize('produced', ['uno', 'otro distinto'])
    def test_the_value_tracks_the_compute_and_not_a_constant(self, produced, monkeypatch):
        monkeypatch.setattr(ComputeDispatchProbe, '_compute_label',
                            lambda record: setattr(record, 'label', produced))
        assert ComputeDispatchProbe().label == produced

    def test_the_facade_routes_a_bare_compute_to_the_descriptor(self):
        field = ComputeDispatchProbe._meta.get_field('label')
        assert field.store is False
        assert field in ComputeDispatchProbe._meta.private_fields
        assert isinstance(ComputeDispatchProbe.__dict__['label'], FieldDescriptor)
        assert isinstance(field, models.CharField)

    def test_a_callable_compute_is_dispatched_too(self):
        assert ComputeDispatchProbe().callable_label == 'por invocable'


class TestTheOtherTwoBranchesStillWin:
    def test_the_written_value_beats_the_compute(self):
        probe = ComputeDispatchProbe()
        probe.label = 'escrito a mano'
        assert probe.label == 'escrito a mano'

    def test_related_beats_the_compute(self):
        assert ComputeDispatchProbe().company_label != 'calculado'


@pytest.fixture
def no_user_defaults(monkeypatch):
    # Estos casos aíslan el default del campo, no la persistencia de ir.default.
    model = apps.get_model('base', 'IrDefault')
    monkeypatch.setattr(model, '_get_model_defaults', lambda *args, **kwargs: {})
    with transaction_scope():
        yield


@pytest.mark.usefixtures('no_user_defaults')
class TestWhatTheBranchDoesNotChange:
    def test_a_field_without_compute_still_reads_its_default(self):
        assert ComputeDispatchProbe(pk=71).plain_label == 'del default'

    def test_a_field_with_neither_reads_false(self):
        assert ComputeDispatchProbe(pk=72).empty_label is False
