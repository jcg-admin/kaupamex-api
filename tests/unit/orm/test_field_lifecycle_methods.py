"""Los seis metodos del ciclo de vida del campo — tarea #211.

Porta el bloque que la referencia declara sobre ``Field`` y que aqui no tenia
contraparte, medido con el gate de porte:

============================  ==========================================
Simbolo                       ``odoo19c: odoo/orm/fields.py``
============================  ==========================================
``get_company_dependent_fallback``  ``:794-801``
``read``                            ``:1486-1489``
``create``                          ``:1491-1499``
``write``                           ``:1501-1518``
``_to_prefetch``                    ``:1588-1593``
``determine_group_expand``          ``:1930-1932``
============================  ==========================================

**Los seis son CONSTRUYE, no TRAE.** Django no tiene la nocion de un campo que
sepa leerse, escribirse y prelectar por si mismo — su ``Field`` describe una
columna y delega en el ``QuerySet``. Pero las primitivas ya estan todas en el
arbol: ``convert_to_cache``/``convert_to_record``, ``_filter_not_equal``,
``_update_cache``, ``_get_cache``, ``expand_ids``, ``PREFETCH_MAX``,
``determine`` y ``Environment.remove_to_compute``. Ninguna pieza viene de
fuera.

**La divergencia de firma de ``remove_to_compute``.** La fuente le pasa el
recordset; el nuestro toma ``(field, record_ids)`` —una coleccion de pk— asi
que ``write`` traduce. Es divergencia de mecanismo declarada, no de contrato:
lo que se descarta es lo mismo.

**El control que discrimina** es
``test_write_does_not_touch_a_row_whose_value_already_matches``: una
implementacion que actualizara la cache sin filtrar por ``_filter_not_equal``
pasaria todos los demas casos y marcaria como sucia una fila que no cambio,
que es justo lo que el filtro existe para evitar.
"""
import pytest
from django.db import models

from orm.environments import env as get_environment
from tools.constants import PREFETCH_MAX
from orm.registry import MODELS_BY_NAME
from orm.utils import model_field_registry


@pytest.fixture
def partner_model(db):
    return MODELS_BY_NAME['res.partner']


@pytest.fixture
def name_field(partner_model):
    return model_field_registry(partner_model)['name']


class TestTheSixAreInstalledOnTheFieldClass:
    """El contrato existe antes que su comportamiento: sin esto, un
    consumidor que los llame recibe ``AttributeError`` y no un resultado."""

    @pytest.mark.parametrize('name', [
        'get_company_dependent_fallback', 'read', 'create', 'write',
        '_to_prefetch', 'determine_group_expand',
    ])
    def test_the_field_class_answers_to_it(self, name):
        assert callable(getattr(models.Field, name, None))


class TestRead:
    """``:1486-1489`` — el cuerpo de la fuente es la guarda: un campo sin
    columna no sabe leerse y lo dice, en vez de devolver ``None``."""

    def test_a_field_without_a_column_refuses(self, partner_model):
        """El objeto del caso negativo EXISTE en el arbol.

        ``models.Field()`` pelado responde ``column_type is None``, que es lo
        que la fuente declara en ``Field._column_type = None``
        (``odoo19c: odoo/orm/fields.py:259``): la guarda apunta al defecto de
        la clase base, no a un objeto fabricado. Anularle el atributo a un
        ``CharField`` no vale: ``column_type`` es una ``property`` sin
        setter, asi que el caso media el ``AttributeError`` del intento y no
        la guarda.
        """
        field = models.Field()
        assert field.column_type is None
        with pytest.raises(NotImplementedError):
            field.read(partner_model.objects.none())

    def test_a_field_with_a_column_does_not_refuse(self, name_field, partner_model):
        name_field.read(partner_model.objects.none())


