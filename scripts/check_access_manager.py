#!/usr/bin/env python3
"""Gate — todo modelo nuestro resuelve las cuatro formas de permiso.

≙ que ``check_access``, ``has_access``, ``_check_access`` y
``_filtered_access`` cuelguen de ``BaseModel``
(``odoo19c: odoo/orm/models.py:4100-4135``): allá **todo** modelo las tiene
sin declarar nada. Aquí las lleva un ``Manager``, y la universalidad la
recupera :func:`orm.model_classes.adopt_access_manager` sobre la señal
``class_prepared``.

Por qué el gate y no sólo la señal
==================================

La señal cubre al modelo que no declara manager propio. **Un modelo que sí lo
declara la esquiva**, y ahí el olvido no falla: el modelo queda sin las cuatro
formas y nada lo delata hasta que alguien las llama. Es el mismo modo de
fallo que ``metrica-decide-la-conclusion.md`` llama *el verde que no
discrimina* — la suite pasa igual, porque nadie pregunta.

Medido al cablearlo: **8** de los 382 modelos concretos quedaban fuera, y uno
de ellos era nuestro (``account.AccountTax``, con ``AccountTaxQuerySet`` sobre
``models.QuerySet``). Los otros siete son de terceros y son la exclusión
declarada.

Qué lo haría fallar
===================

Declarar un manager propio sobre ``models.Manager`` en vez de sobre
``AccessManager`` — que es exactamente lo que ``AccountTax`` hacía. La prueba
de que el gate discrimina está en ``tests/unit/orm/test_access_manager.py``:
rebasa un modelo real a ``models.Manager`` y comprueba que el gate lo nombra.

El segundo eje: un manager declarado NO puede quedar eclipsado
================================================================

El eje de arriba mide *"resuelve las cuatro formas"* y **no discrimina cuál**
manager las trae. ``Options.managers`` recorre el MRO por profundidad y se
queda con el **primer** manager de cada nombre
(``django/db/models/options.py``, ``seen_managers``), así que un manager
colgado de una base genérica eclipsa al de una base especializada declarada
más abajo — y como el eclipsante también deriva de ``AccessManager``, el
primer eje sigue en verde.

Medido: al colgar ``objects = AccessManager()`` de ``TimeStampedModel``,
``crm.ContactMessage`` pasó a resolver ``ManagerFromAccessQuerySet`` en vez de
``SoftDeleteManager`` —una fila borrada volvía a ser visible— y **este gate
publicó OK**. Ocho casos de integración en rojo que el gate no vio. Ver
:ref:`h-api-876`.

Por eso el segundo eje: para cada nombre de manager, el que resuelve tiene que
ser instancia de **todos** los declarados con ese nombre en el MRO. Si dos
bases declaran clases incomparables, el gate lo nombra: es una ambigüedad que
decide una persona, no la profundidad del MRO.

*Métrica:* modelos concretos de ``apps.get_models()`` cuyo ``_default_manager``
no devuelve un ``AccessQuerySet``, excluidos los de terceros por su módulo; más
los que resuelven un manager que no es instancia de alguno declarado con ese
nombre en su MRO.
*Ciega a:* un manager que **herede** de ``AccessManager`` y sobreescriba
``get_queryset`` devolviendo otra cosa — tendría las cuatro formas en el
manager y no en el recordset. No se ha observado ninguno. Y ciega al eclipse
entre dos managers de la **misma** clase: son intercambiables por construcción.

Uso::

    python3 scripts/check_access_manager.py
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


def offenders():
    """Los modelos nuestros sin ``AccessQuerySet``, como lista de etiquetas."""
    from django.apps import apps
    from orm.models import AccessQuerySet

    fuera = []
    for model in apps.get_models():
        if model._meta.abstract or model._meta.proxy:
            continue
        if model.__module__.startswith(THIRD_PARTY_MODULE_PREFIXES):
            continue
        if not isinstance(model._default_manager.get_queryset(), AccessQuerySet):
            fuera.append(model._meta.label)
    return fuera


def shadowed():
    """Managers declarados que el MRO eclipsa, como lista de líneas.

    Para cada nombre, el manager que ``Options.managers`` resuelve debe ser
    instancia de **cada** clase declarada con ese nombre en el MRO. Si no lo
    es, una base declaró un manager que el modelo no está usando.
    """
    from django.apps import apps

    fuera = []
    for model in apps.get_models():
        if model._meta.abstract or model._meta.proxy:
            continue
        if model.__module__.startswith(THIRD_PARTY_MODULE_PREFIXES):
            continue
        resueltos = {m.name: type(m) for m in model._meta.managers}
        for base in model.mro():
            if not hasattr(base, '_meta'):
                continue
            for declarado in base._meta.local_managers:
                gana = resueltos.get(declarado.name)
                if gana is None or issubclass(gana, type(declarado)):
                    continue
                fuera.append(
                    f'{model._meta.label}.{declarado.name}: resuelve '
                    f'{gana.__name__} y eclipsa a {type(declarado).__name__}, '
                    f'declarado en {base.__name__}')
    return fuera


def main():
    _setup()
    from django.apps import apps
    from orm.model_classes import THIRD_PARTY_MODULE_PREFIXES as OTROS

    if OTROS != THIRD_PARTY_MODULE_PREFIXES:
        print('ERROR — la lista de prefijos de terceros diverge entre el gate '
              'y orm/model_classes. NO se emite conteo: un 0 aquí mediría '
              'un conjunto distinto del que el barrido adopta.', file=sys.stderr)
        return 2

    fuera = offenders()
    eclipsados = shadowed()
    concretos = [m for m in apps.get_models() if not m._meta.abstract]
    alcance = f'alcance medido: {len(concretos)} modelo(s) concreto(s)'
    if fuera:
        for label in fuera:
            print(f'{label}: su manager por defecto no devuelve un '
                  f'AccessQuerySet — sin las cuatro formas de permiso')
        print(f'\nFAIL: {len(fuera)} modelo(s) sin AccessManager ({alcance}).')
        print('  Un manager propio debe derivar de models.AccessManager, y su '
              'QuerySet\n  de models.AccessQuerySet. Sin manager propio lo pone '
              'la señal sola.')
    if eclipsados:
        for line in eclipsados:
            print(line)
        print(f'\nFAIL: {len(eclipsados)} manager(s) declarado(s) que el MRO '
              f'eclipsa ({alcance}).')
        print('  Options.managers se queda con el PRIMERO por profundidad de '
              'MRO.\n  Retirar el manager de la base genérica, o declararlo en '
              'el modelo.')
    if fuera or eclipsados:
        return 1
    print(f'OK: todo modelo nuestro resuelve las cuatro formas y ninguna base '
          f'queda eclipsada ({alcance}).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
