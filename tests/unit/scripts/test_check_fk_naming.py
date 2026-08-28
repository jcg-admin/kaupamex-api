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


class TestItSeesTheAnnotatedFormOfTheReference:
    """La referencia 19 declara el campo con anotación de tipo.

    Positivo real, no fabricado: la línea es verbatim de
    ``odoo19c: odoo/addons/base/models/res_partner.py:215``. Un recorrido que
    sólo mire ``ast.Assign`` deja de ver la declaración en cuanto el porte
    adopta esa forma — y su 0 no distingue *"no hay deuda"* de *"el
    instrumento no la puede ver"*.

    Qué haría fallar a este caso
    ============================

    Revertir la rama ``ast.AnnAssign`` de ``declarations``: el archivo pasa a
    reportar 0 declaraciones y el conteo cae en silencio.
    """

    def test_an_annotated_declaration_is_measured(self, tmp_path):
        path = tmp_path / 'res_partner.py'
        path.write_text(
            'from django.db import models\n'
            'import fields\n'
            '\n'
            'class ResPartner(models.Model):\n'
            "    parent_id: 'ResPartner' = fields.Many2one("
            "'res.partner', string='Related Company', index=True)\n"
            "    company = fields.Many2one('res.company')\n"
        )

        forms = {name: form for _k, name, form in gate.declarations(path)}

        assert forms == {'parent_id': 'B', 'company': 'A'}


class TestTheReferenceDecidesTheSymbolNotTheSuffix:
    """El sufijo ``_id`` es el proxy; el criterio es lo que la fuente declara.

    Positivo real del árbol, no fabricado:
    ``addons/crm/models/crm_lead.py::CrmLead.recurring_plan``. La referencia lo
    declara **sin** sufijo (``odoo19c: addons/crm/models/crm_lead.py:144``), así
    que el porte fiel es el símbolo sin sufijo — y el proxy lo marcaba como
    incumplidor, pidiendo apartarse de la referencia.

    No es un caso suelto: medido sobre ``odoo19c``, **128 de 2692** ``Many2one``
    (4.75 %) no llevan sufijo.

    Qué haría fallar a estos casos
    ==============================

    Retirar la consulta a la contraparte de ``declarations``: ``recurring_plan``
    vuelve a la forma D y reaparece como incumplidor nuevo. Es el control que
    se corrió al cerrar #141 — sin la consulta, las formas medidas pasan de
    ``A=637 B=13 C=99 D=5`` a ``A=650 B=0 C=98 D=6``.
    """

    def test_a_symbol_the_reference_declares_without_the_suffix_is_faithful(self):
        assert gate.classify('recurring_plan', True,
                             reference_names=frozenset({'recurring_plan'})) == 'C'

    def test_the_same_symbol_without_the_reference_falls_back_to_the_suffix(self):
        assert gate.classify('recurring_plan', True) == 'D'

    def test_a_divergent_symbol_is_not_absolved_by_the_counterpart(self):
        """``partner`` no está en la contraparte de ``crm_lead``; sigue siendo A."""
        fieles = gate.reference_many2one(
            pathlib.Path('addons/crm/models/crm_lead.py'))
        assert 'recurring_plan' in fieles and 'partner' not in fieles
        assert gate.classify('partner', False, reference_names=fieles) == 'A'

    def test_the_real_declaration_is_measured_as_faithful(self):
        path = REPO / 'addons' / 'crm' / 'models' / 'crm_lead.py'
        forms = {name: form for _k, name, form in gate.declarations(path)}

        assert forms['recurring_plan'] == 'C'

    def test_a_faithful_symbol_without_db_column_is_still_an_offender(self):
        """La consulta arregla el eje del símbolo, no absuelve el de la columna.

        ``country_of_birth`` de ``hr.employee`` es de los 128: símbolo fiel,
        pero sin ``db_column`` su columna sale ``country_of_birth_id``.
        """
        assert gate.classify('country_of_birth', False,
                             reference_names=frozenset({'country_of_birth'})) == 'B'
