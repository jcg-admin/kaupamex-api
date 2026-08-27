"""Auto-suscripción al digest por defecto de los usuarios internos (Odoo
``digest/models/res_users.py``).

≙ el ``create()`` override de la referencia: tras crear un usuario **no
compartido** (``share=False``), si ``digest.default_digest_emails`` está
activado y ``digest.default_digest_id`` apunta a un digest existente, se
suscribe automáticamente.

Por qué NO es ``post_save`` sobre ``ResUsers`` (H-API-304)
----------------------------------------------------------

La primera versión de este archivo escuchaba ``post_save(created=True)`` y
filtraba por ``instance.share``. **Nunca podía suscribir a nadie**, y el
motivo es estructural, no un descuido:

- En la referencia, ``super().create(vals_list)`` devuelve los usuarios **con
  sus grupos ya asignados** — ``group_ids`` es un campo de ``res.users``
  (``odoo19c: odoo/addons/base/models/res_users.py:257``) y viaja dentro de
  ``vals``. Tanto, que el propio ``create`` de la referencia lee
  ``user._is_internal()`` (``:583``) y ``user.share`` (``:590``) sobre lo
  recién creado.
- En Django, el M2M sólo puede escribirse **después** de que la fila tenga
  PK. En ``post_save(created=True)`` el usuario todavía no tiene ningún
  grupo, y ``share`` —definido como ``not _is_internal()``
  (``res_users.py:421-426``)— es **True para todo usuario recién creado**.
  El guard cortaba siempre.

Es decir: el mismo predicado se evalúa en dos instantes distintos porque los
dos ORM crean en distinto orden. Copiar el momento de la referencia sin
comprobar cuándo el dato existe aquí produce código que corre y no hace nada.

La corrección **no** fue mover el disparo a ``m2m_changed`` —eso habría
resuelto el síntoma cambiando la semántica: pasaría a reaccionar a *cualquier*
cambio de grupos, no a la creación—. Se replicó el orden de la referencia:
``ResUsersManager._create_user`` aplica los grupos **dentro** de la creación y
emite ``base.models.signals.res_users_created`` cuando el usuario está en el mismo
estado en que la referencia lo devuelve. Este receptor escucha ahí.
"""
from django.dispatch import receiver

from addons.base.models import SystemParameter
from addons.base.models.signals import res_users_created
from addons.digest.models.digest import DigestDigest


@receiver(res_users_created, dispatch_uid='digest_auto_subscribe_new_user')
def auto_subscribe_new_user_to_default_digest(sender, user, **kwargs):
    """≙ ``ResUsers.create()`` de la referencia.

    Los dos parámetros se leen de ``SystemParameter``
    (``ir.config_parameter`` de la referencia) — NO se porta un
    ``res_config_settings.py`` para escribirlos vía UI: no hay wizard de
    ajustes en este proyecto (mismo criterio ya aplicado en
    ``fleet_vehicle.py`` con ``fleet.delay_alert_contract``). Se fijan con
    ``SystemParameter.set_param(...)``.

    Este módulo sólo se importa desde ``DigestConfig.ready()`` (vía
    ``importlib.import_module``, excepción #4 de ``no-lazy-imports.md``).
    """
    if user.share:
        return

    if not SystemParameter.get_param('digest.default_digest_emails'):
        return
    default_digest_id = SystemParameter.get_param('digest.default_digest_id')
    if not default_digest_id:
        return
    digest = DigestDigest.objects.filter(pk=int(default_digest_id)).first()
    if digest is not None:
        digest.user_ids.add(user)
