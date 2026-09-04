"""Notificaciones de seguridad al activar/desactivar 2FA.

≙ el ``write`` hook de ``auth_totp_mail/models/res_users.py:21-37``: cuando
``totp_secret`` se llena → "2FA Activated"; cuando se vacía → "2FA
Deactivated". Aquí el evento equivalente es la transición de
``TotpSecret.confirmed`` (activación) y el borrado de una fila confirmada
(desactivación) — señales Django en lugar de ``_inherit``.

El correo va directo por ``dispatch_email`` (texto fiel al de la
referencia); el template QWeb ``mail.account_security_alert`` con su
``suggest_2fa`` pertenece a la capa de presentación de Odoo y no se porta.
"""
import logging
from collections import defaultdict

from django.db import transaction
from django.db.models.signals import post_delete, pre_delete, pre_save
from django.dispatch import receiver

from addons.authz_totp.models import TotpSecret
from addons.authz_totp.models.auth_totp import AuthTotpDevice
from addons.mail.models.email_executor import dispatch_email

_logger = logging.getLogger(__name__)

#: Atributo donde cuelga el lote de dispositivos retirados de la transaccion
#: en curso. Vive en la **conexion**, no en un ``threading.local``, y por una
#: razon medida: ver ``_batch_of_the_transaction``.
_ATTR_BATCH = '_authz_totp_mail_dispositivos_retirados'


def _notify(user, subject, content):
    if not user.login:
        return
    dispatch_email(subject, content, None, [user.login])


@receiver(pre_save, sender=TotpSecret,
          dispatch_uid='authz_totp_mail_activation')
def notify_totp_activated(sender, instance, **kwargs):
    """Transición ``confirmed`` False→True = 2FA activado."""
    if not instance.confirmed:
        return
    was_confirmed = (
        instance.pk is not None
        and sender.objects.filter(pk=instance.pk, confirmed=True).exists()
    )
    if not was_confirmed:
        _notify(
            instance.user,
            'Security Update: 2FA Activated',
            'Two-factor authentication has been activated on your account',
        )


@receiver(post_delete, sender=TotpSecret,
          dispatch_uid='authz_totp_mail_deactivation')
def notify_totp_deactivated(sender, instance, **kwargs):
    """Borrado de un secreto confirmado = 2FA desactivado."""
    if instance.confirmed:
        _notify(
            instance.user,
            'Security Update: 2FA Deactivated',
            'Two-factor authentication has been deactivated on your account',
        )


# ---------------------------------------------------------------------------
# ≙ ``auth_totp_mail/models/auth_totp_device.py`` — el aviso al retirar un
# dispositivo de confianza.
#
# **La premisa que decía que esto no se podía portar era falsa.** El
# ``models/__init__.py`` de este addon declaraba ``auth_totp_device.py → SIN
# archivo: extiende `auth_totp.device`, modelo NO portado``. Medido
# 2026-08-27: ``AuthTotpDevice`` existe desde
# ``addons/authz_totp/models/auth_totp.py:121``. La nota fue cierta al
# escribirse y dejó de serlo cuando el addon hermano portó el modelo, sin que
# ningún archivo de éste cambiara — la misma forma que H-API-823 y H-API-827.
#
# La referencia declara DOS símbolos y los dos se portan: ``unlink`` (avisa) y
# ``_classify_by_user`` (agrupa). El agrupamiento **no es cosmético**: revocar
# los tres dispositivos de un usuario manda UN correo con los tres nombres, no
# tres correos. ``revoke_all_devices`` borra por *queryset*, así que sin
# agrupar el titular recibiría tantos avisos como dispositivos tuviera.
#
# **Divergencia declarada — cuándo sale el correo.** La fuente notifica
# *dentro* de ``unlink``, antes del commit: si la transacción revierte, el
# aviso ya salió y el dispositivo sigue ahí. Aquí el envío se difiere a
# ``transaction.on_commit``, así que sólo se avisa de un retiro que de verdad
# ocurrió. Es una divergencia a favor, y por eso se declara en vez de callarse.
# ---------------------------------------------------------------------------


