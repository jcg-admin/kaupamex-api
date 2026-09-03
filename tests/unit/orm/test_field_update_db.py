"""El eje de esquema de ``Field`` — tareas #211 y #346.

Porta los cinco metodos con que un campo lleva su forma a la tabla
(``odoo19c: odoo/orm/fields.py:1094-1202``): :func:`update_db`,
:func:`update_db_column`, :func:`_convert_db_column`,
:func:`update_db_notnull` y :func:`update_db_related`; mas los dos de
``BaseModel`` que el tercero consume — ``_table_has_rows`` (``:3163``) y
``_init_column`` (``:3137``).

**Los casos corren contra un modelo real y su tabla real**, que es lo que la
tarea #346 pide: ``res.partner.bank`` sobre ``res_partner_bank``, con su FK
``bank`` hacia ``res.bank``. El DDL se emite dentro de la transaccion que
pytest revierte, asi que la tabla queda como estaba.

**El control que discrimina** es
``test_a_diverging_type_is_converted_back``: se cambia el tipo de la columna
en la base y se comprueba que el metodo la devuelve al del campo. Un
``update_db_column`` que solo supiera crear columnas pasaria el resto de los
casos igual.
"""
import pytest
from django.db import connection

from orm.registry import MODELS_BY_NAME, Registry, clear_cache
from orm.utils import model_field_registry
from tools.sql import table_columns

TABLE = 'res_partner_bank'


@pytest.fixture
def model(db):
    """La clase de modelo bajo prueba — ``res.partner.bank``."""
    return MODELS_BY_NAME['res.partner.bank']


@pytest.fixture
def fields(model):
    """El mapa ``nombre -> campo`` del modelo."""
    return model_field_registry(model)


@pytest.fixture
def cursor(db):
    """Un cursor sobre la conexion de la prueba."""
    with connection.cursor() as cur:
        yield cur


def _columns(cursor):
    return table_columns(cursor, TABLE)


def _bank_account(model, acc_number, **extra):
    """Una cuenta bancaria real, con su titular, lista para que siga DDL.

    El ``check_constraints()`` del final no es adorno: en una base de pruebas
    las FK de Django se declaran ``DEFERRABLE INITIALLY DEFERRED``, asi que
    cada ``INSERT`` deja eventos de trigger pendientes hasta el commit — y
    PostgreSQL rechaza un ``ALTER TABLE`` mientras los haya
    (``cannot ALTER TABLE ... because it has pending trigger events``). El
    metodo del backend los resuelve con ``SET CONSTRAINTS ALL IMMEDIATE``
    seguido de ``DEFERRED``
    (``django/db/backends/postgresql/base.py:477-484``).

    Es un artefacto de medir DML y DDL dentro de la misma transaccion, no del
    codigo bajo prueba: en el arranque real el eje de esquema corre sobre una
    conexion sin inserciones pendientes.
    """
    partner_model = MODELS_BY_NAME['res.partner']
    partner = partner_model.objects.create(name='Titular de prueba')
    row = model.objects.create(partner=partner, acc_number=acc_number, **extra)
    connection.check_constraints()
    return row


class TestUpdateDb:

    def test_a_field_without_column_is_left_alone(self, model, fields, cursor):
        """``bank_name`` no persiste, asi que el eje de esquema no lo toca."""
        before = set(_columns(cursor))
        assert fields['bank_name'].update_db(model, _columns(cursor)) is False
        assert set(_columns(cursor)) == before

    def test_an_existing_column_needs_no_recompute(self, model, fields, cursor):
        assert fields['note'].update_db(model, _columns(cursor)) is False

    def test_a_missing_column_is_created_and_asks_for_recompute(
            self, model, fields, cursor):
        cursor.execute(f'ALTER TABLE {TABLE} DROP COLUMN note')
        assert 'note' not in _columns(cursor)
        assert fields['note'].update_db(model, _columns(cursor)) is True
        assert _columns(cursor)['note']['udt_name'] == 'text'


class TestUpdateDbColumn:

    def test_creates_the_column_with_the_field_type(self, model, fields, cursor):
        cursor.execute(f'ALTER TABLE {TABLE} DROP COLUMN note')
        fields['note'].update_db_column(model, None)
        assert _columns(cursor)['note']['udt_name'] == 'text'

    def test_a_matching_type_is_left_alone(self, model, fields, cursor):
        column = _columns(cursor)['sequence']
        fields['sequence'].update_db_column(model, column)
        assert _columns(cursor)['sequence']['udt_name'] == 'int4'

    def test_a_diverging_type_is_converted_back(self, model, fields, cursor):
        """El control: la columna se lleva a otro tipo y el metodo la devuelve."""
        cursor.execute(
            f'ALTER TABLE {TABLE} ALTER COLUMN sequence TYPE varchar')
        column = _columns(cursor)['sequence']
        assert column['udt_name'] == 'varchar'
        fields['sequence'].update_db_column(model, column)
        assert _columns(cursor)['sequence']['udt_name'] == 'int4'


