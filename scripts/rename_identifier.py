#!/usr/bin/env python3
"""Renombra un identificador SIN tocar prosa — comentarios, docstrings ni cadenas.

Por que existe (:ref:`h-api-799`)
==================================

Este arbol mezcla, en el mismo archivo, **identificadores en ingles** y **prosa
en espanol**: es la regla (``identificadores-en-ingles.md``), no un accidente.
Un renombre con ``sed`` o ``re.sub`` no distingue las dos cosas, asi que cada
renombre reescribe tambien la prosa que usa esa palabra. Medido: tres episodios
en una sola sesion, y el tercero **quince minutos despues** de escribir el
metodo correcto.

Los intentos de acotar con regex fallan en las dos direcciones a la vez, y eso
tambien esta medido:

- un *lookahead* (``\\bhija\\b(?=[ ,).=])``) dejo **dos** ocurrencias sin
  renombrar —las seguidas de ``]`` y de fin de linea— mientras seguia danando
  la prosa;
- saltar lineas que empiezan por ``#`` o ``\"\"\"`` no ve el **interior** de un
  docstring de modulo, y encima salto una linea de codigo real por contener
  ``or ''``, dejando una variable muerta que devolvia siempre el respaldo.

Un patron mas fino no arregla el problema: lo reparte peor. Lo unico que lo
cierra es no mirar el texto, sino el arbol.

Como decide
===========

Recorre el AST y recoge la **posicion** de cada ``Name``, ``arg``,
``FunctionDef``, ``ClassDef``, ``keyword`` y ``Attribute`` cuyo identificador
coincide. Un comentario no esta en el AST; una cadena es ``Constant`` y no
lleva el nombre; un docstring es una cadena. Por construccion no pueden
tocarse.

Dos precondiciones medidas en este arbol
=========================================

1. **El interprete del proyecto** (``uv run python``, 3.12+), nunca el
   ``python3`` del sistema. Hasta 3.11 una f-string entera es un solo token
   ``STRING`` y su interior es invisible; en 3.12 el AST si entra
   (:ref:`h-api-607`). El guard de abajo lo verifica y **no emite conteo** si
   falla: un 0 ahi seria un verde falso.
2. **Reemplazo por posicion** sobre el texto original, nunca
   ``tokenize.untokenize``, que reformatea el archivo entero — medido: 424
   lineas de churn por 239 renombres.

Uso
===

    uv run python scripts/rename_identifier.py <viejo> <nuevo> <archivo>...
    uv run python scripts/rename_identifier.py --check <viejo> <archivo>...

``--check`` no escribe: solo publica cuantas ocurrencias hay y en que lineas.
Toda escritura verifica despues que **ninguna linea de comentario, docstring o
cadena cambio**, y aborta el archivo entero si alguna lo hizo.
"""
import argparse
import ast
import io
import sys
import token as token_mod
import tokenize
from pathlib import Path

#: Nodos cuyo identificador vive en un atributo distinto. El AST no da columna
#: para el nombre de un ``FunctionDef``/``ClassDef`` —``col_offset`` apunta al
#: ``def``— asi que esos se localizan con el flujo de tokens, no con el nodo.
_CAMPO_POR_NODO = {
    ast.Name: 'id',
    ast.arg: 'arg',
    ast.Attribute: 'attr',
    ast.keyword: 'arg',
    ast.FunctionDef: 'name',
    ast.AsyncFunctionDef: 'name',
    ast.ClassDef: 'name',
    ast.Global: None,        # lleva una lista de cadenas, sin posicion propia
    ast.Nonlocal: None,
}


def require_interpreter():
    """Aborta si el interprete no ve dentro de una f-string (< 3.12).

    NO emite conteo al fallar: un 0 aqui se leeria como "no hay ocurrencias"
    cuando lo cierto es "no pude verlas". Es el sub-patron D de
    ``metrica-decide-la-conclusion.md`` aplicado al propio instrumento.
    """
    if sys.version_info < (3, 12):
        print(
            f'ERROR — este renombrador necesita Python 3.12+; corriendo '
            f'{sys.version_info.major}.{sys.version_info.minor}.\n'
            f'Hasta 3.11 una f-string entera es un solo token STRING y su '
            f'interior es invisible para un renombre por posicion '
            f'(H-API-607). Usar: uv run python scripts/rename_identifier.py\n'
            f'NO se emite un conteo: un 0 aqui seria un verde falso.',
            file=sys.stderr)
        raise SystemExit(2)


def _posiciones_por_ast(source, old):
    """Posiciones ``(linea, columna)`` donde el AST declara el identificador."""
    arbol = ast.parse(source)
    encontradas = set()
    for nodo in ast.walk(arbol):
        campo = _CAMPO_POR_NODO.get(type(nodo))
        if campo is None or not hasattr(nodo, campo):
            continue
        if getattr(nodo, campo) != old:
            continue
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            continue        # su nombre se localiza por tokens, ver abajo
        if isinstance(nodo, ast.Attribute):
            # col_offset apunta al inicio de la expresion, no al atributo
            continue        # idem
        encontradas.add((nodo.lineno, nodo.col_offset))
    return encontradas


