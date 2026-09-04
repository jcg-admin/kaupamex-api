"""#312 — ``precompute`` se CORRE antes del INSERT, no sólo se valida.

Hasta este pase ``precompute`` era una anotación que dos guardas vigilaban y
nadie ejecutaba: ``resolve_depends`` avisa y lo apaga cuando la cadena de
dependencias no lo sostiene (``orm/fields.py:2181-2189``), y
``_apply_precompute_block`` lo rechaza sobre un campo no calculado, no
almacenado o M2M (``orm/fields_nonstored.py:369-406``). Los nueve campos que
lo declaran en el árbol se calculaban **a mano**, desde el ``save()`` de su
modelo.

Lo que la fuente hace, y que aquí faltaba, son dos pasos:
``_prepare_create_values`` (``odoo19c: odoo/orm/models.py:4786-4791``) saca de
``vals`` los precompute **readonly** para forzar su cómputo, y
``_add_precomputed_values`` (``:4814-4846``) computa todo precompute cuyo
nombre ``fname not in vals``, antes del INSERT.

Veredicto por el criterio de las dos categorías
===============================================

**El stack tiene con qué construirlo.** No hay símbolo hecho —Django no tiene
la noción de un campo que se calcula antes de su propia inserción— pero las
tres primitivas están y ninguna viene de fuera del INVENTORY, las tres de
(``django``, evaluación y control de flujo):

- ``pre_init`` entrega los ``kwargs`` **verbatim** del llamador
  (``django/db/models/base.py:491``), que es la traducción literal de
  ``fname not in vals``;
- ``post_init`` (``:595``) los cuelga de la instancia ya construida;
- ``pre_save`` (``:946``) corre **antes** de ``_save_table``, así que el valor
  calculado viaja en la misma sentencia INSERT — que es el punto entero de
  ``precompute``.

Por qué la pereza se hace explícita, y no se copia el registro virtual
=====================================================================

La fuente resuelve el pase con ``self.new(vals)`` y ``record[fname]``: una
**lectura** sobre un registro sin fila, que dispara el cómputo por el camino.
De ahí le salen gratis dos cosas: el orden de declaración da igual (un cómputo
que lee otro precompute lo resuelve al leerlo) y el caché no se ensucia con el
valor de una fila que aún no existe.

Aquí el cómputo se **invoca**, y las dos cosas hay que construirlas:

- el orden, con ``_run_precompute_field``, que antes de correr un cómputo corre
  los de los precompute del mismo modelo que su ``@api.depends`` nombra;
- la limpieza del caché, invocando el método directamente en vez de
  ``field.compute_value``: ``record_ids`` de una fila sin guardar da ``None``,
  y ``_update_cache`` escribiría ``field_cache[None]``, que la siguiente fila
  sin guardar leería como suyo.

La alternativa era portar el registro virtual entero. Se descartó por coste
frente a beneficio, no por dificultad: un registro sin fila exige un caché
propio con su ciclo de vida, y lo que compra —resolución perezosa— aquí se
obtiene con una recursión de doce líneas sobre un mapa que el registro ya
publica (``registry.field_depends``). El día que el ORM tenga registro virtual
por otra razón, esta recursión sobra y el pase se simplifica; hasta entonces
sería superficie sin consumidor.

Medido con cada guarda anulada
==============================

``scripts/evidence/control_312_guards.py`` sustituye el cuerpo de cada guarda
sobre una copia en memoria, corre la clase que la mide y restaura — nunca
``git checkout``, regla #177 — cerrando con el sha256 de cada archivo y con el
``git diff --stat`` comparado contra sí mismo, no contra HEAD (el árbol puede
tener trabajo sin commitear).

.. list-table::
   :header-rows: 1

   * - Guarda anulada
     - Clase medida
     - Resultado
   * - (ninguna)
     - el módulo entero
     - 19 passed
   * - la exclusión del valor dado (``_precomputable_fields``)
     - ``TestOnlyTheUncoveredPrecomputeIsPending``
     - 1 failed, 3 passed
   * - el orden por dependencia (``_run_precompute_field``)
     - ``TestTheComputesRunInDependencyOrder``
     - 2 failed, 2 passed
   * - el guard de ``_state.adding`` (``_run_precompute``)
     - ``TestTheReceiverFiresOnlyOnInsert``
     - 1 failed, 2 passed

*Métrica:* casos de este módulo que caen al anular cada guarda.
*Ciega a:* el orden entre el pase de precompute y el de un campo calculado que
NO lo declara —aquí no se ejerce—, y a un cómputo que lea un precompute de
**otro** modelo, que la recursión no persigue porque sólo mira los pendientes
de la misma fila.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.apps import apps
from django.utils import timezone

from orm import models as orm_models
from orm import registry
from orm.environments import env, transaction_scope
from orm.utils import model_field_registry
from tests.factories.product_factory import make_category, make_product

ResCompany = apps.get_model('base', 'ResCompany')
SaleOrder = apps.get_model('sale', 'SaleOrder')
SaleOrderLine = apps.get_model('sale', 'SaleOrderLine')

pytestmark = pytest.mark.django_db


def field_of(model, name):
    return model_field_registry(model)[name]


def record_calls(instance, names, log):
    """Cuelga de la instancia un envoltorio que anota la llamada y delega.

    El pase invoca ``getattr(instance, field.compute)()``, así que un atributo
    de instancia con el mismo nombre lo intercepta sin tocar el código del
    modelo ni el del motor: se observa el ORDEN sin alterar el EFECTO.
    """
    for name in names:
        real = getattr(instance, name)

        def wrapper(_name=name, _real=real):
            log.append(_name)
            return _real()

        setattr(instance, name, wrapper)


class TestTheCallerNamedValuesAreCaptured:
    """``fname not in vals`` traducido al constructor de Django."""

    def test_a_keyword_argument_is_recorded(self):
        order = SaleOrder(validity_date=None)
        assert 'validity_date' in order._explicit_values

    def test_naming_nothing_leaves_the_set_empty(self):
        """El control que discrimina: la MISMA maquinaria sobre un
        constructor sin argumentos no inventa nombres."""
        assert SaleOrder()._explicit_values == frozenset()

    def test_a_positional_argument_is_recorded_by_name_and_attname(self):
        """La mitad posicional, que ``kwargs`` no ve.

        Django mapea los posicionales contra ``_meta.concrete_fields`` en orden
        (``django/db/models/base.py:496``), y ``from_db`` construye **así** cada
        fila que vuelve de la base. Sin esta mitad, una fila cargada llegaría
        con el conjunto vacío.

        Se registran ``name`` y ``attname`` porque una FK responde a los dos y
        el llamador elige cuál escribe.
        """
        concrete = list(SaleOrder._meta.concrete_fields)
        company = SaleOrder._meta.get_field('company')
        cut = concrete.index(company) + 1

        names = orm_models._explicit_value_names(
            SaleOrder, [None] * cut, {})

        assert company.name in names
        assert company.attname in names
        assert company.name != company.attname

    def test_a_field_beyond_the_positional_run_is_not_recorded(self):
        """El control del caso de arriba: la misma llamada con un argumento
        menos deja fuera al último campo. Sin esto, un mapeo que devolviera
        TODOS los nombres pasaría igual."""
        concrete = list(SaleOrder._meta.concrete_fields)
        company = SaleOrder._meta.get_field('company')
        cut = concrete.index(company)

        names = orm_models._explicit_value_names(
            SaleOrder, [None] * cut, {})

        assert company.name not in names


class TestOnlyTheUncoveredPrecomputeIsPending:
    """Las dos exclusiones que la fuente reparte en dos sitios."""

    def test_a_writable_precompute_nobody_named_is_pending(self):
        assert 'validity_date' in orm_models._precomputable_fields(SaleOrder())

    def test_a_writable_precompute_the_caller_named_is_skipped(self):
        """``if fname not in vals`` (``odoo19c: :4842``): un valor explícito
        sobrevive, aunque sea ``None``."""
        pending = orm_models._precomputable_fields(SaleOrder(validity_date=None))
        assert 'validity_date' not in pending

    def test_a_readonly_precompute_is_pending_even_when_named(self):
        """La otra mitad: la fuente saca los readonly de ``vals`` ANTES de
        mirarlo (``:4786-4791``), así que nombrarlos no los protege."""
        field = field_of(SaleOrderLine, 'price_subtotal')
        assert field.readonly is True

        pending = orm_models._precomputable_fields(
            SaleOrderLine(price_subtotal=Decimal('5.00')))
        assert 'price_subtotal' in pending

    def test_a_field_without_precompute_is_never_pending(self):
        """El control que discrimina: la misma maquinaria sobre un campo que
        no lo declara no lo recoge."""
        assert field_of(SaleOrder, 'name').precompute is False
        assert 'name' not in orm_models._precomputable_fields(SaleOrder())


class TestTheComputesRunInDependencyOrder:
    """La pereza que la fuente obtiene gratis, aquí construida."""

    def test_the_declaration_order_puts_the_reducers_first(self):
        """El control de vacuidad, y es lo que hace real al caso siguiente.

        ``SaleOrderLine`` declara ``price_reduce_taxexcl`` (``:309``) y
        ``price_reduce_taxinc`` (``:317``) ANTES de ``price_subtotal``
        (``:417``), ``price_tax`` (``:425``) y ``price_total`` (``:433``), y
        los dos primeros leen justamente lo que ``_compute_amount`` escribe.
        Sin esta comprobación, un pase que corriera en orden de declaración
        pasaría el caso de abajo por casualidad el día que alguien reordene
        el modelo.
        """
        pending = list(orm_models._precomputable_fields(SaleOrderLine()))
        assert (pending.index('price_reduce_taxexcl')
                < pending.index('price_subtotal'))
        assert registry.field_depends[
            field_of(SaleOrderLine, 'price_reduce_taxexcl')] == (
                'price_subtotal', 'product_uom_qty')

    def test_the_amount_runs_before_the_reducers(self):
        line = SaleOrderLine(
            product_uom_qty=Decimal('2'), price_unit=Decimal('100.00'),
            discount=Decimal('0.00'))
        log = []
        record_calls(line, ['_compute_amount',
                            '_compute_price_reduce_taxexcl',
                            '_compute_price_reduce_taxinc'], log)

        orm_models._add_precomputed_values(line)

        assert log.index('_compute_amount') < log.index(
            '_compute_price_reduce_taxexcl')
        assert log.index('_compute_amount') < log.index(
            '_compute_price_reduce_taxinc')

    def test_a_compute_that_writes_three_fields_runs_once(self):
        """``done`` lleva los MÉTODOS invocados, no los campos.

        ``_compute_amount`` es el compute de tres campos; correrlo una vez por
        campo repetiría su efecto tres veces sobre la misma fila.
        """
        line = SaleOrderLine(
            product_uom_qty=Decimal('2'), price_unit=Decimal('100.00'),
            discount=Decimal('0.00'))
        log = []
        record_calls(line, ['_compute_amount'], log)

        orm_models._add_precomputed_values(line)

        assert log.count('_compute_amount') == 1

    def test_the_pass_leaves_the_value_computed(self):
        """Y el pase hace su trabajo: el reductor sale del subtotal recién
        calculado, no del ``default`` de la columna."""
        line = SaleOrderLine(
            product_uom_qty=Decimal('2'), price_unit=Decimal('100.00'),
            discount=Decimal('0.00'))

        orm_models._add_precomputed_values(line)

        assert line.price_subtotal > Decimal('0.00')
        assert line.price_reduce_taxexcl == (
            line.price_subtotal / Decimal('2')).quantize(Decimal('0.01'))


class TestTheReceiverFiresOnlyOnInsert:
    """Las dos salidas tempranas de ``_run_precompute``."""

    def test_a_row_that_does_not_exist_yet_is_computed(self):
        line = SaleOrderLine(
            product_uom_qty=Decimal('1'), price_unit=Decimal('100.00'),
            discount=Decimal('0.00'))
        line.price_subtotal = Decimal('1.00')

        orm_models._run_precompute(sender=SaleOrderLine, instance=line)

        assert line.price_subtotal != Decimal('1.00')

    def test_a_row_that_already_exists_is_left_alone(self, saved_line):
        """El control que discrimina el guard de ``_state.adding``: un UPDATE
        no vuelve a precomputar — ahí el recálculo lo gobierna ``modified()``,
        no este pase."""
        saved_line.price_subtotal = Decimal('1.00')

        orm_models._run_precompute(sender=SaleOrderLine, instance=saved_line)

        assert saved_line.price_subtotal == Decimal('1.00')

    def test_the_fixture_loader_is_left_alone(self):
        """``raw=True`` es el cargador de fixtures, que escribe la fila tal
        cual viene."""
        line = SaleOrderLine(
            product_uom_qty=Decimal('1'), price_unit=Decimal('100.00'))
        line.price_subtotal = Decimal('1.00')

        orm_models._run_precompute(
            sender=SaleOrderLine, instance=line, raw=True)

        assert line.price_subtotal == Decimal('1.00')


class TestTheUnsavedRowNeverReachesTheCache:
    """La razón de invocar el cómputo y no ``field.compute_value``."""

    def test_no_none_key_lands_in_the_field_cache(self):
        line = SaleOrderLine(
            product_uom_qty=Decimal('1'), price_unit=Decimal('100.00'),
            discount=Decimal('0.00'))
        field = field_of(SaleOrderLine, 'price_subtotal')

        with transaction_scope():
            orm_models._add_precomputed_values(line)
            assert None not in field._get_cache(env())

    def test_the_cache_does_take_the_value_of_a_saved_row(self, saved_line):
        """El control que discrimina: el mismo caché SÍ admite una clave
        cuando la fila tiene ``pk``. Sin este caso, un caché que nunca
        aceptara nada pasaría el de arriba."""
        field = field_of(SaleOrderLine, 'price_subtotal')

        with transaction_scope():
            field._update_cache([saved_line], Decimal('7.00'))
            assert saved_line.pk in field._get_cache(env())


class TestValidityDateEndToEnd:
    """El campo que el árbol calculaba a mano, ahora por el motor."""

    def test_creating_without_naming_it_computes_the_date(self, company):
        order = SaleOrder.objects.create(company=company)

        assert order.validity_date == timezone.localdate() + timedelta(days=15)

    def test_creating_with_an_explicit_none_leaves_it_unset(self, company):
        """El caso que la rama de creación de ``SaleOrder.save()`` fallaba.

        Usaba ``if self.validity_date is None`` como sustituto de ``if fname
        not in vals``, así que un ``None`` explícito era indistinguible de un
        valor ausente y el cómputo lo pisaba. El motor mira lo que el llamador
        NOMBRÓ, no el valor que resultó.

        Se mide la **columna**, no el atributo, y no es un rodeo: ``values_list``
        arma la tupla desde la fila sin instanciar el modelo, así que no pasa
        por el descriptor. Es el único plano donde «el cómputo no escribió» se
        distingue de lo que el descriptor conteste.

        Y el **atributo** se mide junto a ella, porque los dos planos de lectura
        del descriptor ya responden lo mismo: ``False``, que es el vocabulario
        de la fuente para «sin valor» (``odoo19c: odoo/orm/fields.py:1053``:
        ``return False if value is None else value``). Su vuelta la cierra
        ``convert_to_column`` en el camino a la columna, así que ese ``False``
        se guarda como ``NULL`` y no revienta el conversor de Django.
        """
        order = SaleOrder.objects.create(company=company, validity_date=None)

        assert SaleOrder.objects.filter(pk=order.pk).values_list(
            'validity_date', flat=True)[0] is None
        assert order.validity_date is False
        order.refresh_from_db()
        assert order.validity_date is False


@pytest.fixture
def company(db):
    return ResCompany.objects.create(
        code='pre-312', name='Precompute 312', quotation_validity_days=15)


@pytest.fixture
def saved_line(db):
    product = make_product(
        name='Precompute 312', price=Decimal('100.00'), stock=5,
        categ=make_category(name='Cat 312'))
    order = SaleOrder.objects.create()
    return SaleOrderLine.objects.create(
        order=order, product=product, product_uom_qty=Decimal('1'),
        price_unit=Decimal('100.00'))
