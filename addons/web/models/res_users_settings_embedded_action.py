"""``res.users.settings.embedded.action`` — preferencia por usuario de orden y
visibilidad de las acciones embebidas de una vista (Odoo ``web``).

Adaptación de ``odoo19c:
addons/web/models/res_users_settings_embedded_action.py``
(``odoo-tools@622ddc2aa5``, 66 líneas, LGPL-3 — atribución y aviso de
licencia preservados, DEC-KX-03).

Modelo **nuevo** (``_name``, no ``_inherit``): el nodo ``class:`` de la
referencia sí cuenta como símbolo a portar (``porte-completo-no-parcial.md``,
H-API-379) — se declara una clase Django real, no funciones colgadas por
``chain_method`` sobre un modelo ajeno (ese idioma es para ``_inherit``, ver
``res_users.py`` y ``res_users_settings.py`` en este mismo directorio).

Distinto de ``ir.embedded.actions`` (``base/models/ir_embedded_actions.py``,
H-API-142): aquél es la **configuración** de qué acciones embebidas existen
en la vista de un modelo (admin, compartida o de un usuario concreto vía su
propio ``user``); éste es la **preferencia visual por usuario** de las que ya
existen — en qué orden y con qué visibilidad las ve, referenciando
directamente ``ir.actions.act_window`` (no ``ir.embedded.actions``). Son dos
capas de la referencia y no se funden en una.

Medición símbolo-por-símbolo (``re.findall(r'^\\s{4}def (\\w+)', ref)`` + el
nodo ``class:``, mismo criterio que ``porte-completo-no-parcial.md``): **1**
clase + **4** métodos (``_check_embedded_actions_order``,
``_check_embedded_actions_visibility``, ``_check_embedded_actions_field_format``,
``_embedded_action_settings_format``). **5 portados, 0 ausentes.**

Divergencias de mecanismo declaradas
=====================================

- ``@api.constrains`` no dispara solo — a diferencia de Odoo, Django no
  vuelve a validar en cada ``save()``. Los dos chequeos de esta clase
  (``embedded_actions_order``, ``embedded_actions_visibility``) son sobre
  campos **propios escalares** (``Char``), así que caben en ``clean()`` sin
  el problema de "PK todavía no existe" que sí bloquea a un constrains sobre
  una relación (contraste: ``product/models/product_combo.py``, que declara
  ``check_has_items()`` aparte por esa razón). Se decoran con
  ``@api.constrains`` (documental, igual que
  ``account/models/account_move.py::_check_balanced``) y se invocan desde
  ``clean()``.
- ``index='btree_not_null'`` (Odoo: índice parcial que excluye los NULL) no
  se porta — ``user_setting`` es requerido aquí (sin ``null=True``), así que
  no hay NULL que excluir: el índice normal del ``ForeignKey`` (automático en
  Django, y explícito con ``db_index=True`` por consistencia con
  ``ir_embedded_actions.py``) cubre el mismo caso de uso.
- ``export_string_translation=False`` (Odoo: opt-out del exportador de
  cadenas a traducir) no tiene equivalente en este árbol — es metadata del
  exportador de traducciones de Odoo; se omite sin efecto funcional.
- ``_embedded_action_settings_format`` en la referencia opera sobre un
  **recordset** (potencialmente varias filas). Aquí no hay recordset: se
  declara ``staticmethod`` que recibe el **queryset**/iterable explícito de
  ajustes — el llamador
  (``res_users_settings.py::get_embedded_actions_settings``) pasa
  ``self.embedded_actions_config_ids.all()``. La clave del diccionario usa
  ``setting.action_id`` (el entero crudo de la FK que Django expone sin
  golpear la base), que es exactamente el mismo valor que
  ``setting.action_id.id`` calcula en la referencia con una consulta extra.
"""
import api
from django.core.exceptions import ValidationError
import fields
import models

from addons.base.models.ir_actions import IrActionsActWindow
from addons.base.models.res_users_settings import ResUsersSettings
from tools.translate import _


