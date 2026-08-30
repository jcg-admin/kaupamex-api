"""Tests — las restricciones, guardas y consultas de ``ir.model.fields``.

Contrato adaptado de ``odoo19c: odoo/addons/base/models/ir_model.py:588-848``
(computes, restricciones, onchange y resolucion), ``:891-978``
(``_prepare_update``) y ``:1020-1152`` (``create`` / ``write``).

Lo que la fuente decide, y es lo que estos casos fijan
======================================================

Una fila de ``ir.model.fields`` describe un campo, y la fuente cierra por
restriccion cada forma de describirlo mal: un dominio que no evalua, un
Many2one requerido que declara ``set null``, un campo relacionado cuyo tipo no
coincide, una dependencia sobre un campo que no existe.

Y cierra por guarda las tres cosas que no se cambian sobre un campo ya
escrito: su estado base, su modelo y su tipo. La ultima con su propio consejo
— *"Please drop it and create it again!"*.

Que haria fallar a cada control
--------------------------------

``TestCheckOnDeleteRequiredM2o.test_a_required_m2o_cannot_set_null``
    El eje: la politica contradice a la obligatoriedad. Lo haria fallar no
    cruzar los tres campos.

``TestCheckDepends.test_a_non_relational_field_in_the_middle_is_refused``
    CONTROL: sin el, una comprobacion que solo mirara el ultimo tramo pasaria
    los demas casos de dependencias.

``TestWriteGuard.test_the_type_of_a_field_cannot_change``
    CONTROL de la tercera guarda, la que la fuente acompana de su consejo.

``TestPrepareUpdate.test_a_module_column_cannot_be_removed``
    CONTROL de la guarda de borrado, hermana de ``IrModel._unlink_if_manual``.

``TestGetIds.test_a_field_created_after_a_lookup_is_found``
    CONTROL de la invalidacion: sin ella, ``_get_ids`` memoriza el mapa y un
    campo nuevo no se resuelve por nombre.
"""
import pytest

from addons.base.models.ir_model import IrModel, IrModelFields
from django.core.exceptions import ValidationError
from exceptions import UserError

pytestmark = pytest.mark.integration

MODEL_LABEL = 'base.IrModelData'


def _model_row(label=MODEL_LABEL):
    row, _ = IrModel.objects.get_or_create(
        model=label, defaults={'name': 'Dato de modelo'})
    return row


def _field(name='x_prueba', **extra):
    valores = {
        'model': MODEL_LABEL, 'name': name, 'field_description': 'Prueba',
        'ttype': 'char', 'state': 'manual', 'model_id': _model_row(),
    }
    valores.update(extra)
    return IrModelFields.objects.create(**valores)


class TestCheckName:
    """≙ ``_check_name`` (``odoo19c: :641-647``)."""

    def test_a_name_with_a_dash_is_refused(self, db):
        row = IrModelFields(model=MODEL_LABEL, name='con-guion')
        with pytest.raises(ValidationError, match='guiones bajos'):
            row._check_name()

    def test_a_plain_identifier_is_accepted(self, db):
        IrModelFields(model=MODEL_LABEL, name='x_bien')._check_name()


class TestCheckDomain:
    """≙ ``_check_domain`` (``odoo19c: :631-638``)."""

    def test_a_domain_that_does_not_evaluate_is_refused(self, db):
        row = IrModelFields(model=MODEL_LABEL, name='x_a', domain='[(')
        with pytest.raises(Exception):
            row._check_domain()

    def test_an_empty_domain_is_accepted(self, db):
        IrModelFields(model=MODEL_LABEL, name='x_a', domain='')._check_domain()


