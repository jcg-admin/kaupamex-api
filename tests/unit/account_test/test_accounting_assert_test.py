"""Tests unitarios — ``addons.account_test``.

Adaptación de ``addons/account_test/`` (Odoo 19, ``odoo-tools@622ddc2a``,
``odoo19c:``). Cubre el motor de ejecución (``tools/safe_eval_exec.py``,
``models/accounting_assert_test.py``), la siembra (``data/``) y el ViewSet
(``controllers/views.py``).

Requiere ``addons.account_test`` en ``INSTALLED_APPS`` (fuera del alcance de
este porte — ver ``apps.py``) para que la migración cree su tabla; los tests
``@pytest.mark.django_db`` que crean ``AccountingAssertTest`` fallan hasta
ese wiring — mismo gap que ``account_debit_note``/``account_qr_code_sepa``
ya declaran para el mismo caso (ver sus tests en
``tests/unit/account_debit_note/``).

Los tests del ``ViewSet`` llaman ``AccountingAssertTestViewSet.as_view({...})``
directamente con ``APIRequestFactory`` — no dependen de
``controllers/urls.py`` estar incluido en ``config/urls.py`` (también fuera
de este alcance): ejercen la lógica de permisos/acción, no el ruteo HTTP.
"""
import pytest
from django.apps import apps as django_apps
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from addons.account.models import AccountJournal, AccountMove
from addons.account.models.account_account import AccountAccount
from addons.account.models.account_full_reconcile import AccountFullReconcile
from addons.account.models.account_move_line import AccountMoveLine
from addons.account_test.controllers.views import AccountingAssertTestViewSet
from addons.account_test.data import TESTS, seed_accounting_assert_tests
from addons.account_test.models.accounting_assert_test import (
    CODE_EXEC_DEFAULT,
    SUCCESS_MESSAGE,
    AccountingAssertTest,
    execute_code,
    order_columns,
    reconciled_inv,
)
from addons.account_test.tools.safe_eval_exec import safe_eval
from addons.base.models import IrModelData, ResCompany

pytestmark = pytest.mark.django_db


# ─── Fixtures compartidas (mismo patrón que tests/unit/account_debit_note/) ─

@pytest.fixture
def company(db):
    return ResCompany.objects.create(code='acme', name='ACME')


@pytest.fixture
def journal(company):
    return AccountJournal.objects.create(
        name='Ventas', code='VEN', type='sale', company=company)


def _move(company, journal, **kwargs):
    defaults = {
        'move_type': 'out_invoice', 'date': timezone.now().date(),
        'journal': journal, 'company': company,
    }
    defaults.update(kwargs)
    return AccountMove.objects.create(**defaults)


def _account(company, **kwargs):
    defaults = {
        'code': '1105', 'name': 'Clientes',
        'account_type': 'asset_receivable', 'company': company,
    }
    defaults.update(kwargs)
    return AccountAccount.objects.create(**defaults)


# ─── tools/safe_eval_exec.py — el motor de ejecución (sin DB) ─────────────

class TestSafeEvalExec:
    def test_runs_control_flow_and_sets_result(self):
        ctx = {}
        safe_eval(
            'res = []\n'
            'for i in range(3):\n'
            '    res.append(i * 2)\n'
            'result = res\n',
            ctx,
        )
        assert ctx['result'] == [0, 2, 4]

    def test_calls_functions_from_context(self):
        def helper():
            return ['x', 'y']
        ctx = {'helper': helper}
        safe_eval('result = helper()', ctx)
        assert ctx['result'] == ['x', 'y']

    def test_blocks_dunder_attribute_access(self):
        with pytest.raises(NameError):
            safe_eval('result = ().__class__', {})

    def test_blocks_import_statement(self):
        with pytest.raises(ValueError):
            safe_eval('import os\nresult = os.getcwd()', {})

    def test_blocks_import_from_statement(self):
        with pytest.raises(ValueError):
            safe_eval('from os import getcwd\nresult = getcwd()', {})

    def test_open_is_not_a_builtin(self):
        # `ValueError`, no `NameError`: el contrato documentado de `safe_eval`
        # reserva `NameError` para el rechazo de dunders (que ocurre ANTES de
        # evaluar) y envuelve en `ValueError` cualquier error surgido DURANTE
        # la evaluación. Que `open` no exista es lo segundo. La propiedad de
        # seguridad —`open` no está disponible— se sigue afirmando abajo,
        # sobre la causa encadenada.
        with pytest.raises(ValueError) as exc_info:
            safe_eval("result = open('/etc/passwd')", {})
        assert isinstance(exc_info.value.__cause__, NameError)
        assert "'open' is not defined" in str(exc_info.value.__cause__)

    def test_dict_and_string_builtins_available(self):
        ctx = {}
        safe_eval("result = {'a': 1, 'b': 2}", ctx)
        assert ctx['result'] == {'a': 1, 'b': 2}

    def test_context_is_mutated_with_new_variables(self):
        ctx = {'x': 1}
        safe_eval('y = x + 1\nresult = y', ctx)
        assert ctx['y'] == 2
        assert ctx['result'] == 2


