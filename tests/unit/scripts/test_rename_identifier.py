"""Pruebas de ``scripts/rename_identifier.py`` (:ref:`h-api-799`).

**El caso no esta fabricado.** Es el episodio real que origino el script: el
docstring, el comentario y la f-string de
``tests/unit/base/test_ir_actions_server_open.py``, donde un ``re.sub`` de
``accion`` -> ``action`` produjo *"una action suelta no tiene parent_action"*.
Escribir un incumplidor propio heredaria el encuadre de quien escribio el
patron, que es lo que ``hallazgo-abierto-genera-sucesor.md`` prohibe.

Los tres modos de fallo que el script cierra, medidos en la sesion del
2026-08-26/27, y cada uno tiene su caso aqui:

1. **regex sobre el archivo entero** — reescribe la prosa espanola;
2. **regex con lookahead** — deja ocurrencias sin renombrar (las seguidas de
   ``]`` o de fin de linea) y **sigue** danando la prosa;
3. **saltar lineas por su primer caracter** — no ve el interior de un
   docstring de modulo, y salta una linea de codigo real por contener ``or ''``,
   dejando una variable muerta.

El control que puede fallar
---------------------------

La guarda de prosa **no puede dispararse** mientras el renombre sea por AST:
por construccion solo toca tokens ``NAME``. Para comprobar que discrimina hay
que anular el renombrador — sustituirlo por un ``str.replace`` ingenuo — y ver
que la guarda aborta sin escribir. Eso es
``test_the_guard_aborts_a_naive_replacement``, y sin el la guarda seria un
adorno: un control que nunca puede fallar no es una red (sub-patron D de
``metrica-decide-la-conclusion.md``).

Y una nota sobre las cifras de este archivo: dos de ellas se escribieron
**predichas** y la primera corrida las corrigio —cinco ocurrencias, no seis;
cinco tramos de prosa danados, no tres—. Es el mismo defecto que
:ref:`h-api-800` registra, otra vez, y se deja anotado en vez de disimulado
porque la leccion es exactamente esa: una prediccion sobre el resultado de un
control no es el control.
"""
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.rename_identifier import (posiciones, renombrar, _prosa,
                                       _prosa_intacta)

pytestmark = [pytest.mark.unit]

#: El episodio real, reducido a lo que cada modo de fallo toca.
CASO = '''"""Modulo de prueba — el episodio real de H-API-799.

Este docstring dice "una accion suelta no tiene padre", y esa frase es prosa
espanola: un renombre de identificador NO puede tocarla.
"""
# La accion es la que ejecuta; el cron solo aporta la periodicidad.
ACCION_POR_DEFECTO = 'ninguna'


def abrir(accion):
    """Devuelve el descriptor de la accion. La palabra accion es prosa."""
    etiqueta = f'la accion {accion!r} no tiene padre'
    otra = accion or ''
    lista = [accion]
    return {'accion': accion, 'etiqueta': etiqueta, 'otra': otra, 'l': lista}
'''


@pytest.fixture
def target(tmp_path):
    p = tmp_path / 'caso.py'
    p.write_text(CASO, encoding='utf-8')
    return p


# --------------------------------------------------------------------------
# Lo que renombra, y lo que no
# --------------------------------------------------------------------------

def test_it_renames_every_binding_of_the_identifier():
    nuevo, n = renombrar(CASO, 'accion', 'action')
    # Medido, no predicho: el arg, la f-string, el ``or``, la lista y el valor
    # del dict. Son CINCO — la primera version de este caso decia seis.
    assert n == 5
    assert 'def abrir(action):' in nuevo
    assert 'otra = action or ' in nuevo
    assert 'lista = [action]' in nuevo


def test_it_leaves_the_docstring_alone():
    """El modo de fallo 1: el regex sobre el archivo entero."""
    nuevo, _ = renombrar(CASO, 'accion', 'action')
    assert 'una accion suelta no tiene padre' in nuevo
    assert 'La palabra accion es prosa' in nuevo


def test_it_leaves_the_comment_alone():
    nuevo, _ = renombrar(CASO, 'accion', 'action')
    assert '# La accion es la que ejecuta' in nuevo