class TestCheckOnDeleteRequiredM2o:
    """≙ ``_check_on_delete_required_m2o`` (``odoo19c: :835-841``)."""

    def test_a_required_m2o_cannot_set_null(self, db):
        row = IrModelFields(
            model=MODEL_LABEL, name='x_a', ttype='many2one', required=True,
            on_delete='set null')
        with pytest.raises(ValidationError, match='set null'):
            row._check_on_delete_required_m2o()

    def test_a_required_m2o_with_cascade_is_accepted(self, db):
        IrModelFields(
            model=MODEL_LABEL, name='x_a', ttype='many2one', required=True,
            on_delete='cascade')._check_on_delete_required_m2o()

    def test_a_non_required_m2o_may_set_null(self, db):
        IrModelFields(
            model=MODEL_LABEL, name='x_a', ttype='many2one', required=False,
            on_delete='set null')._check_on_delete_required_m2o()


class TestCheckRelation:
    """≙ ``_check_relation`` (``odoo19c: :728-731``)."""

    def test_an_unknown_comodel_is_refused(self, db):
        row = IrModelFields(
            model=MODEL_LABEL, name='x_a', state='manual',
            relation='base.NoExiste')
        with pytest.raises(ValidationError, match='desconocido'):
            row._check_relation()

    def test_a_base_field_is_not_checked(self, db):
        IrModelFields(
            model=MODEL_LABEL, name='x_a', state='base',
            relation='base.NoExiste')._check_relation()


class TestCheckDepends:
    """≙ ``_check_depends`` (``odoo19c: :734-761``)."""

    def test_an_empty_dependency_is_refused(self, db):
        row = IrModelFields(model=MODEL_LABEL, name='x_a', depends='name,')
        with pytest.raises(UserError, match='vacía'):
            row._check_depends()

    def test_depending_on_id_is_refused(self, db):
        row = IrModelFields(model=MODEL_LABEL, name='x_a', depends='id')
        with pytest.raises(UserError, match="'id'"):
            row._check_depends()

    def test_an_unknown_field_is_refused(self, db):
        row = IrModelFields(model=MODEL_LABEL, name='x_a', depends='no_existe')
        with pytest.raises(UserError, match='no_existe'):
            row._check_depends()

    def test_a_non_relational_field_in_the_middle_is_refused(self, db):
        row = IrModelFields(model=MODEL_LABEL, name='x_a', depends='name.algo')
        with pytest.raises(UserError, match='no relacional'):
            row._check_depends()

    def test_a_real_field_is_accepted(self, db):
        IrModelFields(model=MODEL_LABEL, name='x_a',
                      depends='name')._check_depends()


class TestGetIds:
    """≙ ``_get_ids`` y ``_get`` (``odoo19c: :843-854``)."""

    def test_a_field_created_after_a_lookup_is_found(self, db):
        assert 'x_tardio' not in IrModelFields._get_ids(MODEL_LABEL)
        _field('x_tardio')
        assert 'x_tardio' in IrModelFields._get_ids(MODEL_LABEL)

    def test_get_returns_none_for_an_unknown_name(self, db):
        assert IrModelFields._get(MODEL_LABEL, 'x_no_existe') is None


class TestGetFieldString:
    """≙ ``get_field_string`` y ``get_field_help`` (``odoo19c: :1361-1384``)."""

    def test_it_maps_each_name_to_its_label(self, db):
        _field('x_etiquetado', field_description='Etiquetado')
        assert IrModelFields.get_field_string(
            MODEL_LABEL)['x_etiquetado'] == 'Etiquetado'

    def test_the_help_map_carries_the_help_text(self, db):
        _field('x_con_ayuda', help='Una ayuda')
        assert IrModelFields.get_field_help(
            MODEL_LABEL)['x_con_ayuda'] == 'Una ayuda'


class TestCustomMany2manyNames:
    """≙ ``_custom_many2many_names`` (``odoo19c: :793-801``)."""

    def test_two_different_models_give_a_column_per_table(self, db):
        table, first, second = IrModelFields._custom_many2many_names(
            'base.IrModelData', 'base.IrModel')
        assert table.startswith('x_') and table.endswith('_rel')
        assert first.endswith('_id') and second.endswith('_id')

    def test_the_reflexive_case_gives_id1_and_id2(self, db):
        _table, first, second = IrModelFields._custom_many2many_names(
            'base.IrModelData', 'base.IrModelData')
        assert (first, second) == ('id1', 'id2')


