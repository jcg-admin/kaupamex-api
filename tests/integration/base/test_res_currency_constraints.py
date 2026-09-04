"""Tests — la cabecera de ``res.currency`` y su restricción de redondeo.

Contrato adaptado de ``odoo19c: odoo/addons/base/models/res_currency.py``:
los cuatro atributos de clase (``:21-24``) y los dos objetos de tabla
``_unique_name`` y ``_rounding_gt_zero`` (``:48-55``).

Qué haría fallar a cada control se declara en su caso.
"""
import pytest

from django.db import IntegrityError, transaction

from addons.base.models import ResCurrency

pytestmark = pytest.mark.integration


class TestClassAttributes:
    """≙ los cuatro de ``odoo19c: res_currency.py:21-24``."""

    def test_the_four_attributes_of_the_source_are_declared(self):
        assert ResCurrency._name == 'res.currency'
        assert ResCurrency._description == 'Currency'
        assert ResCurrency._rec_names_search == ['name', 'full_name']
        assert ResCurrency._order == 'active desc, name'

    def test_the_table_matches_the_dotted_name(self):
        assert ResCurrency._meta.db_table == ResCurrency._name.replace('.', '_')

    def test_the_ordering_derives_from_the_declared_order(self):
        """``active desc, name`` → ``['-active', 'name']``.

        Sin la primera clave, una divisa archivada encabeza el listado por
        tener un nombre que empieza por A. El caso siguiente lo mide en la
        base, no sólo en la declaración.
        """
        assert ResCurrency._meta.ordering == ['-active', 'name']


class TestOrderingIsObservable:
    """El orden declarado, medido contra la base."""

    def test_an_archived_currency_does_not_lead_an_active_one(self, db):
        """Qué haría fallar al control: volver a ``ordering = ['name']``.

        ``AAA`` está archivada y ``ZZZ`` activa. Con el orden de la fuente,
        ``ZZZ`` va primero; con el nuestro anterior, ``AAA``.
        """
        ResCurrency.objects.create(name='AAA', symbol='a', active=False,
                                   rounding='0.01')
        ResCurrency.objects.create(name='ZZZ', symbol='z', active=True,
                                   rounding='0.01')
        order = list(ResCurrency.objects.filter(
            name__in=['AAA', 'ZZZ']).values_list('name', flat=True))
        assert order == ['ZZZ', 'AAA']


class TestRoundingConstraint:
    """≙ ``_rounding_gt_zero`` (``odoo19c: res_currency.py:52-55``)."""

    def test_a_zero_rounding_is_refused_by_the_row(self, db):
        """La restricción existe para lo que el método NO puede impedir.

        ``round()`` corta antes de dividir cuando ``rounding`` es falso, así
        que nadie revienta; lo que nadie impedía era **guardar** la fila en ese
        estado. Este caso mide la fila, no el método.
        """
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ResCurrency.objects.create(name='ZR0', symbol='z',
                                           rounding='0')

    def test_a_negative_rounding_is_refused(self, db):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ResCurrency.objects.create(name='ZR1', symbol='z',
                                           rounding='-0.01')

    def test_a_positive_rounding_is_accepted(self, db):
        """CONTROL de la dirección contraria: sin él, una restricción que
        rechazara todo pasaría los dos anteriores.
        """
        currency = ResCurrency.objects.create(name='ZR2', symbol='z',
                                              rounding='0.01')
        assert currency.pk

    def test_an_update_cannot_leave_the_row_inconsistent(self, db):
        """El caso que la condición de cierre del DESCONOCIDO esperaba.

        Decía *«se registra cuando exista un endpoint de escritura de rounding
        que lo amerite»*. Una restricción de tabla existe para que el escritor
        no pueda dejar la fila mal; llegar después del escritor es llegar
        tarde. Aquí se mide sin endpoint: basta un ``save()``.
        """
        currency = ResCurrency.objects.create(name='ZR3', symbol='z',
                                              rounding='0.01')
        currency.rounding = '0'
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                currency.save()


class TestUniqueName:
    """≙ ``_unique_name`` (``odoo19c: res_currency.py:48-51``)."""

    def test_two_currencies_cannot_share_a_code(self, db):
        ResCurrency.objects.create(name='ZU1', symbol='z', rounding='0.01')
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ResCurrency.objects.create(name='ZU1', symbol='y',
                                           rounding='0.01')
