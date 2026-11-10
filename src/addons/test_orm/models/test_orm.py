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
from orm.models import BaseModel, extend_model, get_current_user
from api import autovacuum, constrains, depends, onchange
from exceptions import AccessError, ValidationError


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
    color = fields.Integer('Color Index', null=True)
    # H-API-1122: la fuente no declara ``required``, así que el Many2one es
    # opcional; aquí ``required = not null``, de ahí ``null=True``.
    parent = fields.Many2one('test_orm.category', ondelete='cascade',
                             null=True, db_column='parent')
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
    moderator = fields.Many2one('res.users', related_name='+', null=True,
                                db_column='moderator')  # H-API-1122
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
    company = fields.Many2one('res.company', null=True, related_name='+',
                              db_column='company')

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_model_parent'


class TestOrmModelChild(TestOrmModel):
    """≙ ``test_orm.model_child``."""

    _name = 'test_orm.model_child'
    _description = 'Model Multicompany child'
    _check_company_auto = True

    name = fields.Char()
    company = fields.Many2one('res.company', null=True, related_name='+',
                              db_column='company')
    parent = fields.Many2one(
        'test_orm.model_parent', string="Parent", check_company=True,
        null=True, related_name='+', db_column='parent')
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
    company = fields.Many2one('res.company', null=True, related_name='+',
                              db_column='company')
    parent = fields.Many2one(
        'test_orm.model_parent', check_company=False, null=True,
        related_name='+', db_column='parent')

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
    country_id = fields.Many2one('test_orm.country', null=True,
                                 related_name='+', db_column='country_id')

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_city'


class TestOrmModelActiveField(TestOrmModel):
    """≙ ``test_orm.model_active_field``."""

    _name = 'test_orm.model_active_field'
    _description = 'A model with active field'

    name = fields.Char()
    active = fields.Boolean(default=True, null=True)
    parent = fields.Many2one(
        'test_orm.model_active_field', null=True, related_name='+',
        db_column='parent')
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

    pirate_id = fields.Many2one('test_orm.pirate', null=True,
                                related_name='+', db_column='pirate_id')
    prisoner_id = fields.Many2one('test_orm.prisoner', null=True,
                                  related_name='+', db_column='prisoner_id')
    ship_id = fields.Many2one('test_orm.ship', null=True,
                              related_name='+', db_column='ship_id')

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

    name = fields.Char(related='partner.name', readonly=True)
    partner = fields.Many2one('res.partner', null=True, related_name='+',
                              db_column='partner')
    # ``partner.child_ids`` en la fuente; aquí el inverso de ``res.partner``
    # se llama ``children`` (``res_partner.py``, divergencia declarada).
    partners = fields.One2many(related='partner.children')
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
        'test_orm.multi', ondelete='cascade', null=True, related_name='lines',
        db_column='multi')
    name = fields.Char(null=True)
    partner = fields.Many2one(
        'res.partner', related='multi.partner', store=True, null=True,
        related_name='+', db_column='partner')
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
                             related_name='+', db_column='bar_id')
    bar_ids = fields.Many2many('test_orm.related_bar', related_name='+')

    foo_names = fields.Char(related='foo_ids.name', related_sudo=False,
                            string="Foo Names")
    foo_names_sudo = fields.Char(related='foo_ids.name', related_sudo=True,
                                 string="Foo Names Sudo")
    bar_names = fields.Char(related='bar_ids.name', related_sudo=False,
                            string="Bar Names")
    bar_names_sudo = fields.Char(related='bar_ids.name', related_sudo=True,
                                 string="Bar Names Sudo")

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_related_foo'


class TestOrmRelated(TestOrmModel):
    """≙ ``test_orm.related``. ``foo_id`` es el inverso del ``foo_ids`` de
    ``related_foo`` en la fuente: aquí ese One2many es el reverso de Django."""

    _name = 'test_orm.related'
    _description = 'Test ORM Related'

    name = fields.Char(null=True)
    foo_id = fields.Many2one('test_orm.related_foo', null=True,
                             related_name='foo_ids', db_column='foo_id')

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

    foo_bar_ids = fields.Many2many('test_orm.related_bar', related='foo_id.bar_ids',
                                   related_sudo=False)
    foo_bar_sudo_ids = fields.Many2many('test_orm.related_bar', related='foo_id.bar_ids',
                                        related_sudo=True, string='Bars Sudo')
    foo_foo_ids = fields.One2many(related='foo_id.foo_ids',
                                  related_sudo=False, string='Foo Foos')
    foo_foo_sudo_ids = fields.One2many(related='foo_id.foo_ids',
                                       related_sudo=True,
                                       string='Foo Foos Sudo')

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
                                related_name='child_ids',
                                db_column='parent_id')

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_hierarchy_node'


