#!/usr/bin/env python3
"""
lint_agents.py — delega en el gate de thyrox; aquí no vive una segunda copia.

Este archivo **era un fork** del gate. Su `PROHIBITED_FIELDS` incluía `model`,
y `model-selection-subagents.md` —siempre cargada— **exige** `model` con un
identificador del catálogo en toda definición de agente. El gate contradecía al
gobierno vigente, y la contradicción estuvo invisible porque el hook lo invoca
con `|| true`: un exit distinto de 0 se leía como verde (:ref:`h-docs-1057`).

Corregido 2026-09-07T00:01:24 bajo la directiva del ejecutor de resolver
en el mismo pase. El veredicto lo emite **el gate de thyrox**, que es el
proveedor: `thyrox/src/verify/lint_agents.py`, cuyo esquema sombra de 20 claves
admite `model` y sí rechaza lo que el cliente ignora.

Sin thyrox alcanzable **NO se emite un veredicto**: se rehúsa con exit 2. Un 0
aquí no distinguiría «ninguna definición incumple» de «no pude medir», que es
el
sub-patrón D de `metrica-decide-la-conclusion.md`.
"""
import os
import pathlib
import subprocess
import sys


def gate_de_thyrox():
    """La ruta del gate del proveedor — variable declarada, luego hermano."""
    declarada = os.environ.get('THYROX_ROOT')
    candidatas = []
    if declarada:
        candidatas.append(pathlib.Path(declarada))
    # Clon hermano: <arbol>/thyrox junto a <arbol>/kaupamex-*.
    candidatas.append(pathlib.Path(__file__).resolve().parents[3] / 'thyrox')
    for raiz in candidatas:
        gate = raiz / 'src' / 'gates' / 'lint_agents.py'
        if gate.is_file():
            return gate
    return None


def main(argv):
    gate = gate_de_thyrox()
    if gate is None:
        print(
            'FATAL: no se encontró thyrox/src/verify/lint_agents.py.',
            file=sys.stderr,
        )
        print(
            '       Declara THYROX_ROOT o clona thyrox como hermano.',
            file=sys.stderr,
        )
        print(
            '       NO se emite veredicto: un 0 aquí sería un verde falso.',
            file=sys.stderr,
        )
        return 2
    objetivos = argv[1:] or [
        str(pathlib.Path(__file__).resolve().parents[1] / 'agents')
    ]
    return subprocess.call([sys.executable, str(gate), *objetivos])


if __name__ == '__main__':
    sys.exit(main(sys.argv))
