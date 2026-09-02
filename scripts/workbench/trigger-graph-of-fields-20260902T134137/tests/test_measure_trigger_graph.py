#!/usr/bin/env python3
"""Control del instrumento que censa el grafo de disparo.

Prueba el CLASIFICADOR, que es donde el censo puede mentir sin que se note:
una arista mal puesta en ``BY_INVERSE`` haria creer que el arbol de disparo
la puede recorrer, y la capa B de #273 se construiria sobre esa creencia.

Corre con el interprete del proyecto, no con el del sistema::

    uv run python scripts/workbench/trigger-graph-of-fields-20260902T134137/\
tests/test_measure_trigger_graph.py

Que lo haria fallar, que es lo que un control tiene que declarar
(``metrica-decide-la-conclusion.md``, sub-patron D):

- que ``classify`` metiera en ``BY_INVERSE`` una cadena cuyo peldano
  relacional oculta la vuelta (``related_name='+'``);
- que ``inverse_of`` devolviera un nombre para un campo que no es relacion;
- que el censo devolviera vacio sobre un arbol que si declara ``depends`` —
  un cero ahi no distingue «no hay edges» de «el instrumento no las ve».
"""
import os
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(RAIZ / 'src'))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')

import django  # noqa: E402

django.setup()

from django.db import models  # noqa: E402

import orm.fields  # noqa: F401,E402  — instala resolve_depends sobre el campo
from measure_trigger_graph import (  # noqa: E402
    SAME_MODEL,
    BY_SEARCH,
    BY_INVERSE,
    census,
    classify,
    diagnose,
    inverse_of,
)


class HiddenReverseProbe(models.Model):
    """Modelo de prueba: su FK oculta la vuelta con ``related_name='+'``."""

    towards = models.ForeignKey('base.ResCompany', models.CASCADE,
                              related_name='+', null=True)

    class Meta:
        app_label = 'base'
        managed = False


class VisibleReverseProbe(models.Model):
    """Modelo de prueba: su FK deja la vuelta navegable."""

    towards = models.ForeignKey('base.ResCompany', models.CASCADE,
                              related_name='sondas_visibles', null=True)

    class Meta:
        app_label = 'base'
        managed = False


def main():
    failures = []

    def check(condition, message):
        if not condition:
            failures.append(message)

    hidden_side = HiddenReverseProbe._meta.get_field('towards')
    visible_side = VisibleReverseProbe._meta.get_field('towards')

    # 1. La vuelta navegable se nombra; la hidden_side no.
    check(inverse_of(visible_side) == 'sondas_visibles',
              f'inverse_of(visible_side) devolvio {inverse_of(visible_side)!r}')
    check(inverse_of(hidden_side) is None,
              f'inverse_of(hidden_side) devolvio {inverse_of(hidden_side)!r}, esperaba None')

    # 2. Un campo que no es relacion no tiene vuelta.
    flat = VisibleReverseProbe._meta.get_field('id')
    check(inverse_of(flat) is None,
              f'inverse_of(no-relacion) devolvio {inverse_of(flat)!r}')

    # 3. El clasificador reparte los tres cubos.
    check(classify((flat,)) == SAME_MODEL,
              'una cadena de un peldano no es SAME_MODEL')
    check(classify((visible_side, flat)) == BY_INVERSE,
              'una cadena con vuelta navegable no es BY_INVERSE')
    check(classify((hidden_side, flat)) == BY_SEARCH,
              'una cadena con vuelta oculta no es BY_SEARCH')

    # 4. El censo no es un cero MUDO. Hoy da cero legitimamente —las dos
    #    declaraciones no estan unidas (#273 capa 0)—, asi que afirmar
    #    len(edges) > 0 seria un control que falla por el estado del arbol y
    #    no por el instrumento. Lo que si discrimina es la COHERENCIA entre el
    #    recorrido y el mapa que lo alimenta: hay edges exactamente cuando
    #    hay campos unidos. Un recorrido roto sobre un mapa poblado —o al
    #    reves— cae aqui, y el dia que la capa 0 aterrice este caso pasa a
    #    medir edges reales sin tocarlo.
    edges = census()
    d = diagnose()
    check(d['methods_with_depends'] > 0,
              'ningun metodo declara @api.depends: el instrumento dejo de '
              'verlos, o el arbol dejo de declararlos')
    check((len(edges) > 0) == (d['fields_joined'] > 0),
              f'incoherencia: {len(edges)} arista(s) contra '
              f'{d["fields_joined"]} campo(s) unido(s)')

    if failures:
        for f in failures:
            print(f'FALLA: {f}')
        return 1
    print(f'test_measure_trigger_graph: 7 aserciones OK — censo '
          f'{len(edges)} arista(s), {d["methods_with_depends"]} metodo(s) '
          f'con @api.depends, {d["fields_with_compute"]} campo(s) con compute=')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