def _tokens_nombre(source, old):
    """Todos los tokens ``NAME`` con ese texto, con su posicion.

    El flujo de tokens localiza tambien lo que el AST no posiciona: el nombre
    de una funcion o clase, y el atributo de un ``Attribute``. Un comentario es
    ``COMMENT`` y una cadena es ``STRING``, asi que ninguno entra aqui.
    """
    salida = []
    lector = io.StringIO(source).readline
    for tok in tokenize.generate_tokens(lector):
        if tok.type == token_mod.NAME and tok.string == old:
            salida.append(tok.start)
    return salida


def posiciones(source, old):
    """Union de las dos vistas, que es el conjunto que se puede renombrar.

    El flujo de tokens es el que manda —ve todos los ``NAME``— y el AST
    confirma que el archivo parsea. Un ``NAME`` con ese texto nunca esta dentro
    de una cadena ni de un comentario: el tokenizador los clasifica aparte.
    """
    ast.parse(source)                       # falla temprano si no parsea
    return sorted(set(_tokens_nombre(source, old)))


#: Tipos de token cuyo texto ES prosa. ``FSTRING_MIDDLE`` existe desde 3.12:
#: en una f-string el literal se parte en trozos y lo interpolado sale como
#: ``NAME`` aparte, que es justo lo que hace renombrable el interior de una
#: f-string y no lo era hasta 3.11 (H-API-607).
_TIPOS_DE_PROSA = tuple(
    getattr(token_mod, nombre) for nombre in
    ('COMMENT', 'STRING', 'FSTRING_MIDDLE') if hasattr(token_mod, nombre))


def _prosa(source):
    """El texto de cada token de prosa, en orden.

    Se compara la SECUENCIA, no las lineas. Comparar lineas es demasiado
    grueso y da falso positivo: ``{'accion': accion}`` tiene en la misma linea
    una cadena que no debe cambiar y un nombre que si. Medido — la primera
    version de este control abortaba ese caso.
    """
    lector = io.StringIO(source).readline
    return [tok.string for tok in tokenize.generate_tokens(lector)
            if tok.type in _TIPOS_DE_PROSA]


def renombrar(source, old, new):
    """Devuelve ``(texto_nuevo, ocurrencias)``. No escribe."""
    lineas = source.splitlines(keepends=True)
    puntos = posiciones(source, old)
    # de atras hacia adelante: renombrar no desplaza lo que aun no se toco
    for fila, columna in reversed(puntos):
        l = lineas[fila - 1]
        assert l[columna:columna + len(old)] == old, (fila, columna, l)
        lineas[fila - 1] = l[:columna] + new + l[columna + len(old):]
    return ''.join(lineas), len(puntos)


def _prosa_intacta(antes, despues):
    """``(ok, danadas)`` — el control de que no se toco prosa.

    ``danadas`` lleva los pares ``(antes, despues)`` que difieren, para que el
    mensaje diga QUE cambio y no solo donde.
    """
    a, d = _prosa(antes), _prosa(despues)
    if len(a) != len(d):
        return False, [(f'{len(a)} tokens de prosa', f'{len(d)} despues')]
    danadas = [(x, y) for x, y in zip(a, d) if x != y]
    return not danadas, danadas


def main():
    require_interpreter()
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--check', action='store_true',
                   help='no escribe: solo cuenta y lista las lineas')
    p.add_argument('old')
    p.add_argument('new', nargs='?')
    p.add_argument('files', nargs='+')
    args = p.parse_args()

    if not args.check and args.new is None:
        p.error('falta <nuevo>; o usar --check')
    # con --check el segundo posicional es en realidad un archivo
    files = list(args.files)
    if args.check and args.new is not None:
        files.insert(0, args.new)

    total, tocados, fallidos = 0, 0, 0
    for ruta in files:
        camino = Path(ruta)
        antes = camino.read_text(encoding='utf-8')
        try:
            if args.check:
                puntos = posiciones(antes, args.old)
                if puntos:
                    lineas = sorted({f for f, _ in puntos})
                    print(f'{ruta}: {len(puntos)} en lineas '
                          f'{", ".join(map(str, lineas))}')
                total += len(puntos)
                continue

            despues, n = renombrar(antes, args.old, args.new)
            if not n:
                continue
            ok, danadas = _prosa_intacta(antes, despues)
            if not ok:
                print(f'{ruta}: ABORTADO — el renombre tocaria prosa: '
                      f'{danadas[:3]}', file=sys.stderr)
                fallidos += 1
                continue
            camino.write_text(despues, encoding='utf-8')
            print(f'{ruta}: {n} ocurrencia(s) {args.old} -> {args.new}')
            total += n
            tocados += 1
        except SyntaxError as exc:
            print(f'{ruta}: NO PARSEA — {exc}', file=sys.stderr)
            fallidos += 1

    verbo = 'encontradas' if args.check else 'renombradas'
    print(f'{total} ocurrencia(s) {verbo} en {tocados or len(files)} archivo(s) '
          f'(alcance medido: {len(files)} pedido(s), {fallidos} con error)')
    return 1 if fallidos else 0


if __name__ == '__main__':
    raise SystemExit(main())
