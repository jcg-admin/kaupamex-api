"""La fachada ``fields`` publica la superficie pública del ORM.

Es el test de la frontera que :ref:`h-api-604` corrigió: la referencia la
sostiene con **cero** cruces en sus 1 379 archivos de addon, y aquí se rompía
en seis puntos. Un ``import *`` sobre el agregador congelaba la superficie en
el instante del import, así que un campo publicado más tarde —el
``Serialized`` de ``base_sparse_field``, inyectado en ``ready()``— no llegaba
a la puerta pública.

Estos casos fijan las tres propiedades que el defecto violaba: que la fachada
exporte lo que la referencia exporta, que un addon pueda publicar en ella
después del arranque, y que ningún addon necesite cruzarla.
"""
import ast
import pathlib

import pytest

import fields

#: Los nombres que ``odoo19c: odoo/fields/__init__.py`` publica y este árbol ya
#: tiene. Los cinco restantes (``Field``, ``Id``, ``NO_ACCESS``, ``Domain``,
#: y en su día ``parse_field_expr``) llevan su veredicto en el docstring de la
#: fachada — dos son divergencia/bloqueo declarados, uno tiene sucesor abierto.
PUBLIC_SURFACE = (
    'Boolean', 'Json',
    'Integer', 'Float', 'Monetary',
    'Char', 'Text', 'Html',
    'Selection',
    'Date', 'Datetime',
    'Many2one', 'Many2many', 'One2many',
    'Many2oneReference', 'Reference',
    'Properties', 'PropertiesDefinition',
    'Binary', 'Image',
    'Command',
    'parse_field_expr',
)

#: Campo NUESTRO: la referencia no lo tiene, pero es un campo y entra por la
#: misma puerta. Sus cinco consumidores lo usan como ``fields.NonStored``.
OWN_SURFACE = ('NonStored',)

#: Publicados por ``base_sparse_field`` en su ``ready()``, no por el núcleo
#: (≙ ``fields.Serialized = Serialized`` en la cola de su ``models/fields.py``).
INJECTED_SURFACE = ('Serialized', 'Sparse')


@pytest.mark.parametrize('name', PUBLIC_SURFACE + OWN_SURFACE)
def test_facade_exports_the_public_surface(name):
    """Cada nombre de la superficie es alcanzable como ``fields.<name>``."""
    assert hasattr(fields, name), (
        f'{name} no está en la fachada; un addon tendría que cruzar la '
        f'frontera para usarlo'
    )


@pytest.mark.parametrize('name', INJECTED_SURFACE)
def test_addon_can_publish_into_the_facade_after_startup(name):
    """Lo inyectado en ``ready()`` llega a la puerta pública.

    Éste es el caso que fallaba: con ``from orm.fields import *`` la fachada
    congelaba su superficie antes de que corriera el ``ready()`` del addon, y
    el campo quedaba visible sólo en el módulo de implementación.
    """
    assert hasattr(fields, name), (
        f'{name} lo publica base_sparse_field en ready(); si no está aquí, '
        f'la inyección apunta a la capa equivocada (H-API-604)'
    )


def test_facade_does_not_import_with_star():
    """La fachada importa de cada módulo definidor, como la referencia.

    Un ``import *`` esconde la procedencia de cada nombre y congela la
    superficie. ``odoo19c: odoo/fields/__init__.py`` no lo usa: enumera sus
    doce módulos de origen uno por uno.
    """
    arbol = ast.parse(pathlib.Path(fields.__file__).read_text())
    estrellas = [
        nodo.module
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.ImportFrom)
        for alias in nodo.names
        if alias.name == '*'
    ]
    assert estrellas == [], f'import * sobre {estrellas}'


def test_no_addon_crosses_the_facade_boundary():
    """Ningún archivo de ``addons/`` importa de la capa de implementación.

    *Métrica:* ``from orm.fields…`` / ``from orm.commands`` en el AST de cada
    ``.py`` bajo ``addons/``.
    *Ciega a:* un import construido en tiempo de ejecución
    (``importlib.import_module('orm.fields')``), que no aparece como nodo
    ``ImportFrom`` — exactamente la vía que ``base_sparse_field`` usa para
    publicar, y que por eso no cuenta como cruce.
    """
    raiz = pathlib.Path(__file__).resolve().parents[3] / 'addons'
    prohibidos, medidos = [], 0
    for ruta in raiz.rglob('*.py'):
        if 'migrations' in ruta.parts:
            continue
        medidos += 1
        try:
            arbol = ast.parse(ruta.read_text())
        except SyntaxError:                       # pragma: no cover
            continue
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.ImportFrom) and nodo.module and (
                nodo.module.startswith('orm.fields')
                or nodo.module == 'orm.commands'
            ):
                prohibidos.append(f'{ruta.relative_to(raiz)}: {nodo.module}')

    assert prohibidos == [], (
        f'{len(prohibidos)} cruce(s) de la frontera sobre {medidos} archivos '
        f'medidos: {prohibidos}'
    )
