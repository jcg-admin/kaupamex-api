"""El gate de ADR-029 mide las cuatro formas y no confunde N con B (#141).

Mismo principio que ``test_check_porte_completo.py`` y
``test_check_model_class_attributes.py``: un gate se prueba contra un
**positivo conocido del repo**, no contra un incumplidor fabricado por quien
escribió el patrón — un fabricado hereda el encuadre de su autor y confirma el
instrumento en vez de ponerlo a prueba.

Los positivos que este archivo usa existen en el árbol y los nombra el propio
gate al correr:

- forma **A** — ``addons/account/models/account_account.py::AccountAccount.company``
  (símbolo divergente, columna fiel derivada).
- forma **C** — ``addons/base_automation/models/base_automation.py::BaseAutomation.model_id``
  (símbolo fiel + ``db_column`` con ese mismo nombre).
- forma **N** — ``properties_base_definition_id``, un ``store=False`` que **no
  tiene el eje de columna**: clasificarlo como B rotularía de defecto un campo
  al que no se le puede medir lo que B mide (sub-patrón A de
  ``metrica-decide-la-conclusion.md``).

Qué haría fallar a estos casos
==============================

Que el gate dejara de reconocer ``fields.Many2one`` —nuestro despachador— y
sólo viera ``models.ForeignKey``: el alcance medido se desploma y el conteo de
la forma A cae con él. Ése fue el defecto real del primer instrumento, que
midió 111 declaraciones donde hay 747.
"""
import importlib.util
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    'check_fk_naming', REPO / 'scripts' / 'check_fk_naming.py')
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


class TestTheClassifierSeparatesTheFourForms:
    """``classify`` es la tabla de ADR-029, sin más estado que sus argumentos."""

    @pytest.mark.parametrize('name, has_db_column, expected', [
        ('parent', False, 'A'),
        ('crud_model_id', False, 'B'),
        ('model_id', True, 'C'),
        ('page', True, 'D'),
    ])
    def test_the_two_syntactic_properties_decide_the_form(
            self, name, has_db_column, expected):
        assert gate.classify(name, has_db_column) == expected

    def test_a_non_stored_field_is_n_and_not_b(self):
        """``store=False`` no tiene columna: no se le mide fidelidad de columna."""
        assert gate.classify('properties_base_definition_id', False,
                             stored=False) == 'N'

    def test_a_non_stored_field_with_a_divergent_symbol_is_still_n(self):
        """La ausencia del eje gana sobre la forma del nombre."""
        assert gate.classify('parent', False, stored=False) == 'N'


class TestItReadsTheRealTree:
    """Los positivos conocidos, leídos de sus archivos."""

    def test_a_known_form_a_declaration_is_reported_as_a(self):
        path = REPO / 'addons' / 'account' / 'models' / 'account_account.py'

        forms = {name: form for _k, name, form in gate.declarations(path)}

        assert forms['company'] == 'A'

    def test_a_known_form_c_declaration_is_reported_as_c(self):
        path = (REPO / 'addons' / 'base_automation' / 'models'
                / 'base_automation.py')

        forms = {name: form for _k, name, form in gate.declarations(path)}

        assert forms['model_id'] == 'C'
        assert forms['trg_date_id'] == 'C'

    def test_it_recognises_our_dispatcher_not_only_djangos_constructor(self):
        """``fields.Many2one`` cuenta, o el alcance medido no significa nada."""
        assert 'Many2one' in gate.SINGLE_VALUED
        assert 'ForeignKey' in gate.SINGLE_VALUED


class TestTheBaselineAbsorbsTheInheritedDebtAndOnlyThat:
    """Una declaración listada no bloquea; una nueva sí."""

    def test_every_offender_measured_today_is_in_the_baseline(self):
        rows, _counts = gate.survey()
        baseline = gate.load_baseline()

        fresh = [key for form, key in rows
                 if form in ('A', 'B', 'D') and key not in baseline]

        assert fresh == []

    def test_the_baseline_does_not_absolve_a_form_that_is_not_a_debt(self):
        """C y N nunca entran al baseline: no son deuda."""
        rows, _counts = gate.survey()
        baseline = gate.load_baseline()

        faithful = {key for form, key in rows if form in ('C', 'N')}

        assert not (faithful & baseline)

    def test_the_gate_publishes_its_denominator(self, capsys):
        """Un conteo sin alcance medido no es un resultado."""
        gate.main.__globals__['sys'].argv = ['check_fk_naming.py']
        assert gate.main() == 0

        salida = capsys.readouterr().out
        assert 'alcance medido:' in salida
        assert 'formas:' in salida
