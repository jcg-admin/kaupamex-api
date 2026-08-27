#!/usr/bin/env python3
"""Gate: un archivo que se declara fiel a la referencia lo es, o lo declara.

Cierra la tarea #75 (:ref:`h-api-815`). Nace de una cifra: de **442** archivos
que declaran fidelidad en un docstring, **257** tienen par en la referencia y
**205 de esos 257 — el 79 %** entregan menos de lo que dicen, con 4040 símbolos
ausentes. ``res_device.py`` no era la excepción, era la norma.

La declaración es prosa y ningún gate la miraba. Este la cruza con el veredicto
que ``check_porte_completo.py`` ya sabe emitir.

Qué mira
========

Un archivo entra al alcance cuando **declara fidelidad** en el docstring de su
módulo o de alguna de sus clases. Falla cuando además ``check_porte_completo``
le encuentra hallazgos y no está en el baseline.

Por qué por AST y no por grep
==============================

El primer instrumento fue ``grep -rlE "Adaptación fiel"`` con un ``.`` en lugar
de la tilde, y devolvió **0**: en UTF-8 la ``ó`` son dos bytes y ``.`` casa uno.
La misma palabra buscada sin comodín encontró 126 ocurrencias. Un grep de prosa
por su forma superficial es justo el defecto que este gate mide en otros.

Y no hay una cadena, hay seis, medidas: ``Adaptación fiel`` 126 ·
``Portación fiel`` 25 · ``Fiel a`` 18 · ``Portacion fiel`` (sin tilde) 15 ·
``Scaffold fiel`` 5 · ``adaptado VERBATIM`` 1. Por eso el discriminador es la
**palabra** ``fiel``/``verbatim`` dentro de un docstring, no una plantilla.

Deuda heredada congelada, no barrida
=====================================

Los incumplidores del día que se cableó viven en
``fidelidad_declarada_baseline.txt``. Uno listado no bloquea; uno nuevo sí. Al
cerrar el porte de un archivo —o al declarar sus divergencias— se quita su
línea, para que el baseline no mienta sobre deuda que ya no existe.

Mismo criterio prospectivo que ``identificadores-en-ingles.md`` y
``atributos-de-clase-de-modelo.md``: se paga al tocar, no en un barrido.

Ciega a
=======

Los **185** archivos que declaran fidelidad y no tienen par medible: 137 viven
fuera de ``<addon>/models/`` —la única raíz que ``check_porte_completo``
empareja— y 48 dentro, sin archivo homónimo en la referencia porque son propios
del L0. Ninguno cuenta ni a favor ni en contra; esa mitad la cubre la tarea #52.

Y ciega a una declaración de fidelidad escrita en un comentario en vez de un
docstring, que el recorrido por AST no ve.
"""
import argparse
import ast
import pathlib
import re
import subprocess
import sys

RAICES = ('src', 'addons')
BASELINE = pathlib.Path(__file__).with_name('fidelidad_declarada_baseline.txt')
GATE_PORTE = pathlib.Path(__file__).with_name('check_porte_completo.py')

#: La palabra, no la plantilla — las seis formas medidas la comparten. Sin
#: mayúsculas/minúsculas: ``Fiel a`` abre 18 docstrings del árbol y un patrón
#: sensible a la caja los perdía en silencio. Lo destapó el propio test de este
#: gate, no una relectura.
FIDELIDAD = re.compile(r'\b(fiel|verbatim)\b', re.IGNORECASE)

#: Una línea de hallazgo de ``check_porte_completo``:
#: ``<addon>/models/<archivo>.py :: <Clase> — <TIPO> (<n>)``
HALLAZGO = re.compile(r'^(\S+\.py) :: (\S+) — (.+?) \((\d+)\)')


def declara_fidelidad(ruta):
    """¿El docstring del módulo o el de alguna clase declara fidelidad?"""
    try:
        arbol = ast.parse(ruta.read_text(encoding='utf-8'))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return False
    textos = [ast.get_docstring(arbol) or '']
    textos += [ast.get_docstring(n) or '' for n in arbol.body
               if isinstance(n, ast.ClassDef)]
    return bool(FIDELIDAD.search('\n'.join(textos)))


