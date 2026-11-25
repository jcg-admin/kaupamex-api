"""El orden de ``BaseModel.write``: validar, invertir por lote, validar —
TASK-API-0510.

≙ ``odoo19c: odoo/orm/models.py:4488-4514``: dentro del alcance de
protección, ``real_recs._validate_fields(vals, inverse_fields)`` valida primero
las restricciones que no nombran ningún campo invertido; después cada grupo de
inversos corre UNA vez sobre todos los registros, y al final se validan los
campos invertidos (``designs/orm-write-validation-order-0510.md``).

*Métrica:* el ``log`` que dejan el inverso y las restricciones de
``test_orm.compute.inverse``, en orden.
*Ciega a:* ``_check_company``, que sigue corriendo por fila (fuera de esta
unidad).
"""
import pytest

import api
from exceptions import ValidationError
from orm import registry
from orm.environments import Environment
from orm.utils import SUPERUSER_ID

pytestmark = pytest.mark.django_db


@pytest.fixture
def env(db, system_user):
    with Environment(None, SUPERUSER_ID, {}) as environment:
        yield environment


@pytest.fixture
def baz_check():
    """Cuelga un ``@api.constrains('baz')`` en la clase y lo retira.

    Es el mecanismo por el que un addon añade una restricción: un método
    marcado en la clase. ``clear_marked_methods`` reconstruye el colector
    antes y después.
    """
    with Environment(None, SUPERUSER_ID, {}) as environment:
        model_cls = type(environment['test_orm.compute.inverse'])
    state = {'fail': False}

    @api.constrains('baz')
    def _check_baz_only(self):
        self.env.context.get('log', []).append('constraint-baz')
        if state['fail']:
            raise ValidationError('baz rechazado')

    model_cls._check_baz_only = _check_baz_only
    registry.clear_marked_methods()
    try:
        yield state
    finally:
        del model_cls._check_baz_only
        registry.clear_marked_methods()


def _model(env, log):
    return env['test_orm.compute.inverse'].browse(()).with_context(
        log=log, log_constraint=True)


def test_the_inverse_runs_once_for_the_whole_batch(env):
    log = []
    records = _model(env, log).create([{'baz': 'a'}, {'baz': 'b'}])
    log.clear()
    records.write({'bar': 'x'})
    assert log.count('inverse') == 1


def test_non_inversed_constraints_run_before_the_inverse(env, baz_check):
    log = []
    record = _model(env, log).create({'baz': 'a'})
    log.clear()
    record.write({'bar': 'x', 'baz': 'y'})
    assert log == ['constraint-baz', 'inverse', 'constraint']


def test_a_failing_non_inversed_constraint_stops_before_the_inverse(
        env, baz_check):
    log = []
    record = _model(env, log).create({'baz': 'a'})
    log.clear()
    baz_check['fail'] = True
    with pytest.raises(ValidationError):
        record.write({'bar': 'x', 'baz': 'y'})
    assert 'inverse' not in log


def test_writing_only_the_normal_field_runs_no_inverse(env, baz_check):
    log = []
    record = _model(env, log).create({'baz': 'a'})
    log.clear()
    record.write({'baz': 'y'})
    assert log == ['constraint-baz', 'constraint']