class TestOrmHierarchyHead(TestOrmModel):
    """≙ ``test_orm.hierarchy.head``."""

    _name = 'test_orm.hierarchy.head'
    _description = 'Hierarchy Head'

    node_id = fields.Many2one('test_orm.hierarchy.node', null=True,
                              related_name='+', db_column='node_id')

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_hierarchy_head'


class TestOrmRelatedInherits(TestOrmModel):
    """≙ ``test_orm.related_inherits`` (``odoo19c: odoo/addons/test_orm/
    models/test_orm.py:522-527``): delega en ``test_orm.related``."""

    _name = 'test_orm.related_inherits'
    _description = 'test_orm.related_inherits'
    _inherits = {'test_orm.related': 'base_id'}

    base_id = fields.Many2one('test_orm.related', null=False, required=True,
                              ondelete='cascade', related_name='+',
                              db_column='base_id')

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_related_inherits'


class TestOrmMixed(TestOrmModel):
    """≙ ``test_orm.mixed`` (``odoo19c: odoo/addons/test_orm/models/
    test_orm.py:362-402``), sujeto de ``TestDomain``.

    ``number2`` lee su precisión del registro ``ORM Precision`` de
    ``decimal.precision`` que siembra la migración ``0034``, como
    ``test_orm_data.xml`` en la fuente.

    pendiente: ``now``, ``lang``, ``reference``, los seis ``Html`` y el
    defecto ``base.EUR`` de ``currency_id``; entran con los casos de
    ``TestDomain`` que los usan.
    """

    _name = 'test_orm.mixed'
    _description = 'Test ORM Mixed'

    foo = fields.Char(null=True)
    text = fields.Text(null=True)
    truth = fields.Boolean(default=False)
    count = fields.Integer(null=True)
    number = fields.Float(digits=(10, 2), default=3.14)
    number2 = fields.Float(digits='ORM Precision', null=True)
    date = fields.Date(null=True)
    moment = fields.Datetime(null=True)
    currency_id = fields.Many2one('res.currency', null=True,
                                  related_name='+', db_column='currency_id')
    amount = fields.Monetary(max_digits=20, decimal_places=2, null=True)

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_mixed'


class TestOrmMessage(TestOrmModel):
    """≙ ``test_orm.message`` (``odoo19c: odoo/addons/test_orm/models/
    test_orm.py:138-240``), en la parte que usan los casos ``like`` y
    ``bool`` de ``TestDomain``.

    pendiente: ``name`` es aquí un ``Char`` llano y en la fuente es
    ``compute='_compute_name', store=True``; ``size``,
    ``double_size``, ``discussion_name``, ``author_partner``, ``label``,
    ``has_important_sibling`` y las dos restricciones entran
    con ``TestFields``.
    """

    _name = 'test_orm.message'
    _description = 'Test ORM Message'

    discussion = fields.Many2one('test_orm.discussion', ondelete='cascade',
                                 null=True, related_name='+',
                                 db_column='discussion')
    body = fields.Text(index='trigram', null=True)
    author = fields.Many2one('res.users', null=True, related_name='+',
                             db_column='author', default=get_current_user)
    name = fields.Char(string='Title', null=True, compute='_compute_name',
                       store=True)
    important = fields.Boolean(default=False)
    priority = fields.Integer(null=True)
    active = fields.Boolean(default=True)
    attributes = fields.Properties(
        string='Discussion Properties',
        definition='discussion.attributes_definition',
        null=True,
    )

    @constrains('author', 'discussion')
    def _check_author(self):
        for message in self.with_context(active_test=False):
            if (message.discussion and message.author
                    not in message.discussion.sudo().participants):
                raise ValidationError(self.env._(
                    "Author must be among the discussion participants."))

    @depends('author.name', 'discussion.name')
    def _compute_name(self):
        for message in self:
            # ``res.users`` no deriva de ``BaseModel`` (H-API-1083): su
            # ``Many2one`` vacío es el ``None`` de Django y no el recordset
            # vacío de la fuente, cuyo ``name`` vale ``False``
            author = message.author
            message.name = self.env.context.get(
                'compute_name', "[%s] %s" % (message.discussion.name or '',
                                             (author and author.name) or ''))

    @constrains('name')
    def _check_name(self):
        # dummy constraint to check on computed field
        for message in self:
            if message.name.startswith("[X]"):
                msg = "No way!"
                raise ValidationError(msg)

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

    parent_id = fields.Many2one('test_orm.any.parent', null=False,
                                required=True, ondelete='cascade',
                                related_name='child_ids',
                                db_column='parent_id')
    link_sibling_id = fields.Many2one('test_orm.any.child', null=True,
                                      related_name='+',
                                      db_column='link_sibling_id')
    quantity = fields.Integer(null=True)
    #: La tabla y las columnas por defecto de la fuente para un Many2many
    #: sin ``relation`` (``<tabla1>_<tabla2>_rel``, ``<tabla>_id``). Sin
    #: declararlas, la tabla intermedia automática de este campo nombraba en
    #: tiempo de ejecución una columna ``test_orm_any_tag_id`` que su
    #: migración no creó (``testormanytag_id``); la causa no está aislada.
    tag_ids = fields.Many2many(
        'test_orm.any.tag', 'test_orm_any_child_test_orm_any_tag_rel',
        'test_orm_any_child_id', 'test_orm_any_tag_id',
        related_name='child_ids')

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


