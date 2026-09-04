"""``compute=`` en el campo con columna — la capa 0 de #273.

El motor de recálculo (``modified()``) invierte el grafo de ``field_depends``.
Ese mapa lo deriva :class:`~orm.registry._DerivedCollector` uniendo **dos**
declaraciones que viven en sitios distintos: el ``_depends`` que
``@api.depends`` deja en el **método**, y el ``compute`` que el **campo**
declara para nombrarlo (``src/orm/registry.py:473-481``).

Medido antes de escribir estos casos, con el registro poblado: **44** métodos
declaran ``@api.depends``, **0** campos declaran ``compute=``, **0** campos
resuelve ``field_depends``. El mapa está vacío por construcción, así que un
motor construido encima mediría cero **pasando verde** — el sub-patrón D de
``metrica-decide-la-conclusion.md``. El censo:
``scripts/workbench/trigger-graph-of-fields-20260902T134137/``.

La causa: el campo persistido levanta ``TypeError`` ante todo el vocabulario
de cómputo. Sólo la rama ``store=False`` lo acepta, así que hoy este árbol
puede expresar un calculado **sin** columna y no uno **con** columna. En la
referencia esa segunda forma son **1273** declaraciones medidas
(``compute=`` con ``store=True`` explícito sobre 3330 archivos
``models/*.py`` de ``odoo19c``).

Lo que se porta es el bloque de ``odoo19c: odoo/orm/fields.py:443-451``,
verbatim::

    if attrs.get('compute'):
        attrs['store'] = store = attrs.get('store', False)
        attrs['compute_sudo'] = attrs.get('compute_sudo', store)
        if not (attrs['store'] and not attrs.get('readonly', True)):
            attrs['copy'] = attrs.get('copy', False)
        attrs['readonly'] = attrs.get('readonly', not attrs.get('inverse'))

más el de ``precompute`` (``:459-465``), que avisa y desactiva en las dos
formas donde el atributo no tiene efecto.

**El lado DRF no se inventa: se apoya en el riel del anfitrión.** Un campo
calculado sin ``inverse`` es de sólo lectura, y la forma nativa de decirlo en
Django es ``editable=False``. DRF ya lo consume:
``rest_framework/utils/field_mapping.py:124-128`` —
``if isinstance(model_field, models.AutoField) or not model_field.editable:``
→ ``kwargs['read_only'] = True`` con retorno temprano. Así que el contrato del
endpoint sale del mecanismo que DRF ya tiene, sin override en el serializer.

Qué haría fallar a estos casos: que el vocabulario siga levantando
``TypeError``; que un calculado nazca con columna por defecto (la fuente lo
declara sin ella); que un calculado sin ``inverse`` salga escribible en el
contrato; o que ``field_depends`` siga vacío con las dos mitades declaradas.
"""
import pytest
from django.db import models as django_models
from rest_framework import serializers

import api
import fields
from orm import registry
from orm.fields_nonstored import NonStored


class TestTheComputeVocabularyIsAccepted:
    """Los seis atributos del mecanismo, que hoy levantan ``TypeError``."""

    @pytest.mark.parametrize('kwargs', [
        {'compute': '_compute_x'},
        {'compute': '_compute_x', 'store': True},
        {'compute': '_compute_x', 'compute_sudo': True},
        {'compute': '_compute_x', 'inverse': '_inverse_x'},
        {'compute': '_compute_x', 'store': True, 'precompute': True},
        {'compute': '_compute_x', 'recursive': True},
    ])
    def test_the_declaration_builds_a_field(self, kwargs):
        field = fields.Char(max_length=64, **kwargs)
        assert field is not None

    def test_the_declared_method_survives_on_the_field(self):
        field = fields.Char(max_length=64, compute='_compute_x', store=True)
        assert field.compute == '_compute_x'

    def test_the_inverse_survives_on_the_field(self):
        field = fields.Char(max_length=64, compute='_compute_x',
                            inverse='_inverse_x', store=True)
        assert field.inverse == '_inverse_x'

    def test_recursive_survives_on_the_field(self):
        field = fields.Char(max_length=64, compute='_compute_x',
                            recursive=True, store=True)
        assert field.recursive is True


