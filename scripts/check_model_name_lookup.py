#!/usr/bin/env python3
"""Gate — un modelo concreto no puede colisionar con la sintaxis de *lookup*.

Django lo declara en ``_check_model_name_db_lookup_clashes``
(``django/db/models/base.py:2072-2094``), y son **dos** reglas, no una:

===========  ==========================================  ==========================
Código       Condición (verbatim de la fuente)           Por qué
===========  ==========================================  ==========================
``E023``     ``name.startswith("_") or endswith("_")``   choca con la sintaxis de
                                                         *lookup* de consultas
``E024``     ``LOOKUP_SEP in name`` (``__``)             misma colisión, otra forma
===========  ==========================================  ==========================

Se implementan las dos porque la fuente declara las dos, en el mismo método y
por la misma razón (``porte-completo-no-parcial.md``). En Django son
excluyentes —un ``elif``—; aquí también.

Por qué existe este gate, y no basta con que Django ya lo compruebe
===================================================================

Porque ``models.E023`` **sólo se ve al correr la suite entera**. El modelo
ofensor de :ref:`h-api-751` vivía en ``tests/unit/service/`` y hacía fallar un
caso de ``tests/unit/orm/``: se registra en el registro global de apps al
importarse su módulo, así que en aislamiento no reproduce. Un pre-commit que lo
vea en el archivo en *staging* corta el ciclo antes de que llegue a esa
distancia.

Cómo decide qué es un modelo concreto
======================================

Resolución **transitiva dentro del archivo** más un conjunto de raíces medido
sobre el árbol (``TimeStampedModel`` 266 · ``models.Model`` 113 ·
``TransientModel`` 35 · ``SoftDeleteModel`` 7). La transitividad no es un
adorno: el caso real era ``class _Model(_Base)`` con ``_Base(models.Model)``
abstracta **en el mismo archivo**, así que un emparejador que sólo mirara
``models.Model`` en las bases habría sido ciego justo al defecto que motiva el
gate.

*Métrica:* clases cuya cadena de bases llega a una raíz de modelo **dentro del
mismo archivo**, sin ``abstract = True`` en su ``Meta``.
*Ciega a:* una clase cuya base de modelo se importa de otro módulo bajo un
nombre que no está en las raíces — no se resuelve el import. Es una **cota
inferior**: un 0 no prueba que no quede ninguna, prueba que no queda de las que
este instrumento sabe ver.

Uso::

    python3 scripts/check_model_name_lookup.py                # todo el árbol
    python3 scripts/check_model_name_lookup.py <archivos>     # sólo esos
"""
import ast
import pathlib
import sys

#: Raíces de modelo, medidas sobre las bases que el árbol declara de verdad.
#: ``Model`` es la del ORM espejado (``src/orm``), de la que ``TransientModel``
#: desciende; ``models.Model`` es la de Django directa.
MODEL_ROOTS = frozenset({
    'models.Model',
    'Model',
    'TimeStampedModel',
    'TransientModel',
    'SoftDeleteModel',
})

#: Dónde se busca cuando no se piden rutas. ``tests`` entra a propósito: el
#: modelo de :ref:`h-api-751` vivía ahí, y el registro de apps no distingue.
DEFAULT_ROOTS = ('src', 'addons', 'tests')

#: El separador de *lookup* de Django (``django.db.models.constants``).
LOOKUP_SEP = '__'


def _is_abstract(node):
    """¿La clase declara ``abstract = True`` en su ``Meta``?

    Las abstractas nunca llegan al check de Django —no entran en
    ``apps.get_models()``—, así que un ``_Base`` abstracto es legal.
    """
    for hijo in node.body:
        if not (isinstance(hijo, ast.ClassDef) and hijo.name == 'Meta'):
            continue
        for stmt in hijo.body:
            if not isinstance(stmt, ast.Assign):
                continue
            for objetivo in stmt.targets:
                if (isinstance(objetivo, ast.Name)
                        and objetivo.id == 'abstract'
                        and isinstance(stmt.value, ast.Constant)
                        and stmt.value.value is True):
                    return True
    return False


def _offending_reason(name):
    """El motivo por el que Django rechazaría el nombre, o ``None``.

    El orden reproduce el ``if/elif`` de la fuente: E023 gana a E024.
    """
    if name.startswith('_') or name.endswith('_'):
        return ('models.E023', 'no puede empezar ni terminar en guion bajo')
    if LOOKUP_SEP in name:
        return ('models.E024', 'no puede contener doble guion bajo')
    return None


def scan_file(path):
    """Devuelve las infracciones de un archivo: ``(linea, clase, codigo, motivo)``."""
    try:
        arbol = ast.parse(path.read_text(encoding='utf-8'))
    except (SyntaxError, UnicodeDecodeError):
        return []

    model_classes = set()
    findings = []
    # Recorrido en orden de aparición: una clase sólo puede heredar de otra ya
    # definida antes en el mismo módulo, así que una pasada basta.
    for node in ast.walk(arbol):
        if not isinstance(node, ast.ClassDef):
            continue
        bases = {ast.unparse(b) for b in node.bases}
        if not (bases & MODEL_ROOTS or bases & model_classes):
            continue
        model_classes.add(node.name)
        if _is_abstract(node):
            continue
        reason = _offending_reason(node.name)
        if reason:
            findings.append((node.lineno, node.name, *reason))
    return findings


def _targets(argv):
    if argv:
        return [pathlib.Path(a) for a in argv if a.endswith('.py')]
    archivos = []
    for raiz in DEFAULT_ROOTS:
        base = pathlib.Path(raiz)
        if base.is_dir():
            archivos += [p for p in base.rglob('*.py') if 'migrations' not in p.parts]
    return archivos


def main(argv):
    archivos = _targets(argv)
    total = 0
    for path in archivos:
        if not path.is_file():
            continue
        for lineno, clase, codigo, motivo in scan_file(path):
            total += 1
            print(f'{path}:{lineno}: [{codigo}] el modelo concreto '
                  f'{clase!r} {motivo} — choca con la sintaxis de lookup')

    alcance = f'alcance medido: {len(archivos)} archivos'
    if total:
        print(f'\nFAIL: {total} modelo(s) con nombre ilegal ({alcance}).')
        print('  Django lo rechaza en checks; renombrar sin el guion bajo. Si la'
              ' clase es de apoyo\n  y no debe ser un modelo concreto, declarar'
              ' abstract = True en su Meta.')
        return 1
    print(f'OK: ningún modelo concreto choca con el lookup ({alcance}).')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
