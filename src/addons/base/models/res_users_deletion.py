"""``res.users.deletion`` — solicitud de baja de cuenta (Odoo ``base``).

Portación fiel de ``odoo19c: odoo/addons/base/models/res_users_deletion.py``
(LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

**La decisión que hay que copiar, y que se pierde si se porta por nombre.** La
referencia guarda el usuario **dos veces**::

    user_id     = fields.Many2one('res.users', ondelete='set null')
    user_id_int = fields.Integer(compute='_compute_user_id_int', store=True)
    # Integer field because the related user might be deleted from the database

La FK se pone a ``NULL`` cuando el usuario desaparece, pero el entero
almacenado sobrevive. Es lo contrario de ``res.users.settings``, que **cascadea**
con el usuario: una solicitud de baja tiene que seguir existiendo después de
ejecutarse, porque es el registro de que se ejecutó.

**De dónde viene.** Reemplaza al ``UserDeactivationEvent`` que murió con el
addon ``users`` (H-API-119). Aquél tenía FK simple y **no** conservaba nada tras
el borrado — la propiedad de arriba es lo que el port aporta.
"""
import fields
import models

from addons.base.models.mixins import TimeStampedModel


class ResUsersDeletion(TimeStampedModel):
    """``res.users.deletion`` — petición de borrado de una cuenta.

    Fiel a ``odoo19c: odoo/addons/base/models/res_users_deletion.py``.
    """

    STATE_TODO = 'todo'
    STATE_DONE = 'done'
    STATE_FAIL = 'fail'
    STATES = [
        (STATE_TODO, 'Pendiente'),
        (STATE_DONE, 'Ejecutada'),
        (STATE_FAIL, 'Fallida'),
    ]

    user     = fields.Many2one(
        'base.ResUsers', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='deletion_requests',
        help_text='Usuario a dar de baja (Odoo user_id, ondelete=set null).',
    )
    user_int = fields.Integer(
        db_index=True,
        help_text=(
            'Copia del id del usuario (Odoo user_id_int). Sobrevive al borrado '
            'de la fila de usuario: sin ella la solicitud ejecutada quedaría '
            'sin sujeto.'
        ),
    )
    state    = fields.Selection(
        max_length=8, choices=STATES, default=STATE_TODO, db_index=True,
        help_text='Estado de la solicitud (Odoo state).',
    )

    class Meta:
        db_table            = 'res_users_deletion'
        ordering            = ['-id']
        verbose_name        = 'Solicitud de baja'
        verbose_name_plural = 'Solicitudes de baja'

    def __str__(self) -> str:
        return f'baja #{self.pk} usuario {self.user_int} ({self.state})'

    def save(self, *args, **kwargs):
        """Materializa ``user_int`` desde la FK mientras ésta exista.

        En la referencia es un campo ``compute`` con ``store=True``; Django no
        tiene computados almacenados, así que el valor se fija al guardar. El
        efecto es el mismo: cuando la FK pase a ``NULL``, el entero ya está
        escrito.
        """
        if self.user_id and not self.user_int:
            self.user_int = self.user_id
        super().save(*args, **kwargs)
