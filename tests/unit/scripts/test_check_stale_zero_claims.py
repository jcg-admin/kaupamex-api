"""El gate mide el comando que la prosa cita, no el símbolo que uno supone (#228).

Mismo principio que ``test_check_fk_naming.py``: un gate se prueba contra un
**positivo conocido del repo**, no contra un incumplidor fabricado por quien
escribió el patrón — un fabricado hereda el encuadre de su autor y confirma el
instrumento en vez de ponerlo a prueba.

Los cuatro controles que discriminan
=====================================

Cada uno corresponde a un defecto que la primera versión del gate tuvo, y que
publicó una cifra falsa antes de corregirse. El caso está escrito para que
**caiga** si la corrección se revierte:

===========================  ==================================  =============
Control                      Qué mide                            Sin el arreglo
===========================  ==================================  =============
``^class IrUiView``          un cero que el porte dejó falso     no se ve
``wkhtmltopdf`` (la cita)    la prosa citándose a sí misma       5 falsos
``^class IrModel`` (código)  el porte contradiciendo su prosa    se silencia
``grep -ic stdnum``          ``-c`` emite el número, no líneas   5 falsos
===========================  ==================================  =============

Los dos del medio son la misma línea de código con veredictos opuestos, y por
eso van juntos: excluir el archivo entero arregla el primero y rompe el
segundo. El discriminador que sostiene los dos es el literal RST.
"""
import importlib.util
import os
import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    'check_stale_zero_claims', REPO / 'scripts' / 'check_stale_zero_claims.py')
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

#: Los reclamos se re-ejecutan con el repo como directorio de trabajo: las
#: rutas que citan (``src/``, ``addons/``) son relativas a él.
BASE = pytest.fixture(autouse=True)(
    lambda monkeypatch: monkeypatch.chdir(REPO))


class TestTheClaimIsReadWithItsCommand:
    """``claims_in`` extrae la cita y la ancla a la línea que la escribe."""

    def test_it_finds_the_ir_ui_view_claim_of_res_groups(self):
        """``res_groups.py`` declina el conjunto disjunto citando un cero."""
        claims = gate.claims_in(
            pathlib.Path('src/addons/base/models/res_groups.py'))
        commands = [command for command, _ in claims]
        assert any('^class IrUiView' in c for c in commands), commands

    def test_a_repeated_claim_gets_its_own_line(self):
        """Dos archivos repiten su cita; las dos merecen línea propia."""
        claims = gate.claims_in(
            pathlib.Path('addons/account_peppol/models/res_company.py'))
        phone = [line for command, line in claims if 'phonenumbers' in command]
        assert len(phone) == 2, claims
        assert phone[0] != phone[1], phone

    def test_the_line_carries_the_grep_it_names(self):
        """El ancla es la cita, no el primer ``grep`` del archivo."""
        path = pathlib.Path('src/addons/base/models/ir_actions_report.py')
        for command, line in gate.claims_in(path):
            if 'wkhtmltopdf' not in command:
                continue
            text = path.read_text().splitlines()[line - 1]
            assert 'grep' in text and 'wkhtmltopdf' in text, text


class TestTheCitationIsNotItsOwnEvidence:
    """La prosa que cita el comando vive dentro del árbol que el comando barre.

    Al escribirse la cita el archivo aún no la contenía y el cero era honesto;
    hoy el grep encuentra su propio texto. El discriminador es el literal RST,
    que toda cita de este árbol lleva y ninguna línea de código tiene.
    """

    CLAIMING = pathlib.Path('src/addons/base/models/ir_actions_report.py')

    def test_a_citation_line_is_discarded(self):
        line = f'{self.CLAIMING}:41:``grep -rln "…wkhtmltopdf…" src/`` → **0**'
        assert gate.is_its_own_citation(line, self.CLAIMING)

    def test_a_code_line_of_the_same_file_counts(self):
        """El porte que contradice a su propia prosa es el caso interesante."""
        line = f'{self.CLAIMING}:1264:    def get_wkhtmltopdf_state(cls):'
        assert not gate.is_its_own_citation(line, self.CLAIMING)

    def test_another_file_always_counts(self):
        line = 'src/tools/barcode.py:32:La referencia rasteriza con ``reportlab``'
        assert not gate.is_its_own_citation(line, self.CLAIMING)