class TestWrite:

    def test_it_stores_the_value_in_the_cache(self, name_field, partner_model):
        record = partner_model.objects.create(name='Antes')
        name_field.write(record, 'Despues')
        assert name_field._get_cache(get_environment())[record.pk] == 'Despues'

    def test_write_does_not_touch_a_row_whose_value_already_matches(
            self, name_field, partner_model):
        """EL CONTROL: sin ``_filter_not_equal`` la fila entraria igual.

        El observable NO es la cache —escribir el mismo valor la deja igual
        con filtro y sin el, asi que un caso que la mire pasa en los dos
        casos y no discrimina—. El observable es ``transaction.field_dirty``:
        la fila cuyo valor ya coincide **no** debe quedar marcada para el
        UPDATE. Medido con la guarda anulada: este caso cae y los otros 18
        sobreviven.
        """
        record = partner_model.objects.create(name='Igual')
        env = get_environment()
        name_field._update_cache(record, 'Igual', dirty=False)
        env.transaction.field_dirty.pop(name_field, None)

        name_field.write(record, 'Igual')

        assert record.pk not in env.transaction.field_dirty.get(name_field, ())

    def test_write_marks_dirty_a_row_whose_value_changes(
            self, name_field, partner_model):
        """La otra mitad del control: cuando el valor SI cambia, entra."""
        record = partner_model.objects.create(name='Antes')
        env = get_environment()
        name_field._update_cache(record, 'Antes', dirty=False)
        env.transaction.field_dirty.pop(name_field, None)

        name_field.write(record, 'Despues')

        assert record.pk in env.transaction.field_dirty.get(name_field, ())


class TestCreate:
    """``:1491-1499`` — delega en ``write`` por cada par, sin logica propia."""

    def test_it_writes_every_pair(self, name_field, partner_model):
        one = partner_model.objects.create(name='Uno')
        two = partner_model.objects.create(name='Dos')

        name_field.create([(one, 'Uno nuevo'), (two, 'Dos nuevo')])

        cache = name_field._get_cache(get_environment())
        assert cache[one.pk] == 'Uno nuevo'
        assert cache[two.pk] == 'Dos nuevo'

    def test_an_empty_collection_is_a_no_op(self, name_field):
        name_field.create([])


class TestToPrefetch:
    """``:1588-1593`` — la ventana de filas que acompanan a la pedida."""

    def test_it_includes_the_record_itself(self, name_field, partner_model):
        record = partner_model.objects.create(name='Sola')
        assert record.pk in [r.pk for r in name_field._to_prefetch(record)]

    def test_it_leaves_out_what_the_cache_already_has(
            self, name_field, partner_model):
        one = partner_model.objects.create(name='Uno')
        two = partner_model.objects.create(name='Dos')
        one._prefetch_ids = [one.pk, two.pk]
        name_field._get_cache(get_environment())[two.pk] = 'Dos'

        assert two.pk not in [r.pk for r in name_field._to_prefetch(one)]

    def test_the_window_never_exceeds_the_declared_maximum(
            self, name_field, partner_model):
        record = partner_model.objects.create(name='Cabeza')
        record._prefetch_ids = range(record.pk, record.pk + PREFETCH_MAX + 50)

        assert len(list(name_field._to_prefetch(record))) <= PREFETCH_MAX


class TestDetermineGroupExpand:
    """``:1930-1932`` — el cuerpo entero es ``determine(self.group_expand, …)``."""

    def test_it_dispatches_to_the_declared_callable(
            self, name_field, partner_model, monkeypatch):
        seen = {}

        def group_expand(records, values, domain):
            seen['args'] = (values, domain)
            return ['expandido']

        monkeypatch.setattr(name_field, 'group_expand', group_expand,
                            raising=False)
        record = partner_model.objects.create(name='Grupo')

        assert name_field.determine_group_expand(record, ['a'], []) == ['expandido']
        assert seen['args'] == (['a'], [])

    def test_a_field_without_group_expand_raises(self, name_field, partner_model):
        """La fuente no pone guarda: sus llamadas agrupan antes por
        ``field.group_expand``, asi que solo llega aqui quien lo declara. Un
        ``TypeError`` distingue «no lo declara» de «lo declara y no corrio»."""
        record = partner_model.objects.create(name='Sin expand')
        with pytest.raises(TypeError):
            name_field.determine_group_expand(record, [], [])


class TestCompanyDependentFallback:
    """``:794-801`` — el respaldo de ``ir.default`` para un campo de empresa."""

    def test_it_refuses_on_a_field_that_is_not_company_dependent(
            self, name_field, partner_model):
        record = partner_model.objects.create(name='Llano')
        with pytest.raises(AssertionError):
            name_field.get_company_dependent_fallback(record)

    def test_it_returns_the_default_that_ir_default_holds(
            self, partner_model, monkeypatch):
        barcode = model_field_registry(partner_model)['barcode']
        monkeypatch.setattr(
            MODELS_BY_NAME['ir.default'], '_get_model_defaults',
            classmethod(lambda cls, *a, **k: {'barcode': 'MX-RESPALDO'}),
            raising=False)
        record = partner_model.objects.create(name='Con respaldo')

        assert barcode.get_company_dependent_fallback(record) == 'MX-RESPALDO'