def _classify_by_user(instances):
    """≙ ``_classify_by_user`` (``auth_totp_device.py:26-31``).

    Agrupa dispositivos por su dueño. La fuente acumula recordsets con ``|=``
    sobre un ``defaultdict``; aquí acumula el **nombre** de cada uno, que es lo
    único que su ``unlink`` consume (``', '.join(device.name …)``): guardar la
    instancia no aportaría nada y la fila ya no existirá al despachar.
    """
    by_user = defaultdict(list)
    for device in instances:
        by_user[device.user_id].append(device.name or '')
    return by_user


def _flush_still_registered(conn):
    """¿Sigue en pie el ``on_commit`` que registramos para esta conexión?

    Django **descarta** las llamadas de ``on_commit`` de un bloque que revierte
    —las filtra por ``savepoint_ids`` en
    ``django/db/backends/base/base.py:416-418``, leído en el paquete
    instalado—, pero no toca ningún estado nuestro. Sin esta prueba de vida el
    lote sobrevive al rollback y **envenena la transacción siguiente**: la
    próxima retirada real ve un lote no vacío, no registra su propio
    ``on_commit``, y el aviso de seguridad **no sale**. Medido: el caso del
    rollback seguido del caso de una retirada normal deja al titular sin correo
    (:ref:`h-api-830`).

    La forma de cada entrada es ``(set(savepoint_ids), func, robust)``
    (``:732``), así que basta comparar la función.
    """
    return any(func is _flush_removed_devices
               for _sids, func, _robust in conn.run_on_commit)


def _batch_of_the_transaction():
    """El acumulador de esta transacción, creándolo si hace falta.

    Cuelga de la **conexión** y no de un ``threading.local`` porque lo que hay
    que acotar es la transacción, no el hilo: un hilo atiende muchas
    transacciones seguidas y el lote de una no puede alcanzar a la siguiente.
    """
    conn = transaction.get_connection()
    batch = getattr(conn, _ATTR_BATCH, None)
    if batch is None or not _flush_still_registered(conn):
        # O no hay lote, o el que hay quedó huérfano al revertir su bloque.
        batch = defaultdict(list)
        setattr(conn, _ATTR_BATCH, batch)
        transaction.on_commit(_flush_removed_devices)
    return batch


def _flush_removed_devices():
    """Despacha un aviso por usuario, con todos sus dispositivos retirados.

    Corre en ``on_commit``: la fila ya no existe, así que el usuario se
    resuelve por su ``pk``. Si el usuario mismo se borró —y la cascada arrastró
    sus dispositivos— no hay a quién avisar y el lote se descarta en silencio,
    que es el desenlace correcto y no un fallo.
    """
    conn = transaction.get_connection()
    pending = getattr(conn, _ATTR_BATCH, None)
    setattr(conn, _ATTR_BATCH, None)
    if not pending:
        return
    UserModel = TotpSecret._meta.get_field('user').related_model
    for uid, names in pending.items():
        user = UserModel.objects.filter(pk=uid).first()
        if user is None:
            continue
        _notify(
            user,
            'Security Update: Device Removed',
            'A trusted device has just been removed from your account: %s'
            % ', '.join(n for n in names if n),
        )


@receiver(pre_delete, sender=AuthTotpDevice,
          dispatch_uid='authz_totp_mail_device_removed')
def notify_device_removed(sender, instance, **kwargs):
    """≙ ``unlink`` (``auth_totp_device.py:12-23``) — recoge, no despacha.

    ``pre_delete`` es el único momento en que la fila todavía tiene su
    ``name``; el despacho se difiere a ``on_commit`` para poder agrupar y para
    no avisar de un borrado que revierta.
    """
    batch = _batch_of_the_transaction()
    for uid, names in _classify_by_user([instance]).items():
        batch[uid].extend(names)
