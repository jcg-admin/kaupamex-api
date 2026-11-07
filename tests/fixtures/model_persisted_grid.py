"""Rejilla de búsqueda con registros persistidos sobre ``test_orm.category``.

Como las otras rejillas de modelo, no importa ni ``odoo`` ni ``orm``. Crea
tres categorías encadenadas por ``parent`` (raíz, hija y nieta) con nombres
propios de la rejilla; el proceso de referencia revierte su cursor al
terminar y la prueba del puerto corre dentro de una transacción, así que
nada queda en ninguna de las dos bases.

``search_fetch`` (``odoo19c: odoo/orm/models.py:1394-1428``) y
``search_read`` (``:6286-6329``) se piden con orden, con ventana y con un
dominio vacío de resultado. Los ids difieren entre las dos bases, así que
cada id se reemplaza por el nombre de su registro antes de comparar.

``_has_cycle`` (``:5624-5682``) se pide sobre la cadena sin ciclo, sobre un
recordset vacío, con un campo que no existe y con uno que no es relación
sobre el propio modelo; después la rejilla cierra el ciclo con un ``UPDATE``
directo —``_has_cycle`` lee la base, no la caché— y vuelve a preguntar. El
alias deprecado ``_check_recursion`` (``:5684-5686``) responde lo contrario.

``try_lock_for_update`` (``:5592-5622``) bloquea filas en la única conexión
de la rejilla, sin competencia: devuelve lo que puede bloquear, en el orden
de ``self``, con ventana, con un registro nuevo, con un id que no existe y
con el bloqueo que admite referencias.

``copy`` (``:5530-5545``), ``copy_data`` (``:5406-5463``) y
``copy_translations`` (``:5465-5528``) se piden con el flujo entero sobre
``test_orm.discussion``: su ``messages`` es un ``One2many`` con
``copy=True``, ``important_messages`` y ``emails`` lo heredan en ``False``,
y ``categories`` es un ``Many2many`` hacia las categorías sembradas. Se copia
una discusión con mensajes y categorías, con y sin ``default`` —un
``default`` que pisa el ``Many2many`` incluido— y dos discusiones a la vez.
De ``copy_data`` se comparan las claves que los dos modelos declaran; los
mensajes, por su ``priority`` y en orden de id, que es el orden que la fuente
garantiza para emparejar traducciones. El ``test_orm.message`` del puerto es
un porte parcial sin ``body``, así que se identifica cada mensaje por un
campo que los dos declaran y que no se calcula.

``with_context`` (``:6021-6055``) tiene que llegar a lo que se llama sobre
el recordset que devuelve: ``search`` y ``search_count`` sobre
``test_orm.model_active_field``, con una fila archivada, sin contexto, con
``active_test=False`` y de vuelta a ``True``. Lo que ``search`` y
``search_fetch`` devuelven queda en ese mismo entorno (``:1383-1418``: el
resultado sale de ``self``), así que una búsqueda encadenada sobre el
resultado también ve la fila archivada; ``search_count`` (``:1347-1359``)
acepta ``limit`` como cota superior.

``name_create`` (``:1493-1510``) crea una categoría por su nombre y se pide
sobre un modelo sin campo ``name`` (``test_orm.empty_int``), que no tiene
``_rec_name`` y devuelve ``False``.

La lectura del ``One2many`` declarado (``odoo19c:
odoo/orm/fields_relational.py:940-967``) se pide sobre la misma discusión:
si devuelve un recordset, sus líneas, las que cumplen el ``domain`` de
``important_messages`` antes y después de marcar una, las del ``domain``
calculado de ``very_important_messages``, y las líneas tras archivar la
última. Con esa línea archivada se copia la discusión: ``copy`` pide
``copy_data`` con ``active_test=False`` y ``convert_to_record`` filtra con el
contexto del registro (``:643-653``), así que la copia lleva también la
línea archivada; ``copy_data`` a secas, no.
"""

import warnings