class TestTheDefaultsFollowTheSource:
    """``odoo19c: odoo/orm/fields.py:443-451``, atributo por atributo."""

    def test_a_computed_field_has_no_column_by_default(self):
        #: ``attrs['store'] = store = attrs.get('store', False)`` — la fuente
        #: declara el calculado SIN columna salvo que se pida. Es la misma
        #: regla que ``related=``, y la razón por la que 2368 de las 3641
        #: declaraciones de la referencia no llevan ``store=True``.
        field = fields.Char(max_length=64, compute='_compute_x')
        assert isinstance(field, NonStored)
        assert field.store is False

    def test_store_true_gives_a_column(self):
        field = fields.Char(max_length=64, compute='_compute_x', store=True)
        assert isinstance(field, django_models.Field)
        assert field.store is True

    def test_compute_sudo_defaults_to_store(self):
        #: ``attrs['compute_sudo'] = attrs.get('compute_sudo', store)``.
        with_column = fields.Char(max_length=64, compute='_compute_x', store=True)
        without_column = fields.Char(max_length=64, compute='_compute_x')
        assert with_column.compute_sudo is True
        assert without_column.compute_sudo is False

    def test_the_declared_compute_sudo_wins(self):
        field = fields.Char(max_length=64, compute='_compute_x',
                            compute_sudo=True)
        assert field.compute_sudo is True

    def test_a_computed_field_is_readonly_without_inverse(self):
        #: ``attrs['readonly'] = attrs.get('readonly', not attrs.get('inverse'))``
        field = fields.Char(max_length=64, compute='_compute_x', store=True)
        assert field.readonly is True

    def test_an_inversible_computed_field_is_not_readonly(self):
        field = fields.Char(max_length=64, compute='_compute_x',
                            inverse='_inverse_x', store=True)
        assert field.readonly is False

    def test_a_computed_field_is_not_copied(self):
        #: ``if not (attrs['store'] and not attrs.get('readonly', True)):
        #:      attrs['copy'] = attrs.get('copy', False)``
        field = fields.Char(max_length=64, compute='_compute_x', store=True)
        assert field.copy is False

    def test_a_stored_writable_computed_field_keeps_the_copy_default(self):
        #: La única rama que NO fuerza ``copy=False``: con columna Y
        #: ``readonly`` declarado falso. Un caso que la condición doblemente
        #: negada de la fuente esconde, y que sin este caso nadie mediría.
        field = fields.Char(max_length=64, compute='_compute_x',
                            store=True, readonly=False)
        assert field.copy is True


class TestPrecomputeWarnsWhereItHasNoEffect:
    """``odoo19c: odoo/orm/fields.py:459-465`` — avisa y desactiva."""

    def test_precompute_without_compute_warns_and_turns_off(self):
        with pytest.warns(UserWarning, match='non computed field'):
            field = fields.Char(max_length=64, precompute=True)
        assert field.precompute is False

    def test_precompute_without_store_warns_and_turns_off(self):
        with pytest.warns(UserWarning, match='non stored field'):
            field = fields.Char(max_length=64, compute='_compute_x',
                                precompute=True)
        assert field.precompute is False

    def test_precompute_with_compute_and_store_survives(self):
        field = fields.Char(max_length=64, compute='_compute_x',
                            store=True, precompute=True)
        assert field.precompute is True


class TestTheEndpointContract:
    """El lado DRF, por el riel que el anfitrión ya tiene.

    No se toca ``ModelSerializer``: se declara ``editable=False`` en el campo,
    que es como Django dice «esto no lo escribe el cliente», y DRF lo consume
    en ``get_field_kwargs`` (``field_mapping.py:124-128``).
    """

    def test_a_readonly_computed_field_is_not_editable(self):
        field = fields.Char(max_length=64, compute='_compute_x', store=True)
        assert field.editable is False

    def test_an_inversible_computed_field_stays_editable(self):
        field = fields.Char(max_length=64, compute='_compute_x',
                            inverse='_inverse_x', store=True)
        assert field.editable is True

    def test_the_serializer_builds_it_read_only(self, db):
        #: El caso que mide el CONTRATO y no el atributo: se construye un
        #: ``ModelSerializer`` de verdad y se pregunta por el campo que sale.
        class ComputedContractProbe(django_models.Model):
            plain = fields.Char(max_length=64)
            computed = fields.Char(max_length=64, compute='_compute_x',
                                   store=True)

            class Meta:
                app_label = 'base'
                managed = False

        class ProbeSerializer(serializers.ModelSerializer):
            class Meta:
                model = ComputedContractProbe
                fields = ('plain', 'computed')

        built = ProbeSerializer().fields
        assert built['computed'].read_only is True
        assert built['plain'].read_only is False


class TestTheJoinThatUnblocksTheEngine:
    """La mitad que el censo midió en cero: campo y método, unidos."""

    def test_field_depends_resolves_when_both_halves_are_declared(self):
        class DependsJoinProbe(django_models.Model):
            source = fields.Char(max_length=64)
            derived = fields.Char(max_length=64, compute='_compute_derived',
                                  store=True)

            class Meta:
                app_label = 'base'
                managed = False

            @api.depends('source')
            def _compute_derived(self):
                pass

        registry.clear_field_depends()
        field = DependsJoinProbe._meta.get_field('derived')
        assert registry.field_depends[field] == ('source',)
