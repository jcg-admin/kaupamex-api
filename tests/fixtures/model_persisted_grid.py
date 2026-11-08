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

``lock_for_update`` (``:5564-5588``) bloquea todas o lanza ``LockError``: se
pide sobre la cadena, con ``allow_referencing``, vacío, sobre un registro de
``new()`` —sin id que bloquear— y sobre un id que no existe.

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

``search`` (``:1363-1382``, que delega en ``search_fetch``) se pide con
ventana y orden, con el orden del modelo, con un orden inválido —lo rechaza
``_check_qorder``—, con un campo que no existe y con un dominio vacío acotado.

``unlink`` se mide por sus efectos: el ``member_count`` almacenado de
``test_orm.compute.container`` baja al borrar un miembro —la fuente marca lo
dependiente antes de borrar—, una discusión se lleva sus mensajes por
``ondelete='cascade'`` y un recordset vacío devuelve ``True``.

``with_user`` (``:5981-5988``) y ``with_company`` (``:5991-6018``) se miden
por lo que dejan en el entorno: usuario y elevación —el superusuario va
siempre elevado— y el orden de ``allowed_company_ids``, sin datos: las
reglas de acceso por usuario difieren por construcción (DEC-11).

``name_search`` (``odoo19c: odoo/orm/models.py``, sección ``display_name,
name_create, name_search``) se pide con un patrón positivo, vacío con
``limit``, exacto y negativo, siempre acotado a las filas sembradas.
``_search_display_name`` se mide además con ``in``, ``not in`` e ``=`` sobre
``display_name``, y sobre ``test_orm.empty_int``, sin ``_rec_name``, donde el
dominio no restringe nada. Con ``_rec_names_search`` puesto durante la
búsqueda se miden las dos ramas que un ``_rec_name`` de texto no alcanza: un
relacional —el ``Many2many`` ``discussions``— busca por el ``display_name`` del
comodelo, y un ``Integer``
convierte el valor y descarta el que no convierte.

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
línea archivada; ``copy_data`` a secas, no. La guarda de recursión se mide con
el mismo registro dos veces en un recordset: el segundo ``copy_data`` es
``None`` (``:5440-5444``). El filtro de ``convert_to_record`` se mide también
sobre un ``Many2many`` con un enlace archivado.
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
#: Prefijo de la discusión vacía de ``_RelationalMulti.condition_to_sql``.
MULTI_PREFIX = 'grid-multi-'
#: Casos de ``_RelationalMulti.condition_to_sql``: campo, operador, valor.
MULTI_CONDITIONS = (
    ('messages', 'any', '_priority_domain'),
    ('messages', 'not any', '_priority_domain'),
    ('messages', 'any!', '_priority_domain'),
    ('messages', 'in', '_d2_messages'),
    ('messages', 'not in', '_d2_messages'),
    ('messages', 'in', 'false'),
    ('messages', 'not in', 'false'),
    ('categories', 'any', '_seeded_categories'),
    ('categories', 'not any', '_seeded_categories'),
    ('categories', 'in', 'false'),
    ('categories', 'not in', 'false'),
)
#: Prefijo de las categorías que miden ``Many2one.condition_to_sql``.
PARENT_PREFIX = 'grid-parent-'


def _root_domain(D, model, records):
    """El dominio del comodelo que nombra a la raíz, ya optimizado."""
    return D([('name', '=like', f'{PARENT_PREFIX}root')]).optimize_full(model)


def _root_query(D, model, records):
    """La ``Query`` de la raíz."""
    return records.filtered(
        lambda r: r.name == f'{PARENT_PREFIX}root')._as_query(ordered=False)


