"""El mecanismo ``related=`` — ≙ ``odoo19c: odoo/orm/fields.py:604-772``.

Un campo ``related='a.b'`` no guarda dato: proyecta el valor del extremo de la
cadena. La fuente lo declara **597 veces** en los addons que este árbol porta y
**552 sin ``store``** (medido, ver
``test_related_shape_in_the_reference.py``), así que es un mecanismo, no un
puñado de casos que se puedan declinar uno a uno.

Lo que este archivo fija es la parte que faltaba: ``setup_related``, que cablea
las tres funciones del campo, y ``_search_related``, que lo hace **buscable**.
Sin la segunda un ``related`` se puede leer y no se puede filtrar — que es
justo lo que se perdía al «navegarlo por la FK», la razón que varios archivos
del árbol daban para no portarlo.

``_search_related`` es además el quinto lector de ``falsy_value``
(``odoo19c: :744``); los otros cuatro ya viven en ``condition_to_q`` y
``_filter_function``.
"""
import logging

import pytest
from django.apps import apps
from django.db import models

from orm.domains import Domain, DomainCondition


@pytest.fixture
def bank():
    return apps.get_model('base', 'ResBank')


@pytest.fixture
def sequence_range():
    return apps.get_model('base', 'IrSequenceDateRange')


class TestTheSetupWiresTheThreeFunctions:
    """``setup_related`` (``:604-660``) — qué deja instalado en el campo."""

    def test_it_resolves_the_chain_to_its_last_field(self, bank):
        field = models.CharField(max_length=8)
        field.related = 'country.code'
        field.set_attributes_from_name('country_code')
        field.model = bank

        field.setup_related(bank)

        assert field.related_field is bank._meta.get_field('country').related_model._meta.get_field('code')

    def test_it_wires_compute_inverse_and_search(self, bank):
        """``store=False`` no es decoración del caso: es su premisa.

        El defecto de ``store`` es ``True`` (``_FIELD_CLASS_ATTRIBUTES``), y
        con columna propia el valor se busca por ella — la guarda de ``:635``
        salta la cadena. La forma que este caso ejerce es la de **552 de los
        597** ``related=`` medidos en la referencia; la contraria la ejerce
        :meth:`test_a_stored_related_is_not_searchable_by_the_chain`, que es
        su control discriminante.
        """
        field = models.CharField(max_length=8)
        field.related = 'country.code'
        field.store = False
        field.set_attributes_from_name('country_code')
        field.model = bank

        field.setup_related(bank)

        assert field.compute == field._compute_related
        assert field.inverse == field._inverse_related
        assert field.search == field._search_related, (
            'sin search el related se lee pero no se busca, que es exactamente '
            'lo que se perdía al navegarlo por la FK')

    def test_a_stored_related_is_not_searchable_by_the_chain(self, bank):
        """``:635`` — ``if not self.store and ...``.

        Con ``store`` el valor tiene columna propia, así que se busca por ella
        y no recorriendo la cadena. Es el control que discrimina: sin la
        guarda, los dos casos cablearían lo mismo.
        """
        field = models.CharField(max_length=8)
        field.related = 'country.code'
        field.store = True
        field.set_attributes_from_name('country_code')
        field.model = bank

        field.setup_related(bank)

        assert field.search is None

    def test_it_copies_the_attributes_of_the_target(self, bank):
        """``:643-647`` — ``string``, ``help``, ``groups``, ``aggregator`` y
        ``comodel_name`` se copian del campo destino cuando el related no los
        declara."""
        field = models.CharField(max_length=8)
        field.related = 'country.code'
        field.set_attributes_from_name('country_code')
        field.model = bank

        field.setup_related(bank)

        target = bank._meta.get_field('country').related_model._meta.get_field('code')
        assert field.string == target.string

    def test_a_type_mismatch_between_the_related_and_its_target_is_refused(self, bank):
        """``:622-624`` — ``if self.type != field.type: raise TypeError``.

        Una proyección que declara un tipo distinto del de su destino miente
        sobre lo que entrega. ``country.code`` es ``char``; declararlo como
        ``integer`` tiene que reventar al configurarlo, no al leerlo.

        El tipo lo publica la ``property`` ``type`` (``orm/fields.py``), que
        despacha por conducta: la clase de Django no basta para distinguir un
        ``char`` de una ``selection``.
        """
        field = models.IntegerField()
        field.related = 'country.code'
        field.set_attributes_from_name('country_code')
        field.model = bank

        with pytest.raises(TypeError) as excinfo:
            field.setup_related(bank)

        assert 'country_code' in str(excinfo.value)
        assert 'code' in str(excinfo.value)

    def test_a_readonly_related_without_inverse_warns_about_its_default(self, bank, caplog):
        """``:640-641`` — «Redundant default on %s».

        Sin inverso nadie escribe el valor, así que un ``default`` declarado
        no se puede honrar. La fuente avisa en vez de reventar, y aquí igual.
        """
        field = models.CharField(max_length=8, default='XX')
        field.related = 'country.code'
        field.readonly = True
        field.set_attributes_from_name('country_code')
        field.model = bank

        with caplog.at_level(logging.WARNING, logger='orm.fields'):
            field.setup_related(bank)

        assert field.inverse is None, (
            'el aviso sólo tiene sentido si el inverso quedó sin cablear')
        assert any('country_code' in r.getMessage() for r in caplog.records), (
            caplog.text)

    def test_a_writable_related_with_default_does_not_warn(self, bank, caplog):
        """El control que discrimina al anterior.

        Sin ``readonly`` el inverso se cablea, así que el ``default`` sí se
        puede honrar y no hay nada que avisar. Sin este caso, un aviso emitido
        siempre pasaría el test de arriba igual de verde.
        """
        field = models.CharField(max_length=8, default='XX')
        field.related = 'country.code'
        field.set_attributes_from_name('country_code')
        field.model = bank

        with caplog.at_level(logging.WARNING, logger='orm.fields'):
            field.setup_related(bank)

        assert field.inverse is not None
        assert not [r for r in caplog.records
                    if 'edundante' in r.getMessage()]

    def test_a_broken_chain_says_which_link_is_missing(self, bank):
        """``:611-615`` — la fuente lanza ``KeyError`` nombrando el eslabón."""
        field = models.CharField(max_length=8)
        field.related = 'country.no_existe'
        field.set_attributes_from_name('roto')
        field.model = bank

        with pytest.raises(KeyError, match='no_existe'):
            field.setup_related(bank)