# ---------------------------------------------------------------------------
# ``test_orm.model_parent_m2o``/``model_child_m2o``, ``order``/``order.line``
# y ``team``/``team.member`` — ≙ ``odoo19c: odoo/addons/test_orm/models/
# test_orm.py:1406-1449, :681-716, :2287-2302``. Son el sujeto de
# ``One2manyCase`` (``tests/test_one2many.py``): comandos sobre un One2many
# en ``create``/``write`` y ``child_of`` a través de un One2many.
#
# pendiente: ``has_been_rewarded`` de ``order.line`` y los enteros indexados
# de ``order``/``order.line``; ningún caso portado los lee.
# ---------------------------------------------------------------------------


class TestOrmModelParentM2o(TestOrmModel):
    """≙ ``test_orm.model_parent_m2o``. ``child_ids`` es el reverso del
    ``parent_id`` de ``model_child_m2o``."""

    _name = 'test_orm.model_parent_m2o'
    _description = 'dummy model with multiple childs'

    name = fields.Char('Name', null=True)
    cost = fields.Integer(compute='_compute_cost', store=True, null=True)

    @depends('child_ids.cost')
    def _compute_cost(self):
        for record in self:
            record.cost = sum(child.cost for child in record.child_ids)

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_model_parent_m2o'


class TestOrmModelChildM2o(TestOrmModel):
    """≙ ``test_orm.model_child_m2o``: su ``write`` lanza si el hijo se llama
    ``A``, que es lo que detecta reescribir un hijo ya enlazado."""

    _name = 'test_orm.model_child_m2o'
    _description = 'dummy model with override write and ValidationError'

    name = fields.Char('Name', null=True)
    parent_id = fields.Many2one('test_orm.model_parent_m2o',
                                ondelete='cascade', null=True,
                                related_name='child_ids',
                                db_column='parent_id')
    size1 = fields.Integer(compute='_compute_sizes', store=True, null=True)
    size2 = fields.Integer(compute='_compute_sizes', store=True, null=True)
    cost = fields.Integer(compute='_compute_cost', store=True, readonly=False,
                          null=True)

    @depends('parent_id.name')
    def _compute_sizes(self):
        for record in self:
            record.size1 = len(record.parent_id.name)
            record.size2 = len(record.parent_id.name)

    @depends('name')
    def _compute_cost(self):
        for record in self:
            record.cost = len(record.name)

    def write(self, vals):
        res = super().write(vals)
        if self.name == 'A':
            msg = 'the first existing child should not be changed when adding a new child to the parent'
            raise ValidationError(msg)
        return res

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_model_child_m2o'


class TestOrmOrder(TestOrmModel):
    """≙ ``test_orm.order``. ``line_ids`` es el reverso del ``order_id`` de
    ``order.line``."""

    _name = 'test_orm.order'
    _description = 'test_orm.order'

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_order'