def clave(ruta):
    """La ruta tal como la nombra ``check_porte_completo``: ``<addon>/...``."""
    texto = ruta.as_posix()
    return texto.replace('src/addons/', '').replace('addons/', '')


def declarantes(raiz_repo):
    """Los archivos del árbol que declaran fidelidad, por su clave del gate."""
    encontrados = {}
    for raiz in RAICES:
        base = raiz_repo / raiz
        if not base.is_dir():
            continue
        for archivo in base.rglob('*.py'):
            texto = archivo.as_posix()
            if '/migrations/' in texto or '/tests/' in texto:
                continue
            if declara_fidelidad(archivo):
                encontrados[clave(archivo.relative_to(raiz_repo))] = archivo
    return encontrados


def hallazgos_del_porte(raiz_repo):
    """Los archivos a los que ``check_porte_completo`` encuentra hallazgo."""
    salida = subprocess.run(
        [sys.executable, str(GATE_PORTE)],
        cwd=raiz_repo, capture_output=True, text=True, timeout=1800).stdout
    conteo = {}
    for linea in salida.splitlines():
        casa = HALLAZGO.match(linea)
        if casa:
            archivo, _klass, tipo, n = casa.groups()
            if 'AUSENTE' in tipo:
                conteo[archivo] = conteo.get(archivo, 0) + int(n)
            else:
                conteo.setdefault(archivo, 0)
    return conteo


def carga_baseline():
    if not BASELINE.is_file():
        return set()
    return {l.strip() for l in BASELINE.read_text(encoding='utf-8').splitlines()
            if l.strip() and not l.lstrip().startswith('#')}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--strict', action='store_true',
                   help='exit 1 si hay incumplidores fuera del baseline')
    p.add_argument('--write-baseline', action='store_true',
                   help='congela los incumplidores de hoy')
    p.add_argument('--quiet', action='store_true')
    args = p.parse_args()

    raiz_repo = pathlib.Path(__file__).resolve().parent.parent
    declaran = declarantes(raiz_repo)
    con_hallazgo = hallazgos_del_porte(raiz_repo)
    incumplen = sorted(set(declaran) & set(con_hallazgo))

    if args.write_baseline:
        cabecera = (
            '# Archivos que DECLARAN fidelidad a la referencia y entregan\n'
            '# menos — congelados el dia que se cablo el gate (tarea #75,\n'
            '# hallazgo H-API-815). Uno listado no bloquea; uno NUEVO si.\n'
            '#\n'
            '# Al cerrar el porte de un archivo, o al declarar sus\n'
            '# divergencias en `divergencias_declaradas.txt`, se QUITA su\n'
            '# linea: un baseline que conserva deuda ya pagada miente.\n'
            '#\n'
            '# El conteo es de simbolos ausentes, no de hallazgos.\n\n')
        cuerpo = '\n'.join(f'{a}  # {con_hallazgo[a]}' for a in incumplen)
        BASELINE.write_text(cabecera + cuerpo + '\n', encoding='utf-8')
        print(f'baseline escrito: {len(incumplen)} archivo(s).')
        return 0

    base = carga_baseline()
    base_rutas = {l.split('#')[0].strip() for l in base}
    nuevos = [a for a in incumplen if a not in base_rutas]

    if not args.quiet:
        for a in nuevos:
            print(f'  {a}  — declara fidelidad y le faltan '
                  f'{con_hallazgo[a]} simbolo(s)')
    total_sym = sum(con_hallazgo[a] for a in incumplen)
    veredicto = 'FAIL' if (nuevos and args.strict) else 'OK'
    print(f'{veredicto}: {len(nuevos)} archivo(s) nuevo(s) con fidelidad falsa '
          f'(alcance medido: {len(declaran)} declaran fidelidad; '
          f'{len(incumplen)} incumplen con {total_sym} simbolo(s) ausentes; '
          f'{len(base_rutas)} en baseline)')
    return 1 if (nuevos and args.strict) else 0


if __name__ == '__main__':
    sys.exit(main())