#: Casos de ``Many2one.condition_to_sql`` sobre ``parent``.
MANY2ONE_CONDITIONS = (
    ('any', _root_domain), ('not any', _root_domain),
    ('any!', _root_domain), ('not any!', _root_domain),
    ('any', _root_query), ('not any', _root_query),
    ('in', lambda D, m, r: [False]), ('any', lambda D, m, r: 7),
)
#: Dominios de ``Domain._to_sql``, construidos con la ``Domain`` de cada árbol.
DOMAINS = (
    ('condition', lambda D, m: D([('color', 'in', [5])])),
    ('not', lambda D, m: D(['!', ('color', 'in', [5])])),
    ('or', lambda D, m: D(['|', ('color', 'in', [5]),
                           ('name', 'like', 'b-ze')])),
    ('and', lambda D, m: D(['&', ('color', 'in', [0, 5]),
                            ('name', 'not like', 'a-nu')])),
    ('true', lambda D, m: D([])),
    ('false', lambda D, m: D.FALSE),
    ('custom', lambda D, m: D.custom(to_sql=_custom_color)),
    ('not custom', lambda D, m: ~D.custom(to_sql=_custom_color)),
)
#: Casos de ``Boolean._condition_to_sql`` sobre ``active``.
BOOLEAN_CONDITIONS = (
    ('in', [True]), ('in', [False]), ('not in', [True]),
    ('not in', [False]), ('in', [True, False]), ('not in', [True, False]),
    ('in', []), ('<', True),
)
#: Campos de ``test_orm.category`` que declaran los dos árboles.
SEQUENCED = ('discussions', 'parent', 'color', 'name', 'parent_path')
#: Prefijo de las categorías que miden ``Field.condition_to_sql``.
CONDITION_PREFIX = 'grid-condition-'
#: Los casos de ``Field.condition_to_sql`` (``odoo19c: odoo/orm/fields.py:
#: 1249-1366``) sobre ``color`` (``Integer`` nulable, valor *falsy* 0) y
#: ``name`` (``Char`` obligatorio): igualdad con y sin ``False``, los cuatro
#: ``like`` y sus negaciones, las desigualdades que aceptan la fila nula, el
#: subselect de ``any!``, un ``in`` sin colección y un operador inválido.
CONDITIONS = (
    ('color', 'in', [5]), ('color', 'in', [0]), ('color', 'in', [False]),
    ('color', 'in', [5, False]), ('color', 'in', []),
    ('color', 'not in', [5]), ('color', 'not in', [0]),
    ('color', 'not in', [False]), ('color', 'not in', [5, False]),
    ('color', '<', 3), ('color', '<=', 0), ('color', '>', -1),
    ('color', '>=', 1), ('color', '<', False), ('color', '>', 3),
    ('name', 'like', 'b-ze'), ('name', 'ilike', 'B-ZE'),
    ('name', 'not like', 'b-ze'), ('name', 'not ilike', 'B-ZE'),
    ('name', '=like', 'grid-condition-c%'),
    ('name', '=ilike', 'GRID-CONDITION-A%'),
    ('name', 'not =like', 'grid-condition-c%'),
    ('name', 'in', [False]), ('name', 'not in', [False]),
    ('name', 'in', 'b-zero'), ('color', '~', 5),
    ('id', 'any!', lambda records: records[:1]._as_query(ordered=False)),
    ('id', 'not any!', lambda records: records[:1]._as_query(ordered=False)),
)
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
    participants = [user.id] if user else []
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


def _relatives_read(model):
    """Un ``Many2many`` con un enlace archivado, leído sin contexto y con
    ``active_test=False``: el filtro de ``convert_to_record`` sobre la otra
    familia de x2many (``:643-653``)."""
    Active = model.browse(()).env['test_orm.model_active_field'].browse(())
    on, off = Active.create([{'name': f'{PREFIX}rel-on'},
                             {'name': f'{PREFIX}rel-off', 'active': False}])
    owner = Active.create([{'name': f'{PREFIX}rel-owner',
                            'relatives_ids': [(6, 0, [on.id, off.id])]}])
    unarchived = owner.with_context(active_test=False).relatives_ids
    return (sorted(r.name for r in owner.relatives_ids),
            sorted(r.name for r in unarchived),
            unarchived.env.context.get('active_test'))


def _with_user(model):
    """``with_user`` (``:5981-5988``): el usuario y la elevación del entorno
    derivado, para un usuario cualquiera, para el superusuario —que por
    convención va siempre elevado— y para un usuario vacío, que devuelve el
    mismo recordset."""
    records = model.browse(())
    other = records.with_user(2)
    root = records.with_user(1)
    return ((other.env.uid, other.env.su), (root.env.uid, root.env.su),
            records.with_user(False) is records)


def _with_company(model):
    """``with_company`` (``:5991-6018``): el orden de ``allowed_company_ids``
    tras pedir una empresa nueva, una ya permitida y la que ya va primera, y
    que una empresa vacía o la primera devuelven el mismo recordset."""
    records = model.browse(()).with_context(allowed_company_ids=[3, 4])
    return (list(records.with_company(5).env.context['allowed_company_ids']),
            list(records.with_company(4).env.context['allowed_company_ids']),
            records.with_company(3) is records,
            records.with_company(False) is records,
            list(model.browse(()).with_company(7).env.context[
                'allowed_company_ids']))


def _name_searched(model, *args, **kwargs):
    """Los nombres que devuelve ``name_search``, con el id comprobado contra
    el registro: los ids difieren entre bases, el par no."""
    pairs = model.browse(()).name_search(*args, **kwargs)
    return [(model.browse(id_).display_name == name, name)
            for id_, name in pairs]


def _rec_names_searched(model, fname, operator, value):
    """``_search_display_name`` con ``_rec_names_search = [fname]`` puesto en
    la clase sólo durante la búsqueda: un ``Many2one`` busca por el
    ``display_name`` del comodelo, y un campo no textual convierte el valor a
    su tipo y descarta el que no convierte."""
    cls = type(model.browse(()))
    missing = object()
    previous = cls.__dict__.get('_rec_names_search', missing)
    cls._rec_names_search = [fname]
    try:
        return _names(model.search(
            DOMAIN + [('display_name', operator, value)]))
    finally:
        if previous is missing:
            del cls._rec_names_search
        else:
            cls._rec_names_search = previous


