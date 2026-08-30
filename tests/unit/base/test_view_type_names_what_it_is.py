r"""El octavo tipo de vista se nombra por lo que ES, no por su intérprete.

Directiva del ejecutor 2026-08-30: *"no queremos conservar el valor 'qweb' del
tipo de vista, vamos a analizar cómo nombrarlo"*, aplicando el criterio de las
dos categorías —lo que el stack **trae** hecho frente a lo que deja
**construir**—.

**El precedente ya estaba decidido en este árbol, y es el mismo caso.**
``report_type`` retiró el prefijo ``qweb-`` con este argumento verbatim
(``ir_actions_report.py:146-152``): *"En ``qweb-pdf`` el par es (intérprete,
formato) … Escribir ``qweb-pdf`` afirmaría un sustrato que este árbol no
tiene"*. El ``type`` de la vista es el mismo par sin el segundo término: nombra
al intérprete y nada más.

**Por qué ``template`` y no otra palabra.** No se inventa: es el nombre que la
**propia referencia** usa en la superficie que un humano escribe. Su azúcar XML
es ``<template id="...">`` y su manejador ``_tag_template``
(``odoo19c: odoo/tools/convert.py:469,655``); sólo el valor almacenado dice
``qweb``. Nuestro ``tools/convert.py:797`` hace la misma sustitución.

*Métrica:* los tres consumidores del valor en este árbol y el manejador de
``<template>`` en las dos raíces.
*Ciega a:* las filas que una base de producción ya tenga con el valor viejo —
eso lo cubre la migración de datos, no este archivo.
"""
import inspect

import pytest
from django.db.utils import IntegrityError

from addons.web.models.ir_ui_view import get_view_info
from tools import convert
from addons.base.models.ir_ui_view import (
    VIEW_TYPE_CHOICES,
    VIEW_TYPE_TEMPLATE,
    IrUiView,
)


class TestTheValueNamesTheThingAndNotItsInterpreter:

    def test_the_eighth_type_is_template(self):
        assert VIEW_TYPE_TEMPLATE == 'template'

    def test_no_choice_names_an_interpreter(self):
        # Los otros siete nombran qué es la vista: list, form, graph, pivot,
        # calendar, kanban, search. El octavo ya no es la excepción.
        assert 'qweb' not in dict(VIEW_TYPE_CHOICES)

    def test_the_label_is_the_word_the_reference_authors_with(self):
        assert dict(VIEW_TYPE_CHOICES)[VIEW_TYPE_TEMPLATE] == 'Plantilla'

    def test_the_eight_types_stay_eight(self):
        assert len(VIEW_TYPE_CHOICES) == 8

    def test_the_field_offers_it(self):
        assert IrUiView(type=VIEW_TYPE_TEMPLATE).get_type_display() == 'Plantilla'


class TestTheThreeConsumersAgreeOnTheNewValue:
    """Lo que hace de este tipo el distinto: los tres sitios que lo discriminan."""

    def test_the_constraint_requires_a_key_for_this_type(self):
        # Es el único tipo que se resuelve por clave y no por (modelo, tipo).
        nombres = {c.name for c in IrUiView._meta.constraints}
        assert 'ir_ui_view_template_required_key' in nombres
        assert 'ir_ui_view_qweb_required_key' not in nombres

    @pytest.mark.django_db
    def test_the_constraint_still_rejects_a_keyless_template(self):
        # El control tiene que poder fallar: sin clave, la fila no entra.
        with pytest.raises(IntegrityError):
            IrUiView.objects.create(
                name='sin clave', type=VIEW_TYPE_TEMPLATE, key='',
                arch_db='<descriptor/>')

    @pytest.mark.django_db
    def test_and_it_lets_a_template_with_a_key_through(self):
        # El control positivo: lo que cae es la falta de clave, no el tipo.
        fila = IrUiView.objects.create(
            name='con clave', type=VIEW_TYPE_TEMPLATE, key='test.plantilla',
            arch_db='<descriptor/>')
        assert fila.pk is not None

    def test_the_client_registry_excludes_it_by_the_new_name(self):
        # ``addons/web`` lo excluye del registro de vistas del cliente: es la
        # única que el cliente no dibuja.
        assert VIEW_TYPE_TEMPLATE not in get_view_info(IrUiView)


class TestTheSugarWritesTheNewValue:

    def test_the_template_tag_records_the_new_type(self):
        # ``<template id="x"/>`` sigue siendo la superficie que se escribe; lo
        # que cambia es que el valor que graba ya coincide con ella.
        fuente = inspect.getsource(convert)
        assert "Field('qweb', name='type')" not in fuente
        assert f"Field({VIEW_TYPE_TEMPLATE!r}, name='type')" in fuente