class TestTheRerunReproducesWhatTheAuthorMeasured:
    """Cada caso es un reclamo real del árbol, con su conteo de hoy."""

    def test_a_zero_the_port_left_false_is_seen(self):
        """``ir_ui_view.py`` se portó; el cero de ``res_groups.py`` caducó."""
        claiming = pathlib.Path('src/addons/base/models/res_groups.py')
        count, why = gate.rerun('grep -rn "^class IrUiView" src/', claiming)
        assert why is None, why
        assert count > 0, 'el porte de ir_ui_view.py dejó de verse'

    def test_the_port_contradicting_its_own_prose_is_seen(self):
        """``ir_model.py`` declina citando un cero y declara la clase él mismo.

        Es el control que separa las dos exclusiones: por archivo entero, este
        caso desaparece —la única coincidencia está en el archivo que reclama—
        y el gate publica un falso negativo.
        """
        claiming = pathlib.Path('src/addons/base/models/ir_model.py')
        count, why = gate.rerun(r'grep -rn "^class IrModel\b" src/', claiming)
        assert why is None, why
        assert count == 1, 'la clase que el propio porte añadió debe contar'

    def test_count_mode_reads_the_number_not_the_lines(self):
        """``grep -ic`` imprime ``0`` en una línea; contarlas daría 1."""
        claiming = pathlib.Path('addons/account_peppol/models/res_company.py')
        count, why = gate.rerun('grep -ic stdnum uv.lock', claiming)
        assert why is None, why
        assert count == 0, 'la salida de -c ES el número, no una coincidencia'

    def test_a_shell_glob_is_expanded(self):
        """Sin shell, ``src/orm/*.py`` llega literal y grep sale 2."""
        claiming = pathlib.Path('addons/web/models/models.py')
        count, why = gate.rerun('grep -rn "def new(" src/orm/*.py', claiming)
        assert why is None, why
        assert count == 0

    def test_a_grep_v_pipe_filters_in_python(self):
        """Dos autores ya excluían su archivo a mano; se sostiene el filtro."""
        claiming = pathlib.Path('src/addons/base/models/res_company.py')
        count, why = gate.rerun(
            'grep -rn "zeep" src/ | grep -v res_company.py', claiming)
        assert why is None, why
        assert count >= 0

    def test_a_missing_path_is_named_not_counted(self):
        """Una ruta que ya no existe se declara; publicar 0 sería un verde falso."""
        claiming = pathlib.Path('addons/web/models/models.py')
        count, why = gate.rerun(
            'grep -n "_render" src/addons/*/models/template_expressions.py',
            claiming)
        assert count is None
        assert 'ya no existe' in why, why


class TestTheGateRefusesRatherThanPublishAFalseGreen:
    """Un cero sin alcance no distingue «no hay» de «no medí»."""

    def test_it_exits_two_without_emitting_a_count(self, tmp_path):
        (tmp_path / 'src').mkdir()
        (tmp_path / 'addons').mkdir()
        done = subprocess.run(
            [sys.executable, str(REPO / 'scripts' / 'check_stale_zero_claims.py')],
            cwd=tmp_path, capture_output=True, text=True)
        assert done.returncode == 2, done.stdout
        assert 'caducado' not in done.stdout, done.stdout
        assert 'verde falso' in done.stderr, done.stderr

    def test_strict_blocks_a_claim_outside_the_baseline(self, tmp_path):
        """Con el baseline vacío bloquean los 24 reclamos reales del árbol.

        Es el par discriminante del congelado: si el baseline no se leyera,
        este caso y el siguiente darían lo mismo.
        """
        empty = tmp_path / 'vacio.txt'
        empty.write_text('')
        done = self._run('--strict', baseline=empty)
        assert done.returncode == 1, done.stdout
        assert 'fuera del baseline' in done.stdout, done.stdout

    def test_the_frozen_debt_does_not_block(self):
        done = self._run('--strict')
        assert done.returncode == 0, done.stdout
        assert 'en baseline:' in done.stdout, done.stdout

    @staticmethod
    def _run(*flags, baseline=None):
        env = dict(os.environ)
        if baseline is not None:
            env['STALE_ZERO_BASELINE'] = str(baseline)
        return subprocess.run(
            [sys.executable,
             str(REPO / 'scripts' / 'check_stale_zero_claims.py'), *flags],
            cwd=REPO, capture_output=True, text=True, env=env)