class TestUpdateDbNotnull:

    def test_drops_not_null_when_the_field_is_not_required(
            self, model, fields, cursor):
        assert _columns(cursor)['note']['is_nullable'] == 'NO'
        assert fields['note'].required is False
        fields['note'].update_db_notnull(model, _columns(cursor)['note'])
        assert _columns(cursor)['note']['is_nullable'] == 'YES'

    def test_a_required_field_defers_the_constraint_to_post_init(
            self, model, fields, cursor, monkeypatch):
        """La restriccion NO se aplica en el acto: se encola para el final de
        ``init_models``, que es lo que la fuente hace con ``pool.post_init``."""
        cursor.execute(f'ALTER TABLE {TABLE} ALTER COLUMN note DROP NOT NULL')
        monkeypatch.setattr(fields['note'], 'required', True, raising=False)

        registry = Registry('default')
        registry._post_init_queue = []
        registry._is_install = False
        try:
            fields['note'].update_db_notnull(model, _columns(cursor)['note'])
            assert len(registry._post_init_queue) == 1
            assert _columns(cursor)['note']['is_nullable'] == 'YES'
            registry._post_init_queue.pop()()
            assert _columns(cursor)['note']['is_nullable'] == 'NO'
        finally:
            del registry._post_init_queue
            del registry._is_install
            registry._constraint_queue.clear()

    def test_a_new_column_gets_its_default_on_the_rows_that_exist(
            self, model, fields, cursor):
        _bank_account(model, 'MX-0001')
        cursor.execute(f'ALTER TABLE {TABLE} DROP COLUMN note')
        cursor.execute(f'ALTER TABLE {TABLE} ADD COLUMN note text')
        clear_cache()

        fields['note'].update_db_notnull(model, None)

        cursor.execute(f'SELECT note FROM {TABLE}')
        assert cursor.fetchone()[0] == ''


class TestTableHasRows:

    def test_an_empty_table_has_no_rows(self, model, cursor):
        clear_cache()
        assert model._table_has_rows() is False

    def test_one_row_is_enough(self, model, cursor):
        _bank_account(model, 'MX-0002')
        clear_cache()
        assert model._table_has_rows() is True


class TestInitColumn:

    def test_the_default_of_the_field_lands_on_the_null_rows(
            self, model, fields, cursor):
        _bank_account(model, 'MX-0003')
        cursor.execute(f'ALTER TABLE {TABLE} ALTER COLUMN note DROP NOT NULL')
        cursor.execute(f'UPDATE {TABLE} SET note = NULL')

        model._init_column('note')

        cursor.execute(f'SELECT note FROM {TABLE}')
        assert cursor.fetchone()[0] == ''

    def test_a_field_without_default_leaves_the_column_alone(
            self, model, fields, cursor):
        _bank_account(model, 'MX-0004')
        cursor.execute(f'ALTER TABLE {TABLE} ALTER COLUMN note DROP NOT NULL')
        cursor.execute(f'UPDATE {TABLE} SET note = NULL')

        model._init_column('acc_holder_name')

        cursor.execute(f'SELECT note FROM {TABLE}')
        assert cursor.fetchone()[0] is None


class TestUpdateDbRelated:

    def test_the_column_is_filled_from_the_comodel_in_one_statement(
            self, model, fields, cursor, monkeypatch):
        """``acc_holder_name`` se declara related de ``bank.name`` y el metodo
        lo llena con un solo ``UPDATE ... FROM``, sin recorrer las filas."""
        bank_model = MODELS_BY_NAME['res.bank']
        bank = bank_model.objects.create(name='Banco de prueba')
        _bank_account(model, 'MX-0005', bank=bank)

        target = model_field_registry(bank_model)['name']
        monkeypatch.setattr(fields['acc_holder_name'], 'related', 'bank.name',
                            raising=False)
        monkeypatch.setattr(fields['acc_holder_name'], 'related_field', target,
                            raising=False)

        fields['acc_holder_name'].update_db_related(model)

        cursor.execute(f'SELECT acc_holder_name FROM {TABLE}')
        assert cursor.fetchone()[0] == 'Banco de prueba'


class TestConvertToColumnInsertFromInitColumn:
    """El receptor que ``_init_column`` pasa es la CLASE, no una fila.

    ``_init_column`` (``odoo19c: odoo/orm/models.py:3137``) llama a
    ``convert_to_column_insert`` sobre el mismo receptor con que se lo invoca.
    En la fuente ese receptor es un recordset vacio —una instancia— y
    ``record._name`` responde igual. Aqui es la clase de modelo, y
    ``type(record)`` sobre una clase da ``ModelBase``, que no tiene ``_meta``.

    Sin cobertura, la rama solo revienta cuando el eje de esquema alcanza un
    campo dependiente de empresa con default: la unica familia que consulta
    ``ir.default`` por el nombre del modelo.
    """

    def test_a_company_dependent_field_takes_the_model_class(self, db):
        partner_model = MODELS_BY_NAME['res.partner']
        field = model_field_registry(partner_model)['barcode']
        assert field.company_dependent is True

        value = field.convert_to_column_insert('MX-BARCODE-1', partner_model)

        assert value is not None
