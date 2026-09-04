#!/usr/bin/env python3
"""Gate — todo modelo nuestro tiene su etiqueta y el bloque que la calcula.

≙ que ``display_name`` y sus cuatro compañeros —``_compute_display_name``,
``_search_display_name``, ``name_create`` y ``name_search``— cuelguen de
``BaseModel`` (``odoo19c: odoo/orm/models.py:473,1425-1543``): allá **todo**
modelo los tiene sin declarar nada.

Aquí la universalidad se recupera con la misma pareja de vías que ``H-API-577``
estableció para el registro por nombre: la base común los trae por herencia
(``orm.models.DisplayNameMixin`` vía ``TimeStampedModel``), y
:func:`orm.model_classes.adopt_display_name` los instala sobre
``class_prepared`` en los que no la heredan.

Por qué el gate y no sólo las dos vías
=======================================

Un modelo que declara **uno** de los cinco símbolos por su cuenta esquiva al
adoptador para ese símbolo, y ahí el olvido no falla: la etiqueta se cae al
``__str__`` de Django y nadie lo nota, porque `str()` siempre devuelve algo.
Es *el verde que no discrimina* de ``metrica-decide-la-conclusion.md``.

Qué lo haría fallar
===================

Declarar ``display_name`` como método o ``property`` en vez de dejar el campo
del mixin — que es exactamente lo que hacían once modelos antes de la tarea
#134. La prueba de que el gate discrimina está en
``tests/unit/orm/test_display_name.py``: rebasa un modelo real a una
``property`` y comprueba que el gate lo nombra.

*Métrica:* modelos concretos de ``apps.get_models()`` a los que les falta
alguno de los cinco símbolos, o cuyo ``display_name`` no es el descriptor
``NonStored`` del mixin; excluidos los de terceros por su módulo.
*Ciega a:* un ``_compute_display_name`` propio que devuelva algo inútil —el
gate mide que el símbolo esté y que el campo sea el descriptor, no qué calcula
el cómputo. Y ciega a un modelo de terceros, que el adoptador no toca por
diseño.

Uso::

    python3 scripts/check_display_name.py
"""
import os
import pathlib
import sys

import django

#: Los prefijos de módulo que NO son nuestros. Se declaran aquí y en
#: ``orm/model_classes.py``, y el gate lo verifica: si divergieran, el barrido
#: adoptaría un conjunto y el gate mediría otro.
THIRD_PARTY_MODULE_PREFIXES = ('django.', 'rest_framework')


def _setup():
    """Arranca Django con los settings de pruebas, desde la raíz del repo."""
    raiz = pathlib.Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(raiz / 'src'))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
    django.setup()


def _ours():
    """Los modelos concretos nuestros, en el orden de ``apps.get_models()``."""
    from django.apps import apps

    return [m for m in apps.get_models()
            if not m._meta.abstract and not m._meta.proxy
            and not m.__module__.startswith(THIRD_PARTY_MODULE_PREFIXES)]


def offenders():
    """Los modelos a los que les falta alguno de los cinco, como líneas."""
    from orm.model_classes import DISPLAY_NAME_SYMBOLS

    fuera = []
    for model in _ours():
        faltantes = [n for n in DISPLAY_NAME_SYMBOLS
                     if getattr(model, n, None) is None]
        if faltantes:
            fuera.append(f'{model._meta.label}: sin {", ".join(faltantes)}')
    return fuera


def not_a_field():
    """Los modelos cuyo ``display_name`` no es el descriptor, como líneas.

    El segundo eje, y el que discrimina de verdad: el primero mide *"existe"*,
    y una ``property`` propia existe. La fuente declara ``display_name`` como
    **campo**, así que admite asignación (``lot.display_name = name``, en
    ``odoo19c: product_expiry/models/production_lot.py:35``); una ``property``
    de sólo lectura la rechaza, y el override que la asigna revienta.
    """
    from orm.fields_nonstored import NonStored

    fuera = []
    for model in _ours():
        for base in model.mro():
            if 'display_name' in vars(base):
                if not isinstance(vars(base)['display_name'], NonStored):
                    fuera.append(
                        f'{model._meta.label}.display_name es '
                        f'{type(vars(base)["display_name"]).__name__} declarado '
                        f'en {base.__name__}, no el campo NonStored del mixin — '
                        f'el cómputo va en _compute_display_name')
                break
    return fuera


def main():
    _setup()
    from orm.model_classes import THIRD_PARTY_MODULE_PREFIXES as OTROS

    if OTROS != THIRD_PARTY_MODULE_PREFIXES:
        print('ERROR — la lista de prefijos de terceros diverge entre el gate '
              'y orm/model_classes. NO se emite conteo: un 0 aquí mediría '
              'un conjunto distinto del que el barrido adopta.', file=sys.stderr)
        return 2

    fuera = offenders()
    no_campo = not_a_field()
    alcance = f'alcance medido: {len(_ours())} modelo(s) concreto(s) nuestro(s)'
    if fuera:
        for line in fuera:
            print(line)
        print(f'\nFAIL: {len(fuera)} modelo(s) sin el bloque de display_name '
              f'({alcance}).')
        print('  Lo instala orm.model_classes.adopt_display_name sobre '
              'class_prepared;\n  si un modelo queda fuera, es que declaró el '
              'símbolo por su cuenta.')
    if no_campo:
        for line in no_campo:
            print(line)
        print(f'\nFAIL: {len(no_campo)} modelo(s) con display_name que no es el '
              f'campo ({alcance}).')
        print('  La fuente lo declara campo y el cómputo aparte '
              '(porte-completo-no-parcial.md:\n  «el guion bajo se porta»). '
              'Renombrar el override a _compute_display_name.')
    if fuera or no_campo:
        return 1
    print(f'OK: todo modelo nuestro tiene su etiqueta y su bloque ({alcance}).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