def _integer_conversions(model):
    """La cadena de conversiones de ``Integer`` (``odoo19c:
    odoo/orm/fields_numeric.py:17-57``) sobre ``test_orm.category.color``:
    columna, caché —con el dict de inverso y un valor que no convierte—,
    registro, lectura —por encima de ``MAXINT`` pasa a float—, escritura y
    exportación; y el resultado observable de escribir un texto y leerlo."""
    field = model._fields['color']
    record = model.browse(())
    values = []
    for convert, args in (
            (field.convert_to_column, (False,)),
            (field.convert_to_column, ('5',)),
            (field.convert_to_cache, ('7',)),
            (field.convert_to_cache, (None,)),
            (field.convert_to_cache, ({'id': 4},)),
            (field.convert_to_cache, ('x',)),
            (field.convert_to_record, (None,)),
            (field.convert_to_read, (2 ** 31,)),
            (field.convert_to_read, (12,)),
            (field.convert_to_write, ('3',)),
            (field.convert_to_export, (0,)),
            (field.convert_to_export, (None,))):
        try:
            values.append(repr(convert(*args, record)))
        except (ValueError, TypeError) as error:
            values.append(type(error).__name__)
    written = model.search(DOMAIN, order='name', limit=1)
    written.write({'color': '9'})
    written.invalidate_recordset(['color'])
    values.append(repr(written.color))
    written.write({'color': False})
    written.invalidate_recordset(['color'])
    values.append(repr(written.color))
    return values


def _unlinked_member(model):
    """``unlink`` (``odoo19c: odoo/orm/models.py``, ``BaseModel.unlink``)
    marca para recalcular lo que depende de las filas antes de borrarlas
    (``self.modified(self._fields, before=True)``): el ``member_count``
    almacenado del contenedor baja al borrar un miembro. Devuelve el valor
    antes y después, y lo que ``unlink`` devuelve."""
    env = model.browse(()).env
    name = f'{PREFIX}container'
    Container = env['test_orm.compute.container'].browse(())
    Member = env['test_orm.compute.member'].browse(())
    container = Container.create({'name': name})
    members = Member.create([{'name': name}, {'name': name}])
    before = container.member_count
    result = members[:1].unlink()
    return before, container.member_count, result


def _unlinked_discussion(model):
    """Borrar una discusión borra sus mensajes por ``ondelete='cascade'``;
    un recordset vacío devuelve ``True`` sin tocar nada."""
    env = model.browse(()).env
    Discussion = env['test_orm.discussion'].browse(())
    Message = env['test_orm.message'].browse(())
    # el autor del mensaje tiene que participar (``_check_author`` de la
    # fuente), como en ``_seed_discussions``
    participants = [env.user.id] if env.user else []
    discussion = Discussion.create({
        'name': f'{PREFIX}to-unlink', 'participants': [(6, 0, participants)]})
    Message.create([{'discussion': discussion.id, 'priority': 1}])
    domain = [('discussion', '=', discussion.id)]
    before = Message.search_count(domain)
    result = discussion.unlink()
    return (before, Message.search_count(domain), result,
            Discussion.unlink(), discussion.exists().ids)


def _external_ids(model, chain):
    """``_get_external_ids`` y ``get_external_id`` (``odoo19c:
    odoo/orm/models.py:5695-5735``) sobre la cadena: la raíz con
    dos ids externos, en orden de creación, el hijo con uno y el nieto sin
    ninguno. Las claves se traducen al nombre del registro."""
    Data = model.browse(()).env['ir.model.data']
    by_name = {record.name: record for record in chain}
    root, child = by_name[f'{PREFIX}a-root'], by_name[f'{PREFIX}b-child']
    rows = [('root_one', root.id), ('root_two', root.id), ('child', child.id)]
    if hasattr(Data, 'search'):
        # la referencia: ``ir.model.data`` es un modelo de su ORM, y la
        # columna ``model`` lleva el nombre con puntos
        if not Data.search([('module', '=', 'grid')]):
            Data.create([{'module': 'grid', 'name': name,
                          'model': model._name, 'res_id': res_id}
                         for name, res_id in rows])
    elif not Data.objects.filter(module='grid').exists():
        # el puerto: un modelo de Django, y la columna ``model`` lleva la
        # etiqueta de Django, que es lo que escribe su único escritor
        Data.objects.bulk_create([
            Data(module='grid', name=name, model=model._meta.label,
                 res_id=res_id) for name, res_id in rows])
    names = {record.id: record.name for record in chain}
    return (sorted((names[key], value)
                   for key, value in chain._get_external_ids().items()),
            sorted((names[key], value)
                   for key, value in chain.get_external_id().items()))


