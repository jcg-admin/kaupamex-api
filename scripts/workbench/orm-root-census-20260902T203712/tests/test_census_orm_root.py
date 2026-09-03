"""Los controles del censo de la raiz espejada ``src/orm`` <-> ``odoo/orm``.

Se escriben ANTES del instrumento (TDD) y cada uno declara que lo haria
fallar, que es la exigencia del sub-patron D de
``metrica-decide-la-conclusion.md``: un verde que no discrimina no es
evidencia.

El fenomeno que el censo tiene que ver, y que un conteo por nombre desnudo
**no** ve, es el reparto estructural de este arbol: la fuente declara los
metodos de ``BaseModel`` dentro de una clase, y aqui viven como funciones de
modulo o colgados por ``extend_model``. Un censo por ``Clase.metodo`` los
cuenta a todos como ausentes; uno por nombre desnudo sobre la raiz entera los
cuenta a todos como presentes aunque vivan en otro archivo. Ninguna de las dos
cifras describe el porte.
"""
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import census_orm_root as censo  # noqa: E402


@pytest.fixture
def tree(tmp_path):
    """Un par de raices sinteticas: la referencia y la nuestra."""
    ref = tmp_path / 'ref'
    mine = tmp_path / 'mine'
    ref.mkdir()
    mine.mkdir()
    return ref, mine


class TestTheScopeIsTheFile:
    """El alcance de resolucion es el archivo, como en ``file_symbols``."""

    def test_a_method_of_the_source_class_counts_as_ported_as_a_module_function(
            self, tree):
        """El reparto de este arbol: la fuente lo declara en la clase y aqui
        es una funcion de modulo del MISMO archivo."""
        ref, mine = tree
        (ref / 'models.py').write_text(
            'class BaseModel:\n    def flush_model(self):\n        pass\n')
        (mine / 'models.py').write_text('def flush_model(self):\n    pass\n')

        fila = censo.census(ref, mine)['models.py']
        assert fila.missing == []
        assert 'flush_model' in fila.present
        # La clase NO esta, y eso no es una ausencia: es la divergencia de
        # forma que este arbol declara. Su cubo propio lo dice.
        assert fila.dissolved == ['BaseModel']

    def test_the_same_name_in_ANOTHER_file_is_not_present_but_misplaced(
            self, tree):
        """El control que discrimina el alcance. Sin el, un censo por nombre
        desnudo sobre la raiz entera absuelve un simbolo que vive donde la
        fuente no lo declara — y eso es una divergencia de sitio, no un porte
        (:ref:`h-api-578`)."""
        ref, mine = tree
        (ref / 'models.py').write_text(
            'class BaseModel:\n    def flush_model(self):\n        pass\n')
        (mine / 'models.py').write_text('pass\n')
        (mine / 'registry.py').write_text('def flush_model(self):\n    pass\n')

        fila = censo.census(ref, mine)['models.py']
        assert fila.missing == []
        assert fila.misplaced == {'flush_model': 'registry.py'}
        assert 'flush_model' not in fila.present
        assert fila.dissolved == ['BaseModel']

    def test_a_name_nobody_declares_is_missing(self, tree):
        """El control positivo: si el simbolo no esta en ninguna parte, sale
        ausente. Sin este caso los dos de arriba pasarian con un instrumento
        que devolviera siempre ``missing == []``."""
        ref, mine = tree
        (ref / 'models.py').write_text(
            'class BaseModel:\n    def flush_model(self):\n        pass\n')
        (mine / 'models.py').write_text('pass\n')

        fila = censo.census(ref, mine)['models.py']
        assert fila.missing == ['flush_model']
        assert fila.misplaced == {}
        # El control que discrimina el cubo nuevo: una clase cuyo miembro
        # falta NO esta disuelta — esta sin portar, y decir lo contrario
        # convertiria el cubo en una amnistia automatica.
        assert fila.dissolved == []
        assert 'BaseModel' in fila.missing_classes


class TestTheInstallersAreRead:
    """``extend_model`` instala simbolos que ningun ``def`` declara."""

    def test_a_method_installed_by_extend_model_counts(self, tree):
        ref, mine = tree
        (ref / 'models.py').write_text(
            'class BaseModel:\n    def modified(self):\n        pass\n')
        (mine / 'models.py').write_text(
            "extend_model('base.Model', metodos={'modified': _modified})\n")

        fila = censo.census(ref, mine)['models.py']
        assert fila.missing == []

    def test_a_dict_key_that_is_not_the_symbol_does_not_absolve(self, tree):
        """El control que discrimina el lector de instaladores: una clave
        cualquiera de un dict NO absuelve — sólo la de un ``extend_model``."""
        ref, mine = tree
        (ref / 'models.py').write_text(
            'class BaseModel:\n    def modified(self):\n        pass\n')
        (mine / 'models.py').write_text("OTRO = {'modified': 1}\n")

        fila = censo.census(ref, mine)['models.py']
        assert fila.missing == ['modified']


class TestTheFileItselfCanBeMissing:
    """Un archivo de la referencia sin contraparte es otro estado."""

    def test_a_file_without_counterpart_is_its_own_verdict(self, tree):
        ref, mine = tree
        (ref / 'commands.py').write_text('def create():\n    pass\n')

        fila = censo.census(ref, mine)['commands.py']
        assert fila.file_missing is True
        assert fila.missing == ['create']

    def test_a_file_of_ours_without_counterpart_is_reported_apart(self, tree):
        """El eje inverso: lo nuestro que la referencia no declara. Es la
        ceguera estructural de ``check_porte_completo`` (:ref:`h-api-569`) —
        un archivo que la fuente no tiene no entra en ninguna comparacion."""
        ref, mine = tree
        (ref / 'models.py').write_text('pass\n')
        (mine / 'models.py').write_text('pass\n')
        (mine / 'routers.py').write_text('pass\n')

        assert censo.ours_without_counterpart(ref, mine) == ['routers.py']


class TestTheDenominatorTravelsWithTheCount:
    """Toda cifra sale con su poblacion — ``calibration-verified-numbers``."""

    def test_the_summary_declares_its_universe(self, tree):
        ref, mine = tree
        (ref / 'models.py').write_text(
            'class B:\n    def a(self):\n        pass\n'
            '    def b(self):\n        pass\n')
        (mine / 'models.py').write_text('def a():\n    pass\n')

        total = censo.summary(censo.census(ref, mine))
        assert total.reference_symbols == 3      # B, a, b
        assert total.present == 1
        # 'b' falta y 'B' no esta disuelta (le falta un miembro): las dos
        # cuentan como ausentes, y el cubo de disueltas queda en cero.
        assert total.missing == 2
        assert total.dissolved == 0