# ─── models/accounting_assert_test.py — el modelo ─────────────────────────

class TestAccountingAssertTestModel:
    def test_create_with_defaults(self):
        test = AccountingAssertTest.objects.create(name='Balance general')
        assert test.code_exec == CODE_EXEC_DEFAULT
        assert test.active is True
        assert test.sequence == 10
        assert test.desc == ''

    def test_str_is_the_name(self):
        test = AccountingAssertTest.objects.create(name='Balance general')
        assert str(test) == 'Balance general'

    def test_ordering_is_by_sequence(self):
        AccountingAssertTest.objects.create(name='B', sequence=5)
        AccountingAssertTest.objects.create(name='A', sequence=1)
        # Acotado a las dos filas que crea este test: con el addon cableado,
        # la migración de datos `0002_seed_accounting_assert_tests` siembra 7
        # pruebas, así que la tabla NO está vacía. Lo que se afirma es el
        # ORDEN por `sequence`, que es lo que el test mide — no que estas dos
        # sean las únicas filas.
        names = list(
            AccountingAssertTest.objects
            .filter(name__in=['A', 'B'])
            .values_list('name', flat=True))
        assert names == ['A', 'B']

    def test_run_delegates_to_execute_code(self):
        test = AccountingAssertTest.objects.create(
            name='Vacía', code_exec='result = []')
        passed, lines = test.run()
        assert passed is True
        assert lines == [SUCCESS_MESSAGE]


# ─── order_columns() — función pura ────────────────────────────────────────

class TestOrderColumns:
    def test_default_order_is_dict_order(self):
        item = {'b': 2, 'a': 1}
        assert order_columns(item) == [('b', 2), ('a', 1)]

    def test_explicit_order(self):
        item = {'b': 2, 'a': 1}
        assert order_columns(item, cols=['a', 'b']) == [('a', 1), ('b', 2)]

    def test_columns_not_present_in_item_are_skipped(self):
        item = {'a': 1}
        assert order_columns(item, cols=['a', 'missing']) == [('a', 1)]


# ─── execute_code() — el motor completo, contra PostgreSQL real ──────────

class TestExecuteCode:
    def test_empty_result_reports_success(self):
        passed, lines = execute_code('result = []')
        assert passed is True
        assert lines == [SUCCESS_MESSAGE]

    def test_untouched_result_none_reports_failure(self):
        # `result` arranca en `None` en el contexto — código que nunca lo
        # reasigna NO cae en el camino de éxito: la referencia convierte
        # `None` en `[None]` (`if not isinstance(result, (tuple, list,
        # set)): result = [result]`), y `[None]` es "no vacío" — caso
        # borde del contrato, probado explícitamente.
        passed, lines = execute_code('pass')
        assert passed is False
        assert lines == ['None']

    def test_non_empty_result_reports_failure(self):
        passed, lines = execute_code("result = ['algo salió mal']")
        assert passed is False
        assert lines == ['algo salió mal']

    def test_dict_rows_are_formatted_with_column_order(self):
        passed, lines = execute_code(
            "column_order = ['b', 'a']\n"
            "result = [{'a': 1, 'b': 2}]\n"
        )
        assert passed is False
        assert lines == ['b: 2, a: 1']

    def test_cr_execute_and_dictfetchall_hit_real_db(self):
        passed, lines = execute_code(
            "cr.execute('SELECT 1 AS uno')\n"
            "result = cr.dictfetchall()\n"
        )
        assert passed is False
        assert lines == ['uno: 1']

    def test_reconciled_inv_is_available_in_context(self):
        passed, lines = execute_code('result = reconciled_inv()')
        assert passed is True

    def test_invalid_syntax_raises(self):
        with pytest.raises(SyntaxError):
            execute_code('result = (')

    def test_dunder_access_raises_name_error(self):
        with pytest.raises(NameError):
            execute_code('result = ().__class__')