def _assigned_inverse(model):
    """``self[name] = value`` sobre un registro guardado pasa por
    ``write`` (``odoo19c: odoo/orm/fields.py:1837-1841``), y ``write``
    despacha el inverso de un campo calculado (``models.py``,
    ``BaseModel.write``). ``display_name`` de la categoría es calculado con
    inverso (``_inverse_display_name``): el valor ``'padre / nombre'``
    reasigna el padre y el nombre. Se lee de vuelta con ``search_read``."""
    record = model.browse(()).create({'name': f'{PREFIX}to-inverse'})
    record['display_name'] = f'{PREFIX}a-root / {PREFIX}inversed'
    stored = model.browse(()).search_read([('id', '=', record.id)],
                                          ['name', 'parent'])
    return [(row['name'], row['parent'] and row['parent'][1])
            for row in stored]


def _has_onchanges(model):
    """``_has_onchange`` (``odoo19c: odoo/orm/models.py``,
    ``BaseModel._has_onchange``): un campo dispara onchange si tiene un
    método ``@api.onchange`` o si alguno de ``other_fields`` depende de él.
    Lo consume la vista (``ir_ui_view.py:1597``) para marcar los campos.
    Sobre la discusión, con métodos ``@api.onchange`` en ``name`` y
    ``moderator``; sobre la categoría, cuyo ``display_name`` depende de
    ``name`` y no de ``color``."""
    env = model.browse(()).env
    discussions = env['test_orm.discussion'].browse(())
    categories = model.browse(())
    dfields, cfields = discussions._fields, categories._fields
    display = [cfields['display_name']]
    return [discussions._has_onchange(dfields['name'], []),
            discussions._has_onchange(dfields['moderator'], []),
            discussions._has_onchange(dfields['history'], []),
            categories._has_onchange(cfields['name'], display),
            categories._has_onchange(cfields['color'], display),
            categories._has_onchange(cfields['name'], [])]


def _recomputed_constraint(model):
    """``_compute_field_value`` (``odoo19c: odoo/orm/models.py``,
    ``BaseModel._compute_field_value``) valida las restricciones de un campo
    calculado almacenado después de calcularlo. Escenario de
    ``test_15_constraint`` (``odoo/addons/test_orm/tests/test_fields.py:
    798-820``): el ``name`` de un mensaje es ``'[<discusión>] <autor>'``;
    renombrar la discusión a ``'X'`` lo recalcula a ``'[X] …'`` y
    ``_check_name`` lo rechaza. Se devuelve la excepción y el nombre que el
    mensaje conserva."""
    env = model.browse(()).env
    user = env.user
    discussion = env['test_orm.discussion'].browse(()).create({
        'name': f'{PREFIX}to-constrain',
        'participants': [(6, 0, [user.id] if user else [])]})
    message = env['test_orm.message'].browse(()).create(
        {'discussion': discussion.id, 'priority': 7})
    before = message.name.split(']')[0]
    try:
        discussion['name'] = 'X'
        discussion.flush_model()
        message.flush_model()
        raised = None
    except Exception as error:
        # la traza compara la clase de la excepción, no la silencia
        raised = type(error).__name__
    # el recálculo rechazado sigue pendiente en el entorno; con el nombre
    # válido de vuelta se resuelve y el volcado siguiente no lo arrastra
    discussion['name'] = f'{PREFIX}to-constrain'
    discussion.flush_model()
    message.flush_model()
    return before, raised, message.name.split(']')[0]


def _exported(discussions):
    """``export_data`` (``odoo19c: odoo/orm/models.py:880-892``) sobre las
    discusiones sembradas: el ``One2many`` abre una fila por mensaje y el
    ``Many2many``, en modo compatible con la importación —el defecto—, va en
    una sola celda con los nombres separados por coma (``:820-844``)."""
    return discussions.export_data(
        ['name', 'messages/priority', 'categories/name'])['datas']


def _relational_multi(discussions):
    """Un relacional leído sobre varios registros es la unión de sus valores,
    sin repetidos (``odoo19c: odoo/orm/fields_relational.py:42-79`` y
    ``convert_to_record_multi``, ``:360-364``, ``:655-667``): las dos
    discusiones comparten sus categorías, que salen una sola vez."""
    return (sorted(discussions['messages'].mapped('priority')),
            sorted(discussions['categories'].mapped('name')))


def _exported_xids(discussions):
    """La columna ``id`` (``:858-874``): cada registro sin identificador
    externo recibe uno ``__export__.<tabla>_<id>_<uuid>`` (``:599-677``), y
    la segunda exportación devuelve el mismo. El uuid y el id difieren entre
    las dos bases; se mide la forma, la estabilidad y ``.id``."""
    first = discussions.export_data(['name', 'id', '.id'])['datas']
    again = discussions.export_data(['id'])['datas']
    return [(name, xid.startswith('__export__.test_orm_discussion_'),
             xid == row[0], dot_id == str(record.id))
            for (name, xid, dot_id), row, record
            in zip(first, again, discussions)]


