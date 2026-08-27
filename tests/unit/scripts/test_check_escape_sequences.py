"""Pruebas de ``scripts/check_escape_sequences.py`` (H-API-758).

El control positivo **no está fabricado**: es el docstring real que
``addons/website_sale/models/crm_team.py`` tenía antes del arreglo, recuperado
de git. Ésa es la exigencia de ``hallazgo-abierto-genera-sucesor.md`` — un
incumplidor escrito por quien escribió el patrón hereda su encuadre y confirma
el instrumento en vez de medirlo.

Los dos casos reales son distintos entre sí a propósito, y eso importa:
``\\`` + espacio es el escape de espacio de RST, y ``\\|`` es parte de un
comando ``grep`` citado. Los dos se arreglan con el prefijo ``r`` en la cadena
y ninguno duplicando la barra.
"""
import subprocess
import sys

import pytest

from scripts.check_escape_sequences import find_invalid_escapes, main

pytestmark = [pytest.mark.unit]

#: Verbatim de ``crm_team.py:65`` antes del arreglo — el comando que
#: el docstring cita para justificar un veredicto de vocabulario.
REAL_RST_PIPE = '''"""Un docstring que cita un comando con alternancia.

``grep -rn "salesteam\\|salesperson" addons/ src/ --include=*.py`` -> 0 hits.
"""
'''

#: Verbatim de ``product_strategy.py:92`` antes del mismo pase — el escape de
#: espacio de RST, que pega el markup al parentesis sin dejar hueco.
REAL_RST_SPACE = '''"""Un docstring con markup pegado.

**(mismo patron que H-API-619 en** ``stock_package_type.py``\\ **).** El cuerpo
"""
'''


def _write(tmp_path, name, content):
    path = tmp_path / name
    path.write_text(content, encoding='utf-8')
    return path


@pytest.mark.parametrize(
    'content,expected',
    [(REAL_RST_PIPE, "'\\|'"), (REAL_RST_SPACE, "'\\ '")],
    ids=['grep-con-alternancia', 'escape-de-espacio-rst'],
)
def test_the_real_offenders_are_caught(tmp_path, content, expected):
    """Los dos casos que el árbol tuvo, no dos inventados."""
    path = _write(tmp_path, 'ofensor.py', content)
    findings = find_invalid_escapes(path)
    assert len(findings) == 1
    lineno, message = findings[0]
    assert lineno == 1, 'el docstring de módulo se reporta en su línea de apertura'
    assert expected in message


@pytest.mark.parametrize(
    'content',
    [REAL_RST_PIPE, REAL_RST_SPACE],
    ids=['grep-con-alternancia', 'escape-de-espacio-rst'],
)
def test_the_raw_prefix_is_what_fixes_them(tmp_path, content):
    """``r\"\"\"`` limpia el aviso **y** deja el contenido byte a byte."""
    path = _write(tmp_path, 'arreglado.py', 'r' + content)
    assert find_invalid_escapes(path) == []
    assert '\\|' in path.read_text() or '\\ ' in path.read_text()


def test_a_legitimate_escape_is_not_flagged(tmp_path):
    """``\\n`` y ``\\t`` son escapes que Python sí conoce."""
    path = _write(tmp_path, 'limpio.py', '"""Con salto\\ny tabulador\\t."""\n')
    assert find_invalid_escapes(path) == []


def test_a_broken_file_is_left_to_the_syntax_error(tmp_path):
    """Un archivo que no compila devuelve vacío — no se apila ruido sobre ruido."""
    path = _write(tmp_path, 'roto.py', 'def f(\n')
    assert find_invalid_escapes(path) == []


def test_the_scope_is_printed_next_to_the_verdict(tmp_path, capsys):
    """Un conteo sin denominador no es un resultado (H-DOCS-18/21)."""
    clean = _write(tmp_path, 'limpio.py', '"""Sin escapes."""\n')
    assert main([str(clean)]) == 0
    assert '1 archivos pedidos por ruta' in capsys.readouterr().out


def test_the_offender_makes_the_gate_fail(tmp_path, capsys):
    path = _write(tmp_path, 'ofensor.py', REAL_RST_PIPE)
    assert main([str(path)]) == 1
    err = capsys.readouterr().err
    assert 'ofensor.py:1' in err
    assert 'r"""' in err, 'el mensaje nombra el arreglo, no sólo el defecto'


def test_the_whole_tree_is_clean():
    """El árbol real, medido con el intérprete del proyecto.

    Es la aserción que cierra el grifo: un archivo nuevo con un escape
    inválido la rompe aquí aunque nadie corra el pre-commit.
    """
    process = subprocess.run(
        [sys.executable, 'scripts/check_escape_sequences.py'],
        capture_output=True, text=True,
    )
    assert process.returncode == 0, process.stderr
    assert 'archivos del árbol' in process.stdout
