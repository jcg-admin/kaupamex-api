"""Lo que un alta protege del recómputo, por las dos vías de creación.

≙ ``create`` de ``odoo19c: odoo/orm/models.py:4681-4684``: un campo calculado
que llega en ``vals`` queda protegido sólo si es editable o precompute
(``field.compute and (not field.readonly or field.precompute)``), y con él
**todo su grupo** —``self.pool.field_computed.get(field, [field])``—. Los
precompute que ``_add_precomputed_values`` (``:4814-4846``) añade a ``vals``
entran por la misma condición, así que el alta los protege todos. Después
``_create`` llama ``modified(self._fields, create=True)`` bajo
``env.protecting(protected)`` (``:4930-4933``).

Aquí un alta llega por dos caminos: ``BaseModel.create`` y ``save()`` de
Django, que marca la fila en ``post_save``. Los dos tienen que proteger el
mismo conjunto (designs/stored-computes-on-django-create.md).

*Métrica:* valores persistidos tras el volcado, llamadas al método de
cómputo y marcas pendientes en la transacción.
*Ciega a:* el alias de base de datos: la transacción del ORM es una por
proceso y estas pruebas corren sobre ``default``; el aislamiento entre bases
lo miden ``tests/integration/multidb``.
"""
from decimal import Decimal

import pytest
from django.apps import apps
from django.db import transaction
from django.db.migrations.state import ProjectState

from addons.project.models import Project
from addons.sale.models import SaleOrderLine
from orm.environments import env as current_env
from orm.environments import transaction_scope
from orm import models as orm_models
from orm.models import _protected_on_create
from orm.utils import record_ids
from tests.factories.order_factory import make_order
from tests.factories.product_factory import make_product

pytestmark = pytest.mark.django_db

EmployeeMap = apps.get_model('sale_timesheet', 'ProjectSaleLineEmployeeMap')
HrEmployee = apps.get_model('hr', 'HrEmployee')
SharedCompute = apps.get_model('test_orm', 'TestOrmSharedCompute')


def _flush():
    with transaction_scope():
        current_env().flush_all()


def _shared_row(pk):
    return SharedCompute.objects.values('name', 'start', 'end').get(pk=pk)


def _pending_for(model):
    names = {field.name for field in model._meta.concrete_fields}
    return [field for field in current_env().fields_to_compute()
            if getattr(field, 'model', None) is model
            and field.name in names]


@pytest.fixture
def project():
    return Project.objects.create(name='Proyecto con tarifas')


@pytest.fixture
def employee():
    return HrEmployee.objects.create(name='Consultora',
                                     hourly_cost=Decimal('40.00'))


@pytest.fixture
def sale_line(user):
    product = make_product(name='Hora de consultoría')
    return SaleOrderLine.objects.create(
        order=make_order(user=user), product=product, name=product.name,
        price_unit=Decimal('90.00'), product_uom_qty=1)


#: ``end`` protegido no se calcula: queda en su valor sin asignar, que un
#: ``Integer`` lee como 0 (``convert_to_record``: ``value or 0``,
#: ``odoo19c: odoo/orm/fields_numeric.py:41-42``). Sin protección del grupo
#: tomaría el 10 de ``_compute_start_end`` y ``name`` pasaría a ``'5->10'``.
EXPECTED_GROUP_ROW = {'name': None, 'start': 5, 'end': 0}


def test_django_create_protects_the_whole_computed_group():
    """``start`` llega dado: ``end``, calculado por el mismo método, queda
    protegido con él y no toma el 10 de ``_compute_start_end``."""
    record = SharedCompute.objects.create(start=5)
    _flush()
    assert _shared_row(record.pk) == EXPECTED_GROUP_ROW


def test_orm_create_protects_the_whole_computed_group():
    record = current_env()['test_orm.shared.compute'].sudo().create(
        {'start': 5})
    record.flush_model()
    assert _shared_row(record.id) == EXPECTED_GROUP_ROW


def test_an_explicit_editable_computed_value_is_kept(project, employee,
                                                     sale_line):
    entry = EmployeeMap.objects.create(project=project, employee=employee,
                                       sale_line=sale_line,
                                       cost=Decimal('12.00'))
    _flush()
    assert EmployeeMap.objects.get(pk=entry.pk).cost == Decimal('12.00')


def test_an_explicit_readonly_computed_value_is_recomputed(project, employee,
                                                           sale_line):
    """``price_unit`` es readonly sin precompute: el valor dado se guarda y
    el cómputo de creación lo sustituye por el de la línea."""
    entry = EmployeeMap.objects.create(project=project, employee=employee,
                                       sale_line=sale_line,
                                       price_unit=Decimal('1.00'))
    _flush()
    assert EmployeeMap.objects.get(pk=entry.pk).price_unit == pytest.approx(
        90.0)