def _field_strings(model):
    """La etiqueta de cada campo (``odoo19c: odoo/orm/fields.py:506-511``):
    la declarada si la hay; si no, el nombre sin el sufijo ``_id``/``_ids``,
    con espacios y en mayúscula inicial. ``name`` y ``parent_path`` no
    declaran etiqueta, ``color`` sí (``'Color Index'``), y ``country_id`` de
    ``test_orm.city`` pierde su sufijo."""
    city = model.browse(()).env['test_orm.city'].browse(())
    return ([(name, model._fields[name].string)
             for name in ('name', 'color', 'parent_path')]
            + [('country_id', city._fields['country_id'].string)])


def _empty_many2one(model):
    """Un ``Many2one`` sin valor se lee como el recordset vacío de su
    comodelo (``odoo19c: odoo/orm/fields_relational.py:354-358``,
    ``Many2one.convert_to_record``), no como ``None``: se puede preguntar su
    longitud, su modelo y sus campos, que valen ``False``. La raíz de la
    cadena no tiene padre."""
    root = model.browse(()).search([('name', '=', f'{PREFIX}a-root')])
    parent = root.parent
    return (bool(parent), len(parent), parent._name, parent.name,
            parent.ids, root.parent.parent.ids)


def _rec_name_fallbacks(model):
    """``_rec_name_fallback`` (``odoo19c: odoo/orm/models.py:1341-1343``):
    ``_rec_name`` si el modelo lo tiene, ``'id'`` si no. Lo consumen las
    vistas por defecto (``ir_ui_view.py:2816-2883``) y la exportación
    (``web/controllers/export.py:379``). Se pide sobre modelos con ``name``
    resuelto y sin campo ``name``. La rama del ``_rec_name`` declarado
    distinto de ``name`` queda sin medir: ningún modelo del puerto que derive
    de ``BaseModel`` lo declara, y ``res.groups`` —que sí lo hace— no deriva
    de ella (H-API-1083)."""
    env = model.browse(()).env
    return [(name, env[name]._rec_name_fallback())
            for name in ('test_orm.category', 'test_orm.empty_int',
                         'test_orm.model_active_field', 'test_orm.mixed')]


def _parent_paths_recomputed(model, chain):
    """``_parent_store_compute`` (``odoo19c: odoo/orm/models.py:3071-3105``)
    reconstruye ``parent_path`` desde cero con un ``WITH RECURSIVE`` sobre
    la columna del padre. Se corrompe la ruta de la cadena con un ``UPDATE``
    directo —la base, no la caché—, se recalcula y se lee de vuelta con
    ``search_read``; cada id de la ruta se traduce al nombre de su registro."""
    ids = [record.id for record in chain]
    _execute(model, f"UPDATE {model._table} SET parent_path = 'x/' "
             'WHERE id = ANY(%s)', [ids])
    # la ruta corrupta entra en la caché: sin la invalidación de la fuente,
    # la lectura posterior la devolvería
    chain.invalidate_model(['parent_path'])
    cached = [record.parent_path for record in model.browse(ids)]
    model.browse(())._parent_store_compute()
    names = {record.id: record.name for record in chain}

    def _path(value):
        return [names.get(int(part), part)
                for part in value.split('/') if part]

    return (sorted(set(cached)),
            sorted((record.name, _path(record.parent_path))
                   for record in model.browse(ids)))


def _ordered_by_parent(model):
    """Un ``Many2one`` se ordena por el ``_order`` de su comodelo —``name``
    en la categoría—, no por el id del padre. Los padres se crean en orden
    inverso al alfabético, así que los dos órdenes difieren; con
    ``parent.id`` el orden sí es el del id. Los nombres quedan fuera de
    ``DOMAIN`` para no alterar los demás pasos."""
    categories = model.browse(())
    found = categories.search([('name', '=like', 'order-probe-%')])
    if not found:
        late = categories.create({'name': 'order-probe-z-parent'})
        early = categories.create({'name': 'order-probe-m-parent'})
        categories.create({'name': 'order-probe-k1', 'parent': late.id})
        categories.create({'name': 'order-probe-k2', 'parent': early.id})
    domain = [('name', '=like', 'order-probe-k%')]
    return (_names(categories.search(domain, order='parent')),
            _names(categories.search(domain, order='parent.id')))


def _metadata(chain):
    """``get_metadata`` (``odoo19c: odoo/orm/models.py``,
    ``BaseModel.get_metadata``) sobre la cadena, después del paso de ids
    externos: la raíz con dos, el hijo con uno y el nieto sin ninguno. Se
    compara la parte de ``ir.model.data`` —``xmlid``, ``noupdate`` y
    ``xmlids``, en el orden que la fuente fija—. Las columnas de
    ``_log_access`` quedan fuera: el puerto declara otras
    (``LOG_ACCESS_COLUMNS``, ``orm/model_classes.py``), divergencia ya
    registrada."""
    names = {record.id: record.name for record in chain}
    return sorted((names[row['id']], row['xmlid'], row['noupdate'],
                   [item['xmlid'] for item in row['xmlids']],
                   [item['noupdate'] for item in row['xmlids']])
                  for row in chain.get_metadata())


