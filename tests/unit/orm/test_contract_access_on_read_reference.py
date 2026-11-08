"""Lectura por atributo bajo reglas de acceso, contra ``odoo19c``.

El escenario siembra un grupo con ACL sobre ``test_orm.related``, su modelo
delegante ``test_orm.related_inherits``, ``res.users`` y ``res.partner``, y
dos reglas de fila que ocultan ``secret`` y ``secret-partner``. Un usuario de
ese grupo lee por atributo; la referencia corre el mismo escenario en su
proceso aislado (``tests/fixtures/reference_access_on_read.py``).

Lo que la referencia fija, medido:

- leer un registro prohibido levanta ``AccessError`` —``Field.__get__`` →
  ``_fetch_field`` → ``fetch`` → ``check_access('read')``
  (``odoo19c: odoo/orm/models.py:3775-3818``)—, y en modo superusuario no;
- las reglas del padre aplican al modelo delegante
  (``odoo/addons/base/models/ir_rule.py:144-150``): el hijo de un padre
  prohibido no se lee, ni siquiera su propia clave;
- un campo heredado (``related_sudo=False``) no salta las reglas del padre;
  las redeclaraciones de ``res.users`` —``name`` y ``email``, con
  ``related_sudo`` por omisión— sí (``res_users.py:250-255``);
- ``env.user`` es elevado (``environments.py:208-213``): sus campos
  heredados se leen aunque el partner esté prohibido.

*Métrica:* ``repr`` del valor o nombre de la excepción por escenario.
*Ciega a:* ``groups`` en el campo, que exige los modelos de prueba con
``groups=`` y es otra unidad; y a la escritura.
"""
import pytest
from django.contrib.auth import get_user_model
from django.db import transaction

from exceptions import AccessError

from orm.environments import env as current_env
from orm.environments import get_current_user, sudo, user_scope
from orm.registry import MODELS_BY_NAME
from tests.fixtures import reference_process

pytestmark = [pytest.mark.reference, pytest.mark.django_db]

MODELS = ('test_orm.related', 'test_orm.related_inherits',
          'test_orm.related_foo', 'test_orm.related_bar', 'res.users',
          'res.partner')

#: Diferencias abiertas, con su motivo y su sucesor. Cada una debe seguir
#: siendo diferencia: cuando se cierre, la prueba exige retirarla de aquí.
OPEN = {
    # ``res.users`` no es todavía un ``BaseModel`` (tarea #96): su fila de
    # Django no tiene gancho de lectura, y leer una columna propia de un
    # usuario cuyo partner está prohibido devuelve el valor. La regla del
    # partner sí aplica a su búsqueda desde este pase. Sucesor:
    # TASK-API-0182.
    'users own login': 'AccessError',
}


def _seed():
    G, A, R, IM = (MODELS_BY_NAME[name] for name in (
        'res.groups', 'ir.model.access', 'ir.rule', 'ir.model'))
    group = G.objects.create(name='access-on-read')
    reader = get_user_model().objects.create_user(
        login='access-reader', password=None, name='access-reader')
    reader.group_ids.add(group)
    for name in MODELS:
        label = MODELS_BY_NAME[name]._meta.label
        model = (IM.objects.filter(model=label).first()
                 or IM.objects.create(model=label, name=name))
        A.objects.create(name=name, model_id=model, group_id=group,
                         perm_read=True, perm_write=True, perm_create=True,
                         perm_unlink=True)
    for name, domain in (('test_orm.related', "[('name', '!=', 'secret')]"),
                         ('res.partner',
                          "[('name', '!=', 'secret-partner')]")):
        rule = R.objects.create(
            name=f'hide {name}', model_name=MODELS_BY_NAME[name]._meta.label,
            domain_force=domain)
        rule.groups.add(group)
    writing = G.objects.create(name='access-on-write')
    writer = get_user_model().objects.create_user(
        login='access-writer', password=None, name='access-writer')
    writer.group_ids.add(writing)
    for name in ('test_orm.related', 'test_orm.related_inherits'):
        label = MODELS_BY_NAME[name]._meta.label
        A.objects.create(
            name=f'{name} writer', model_id=IM.objects.get(model=label),
            group_id=writing, perm_read=True,
            perm_write=name != 'test_orm.related',
            perm_create=name != 'test_orm.related',
            perm_unlink=True)
    other = get_user_model().objects.create_user(
        login='access-other', password=None, name='secret-partner',
        email='other@x.test')
    other.partner.street = 'other street'
    other.partner.save()
    env = MODELS_BY_NAME['test_orm.related'].browse(()).env
    foo = env['test_orm.related_foo'].create({'name': 'foo'})
    secret = env['test_orm.related'].create({'name': 'secret',
                                             'foo_id': foo.id})
    visible = env['test_orm.related'].create({'name': 'visible',
                                              'foo_id': foo.id})
    Child = env['test_orm.related_inherits']
    return {'user': reader.pk, 'writer': writer.pk, 'other': other.pk,
            'foo': foo.id,
            'secret': secret.id,
            'visible': visible.id,
            'secret_child': Child.create({'base_id': secret.id}).id,
            'visible_child': Child.create({'base_id': visible.id}).id}


