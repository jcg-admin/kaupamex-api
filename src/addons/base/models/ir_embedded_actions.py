"""``ir.embedded.actions`` — acciones embebidas en la vista de un registro.

Adaptación de ``odoo/addons/base/models/ir_embedded_actions.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 111 líneas), sobre
``models.BaseModel``: los atributos de clase, los campos con los nombres de la
fuente, las dos restricciones SQL, ``create``, ``_compute_display_name``,
``_compute_is_deletable``, ``_compute_is_visible``,
``_unlink_if_action_deletable`` y ``_get_readable_fields``.
Diseño: ``designs/ir-embedded-actions-basemodel.md``.

Cada ``Many2one`` declara ``db_column`` con su mismo nombre, la columna que
la fuente crea para un campo ``<x>_id``. ``groups_ids`` usa la tabla y las
columnas que la fuente deriva cuando no se le da ``relation``:
``'%s_%s_rel'`` sobre las dos tablas ordenadas, y ``'%s_id'`` por tabla
(``odoo19c: odoo/orm/fields_relational.py:1291-1295``).
"""

from ast import literal_eval

import api
import fields
import models

from addons.base.models.ir_actions import (
    IrActionsActions,
    IrActionsActWindow,
)
from addons.base.models.res_groups import ResGroups
from addons.base.models.res_users import ResUsers
from addons.base.models.timestamped_mixin import TimeStampedModel
from exceptions import UserError
from orm.environments import sudo
from tools.translate import _