def _updated(model):
    """``update`` (``odoo19c: odoo/orm/models.py``, ``BaseModel.update``)
    asigna cada valor con ``self[name] = value``: sobre un registro guardado
    la asignación escribe en la base, y sobre uno de ``new()`` sólo en su
    caché. Se lee de vuelta con ``search_read``, que va a la base."""
    record = model.browse(()).create({'name': f'{PREFIX}to-update'})
    record.update({'name': f'{PREFIX}updated', 'color': 4})
    record['color'] = 6
    stored = model.browse(()).search_read([('id', '=', record.id)],
                                          ['name', 'color'])
    draft = model.new({'name': 'N'})
    draft.update({'name': 'M'})
    return ([(row['name'], row['color']) for row in stored], draft.name,
            model.browse(()).search_count([('name', '=', 'M')]))


def _multi_records(discussions):
    """Las dos discusiones sembradas y una sin mensajes ni categorías."""
    Discussion = discussions.browse(())
    user = Discussion.env.user
    empty = Discussion.create({
        'name': f'{MULTI_PREFIX}empty',
        'participants': [(6, 0, [user.id] if user else [])],
    })
    return discussions | empty


def _multi_selected(Domain, records, fname, operator, build):
    """Las filas que ``_RelationalMulti.condition_to_sql`` selecciona.

    ``odoo19c: odoo/orm/fields_relational.py:779-837`` y los
    ``_condition_to_sql_relational`` de ``One2many`` (``:1154-1200``) y
    ``Many2many`` (``:1705-1730``): ``in``/``not in`` con ids o con
    ``False``, y ``any``/``not any``/``any!`` con un dominio del comodelo.
    """
    model = records.browse(())
    query = records._as_query(ordered=False)
    value = build(Domain, model, records)
    sql = model._fields[fname].condition_to_sql(
        fname, operator, value, model, query.table, query)
    query.add_where(sql)
    rows = model.env.execute_query(
        query.select(model._field_to_sql(query.table, 'name', query)))
    return sorted(name.removeprefix(MULTI_PREFIX).removeprefix(PREFIX)
                  for name, in rows)


def _priority_domain(D, model, records):
    """Los mensajes de prioridad 11 —los de ``d1``—, optimizado."""
    Message = model.env['test_orm.message'].browse(())
    return D([('priority', '=', 11)]).optimize_full(Message)


def _d2_messages(D, model, records):
    """Los ids de los mensajes de ``d2``."""
    d2 = records.filtered(lambda r: r.name == f'{PREFIX}d2')
    return list(d2.messages.ids)


def _seeded_categories(D, model, records):
    """Las categorías sembradas por la rejilla, optimizado."""
    Category = model.env['test_orm.category'].browse(())
    return D([('name', '=like', f'{PREFIX}a%')]).optimize_full(Category)


def _parent_records(model):
    """Una raíz, su hija y un huérfano, para ``Many2one.condition_to_sql``."""
    root = model.create({'name': f'{PARENT_PREFIX}root'})
    child = model.create({'name': f'{PARENT_PREFIX}child', 'parent': root.id})
    orphan = model.create({'name': f'{PARENT_PREFIX}orphan'})
    return root | child | orphan


def _many2one_selected(Domain, records, operator, build):
    """Las filas que ``Many2one.condition_to_sql`` selecciona sobre ``parent``.

    ``odoo19c: odoo/orm/fields_relational.py:480-537``: ``any``/``not any``
    con un dominio del comodelo, con ``any!`` —que salta el acceso y puede
    ir por ``LEFT JOIN``— y con una ``Query``; el resto va al cuerpo de
    ``Field``. El valor ``Domain`` llega optimizado sobre el comodelo, como
    exige la rama del ``LEFT JOIN``.
    """
    model = records.browse(())
    query = records._as_query(ordered=False)
    value = build(Domain, model, records)
    sql = model._fields['parent'].condition_to_sql(
        'parent', operator, value, model, query.table, query)
    query.add_where(sql)
    rows = model.env.execute_query(
        query.select(model._field_to_sql(query.table, 'name', query)))
    return sorted(name.removeprefix(PARENT_PREFIX) for name, in rows)


def _domain_selected(Domain, records, build, optimize=True):
    """Las filas de ``records`` que ``Domain._to_sql`` selecciona.

    ``odoo19c: odoo/orm/domains.py:470-1097``: cada clase de dominio compone
    su ``SQL`` —``TRUE``/``FALSE``, ``(...) IS NOT TRUE``, ``AND``/``OR``, el
    invocable de ``Domain.custom``— y la condición delega en
    ``Field.condition_to_sql``. La fuente exige el dominio optimizado.
    """
    model = records.browse(())
    query = records._as_query(ordered=False)
    domain = build(Domain, model)
    if optimize:
        domain = domain.optimize_full(model)
    query.add_where(domain._to_sql(model, query.table, query))
    rows = model.env.execute_query(
        query.select(model._field_to_sql(query.table, 'name', query)))
    return sorted(name.removeprefix(CONDITION_PREFIX) for name, in rows)


