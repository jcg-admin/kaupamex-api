"""
Los modelos de la suite del ORM — ≙ ``odoo19c:
odoo/addons/test_orm/models/test_orm.py``.

Adaptado de Odoo Community (LGPL-3): copia + adaptación con atribución, que es
el mecanismo que su manifest autoriza (DEC-KX-03). El porte es casi literal —
lo que cambia es el vocabulario de importación, porque aquí los primitivos del
ORM viven en la raíz ``src/`` espejada y no bajo un paquete ``odoo``.

Estos modelos no son producto: son el **sujeto** contra el que la suite mide el
porte de ``src/orm``. Un símbolo presente con la semántica cambiada pasa
cualquier censo de nombres y falla aquí, que es exactamente para lo que
existen.
"""

import datetime
import itertools

import fields
import models
from addons.base.models.timestamped_mixin import TimeStampedModel
from orm.models import BaseModel
from api import autovacuum, depends, onchange
from exceptions import AccessError


class TestOrmModel(BaseModel, TimeStampedModel):
    """La base de los modelos de este addon — ≙ ``models.Model`` de la fuente.

    Todo modelo de ``odoo19c: odoo/addons/test_orm/models/test_orm.py`` es un
    recordset: la suite lo crea con ``env[...].create`` y lo consulta con
    ``search``, ``browse`` y ``exists``. Aquí ese protocolo lo aporta
    :class:`~orm.models.BaseModel` (decisión registrada en H-API-1083: los
    modelos portados derivan de ella), y ``TimeStampedModel`` conserva las
    columnas y el ``Meta`` que el esquema ya migrado declara.

    El ``Meta`` se hereda explícitamente porque Django toma el del primer
    padre abstracto, y el primero es ``BaseModel``: sin esta línea el modelo
    perdía ``get_latest_by`` y la migración cambiaba sin que el esquema lo
    pidiera. Adoptar ``BaseModel`` en ``TimeStampedModel`` para todo el árbol
    es otra decisión y no se toma aquí.
    """

    class Meta(TimeStampedModel.Meta):
        abstract = True


class TestOrmCategory(TestOrmModel):
    """≙ ``:15``."""

    _name = 'test_orm.category'
    _description = 'Test ORM Category'
    _order = 'name'
    _parent_store = True
    _parent_name = 'parent'

    name = fields.Char(required=True)
    color = fields.Integer('Color Index')
    # H-API-1122: la fuente no declara ``required``, así que el Many2one es
    # opcional; aquí ``required = not null``, de ahí ``null=True``.
    parent = fields.Many2one('test_orm.category', ondelete='cascade', null=True)
    parent_path = fields.Char(index=True)
    depth = fields.Integer(compute='_compute_depth')
    root_categ = fields.Many2one(
        'test_orm.category', compute='_compute_root_categ'
    )
    display_name = fields.Char(
        inverse='_inverse_display_name',
        recursive=True,
    )
    dummy = fields.Char(store=False)
    discussions = fields.Many2many(
        'test_orm.discussion',
        'test_orm_discussion_category',
        'category',
        'discussion',
    )

    _positive_color = models.Constraint(
        'CHECK(color >= 0)',
        "The color code must be positive!",
    )

    @depends('name', 'parent.display_name')  # this definition is recursive
    def _compute_display_name(self):
        for cat in self:
            if cat.parent:
                cat.display_name = cat.parent.display_name + ' / ' + cat.name
            else:
                cat.display_name = cat.name

    @depends('parent')
    def _compute_root_categ(self):
        for cat in self:
            current = cat
            while current.parent:
                current = current.parent
            cat.root_categ = current

    @depends('parent_path')
    def _compute_depth(self):
        for cat in self:
            cat.depth = cat.parent_path.count('/') - 1

    def _inverse_display_name(self):
        for cat in self:
            names = cat.display_name.split('/')
            # determine sequence of categories
            categories = []
            for name in names[:-1]:
                category = self.search([('name', 'ilike', name.strip())])
                categories.append(category[0])
            categories.append(cat)
            # assign parents following sequence
            for parent, child in itertools.pairwise(categories):
                if parent and child:
                    child.parent = parent
            # assign name of last category, and reassign display_name
            # (to normalize it)
            cat.name = names[-1].strip()

    def _fetch_query(self, query, fields):
        # DLE P45: `test_31_prefetch`,
        # with self.assertRaises(AccessError):
        #     cat1.name
        if self.search_count(
            [('id', 'in', self._ids), ('name', '=', 'NOACCESS')]
        ):
            msg = 'Sorry'
            raise AccessError(msg)
        return super()._fetch_query(query, fields)

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_category'