PREFIX = 'grid-persisted-'
DOMAIN = [('name', '=like', f'{PREFIX}%')]
NOTHING = [('name', '=', f'{PREFIX}none')]
FIELDS = ['name', 'parent']
#: Claves de ``copy_data`` que los dos ``test_orm.discussion`` declaran.
#: ``message_concat`` queda fuera: el puerto declara su ``Text`` sin
#: ``null=True`` y guarda ``''`` donde la fuente guarda NULL, que es la
#: nulabilidad de la columna y no ``copy``.
COPIED = ('name', 'categories', 'messages', 'important_messages', 'emails')
#: Id que ninguna de las dos bases de prueba alcanza.
MISSING_ID = 987654321


def _step(function):
    try:
        return repr(function())
    except Exception as error:
        # La clase de la excepción es el resultado del paso; su mensaje no.
        return f'raises {type(error).__name__}'


def _seed(model):
    root = model.create({'name': f'{PREFIX}a-root'})
    child = model.create({'name': f'{PREFIX}b-child', 'parent': root.id})
    model.create({'name': f'{PREFIX}c-grandchild', 'parent': child.id})
    return {record.id: record.name
            for record in model.search(DOMAIN)}


def _execute(model, query, params):
    """Allá ``env.cr`` es un cursor; aquí es la conexión de Django."""
    cr = model.browse(()).env.cr
    if getattr(cr, 'execute', None) is not None:
        cr.execute(query, params)
        return
    with cr.cursor() as cursor:
        cursor.execute(query, params)


def _close_cycle(model):
    """La raíz pasa a colgar de la nieta: raíz → nieta → hija → raíz."""
    by_name = {record.name: record.id for record in model.search(DOMAIN)}
    _execute(model, f'UPDATE {model._table} SET parent = %s WHERE id = %s',
             [by_name[f'{PREFIX}c-grandchild'], by_name[f'{PREFIX}a-root']])
    return True


def _recursion(records):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        return records._check_recursion()


def _named(names, value):
    if isinstance(value, tuple):
        return (names.get(value[0], value[0]), value[1])
    if type(value) is int:
        return names.get(value, value)
    return value


def _seed_discussions(model):
    """Dos discusiones con mensajes y con las dos primeras categorías."""
    env = model.browse(()).env
    categories = model.search(DOMAIN, order='name')[:2]
    Discussion = env['test_orm.discussion']
    Message = env['test_orm.message']
    found = Discussion.browse(())
    # el autor por defecto de un mensaje es el usuario del entorno, y la
    # fuente exige que participe en la discusión (``_check_author``)
    user = env.user
    participants = list(user.ids) if user else []
    for label in ('d1', 'd2'):
        discussion = Discussion.create({
            'name': f'{PREFIX}{label}', 'categories': [(6, 0, categories.ids)],
            'participants': [(6, 0, participants)],
        })
        for priority in (1, 2):
            Message.create({'discussion': discussion.id,
                            'priority': int(label[1]) * 10 + priority})
        found |= discussion
    return found


def _command(names, command):
    """Un comando x2many con sus ids traducidos y su carga recortada."""
    code, _id, payload = command
    if isinstance(payload, dict):
        payload = sorted((key, value) for key, value in payload.items()
                         if key in ('priority',))
    elif isinstance(payload, (list, tuple)):
        payload = sorted(names.get(item, item) for item in payload)
    return (int(code), payload)


def _copied(names, vals_list):
    rows = []
    for vals in vals_list:
        if vals is None:
            rows.append(None)
            continue
        row = []
        for key in sorted(set(vals) & set(COPIED)):
            value = vals[key]
            if isinstance(value, list):
                value = [_command(names, command) for command in value]
            row.append((key, _named(names, value)))
        rows.append(row)
    return rows


def _active_counts(model, back=False):
    """Cuántos registros de ``test_orm.model_active_field`` ve un método de
    clase llamado sobre ``with_context``: sin contexto, con
    ``active_test=False`` y, con ``back``, de vuelta a ``active_test=True``
    sobre ese mismo recordset."""
    Active = model.browse(()).env['test_orm.model_active_field'].browse(())
    if not Active.search([('name', '=like', f'{PREFIX}%')]):
        Active.create([{'name': f'{PREFIX}on', 'active': True},
                       {'name': f'{PREFIX}off', 'active': False}])
    domain = [('name', '=like', f'{PREFIX}%')]
    unarchived = Active.with_context(active_test=False)
    if back:
        unarchived = unarchived.with_context(active_test=True)
    return (len(Active.search(domain)), len(unarchived.search(domain)),
            unarchived.search_count(domain))


