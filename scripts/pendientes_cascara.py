#!/usr/bin/env python3
"""Qué falta portar de un addon — la lista lista para pegar en ``args``.

Origen: :ref:`h-api-372`. La campaña de DEC-FW-04 se ejecuta en corridas de
``Workflow`` que pueden morir a medias — por límite de tokens, por un agente
que revienta, por cierre de sesión. La pregunta que hay que poder contestar en
frío, sin leer un log ni confiar en la notificación de la corrida, es
**"¿qué falta?"**.

Este script la contesta **desde el disco**, que es el único estado que
sobrevive a todo: no lee journals, no lee reportes de agentes, no confía en el
``agents_error`` de la notificación. Compara los ``def`` de cada archivo de la
referencia contra el archivo homólogo nuestro y clasifica.

Por qué NO basta ``resumeFromRunId``
-------------------------------------

El resume reintenta lo que la corrida marcó como fallido. Medido en
``wf_28d45ea6-b88``: cuatro agentes murieron por límite, pero uno de ellos
—``controllers/session.py``— **había terminado de escribir y murió al
devolver**. El resume lo habría re-ejecutado: retrabajo puro sobre un archivo
ya completo. El disco lo sabía; la corrida no.

Un agente muerto no es trabajo perdido, y un agente vivo no garantiza trabajo
hecho. Sólo el disco lo dice.

Uso
---

    python3 scripts/pendientes_cascara.py web            # legible
    python3 scripts/pendientes_cascara.py web --args     # JSON para Workflow
    python3 scripts/pendientes_cascara.py web --args --limite 12
"""
import argparse
import ast
import json
import os
import sys

import sys as _s, os.path as _op
_s.path.insert(0, _op.dirname(_op.abspath(__file__)))
from reference_roots import tree as _tree
ODOO19C = str(_tree('odoo19c') / 'addons')
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from addons_roots import addon_path


def simbolos(ruta):
    """Nombres declarados en un archivo, por AST.

    **Por AST y no por substring.** La primera versión de este script comparaba
    ``nombre not in texto``, y eso dio un falso "completo" en
    ``web/controllers/session.py``: ``authenticate`` es substring de
    ``session_authenticate``, ``destroy`` de ``session_destroy``, ``logout`` de
    ``session_logout``. El archivo declaraba **cinco funciones sueltas** contra
    una ``class Session`` con nueve métodos, y el script lo dio por portado.

    Es el conteo generoso de ``porte-completo-no-parcial.md`` — construido
    dentro del instrumento escrito para evitarlo. Ver :ref:`h-api-373`.
    """
    try:
        arbol = ast.parse(open(ruta, encoding='utf-8', errors='ignore').read())
    except SyntaxError:
        return set()
    nombres = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            nombres.add(nodo.name)
        elif isinstance(nodo, ast.ClassDef):
            nombres.add('class:' + nodo.name)
    return nombres


def archivos_de_produccion(raiz):
    """Los ``.py`` del addon, sin ``tests/`` — ver H-API-370 para el porqué."""
    salida = []
    for dirpath, _, ficheros in os.walk(raiz):
        if '__pycache__' in dirpath or os.sep + 'tests' in dirpath + os.sep:
            continue
        for f in ficheros:
            if f.endswith('.py'):
                salida.append(os.path.relpath(os.path.join(dirpath, f), raiz))
    return sorted(salida)


def estado(addon):
    """Clasifica cada archivo de la referencia. Devuelve (pendientes, hechos)."""
    ref_raiz = os.path.join(ODOO19C, addon)
    mio_raiz = str(addon_path(addon) or '')
    if not os.path.isdir(ref_raiz):
        sys.exit(f"'{addon}' no existe en la referencia ({ref_raiz})")
    pendientes, hechos = [], []
    for rel in archivos_de_produccion(ref_raiz):
        de_ref = simbolos(os.path.join(ref_raiz, rel))
        if not de_ref:
            continue                      # __init__ vacíos y afines: nada que portar
        mio = os.path.join(mio_raiz, rel)
        if not os.path.exists(mio):
            pendientes.append((rel, len(de_ref), len(de_ref)))
            continue
        falta = de_ref - simbolos(mio)
        (pendientes if falta else hechos).append((rel, len(de_ref), len(falta)))
    return pendientes, hechos


def main():
    p = argparse.ArgumentParser()
    p.add_argument('addon')
    p.add_argument('--args', action='store_true',
                   help='emite el JSON de args para completar-cascara.js')
    p.add_argument('--limite', type=int, default=12,
                   help='cuántos archivos meter en el lote (default 12)')
    a = p.parse_args()

    pendientes, hechos = estado(a.addon)
    # Los más grandes primero: si el lote se corta, se cortó por lo barato.
    pendientes.sort(key=lambda x: -x[2])

    if a.args:
        print(json.dumps({'addon': a.addon,
                          'archivos': [r for r, _, _ in pendientes[:a.limite]]},
                         ensure_ascii=False))
        return

    print(f"{a.addon}: {len(hechos)} archivos completos · "
          f"{len(pendientes)} con símbolos ausentes")
    print(f"  símbolos ausentes en total: {sum(f for _, _, f in pendientes)}")
    if pendientes:
        print(f"\n  {'archivo':<44} {'ref':>5} {'falta':>6}")
        for rel, ref, falta in pendientes[:30]:
            print(f"  {rel:<44} {ref:>5} {falta:>6}")
        if len(pendientes) > 30:
            print(f"  … {len(pendientes) - 30} archivos más")
        print(f"\n  Siguiente lote:\n"
              f"    python3 scripts/pendientes_cascara.py {a.addon} --args")


if __name__ == '__main__':
    main()
