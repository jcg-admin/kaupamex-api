"""``groups`` en el campo al leer y al escribir, en el ORM de ``odoo19c``.

Corre en el entorno aislado de referencia (``reference_process``). Siembra
en modo ``su`` un grupo con ACL sobre ``test_orm.model.some_access`` y dos
usuarios: uno sólo de ese grupo y otro además de
``base.group_erp_manager``. Cada uno lee los campos con ``groups`` por
``browse``, por una fila ya cargada con ``search`` y en modo superusuario.
Imprime ``{escenario: repr del valor o nombre de la excepción}``.

El espejo está en
``tests/unit/orm/test_contract_field_groups_reference.py``.
"""
import importlib
import json
import sys

FIELDS = ('a', 'd', 'e', 'g', 'h', 'i', 'j', 'k')


def seed(env):
    group = env['res.groups'].create({'name': 'field-groups'})
    env['ir.model.access'].create({
        'name': 'some_access',
        'model_id': env['ir.model']._get('test_orm.model.some_access').id,
        'group_id': group.id, 'perm_read': True, 'perm_write': True,
        'perm_create': True, 'perm_unlink': True})
    manager = env.ref('base.group_erp_manager')
    plain = env['res.users'].create({'name': 'groups-plain',
                                     'login': 'groups-plain',
                                     'group_ids': [(6, 0, [group.id])]})
    rich = env['res.users'].create({
        'name': 'groups-manager', 'login': 'groups-manager',
        'group_ids': [(6, 0, [group.id, manager.id])]})
    record = env['test_orm.model.some_access'].create({'a': 7})
    return {'plain': plain.id, 'rich': rich.id, 'record': record.id}


def scenarios(make_env, ids):
    result = []
    for actor in ('plain', 'rich'):
        Model = make_env(ids[actor])['test_orm.model.some_access']
        for name in FIELDS:
            result.append((f'{actor} browse {name}',
                           lambda M=Model, n=name: M.browse(ids['record'])[n]))
            result.append((f'{actor} loaded {name}', lambda M=Model, n=name: (
                M.search([('id', '=', ids['record'])]).read(['a'])
                and M.browse(ids['record'])[n])))
    for actor in ('plain', 'rich'):
        Model = make_env(ids[actor])['test_orm.model.some_access']
        for name in FIELDS:
            result.append((f'{actor} write {name}', lambda M=Model, n=name: (
                M.browse(ids['record']).write({n: 9})
                and M.env.flush_all() or 'ok')))
            result.append((f'{actor} assign {name}', lambda M=Model, n=name: (
                setattr(M.browse(ids['record']), n, 9)
                or M.env.flush_all() or 'ok')))
    Model = make_env(ids['plain'])['test_orm.model.some_access']
    result.append(('superuser browse d',
                   lambda: Model.sudo().browse(ids['record']).d))
    return result


def main(root, database, data_dir):
    sys.path.insert(0, root)
    importlib.import_module('odoo.tools').config['data_dir'] = data_dir
    Environment = importlib.import_module('odoo.orm.environments').Environment
    Registry = importlib.import_module('odoo.orm.registry').Registry
    with Registry(database).cursor() as cursor:
        root_env = Environment(cursor, 1, {}, su=True)
        ids = seed(root_env)
        root_env.flush_all()
        result = {}
        for label, read in scenarios(
                lambda uid: Environment(cursor, uid, {}), ids):
            root_env.invalidate_all()
            savepoint = cursor.savepoint()
            try:
                result[label] = repr(read())
            except Exception as error:
                # Cualquier otro rechazo se registra por su tipo: la
                # comparación lo distingue del valor y de AccessError.
                result[label] = type(error).__name__
            finally:
                # Cada escenario parte del mismo estado: una escritura no
                # se arrastra al siguiente.
                savepoint.rollback()
        cursor.rollback()
    print(json.dumps(result))


if __name__ == '__main__':
    main(*sys.argv[1:4])
