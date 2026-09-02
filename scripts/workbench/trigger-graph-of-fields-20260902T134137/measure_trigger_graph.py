#!/usr/bin/env python3
"""Censo del grafo de disparo: que edges campo->campo declara hoy el arbol.

Precede a la capa B de la tarea **#273** — ``_field_triggers`` y
``get_trigger_tree`` en ``src/orm/registry.py``—, que se construye
**invirtiendo** el grafo de ``field_depends``. Antes de invertirlo hay que
saber que hay que invertir, y eso no se puede suponer.

La fuente del mecanismo, leida y no recordada:

- ``odoo19c: odoo/orm/registry.py:644-668`` — ``_field_triggers`` guarda
  ``{campo_dependencia: {camino_invertido: {campos_dependientes}}}``. El camino
  se guarda **al reves** (``tuple(reversed(path))``) porque se recorre desde el
  modelo del que cambia towards el modelo del que depende.
- ``odoo19c: odoo/orm/models.py:6862-6923`` — ``_modified_triggers`` recorre ese
  camino. Para cada peldano busca un inverso en ``field_inverses``; **si no
  encuentra ninguno cae al ``else`` del ``for``** y navega con
  ``model.search([(field.name, 'in', real_records.ids)])``.

Esa ultima linea es la que corrigio la premisa de esta pieza: la vuelta
**siempre** existe. Un peldano sin inverso no bloquea el arbol de disparo — lo
encarece en una consulta. Por eso los cubos miden coste y no viabilidad, y por
eso el tercero se llama ``BY_SEARCH`` y no «sin vuelta».

*Metrica:* edges que ``Field.resolve_depends`` devuelve sobre
``apps.get_models()``, repartidas en tres cubos por como se recorre su vuelta.
*Ciega a:* lo declarado en ``manifest.json``, clave ``blind_to`` — en
particular, al ``domain`` del inverso, que la fuente si consulta
(``models.py:6883``) y este censo no.
"""
import collections
import os
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / 'src'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')

import django  # noqa: E402

#: Un solo peldano: el campo dependiente vive en el mismo modelo que su
#: dependencia, asi que no hay vuelta que recorrer.
SAME_MODEL = 'SAME_MODEL'

#: La vuelta se navega por el accesor inverso que Django ya deja puesto.
BY_INVERSE = 'BY_INVERSE'

#: La vuelta esta hidden_side (``related_name='+'``) y cuesta un ``search`` por
#: peldano — el ``else`` del ``for`` de ``_modified_triggers``.
BY_SEARCH = 'BY_SEARCH'


def inverse_of(field):
    """El nombre del accesor de vuelta de ``field``, o ``None`` si no lo hay.

    ≙ el papel de ``Registry.field_inverses`` (``odoo19c:
    odoo/orm/registry.py:506``) en este stack: alli el registro mantiene el
    mapa a mano porque su ORM no lo deriva; aqui lo deriva Django al ligar la
    relacion, asi que se lee del campo en vez de mantenerse.

    Tres casos, y el tercero es el que discrimina:

    - **relacion inversa** (``ForeignObjectRel``) — su vuelta es el campo de
      ida, que siempre existe.
    - **relacion de ida** con la vuelta visible — el accesor que Django genera.
    - **relacion de ida con ``related_name='+'``** — Django marca el inverso
      como oculto y no genera accesor. Ahi no hay vuelta que navegar.
    """
    remote = getattr(field, 'remote_field', None)
    if remote is None:
        return None
    if not getattr(field, 'concrete', True) and hasattr(field, 'field'):
        #: Lado inverso ya materializado: su vuelta es el campo de ida.
        return field.field.name
    #: ``hidden`` es una ``cached_property``, no un metodo:
    #: ``django/db/models/fields/reverse_related.py:64-67`` la declara asi y su
    #: cuerpo es ``bool(self.related_name) and self.related_name[-1] == '+'``.
    #: La primera version de este guion pregunto por ``is_hidden`` —el nombre
    #: de Django 4— con un ``getattr(..., None)`` que, al no encontrarlo,
    #: **saltaba la comprobacion en silencio** y devolvia ``'+'`` como si fuera
    #: un accesor. Es el sub-patron D: una guarda cuyo fallo no se distingue de
    #: su exito. Se pregunta por el nombre real, sin respaldo que lo enmascare.
    if remote.hidden:
        return None
    return remote.get_accessor_name()