class IrEmbeddedActions(models.BaseModel, TimeStampedModel):
    """Acción embebida en la vista de un registro (``ir.embedded.actions``,
    ``odoo19c: ir_embedded_actions.py:8-111``)."""

    _name = 'ir.embedded.actions'
    _description = 'Embedded Actions'
    _order = 'sequence, id'

    name = fields.Char(translate=True, null=True, blank=True)
    sequence = fields.Integer(null=True, blank=True)
    parent_action_id = fields.Many2one(
        IrActionsActWindow,
        null=False,
        on_delete=models.CASCADE,
        related_name='+',
        db_column='parent_action_id',
        verbose_name='Parent Action',
    )
    parent_res_id = fields.Integer(
        null=True, blank=True, verbose_name='Active Parent Id')
    parent_res_model = fields.Char(verbose_name='Active Parent Model')
    # It is required to have either action_id or python_method
    action_id = fields.Many2one(
        IrActionsActions,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        # Sin clave foránea: ``ir_actions`` se hereda (``odoo19c:
        # odoo/orm/fields_relational.py:313-314``).
        db_constraint=False,
        related_name='+',
        db_column='action_id',
        verbose_name='Action',
    )
    python_method = fields.Char(
        null=True, blank=True,
        help_text='Python method returning an action')
    user_id = fields.Many2one(
        ResUsers,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='+',
        db_column='user_id',
        verbose_name='User',
        help_text=(
            'User specific embedded action. If empty, shared embedded action'
        ),
    )
    is_deletable = fields.Boolean(compute='_compute_is_deletable')
    default_view_mode = fields.Char(
        null=True,
        blank=True,
        verbose_name='Default View',
        help_text=(
            'Default view (if none, default view of the action is taken)'
        ),
    )
    is_visible = fields.Boolean(
        compute='_compute_is_visible',
        verbose_name='Embedded visibility',
        help_text=(
            'Computed field to check if the record should be visible '
            'according to the domain'
        ),
    )
    domain = fields.Char(
        default='[]', null=True, blank=True,
        help_text='Domain applied to the active id of the parent model')
    context = fields.Char(
        default='{}',
        null=True,
        blank=True,
        help_text=(
            'Context dictionary as Python expression, empty by default '
            '(Default: {})'
        ),
    )
    groups_ids = fields.Many2many(
        ResGroups,
        relation='ir_embedded_actions_res_groups_rel',
        column1='ir_embedded_actions_id',
        column2='res_groups_id',
        blank=True,
        related_name='+',
        help_text=(
            'Groups that can execute the embedded action. Leave empty to '
            'allow everybody.'
        ),
    )

    class Meta:
        db_table = 'ir_embedded_actions'
        ordering = ['sequence', 'id']
        verbose_name = 'Embedded Actions'
        verbose_name_plural = 'Embedded Actions'
        constraints = [
            #: ≙ ``_check_only_one_action_defined`` (``:31-37``).
            models.CheckConstraint(
                condition=(
                    models.Q(action_id__isnull=False,
                             python_method__isnull=True)
                    | models.Q(action_id__isnull=True,
                               python_method__isnull=False)
                ),
                name='ir_embedded_actions_check_only_one_action_defined',
            ),
            #: ≙ ``_check_python_method_requires_name`` (``:38-41``).
            models.CheckConstraint(
                condition=~models.Q(python_method__isnull=False,
                                    name__isnull=True),
                name='ir_embedded_actions_check_python_method_requires_name',
            ),
        ]

    @api.model_create_multi
    @classmethod
    def create(cls, vals_list):
        """≙ ``create`` (``:43-55``)."""
        # The name by default is computed based on the triggered action if a
        # action_id is defined.
        for vals in vals_list:
            if "name" not in vals:
                vals["name"] = IrActionsActions.objects.get(
                    pk=vals["action_id"]).name
            if "python_method" in vals and "action_id" in vals:
                if vals.get("python_method"):
                    # then remove the action_id since the action surely given
                    # by the python method.
                    del vals["action_id"]
                else:  # remove python_method in the vals since the vals is
                    # falsy.
                    del vals["python_method"]
        return super().create(vals_list)

    @api.depends('action_id.display_name', 'name')
    def _compute_display_name(self):
        """≙ ``_compute_display_name`` (``:57-64``). El ``.sudo()`` de la
        fuente es aquí el contexto ``sudo()`` de ``orm.environments``."""
        for record in self:
            if record.action_id:
                # User might not have access to the linked action, so we need
                # to use sudo to read the display_name.
                with sudo():
                    record.display_name = record.action_id.display_name
            else:
                record.display_name = record.name

    # The record is deletable if it hasn't been created from a xml record
    # (i.e. is not a default embedded action)
    def _compute_is_deletable(self):
        """≙ ``_compute_is_deletable`` (``:66-73``)."""
        external_ids = self._get_external_ids()
        for record in self:
            record_external_ids = external_ids[record.id]
            record.is_deletable = all(
                ex_id.startswith(("__export__", "__custom__"))
                for ex_id in record_external_ids
            )

    # Compute if the record should be visible to the user based on the domain
    # applied to the active id of the parent model and based on the groups
    # allowed to access the record.
    def _compute_is_visible(self):
        """≙ ``_compute_is_visible`` (``:75-96``)."""
        active_id = self.env.context.get("active_id", False)
        if not active_id:
            self.is_visible = False
            return
        domain_id = [("id", "=", active_id)]
        for parent_res_model, records in self.grouped(
                'parent_res_model').items():
            active_model_record = self.env[parent_res_model].search(
                domain_id, order='id')
            for record in records:
                action_groups = record.groups_ids
                is_valid_method = not record.python_method or hasattr(
                    self.env[parent_res_model], record.python_method)
                if is_valid_method and (
                        not action_groups
                        or (action_groups & self.env.user.all_group_ids)):
                    domain_model = literal_eval(record.domain or '[]')
                    record.is_visible = bool(
                        record.parent_res_id in (
                            False, None,
                            self.env.context.get('active_id', False))
                        and (record.user_id.id if record.user_id else False)
                        in (False, self.env.uid)
                        and active_model_record.filtered_domain(domain_model)
                    )
                else:
                    record.is_visible = False

    # Delete the filters linked to a embedded action.
    @api.ondelete(at_uninstall=False)
    def _unlink_if_action_deletable(self):
        """≙ ``_unlink_if_action_deletable`` (``:98-103``)."""
        for record in self:
            if not record.is_deletable:
                raise UserError(
                    _('You cannot delete a default embedded action'))

    def _get_readable_fields(self):
        """≙ ``_get_readable_fields`` (``:105-111``): *"return the list of
        fields that are safe to read"*."""
        return {
            "name", "parent_action_id", "parent_res_id", "parent_res_model",
            "action_id", "python_method", "user_id", "is_deletable",
            "default_view_mode", "filter_ids", "domain", "context",
            "groups_ids",
        }
