"""El candado por tiempo estrecha la confianza del dispositivo.

Portación de ``odoo19c: auth_timeout/models/auth_totp_device.py`` (LGPL-3,
``odoo-tools@abe4040ec1``) — atribución y aviso de licencia preservados
(DEC-KX-03).

Un archivo, una clase, **un** método. Su cuerpo entero es esta pregunta: si el
usuario pertenece a un grupo cuyo candado absoluto exige segundo factor, la
confianza del dispositivo **no puede durar más** que ese candado. Sin este
estrechamiento, el dispositivo recordado dejaría pasar un candado que existe
precisamente para no dejar pasar.

Verbatim, la fuente entera::

    class AuthTotpDevice(models.Model):
        _inherit = "auth_totp.device"

        def _get_trusted_device_age(self):
            age = super()._get_trusted_device_age()
            user_lock_timeout_mfa = [
                threshold for threshold, mfa in self.env.user._get_lock_timeouts().get("lock_timeout") if mfa
            ]
            if user_lock_timeout_mfa:
                return min(age, *user_lock_timeout_mfa)
            return age

Cómo se materializa aquí — ``combine``, no relevo
==================================================

El ``_inherit`` con ``_name`` **implícito** de la fuente es una extensión: el
addon cuelga un override sobre un modelo ajeno. Aquí eso es
``extend_model(...)`` con ``chain_method``, que es el ``super()`` que este
idioma no tiene (``orm/method_chain.py``).

Pero el relevo por defecto de ``chain_method`` **no sirve** para este método:
aquel corre la nueva implementación y sólo cae en la previa si devolvió
``None``, mientras que aquí la previa se necesita **siempre** — es el ``age``
que se estrecha. La forma correcta es ``combine=``, que invoca las dos y funde
sus resultados. Es el mismo mecanismo que ``_mfa_type`` usa con
``keep_previous``, con otra función de fusión.

``combine`` es parámetro de ``chain_method``, **no** de ``extend_model``: el
bloque ``metodos=`` de aquél encadena siempre con el relevo por defecto. Por eso
el cableado va por su escotilla ``luego=``, que recibe la clase destino cuando
Django la tiene cargada y deja llamar a ``chain_method`` con la firma completa.

Divergencia declarada — ``min(age, *lista)`` frente a ``min(lista + [age])``
============================================================================

La fuente escribe ``min(age, *user_lock_timeout_mfa)`` bajo la guarda
``if user_lock_timeout_mfa``, porque ``min(x, *[])`` sería ``min(x)`` y eso
levanta ``TypeError``. Aquí la fusión recibe la lista ya calculada, así que la
guarda y el desempaquetado se colapsan en un ``min`` sobre la unión — mismo
resultado, sin el caso de borde que la guarda existe para evitar.
"""
from orm.environments import get_current_user
from orm.method_chain import chain_method
from orm.model_classes import extend_model


def _mfa_lock_timeouts(cls):
    """Los umbrales de candado **absoluto** que exigen segundo factor.

    ≙ la comprensión de lista de ``:9-11``. Devuelve una lista, posiblemente
    vacía; nunca ``None``, para que ``combine`` no la confunda con «no hay
    respuesta» (que es la semántica del relevo por defecto).

    El usuario es el de la petición en curso — ≙ ``self.env.user``. Se obtiene
    del método ya portado en ``res.users``, que es el que sabe resolver los
    grupos y su caché (``addons/authz_timeout/models/res_users.py``).
    """
    actor = get_current_user()
    if actor is None:
        return []
    timeouts = actor._get_lock_timeouts().get('lock_timeout') or []
    return [threshold for threshold, mfa in timeouts if mfa]


def _narrow_to_shortest(mfa_thresholds, age):
    """``combine`` de estrechamiento — ≙ ``min(age, *user_lock_timeout_mfa)``.

    :param mfa_thresholds: lo que devolvió :func:`_mfa_lock_timeouts`.
    :param age: lo que devolvió el ``_get_trusted_device_age`` previo.
    """
    return min([age, *mfa_thresholds])


def _chain_narrowing(model):
    """El cableado, con la firma completa de ``chain_method``.

    ``extend_model`` recibe esto como ``luego=`` y lo invoca con la clase ya
    cargada. El bloque ``metodos=`` no serviría: encadena con el relevo por
    defecto y no admite ``combine``.
    """
    chain_method(model, '_get_trusted_device_age',
                 classmethod(_mfa_lock_timeouts), combine=_narrow_to_shortest)


def apply_authz_timeout_auth_totp_device_extensions():
    """Cuelga el estrechamiento sobre ``auth_totp.device`` — ≙ ``_inherit``."""
    extend_model('authz_totp', 'AuthTotpDevice', luego=_chain_narrowing)