class TestOrmDiscussion(TestOrmModel):
    """≙ ``:88``."""

    _name = 'test_orm.discussion'
    _description = 'Test ORM Discussion'

    name = fields.Char(
        string='Title', required=True, help="Description of discussion."
    )
    # ``related_name='+'`` porta la AUSENCIA de reverso, no la relaja: la
    # fuente nunca crea un accesor inverso implicito —el inverso de un
    # ``Many2one`` alla solo existe si alguien declara un ``One2many`` con su
    # ``inverse_name``— y medido, ninguno lo hace para estos dos, ni aqui ni en
    # ``odoo19c: odoo/addons/test_orm/models/test_orm.py:93,96``. Django si lo
    # crea, y dos campos al mismo destino chocan en ``testormdiscussion_set``
    # (``fields.E304``). Es la convencion dominante del arbol: 197
    # declaraciones ya la usan, y ``One2many.__get__`` la contempla
    # (``src/orm/fields_relational.py:371-373``).
    moderator = fields.Many2one('res.users', related_name='+', null=True)  # H-API-1122
    categories = fields.Many2many(
        'test_orm.category',
        'test_orm_discussion_category',
        'discussion',
        'category',
    )
    participants = fields.Many2many(
        'res.users', context={'active_test': False}, related_name='+'
    )
    messages = fields.One2many('test_orm.message', 'discussion', copy=True)
    message_concat = fields.Text(string='Message concatenate')
    important_messages = fields.One2many(
        'test_orm.message', 'discussion', domain=[('important', '=', True)]
    )
    very_important_messages = fields.One2many(
        'test_orm.message',
        'discussion',
        domain=lambda self: self._domain_very_important(),
    )
    emails = fields.One2many('test_orm.emailmessage', 'discussion')
    important_emails = fields.One2many(
        'test_orm.emailmessage',
        'discussion',
        domain=[('important', '=', True)],
    )

    history = fields.Json('History', default={'delete_messages': []})
    attributes_definition = fields.PropertiesDefinition(
        'Message Properties'
    )  # see message@attributes

    def _domain_very_important(self):
        """Ensure computed O2M domains work as expected."""
        return [("important", "=", True)]

    @onchange('name')
    def _onchange_name(self):
        # test onchange modifying one2many field values
        if (
            self.env.context.get('generate_dummy_message')
            and self.name == '{generate_dummy_message}'
        ):
            # update body of existings messages and emails
            for message in self.messages:
                message.body = 'not last dummy message'
            for message in self.important_messages:
                message.body = 'not last dummy message'
            # add new dummy message
            message_vals = self.messages._add_missing_default_values(
                {'body': 'dummy message', 'important': True}
            )
            self.messages |= self.messages.new(message_vals)
            self.important_messages |= self.messages.new(message_vals)

    @onchange('moderator')
    def _onchange_moderator(self):
        self.participants |= self.moderator

    @onchange('messages')
    def _onchange_messages(self):
        self.message_concat = "\n".join(
            ["%s:%s" % (m.name, m.body) for m in self.messages]
        )

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_discussion'


# ---------------------------------------------------------------------------
# Multicompañía — ≙ ``odoo19c: odoo/addons/test_orm/models/test_orm.py``
# (``TestOrmModel_Parent``, ``_Child``, ``_Child_Nocheck``). Ningún Many2one de
# la fuente declara ``required``, así que todos llevan ``null=True``
# (H-API-1122). El nombre sigue la convención del árbol: ``company`` con
# ``attname`` ``company_id``, que es el nombre por el que ``create`` y
# ``_fields`` responden también.
# ---------------------------------------------------------------------------


class TestOrmModelParent(TestOrmModel):
    """≙ ``test_orm.model_parent``."""

    _name = 'test_orm.model_parent'
    _description = 'Model Multicompany parent'

    name = fields.Char()
    company = fields.Many2one('res.company', null=True, related_name='+')

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_model_parent'


class TestOrmModelChild(TestOrmModel):
    """≙ ``test_orm.model_child``."""

    _name = 'test_orm.model_child'
    _description = 'Model Multicompany child'
    _check_company_auto = True

    name = fields.Char()
    company = fields.Many2one('res.company', null=True, related_name='+')
    parent = fields.Many2one(
        'test_orm.model_parent', string="Parent", check_company=True,
        null=True, related_name='+')
    parent_ids = fields.Many2many(
        'test_orm.model_parent', string="Parents", check_company=True,
        related_name='+')

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_model_child'