def test_it_leaves_a_different_identifier_alone():
    """``ACCION_POR_DEFECTO`` contiene la palabra y NO es el identificador."""
    nuevo, _ = renombrar(CASO, 'accion', 'action')
    assert 'ACCION_POR_DEFECTO' in nuevo


def test_a_string_key_and_a_name_on_the_same_line_get_opposite_verdicts():
    """La linea del ``return`` tiene las dos cosas, y solo una cambia.

    Es el caso que un control por LINEAS no puede resolver: la primera version
    de la guarda comparaba lineas y abortaba aqui por falso positivo.
    """
    nuevo, _ = renombrar(CASO, 'accion', 'action')
    assert "'accion': action" in nuevo


def test_the_interior_of_an_f_string_is_renamed_but_not_its_literal():
    """Precondicion 3.12 (:ref:`h-api-607`): hasta 3.11 esto era invisible."""
    nuevo, _ = renombrar(CASO, 'accion', 'action')
    assert "f'la accion {action!r} no tiene padre'" in nuevo


def test_it_finds_the_occurrence_a_lookahead_would_miss():
    """El modo de fallo 2: ``[accion]`` y el ``accion`` a fin de linea."""
    filas = {f for f, _ in posiciones(CASO, 'accion')}
    assert len(posiciones(CASO, 'accion')) == 5
    # la linea de la lista esta cubierta
    assert any('lista = [accion]' in CASO.splitlines()[f - 1] for f in filas)


def test_it_finds_the_line_a_quote_heuristic_would_skip():
    """El modo de fallo 3: ``otra = accion or ''`` tiene comillas y es codigo."""
    filas = {f for f, _ in posiciones(CASO, 'accion')}
    assert any("otra = accion or ''" in CASO.splitlines()[f - 1] for f in filas)


# --------------------------------------------------------------------------
# La guarda de prosa — y el control que la hace discriminar
# --------------------------------------------------------------------------

def test_the_prose_is_untouched_by_construction():
    nuevo, _ = renombrar(CASO, 'accion', 'action')
    ok, danadas = _prosa_intacta(CASO, nuevo)
    assert ok, danadas
    assert _prosa(CASO) == _prosa(nuevo)


def test_the_guard_aborts_a_naive_replacement():
    """El control: con el renombre ingenuo, la guarda DEBE ver el dano.

    Sin este caso la guarda nunca podria fallar y seria un adorno.
    """
    ingenuo = CASO.replace('accion', 'action')
    ok, danadas = _prosa_intacta(CASO, ingenuo)
    assert not ok
    # Medido: los dos docstrings, el comentario, el literal de la f-string y
    # la clave del dict. CINCO — no los tres que la primera version predijo.
    assert len(danadas) == 5


# --------------------------------------------------------------------------
# El guard de interprete — no emite cifra al fallar
# --------------------------------------------------------------------------

def test_the_interpreter_guard_refuses_below_312(target):
    """Con 3.11 aborta con exit 2, sin escribir y **sin publicar un conteo**.

    Un 0 ahi se leeria como "no hay ocurrencias" cuando lo cierto es "no pude
    verlas": hasta 3.11 el interior de una f-string es invisible.
    """
    viejo = Path('/usr/bin/python3.11')
    if not viejo.exists():
        pytest.skip('no hay Python 3.11 en el sistema para medir el guard')
    antes = target.read_text(encoding='utf-8')
    r = subprocess.run(
        [str(viejo), 'scripts/rename_identifier.py', 'accion', 'action',
         str(target)], capture_output=True, text=True)
    assert r.returncode == 2
    assert 'ocurrencia' not in r.stdout
    assert target.read_text(encoding='utf-8') == antes


def test_it_runs_end_to_end_on_the_project_interpreter(target):
    r = subprocess.run(
        [sys.executable, 'scripts/rename_identifier.py', 'accion', 'action',
         str(target)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    salida = target.read_text(encoding='utf-8')
    assert 'def abrir(action):' in salida
    assert 'una accion suelta no tiene padre' in salida