def _returned_env(model):
    """El entorno del recordset que devuelven ``search`` y ``search_fetch``
    llamados sobre ``with_context(active_test=False)``: la clave del contexto
    que conserva, y lo que ve una búsqueda encadenada sobre el resultado, con
    ``search_count`` acotado por ``limit``."""
    Active = model.browse(()).env['test_orm.model_active_field'].browse(())
    _active_counts(model)
    domain = [('name', '=like', f'{PREFIX}%')]
    unarchived = Active.with_context(active_test=False)
    found = unarchived.search(domain)
    fetched = unarchived.search_fetch(domain, ['name'])
    return (found.env.context.get('active_test'),
            fetched.env.context.get('active_test'),
            len(found.search(domain)), found.search_count(domain, limit=1))


def _name_created(model, name):
    """El par que devuelve ``name_create``, con el id como nombre, y si el
    registro quedó escrito."""
    record_id, display_name = model.name_create(name)
    found = model.search([('id', '=', record_id)])
    return (found.name, display_name, found.parent.name if found.parent
            else False)


def _priorities(lines):
    return [line.priority for line in sorted(lines, key=_by_id)]


def _fresh_priorities(discussion, name):
    """Las líneas de ``name`` leídas sin caché. Un ``domain`` calculado no
    declara dependencias, así que la caché de la fuente no se invalida al
    escribir en las líneas; aquí se invalida a mano para medir el
    ``domain`` y no la caché."""
    discussion.invalidate_recordset([name])
    return _priorities(discussion[name])


def _mark_important(discussion):
    """Marca el primer mensaje y vuelve a leer el One2many con ``domain``."""
    first = sorted(discussion.messages, key=_by_id)[0]
    first.write({'important': True})
    return _priorities(discussion.important_messages)


def _archive_last(discussion):
    """Archiva el último mensaje y vuelve a leer ``messages``."""
    last = sorted(discussion.messages, key=_by_id)[-1]
    last.write({'active': False})
    return _priorities(discussion.messages)


def _copied_archived(discussion):
    """Con un mensaje archivado: cuántas líneas trae ``copy_data`` sin
    contexto, y cuántos mensajes —archivados incluidos y sólo activos—
    apuntan a la copia que hace ``copy``, que pide ``active_test=False``."""
    lines = discussion.copy_data()[0]['messages']
    copy = discussion.copy()
    Message = discussion.browse(()).env['test_orm.message'].browse(())
    domain = [('discussion', '=', copy.id)]
    return (len(lines),
            Message.with_context(active_test=False).search_count(domain),
            Message.search_count(domain))


def _by_id(record):
    return record.id


def _discussions(names, records):
    return [(record.name,
             sorted(names.get(category.id, category.id)
                    for category in record.categories),
             # ordenado a mano: el One2many declarado del puerto se lee hoy
             # como un QuerySet, sin ``sorted``
             [message.priority
              for message in sorted(record.messages, key=_by_id)],
             # cuántos mensajes apuntan a la copia, contados por búsqueda: el
             # One2many declarado del puerto aún no aplica su ``domain``
             record.browse(()).env['test_orm.message'].search_count(
                 [('discussion', '=', record.id)]))
            for record in records]


def _names(records):
    return [record.name for record in records]


def _records(records):
    # un Many2one vacío es allá un conjunto vacío y aquí ``None``
    return [(record.name, record.parent.name if record.parent else False)
            for record in records]


def _rows(names, rows):
    return [sorted((key, _named(names, value)) for key, value in row.items())
            for row in rows]


