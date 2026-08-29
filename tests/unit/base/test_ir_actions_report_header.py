"""La cabecera de ``ir.actions.report``: atributos de clase y campos derivados.

Cubre el bloque de declaración que el porte de
``odoo19c: odoo/addons/base/models/ir_actions_report.py:157-229`` trae: los
seis atributos de clase, el ``model_id`` sin columna con su ``_compute`` y su
``_search``, y la lista de campos legibles.

*Métrica:* atributos declarados en la clase y conducta de los tres métodos de
la cabecera, contra la fuente.
*Ciega a:* que el valor de ``_order`` gobierne el orden real de una consulta —
eso lo decide ``Meta.ordering``, y el caso que los compara sólo comprueba que
los dos digan lo mismo, no que la base los obedezca.
"""

import pytest

from addons.base.models.ir_actions_report import IrActionsReport
from addons.base.models.ir_model import IrModel
from addons.base.models.res_groups import ResGroups
from orm.domains import Domain

pytestmark = pytest.mark.django_db


class TestTheClassAttributes:
    """Los seis que la fuente declara, verbatim."""

    def test_the_six_attributes_carry_the_value_of_the_source(self):
        assert IrActionsReport._name == 'ir.actions.report'
        assert IrActionsReport._description == 'Report Action'
        assert IrActionsReport._inherit == ['ir.actions.actions']
        assert IrActionsReport._table == 'ir_act_report_xml'
        assert IrActionsReport._order == 'name, id'
        assert IrActionsReport._allow_sudo_commands is False

    def test_the_table_of_the_source_and_the_one_of_django_agree(self):
        """``_table`` no sustituye a ``Meta.db_table``: conviven y coinciden."""
        assert IrActionsReport._table == IrActionsReport._meta.db_table

    def test_the_order_of_the_source_and_the_one_of_django_agree(self):
        assert IrActionsReport._order == ', '.join(
            IrActionsReport._meta.ordering)


class TestTheDerivedModelRow:
    """``model_id`` — la fila de ``ir.model``, sin columna."""

    def test_it_has_no_column(self):
        """Un ``compute`` sin ``store`` no persiste: la fuente lo promete."""
        columnas = {f.name for f in IrActionsReport._meta.get_fields()}
        assert 'model_id' not in columnas

    def test_it_resolves_the_row_of_the_technical_name(self):
        row = IrModel.objects.create(model='x_report_probe', name='Probe')
        report = IrActionsReport(name='R', model='x_report_probe')
        assert report.model_id == row

    def test_without_a_model_it_resolves_to_nothing(self):
        assert IrActionsReport(name='R', model='').model_id is None

    def test_an_unknown_model_resolves_to_nothing(self):
        assert IrActionsReport(name='R', model='x_no_existe').model_id is None


class TestTheSearchOverTheDerivedField:
    """``_search_model_id`` — traduce a una búsqueda por ``model``."""

    def test_a_negative_operator_is_left_to_the_general_path(self):
        for operator in Domain.NEGATIVE_OPERATORS:
            assert IrActionsReport._search_model_id(operator, 'x') is NotImplemented

    def test_an_id_narrows_to_the_technical_name_of_that_row(self):
        row = IrModel.objects.create(model='x_report_by_id', name='By id')
        domain = IrActionsReport._search_model_id('=', row.pk)
        assert isinstance(domain, Domain)
        assert 'x_report_by_id' in str(domain)

    def test_a_list_of_ids_narrows_to_their_names(self):
        uno = IrModel.objects.create(model='x_report_in_one', name='One')
        dos = IrModel.objects.create(model='x_report_in_two', name='Two')
        domain = IrActionsReport._search_model_id('in', [uno.pk, dos.pk])
        texto = str(domain)
        assert 'x_report_in_one' in texto and 'x_report_in_two' in texto

    def test_nothing_matching_gives_an_empty_narrowing(self):
        domain = IrActionsReport._search_model_id('=', 10 ** 9)
        assert str(domain).count('x_') == 0


class TestTheReadableFields:
    """``_get_readable_fields`` — la unión que la fuente declara."""

    def test_it_adds_the_seven_names_of_the_source(self):
        readable = IrActionsReport(name='R', model='x')._get_readable_fields()
        assert {'report_name', 'report_type', 'target', 'context', 'data',
                'close_on_report_download', 'domain'} <= readable

    def test_it_keeps_what_the_parent_declares(self):
        report = IrActionsReport(name='R', model='x')
        assert super(IrActionsReport, report)._get_readable_fields() <= \
            report._get_readable_fields()


class TestTheTwoRelationalSymbols:
    """``group_ids`` y ``paperformat_id`` — forma C: símbolo y columna fieles."""

    def test_the_symbols_are_the_ones_of_the_source(self):
        nombres = {f.name for f in IrActionsReport._meta.get_fields()}
        assert 'group_ids' in nombres and 'paperformat_id' in nombres
        assert 'groups' not in nombres and 'paperformat' not in nombres

    def test_the_foreign_key_column_did_not_move(self):
        field = IrActionsReport._meta.get_field('paperformat_id')
        assert field.db_column == 'paperformat_id'

    def test_the_join_table_of_the_groups_did_not_move(self):
        field = IrActionsReport._meta.get_field('group_ids')
        assert field.remote_field.through._meta.db_table == 'res_groups_report_rel'


class TestTheReportsApplicableToAModel:
    """``valid_reports_for`` — el camino que nombraba el símbolo viejo.

    El renombre de ``groups`` a ``group_ids`` dejó atrás un
    ``prefetch_related('groups')`` y **la suite siguió verde**: ningún caso
    ejercía este método, así que el nombre muerto no tenía quien lo delatara.
    Es el sub-patrón D de ``metrica-decide-la-conclusion.md`` — un verde que no
    discrimina *"el código funciona"* de *"nadie lo llama"*.

    Estos casos son el control que faltaba, y se midieron con el nombre viejo
    puesto de vuelta: **2 failed, 17 passed**. Caen los dos que llegan a la
    consulta; sobrevive ``test_another_model_does_not_bring_it``, porque su
    filtro por modelo devuelve vacío antes de tocar el ``prefetch_related``.
    Ese tercero mide otra cosa —que un reporte ajeno no se cuele— y está bien
    que la mida; lo que no valdría es no saberlo.
    """

    def test_a_report_without_groups_is_applicable_to_everyone(self):
        IrActionsReport.objects.create(
            name='Libre', model='x_applicable', report_name='libre')
        assert len(IrActionsReport.valid_reports_for('x_applicable')) == 1

    def test_a_report_with_groups_needs_one_of_them(self):
        group = ResGroups.objects.create(name='Impresores')
        report = IrActionsReport.objects.create(
            name='Restringido', model='x_restricted', report_name='restringido')
        report.group_ids.add(group)

        assert IrActionsReport.valid_reports_for('x_restricted') == []
        assert len(IrActionsReport.valid_reports_for(
            'x_restricted', groups=[group])) == 1

    def test_another_model_does_not_bring_it(self):
        IrActionsReport.objects.create(
            name='Ajeno', model='x_other', report_name='ajeno')
        assert IrActionsReport.valid_reports_for('x_applicable') == []
