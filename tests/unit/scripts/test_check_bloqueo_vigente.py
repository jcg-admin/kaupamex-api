"""Control de ``scripts/check_bloqueo_vigente.py``.

El gate existe para atrapar una marca de bloqueo cuya causa ya no existe. Su
modo de fallo peligroso no es el falso negativo —una marca caducada que se
escapa— sino el **falso positivo**: absolver un bloqueo vivo porque su destino
se parece a algo que existe. Por eso los casos de abajo miden las dos
direcciones, y los dos extremos salen del repo, no de un fixture inventado.
"""
import importlib.util
import os
import pathlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[3]


def _cargar():
    ruta = RAIZ / 'scripts' / 'check_bloqueo_vigente.py'
    spec = importlib.util.spec_from_file_location('cbv', ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope='module')
def gate():
    previo = os.getcwd()
    os.chdir(RAIZ)
    try:
        yield _cargar()
    finally:
        os.chdir(previo)


class TestTheDestinationResolvesInBothDirections:

    def test_a_model_that_exists_expires_its_marker(self, gate):
        """``account.edi.common`` se declara desde que se portó su addon."""
        assert 'account.edi.common' in gate.declared_model_names()
        assert gate.resolve('account.edi.common')[0] == 'existe'

    def test_a_model_that_does_not_exist_keeps_the_marker_alive(self, gate):
        """``mail.ice.server`` es uno de los tres bloqueos vivos de html_editor."""
        assert 'mail.ice.server' not in gate.declared_model_names()
        assert gate.resolve('mail.ice.server')[0] == 'falta'

    def test_an_addon_directory_that_is_absent_keeps_it_alive(self, gate):
        assert gate.resolve('iap')[0] == 'falta'

    def test_an_addon_directory_that_is_present_expires_it(self, gate):
        assert gate.resolve('account')[0] == 'existe'


class TestAPathResolvesOnlyTowardsAlive:
    """Que una ruta exista NO levanta el bloqueo, y ése fue el primer falso positivo.

    La marca de ``html_editor/models/ir_attachment.py`` nombra
    ``src/addons/base/migrations``, que existe desde siempre: su bloqueo es de
    alcance —el ``AddField`` es de otro puerto— y no de artefacto ausente.
    """

    def test_an_existing_path_is_not_measurable(self, gate):
        assert os.path.isdir('src/addons/base/migrations')
        assert gate.resolve('src/addons/base/migrations')[0] == 'no-medible'

    def test_a_missing_path_confirms_the_blockage(self, gate):
        assert gate.resolve('addons/no_existe_este_addon/models')[0] == 'falta'


class TestProseIsDeclaredNotMeasurable:
    """Un destino que no es un nombre resoluble sale aparte, nunca como caducado.

    Publicar el conteo de no medibles es lo que impide leer el cero de
    caducadas como cobertura: sin él, un guion que no resolviera nada
    publicaría el mismo cero que uno que lo resolviera todo.
    """

    @pytest.mark.parametrize('destino', [
        'el motor de compute',
        'super()',
        'self.env',
        'ResConfigSettings',
        'so_line',
    ])
    def test_it_is_neither_expired_nor_alive(self, gate, destino):
        assert gate.resolve(destino)[0] == 'no-medible'


class TestTheGateReadsTheRealTree:

    def test_it_finds_the_well_formed_edges(self, gate):
        aristas = gate.edges([])
        assert len(aristas) > 100, 'el recorrido dejo de ver las aristas'
        destinos = {d for _, _, d, _ in aristas}
        # Dos extremos conocidos: uno vivo y uno caducado.
        assert 'mail.ice.server' in destinos
        assert 'account_edi_ubl_cii' in destinos

    def test_the_counts_add_up_to_the_edges(self, gate):
        aristas = gate.edges([])
        estados = [gate.resolve(d)[0] for _, _, d, _ in aristas]
        assert len(estados) == len(aristas)
        assert set(estados) <= {'existe', 'falta', 'no-medible'}


class TestTheSymbolIsLookedUpInItsOwnModel:
    """El conjunto de ``def`` del árbol entero absolvía once marcas vivas.

    ``_render_template`` existe —en ``ir.actions.report``— y
    ``ir.ui.view._render_template`` seguía bloqueado igual. Preguntarle al
    árbol entero daba por caducado el bloqueo raíz de la tarea #274.
    """

    def test_a_symbol_of_another_model_does_not_expire_it(self, gate):
        assert 'ir.ui.view' in gate.declared_model_names()
        assert '_render_template' not in gate.symbols_of_model('ir.ui.view')
        assert '_render_template' in gate.symbols_of_model('ir.actions.report')
        assert gate.resolve('ir.ui.view._render_template')[0] == 'falta'
        assert gate.resolve(
            'ir.actions.report._render_qweb_pdf_prepare_streams')[0] == 'existe'

    def test_a_symbol_installed_by_extend_model_counts(self, gate):
        """El símbolo no tiene por qué estar en una ``class``: basta instalarlo.

        ``html_editor`` cuelga los suyos sobre ``ir.ui.view`` con
        ``extend_model``, sin declarar la clase. Mirar sólo los ``def`` de un
        archivo con ``_name`` los habría perdido.
        """
        simbolos = gate.symbols_of_model('ir.ui.view')
        assert 'save_from_html' in simbolos
        assert '_set_noupdate' in simbolos
