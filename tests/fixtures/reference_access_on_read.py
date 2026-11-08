"""Lectura por atributo bajo reglas de acceso, en el ORM de ``odoo19c``.

Corre en el entorno aislado de referencia (``reference_process``): no ve
``src/`` ni los settings de Django. Siembra en modo ``su`` un grupo con ACL
sobre los modelos del escenario y dos reglas de fila —una sobre
``test_orm.related`` y otra sobre ``res.partner``—, y lee como un usuario de
ese grupo. Imprime ``{escenario: repr del valor o nombre de la excepción}``.

El espejo de este escenario está en
``tests/unit/orm/test_contract_access_on_read_reference.py``; las dos listas
de escenarios se comparan por etiqueta.
"""
import importlib
import json
import sys

MODELS = ('test_orm.related', 'test_orm.related_inherits',
          'test_orm.related_foo', 'test_orm.related_bar', 'res.users',
          'res.partner')


def seed(env):
    group = env['res.groups'].create({'name': 'access-on-read'})
    user = env['res.users'].create({'name': 'access-reader',
                                    'login': 'access-reader',
                                    'group_ids': [(6, 0, [group.id])]})
    for name in MODELS:
        env['ir.model.access'].create({
            'name': name, 'model_id': env['ir.model']._get(name).id,
            'group_id': group.id, 'perm_read': True, 'perm_write': True,
            'perm_create': True, 'perm_unlink': True})
    for name, domain in (('test_orm.related', "[('name', '!=', 'secret')]"),
                         ('res.partner',
                          "[('name', '!=', 'secret-partner')]")):
        env['ir.rule'].create({
            'name': f'hide {name}', 'model_id': env['ir.model']._get(name).id,
            'domain_force': domain, 'groups': [(6, 0, [group.id])]})
    other = env['res.users'].create({'name': 'secret-partner',
                                     'login': 'access-other',
                                     'email': 'other@x.test',
                                     'street': 'other street'})
    foo = env['test_orm.related_foo'].create({'name': 'foo'})
    secret = env['test_orm.related'].create({'name': 'secret',
                                             'foo_id': foo.id})
    visible = env['test_orm.related'].create({'name': 'visible',
                                              'foo_id': foo.id})
    Child = env['test_orm.related_inherits']
    return {'user': user.id, 'other': other.id, 'secret': secret.id,
            'visible': visible.id,
            'secret_child': Child.create({'base_id': secret.id}).id,
            'visible_child': Child.create({'base_id': visible.id}).id}


def scenarios(env, ids):
    """Los escenarios, en el orden en que se comparan."""
    Related = env['test_orm.related']
    Child = env['test_orm.related_inherits']
    Users = env['res.users']
    return [
        ('direct allowed', lambda: Related.browse(ids['visible']).name),
        ('direct forbidden', lambda: Related.browse(ids['secret']).name),
        ('direct forbidden as superuser',
         lambda: Related.sudo().browse(ids['secret']).name),
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
        ('users redeclared name', lambda: Users.browse(ids['other']).name),
        ('users redeclared email',
         lambda: Users.browse(ids['other']).email),
        ('users inherited street',
         lambda: Users.browse(ids['other']).street),
        ('users own login', lambda: Users.browse(ids['other']).login),
        ('current user inherited street',
         lambda: env(user=ids['other']).user.street),
    ]


def main(root, database, data_dir):
    sys.path.insert(0, root)
    importlib.import_module('odoo.tools').config['data_dir'] = data_dir
    Environment = importlib.import_module('odoo.orm.environments').Environment
    Registry = importlib.import_module('odoo.orm.registry').Registry
    with Registry(database).cursor() as cursor:
        ids = seed(Environment(cursor, 1, {}, su=True))
        env = Environment(cursor, ids['user'], {})
        env.flush_all()
        result = {}
        for label, read in scenarios(env, ids):
            env.invalidate_all()
            try:
                result[label] = repr(read())
            except Exception as error:
                # Cualquier otro rechazo se registra por su tipo: la
                # comparación lo distingue del valor y de AccessError.
                result[label] = type(error).__name__
        cursor.rollback()
    print(json.dumps(result))


if __name__ == '__main__':
    main(*sys.argv[1:4])
