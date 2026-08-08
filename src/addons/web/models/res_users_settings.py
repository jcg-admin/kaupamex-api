"""``res.users.settings`` extendido por ``web`` — preferencias de acciones
embebidas.

Adaptación de ``odoo19c: addons/web/models/res_users_settings.py``
(``odoo-tools@622ddc2aa5``, 39 líneas, LGPL-3 — atribución y aviso de
licencia preservados, DEC-KX-03). Extiende ``res.users.settings`` (ya
portado en ``base/models/res_users_settings.py``) con el CRUD de las
preferencias de orden/visibilidad de acciones embebidas — el modelo que las
guarda es ``res_users_settings_embedded_action.py``, en este mismo
directorio.

Medición símbolo-por-símbolo (mismo criterio que
``porte-completo-no-parcial.md``): **1** campo
(``embedded_actions_config_ids``) + **3** métodos (``_format_settings``,
``get_embedded_actions_settings``, ``set_embedded_actions_setting``).
**4 portados, 0 ausentes.**

Divergencias de mecanismo declaradas
=====================================

- ``embedded_actions_config_ids`` (``One2many`` en la referencia) **no** se
  declara como campo aquí. En este ORM el ``One2many`` es el reverso de un
  ``ForeignKey`` — ``orm/fields_relational.py``: *"One2many es el reverso de
  un FK en Django, sin clase propia"*. Ya existe: lo aporta
  ``related_name='embedded_actions_config_ids'`` del campo ``user_setting``
  de ``ResUsersSettingsEmbeddedAction``
  (``res_users_settings_embedded_action.py``). No hay nada que colgar aquí
  con ``chain_method`` — no es un método a sobrescribir, es una relación que
  el modelo hijo ya declaró.
- ``_format_settings`` en la referencia extiende ``super()._format_settings()``.
  ``base.ResUsersSettings`` (nuestro "contenedor" — su propio docstring dice
  *"cada addon le añade sus preferencias por ``_inherit``"*) **no** define
  ``_format_settings`` todavía: ``web`` es el primer addon en instalarlo, así
  que ``chain_method`` encuentra ``previous=None`` y no hay ``super()`` que
  encadenar — el diccionario arranca en ``{}`` aquí mismo, con el mismo
  resultado que tendría un ``super()`` que devolviera ``{}`` vacío.
- ``self.ensure_one()`` (reference, ``get_embedded_actions_settings``) no se
  porta como aserción — mismo razonamiento que ``res_users.py`` en este
  directorio: una instancia Django es siempre una sola fila.
"""
from orm.method_chain import chain_method

from addons.base.models.res_users_settings import ResUsersSettings
from addons.web.models.res_users_settings_embedded_action import (
    ResUsersSettingsEmbeddedAction,
)


def _format_settings(self, fields_to_format):
    """≙ ``_format_settings`` (odoo19c: web/models/res_users_settings.py:9-14).

    Ver la sección de divergencias del docstring del módulo: arranca en
    ``{}`` porque no hay ``super()`` que encadenar todavía.
    """
    res = {}
    if 'embedded_actions_config_ids' in fields_to_format:
        res['embedded_actions_config_ids'] = (
            ResUsersSettingsEmbeddedAction._embedded_action_settings_format(
                self.embedded_actions_config_ids.all()
            )
        )
    return res


def get_embedded_actions_settings(self):
    """≙ ``get_embedded_actions_settings`` (odoo19c:
    web/models/res_users_settings.py:16-18)."""
    return ResUsersSettingsEmbeddedAction._embedded_action_settings_format(
        self.embedded_actions_config_ids.all())


def set_embedded_actions_setting(self, action_id, res_id, vals):
    """≙ ``set_embedded_actions_setting`` (odoo19c:
    web/models/res_users_settings.py:20-39).

    Busca el ajuste existente por (usuario, acción, registro): lo actualiza
    si existe, lo crea si no. ``embedded_actions_order``/
    ``embedded_actions_visibility`` llegan como lista de ids (``False``
    marca un hueco) y se serializan a CSV — el mismo formato que
    ``ResUsersSettingsEmbeddedAction._embedded_action_settings_format``
    deserializa. ``action_id=`` se filtra/crea por la FK cruda (sin cargar
    el ``IrActionsActWindow``), igual que ``action_id.id`` en la referencia
    no exige el registro completo.
    """
    embedded_actions_config = self.embedded_actions_config_ids.filter(
        action_id=action_id, res_id=res_id).first()
    new_vals = {}
    for field, value in vals.items():
        if field in ('embedded_actions_order', 'embedded_actions_visibility'):
            new_vals[field] = ','.join(
                'false' if action_id_value is False else str(action_id_value)
                for action_id_value in value
            )
        else:
            new_vals[field] = value
    if embedded_actions_config:
        for field, value in new_vals.items():
            setattr(embedded_actions_config, field, value)
        embedded_actions_config.save()
    else:
        ResUsersSettingsEmbeddedAction.objects.create(
            **new_vals,
            user_setting=self,
            action_id=action_id,
            res_id=res_id,
        )


def apply_web_extensions():
    """Cuelga las preferencias de acciones embebidas sobre
    ``base.ResUsersSettings``.

    Se invoca desde ``WebConfig.ready()`` (pendiente de sumar
    ``'addons.web.models.res_users_settings'`` a ``WebConfig._EXTENSIONES``
    — fase de consolidación del batch, ver ``apps.py``), mismo patrón que
    ``ir_http.py``/``res_partner.py``/``res_users.py``.
    """
    chain_method(ResUsersSettings, '_format_settings', _format_settings)
    chain_method(
        ResUsersSettings, 'get_embedded_actions_settings',
        get_embedded_actions_settings)
    chain_method(
        ResUsersSettings, 'set_embedded_actions_setting',
        set_embedded_actions_setting)