class TestOrmModelChildNocheck(TestOrmModel):
    """≙ ``test_orm.model_child_nocheck``."""

    _name = 'test_orm.model_child_nocheck'
    _description = 'Model Multicompany child'
    _check_company_auto = True

    name = fields.Char()
    company = fields.Many2one('res.company', null=True, related_name='+')
    parent = fields.Many2one(
        'test_orm.model_parent', check_company=False, null=True,
        related_name='+')

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_model_child_nocheck'


# ---------------------------------------------------------------------------
# Orden — ≙ ``TestOrmCountry``, ``TestOrmCity`` y ``TestOrmModel_Active_Field``
# (``odoo19c: odoo/addons/test_orm/models/test_orm.py``). Los Many2one son
# opcionales como en la fuente (H-API-1122).
# ---------------------------------------------------------------------------


class TestOrmCountry(TestOrmModel):
    """≙ ``test_orm.country``."""

    _name = 'test_orm.country'
    _description = 'Country, ordered by name'
    _order = 'name, id'

    name = fields.Char()

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_country'


class TestOrmCity(TestOrmModel):
    """≙ ``test_orm.city``."""

    _name = 'test_orm.city'
    _description = 'City, ordered by country then name'
    _order = 'country_id, name, id'

    # La fuente no declara ``required``: el nombre admite ``NULL``, y
    # ``test_sort.test_nulls`` lo crea con ``False``. Aquí un ``Char`` es
    # ``NOT NULL`` por omisión (H-API-1125).
    name = fields.Char(null=True)
    country = fields.Many2one('test_orm.country', null=True, related_name='+')

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_city'


class TestOrmModelActiveField(TestOrmModel):
    """≙ ``test_orm.model_active_field``."""

    _name = 'test_orm.model_active_field'
    _description = 'A model with active field'

    name = fields.Char()
    active = fields.Boolean(default=True)
    parent = fields.Many2one(
        'test_orm.model_active_field', null=True, related_name='+')
    children_ids = fields.One2many('test_orm.model_active_field', 'parent')
    all_children_ids = fields.One2many(
        'test_orm.model_active_field', 'parent',
        context={'active_test': False})
    active_children_ids = fields.One2many(
        'test_orm.model_active_field', 'parent',
        context={'active_test': True})
    relatives_ids = fields.Many2many(
        'test_orm.model_active_field',
        'model_active_field_relatives_rel', 'source_id', 'dest_id',
    )

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_model_active_field'


class TestOrmAutovacuumed(TestOrmModel):
    """≙ ``test_orm.autovacuumed`` (``odoo19c: odoo/addons/test_orm/models/
    test_orm.py:2437``): dos métodos ``@api.autovacuum`` sobre el recordset.
    """

    _name = 'test_orm.autovacuumed'
    _description = 'test_orm.autovacuumed'

    expire_at = fields.Datetime('Expires at', null=True)

    @autovacuum
    def _gc_simple(self):
        self.search([('expire_at', '<', datetime.datetime.now() - datetime.timedelta(days=1))]).unlink()

    @autovacuum
    def _gc_proper(self, limit=5):
        records = self.search([('expire_at', '<', datetime.datetime.now() - datetime.timedelta(days=1))], limit=limit)
        records.unlink()
        return len(records), len(records) == limit

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_autovacuumed'


# ---------------------------------------------------------------------------
# Una tabla, dos relaciones — ≙ ``TestOrmCrew``, ``TestOrmShip``,
# ``TestOrmPirate`` y ``TestOrmPrisoner`` (``odoo19c: odoo/addons/test_orm/
# models/test_orm.py:1960-1995``). ``test_orm_crew`` es la tabla del modelo
# ``crew``: *"the union of two relations pirate/ship and prisoner/ship, where
# some of the many2one fields can be NULL"*.
# ---------------------------------------------------------------------------


class TestOrmCrew(TestOrmModel):
    """≙ ``test_orm.crew``."""

    _name = 'test_orm.crew'
    _description = 'All yaaaaaarrrrr by ship'
    _table = 'test_orm_crew'

    pirate = fields.Many2one('test_orm.pirate', null=True, related_name='+')
    prisoner = fields.Many2one('test_orm.prisoner', null=True, related_name='+')
    ship = fields.Many2one('test_orm.ship', null=True, related_name='+')

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_crew'