def _custom_color(model, alias, query):
    """El ``to_sql`` de un ``Domain.custom``: ``color > 3``."""
    return model._fields['color'].condition_to_sql(
        'color', '>', 3, model, alias, query)


def _boolean_condition(model, operator, value):
    """``Boolean._condition_to_sql`` sobre ``active``: código, parámetros y
    filas.

    El sobreescrito (``odoo19c: odoo/orm/fields_misc.py:35-49``) cambia la
    **forma** del ``SQL`` —``IS TRUE`` / ``IS NOT TRUE``— y no el conjunto de
    filas que daría el cuerpo de ``Field``; por eso se compara también el
    código emitido, que es lo único que lo distingue.
    """
    Active = model.browse(()).env['test_orm.model_active_field'].browse(())
    Active = Active.with_context(active_test=False)
    records = Active.search([('name', '=like', f'{PREFIX}%')])
    if not records:
        records = Active.create([{'name': f'{PREFIX}on', 'active': True},
                                 {'name': f'{PREFIX}off', 'active': False}])
    query = records._as_query(ordered=False)
    sql = Active._fields['active'].condition_to_sql(
        'active', operator, value, Active, query.table, query)
    query.add_where(sql)
    rows = Active.env.execute_query(
        query.select(Active._field_to_sql(query.table, 'name', query)))
    return (sql.code, list(sql.params),
            sorted(name.removeprefix(PREFIX) for name, in rows))


def _sequence_order(model):
    """Los campos declarados de la categoría, ordenados por ``_sequence``.

    ``Field._sequence`` (``odoo19c: odoo/orm/fields.py:265,316``) es el orden
    absoluto de declaración; ``_create`` lo usa para escribir los campos sin
    columna en ese orden (``models.py:4938``). Se comparan el orden y que el
    valor sea un entero distinto por campo.
    """
    fields = [model._fields[name] for name in SEQUENCED
              if name in model._fields]
    values = [field._sequence for field in fields]
    ordered = sorted(fields, key=lambda field: field._sequence)
    return ([field.name for field in ordered],
            all(type(value) is int for value in values),
            len(set(values)) == len(values))


def _condition_records(model):
    """Tres categorías con ``color`` nulo, cero y cinco, en orden de nombre.

    El color se fija con ``UPDATE``: ``Integer`` convierte ``False`` en 0 al
    escribir, así que el ORM no deja una columna nula en ninguno de los dos.
    """
    records = model.create([{'name': f'{CONDITION_PREFIX}{tag}'}
                            for tag in ('a-null', 'b-zero', 'c-five')])
    for record, color in zip(records, (None, 0, 5)):
        _execute(model, f'UPDATE {model._table} SET color = %s WHERE id = %s',
                 (color, record.id))
    return records