class TestOrmOrderLine(TestOrmModel):
    """≙ ``test_orm.order.line``: borrar una línea borra también su línea de
    recompensa."""

    _name = 'test_orm.order.line'
    _description = 'test_orm.order.line'

    order_id = fields.Many2one('test_orm.order', null=False, required=True,
                               ondelete='cascade', related_name='line_ids',
                               db_column='order_id')
    product = fields.Char(null=True)
    reward = fields.Boolean(default=False)

    def unlink(self):
        # also delete associated reward lines
        reward_lines = [
            other_line
            for line in self
            if not line.reward
            for other_line in line.order_id.line_ids
            if other_line.reward and other_line.product == line.product
        ]
        self = self.union(*reward_lines)  # noqa: PLW0642
        return super().unlink()

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_order_line'


class TestOrmTeam(TestOrmModel):
    """≙ ``test_orm.team``. ``member_ids`` es el reverso del ``team_id`` de
    ``team.member``."""

    _name = 'test_orm.team'
    _description = 'Odoo Team'

    name = fields.Char(null=True)
    parent_id = fields.Many2one('test_orm.team', null=True, related_name='+',
                                db_column='parent_id')

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_team'


class TestOrmTeamMember(TestOrmModel):
    """≙ ``test_orm.team.member``: ``parent_id`` es el padre del equipo."""

    _name = 'test_orm.team.member'
    _description = 'Odoo Developer'

    name = fields.Char('Name', null=True)
    team_id = fields.Many2one('test_orm.team', null=True,
                              related_name='member_ids', db_column='team_id')
    parent_id = fields.Many2one('test_orm.team', related='team_id.parent_id')

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_team_member'


# ---------------------------------------------------------------------------
# ``test_orm.compute.container`` y ``compute.member`` — ≙ ``odoo19c:
# odoo/addons/test_orm/models/test_orm.py`` (``TestOrmComputeContainer``,
# ``TestOrmComputeMember``). Sujeto de
# ``test_compute_stored_many2one_one2many`` (``tests/test_one2many.py:317``):
# un Many2one calculado y almacenado cuyo
# One2many inverso alimenta un contador también almacenado.
#
# pendiente: ``name_translated`` de ``container`` y ``container_super_id``,
# ``container_context_id`` y sus dos ``related`` de ``member``; los usan
# ``test_fields.py`` y ``test_search.py``, aún no portados en esa parte.
# ---------------------------------------------------------------------------


class TestOrmComputeContainer(TestOrmModel):
    """≙ ``test_orm.compute.container``. ``member_ids`` es el reverso del
    ``container_id`` de ``compute.member``."""

    _name = 'test_orm.compute.container'
    _description = 'test_orm.compute.container'

    name = fields.Char(null=True)
    member_count = fields.Integer(compute='_compute_member_count', store=True,
                                  null=True)

    @depends('member_ids')
    def _compute_member_count(self):
        for record in self:
            record.member_count = len(record.member_ids)

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_compute_container'


class TestOrmComputeMember(TestOrmModel):
    """≙ ``test_orm.compute.member``: su contenedor es el que lleva su
    nombre."""

    _name = 'test_orm.compute.member'
    _description = 'test_orm.compute.member'

    name = fields.Char(null=True)
    container_id = fields.Many2one('test_orm.compute.container',
                                   compute='_compute_container', store=True,
                                   related_name='member_ids',
                                   db_column='container_id')

    @depends('name')
    def _compute_container(self):
        container = self.env['test_orm.compute.container']
        for member in self:
            member.container_id = container.search(
                [('name', '=', member.name)], limit=1)

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_compute_member'


class TestOrmUnsearchableO2m(TestOrmModel):
    """≙ ``test_orm.unsearchable.o2m`` (``odoo19c: odoo/addons/test_orm/models/
    test_orm.py``, ``TestOrmUnsearchableO2m``): un One2many cuyo inverso es un
    Many2one calculado y sin columna. Leerlo no tiene SQL que emitir."""

    _name = 'test_orm.unsearchable.o2m'
    _description = 'Test non-stored unsearchable o2m'

    name = fields.Char('Name', null=True)
    stored_parent_id = fields.Many2one('test_orm.unsearchable.o2m', null=True,
                                       related_name='+',
                                       db_column='stored_parent_id')
    parent_id = fields.Many2one('test_orm.unsearchable.o2m', store=False,
                                compute='_compute_parent_id',
                                related_name='+')
    child_ids = fields.One2many('test_orm.unsearchable.o2m', 'parent_id')

    @depends('stored_parent_id')
    def _compute_parent_id(self):
        for r in self:
            r.parent_id = r.stored_parent_id

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_unsearchable_o2m'