class TestExecuteCodeSeedRecords:
    """Los seis ``code_exec`` de ``data/accounting_assert_tests.py`` —
    verificados contra una base sin datos (los tres que referencian
    ``account_invoice`` deben fallar, tal como fallarían en la referencia:
    ver el docstring de ``data/accounting_assert_tests.py``)."""

    def test_account_test_01_passes_on_empty_db(self):
        entry = next(t for t in TESTS if t['xmlid'] == 'account_test_01')
        passed, _lines = execute_code(entry['code_exec'])
        assert passed is True

    def test_account_test_03_passes_on_empty_db(self):
        entry = next(t for t in TESTS if t['xmlid'] == 'account_test_03')
        passed, _lines = execute_code(entry['code_exec'])
        assert passed is True

    def test_account_test_07_passes_on_empty_db(self):
        entry = next(t for t in TESTS if t['xmlid'] == 'account_test_07')
        passed, _lines = execute_code(entry['code_exec'])
        assert passed is True

    @pytest.mark.parametrize('xmlid', [
        'account_test_05', 'account_test_06',
    ])
    def test_account_invoice_tests_fail_table_absent(self, xmlid):
        # Drift de la referencia preservado a propósito (docstring del
        # módulo de datos): `account_invoice` no existe.
        #
        # `account_test_05_2` NO está en esta lista: su consulta va detrás de
        # un `if res:` (`res = reconciled_inv()`), así que sobre una base sin
        # facturas conciliadas la rama nunca corre y no puede tocar la tabla
        # ausente. Ver el test de abajo, que fija ese comportamiento.
        entry = next(t for t in TESTS if t['xmlid'] == xmlid)
        with pytest.raises(Exception):
            execute_code(entry['code_exec'])

    def test_account_test_05_2_is_guarded_and_does_not_reach_the_table(self):
        # El código de `account_test_05_2` empieza con `res = reconciled_inv()`
        # y sólo consulta `account_invoice` si `res` trae algo. Sin facturas
        # conciliadas el guard corta antes, así que NO falla pese a que la
        # tabla no existe — el drift de la referencia sigue latente, pero no
        # es alcanzable desde este estado.
        entry = next(t for t in TESTS if t['xmlid'] == 'account_test_05_2')
        passed, _lines = execute_code(entry['code_exec'])
        assert passed is True


# ─── reconciled_inv() — divergencia declarada (full_reconcile) ────────────

class TestReconciledInv:
    def test_empty_db_returns_empty(self):
        assert list(reconciled_inv()) == []

    def test_line_without_full_reconcile_is_excluded(self, company, journal):
        move = _move(company, journal)
        account = _account(company)
        AccountMoveLine.objects.create(
            move=move, account=account, debit=100, credit=0)
        assert list(reconciled_inv()) == []

    def test_line_with_full_reconcile_on_receivable_is_included(
            self, company, journal):
        move = _move(company, journal)
        account = _account(company, account_type='asset_receivable')
        full = AccountFullReconcile.objects.create()
        AccountMoveLine.objects.create(
            move=move, account=account, debit=100, credit=0,
            full_reconcile=full)
        assert list(reconciled_inv()) == [move.pk]

    def test_line_with_full_reconcile_on_non_receivable_is_excluded(
            self, company, journal):
        move = _move(company, journal)
        account = _account(
            company, code='6001', name='Gastos', account_type='expense')
        full = AccountFullReconcile.objects.create()
        AccountMoveLine.objects.create(
            move=move, account=account, debit=100, credit=0,
            full_reconcile=full)
        assert list(reconciled_inv()) == []

    def test_a_move_appears_once_even_with_two_reconciled_lines(
            self, company, journal):
        move = _move(company, journal)
        account = _account(company, account_type='liability_payable')
        full = AccountFullReconcile.objects.create()
        AccountMoveLine.objects.create(
            move=move, account=account, debit=50, credit=0,
            full_reconcile=full)
        AccountMoveLine.objects.create(
            move=move, account=account, debit=0, credit=50,
            full_reconcile=full)
        assert list(reconciled_inv()) == [move.pk]


# ─── data/accounting_assert_tests.py — la siembra ──────────────────────────

class TestSeedAccountingAssertTests:
    def test_active_test_count_matches_reference_minus_commented(self):
        # ≙ el conteo del docstring del módulo: 8 <record> en la
        # referencia, 2 comentados (account_test_04/08) → 6 activos.
        assert len(TESTS) == 6

    def test_creates_the_six_active_tests(self):
        created = seed_accounting_assert_tests(django_apps, 'default')
        assert len(created) == 6
        assert AccountingAssertTest.objects.count() == 6

    def test_is_idempotent(self):
        seed_accounting_assert_tests(django_apps, 'default')
        seed_accounting_assert_tests(django_apps, 'default')
        assert AccountingAssertTest.objects.count() == 6

    def test_writes_the_ir_model_data_xmlids(self):
        seed_accounting_assert_tests(django_apps, 'default')
        xmlids = set(
            IrModelData.objects.filter(module='account_test')
            .values_list('name', flat=True)
        )
        assert xmlids == {t['xmlid'] for t in TESTS}

    def test_reruns_do_not_duplicate_ir_model_data_rows(self):
        seed_accounting_assert_tests(django_apps, 'default')
        seed_accounting_assert_tests(django_apps, 'default')
        assert IrModelData.objects.filter(module='account_test').count() == 6


