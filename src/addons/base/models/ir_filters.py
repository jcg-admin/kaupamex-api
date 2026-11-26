"""``ir.filters`` — filtros de búsqueda guardados (Odoo ``base``).

Porte de ``IrFilters``
(``odoo19c: odoo/addons/base/models/ir_filters.py:7-109``) sobre
``BaseModel``: la cabecera, los diez campos, los tres objetos de tabla y los
siete métodos. Diseño: ``designs/ir-filters-port-19.md`` del banco
``orm-continuation-plan-20261103T095630``.

Este archivo portaba antes la forma de Odoo 18 —un único dueño ``user``, la
etiqueta de Django en ``model_id``, la unicidad ``name_model_uid_unique`` y el
«un solo filtro por defecto» de ``_check_global_default``— y lo declaraba como
decisión. 19 gobierna: la migración ``0131`` lleva las filas existentes a
``user_ids`` y a la identidad del modelo, y retira la columna y la unicidad.

Lo que se adapta, y por qué:

- **``model_id``** guarda la identidad de :func:`orm.registry.identity_of`
  (el ``_name``, o la etiqueta mientras la clase no declara uno), que es lo
  que guarda ``ir_model.model`` (``designs/model-identity-contract.md``).
- **``_list_all_models``** ordena por ``ir_model.name`` sin el ``->>`` por
  idioma de la fuente: aquí la columna es texto plano, no ``jsonb``
  traducible.
- **``embedded_action``** conserva el nombre de su porte anterior; la columna
  es ``embedded_action_id``, la de la fuente.
"""

import ast

from django.db.models.lookups import Exact

import api
import fields
import models
from addons.base.models.res_users import ResUsers


class JsonbTypeOf(models.Func):
    """``jsonb_typeof(<expr>::jsonb)`` — el tipo JSON de una columna de texto.

    La referencia no necesita un ayudante: su ``models.Constraint`` recibe el
    SQL como cadena (``odoo19c: ir_filters.py:37-40``). Aquí la restricción se
    declara con el ORM, así que el ``::jsonb`` y la llamada se expresan como
    ``Func``. Vive junto a su único consumidor.
    """

    function = 'jsonb_typeof'
    template = '%(function)s(%(expressions)s::jsonb)'
    output_field = models.CharField()