class TestOrmComputedInverseOne2many(TestOrmModel):
    """≙ ``test_orm.computed_inverse_one2many`` (``odoo19c: odoo/addons/
    test_orm/models/test_orm.py:1044-1062``): dos One2many calculados, con
    ``inverse``, que reparten las líneas de ``all_line_ids`` por prioridad."""

    _name = 'test_orm.computed_inverse_one2many'
    _description = "A computed/inverse o2m, subset of a main one"

    name = fields.Char(null=True)
    low_priority_line_ids = fields.One2many(
        'test_orm.computed_inverse_one2many_line',
        compute='_compute_priority_line_ids', inverse='_inverse_line_ids')
    high_priority_line_ids = fields.One2many(
        'test_orm.computed_inverse_one2many_line',
        compute='_compute_priority_line_ids', inverse='_inverse_line_ids')

    @depends('all_line_ids')
    def _compute_priority_line_ids(self):
        for record in self:
            low_lines = record.all_line_ids.filtered(lambda line: line.priority < 4)
            record.low_priority_line_ids = low_lines
            record.high_priority_line_ids = record.all_line_ids - low_lines

    def _inverse_line_ids(self):
        for record in self:
            record.all_line_ids = record.low_priority_line_ids | record.high_priority_line_ids

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_computed_inverse_one2many'


class TestOrmComputedInverseOne2manyLine(TestOrmModel):
    """≙ ``test_orm.computed_inverse_one2many_line``. ``parent_id`` es el
    inverso de ``all_line_ids``."""

    _name = 'test_orm.computed_inverse_one2many_line'
    _description = "Line of a computed/inverse one2many"

    name = fields.Char(null=True)
    priority = fields.Integer(null=True)
    parent_id = fields.Many2one('test_orm.computed_inverse_one2many',
                                related_name='all_line_ids',
                                db_column='parent_id')

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_computed_inverse_one2many_line'


class TestOrmModelSelectionBase(TestOrmModel):
    """≙ ``test_orm.model_selection_base`` (``odoo19c: odoo/addons/test_orm/
    models/test_orm.py:1477-1505``): la declaración base de ``my_selection``.

    La fuente suma ``quux`` y ``ham`` con dos redefiniciones ``_inherit``
    del mismo addon; aquí son las dos llamadas a :func:`extend_model` de
    abajo, que anotan ``test_orm`` como el módulo que las define.
    """

    _name = 'test_orm.model_selection_base'
    _description = "Model with a base selection field"

    my_selection = fields.Selection([
        ('foo', "Foo"),
        ('bar', "Bar"),
    ], null=True)

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_model_selection_base'


#: ≙ «Model with a selection field extension with ondelete null»
#: (``:1488-1495``).
extend_model('test_orm.model_selection_base',
             selection_add={'my_selection': [('quux', "Quux")]},
             ondelete={'my_selection': {'quux': 'set null'}})

#: ≙ «Model with a selection field extension without ondelete»
#: (``:1498-1505``).
extend_model('test_orm.model_selection_base',
             selection_add={'my_selection': [('ham', "Ham")]})


# ---------------------------------------------------------------------------
# ``test_orm.model.no_access`` / ``all_access`` / ``some_access`` — ≙
# ``odoo19c: odoo/addons/test_orm/models/test_orm.py:1794-1830``: los
# modelos con que la fuente prueba ``groups`` en el campo.
# ---------------------------------------------------------------------------


class TestOrmModelNoAccess(TestOrmModel):
    """≙ ``test_orm.model.no_access`` (``:1794-1799``)."""

    _name = 'test_orm.model.no_access'
    _description = "Testing Utilities attrs and groups: if never access rights"

    ab = fields.Integer(default=1)
    cd = fields.Integer(default=1, groups="base.group_portal")

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_model_no_access'


class TestOrmModelAllAccess(TestOrmModel):
    """≙ ``test_orm.model.all_access`` (``:1802-1811``)."""

    _name = 'test_orm.model.all_access'
    _description = "Testing Utilities attrs and groups: if free access rights"

    ab = fields.Integer(default=1)
    cd = fields.Integer(default=1, groups="base.group_portal")
    ef = fields.Integer(default=1)

    def action_full(self):
        return

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_model_all_access'