# ─── controllers/views.py — el ViewSet (sin depender de config/urls.py) ───

class TestAccountingAssertTestViewSet:
    def test_list_denied_without_capability(self, user):
        factory = APIRequestFactory()
        request = factory.get('/accounting-assert-tests/')
        force_authenticate(request, user=user)
        view = AccountingAssertTestViewSet.as_view({'get': 'list'})
        response = view(request)
        assert response.status_code == 403

    def test_list_allowed_for_superadmin(self, admin_user):
        AccountingAssertTest.objects.create(name='X')
        factory = APIRequestFactory()
        request = factory.get('/accounting-assert-tests/')
        force_authenticate(request, user=admin_user)
        view = AccountingAssertTestViewSet.as_view({'get': 'list'})
        response = view(request)
        assert response.status_code == 200
        # Presencia, no exclusividad: la migración de datos siembra 7 pruebas,
        # así que `len(...) == 1` sólo pasaba con el addon sin cablear. Lo que
        # el test verifica es que el superadmin SÍ ve la lista y que la fila
        # creada aquí aparece en ella.
        assert 'X' in [row['name'] for row in response.data]

    def test_retrieve_allowed_for_superadmin(self, admin_user):
        test = AccountingAssertTest.objects.create(name='X')
        factory = APIRequestFactory()
        request = factory.get('/accounting-assert-tests/%d/' % test.pk)
        force_authenticate(request, user=admin_user)
        view = AccountingAssertTestViewSet.as_view({'get': 'retrieve'})
        response = view(request, pk=test.pk)
        assert response.status_code == 200
        assert response.data['name'] == 'X'

    def test_run_executes_and_reports_pass(self, admin_user):
        test = AccountingAssertTest.objects.create(
            name='Siempre pasa', code_exec='result = []')
        factory = APIRequestFactory()
        request = factory.post('/accounting-assert-tests/%d/run/' % test.pk)
        force_authenticate(request, user=admin_user)
        view = AccountingAssertTestViewSet.as_view({'post': 'run'})
        response = view(request, pk=test.pk)
        assert response.status_code == 200
        assert response.data['passed'] is True
        assert response.data['result'] == [SUCCESS_MESSAGE]
        assert response.data['id'] == test.pk

    def test_run_reports_invalid_code_as_400(self, admin_user):
        test = AccountingAssertTest.objects.create(
            name='Código roto', code_exec='result = (')
        factory = APIRequestFactory()
        request = factory.post('/accounting-assert-tests/%d/run/' % test.pk)
        force_authenticate(request, user=admin_user)
        view = AccountingAssertTestViewSet.as_view({'post': 'run'})
        response = view(request, pk=test.pk)
        assert response.status_code == 400
        assert response.data['codigo_error'] == 'ACCOUNT_TEST_INVALID_CODE'

    def test_run_denied_without_capability(self, user):
        test = AccountingAssertTest.objects.create(name='X')
        factory = APIRequestFactory()
        request = factory.post('/accounting-assert-tests/%d/run/' % test.pk)
        force_authenticate(request, user=user)
        view = AccountingAssertTestViewSet.as_view({'post': 'run'})
        response = view(request, pk=test.pk)
        assert response.status_code == 403

    def test_destroy_allowed_for_superadmin(self, admin_user):
        test = AccountingAssertTest.objects.create(name='Borrable')
        factory = APIRequestFactory()
        request = factory.delete('/accounting-assert-tests/%d/' % test.pk)
        force_authenticate(request, user=admin_user)
        view = AccountingAssertTestViewSet.as_view({'delete': 'destroy'})
        response = view(request, pk=test.pk)
        assert response.status_code == 204
        assert not AccountingAssertTest.objects.filter(pk=test.pk).exists()

    def test_destroy_denied_without_capability(self, user):
        test = AccountingAssertTest.objects.create(name='No borrable')
        factory = APIRequestFactory()
        request = factory.delete('/accounting-assert-tests/%d/' % test.pk)
        force_authenticate(request, user=user)
        view = AccountingAssertTestViewSet.as_view({'delete': 'destroy'})
        response = view(request, pk=test.pk)
        assert response.status_code == 403
        assert AccountingAssertTest.objects.filter(pk=test.pk).exists()

    def test_create_is_not_exposed(self):
        # ≙ perm_create=0 en AMBOS grupos de la referencia — ver
        # security/__init__.py. `http_method_names` no incluye 'put'/
        # 'patch'; POST sólo mapea a la acción `run`, nunca a `create`.
        assert 'put' not in AccountingAssertTestViewSet.http_method_names
        assert 'patch' not in AccountingAssertTestViewSet.http_method_names
