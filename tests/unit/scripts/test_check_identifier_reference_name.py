"""El gate que impide que un identificador nuestro lleve el nombre de la
referencia (directiva del ejecutor 2026-09-02).

Qué haría fallar a estos casos
==============================

El control positivo **no está fabricado**: es la línea que este repo tuvo hasta
el 2026-09-02, ``campo.odoo_translate = bool(translate)`` en
``src/orm/fields_textual.py``. Un incumplidor inventado por quien escribió el
patrón hereda su encuadre y confirma el instrumento; éste lo contradice, porque
el árbol lo produjo antes de que el gate existiera.

Y el control negativo es el que separa este eje del de la cita: una **cadena**
con el nombre de la referencia —el alias ``'odoo19c'``, la variable de entorno
``os.environ['ODOO19C']``— es cómo este árbol nombra su fuente, y tiene que
pasar. Sin ese caso, un gate que midiera el texto crudo en vez del AST daría el
mismo verde sobre el árbol limpio y rompería el primer script que cite la
referencia.
"""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / 'scripts'))
import check_identifier_reference_name as gate


@pytest.fixture
def module_file(tmp_path):
    def write(source, name='probe.py'):
        path = tmp_path / name
        path.write_text(source, encoding='utf-8')
        return path
    return write


class TestTheGateSeesTheIdentifierThatTheTreeActuallyHad:
    """El control positivo, verbatim del árbol antes del renombre."""

    def test_the_assigned_attribute_is_caught(self, module_file):
        path = module_file('def Char(translate=None):\n'
                           '    campo = object()\n'
                           '    campo.odoo_translate = bool(translate)\n')
        assert [name for _, name, _ in gate.offenders_in(path)] == ['odoo_translate']

    def test_a_class_is_caught(self, module_file):
        path = module_file('class OdooAdapter:\n    pass\n')
        assert [name for _, name, _ in gate.offenders_in(path)] == ['OdooAdapter']

    def test_a_function_is_caught(self, module_file):
        path = module_file('def derives_from_the_odoo_name():\n    pass\n')
        assert gate.offenders_in(path)[0][1] == 'derives_from_the_odoo_name'

    def test_a_parameter_of_the_signature_is_caught(self, module_file):
        """La firma entra: es lo que la directiva nombra explícitamente."""
        path = module_file('def expected_class(modelo_odoo):\n    return modelo_odoo\n')
        assert gate.offenders_in(path)[0][1] == 'modelo_odoo'

    def test_a_module_constant_is_caught(self, module_file):
        path = module_file("ODOO19C = 'x'\n")
        assert gate.offenders_in(path)[0][1] == 'ODOO19C'

    def test_the_file_name_is_caught(self, module_file):
        path = module_file('x = 1\n', name='odoo_helpers.py')
        assert gate.offenders_in(path)[0][2] == 'nombre de archivo'


class TestTheGateLeavesTheCitationAlone:
    """El control negativo: citar la fuente no es bautizar con su nombre."""

    def test_a_string_alias_passes(self, module_file):
        """``'odoo19c'`` es el alias de cita que la convención fija."""
        path = module_file("from reference_roots import tree\n"
                           "REFERENCE_19C = tree('odoo19c')\n")
        assert gate.offenders_in(path) == []

    def test_reading_the_environment_variable_passes(self, module_file):
        """El nombre de la variable es la interfaz con el shell, no un símbolo."""
        path = module_file("import os\n"
                           "REFERENCE_19C = os.environ.get('ODOO19C', '')\n")
        assert gate.offenders_in(path) == []

    def test_the_prose_of_a_docstring_passes(self, module_file):
        """La cita ``odoo19c: odoo/orm/fields.py:288`` vive en docstrings."""
        path = module_file('"""≙ ``Field.translate`` '
                           '(``odoo19c: odoo/orm/fields.py:288``)."""\n'
                           'translate = False\n')
        assert gate.offenders_in(path) == []

    def test_a_file_that_does_not_parse_is_not_this_gates_problem(self, module_file):
        """Su nombre sí se mide; su contenido lo bloquea quien compila."""
        path = module_file('def roto(\n', name='odoo_roto.py')
        assert [kind for _, _, kind in gate.offenders_in(path)] == ['nombre de archivo']


class TestTheGateMeasuresTheWholeTreeAndPublishesItsDenominator:
    """Sin baseline: el árbol estaba en 0 al cablearlo."""

    def test_the_tree_is_clean(self, capsys):
        assert gate.main([]) == 0
        output = capsys.readouterr().out
        assert 'archivos medidos' in output

    def test_it_refuses_when_given_an_offender(self, module_file, capsys):
        path = module_file('def odoo_helper():\n    pass\n')
        assert gate.main([str(path)]) == 1
        assert 'odoo_helper' in capsys.readouterr().out