class TestOrmModelSomeAccess(TestOrmModel):
    """≙ ``test_orm.model.some_access`` (``:1814-1830``)."""

    _name = 'test_orm.model.some_access'
    _description = 'Testing Utilities attrs and groups'

    a = fields.Integer(null=True)
    b = fields.Integer(null=True)
    c = fields.Integer(null=True)
    d = fields.Integer(default=1, groups="base.group_erp_manager")
    e = fields.Integer(
        default=1, groups="base.group_erp_manager,base.group_multi_company")
    f = fields.Integer(
        null=True, groups="base.group_erp_manager,base.group_portal")
    g = fields.Integer(
        default=1,
        groups="base.group_erp_manager,base.group_multi_company,"
               "!base.group_portal")
    h = fields.Integer(
        default=1, groups="base.group_erp_manager,!base.group_portal")
    i = fields.Integer(default=1, groups="!base.group_portal")
    j = fields.Integer(default=1, groups="base.group_portal")
    k = fields.Integer(default=1, groups="base.group_public")
    g_id = fields.Many2one(
        'test_orm.model.all_access', string="m2o g_id", null=True,
        related_name='+', db_column='g_id')

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_model_some_access'


class TestOrmRelatedInheritsTwo(TestOrmModel):
    """Modelo de prueba propio: ``_inherits`` con dos padres.

    Ningún modelo de ``odoo19c`` declara dos padres (recorrido AST, 0), pero
    el atributo lo admite (``odoo/orm/models.py:407-425``) y con un nombre
    repetido gana el último padre. ``name`` está en los dos; ``foo_id`` sólo
    en ``test_orm.related`` y ``active`` sólo en ``test_orm.related_bar``.
    """

    _name = 'test_orm.related_inherits_two'
    _description = 'test_orm.related_inherits_two'
    _inherits = {'test_orm.related': 'base_id',
                 'test_orm.related_bar': 'bar_parent_id'}

    base_id = fields.Many2one('test_orm.related', null=False, required=True,
                              ondelete='cascade', related_name='+',
                              db_column='base_id')
    bar_parent_id = fields.Many2one('test_orm.related_bar', null=False,
                                    required=True, ondelete='cascade',
                                    related_name='+',
                                    db_column='bar_parent_id')

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_related_inherits_two'


class TestOrmUser(TestOrmModel):
    """≙ ``test_orm.user`` (``odoo19c: odoo/addons/test_orm/models/
    test_orm.py:1770-1783``) — destino de ``test_sudo_commands``."""

    _name = 'test_orm.user'
    _description = 'test_orm.user'
    _allow_sudo_commands = False

    name = fields.Char(null=True)
    group_ids = fields.Many2many(
        'test_orm.group', 'test_orm_group_test_orm_user_rel',
        'test_orm_user_id', 'test_orm_group_id')
    group_count = fields.Integer(null=True, compute='_compute_group_count',
                                 store=True)

    @depends('group_ids')
    def _compute_group_count(self):
        for user in self:
            user.group_count = len(user.group_ids)

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_user'


class TestOrmGroup(TestOrmModel):
    """≙ ``test_orm.group`` (``:1786-1791``)."""

    _name = 'test_orm.group'
    _description = 'test_orm.group'
    _allow_sudo_commands = False

    name = fields.Char(null=True)
    user_ids = fields.Many2many(
        'test_orm.user', 'test_orm_group_test_orm_user_rel',
        'test_orm_group_id', 'test_orm_user_id')

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_group'


