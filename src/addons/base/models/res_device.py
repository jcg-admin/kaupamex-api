"""``res.device.log`` — dispositivos desde los que se abre sesión (Odoo ``base``).

Portación fiel de ``odoo19c: odoo/addons/base/models/res_device.py`` (LGPL-3)
— atribución y aviso de licencia preservados (DEC-KX-03).

**Sólo se porta el log, y es deliberado.** La referencia declara **dos**
modelos, y sólo uno es una tabla::

    res_device.py:17   _name = 'res.device.log'
    res_device.py:175  _name = 'res.device'
                       _inherit = ["res.device.log"]
                       _auto = False          ← vista SQL, no tabla

``res.device`` es una **vista** que agrupa el log por sesión (su ``_select`` lo
construye en SQL). Portarla como modelo con tabla propia duplicaría los datos y
fabricaría una capacidad que la referencia no tiene. Queda pendiente con esa
razón declarada, no por olvido: en Django el equivalente es
``Meta.managed = False`` sobre una vista creada por migración, y este árbol
todavía no arranca para generar migraciones.

**De dónde viene.** Reemplaza al ``UserSession`` que murió con el addon
``users`` (H-API-119). El modelo de la referencia es más rico que aquél
—``platform``, ``browser``, ``country``, ``city``, ``device_type``,
``revoked``— así que el port no es una mudanza: es lo que ``UserSession``
quería ser.
"""
import fields
import models

from addons.base.models.timestamped_mixin import TimeStampedModel


class ResDeviceLog(TimeStampedModel):
    """``res.device.log`` — una fila por actividad de sesión en un dispositivo.

    Fiel a ``odoo19c: odoo/addons/base/models/res_device.py:17-35``.
    """

    DEVICE_COMPUTER = 'computer'
    DEVICE_MOBILE   = 'mobile'
    DEVICE_TYPES = [
        (DEVICE_COMPUTER, 'Computadora'),
        (DEVICE_MOBILE,   'Móvil'),
    ]

    session_identifier = fields.Char(
        max_length=128, db_index=True,
        help_text='Identificador de la sesión (Odoo session_identifier).',
    )
    platform    = fields.Char(max_length=64,  blank=True, default='')
    browser     = fields.Char(max_length=64,  blank=True, default='')
    ip_address  = fields.Char(max_length=45,  blank=True, default='',
                              help_text='IPv4 o IPv6 (Odoo ip_address).')
    country     = fields.Char(max_length=64,  blank=True, default='')
    city        = fields.Char(max_length=120, blank=True, default='')
    device_type = fields.Selection(
        max_length=16, choices=DEVICE_TYPES, null=True, blank=True,
        help_text='Tipo de dispositivo (Odoo device_type).',
    )
    user        = fields.Many2one(
        'base.ResUsers', on_delete=models.CASCADE, db_index=True,
        related_name='device_logs',
        help_text='Usuario de la sesión (Odoo user_id).',
    )
    first_activity = fields.Datetime(null=True, blank=True)
    last_activity  = fields.Datetime(null=True, blank=True, db_index=True)
    revoked        = fields.Boolean(
        default=False,
        help_text='Sesión revocada desde el panel de dispositivos (Odoo revoked).',
    )

    class Meta:
        db_table            = 'res_device_log'
        ordering            = ['-last_activity']
        verbose_name        = 'Registro de dispositivo'
        verbose_name_plural = 'Registros de dispositivo'

    def __str__(self) -> str:
        return f'{self.browser or "?"} / {self.platform or "?"} ({self.user_id})'
