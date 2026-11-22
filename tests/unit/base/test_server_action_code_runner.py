"""El corredor del modo ``code`` de ``ir.actions.server``.

≙ ``_run_action_code_multi``
(``odoo19c: odoo/addons/base/models/ir_actions.py:1013-1017``), ``LoggerProxy``
(``:30-54``) y los dos ``_get_eval_context`` (``:140-153`` y ``:1111-1149``).
Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
server-action-code-runner.md``.

Qué haría fallar a estos casos: sin corredor, ``run()`` registra «no hay manera
de ejecutar» y devuelve ``False``; cada caso afirma un efecto del código
(una fila escrita, un valor devuelto, un registro en el log), no la forma del
resultado.

*Métrica:* el efecto observable del código evaluado.
*Ciega a:* el aislamiento de ``safe_eval`` más allá del caso de ``import``,
que mide su propia suite.
"""
import logging

import pytest

from addons.base.models.ir_actions import IrActionsServer, LoggerProxy
from addons.base.models.res_partner import ResPartner
from fields import Command
from orm.environments import context_scope, sudo

pytestmark = pytest.mark.django_db

PARTNER = 'base.ResPartner'


@pytest.fixture(autouse=True)
def _elevated():
    with sudo():
        yield


def _code(code, model_name=PARTNER):
    return IrActionsServer.objects.create(
        name='Codigo', state='code', model_name=model_name, code=code)


def test_empty_code_returns_none():
    assert _code('').run() is None


def test_code_writes_through_the_active_record():
    partner = ResPartner.objects.create(name='Antes')
    action = _code("record.write({'name': 'Despues'})")
    with context_scope(active_model=PARTNER, active_id=partner.pk):
        action.run()
    partner.refresh_from_db()
    assert partner.name == 'Despues'


def test_the_action_variable_is_the_result():
    action = _code("action = {'type': 'ir.actions.act_window_close'}")
    assert action.run() == {'type': 'ir.actions.act_window_close'}


def test_the_context_carries_the_source_keys():
    action = _code(
        "action = [model is not None, env is not None, Command is not None,"
        " datetime.date(2026, 1, 2).day, b64decode(b64encode(b'x')),"
        " float_compare(1.0, 1.0, precision_digits=2)]")
    assert action.run() == [True, True, True, 2, b'x', 0]
    assert action._get_eval_context()['Command'] is Command


def test_code_cannot_import():
    with pytest.raises(Exception):
        _code('import os').run()


def test_the_logger_is_the_proxy(caplog):
    action = _code("_logger.info('desde el codigo')")
    assert action._get_eval_context()['_logger'] is LoggerProxy
    with caplog.at_level(logging.INFO):
        action.run()
    assert any(r.name.endswith('server_action_safe_eval')
               and r.getMessage() == 'desde el codigo'
               for r in caplog.records)


def test_an_equation_value_is_evaluated():
    action = IrActionsServer.objects.create(
        name='Ecuacion', state='object_write', model_name=PARTNER,
        evaluation_type='equation', value='2 + 3')
    assert action._eval_value(action._get_eval_context()) == {action.pk: 5}