class TestOrmComputeInverse(TestOrmModel):
    """≙ ``test_orm.compute.inverse`` (``odoo19c: odoo/addons/test_orm/
    models/test_orm.py:543-584``): un ``Char`` calculado, almacenado y con
    ``inverse`` (``bar``) junto a uno normal (``baz``), una restricción que
    nombra a los dos, y un ``One2many`` calculado con ``inverse``. Cada
    método anota su paso en ``context['log']`` para que las pruebas vean el
    orden de compute, inverse y restricción.
    """

    _name = 'test_orm.compute.inverse'
    _description = 'Model with a computed inversed field'

    foo = fields.Char(null=True)
    bar = fields.Char(compute='_compute_bar', inverse='_inverse_bar',
                      store=True, null=True)
    baz = fields.Char(null=True)
    child_ids = fields.One2many(
        'test_orm.compute.inverse', 'parent_id',
        compute='_compute_child_ids', inverse='_inverse_child_ids',
        store=True)
    parent_id = fields.Many2one('test_orm.compute.inverse', null=True,
                                related_name='+', db_column='parent_id')

    @depends('foo')
    def _compute_bar(self):
        self.env.context.get('log', []).append('compute')
        for record in self:
            record.bar = record.foo

    def _inverse_bar(self):
        self.env.context.get('log', []).append('inverse')
        for record in self:
            record.foo = record.bar

    @constrains('bar', 'baz')
    def _check_constraint(self):
        if self.env.context.get('log_constraint'):
            self.env.context.get('log', []).append('constraint')

    @depends('foo')
    def _compute_child_ids(self):
        for rec in self:
            if rec.foo == 'has one child':
                rec.child_ids = [
                    fields.Command.clear(),
                    fields.Command.create({'foo': 'child'}),
                ]

    def _inverse_child_ids(self):
        for rec in self:
            if any(child.foo == 'child' for child in self.child_ids):
                rec.foo = 'has one child'

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_compute_inverse'


class TestOrmComputeOnchange(TestOrmModel):
    """≙ ``test_orm.compute.onchange`` (``odoo19c: odoo/addons/test_orm/
    models/test_orm.py:880-937``): cómputos almacenados de sólo lectura
    (``bar``) y editables (``baz``), uno sin dependencias (``quux``), y dos
    x2many calculados, almacenados y editables: ``line_ids`` (``One2many``) y
    ``tag_ids`` (``Many2many``)."""

    _name = 'test_orm.compute.onchange'
    _description = "Compute method as an onchange"

    active = fields.Boolean(null=True)
    foo = fields.Char(null=True)
    bar = fields.Char(compute='_compute_bar', store=True, null=True)
    baz = fields.Char(compute='_compute_baz', store=True, readonly=False,
                      null=True)
    quux = fields.Char(compute='_compute_quux')
    count = fields.Integer(default=0, null=True)
    line_ids = fields.One2many(
        'test_orm.compute.onchange.line', 'record_id',
        compute='_compute_line_ids', store=True, readonly=False,
    )
    #: La tabla intermedia lleva el nombre por defecto de la fuente
    #: (``<modelo>_<comodelo>_rel``), declarado porque el de Django es otro.
    tag_ids = fields.Many2many(
        'test_orm.multi.tag',
        'test_orm_compute_onchange_test_orm_multi_tag_rel',
        'test_orm_compute_onchange_id', 'test_orm_multi_tag_id',
        compute='_compute_tag_ids', store=True, readonly=False,
    )

    @onchange('foo')
    def _onchange_foo(self):
        self.count += 1

    @depends('foo')
    def _compute_bar(self):
        for record in self:
            record.bar = (record.foo or "") + "r"

    @depends('active', 'foo')
    def _compute_baz(self):
        for record in self:
            if record.active:
                record.baz = (record.foo or "") + "z"

    # special case: this field has no dependency
    def _compute_quux(self):
        self.quux = "quux"

    @depends('foo')
    def _compute_line_ids(self):
        for record in self:
            if not record.foo:
                continue
            if any(line.foo == record.foo for line in record.line_ids):
                continue
            # add a line with the same value as 'foo'
            record.line_ids = [fields.Command.create({'foo': record.foo})]

    @depends('foo')
    def _compute_tag_ids(self):
        Tag = self.env['test_orm.multi.tag']
        for record in self:
            if record.foo:
                record.tag_ids = Tag.search([('name', '=', record.foo)])

    def copy_data(self, default=None):
        vals_list = super().copy_data(default=default)
        return [dict(vals, foo=self.env._("%s (copy)", record.foo))
                for record, vals in zip(self, vals_list)]

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_compute_onchange'


class TestOrmComputeOnchangeLine(TestOrmModel):
    """≙ ``test_orm.compute.onchange.line`` (``:940-950``)."""

    _name = 'test_orm.compute.onchange.line'
    _description = "Line-like model for test_orm.compute.onchange"

    record_id = fields.Many2one('test_orm.compute.onchange',
                                ondelete='cascade', null=True,
                                related_name='+', db_column='record_id')
    foo = fields.Char(null=True)
    bar = fields.Char(compute='_compute_bar')

    @depends('foo')
    def _compute_bar(self):
        for line in self:
            line.bar = (line.foo or "") + "r"

    class Meta(TestOrmModel.Meta):
        db_table = 'test_orm_compute_onchange_line'