class TestOrmShip(TestOrmModel):
    """≙ ``test_orm.ship``."""

    _name = 'test_orm.ship'
    _description = 'Yaaaarrr machine'

    name = fields.Char('Name', null=True)
    pirate_ids = fields.Many2many(
        'test_orm.pirate', 'test_orm_crew', 'ship_id', 'pirate_id')
    prisoner_ids = fields.Many2many(
        'test_orm.prisoner', 'test_orm_crew', 'ship_id', 'prisoner_id')

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_ship'


class TestOrmPirate(TestOrmModel):
    """≙ ``test_orm.pirate``."""

    _name = 'test_orm.pirate'
    _description = 'Yaaarrr'

    name = fields.Char('Name', null=True)
    ship_ids = fields.Many2many(
        'test_orm.ship', 'test_orm_crew', 'pirate_id', 'ship_id')

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_pirate'


class TestOrmPrisoner(TestOrmModel):
    """≙ ``test_orm.prisoner``."""

    _name = 'test_orm.prisoner'
    _description = 'Yaaarrr minions'

    name = fields.Char('Name', null=True)
    ship_ids = fields.Many2many(
        'test_orm.ship', 'test_orm_crew', 'prisoner_id', 'ship_id')

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_prisoner'


# ---------------------------------------------------------------------------
# ``test_orm.multi`` y sus líneas y etiquetas — ≙ ``odoo19c: odoo/addons/
# test_orm/models/test_orm.py:274-330``. Son el sujeto de ``TestSubqueries``
# (``tests/test_search.py``): búsquedas con subcampo sobre un Many2one, un
# One2many y un Many2many.
#
# pendiente: ``name`` (``related='partner.name'``), ``partners``
# (``One2many(related='partner.child_ids')``), ``_onchange_name`` de ``multi``
# y el ``display_name`` dependiente de contexto de ``multi.tag``: ninguno lo
# usa ``TestSubqueries``; entran con el porte de ``test_onchange.py``.
# ---------------------------------------------------------------------------


class TestOrmMultiTag(TestOrmModel):
    """≙ ``test_orm.multi.tag``."""

    _name = 'test_orm.multi.tag'
    _description = 'Test ORM Multi Tag'

    name = fields.Char(null=True)

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_multi_tag'


class TestOrmMulti(TestOrmModel):
    """≙ ``test_orm.multi``."""

    _name = 'test_orm.multi'
    _description = 'Test ORM Multi'

    partner = fields.Many2one('res.partner', null=True, related_name='+')
    tags = fields.Many2many(
        'test_orm.multi.tag', domain=[('name', 'ilike', 'a')])

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_multi'


class TestOrmMultiLine(TestOrmModel):
    """≙ ``test_orm.multi.line``. ``multi`` es el inverso del One2many
    ``lines`` de la fuente: aquí el uno-a-muchos es el reverso de Django."""

    _name = 'test_orm.multi.line'
    _description = 'Test ORM Multi Line'

    multi = fields.Many2one(
        'test_orm.multi', ondelete='cascade', null=True, related_name='lines')
    name = fields.Char(null=True)
    partner = fields.Many2one(
        'res.partner', related='multi.partner', store=True, null=True,
        related_name='+')
    tags = fields.Many2many('test_orm.multi.tag', related_name='+')

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_multi_line'


# ---------------------------------------------------------------------------
# ``test_orm.related``, ``related_foo`` y ``related_bar`` — ≙ ``odoo19c:
# odoo/addons/test_orm/models/test_orm.py:447-520``. Son el sujeto de
# ``TestSearchAny`` (``tests/test_search.py:1360``): ``any`` aplica las reglas
# de fila del comodelo y ``any!`` las salta.
#
# pendiente: los demás campos ``related=`` de ``related`` (Many2one,
# Many2many, One2many y binarios), ``message`` y los binarios de
# ``related_foo``; los usan los casos de ``TestSearchRelated`` aún no
# portados.
# ---------------------------------------------------------------------------


class TestOrmRelatedBar(TestOrmModel):
    """≙ ``test_orm.related_bar``."""

    _name = 'test_orm.related_bar'
    _description = 'test_orm.related_bar'

    name = fields.Char(null=True)
    active = fields.Boolean(default=True)

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_related_bar'


