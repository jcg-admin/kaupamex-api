"""El gate que cruza la fidelidad DECLARADA con la ENTREGADA.

Nace de :ref:`h-api-815`: de **442** archivos que declaran fidelidad en un
docstring, **257** tienen par en la referencia y **205 de esos 257 — el 79 %**
entregan menos de lo que dicen. La afirmación era prosa y ningún gate la
miraba.

Los tests son **puros**: miden el instrumento, no el árbol. El caso caro —el
que corre ``check_porte_completo`` entero— está marcado aparte.

El positivo es del repo, no fabricado
======================================

``account/models/account_move.py`` es el peor de los 205 con **348** símbolos
ausentes, y declara fidelidad. Un incumplidor escrito a mano por quien escribió
el patrón heredaría su encuadre y confirmaría el instrumento; éste no.

El detector NO puede ser un grep de forma superficial
======================================================

El primer instrumento fue ``grep -rlE "Adaptación fiel"`` con ``.`` en lugar de
la tilde y devolvió **0** — en UTF-8 la ``ó`` son dos bytes y ``.`` casa uno.
El caso ``test_the_accented_form_is_detected`` fija esa regresión.
"""
import importlib.util
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    'check_fidelidad_declarada', REPO / 'scripts' / 'check_fidelidad_declarada.py')
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

#: El positivo real: el peor de los 205 al escribir estos tests.
REAL_POSITIVE = 'account/models/account_move.py'


def _write(tmp_path, name, body):
    path = tmp_path / name
    path.write_text(body, encoding='utf-8')
    return path


# ----------------------------------------------------------------------
# El detector de la declaración
# ----------------------------------------------------------------------

def test_the_accented_form_is_detected(tmp_path):
    """La regresión que motivó el AST: ``Adaptación`` lleva tilde."""
    path = _write(tmp_path, 'a.py', '"""Adaptación fiel de la referencia."""\n')
    assert gate.declara_fidelidad(path)


def test_the_unaccented_form_is_detected(tmp_path):
    """``Portacion fiel`` sin tilde sale 15 veces en el árbol."""
    path = _write(tmp_path, 'b.py', '"""Portacion fiel de x/y.py."""\n')
    assert gate.declara_fidelidad(path)


def test_verbatim_is_detected(tmp_path):
    path = _write(tmp_path, 'c.py', '"""Cuerpo adaptado VERBATIM de la fuente."""\n')
    assert gate.declara_fidelidad(path)


def test_a_class_docstring_counts(tmp_path):
    """La declaración vive tan a menudo en la clase como en el módulo."""
    path = _write(tmp_path, 'd.py',
                  '"""Sin declaración aquí."""\n\n\nclass X:\n    """Fiel a la fuente."""\n')
    assert gate.declara_fidelidad(path)


def test_a_file_without_the_word_does_not_enter(tmp_path):
    path = _write(tmp_path, 'e.py', '"""Un modelo propio del L0."""\n')
    assert not gate.declara_fidelidad(path)


def test_a_comment_is_not_a_docstring(tmp_path):
    """Ceguera declarada: el AST no ve comentarios, y eso es deliberado."""
    path = _write(tmp_path, 'f.py', '# Adaptación fiel de x/y.py\n')
    assert not gate.declara_fidelidad(path)


def test_a_broken_file_does_not_crash_the_gate(tmp_path):
    """Un `.py` que no parsea sale del alcance, no rompe el barrido."""
    path = _write(tmp_path, 'g.py', 'def (:\n')
    assert not gate.declara_fidelidad(path)


# ----------------------------------------------------------------------
# La clave, que es como el gate hermano nombra el archivo
# ----------------------------------------------------------------------

def test_the_key_drops_both_addon_roots():
    assert gate.clave(pathlib.Path('src/addons/base/models/x.py')) == \
        'base/models/x.py'
    assert gate.clave(pathlib.Path('addons/account/models/y.py')) == \
        'account/models/y.py'


# ----------------------------------------------------------------------
# El baseline
# ----------------------------------------------------------------------

def test_the_baseline_exists_and_is_not_empty():
    """Un baseline vacío haría que el gate pase por vacuidad."""
    assert gate.BASELINE.is_file()
    assert gate.carga_baseline(), 'baseline vacío: el gate pasaría sin medir'


def test_the_real_positive_is_in_the_baseline():
    rutas = {l.split('#')[0].strip() for l in gate.carga_baseline()}
    assert REAL_POSITIVE in rutas


def test_comments_do_not_enter_the_baseline():
    """La cabecera del baseline es casi todo el archivo."""
    assert not any(l.lstrip().startswith('#') for l in gate.carga_baseline())


# ----------------------------------------------------------------------
# El positivo real, contra el archivo del árbol
# ----------------------------------------------------------------------

def test_the_real_positive_declares_fidelity_in_the_tree():
    """El positivo real, medido sobre el archivo del árbol y no sobre uno hecho."""
    path = REPO / 'addons' / REAL_POSITIVE
    assert path.is_file(), 'el positivo real se movió: elegir otro de los 205'
    assert gate.declara_fidelidad(path)
