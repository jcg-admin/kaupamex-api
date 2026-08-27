"""``fields.Html`` tiene identidad de clase sin cambiar la columna (H-API-700).

Hasta la tarea #554 ``Html`` era un alias pelado de ``TextField``
(``orm/fields_textual.py``): en runtime un campo HTML era indistinguible de un
``Text``, y ``Website._get_html_fields`` lo rodeaba parseando el fuente por
AST. La referencia distingue el tipo por catálogo — ``ttype = 'html'`` en
``ir.model.fields`` (``odoo19c: addons/website/models/website.py:1883-1908``) —
y la subclase es aquí el equivalente mínimo que habilita ``isinstance``.

Estos casos fijan los tres invariantes del cambio: (a) ``isinstance`` distingue
``Html`` de ``Text``; (b) un modelo existente conserva su columna ``TEXT``;
(c) la deconstrucción sigue apuntando a ``django.db.models.TextField``, que es
lo que deja ``makemigrations --check`` en *No changes detected*.
"""
from django.apps import apps
from django.db import connection, models

import fields
from orm.fields_textual import Html, Text


def test_isinstance_tells_html_apart_from_text():
    """Un campo ``Html`` ya no es indistinguible de un ``Text``.

    Es la propiedad que el alias no podía dar: con ``Html = TextField``,
    ``isinstance`` sobre un campo ``Text`` también daba ``True``.
    """
    html_field = fields.Html(blank=True, default='')
    text_field = Text(blank=True, default='')

    assert isinstance(html_field, Html)
    assert not isinstance(text_field, Html), (
        'un Text pasa como Html: la clase sigue siendo un alias (H-API-700)'
    )
    # La otra dirección se conserva: todo Html sigue siendo un TextField.
    assert isinstance(html_field, models.TextField)


def test_facade_html_is_the_subclass():
    """La fachada ``fields`` publica la subclase, no el alias viejo."""
    assert fields.Html is Html
    assert issubclass(fields.Html, models.TextField)
    assert fields.Html is not models.TextField


def test_existing_model_keeps_its_text_column():
    """``ResCompany.report_header`` sigue siendo columna ``TEXT``.

    ``db_type`` sólo consulta el mapa de tipos del backend — no abre conexión —
    así que el caso es lógica pura contra el modelo real ya registrado.
    """
    report_header = apps.get_model('base', 'ResCompany')._meta.get_field(
        'report_header')

    assert isinstance(report_header, Html)
    assert report_header.get_internal_type() == 'TextField'
    assert report_header.db_type(connection) == Text(
        blank=True, default='').db_type(connection)


def test_deconstruct_points_to_textfield():
    """La deconstrucción conserva la ruta del alias.

    Las migraciones existentes se generaron con ``Html = TextField``; si la
    subclase deconstruyera con su propia ruta, ``makemigrations`` propondría un
    ``AlterField`` por cada campo HTML del árbol.
    """
    _name, path, args, kwargs = fields.Html(
        blank=True, default='').deconstruct()

    assert path == 'django.db.models.TextField'
    assert args == []
    assert kwargs == {'blank': True, 'default': ''}