def _condition_selected(records, fname, operator, value):
    """Las filas de ``records`` que ``Field.condition_to_sql`` selecciona.

    La condición se añade a la consulta de los propios registros, así que el
    resultado sólo puede nombrar categorías de la rejilla.
    """
    model = records.browse(())
    query = records._as_query(ordered=False)
    if callable(value):
        value = value(records)
    sql = model._fields[fname].condition_to_sql(
        fname, operator, value, model, query.table, query)
    query.add_where(sql)
    rows = model.env.execute_query(
        query.select(model._field_to_sql(query.table, 'name', query)))
    return sorted(name.removeprefix(CONDITION_PREFIX) for name, in rows)


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
    del model_name
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
        ('with_user', lambda: _with_user(model)),
        ('with_company', lambda: _with_company(model)),
        ('integer conversions', lambda: _integer_conversions(model)),
        ('update', lambda: _updated(model)),
        ('rec_name fallback', lambda: _rec_name_fallbacks(model)),
        ('empty many2one', lambda: _empty_many2one(model)),
        ('field strings', lambda: _field_strings(model)),
        ('export_data', lambda: _exported(discussions)),
        ('export_data xid', lambda: _exported_xids(discussions)),
        ('relational multi', lambda: _relational_multi(discussions)),
    ]
    steps += [('field sequence order', lambda: _sequence_order(model))]
    steps += [
        (f'domain _to_sql {name}',
         lambda build=build: _domain_selected(Domain, conditioned, build))
        for name, build in DOMAINS
    ]
    steps += [('domain _to_sql unoptimized', lambda: _domain_selected(
        Domain, conditioned, DOMAINS[0][1], optimize=False))]
    steps += [
        (f'boolean condition_to_sql {operator} {value!r}',
         lambda case=(operator, value): _boolean_condition(model, *case))
        for operator, value in BOOLEAN_CONDITIONS
    ]
    multi = _multi_records(discussions)
    builders = {'false': lambda D, m, r: [False],
                '_priority_domain': _priority_domain,
                '_d2_messages': _d2_messages,
                '_seeded_categories': _seeded_categories}
    steps += [
        (f'multi condition_to_sql {fname} {operator} {value}',
         lambda case=(fname, operator, builders[value]): _multi_selected(
             Domain, multi, *case))
        for fname, operator, value in MULTI_CONDITIONS
    ]
    parented = _parent_records(model)
    steps += [
        (f'many2one condition_to_sql {operator} {build.__name__}',
         lambda case=(operator, build): _many2one_selected(
             Domain, parented, *case))
        for operator, build in MANY2ONE_CONDITIONS
    ]
    conditioned = _condition_records(model)
    steps += [
        (f'condition_to_sql {fname} {operator} '
         f'{"<query>" if callable(value) else repr(value)}',
         lambda case=(fname, operator, value): _condition_selected(
             conditioned, *case))
        for fname, operator, value in CONDITIONS
    ]
    steps += [
        ('recomputed constraint', lambda: _recomputed_constraint(model)),
        ('has onchange', lambda: _has_onchanges(model)),
        ('assigned inverse', lambda: _assigned_inverse(model)),
        ('search window', lambda: _names(model.search(
            DOMAIN, offset=1, limit=1, order='name desc'))),
        ('search default order', lambda: _names(model.search(DOMAIN))),
        ('search invalid order', lambda: _names(model.search(
            DOMAIN, order='name; drop'))),
        ('search unknown field', lambda: _names(model.search(
            [('no_such_field', '=', 1)]))),
        ('search empty domain limit', lambda: len(model.search([], limit=2))),
        # ``_order_to_sql``/``_order_field_to_sql`` (``:5224-5322``): un
        # ``Many2one`` se ordena por el ``_order`` de su comodelo, el sentido
        # se invierte con ``desc`` y ``nulls first`` adelanta las raíces
        ('search order many2one', lambda: _names(model.search(
            DOMAIN, order='parent, name'))),
        ('search order many2one desc', lambda: _names(model.search(
            DOMAIN, order='parent desc, name'))),
        ('search order many2one nulls first', lambda: _names(model.search(
            DOMAIN, order='parent nulls first, name'))),
        ('search order many2one id', lambda: _names(model.search(
            DOMAIN, order='parent.id desc, name'))),
        ('search order by comodel order', lambda: _ordered_by_parent(
            model)),
        ('unlink member', lambda: _unlinked_member(model)),
        ('unlink discussion', lambda: _unlinked_discussion(model)),
        ('name_search', lambda: _name_searched(model, 'child', DOMAIN)),
        ('name_search empty', lambda: _name_searched(
            model, '', DOMAIN, limit=2)),
        ('name_search exact', lambda: _name_searched(
            model, f'{PREFIX}a-root', DOMAIN, operator='=')),
        ('name_search negative', lambda: _name_searched(
            model, 'root', DOMAIN, operator='not ilike')),
        ('name_search domain', lambda: _name_searched(
            model, '', [('name', '=', f'{PREFIX}c-grandchild')])),
        ('display_name in', lambda: _names(model.search(DOMAIN + [(
            'display_name', 'in', [f'{PREFIX}a-root', f'{PREFIX}b-child'])]))),
        ('display_name not in', lambda: _names(model.search(DOMAIN + [(
            'display_name', 'not in', [f'{PREFIX}a-root'])]))),
        ('display_name equal', lambda: _names(model.search(DOMAIN + [(
            'display_name', '=', f'{PREFIX}c-grandchild')]))),
        # sobre ``parent`` la búsqueda vuelve a la misma regla y las dos
        # bases levantan RecursionError: se mide sobre otro comodelo
        ('rec_names_search relational', lambda: _rec_names_searched(
            model, 'discussions', 'ilike', 'd1')),
        ('rec_names_search typed', lambda: _rec_names_searched(
            model, 'color', 'in', ['0', '7'])),
        ('rec_names_search unconvertible', lambda: _rec_names_searched(
            model, 'color', '=', 'abc')),
        ('rec_names_search converted', lambda: _rec_names_searched(
            model, 'color', '=', '')),
        ('display_name without rec_name', lambda: (lambda Empty: len(
            Empty.search([('display_name', 'ilike', 'zzz')])) == len(
            Empty.search([])))(model.browse(()).env['test_orm.empty_int'])),
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
        ('copy_data seen twice', lambda: [
            values is None
            for values in (discussions[:1] + discussions[:1]).copy_data()]),
        ('many2many archived', lambda: _relatives_read(model)),
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
        ('external ids', lambda: _external_ids(model, chain)),
        ('parent store compute', lambda: _parent_paths_recomputed(
            model, chain)),
        ('metadata', lambda: _metadata(chain)),
        ('metadata empty', lambda: model.browse(()).get_metadata()),
        ('lock_for_update chain', lambda: chain.lock_for_update()),
        ('lock_for_update referencing', lambda: chain.lock_for_update(
            allow_referencing=True)),
        ('lock_for_update empty', lambda: model.browse(()).lock_for_update()),
        ('lock_for_update new', lambda: model.new(
            {'name': 'N'}).lock_for_update()),
        ('lock_for_update missing', lambda: model.browse(
            (MISSING_ID,)).lock_for_update()),
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
