"""Casos del localizador, escritos ANTES del instrumento.

Lo que se prueba no es «encuentra cosas» —eso lo cumple un ``grep``— sino las
tres distinciones sin las cuales el veredicto TRAE/CONSTRUYE seria un verde
que no discrimina:

1. **declaracion, no mencion.** Un nombre que sale en el CUERPO de una funcion
   no es un simbolo que se pueda llamar. El control positivo de esto es el
   caso ``test_a_name_only_mentioned_in_a_body_is_not_a_declaration``: si el
   instrumento midiera por texto, ese caso pasaria a ``trae_candidato`` y el
   veredicto diria «el stack lo trae» sobre una variable local.
2. **especificidad del nombre.** ``create`` lo declaran doce paquetes y no
   dice nada; ``frozendict`` lo declara uno y si dice. Colapsarlos publica una
   cota superior disfrazada de medicion.
3. **nuestro arbol es OTRO universo.** Un simbolo que ya vive en ``src/tools``
   no es «el stack lo trae hecho»: es porte nuestro fuera de la raiz espejada,
   y su desenlace es reubicar o declarar, no construir.
"""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import locate_absent_symbols as loc  # noqa: E402


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


class TestOnlyDeclarationsCount:
    """El instrumento mide lo que se declara, no lo que se nombra."""

    def test_a_top_level_function_is_a_declaration(self, tmp_path):
        write(tmp_path / 'm.py', 'def frozendict():\n    pass\n')
        assert 'frozendict' in loc.declarations_in(tmp_path / 'm.py')

    def test_a_class_and_its_methods_are_declarations(self, tmp_path):
        write(tmp_path / 'm.py', 'class Cache:\n    def invalidate(self):\n        pass\n')
        found = loc.declarations_in(tmp_path / 'm.py')
        assert {'Cache', 'invalidate'} <= found

    def test_a_name_only_mentioned_in_a_body_is_not_a_declaration(self, tmp_path):
        """EL CONTROL que discrimina medir por AST de medir por texto.

        ``OrderedSet`` sale dos veces en el archivo y no se declara ninguna.
        Un instrumento que grepeara el nombre lo daria por presente y el
        veredicto diria «el stack lo trae hecho» sobre una variable local.
        """
        write(tmp_path / 'm.py',
              'def build():\n'
              '    OrderedSet = list\n'
              '    return OrderedSet()\n')
        assert 'OrderedSet' not in loc.declarations_in(tmp_path / 'm.py')

    def test_a_file_that_does_not_parse_yields_nothing_instead_of_raising(
            self, tmp_path):
        """El indice recorre miles de archivos instalados; uno con sintaxis de
        otra version no puede tumbar la medicion — pero tampoco inventar."""
        write(tmp_path / 'm.py', 'def roto(:\n')
        assert loc.declarations_in(tmp_path / 'm.py') == set()


class TestTheNameSpecificityIsMeasured:
    """Un nombre en varios paquetes no es evidencia de nada."""

    def test_a_name_in_one_package_is_a_candidate(self, tmp_path):
        write(tmp_path / 'django' / 'a.py', 'def frozendict():\n    pass\n')
        index = loc.index_declarations([tmp_path])
        assert loc.classify('frozendict', index, {}) == 'trae_candidato'

    def test_a_name_in_two_packages_is_generic(self, tmp_path):
        write(tmp_path / 'django' / 'a.py', 'def create():\n    pass\n')
        write(tmp_path / 'lxml' / 'b.py', 'def create():\n    pass\n')
        index = loc.index_declarations([tmp_path])
        assert loc.classify('create', index, {}) == 'nombre_generico'

    def test_the_package_is_the_first_segment_not_the_file(self, tmp_path):
        """Dos archivos del MISMO paquete no lo vuelven generico: el eje es
        cuantos paquetes distintos lo declaran, no cuantos archivos."""
        write(tmp_path / 'django' / 'a.py', 'def SQL():\n    pass\n')
        write(tmp_path / 'django' / 'db' / 'b.py', 'def SQL():\n    pass\n')
        index = loc.index_declarations([tmp_path])
        assert loc.classify('SQL', index, {}) == 'trae_candidato'