@pytest.fixture
def amount_calls(monkeypatch):
    calls = []
    original = SaleOrderLine._compute_amount

    def counting(self):
        calls.append(self.pk)
        return original(self)

    monkeypatch.setattr(SaleOrderLine, '_compute_amount', counting)
    return calls


def _after_insert(calls):
    """Las llamadas sobre la fila ya insertada. Antes del INSERT el cómputo
    corre en ``pre_save`` (precompute) y, además, en ``SaleOrderLine.save``,
    que lo invoca por su cuenta; ese segundo cálculo es del modelo, no del
    marcado de creación, y queda registrado en el diseño."""
    return [pk for pk in calls if pk is not None]


def test_django_create_computes_a_precompute_once(user, amount_calls):
    """``_compute_amount`` es precompute: corre antes del INSERT y el alta
    lo protege, así que el marcado de creación no lo vuelve a correr."""
    product = make_product(name='Hora')
    SaleOrderLine.objects.create(
        order=make_order(user=user), product=product, name=product.name,
        price_unit=Decimal('90.00'), product_uom_qty=1)
    _flush()
    assert _after_insert(amount_calls) == []


def _names(fields):
    return sorted({field.name for field in fields})


def test_the_rule_protects_every_precompute_even_when_not_given():
    """Ningún ``BaseModel`` del árbol declara hoy un precompute, así que la
    vía de ``BaseModel.create`` se mide por la regla que comparte con el
    receptor."""
    assert _names(_protected_on_create(SaleOrderLine, frozenset())) == [
        'price_reduce_taxexcl', 'price_reduce_taxinc', 'price_subtotal',
        'price_tax', 'price_total']


def test_the_rule_skips_a_given_readonly_computed_field():
    assert _names(_protected_on_create(
        EmployeeMap, frozenset({'price_unit'}))) == []


def test_the_rule_protects_a_given_editable_field_and_its_group():
    assert _names(_protected_on_create(
        SharedCompute, frozenset({'start'}))) == ['end', 'start']


def test_the_rule_reads_the_given_attname():
    assert _names(_protected_on_create(
        EmployeeMap, frozenset({'currency_id'}))) == ['currency']


def test_a_rolled_back_creation_leaves_no_pending_marks(project, employee,
                                                        sale_line):
    _flush()
    with pytest.raises(RuntimeError):
        with transaction.atomic():
            EmployeeMap.objects.create(project=project, employee=employee,
                                       sale_line=sale_line)
            raise RuntimeError('deshacer')
    assert _pending_for(EmployeeMap) == []


def test_a_historical_creation_is_not_marked(project, employee,
                                             monkeypatch):
    """El modelo histórico también declara los calculados almacenados
    —sus campos son clones de los del ORM—, pero no tiene disparadores en
    el registro vivo: ``modified`` sobre él no deja marcas aunque se llame.
    Por eso el control mide la llamada, no sólo su resultado."""
    calls = []
    original = orm_models.modified

    def counting(records, fnames, create=False, before=False):
        calls.append(type(records))
        return original(records, fnames, create=create, before=before)

    _flush()
    monkeypatch.setattr(orm_models, 'modified', counting)
    historical = ProjectState.from_apps(apps).apps.get_model(
        'sale_timesheet', 'ProjectSaleLineEmployeeMap')
    assert historical._meta.apps is not apps
    historical.objects.create(project_id=project.pk,
                              employee_id=employee.pk)
    assert calls == []
    assert current_env().fields_to_compute() == []


def test_orm_create_marks_the_creation_once(monkeypatch):
    """``BaseModel._create`` inserta con ``save()`` y llama él mismo
    ``modified(..., create=True)``; el receptor de ``post_save`` no repite
    el marcado de esas filas."""
    calls = []
    original = orm_models.modified

    def counting(records, fnames, create=False, before=False):
        if create:
            calls.append(record_ids(records))
        return original(records, fnames, create=create, before=before)

    monkeypatch.setattr(orm_models, 'modified', counting)
    record = current_env()['test_orm.shared.compute'].sudo().create(
        {'start': 5})
    assert calls == [(record.id,)]


def test_a_value_assigned_before_the_first_save_counts_as_given():
    """``_explicit_values`` se captura al construir. Un valor asignado
    entre ``__init__`` y ``save()`` es igual de explícito: en la fuente
    llegaría en ``vals``. Sin registrarlo, el cómputo de creación pisaba el
    5 de ``start`` con el 0 de ``_compute_start_end``."""
    record = SharedCompute()
    record.start = 5
    record.save()
    _flush()
    assert _shared_row(record.pk) == EXPECTED_GROUP_ROW


def test_construction_values_are_not_recorded_twice():
    record = SharedCompute(start=5)
    assert record._explicit_values == frozenset({'start'})