class ResUsersSettingsEmbeddedAction(models.Model):
    """Orden y visibilidad, por usuario, de una acción embebida.

    Fiel a ``odoo19c:
    web/models/res_users_settings_embedded_action.py:5-20``.
    """

    user_setting = fields.Many2one(
        ResUsersSettings, on_delete=models.CASCADE, db_index=True,
        related_name='embedded_actions_config_ids',
        verbose_name='Preferencias del usuario',
        help_text=(
            'Preferencias del usuario dueño de este ajuste (Odoo '
            'user_setting_id, requerido, ondelete=cascade).'
        ),
    )
    action = fields.Many2one(
        IrActionsActWindow, on_delete=models.CASCADE, db_index=True,
        related_name='embedded_user_settings', verbose_name='Acción',
        help_text=(
            'Acción embebida a la que aplica el ajuste (Odoo action_id, '
            'requerido, ondelete=cascade).'
        ),
    )
    res_model = fields.Char(
        max_length=120, verbose_name='Modelo del registro',
        help_text='Modelo donde se embebe la acción (Odoo res_model, '
                  'requerido).',
    )
    res_id = fields.Integer(
        default=0, verbose_name='ID del registro',
        help_text='ID del registro donde se embebe; 0 = ningún registro '
                  'particular (Odoo res_id).',
    )
    embedded_actions_order = fields.Char(
        max_length=255, blank=True, default='',
        verbose_name='Orden de las acciones embebidas',
        help_text='IDs separados por coma, en el orden elegido por el '
                  'usuario; "false" marca un hueco (Odoo '
                  'embedded_actions_order).',
    )
    embedded_actions_visibility = fields.Char(
        max_length=255, blank=True, default='',
        verbose_name='Visibilidad de las acciones embebidas',
        help_text='IDs separados por coma de las acciones visibles (Odoo '
                  'embedded_actions_visibility).',
    )
    embedded_visibility = fields.Boolean(
        default=False, verbose_name='Barra superior visible',
        help_text='Si la barra superior de acciones embebidas está visible '
                  '(Odoo embedded_visibility).',
    )

    class Meta:
        db_table            = 'res_users_settings_embedded_action'
        verbose_name        = 'Ajuste de acción embebida por usuario'
        verbose_name_plural = 'Ajustes de acciones embebidas por usuario'
        # ≙ ``_res_user_settings_embedded_action_unique`` de la referencia
        # (``UNIQUE (user_setting_id, action_id, res_id)``): un usuario no
        # puede tener dos ajustes para la misma acción en el mismo registro.
        constraints = [
            models.UniqueConstraint(
                fields=['user_setting', 'action', 'res_id'],
                name='res_users_settings_embedded_action_unique',
            ),
        ]

    def __str__(self) -> str:
        return f'ajuste embebido {self.action_id} de {self.user_setting_id}'

    def clean(self):
        super().clean()
        self._check_embedded_actions_order()
        self._check_embedded_actions_visibility()

    @api.constrains('embedded_actions_order')
    def _check_embedded_actions_order(self):
        """≙ ``_check_embedded_actions_order`` (odoo19c:
        res_users_settings_embedded_action.py:22-24)."""
        self._check_embedded_actions_field_format('embedded_actions_order')

    @api.constrains('embedded_actions_visibility')
    def _check_embedded_actions_visibility(self):
        """≙ ``_check_embedded_actions_visibility`` (odoo19c:
        res_users_settings_embedded_action.py:26-28)."""
        self._check_embedded_actions_field_format(
            'embedded_actions_visibility')

    def _check_embedded_actions_field_format(self, field_name):
        """≙ ``_check_embedded_actions_field_format`` (odoo19c:
        res_users_settings_embedded_action.py:30-52).

        Sin ids repetidos, y cada id es un entero o el literal ``"false"``
        (un hueco en la lista). Divergencia: la referencia itera
        ``for setting in self`` (recordset); aquí ``self`` es siempre una
        sola fila (instancia Django), así que el bucle se colapsa a una
        sola verificación.
        """
        value = getattr(self, field_name)
        if not value:
            return
        action_ids = value.split(',')
        if len(action_ids) != len(set(action_ids)):
            raise ValidationError(
                _('Los ids en %(field_name)s no deben repetirse: '
                  '«%(action_ids)s».') % {
                    'field_name': field_name, 'action_ids': action_ids,
                }
            )
        for action_id in action_ids:
            if not (action_id.isdigit() or action_id == 'false'):
                raise ValidationError(
                    _('Los ids en %(field_name)s sólo admiten enteros o '
                      '"false": «%(action_ids)s».') % {
                        'field_name': field_name, 'action_ids': action_ids,
                    }
                )

    @staticmethod
    def _embedded_action_settings_format(queryset):
        """≙ ``_embedded_action_settings_format`` (odoo19c:
        res_users_settings_embedded_action.py:54-66).

        Recibe el queryset de ajustes de un usuario (ver la sección de
        divergencias del docstring del módulo) y devuelve el mismo mapeo
        ``"{action_id}+{res_id}" -> {...}`` que la referencia.
        """
        return {
            f'{setting.action_id}+{setting.res_id or ""}': {
                'embedded_actions_order': [
                    False if action_id == 'false' else int(action_id)
                    for action_id in setting.embedded_actions_order.split(',')
                ] if setting.embedded_actions_order else [],
                'embedded_actions_visibility': [
                    False if action_id == 'false' else int(action_id)
                    for action_id in
                    setting.embedded_actions_visibility.split(',')
                ] if setting.embedded_actions_visibility else [],
                'embedded_visibility': setting.embedded_visibility,
            }
            for setting in queryset
        }