def _scenarios(env, ids):
    """Los escenarios del espejo, con las etiquetas de la referencia.

    ``res.users`` no tiene ``browse`` aquí; su equivalente es la fila que
    devuelve el manager por id. Y ``sudo`` es de instancia, no de clase: el
    recordset se eleva después de ``browse``, que es la misma operación.
    """
    Related = env['test_orm.related']
    Child = env['test_orm.related_inherits']

    def user():
        return MODELS_BY_NAME['res.users'].objects.get(pk=ids['other'])

    def as_writer(values):
        with user_scope(ids['writer']):
            return _written(current_env()['test_orm.related_inherits']
                            .browse(ids['visible_child']), values)

    def writer_creates(values):
        with user_scope(ids['writer']):
            return _created(current_env()['test_orm.related_inherits'],
                            values)

    def current_user_street():
        # ``env.user`` es elevado (``environments.py:208-213``): su campo
        # heredado no pasa por la regla del partner.
        with user_scope(ids['other']):
            return get_current_user().street

    return [
        ('direct allowed', lambda: Related.browse(ids['visible']).name),
        ('direct forbidden', lambda: Related.browse(ids['secret']).name),
        ('direct forbidden as superuser',
         lambda: Related.browse(ids['secret']).sudo().name),
        ('mixed records', lambda: Related.browse(
            [ids['visible'], ids['secret']]).mapped('name')),
        ('child allowed inherited',
         lambda: Child.browse(ids['visible_child']).name),
        ('child forbidden inherited',
         lambda: Child.browse(ids['secret_child']).name),
        ('child forbidden inherited related',
         lambda: Child.browse(ids['secret_child']).foo_name),
        ('child forbidden own key',
         lambda: bool(Child.browse(ids['secret_child']).base_id)),
        ('child forbidden through key',
         lambda: Child.browse(ids['secret_child']).base_id.name),
        ('child search count', lambda: Child.search_count(
            [('id', 'in', [ids['visible_child'], ids['secret_child']])])),
        ('users redeclared name', lambda: user().name),
        ('users redeclared email', lambda: user().email),
        ('users inherited street', lambda: user().street),
        ('users own login', lambda: user().login),
        ('current user inherited street', current_user_street),
        ('write allowed child inherited', lambda: _written(
            Child.browse(ids['visible_child']), {'name': 'renamed'})),
        ('write forbidden child inherited', lambda: _written(
            Child.browse(ids['secret_child']), {'name': 'renamed'})),
        ('write without parent access inherited',
         lambda: as_writer({'name': 'renamed'})),
        ('write without parent access own key',
         lambda: as_writer({'base_id': ids['visible']})),
        ('create child inherited', lambda: _created(
            Child, {'name': 'born', 'foo_id': ids['foo']})),
        ('create without parent create access',
         lambda: writer_creates({'name': 'born'})),
        ('create with parent key without parent write',
         lambda: writer_creates({'base_id': ids['visible'],
                                 'name': 'born'})),
        ('create with parent key only',
         lambda: writer_creates({'base_id': ids['visible']})),
        ('create with forbidden parent key', lambda: _created(
            Child, {'base_id': ids['secret'], 'name': 'born'})),
    ]


def _created(model, values):
    """Crea, vuelca y lee el nombre heredado, como el espejo de la
    referencia. ``env['…']`` devuelve aquí la clase del modelo, así que el
    entorno se toma del registro creado, que es el mismo."""
    record = model.create(values)
    record.env.flush_all()
    return record.name


def _written(records, values):
    """Escribe y vuelca, como el espejo de la referencia."""
    records.write(values)
    records.env.flush_all()
    return 'ok'


class _Rollback(Exception):
    """Deshace el escenario: cada uno parte del mismo estado."""


def _ours():
    actor = get_user_model().objects.create_user(
        login='access-root', password=None, name='access-root')
    with user_scope(actor.pk), sudo():
        ids = _seed()
    result = {}
    with user_scope(ids['user']):
        env = current_env()
        for label, read in _scenarios(env, ids):
            env.invalidate_all()
            try:
                with transaction.atomic():
                    result[label] = repr(read())
                    raise _Rollback
            except _Rollback:
                # silent OK because la excepción sólo deshace el escenario:
                # el resultado ya quedó registrado antes de levantarla.
                pass
            except AccessError:
                # ``AccessError`` es aquí el alias de ``PermissionDenied``
                # (``src/exceptions.py``): se compara la clase, no el nombre.
                result[label] = 'AccessError'
            except Exception as error:
                # Cualquier otro rechazo se registra por su tipo: la
                # comparación lo distingue del valor y de AccessError.
                result[label] = type(error).__name__
    return result


@pytest.fixture(scope='module')
def reference_result():
    reference_process.require()
    return reference_process.run_script(
        reference_process.FIXTURES / 'reference_access_on_read.py')


def test_the_reads_match_the_reference(reference_result):
    ours = _ours()
    assert list(ours) == list(reference_result)
    differences = {label: (reference_result[label], ours[label])
                   for label in ours
                   if label not in OPEN
                   and ours[label] != reference_result[label]}
    assert differences == {}


def test_the_open_differences_are_still_open(reference_result):
    """Una diferencia declarada abierta que ya coincide se retira de
    ``OPEN``: dejarla ahí ocultaría un cierre."""
    ours = _ours()
    for label, expected in OPEN.items():
        assert reference_result[label] == expected
        assert ours[label] != expected, label


def test_the_reference_forbids_and_bypasses(reference_result):
    """Control del escenario: si la regla no se sembrara, todo sería legible
    y la comparación pasaría vacía de contenido."""
    assert reference_result['direct forbidden'] == 'AccessError'
    assert reference_result['direct allowed'] == "'visible'"
    assert reference_result['users redeclared name'] == "'secret-partner'"
