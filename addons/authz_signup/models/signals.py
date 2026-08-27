"""Cancelación del signup pendiente cuando el usuario deja de poder usarlo.

≙ los dos ganchos de escritura de ``auth_signup/models/res_users.py``
(``odoo19c:``, LGPL-3) que la fuente cuelga de ``res.users`` por ``_inherit``:

- ``write`` (``:282-285``) — al desactivar un usuario, cancela el signup
  pendiente de su partner.
- ``_ondelete_signup_cancel`` (``:287-292``) — al borrarlo, lo mismo.

Aquí Django no permite ``_inherit``, así que son **señales** sobre el modelo
de usuario — el mismo idioma que ``authz_totp_mail/models/signals.py``. La
fuente los declara como dos métodos porque su ORM separa escritura de borrado;
el evento que importa es el mismo, y por eso los dos cuerpos son idénticos.

**Por qué esto no es cosmético.** Un ``SignupRequest`` vivo es un permiso: dice
que ese partner tiene una alta o un reset en curso. Dejarlo tras desactivar al
usuario deja el permiso en pie después de haber retirado a quien lo iba a usar.
El token en sí caduca por otra vía —``_get_partner_from_token`` compara el
conjunto de usuarios del partner, que al borrar cambia— pero esa es la
**segunda** línea, y su cobertura depende de que el cambio de estado se note.
La fuente cancela explícitamente; aquí también.
"""
import logging

from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from addons.authz_signup.models.res_partner import signup_cancel
from addons.base.models.res_users import ResUsers

_logger = logging.getLogger(__name__)


def _cancel_for(user, motivo):
    """Cancela el signup pendiente del partner del usuario, si lo hay."""
    partner = user.partner if user.partner_id else None
    if partner is None:
        return
    if signup_cancel(partner):
        _logger.info('Signup pendiente cancelado para el partner #%s (%s)',
                     partner.pk, motivo)


@receiver(pre_save, sender=ResUsers, dispatch_uid='authz_signup_deactivation')
def cancel_signup_on_deactivation(sender, instance, **kwargs):
    """≙ ``write`` (``:282-285``) — la transición ``active`` True→False.

    La fuente mira ``'active' in vals and not vals['active']``, que es *"la
    escritura pone active en falso"*. Aquí el equivalente es la **transición**:
    sin leer el valor previo, un ``save()`` cualquiera sobre un usuario ya
    inactivo volvería a cancelar, y peor, uno que nunca tocó ``active``
    también. Por eso se consulta la fila guardada.
    """
    if instance.pk is None or instance.active:
        return
    era_activo = sender.objects.filter(pk=instance.pk, active=True).exists()
    if era_activo:
        _cancel_for(instance, 'desactivado')


@receiver(post_delete, sender=ResUsers, dispatch_uid='authz_signup_deletion')
def cancel_signup_on_deletion(sender, instance, **kwargs):
    """≙ ``_ondelete_signup_cancel`` (``:287-292``).

    ``post_delete`` y no ``pre_delete`` porque la fuente cancela **al**
    borrar. Y sólo por eso: medido, las dos señales dan el mismo resultado
    ante un rollback —viajan en la misma transacción, así que se revierten
    juntas—, de modo que la suite no las distingue. No es como el aviso de
    dispositivo de ``authz_totp_mail``, que sí necesita ``on_commit`` porque
    su efecto (un correo) **no** es transaccional.
    """
    _cancel_for(instance, 'borrado')