class TestWriteGuard:
    """≙ las guardas de ``write`` (``odoo19c: :1074-1088``)."""

    def test_a_base_field_is_not_altered_by_this_path(self, db):
        row = _field('x_base')
        IrModelFields.objects.filter(pk=row.pk).update(state='base')
        row.refresh_from_db()
        row.field_description = 'Otra'
        with pytest.raises(UserError, match='campo base'):
            row.save()

    def test_the_model_of_a_field_cannot_change(self, db):
        row = _field('x_mueve')
        other, _ = IrModel.objects.get_or_create(
            model='base.IrModel', defaults={'name': 'Modelo'})
        row.model_id = other
        with pytest.raises(UserError, match='modelo'):
            row.save()

    def test_the_type_of_a_field_cannot_change(self, db):
        row = _field('x_tipo')
        row.ttype = 'text'
        with pytest.raises(UserError, match='tipo'):
            row.save()

    def test_a_label_change_is_allowed(self, db):
        row = _field('x_etiqueta')
        row.field_description = 'Otra etiqueta'
        row.save()
        row.refresh_from_db()
        assert row.field_description == 'Otra etiqueta'


class TestCreateGuard:
    """≙ las guardas de ``create`` (``odoo19c: :1036-1050``)."""

    def test_an_unknown_comodel_is_refused(self, db):
        with pytest.raises(UserError, match='no existe'):
            _field('x_rel', ttype='many2one', relation='base.NoExiste')

    def test_a_stored_one2many_without_its_inverse_is_refused(self, db):
        with pytest.raises(UserError, match='Many2one'):
            _field('x_hijos', ttype='one2many', relation=MODEL_LABEL,
                   relation_field='x_padre')


class TestPrepareUpdate:
    """≙ ``_prepare_update`` (``odoo19c: :891-978``)."""

    def test_a_module_column_cannot_be_removed(self, db):
        row = _field('x_de_modulo')
        IrModelFields.objects.filter(pk=row.pk).update(state='base')
        row.refresh_from_db()
        with pytest.raises(UserError, match='datos de módulo'):
            row.delete()

    def test_a_manual_column_is_removed(self, db):
        row = _field('x_efimero')
        row.delete()
        assert not IrModelFields.objects.filter(name='x_efimero').exists()


class TestComputeCopied:
    """≙ ``_compute_copied`` (``odoo19c: :617-619``)."""

    @pytest.mark.parametrize('extra, expected', [
        ({}, True),
        ({'ttype': 'one2many'}, False),
        ({'related': 'partner_id.name'}, False),
        ({'compute': 'algo'}, False),
    ])
    def test_a_derived_field_is_not_copied(self, db, extra, expected):
        valores = {'ttype': 'char'}
        valores.update(extra)
        row = IrModelFields(model=MODEL_LABEL, name='x_a', **valores)
        assert row._compute_copied() is expected


class TestOnchange:
    """≙ los cinco ``_onchange_*`` (``odoo19c: :710-832``)."""

    def test_declaring_a_compute_marks_the_field_readonly(self, db):
        row = IrModelFields(model=MODEL_LABEL, name='x_a', compute='algo')
        row._onchange_compute()
        assert row.readonly is True

    def test_a_type_that_is_not_many2many_clears_the_table_names(self, db):
        row = IrModelFields(model=MODEL_LABEL, name='x_a', ttype='char',
                            relation_table='algo', column1='a', column2='b')
        row._onchange_ttype()
        assert (row.relation_table, row.column1, row.column2) == ('', '', '')

    def test_an_unknown_comodel_comes_back_as_a_warning(self, db):
        row = IrModelFields(model=MODEL_LABEL, name='x_a', state='manual',
                            relation='base.NoExiste')
        assert 'warning' in row._onchange_relation()
