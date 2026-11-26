"""``res.users.deletion`` — solicitud de baja de cuenta (Odoo ``base``).

Portación fiel de ``odoo19c: odoo/addons/base/models/res_users_deletion.py``
(LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

**La decisión que hay que copiar, y que se pierde si se porta por nombre.** La
referencia guarda el usuario **dos veces**::

    user_id     = fields.Many2one('res.users', ondelete='set null')
    user_id_int = fields.Integer(compute='_compute_user_id_int', store=True)
    # Integer field because the related user might be deleted from the database

La FK se pone a ``NULL`` cuando el usuario desaparece, pero el entero
almacenado sobrevive. Es lo contrario de ``res.users.settings``, que
**cascadea**
con el usuario: una solicitud de baja tiene que seguir existiendo después de
ejecutarse, porque es el registro de que se ejecutó.

**De dónde viene.** Reemplaza al ``UserDeactivationEvent`` que murió con el
addon ``users`` (H-API-119). Aquél tenía FK simple y **no** conservaba nada
tras
el borrado — la propiedad de arriba es lo que el port aporta.
"""

import logging

import api
import fields
import models
from django.apps import apps
from django.db import transaction

from addons.base.models.timestamped_mixin import TimeStampedModel

_logger = logging.getLogger(__name__)


class ResUsersDeletion(models.BaseModel, TimeStampedModel):
    """``res.users.deletion`` — petición de borrado de una cuenta.

    Fiel a ``odoo19c: odoo/addons/base/models/res_users_deletion.py:11-100``.
    El campo se llama ``user`` (columna ``user_id``), así que ``_rec_name``
    lo nombra por el campo.
    """

    _name = 'res.users.deletion'
    _description = 'Users Deletion Request'
    _rec_name = 'user'

    STATE_TODO = 'todo'
    STATE_DONE = 'done'
    STATE_FAIL = 'fail'
    STATES = [
        (STATE_TODO, 'Pendiente'),
        (STATE_DONE, 'Ejecutada'),
        (STATE_FAIL, 'Fallida'),
    ]

    user = fields.Many2one(
        'base.ResUsers',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deletion_requests',
        help_text='Usuario a dar de baja (Odoo user_id, ondelete=set null).',
    )
    user_int = fields.Integer(
        db_index=True,
        help_text=(
            'Copia del id del usuario (Odoo user_id_int). Sobrevive al borrado'
            ' de la fila de usuario: sin ella la solicitud ejecutada quedaría'
            ' sin sujeto.'
        ),
    )
    state = fields.Selection(
        max_length=8,
        choices=STATES,
        default=STATE_TODO,
        db_index=True,
        help_text='Estado de la solicitud (Odoo state).',
    )

    class Meta:
        db_table = 'res_users_deletion'
        ordering = ['-id']
        verbose_name = 'Solicitud de baja'
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

    @api.model
    def _gc_portal_users(self, batch_size=50):
        """Remove the portal users that asked to deactivate their account.

        ≙ ``_gc_portal_users`` (``odoo19c: res_users_deletion.py:36-100``),
        el cron ``ir_cron_res_users_deletion``. Las solicitudes sin usuario
        pasan a ``done``; de las demás, hasta ``batch_size``, cada una borra
        su usuario y después intenta borrar su partner.

        El ``self.env.cr.rollback()`` de la fuente tras un borrado fallido es
        aquí un ``savepoint`` alrededor de cada borrado: Django prohíbe el
        ``rollback`` de la transacción dentro de un ``atomic``, y el
        ``savepoint`` deshace lo mismo —el intento fallido— sin tocar lo ya
        hecho. El ``unlink`` de usuario y partner es su ``delete()``.
        """
        delete_requests = self.search([('state', '=', self.STATE_TODO)])

        # filter the requests related to a deleted user
        done_requests = delete_requests.filtered(
            lambda request: not request.user_id)
        done_requests.write({'state': self.STATE_DONE})

        pending_requests = delete_requests - done_requests
        commit_progress = apps.get_model('base', 'IrCron')._commit_progress
        commit_progress(len(done_requests), remaining=len(pending_requests))

        for delete_request in pending_requests[:batch_size]:
            delete_request = delete_request.try_lock_for_update().filtered(
                lambda d: d.state == self.STATE_TODO)
            if not delete_request:
                continue
            user = delete_request.user
            user_id = user.pk
            user_name = user.name
            partner = user.partner
            requester_name = (
                delete_request.create_uid.name
                if delete_request.create_uid else ''
            )

            # Step 1: Delete User
            try:
                with transaction.atomic():
                    user.delete()
                # ``ondelete='set null'`` vació la columna; el caché de la
                # fuente se invalida al borrar, aquí se relee la solicitud.
                delete_request = self.browse(delete_request.ids)
                _logger.info(
                    "User #%i %r, deleted. Original request from %r.",
                    user_id, user_name, requester_name)
                delete_request.write({'state': self.STATE_DONE})
                commit_progress(1)
            except Exception as e:
                _logger.error(
                    "User #%i %r could not be deleted. Original request "
                    "from %r. Related error: %s",
                    user_id, user_name, requester_name, e)
                delete_request.write({'state': self.STATE_FAIL})
                # commit and progress even when failed
                if commit_progress(1):
                    continue
                else:
                    break

            # Step 2: Delete Linked Partner
            #         Could be impossible if the partner is linked to a SO for
            #         example
            partner_id = partner.pk
            try:
                with transaction.atomic():
                    partner.delete()
                _logger.info(
                    "Partner #%i %r, deleted. Original request from %r.",
                    partner_id, user_name, requester_name)
                if not commit_progress():
                    break
            except Exception as e:
                _logger.warning(
                    "Partner #%i %r could not be deleted. Original request "
                    "from %r. Related error: %s",
                    partner_id, user_name, requester_name, e)
                if not commit_progress():  # just check if we should stop
                    break
