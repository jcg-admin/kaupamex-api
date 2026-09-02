"""``res.users`` extendido por ``base_setup`` — el alta de usuarios por correo.

Adaptación de ``odoo19c: addons/base_setup/models/res_users.py``
(``odoo-tools@622ddc2a``, LGPL-3 — atribución y aviso de licencia preservados,
DEC-KX-03; mecanismo: **copia + adaptación**).

Los 2 símbolos de la fuente están portados: la clase —como instalación sobre
``base.ResUsers``— y su ``web_create_users``.

Cómo se instala, y por qué no es una subclase
=============================================

``res.users`` es aquí un modelo **concreto** de ``base``, no un abstracto, así
que el ``_inherit`` de la fuente no se puede modelar heredando: eso crearía una
tabla nueva. La forma del árbol para colgar sobre un modelo ajeno es
``extend_model`` desde el ``ready()`` del addon (``orm/model_classes.py``), y
es la que se usa aquí. ``check_porte_completo`` la reconoce: el destino se
nombra con un literal y de él deriva la clase ``ResUsers``.

Divergencias declaradas
=======================

- **``self._fields``** de la fuente ≙ los nombres de ``cls._meta.get_fields()``.
  Es el mismo predicado —¿el modelo declara este campo?— sobre el registro de
  campos del ORM anfitrión.
- **``with_context(active_test=False)``** no tiene receptor: el gestor de
  ``res.users`` de este árbol **no** filtra por ``active``, así que la consulta
  ya ve a los desactivados y la clave no cambiaría nada. Se omite la llamada y
  se declara aquí, en vez de fabricar un contexto que nadie lee.
- **``with_context(signup_valid=True)``** sí se pasa —con
  ``orm.environments.context_scope``, el ``with_context`` de este árbol—
  aunque hoy ningún ``create`` lo lea: la clave es del addon de registro
  (``authz_signup``) y quitarla dejaría el alta sin la marca que la fuente le
  pone. Medido: ``grep -rn "signup_valid" src/ addons/`` → 0 lectores; el
  sucesor es el porte de ``auth_signup.res_users``, tarea **#455**.
- **El alta reparte en dos filas.** La fuente crea el usuario con
  ``{'login', 'name', 'email', 'active'}`` y su ``_inherits`` deriva ``name`` y
  ``email`` al partner. Aquí ``ResUsers.name`` es una propiedad que delega en
  ``partner`` (``orm/inherits.py``) y el ``create`` de Django no acepta
  delegados, así que el partner se crea primero y el usuario apunta a él — que
  es exactamente lo que el ``_inherits`` hace por dentro.
"""
from django.db.models import Q

from addons.base.models.res_partner import ResPartner
from addons.base.models.res_users import ResUsers
from exceptions import UserError
from orm.environments import context_scope
from orm.model_classes import extend_model
from tools.mail import parse_contact_from_email

#: ≙ el mensaje de la fuente (``odoo19c: res_users.py:17``), verbatim.
DISCUSS_REQUIRED_MESSAGE = (
    'You have to install the Discuss application to use this feature.')

#: El campo que la fuente exige para poder buscar por correo normalizado. Lo
#: aporta Discuss (``mail``); mientras no exista, ``web_create_users`` levanta.
EMAIL_NORMALIZED_FIELD = 'email_normalized'


def web_create_users(cls, emails):
    """≙ ``web_create_users`` (``odoo19c: base_setup/models/res_users.py:12-37``).

    Reactiva a quien ya existía desactivado y crea a los demás. ``@api.model``
    de la fuente ≙ ``classmethod``: opera sobre el modelo, no sobre un registro.

    **La guarda de la fuente es load-bearing aquí, no decorativa.** Medido:
    ``grep -rn "email_normalized" src/ addons/ --include=*.py`` no devuelve
    ningún **campo** con ese nombre —sólo variables locales de
    ``res_partner.py``—, así que hoy este método levanta ``UserError`` con el
    mensaje de la fuente, que es su conducta cuando Discuss no está instalado.
    El resto del cuerpo se porta igual: la guarda es una condición de entorno,
    no una razón para no escribirlo.
    """
    emails_normalized = [parse_contact_from_email(email)[1]
                         for email in emails]

    if EMAIL_NORMALIZED_FIELD not in {f.name for f in cls._meta.get_fields()}:
        raise UserError(DISCUSS_REQUIRED_MESSAGE)

    # Reactivate already existing users if needed
    deactivated_users = list(cls.objects.filter(
        Q(active=False)
        & (Q(login__in=list(emails) + emails_normalized)
           | Q(**{f'{EMAIL_NORMALIZED_FIELD}__in': emails_normalized}))))
    for user in deactivated_users:
        user.active = True
        user.save(update_fields=['active'])
    done = [getattr(user, EMAIL_NORMALIZED_FIELD) for user in deactivated_users]

    new_emails = set(emails) - {user.email for user in deactivated_users}

    # Process new email addresses : create new users
    for email in new_emails:
        name, email_normalized = parse_contact_from_email(email)
        if email_normalized in done:
            continue
        with context_scope(signup_valid=True):
            partner = ResPartner.objects.create(
                name=name or email_normalized, email=email_normalized)
            cls.objects.create(
                login=email_normalized, partner=partner, active=True)

    return True


def apply_base_setup_extensions():
    """Cuelga ``web_create_users`` sobre ``base.ResUsers``.

    La llama ``BaseSetupConfig.ready()``, no el import del módulo: en tiempo de
    import el registro de modelos aún no está poblado y colgar sobre un modelo
    ajeno fallaría con ``AppRegistryNotReady``.

    Va por ``metodos=`` —no ``overrides=``— porque el símbolo es **nuevo**
    sobre ``res.users``: ``wrap_method`` exige que el anterior exista y aquí no
    hay ninguno que envolver.
    """
    extend_model('res.users', metodos={
        'web_create_users': classmethod(web_create_users),
    })