def classify(field_sequence):
    """El bucket de una arista, dado el camino de campos que la resuelve.

    ``field_sequence`` es lo que ``Field.resolve_depends`` devuelve: la tupla
    de campos que recorre el nombre punteado, de ida. La vuelta que el motor
    recorrera son sus peldanos **salvo el ultimo**, que es la dependencia
    misma y no se navega.
    """
    if len(field_sequence) <= 1:
        return SAME_MODEL
    for step in field_sequence[:-1]:
        if inverse_of(step) is None:
            return BY_SEARCH
    return BY_INVERSE


def census():
    """Las edges del arbol, como ``(dependencia, camino, dependiente)``.

    El camino va **invertido**, igual que lo guarda ``_field_triggers``: es el
    orden en que ``_modified_triggers`` lo recorrera.
    """
    from django.apps import apps

    from orm import registry

    edges = []
    for model in apps.get_models():
        for field in model._meta.get_fields():
            if not registry.field_depends[field]:
                continue
            for dependency in field.resolve_depends(registry):
                *path, dep_field = dependency
                edges.append((dep_field, tuple(reversed(path)), field))
    return edges


def diagnose():
    """Por que el censo puede dar cero, sin que el cero sea mudo.

    ``field_depends`` une DOS declaraciones que viven en sitios distintos: el
    ``_depends`` que ``@api.depends`` deja en el **metodo**, y el ``compute``
    que el **campo** declara para nombrarlo. ``_DerivedCollector._build``
    (``src/orm/registry.py:473-481``) las junta por ahi.

    Si una de las dos falta, el mapa sale vacio y todo lo que se construya
    encima mide cero pasando verde. Este diagnostico separa los tres casos, y
    se imprime SIEMPRE — un cero sin el no distingue «no hay dependencias» de
    «no estan cableadas».
    """
    from django.apps import apps

    from orm import registry

    methods_with_depends = 0
    fields_with_compute = 0
    fields_joined = 0
    for model in apps.get_models():
        for name in dir(model):
            try:
                attribute = getattr(model, name)
            except Exception:
                continue
            if callable(attribute) and getattr(attribute, '_depends', None):
                methods_with_depends += 1
        for field in model._meta.get_fields():
            compute = getattr(field, 'compute', None)
            if compute:
                fields_with_compute += 1
            if registry.field_depends[field]:
                fields_joined += 1
    return {
        'methods_with_depends': methods_with_depends,
        'fields_with_compute': fields_with_compute,
        'fields_joined': fields_joined,
    }


def _label(field):
    """El nombre completo de un campo, para poder citarlo en el hallazgo."""
    model = getattr(field, 'model', None)
    owner = getattr(model, '__name__', '?') if model is not None else '?'
    return f'{owner}.{getattr(field, "name", field)}'


def main():
    django.setup()
    import orm.fields  # noqa: F401  — instala resolve_depends sobre el campo

    edges = census()
    buckets = collections.Counter()
    by_search = []
    for dep_field, path, field in edges:
        bucket = classify(tuple(path) + (dep_field,))
        buckets[bucket] += 1
        if bucket == BY_SEARCH:
            by_search.append((dep_field, path, field))

    total = len(edges)
    d = diagnose()
    print(f'=== grafo de disparo — {total} arista(s) ===')
    print(f'  metodos que declaran @api.depends : {d["methods_with_depends"]:>5}')
    print(f'  campos que declaran compute=      : {d["fields_with_compute"]:>5}')
    print(f'  campos que field_depends resuelve : {d["fields_joined"]:>5}')
    if total == 0:
        print('\n  El cero NO dice «no hay dependencias»: dice que las dos '
              'declaraciones\n  no estan unidas. @api.depends marca el METODO; '
              'el CAMPO tiene que\n  nombrarlo con compute= para que '
              '_DerivedCollector las junte.')
    for bucket in (SAME_MODEL, BY_INVERSE, BY_SEARCH):
        n = buckets[bucket]
        pct = (100.0 * n / total) if total else 0.0
        print(f'  {bucket:<14} {n:>5}  ({pct:.1f} %)')

    if by_search:
        print('\n--- las que costarian un search por peldano ---')
        for dep_field, path, field in by_search:
            path_labels = ' -> '.join(_label(s) for s in path) or '(directo)'
            print(f'  {_label(dep_field)}  via {path_labels}  dispara {_label(field)}')

    print('\nMetrica: edges que Field.resolve_depends devuelve sobre '
          'apps.get_models(), por como se recorre su vuelta.')
    print('Ciega a: el domain del inverso, el coste real de la consulta, y '
          'toda dependencia que resolve_depends no resuelve (ver manifest.json).')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