class IrFilters(models.BaseModel):
    """``ir.filters`` — filtro de búsqueda nombrado.

    Guarda dominio, contexto y orden.
    """

    _name = 'ir.filters'
    _description = 'Filters'
    _order = 'model_id, name, id desc'

    name = fields.Char(
        max_length=256, verbose_name='Filter Name',
        help_text='Nombre del filtro (Odoo name, requerido).',
    )
    #: ≙ ``user_ids`` (``:13``), con la tabla y las columnas que el ORM de la
    #: fuente deriva para ``ir.filters`` × ``res.users``
    #: (``odoo19c: odoo/orm/fields_relational.py:1286-1295``).
    user_ids = fields.Many2many(
        ResUsers, relation='ir_filters_res_users_rel',
        column1='ir_filters_id', column2='res_users_id',
        blank=True, related_name='+', verbose_name='Users',
        help_text=(
            'The users the filter is shared with. If empty, the filter is '
            'shared with all users.'
        ),
    )
    domain = fields.Text(default='[]', help_text='Odoo domain.')
    context = fields.Text(default='{}', help_text='Odoo context.')
    sort = fields.Char(max_length=512, default='[]', help_text='Odoo sort.')
    model_id = fields.Selection(
        selection='_list_all_models', max_length=128, verbose_name='Model',
        help_text='Identidad del modelo (Odoo model_id).',
    )
    is_default = fields.Boolean(
        default=False, verbose_name='Default Filter',
        help_text='Odoo is_default.',
    )
    #: Forma **C** de ADR-029: el símbolo lleva el nombre de la fuente y
    #: ``db_column`` mantiene la columna ``action_id``.
    action_id = fields.Many2one(
        'base.IrActionsActions', on_delete=models.CASCADE,
        db_column='action_id', null=True, blank=True, db_index=True,
        related_name='filter_ids', verbose_name='Action',
        help_text=(
            'The menu action this filter applies to. When left empty the '
            'filter applies to all menus for this model.'
        ),
    )
    embedded_action = fields.Many2one(
        'base.IrEmbeddedActions', on_delete=models.CASCADE,
        null=True, blank=True, db_index=True, related_name='filter_ids',
        verbose_name='Embedded action',
        help_text='The embedded action this filter is applied to',
    )
    embedded_parent_res_id = fields.Integer(
        null=True, blank=True,
        help_text=(
            'id of the record the filter should be applied to. Only used in '
            'combination with embedded actions'
        ),
    )
    active = fields.Boolean(default=True, help_text='Odoo active.')

    class Meta:
        db_table = 'ir_filters'
        ordering = ['model_id', 'name', '-id']
        verbose_name = 'Filtro'
        verbose_name_plural = 'Filtros'
        #: ≙ ``_get_filters_index`` (``:27-29``), con su nombre conservado.
        indexes = [
            models.Index(
                fields=['model_id', 'action_id', 'embedded_action',
                        'embedded_parent_res_id'],
                name='ir_filters_get_filters_index',
            ),
        ]
        constraints = [
            #: ≙ ``_check_res_id_only_when_embedded_action`` (``:33-36``).
            #: Comentario de la fuente, verbatim: *"The embedded_parent_res_id
            #: can only be defined when the embedded_action_id field is set."*
            models.CheckConstraint(
                condition=~models.Q(
                    embedded_parent_res_id__isnull=False,
                    embedded_action__isnull=True,
                ),
                name='ir_filters_check_res_id_only_when_embedded_action',
            ),
            #: ≙ ``_check_sort_json`` (``:37-40``): ``CHECK ("sort" IS NULL
            #: OR jsonb_typeof("sort"::jsonb) = 'array')``.
            models.CheckConstraint(
                condition=(
                    models.Q(sort__isnull=True)
                    | models.Q(
                        Exact(JsonbTypeOf('sort'), models.Value('array'))
                    )
                ),
                name='ir_filters_check_sort_json',
            ),
        ]

    def __str__(self) -> str:
        return self.name

    @api.model
    def _list_all_models(self):
        """≙ ``_list_all_models`` (``:42-49``): los pares ``(model, name)`` de
        ``ir_model`` ordenados por nombre."""
        ir_model = self.env['ir.model']
        return [
            (model, name) for model, name in
            ir_model.objects.order_by('name').values_list('model', 'name')
        ]

    def copy_data(self, default=None):
        """≙ ``copy_data`` (``:51-58``)."""
        vals_list = super().copy_data(default=default)
        # NULL Integer field value read as 0, wouldn't matter except in this
        # case will trigger check_res_id_only_when_embedded_action
        for vals in vals_list:
            if vals.get('embedded_parent_res_id') == 0:
                del vals['embedded_parent_res_id']
        return [dict(vals, name=self.env._("%s (copy)", ir_filter.name))
                for ir_filter, vals in zip(self, vals_list)]

    def write(self, vals):
        """≙ ``write`` (``:60-63``)."""
        new_filter = super().write(vals)
        self.check_access('write')
        return new_filter

    def _get_eval_domain(self):
        """≙ ``_get_eval_domain`` (``:65-69``)."""
        try:
            return ast.literal_eval(self.domain)
        except ValueError as e:
            raise ValueError("Invalid domain: {self.domain}") from e

    @api.model
    def _get_action_domain(self, action_id=None, embedded_action_id=None,
                           embedded_parent_res_id=None):
        """Return a domain component for matching filters that are visible
        in the same context (menu/view) as the given action. ≙ ``:71-79``."""
        action_condition = (
            ('action_id', 'in', [action_id, False]) if action_id
            else ('action_id', '=', False))
        embedded_condition = (
            ('embedded_action_id', '=', embedded_action_id)
            if embedded_action_id
            else ('embedded_action_id', '=', False))
        embedded_parent_res_id_condition = (
            ('embedded_parent_res_id', '=', embedded_parent_res_id)
            if embedded_action_id and embedded_parent_res_id
            else ('embedded_parent_res_id', 'in', [0, False]))

        return [action_condition, embedded_condition,
                embedded_parent_res_id_condition]

    @api.model
    def get_filters(self, model, action_id=None, embedded_action_id=None,
                    embedded_parent_res_id=None):
        """Obtain the list of filters available for the user on the given
        model. ≙ ``get_filters`` (``:81-102``).

        :return: list of :meth:`~osv.read`-like dicts containing the
            ``name``, ``is_default``, ``domain``, ``user_ids`` (m2m),
            ``action_id`` (m2o tuple), ``embedded_action_id`` (m2o tuple),
            ``embedded_parent_res_id`` and ``context`` of the matching
            ``ir.filters``.
        """
        # available filters: private filters (user_ids=uids) and public
        # filters (uids=NULL), and filters for the action
        # (action_id=action_id) or global (action_id=NULL)
        user_context = self.env['res.users'].context_get()
        action_domain = self._get_action_domain(
            action_id, embedded_action_id, embedded_parent_res_id)
        return self.with_context(user_context).search_read(
            action_domain + [('model_id', '=', model),
                             ('user_ids', 'in', [self.env.uid, False])],
            ['name', 'is_default', 'domain', 'context', 'user_ids', 'sort',
             'embedded_action_id', 'embedded_parent_res_id'],
        )

    @api.model
    def create_filter(self, vals):
        """≙ ``create_filter`` (``:104-109``)."""
        embedded_action_id = vals.get('embedded_action_id')
        if not embedded_action_id and 'embedded_parent_res_id' in vals:
            del vals['embedded_parent_res_id']
        return self.create(vals)
