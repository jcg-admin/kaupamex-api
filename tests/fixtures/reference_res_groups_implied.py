"""Grupos implicados y pertenencia efectiva, en el ORM de ``odoo19c``.

Corre en el entorno aislado de referencia (``reference_process``). Siembra
cuatro grupos —A implica B, B implica C, D aislado— y un usuario en A, y
imprime ``{escenario: nombres ordenados o nombre de la excepción}``.

El espejo está en
``tests/unit/orm/test_contract_res_groups_implied_reference.py``.
"""
import importlib
import json
import sys

NAMES = ('impl-A', 'impl-B', 'impl-C', 'impl-D')


def seed(env):
    Groups = env['res.groups']
    c = Groups.create({'name': 'impl-C'})
    b = Groups.create({'name': 'impl-B', 'implied_ids': [(6, 0, [c.id])]})
    a = Groups.create({'name': 'impl-A', 'implied_ids': [(6, 0, [b.id])]})
    d = Groups.create({'name': 'impl-D'})
    user = env['res.users'].create({'name': 'impl-user', 'login': 'impl-user',
                                    'group_ids': [(6, 0, [a.id])]})
    return {'A': a.id, 'B': b.id, 'C': c.id, 'D': d.id, 'user': user.id}


def names(records):
    return sorted(n for n in records.mapped('name') if n in NAMES)


def scenarios(env, ids):
    Groups = env['res.groups']
    Users = env['res.users']

    def cut():
        Groups.browse(ids['B']).write({'implied_ids': [(5, 0, 0)]})
        env.flush_all()
        env.invalidate_all()
        return {'A': names(Groups.browse(ids['A']).all_implied_ids),
                'user': names(Users.browse(ids['user']).all_group_ids)}

    return [
        ('A all_implied',
         lambda: names(Groups.browse(ids['A']).all_implied_ids)),
        ('C all_implied_by',
         lambda: names(Groups.browse(ids['C']).all_implied_by_ids)),
        ('D all_implied',
         lambda: names(Groups.browse(ids['D']).all_implied_ids)),
        ('user all_group_ids',
         lambda: names(Users.browse(ids['user']).all_group_ids)),
        ('search groups implying C', lambda: names(Groups.search(
            [('all_implied_ids', 'in', [ids['C']])]))),
        ('search users in C', lambda: Users.search_count(
            [('id', '=', ids['user']), ('all_group_ids', 'in', [ids['C']])])),
        ('after cutting B-C', cut),
    ]


def main(root, database, data_dir):
    sys.path.insert(0, root)
    importlib.import_module('odoo.tools').config['data_dir'] = data_dir
    Environment = importlib.import_module('odoo.orm.environments').Environment
    Registry = importlib.import_module('odoo.orm.registry').Registry
    with Registry(database).cursor() as cursor:
        env = Environment(cursor, 1, {}, su=True)
        ids = seed(env)
        env.flush_all()
        result = {}
        for label, run in scenarios(env, ids):
            env.invalidate_all()
            savepoint = cursor.savepoint()
            try:
                result[label] = repr(run())
            except Exception as error:
                # Cualquier otro rechazo se registra por su tipo.
                result[label] = type(error).__name__
            finally:
                savepoint.rollback()
        cursor.rollback()
    print(json.dumps(result))


if __name__ == '__main__':
    main(*sys.argv[1:4])