class TestOrmRelatedFoo(TestOrmModel):
    """≙ ``test_orm.related_foo``."""

    _name = 'test_orm.related_foo'
    _description = 'test_orm.related_foo'

    name = fields.Char(null=True)
    bar_id = fields.Many2one('test_orm.related_bar', null=True,
                             related_name='+')
    bar_ids = fields.Many2many('test_orm.related_bar', related_name='+')

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_related_foo'


class TestOrmRelated(TestOrmModel):
    """≙ ``test_orm.related``. ``foo_id`` es el inverso del ``foo_ids`` de
    ``related_foo`` en la fuente: aquí ese One2many es el reverso de Django."""

    _name = 'test_orm.related'
    _description = 'Test ORM Related'

    name = fields.Char(null=True)
    foo_id = fields.Many2one('test_orm.related_foo', null=True,
                             related_name='foo_ids')

    foo_name = fields.Char('foo_name', related='foo_id.name',
                           related_sudo=False)
    foo_name_sudo = fields.Char('foo_name_sudo', related='foo_id.name',
                                related_sudo=True)
    foo_bar_name = fields.Char('foo_bar_name', related='foo_id.bar_id.name',
                               related_sudo=False)
    foo_bar_name_sudo = fields.Char('foo_bar_name_sudo',
                                    related='foo_id.bar_id.name',
                                    related_sudo=True)

    foo_bar_id = fields.Many2one('test_orm.related_bar',
                                 related='foo_id.bar_id', related_sudo=False,
                                 string='Bar')
    foo_bar_sudo_id = fields.Many2one('test_orm.related_bar',
                                      related='foo_id.bar_id',
                                      related_sudo=True, string='Bar Sudo')

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_related'


# ---------------------------------------------------------------------------
# ``test_orm.hierarchy.head`` y ``node`` — ≙ ``odoo19c: odoo/addons/test_orm/
# models/test_orm.py:2348-2361``. Jerarquía sin ``_parent_store``: el
# ``child_of``/``parent_of`` se resuelve nivel por nivel.
# ---------------------------------------------------------------------------


class TestOrmHierarchyNode(TestOrmModel):
    """≙ ``test_orm.hierarchy.node``. ``child_ids`` es el reverso de
    ``parent_id``."""

    _name = 'test_orm.hierarchy.node'
    _description = 'Hierarchy Node'

    name = fields.Char(null=True)
    parent_id = fields.Many2one('test_orm.hierarchy.node', null=True,
                                related_name='child_ids')

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_hierarchy_node'


class TestOrmHierarchyHead(TestOrmModel):
    """≙ ``test_orm.hierarchy.head``."""

    _name = 'test_orm.hierarchy.head'
    _description = 'Hierarchy Head'

    node_id = fields.Many2one('test_orm.hierarchy.node', null=True,
                              related_name='+')

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_hierarchy_head'


class TestOrmRelatedInherits(TestOrmModel):
    """≙ ``test_orm.related_inherits`` (``odoo19c: odoo/addons/test_orm/
    models/test_orm.py:522-527``): delega en ``test_orm.related``."""

    _name = 'test_orm.related_inherits'
    _description = 'test_orm.related_inherits'
    _inherits = {'test_orm.related': 'base_id'}

    base_id = fields.Many2one('test_orm.related', required=True,
                              ondelete='cascade', related_name='+')

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_related_inherits'


class TestOrmMixed(TestOrmModel):
    """≙ ``test_orm.mixed`` (``odoo19c: odoo/addons/test_orm/models/
    test_orm.py:362-402``), sujeto de ``TestDomain``.

    pendiente: ``number2`` (``digits='ORM Precision'``, que exige el registro
    de ``decimal.precision`` del addon), ``now``, ``lang``, ``reference``, los
    seis ``Html`` y el defecto ``base.EUR`` de ``currency_id``; entran con los
    casos de ``TestDomain`` que los usan.
    """

    _name = 'test_orm.mixed'
    _description = 'Test ORM Mixed'

    foo = fields.Char(null=True)
    text = fields.Text(null=True)
    truth = fields.Boolean(default=False)
    count = fields.Integer(null=True)
    number = fields.Float(digits=(10, 2), default=3.14)
    date = fields.Date(null=True)
    moment = fields.Datetime(null=True)
    currency_id = fields.Many2one('res.currency', null=True,
                                  related_name='+')

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_mixed'