class TestOurTreeIsAnotherUniverse:
    """Lo que ya escribimos no es «el stack lo trae hecho»."""

    def test_a_symbol_of_ours_wins_over_the_stack(self, tmp_path):
        write(tmp_path / 'django' / 'a.py', 'def Query():\n    pass\n')
        stack = loc.index_declarations([tmp_path])
        ours = {'Query': {'src/tools/query.py'}}
        assert loc.classify('Query', stack, ours) == 'ya_esta_aqui'

    def test_with_no_trace_anywhere_it_is_its_own_bucket(self, tmp_path):
        """EL CONTROL POSITIVO del cubo terminal: sin este caso, un indice
        vacio por un error de ruta publicaria «todo se construye» y el verde
        no distinguiria «no lo trae nadie» de «no pude medir»."""
        write(tmp_path / 'django' / 'a.py', 'def otra_cosa():\n    pass\n')
        stack = loc.index_declarations([tmp_path])
        assert loc.classify('LangProxyDict', stack, {}) == 'sin_rastro'


class TestTheDenominatorTravelsWithTheCount:
    """Un conteo sin universo no es un resultado."""

    def test_the_summary_carries_its_population(self, tmp_path):
        write(tmp_path / 'django' / 'a.py', 'def uno():\n    pass\n')
        stack = loc.index_declarations([tmp_path])
        total = loc.summary(['uno', 'dos'], stack, {'dos': {'src/x.py'}})
        assert total.universe == 2
        assert total.by_bucket['trae_candidato'] == 1
        assert total.by_bucket['ya_esta_aqui'] == 1
        assert sum(total.by_bucket.values()) == total.universe


class TestTheIndexRefusesAnEmptyRoot:
    """Un indice vacio es «no pude medir», no «el stack no lo trae»."""

    def test_a_root_that_does_not_exist_is_reported_not_swallowed(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            loc.index_declarations([tmp_path / 'no-existe'])


class TestTheSpecificityIsDemandedOnBothSides:
    """El cubo de «ya lo tenemos» no puede llenarse de nombres genericos."""

    def test_two_files_of_ours_make_the_name_generic(self, tmp_path):
        """EL CONTROL de la simetria: sin el, ``add`` —declarado en tres
        archivos nuestros, ninguno el de la fuente— entraria como inventario
        propio y el veredicto TRAE/CONSTRUYE partiria de una cota superior
        contaminada."""
        ours = {'add': {'src/tools/misc.py', 'src/tools/date_utils.py'}}
        assert loc.classify('add', {}, ours) == 'nombre_generico'

    def test_one_file_of_ours_still_wins(self, tmp_path):
        ours = {'ormcache': {'src/tools/cache.py'}}
        assert loc.classify('ormcache', {}, ours) == 'ya_esta_aqui'


class TestTheEvidenceComesFromBothUniverses:
    """El detalle se leia solo del stack y reventaba sobre un generico nuestro."""

    def test_a_generic_of_ours_has_evidence_without_the_stack(self):
        """EL CONTROL del defecto real: ``_read_group_select`` lo declaran dos
        addons nuestros y ningun paquete instalado. Leer la evidencia del
        stack levantaba ``KeyError`` y mataba el listado a la mitad."""
        ours = {'_read_group_select': {'addons/stock/models/stock_quant.py',
                                       'addons/account/report/x.py'}}
        assert loc.classify('_read_group_select', {}, ours) == 'nombre_generico'
        assert len(loc.evidence('_read_group_select', {}, ours)) == 2

    def test_a_symbol_with_no_trace_has_no_evidence(self):
        assert loc.evidence('LangProxyDict', {}, {}) == []