class TestTheSearchWalksTheChainBackwards:
    """``_search_related`` (``:735-772``) — el dominio que sustituye a la
    condición sobre el campo proyectado."""

    def _related_field(self, model, path, name):
        field = models.CharField(max_length=8)
        field.related = path
        field.set_attributes_from_name(name)
        field.model = model
        field.setup_related(model)
        return field

    def test_it_builds_the_any_chain(self, bank):
        """``:764-770`` — ``('x.y', op, v)`` se convierte en
        ``('x', 'any', [('y', op, v)])``."""
        field = self._related_field(bank, 'country.code', 'country_code')

        domain = field._search_related(bank, '=', 'MX')

        condition = next(iter(domain.iter_conditions()))
        assert condition.field_expr == 'country'
        assert condition.operator in ('any', 'any!')

    def test_a_nullable_many2one_accepts_the_row_without_value(self, bank):
        """``:771-772`` — el quinto lector de ``falsy_value``.

        Buscar ``country_code = False`` sobre una cadena cuyo eslabón es un
        many2one nulable tiene que aceptar también la fila **sin país**: allá
        no hay país que mirar, y su código es el ``falsy_value`` del campo.
        """
        country = bank._meta.get_field('country')
        assert country.null is True, (
            'la precondición del caso cambió: con country NOT NULL no hay '
            'fila sin valor que aceptar y este caso no distingue nada')

        field = self._related_field(bank, 'country.code', 'country_code')
        domain = field._search_related(bank, '=', False)

        conditions = list(domain.iter_conditions())
        assert any(c.field_expr == 'country' and c.operator in ('in', '=')
                   and False in (c.value if isinstance(c.value, (list, set, tuple))
                                 else [c.value])
                   for c in conditions), (
            f'no se añadió la rama de la fila sin valor — {domain}')

    def test_a_positive_search_does_not_add_it(self, bank):
        """El control que discrimina: con un valor verdadero la rama sobra.

        Sin este caso, un ``can_be_null`` que valiera siempre ``True`` pasaría
        el caso de arriba y nadie lo notaría.
        """
        field = self._related_field(bank, 'country.code', 'country_code')
        domain = field._search_related(bank, '=', 'MX')

        conditions = list(domain.iter_conditions())
        assert len(conditions) == 1, (
            f'se añadió la rama de nulos a una búsqueda positiva — {domain}')

    def test_a_negative_operator_with_a_truthy_value_gives_up(self, bank):
        """``:752-755`` — verbatim: devuelve ``NotImplemented`` para que el
        despachador lo reintente con el operador positivo."""
        field = self._related_field(bank, 'country.code', 'country_code')

        assert field._search_related(bank, 'not in', ['MX']) is NotImplemented
