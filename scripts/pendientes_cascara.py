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
import json
import os
import re
import sys

ODOO19C = ('/home/user/odoo-tools/19.x/odoo-19.0/odoo-19.0/odoo-19.0/addons')
NUESTRO = 'src/addons'
RE_DEF = re.compile(r'^\s*def (\w+)', re.M)


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
    mio_raiz = os.path.join(NUESTRO, addon)
    if not os.path.isdir(ref_raiz):
        sys.exit(f"'{addon}' no existe en la referencia ({ref_raiz})")
    pendientes, hechos = [], []
    for rel in archivos_de_produccion(ref_raiz):
        texto_ref = open(os.path.join(ref_raiz, rel),
                         encoding='utf-8', errors='ignore').read()
        simbolos = RE_DEF.findall(texto_ref)
        if not simbolos:
            continue                      # __init__ vacíos y afines: nada que portar
        mio = os.path.join(mio_raiz, rel)
        if not os.path.exists(mio):
            pendientes.append((rel, len(simbolos), len(simbolos)))
            continue
        texto_mio = open(mio, encoding='utf-8', errors='ignore').read()
        falta = [s for s in simbolos if s not in texto_mio]
        (pendientes if falta else hechos).append((rel, len(simbolos), len(falta)))
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