class TestOrmMessage(TestOrmModel):
    """≙ ``test_orm.message`` (``odoo19c: odoo/addons/test_orm/models/
    test_orm.py:138-240``), en la parte que usan los casos ``like`` y
    ``bool`` de ``TestDomain``.

    pendiente: ``name`` es aquí un ``Char`` llano y en la fuente es
    ``compute='_compute_name', store=True``; ``author``, ``body``, ``size``,
    ``double_size``, ``discussion_name``, ``author_partner``, ``label``,
    ``has_important_sibling``, ``attributes`` y las dos restricciones entran
    con ``TestFields``.
    """

    _name = 'test_orm.message'
    _description = 'Test ORM Message'

    discussion = fields.Many2one('test_orm.discussion', ondelete='cascade',
                                 null=True, related_name='+')
    name = fields.Char(string='Title', null=True)
    important = fields.Boolean(default=False)
    priority = fields.Integer(null=True)
    active = fields.Boolean(default=True)

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_message'


class TestOrmEmptyChar(TestOrmModel):
    """≙ ``test_orm.empty_char`` (``odoo19c: :2272-2276``)."""

    _name = 'test_orm.empty_char'
    _description = 'A model to test emtpy char'

    name = fields.Char('Name', null=True)

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_empty_char'


class TestOrmEmptyInt(TestOrmModel):
    """≙ ``test_orm.empty_int`` (``odoo19c: :2279-2283``)."""

    _name = 'test_orm.empty_int'
    _description = 'A model to test empty int'

    number = fields.Integer('Number', null=True)

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_empty_int'


class TestOrmFoo(TestOrmModel):
    """≙ ``test_orm.foo`` (``odoo19c: :414-421``).

    pendiente: ``change_default`` de ``value1`` y ``trim=False`` de ``text``.
    """

    _name = 'test_orm.foo'
    _description = 'Test ORM Foo'

    name = fields.Char(null=True)
    value1 = fields.Integer(null=True)
    value2 = fields.Integer(null=True)
    text = fields.Char(null=True)

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_foo'


class TestOrmBar(TestOrmModel):
    """≙ ``test_orm.bar`` (``odoo19c: :424-445``): un Many2one calculado, sin
    columna, que se busca por el nombre del ``foo``.

    pendiente: los ``related`` ``value1``, ``value2``, ``text1`` y ``text2``.
    """

    _name = 'test_orm.bar'
    _description = 'Test ORM Bar'

    name = fields.Char(null=True)
    foo = fields.Many2one('test_orm.foo', compute='_compute_foo',
                          search='_search_foo', related_name='+')

    @depends('name')
    def _compute_foo(self):
        for bar in self:
            bar.foo = self.env['test_orm.foo'].search(
                [('name', '=', bar.name)], limit=1)

    @classmethod
    def _search_foo(cls, operator, value):
        # ``@classmethod``: el método ``search=`` se invoca sobre la clase,
        # que es lo que ``env['x']`` devuelve aquí.
        if operator not in ('in', 'any'):
            return NotImplemented
        records = TestOrmFoo.browse(value)
        return [('name', 'in', records.mapped('name'))]

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_bar'


class TestOrmAnyParent(TestOrmModel):
    """≙ ``test_orm.any.parent`` (``odoo19c: :2319-2324``). ``child_ids`` es
    el reverso del ``parent_id`` de ``any.child``."""

    _name = 'test_orm.any.parent'
    _description = 'Any Parent'

    name = fields.Char(null=True)

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_any_parent'


class TestOrmAnyChild(TestOrmModel):
    """≙ ``test_orm.any.child`` (``odoo19c: :2327-2337``): delega en
    ``any.parent``."""

    _name = 'test_orm.any.child'
    _description = 'Any Child'
    _inherits = {'test_orm.any.parent': 'parent_id'}

    parent_id = fields.Many2one('test_orm.any.parent', required=True,
                                ondelete='cascade', related_name='child_ids')
    link_sibling_id = fields.Many2one('test_orm.any.child', null=True,
                                      related_name='+')
    quantity = fields.Integer(null=True)
    tag_ids = fields.Many2many('test_orm.any.tag', related_name='child_ids')

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_any_child'


class TestOrmAnyTag(TestOrmModel):
    """≙ ``test_orm.any.tag`` (``odoo19c: :2340-2345``). ``child_ids`` es el
    reverso del ``tag_ids`` de ``any.child``."""

    _name = 'test_orm.any.tag'
    _description = 'Any tag'

    name = fields.Char(null=True)

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_any_tag'
