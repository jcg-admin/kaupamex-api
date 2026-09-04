"""Tests — ``required=`` es la intención declarada, no el defecto de Django.

Contrato adaptado de ``odoo19c: odoo/orm/fields.py`` (``Field.required``, cuyo
defecto es ``False``) y de su consumidor
``odoo19c: odoo/orm/fields_selection.py:129-134``, que decide si un
``selection_add`` con política ``'set null'`` es un error.

Lo que la fuente decide, y es lo que estos casos fijan
======================================================

En la fuente ``required`` es un atributo del campo que **sólo vale verdadero
cuando la declaración lo dice**. Aquí el ORM anfitrión trae ``null`` y
``blank`` en ``False`` por omisión, así que deducir "requerido" de ellos
convierte a todo campo en requerido — mide la forma de Django y concluye
sobre la intención de la fuente.

Por eso el despachador **anota** ``field.required``: es el nombre de la fuente
y ``models.Field`` de Django lo deja libre.

Qué haría fallar a cada control
--------------------------------

``TestTheDeclaredIntent.test_a_field_that_declares_nothing_is_not_required``
    El caso que da nombre a todo esto. Lo haría fallar volver a deducir
    ``required`` de ``null``/``blank``: el campo de este caso no declara
    ninguno de los dos, así que la deducción daría ``True``.

``TestTheDeclaredIntent.test_declaring_it_true_does_not_move_the_column``
    CONTROL: separa la anotación del esquema. Si un día ``required=True``
    empezara a poner ``null=True`` o a mover la columna, este caso cae y el
    resto seguiría verde.

``TestTheCompanyDependentGuard.test_a_company_dependent_field_cannot_be_required``
    CONTROL POSITIVO de la guarda de la fuente (``:466-470``): el despachador
    saca ``required`` de kwargs, y este caso mide que se lo devuelve a
    ``CompanyDependent`` — sin ello la guarda dejaría de disparar en silencio.

``TestTheOndeleteConsumer.*``
    El consumidor real. Miden que la decisión de
    ``check_ondelete_policies`` la toma la anotación y no el esquema.
"""
import pytest

import fields
from orm.model_classes import check_ondelete_policies

pytestmark = pytest.mark.unit


def _selection(**kwargs):
    kwargs.setdefault('max_length', 16)
    kwargs.setdefault('choices', [('a', 'Alfa')])
    field = fields.Selection(**kwargs)
    field.name = 'probe'
    return field


class TestTheDeclaredIntent:
    """``required`` sale de la declaración, no de ``null``/``blank``."""

    def test_a_field_that_declares_nothing_is_not_required(self):
        field = _selection()
        assert field.null is False and field.blank is False
        assert field.required is False

    def test_declaring_it_true_marks_the_field(self):
        assert _selection(required=True).required is True

    def test_declaring_it_false_marks_the_field_and_opens_blank(self):
        field = _selection(required=False)
        assert field.required is False
        assert field.blank is True

    def test_declaring_it_true_does_not_move_the_column(self):
        """``required=True`` anota; no cambia la nulabilidad de la columna."""
        declared = _selection(required=True)
        silent = _selection()
        assert declared.null == silent.null is False
        assert declared.blank == silent.blank is False

    def test_an_explicit_blank_wins_over_the_alias(self):
        """``setdefault``: quien escribe ``blank=`` manda sobre el alias."""
        assert _selection(required=True, blank=True).blank is True


class TestTheCompanyDependentGuard:
    """≙ los dos avisos de ``odoo19c: odoo/orm/fields.py:466-470``."""

    def test_a_company_dependent_field_cannot_be_required(self):
        with pytest.raises(ValueError, match='cannot be required'):
            fields.Selection(company_dependent=True, required=True)

    def test_without_required_it_builds(self):
        """CONTROL: la guarda dispara por ``required``, no por la palabra."""
        field = fields.Selection(company_dependent=True)
        assert field.required is False


class TestTheOndeleteConsumer:
    """El consumidor: ``check_ondelete_policies`` lee la anotación."""

    def test_a_silent_field_accepts_the_default_policy(self):
        """Sin ``required`` declarado, ``'set null'`` es válido — como la
        fuente, cuyo ``required`` ausente vale ``False``."""
        field = _selection()
        check_ondelete_policies(field, {'b': 'set null'}, ['b'], {'a', 'b'})

    def test_a_declared_required_field_refuses_the_default_policy(self):
        field = _selection(required=True)
        with pytest.raises(ValueError, match='requerido'):
            check_ondelete_policies(field, {'b': 'set null'}, ['b'], {'a', 'b'})

    def test_a_declared_required_field_accepts_cascade(self):
        field = _selection(required=True)
        check_ondelete_policies(field, {'b': 'cascade'}, ['b'], {'a', 'b'})

    def test_without_new_values_the_check_does_not_fire(self):
        """CONTROL: la fuente exige ``new_values`` — la política sólo aplica a
        los valores que este ``selection_add`` agrega."""
        field = _selection(required=True)
        check_ondelete_policies(field, {'a': 'set null'}, [], {'a'})