def trace(Domain, model, model_name):
    """Los pasos de la rejilla, cada uno como ``nombre resultado``."""
    del Domain, model_name
    names = _seed(model)
    steps = [
        ('search_fetch ordered', lambda: _records(model.search_fetch(
            DOMAIN, FIELDS, order='name desc'))),
        ('search_fetch window', lambda: _records(model.search_fetch(
            DOMAIN, FIELDS, offset=1, limit=1))),
        ('search_fetch nothing', lambda: _records(model.search_fetch(
            NOTHING, FIELDS))),
        ('search_read ordered', lambda: _rows(names, model.search_read(
            DOMAIN, FIELDS, order='name'))),
        ('search_read no load', lambda: _rows(names, model.search_read(
            DOMAIN, FIELDS, order='name', load=None))),
        ('search_read window', lambda: _rows(names, model.search_read(
            DOMAIN, ['name'], offset=2, limit=5, order='name'))),
        ('search_read nothing', lambda: _rows(names, model.search_read(
            NOTHING, FIELDS))),
    ]
    discussions = _seed_discussions(model)
    steps += [
        ('copy_data discussion', lambda: _copied(
            names, discussions[:1].copy_data())),
        ('copy_data default', lambda: _copied(names, discussions[:1].copy_data(
            {'name': f'{PREFIX}d-default', 'categories': False}))),
        ('copy discussion', lambda: _discussions(
            names, discussions[:1].copy())),
        ('copy default', lambda: _discussions(names, discussions[:1].copy(
            {'name': f'{PREFIX}d-copy'}))),
        ('copy two', lambda: _discussions(names, discussions.copy())),
        ('copy empty', lambda: _discussions(names, discussions[:0].copy())),
        # el último: el comando mueve el mensaje de la segunda discusión
        ('copy one2many default', lambda: _discussions(
            names, discussions[:1].copy({'messages': [(6, 0, [
                sorted(discussions[1:].messages, key=_by_id)[0].id])]}))),
    ]
    steps += [
        ('with_context search', lambda: _active_counts(model)),
        ('with_context search back', lambda: _active_counts(model, True)),
        ('search returns its env', lambda: _returned_env(model)),
    ]
    steps += [
        ('name_create', lambda: _name_created(model, f'{PREFIX}n-created')),
        ('name_create without rec_name', lambda: model.browse(()).env[
            'test_orm.empty_int'].name_create('7')),
    ]
    steps += [
        ('one2many is a recordset', lambda: hasattr(
            discussions[:1].messages, '_ids')),
        ('one2many lines', lambda: _priorities(discussions[:1].messages)),
        ('one2many domain', lambda: _priorities(
            discussions[:1].important_messages)),
        ('one2many domain after', lambda: _mark_important(discussions[:1])),
        ('one2many callable domain', lambda: _fresh_priorities(
            discussions[:1], 'very_important_messages')),
        ('one2many archived', lambda: _archive_last(discussions[:1])),
        ('copy archived lines', lambda: _copied_archived(discussions[:1])),
        ('one2many record env', lambda: (lambda lines: (
            lines.env.context.get('active_test'), _priorities(lines)))(
            discussions[:1].with_context(active_test=False).messages)),
    ]
    chain = model.search(DOMAIN, order='name desc')
    root = model.search([('name', '=', f'{PREFIX}a-root')])
    steps += [
        ('lock chain', lambda: _names(chain.try_lock_for_update())),
        ('lock limit', lambda: _names(chain.try_lock_for_update(limit=2))),
        ('lock referencing', lambda: _names(chain.try_lock_for_update(
            allow_referencing=True))),
        ('lock missing', lambda: _names(model.browse(
            (MISSING_ID,)).try_lock_for_update())),
        ('lock new', lambda: _names(model.new(
            {'name': 'N'}).try_lock_for_update(limit=1))),
        ('lock chain and new', lambda: _names((chain + model.new(
            {'name': 'N'})).try_lock_for_update())),
        ('lock empty', lambda: _names(model.browse(
            ()).try_lock_for_update())),
    ]
    steps += [
        ('has_cycle chain', lambda: chain._has_cycle()),
        ('has_cycle root', lambda: root._has_cycle('parent')),
        ('has_cycle empty', lambda: model.browse(())._has_cycle()),
        ('has_cycle unknown field', lambda: chain._has_cycle('nope')),
        ('has_cycle not a relation', lambda: chain._has_cycle('name')),
        ('check_recursion chain', lambda: _recursion(chain)),
        ('close cycle', lambda: _close_cycle(model)),
        ('has_cycle after', lambda: chain._has_cycle()),
        ('has_cycle root after', lambda: root._has_cycle()),
        ('check_recursion after', lambda: _recursion(chain)),
    ]
    return [f'{name} {_step(function)}' for name, function in steps]
