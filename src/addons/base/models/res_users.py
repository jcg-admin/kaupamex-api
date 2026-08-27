"""``res.users`` — la credencial de acceso (Odoo ``base``).

Portación fiel de ``odoo19c: odoo/addons/base/models/res_users.py`` (LGPL-3)
— atribución y aviso de licencia preservados (DEC-KX-03).

**La decisión que estructura este archivo** es la línea 165 de la referencia::

    _inherits = {'res.partner': 'partner_id'}

``res.users`` **no es la persona**. Es la credencial, y delega quién eres a un
``res.partner`` requerido. Por eso ``name``/``email``/``phone`` figuran en
``res.users`` como campos ``related`` (``:252-255``): se leen del partner, no
se guardan dos veces. Un empleado que deja de tener login sigue existiendo como
partner; un cliente sin cuenta nunca necesita uno.

**Django sí tiene un mecanismo parecido, y no se usa.** La herencia multi-tabla
(MTI) hace mecánicamente casi lo mismo: al heredar de un modelo concreto,
``ModelBase`` inyecta un enlace oculto —``base.py:301-307``,
``OneToOneField(base, on_delete=CASCADE, auto_created=True, parent_link=True)``
llamado ``<modelo>_ptr``— guarda cada tabla por separado y hace el ``JOIN``
implícito. Sería ``class ResUsers(ResPartner)`` y ``name``/``email`` saldrían
gratis, sin las propiedades de abajo.

**Una sola diferencia estructural lo descarta**, y sólo queda en pie porque se
midió: el enlace de MTI es **siempre** ``OneToOneField`` —``parent_link=True``
lo exige—, mientras que ``partner_id`` de la referencia es ``Many2one`` sin
restricción única (``res_users.py:214``). Dos credenciales sobre un mismo
partner: la FK lo permite, MTI da ``IntegrityError``. Declarar el enlace a mano
no lo cambia; sigue siendo ``unique=True``.

Las otras dos objeciones que se escribieron aquí **eran falsas** y se corrigen
(medido con ``parent_link`` declarado explícitamente):

- *"MTI cablea* ``CASCADE`` *y no es configurable"* — **falso**. Declarando el
  campo (``OneToOneField(Parent, on_delete=PROTECT, parent_link=True,
  primary_key=True)``) el ``on_delete`` es el que se elija: borrar el padre da
  ``ProtectedError``. El ``CASCADE`` es sólo el default del campo
  ``auto_created``.
- *"con MTI no se puede adjuntar a un padre preexistente"* — **falso** con ese
  mismo override: ``Child.objects.create(parent_link=<padre existente>, …)``
  **no** crea fila nueva de padre. Lo que no funciona es la vía automática.

Queda además la divergencia conceptual: MTI es *is-a*
(``isinstance(user, ResPartner)`` sería ``True``), mientras que el ORM de la
referencia describe ``_inherits`` como *"implements **composition-based**
inheritance: the new model exposes all the fields of the inherited models but
**stores none of them**"* (``odoo/orm/models.py:416-418``).

Y un argumento de coste, no de capacidad: para que MTI se comportara como la
referencia habría que declarar el ``parent_link`` a mano — momento en que ya se
está escribiendo la FK, sin la automagia que hacía atractivo a MTI, y **aun
así** con la cardinalidad equivocada. Por eso: FK requerida + propiedades que
reenvían.

**Lo que NO se hereda de Django.** El modelo no extiende ``AbstractBaseUser``:
reimplementa el contrato de auth a mano (U-D puro, T-203) para no arrastrar
``is_staff``/``is_superuser`` ni el M2M de permisos nativo — la autorización
vive en ``authz`` por capacidad (DEC-11), y un flag de superusuario saltaría
ese modelo. Los *hashers* de Django sí se usan, como librería.
"""
import binascii
import contextlib
import datetime
import hashlib
import ipaddress
import logging
import os
import time
from dataclasses import dataclass
from datetime import timedelta
from zoneinfo import available_timezones

import api
import fields
import models

from django.apps import apps
from django.conf import settings
from django.contrib.auth import authenticate as django_authenticate
from django.contrib.auth import hashers
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db.models import F, Q
from django.db.models.functions import Length
from django.db.models.lookups import Exact
from django.db.models.signals import m2m_changed, post_delete, post_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from django.utils.crypto import salted_hmac

from addons.base.models import signals
from addons.base.models.ir_http import get_current_request
from addons.base.models.res_device import _client_ip
from addons.base.models.timestamped_mixin import TimeStampedModel
from exceptions import AccessDenied, AccessError, UserError
from orm.environments import get_current_company, get_current_user, is_su
from orm.utils import SUPERUSER_ID

#: ≙ el ``_logger`` de módulo que la referencia declara en la cabecera de
#: ``res_users.py`` (``odoo19c: res_users.py:38``). Se llamaba
#: ``_logger``, que era una acotación nuestra y no de la fuente: allá
#: lo usan el bloque de claves de API, el enfriamiento de acceso Y el cambio de
#: contraseña. El nombre acotado sugería que cada bloque traía el suyo.
_logger = logging.getLogger(__name__)

#: Prefijo de la clave con que se memoriza la clausura de grupos de un usuario.
#:
#: ≙ el ``@tools.ormcache('self.id')`` que la referencia cuelga de
#: ``_get_group_ids`` (``odoo19c: res_users.py:1098``). Su ``ormcache`` es un
#: diccionario por registro y por base; aquí el equivalente es el backend de
#: caché configurado, y la clave lleva **dos** ejes porque hay dos cosas que
#: pueden cambiar el resultado: el usuario y el grafo de implicación.
_GROUP_IDS_CACHE_PREFIX = 'base:group_ids'

#: Clave del contador de generación del grafo de implicación.
#:
#: El grafo de ``res.groups`` es **compartido**: reescribir un ``implied_ids``
#: cambia la clausura de todos los usuarios a la vez, no la de uno. Purgar por
#: usuario exigiría enumerarlos —lo que no escala y la propia fuente evita en
#: ``check_user_disjoint_groups``—, así que el invalidador de grafo incrementa
#: esta generación y con ello **jubila todas las claves vivas de golpe**.
#:
#: Es la adaptación de lo que la fuente resuelve con ``registry.clear_cache()``
#: (``odoo19c: res_users.py:643``), que purga el registro entero. Aquí un
#: ``cache.clear()`` sería más ancho todavía: barrería también las capacidades
#: de ``addons.authz.resolution``, que no dependen de este grafo.
_GROUP_GRAPH_GENERATION_KEY = 'base:group_graph_generation'

#: Vigencia del memo, en segundos. Es un techo, no el mecanismo de corrección:
#: quien corrige es el invalidador. El TTL sólo acota la ventana de una
#: escritura que ocurriera fuera de los descriptores del ORM —SQL crudo, o un
#: ``bulk_create`` sobre la tabla intermedia—, que no emite señal.
_GROUP_IDS_CACHE_TTL = 300


def _group_graph_generation():
    """La generación vigente del grafo de implicación.

    ``cache.get_or_set`` en vez de ``get`` con respaldo: si la clave se cayó
    —desalojo, reinicio del proceso— la generación arranca de nuevo en 1, y
    eso es **seguro por construcción**: las claves de la generación anterior
    quedan huérfanas y nadie vuelve a leerlas.
    """
    return cache.get_or_set(_GROUP_GRAPH_GENERATION_KEY, 1, None)


def _group_ids_cache_key(user_pk):
    return f'{_GROUP_IDS_CACHE_PREFIX}:{_group_graph_generation()}:{user_pk}'


def _invalidate_group_ids(user_pks=None):
    """Purga el memo de la clausura de grupos.

    Sin argumento, **jubila la generación entera**: es el caso del grafo de
    implicación, cuyo cambio afecta a todos los usuarios. Con una lista de PKs,
    purga sólo a ésos: es el caso de un usuario que gana o pierde un grupo.

    Las dos vías comparten nombre a propósito — anularlo con un ``return`` al
    entrar desactiva la invalidación completa, que es el control de
    ``metrica-decide-la-conclusion.md`` sub-patrón D que la suite ejercita.
    """
    if user_pks is None:
        try:
            cache.incr(_GROUP_GRAPH_GENERATION_KEY)
        except ValueError:
            # La clave no existe todavía: sembrarla ya jubila lo que hubiera.
            cache.set(_GROUP_GRAPH_GENERATION_KEY, 2, None)
        return
    cache.delete_many([_group_ids_cache_key(pk) for pk in user_pks if pk])


#: Contador de intentos fallidos por origen, para el enfriamiento de acceso.
#:
#: DIVERGENCIA DE MECANISMO, declarada: la fuente lo cuelga del **registro**
#: (``registry._login_failures``, ``odoo19c: res_users.py:1247-1250``), que en
#: su arquitectura es un objeto por proceso y por base. Aquí no hay tal objeto,
#: así que vive a nivel de módulo — **mismo alcance efectivo**: uno por proceso.
#:
#: La fuente declara ella misma la limitación que esto acarrea, y vale igual
#: aquí: *"The login counter is not shared between workers and not specifically
#: thread-safe, the feature exists mostly for rate-limiting on large number of
#: login attempts (brute-forcing passwords) so that should not be much of an
#: issue."* Su punto de extensión para una estrategia compartida —base de datos,
#: caché distribuida— es sobrescribir ``_assert_can_auth``, y ese punto se
#: conserva.
_LOGIN_FAILURES: dict = {}

# Sal del HMAC de sesión. Literal de Django (``AbstractBaseUser``): cambiarlo
# invalidaría toda sesión viva, así que se replica verbatim.
_SESSION_AUTH_KEY_SALT = (
    'django.contrib.auth.models.AbstractBaseUser.get_session_auth_hash'
)

#: El grupo "funciones técnicas". La referencia lo hace efectivo sólo en modo
#: depuración (``res_users.py:1080-1082``); aquí no hay tal modo — ver
#: :meth:`ResUsers.has_group`.
GROUP_NO_ONE_XMLID = 'base.group_no_one'

#: El grupo de usuario interno. Es el que la guarda de :meth:`ResUsers.has_group`
#: exige a quien pregunta por los grupos de otro.
GROUP_USER_XMLID = 'base.group_user'

#: El grupo de administración del sistema — ``_is_system`` (``:1177-1179``).
GROUP_SYSTEM_XMLID = 'base.group_system'

#: El grupo de administración funcional — la segunda mitad de ``_is_admin``
#: (``:1181-1183``).
GROUP_ERP_MANAGER_XMLID = 'base.group_erp_manager'

#: Los logins que :meth:`ResUsers.delete` protege — ≙ los cuatro ``env.ref``
#: de ``_unlink_except_master_data`` (``:648-660``), menos la plantilla de
#: usuario portal, que este árbol no tiene (invita por endpoint).
_SYSTEM_LOGINS = frozenset({'admin', 'public', '__system__'})


class ResUsersQuerySet(models.QuerySet):
    """El **recordset** de la credencial.

    La referencia declara sobre el recordset los métodos que actúan sobre un
    conjunto (``self.filtered(...)``, un ``for user in self``); aquí el
    recordset es el ``QuerySet``, no la instancia. Declararlos en el modelo
    obligaría a quien llama a iterar por su cuenta, y con eso se perdería la
    guarda que la fuente aplica **al conjunto entero antes de tocar nada**.
    """

    def _deactivate_portal_user(self, **post):
        """≙ ``_deactivate_portal_user`` (``odoo19c: res_users.py:934-987``).

        Su docstring de la fuente dice para qué existe: *"This is used to give
        the opportunity to portal users to de-activate their accounts. Indeed,
        as the portal users can easily create accounts, they will sometimes
        wish it removed because they don't use this Odoo portal anymore."*

        Seis efectos, en el orden de la fuente:

        1. **La guarda de clase, sobre el conjunto entero.** Si algún usuario
           del recordset no es de portal, no se da de baja a **ninguno** —
           ``AccessDenied`` antes del primer ``save()``. La fuente hace lo
           mismo con ``self.filtered(lambda user: not user.share)``.
        2. **El login se ofusca** a ``__deleted_user_<pk>_<epoch>``: libera el
           correo para que la persona pueda volver a registrarse, y deja la
           fila trazable mientras la cola de borrado la procesa.
        3. **La contraseña queda inutilizable.** La fuente escribe ``''``;
           aquí ``set_unusable_password()`` es la forma del stack, y es más
           estricta — un hash con prefijo ``!`` que ningún hasher valida.
        4. **Se retiran las claves de API** con ``_remove()``, que **sigue
           exigiendo identidad**: la baja la pide el propio usuario, así que
           el actor es él. Es la misma condición que la fuente impone
           (``env.is_system()`` o ser el dueño), y no se relaja aquí.
        5. **Se archivan el usuario y su partner.** La fuente envuelve las dos
           en ``try/except`` porque su ``action_archive`` puede fallar por una
           restricción de integridad (*"if the partner is related to an
           invoice e.g."*); aquí son escrituras de campo y no lanzan, así que
           el ``except`` no se porta — no hay excepción que tragar.
        6. **Se encola la fila de ``res.users.deletion``** en estado ``todo``,
           que es lo que la fuente hace al final.

        DIVERGENCIA, y es un **añadido** de este árbol: se escribe además
        ``deactivated_reason = DEACTIVATION_SELF_DELETED`` con su
        ``deactivated_at``. La fuente no lo necesita porque su ``active`` es un
        booleano sin motivo; aquí el flujo de reactivación por email decide
        con esa causa, y sin ella una baja voluntaria es indistinguible de una
        suspensión administrativa.

        :raises AccessDenied: si algún usuario del recordset no es de portal.
        """
        users = list(self)
        if not users:
            return
        no_portal = [user for user in users if not user.share]
        if no_portal:
            raise AccessDenied(
                'Sólo los usuarios de portal pueden dar de baja su cuenta. '
                'No se puede dar de baja a: %s'
                % ', '.join(user.login for user in no_portal))

        request = get_current_request()
        origen = _client_ip(request) if request is not None else 'n/a'
        ahora = timezone.now()
        model = self.model
        deletion = apps.get_model('base', 'ResUsersDeletion')

        for user in users:
            _logger.info(
                'Baja de cuenta solicitada para %r (#%s) desde %s. '
                'Se archiva al usuario y se retira su información de acceso.',
                user.login, user.pk, origen)

            user.login = '__deleted_user_%s_%s' % (user.pk, time.time())
            user.set_unusable_password()
            user.active = False
            user.deactivated_reason = model.DEACTIVATION_SELF_DELETED
            user.deactivated_at = ahora
            user.save(update_fields=[
                'login', 'password', 'active',
                'deactivated_reason', 'deactivated_at',
            ])

            for clave in list(user.api_keys.all()):
                clave._remove()

            if user.partner_id is not None:
                user.partner.active = False
                user.partner.save(update_fields=['active'])

            deletion.objects.create(
                user=user, user_int=user.pk, state=deletion.STATE_TODO)


class ResUsersManager(models.Manager):
    """Manager de la credencial. Replica lo que el framework consume.

    No hereda ``BaseUserManager`` por la misma razón que el modelo no hereda
    ``AbstractBaseUser``: sólo se replican los métodos que Django y
    ``createsuperuser`` llaman de verdad.
    """

    use_in_migrations = True

    def get_queryset(self):
        return ResUsersQuerySet(self.model, using=self._db)

    def _deactivate_portal_user(self, **post):
        """Delegación al recordset — ver
        :meth:`ResUsersQuerySet._deactivate_portal_user`."""
        return self.get_queryset()._deactivate_portal_user(**post)

    @staticmethod
    def normalize_email(email):
        """Normaliza el dominio a minúsculas (copia de ``BaseUserManager``)."""
        email = email or ''
        try:
            email_name, domain_part = email.strip().rsplit('@', 1)
        except ValueError:
            return email.strip()
        return email_name + '@' + domain_part.lower()

    def _create_user(self, login, password, partner=None, group_ids=None,
                     **extra_fields):
        """Crea la credencial **con sus grupos ya aplicados**.

        ``group_ids`` replica el campo homónimo de ``res.users`` en la
        referencia (``odoo19c: odoo/addons/base/models/res_users.py:257``),
        que viaja dentro de ``vals`` y queda escrito cuando ``create()``
        retorna. Por eso el propio ``create`` de la referencia puede leer
        ``user._is_internal()`` (``:583``) y ``user.share`` (``:590``) sobre
        lo que acaba de crear, y por eso el override de ``digest`` funciona.

        En Django el M2M sólo se escribe una vez que la fila tiene PK, así
        que aquí se aplica explícitamente entre el ``save()`` y el retorno.
        Quien reciba el usuario lo recibe en el mismo estado que en la
        referencia. Ver H-API-304.
        """
        if not login:
            raise ValueError('El login es obligatorio para ResUsers')
        login = self.normalize_email(login)
        if partner is None:
            # La referencia exige ``partner_id``: no hay credencial sin party.
            # Si el llamador no trae uno, se crea el mínimo viable con el
            # login como nombre — igual que ``res.users.create`` de Odoo, que
            # crea el partner cuando falta.
            partner = _partner_model().objects.create(
                name=extra_fields.pop('name', '') or login,
                email=login,
            )
        user = self.model(login=login, partner=partner, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        if group_ids:
            user.group_ids.set(group_ids)
        # Equivalente del punto en que ``super().create()`` retorna en la
        # referencia: la credencial existe y sus grupos están escritos. Los
        # satélites (``digest``) escuchan aquí; ``base`` no los importa.
        signals.res_users_created.send(sender=self.model, user=user)
        return user

    def create_user(self, login, password=None, **extra_fields):
        extra_fields.setdefault('active', True)
        return self._create_user(login, password, **extra_fields)

    def create_superuser(self, login, password=None, **extra_fields):
        """Crea la credencial. El rol ``superadmin`` (DEC-01=B) se asigna en el
        seed de ``authz``: U-D puro no tiene flag ``is_superuser``.
        """
        extra_fields.setdefault('active', True)
        return self._create_user(login, password, **extra_fields)

    def get_by_natural_key(self, username):
        return self.get(**{self.model.USERNAME_FIELD: username})


def _partner_model():
    """Resuelve ``ResPartner`` por el registro de apps.

    Lo que se difiere es la **resolución** (``get_model``), no el import: un
    import de ``res_partner`` a nivel de módulo cerraría el ciclo
    ``res_users`` → ``res_partner`` → ``__init__``, pero ``django.apps`` es el
    registro, no el modelo, y se importa arriba sin tocar ese ciclo.

    La versión anterior tenía el ``from django.apps import apps`` **dentro** de
    la función y un docstring que lo justificaba como "una llamada, no un
    statement". Era falso —es un statement de import— y sólo pasaba el gate
    porque el gate no miraba este árbol (ver H-API-221).
    """
    return apps.get_model('base', 'ResPartner')


class ResUsers(TimeStampedModel):
    """``res.users`` — credencial de acceso, delegando identidad al partner.

    Fiel a ``odoo19c: odoo/addons/base/models/res_users.py:163-257`` en lo
    estructural: ``partner`` requerido (``partner_id``), ``login``,
    ``password``, ``active``, ``company``. Los campos computados de la
    referencia (``share``, ``companies_count``, ``tz_offset``) no se portan.

    **El M2M a ``res.groups`` sí existe desde ``res_groups.py``.** La nota
    anterior decía que no se portaba; quedó obsoleta al portar ese archivo. La
    referencia declara ``user_ids`` **del lado de ``res.groups``**
    (``res_groups_users_rel``), así que aquí el reverso llega por
    ``related_name='group_ids'`` sin declarar nada. Que exista la relación NO
    cambia la autorización: este árbol sigue autorizando por **capacidad**
    (DEC-11, ``HasCapability`` fail-closed) sobre ``authz``; el re-apuntado de
    los consumidores es una decisión de producto aparte.

    Los cinco atributos de clase (H-API-618, tarea #385)
    -----------------------------------------------------

    La fuente los declara en ``:163-167``; aquí van los cinco, con su forma
    Django derivada al lado cuando existe:

    - ``_inherits`` — el destino de la delegación. **El mecanismo ya estaba**
      (``orm/inherits.py``, tarea #88, aplicado en ``BaseConfig.ready()``); lo
      que faltaba era la declaración, que es de donde ese cableado ahora lee su
      par delegado→FK en vez de tenerlo escrito a mano. El valor de la FK es
      ``partner``, no ``partner_id``: este árbol suprime el sufijo ``_id``.
    - ``_order = 'name, login'`` → ``Meta.ordering = ['partner__name',
      'login']``. ``name`` **no es columna** de ``res_users``: la fuente lo
      obtiene del partner por la misma delegación, y aquí eso es el lookup de
      la FK. Antes decía ``['login']`` — divergencia silenciosa, ahora cerrada.
    - ``_allow_sudo_commands = False`` — la fuente lo declara explícito: este
      modelo **no** admite comandos con privilegio.
    - ``_name`` y ``_description`` — verbatim; ``_description`` convive con
      ``Meta.verbose_name``, no lo sustituye.

    **El objeto de tabla ``_login_key``** (``UNIQUE (login)``, ``:274``) ya
    existe y con el nombre de la referencia: ``login`` se declara
    ``unique=True`` y PostgreSQL nombra el constraint ``res_users_login_key``
    — verificado con ``pg_constraint``. No hace falta un ``Meta.constraints``
    para renombrarlo.

    Los 73 símbolos que este porte NO trae, y su desenlace
    -------------------------------------------------------

    Medido con ``check_porte_completo`` contra
    ``odoo19c: odoo/addons/base/models/res_users.py`` tras el pase de #51.
    Ninguno se omite en silencio — ``porte-completo-no-parcial.md`` admite
    tres desenlaces y cada familia declara el suyo.

    *Métrica:* nombres de método declarados en la referencia y ausentes por
    **literal** en este archivo (AST, no grep).
    *Ciega a:* un símbolo portado **bajo otro nombre**, que el instrumento
    cuenta como ausente. Aquí hay uno y va declarado: la lista incluye
    ``_unlink_except_master_data``, que **sí está portado** — como
    :meth:`delete`, porque el gancho equivalente de Django es sobrescribir ese
    método y no un ``@api.ondelete``. Los 72 restantes sí son ausencias.

    **1. La capa de vista de su cliente OWL — 21 símbolos.** DIVERGENCIA DE
    STACK. ``onchange``, ``on_change_login``, ``onchange_parent_id``,
    ``_onchange_role``, ``fields_get``, ``_get_view_postprocessed``,
    ``_default_view_group_hierarchy``, ``_action_show``,
    ``action_show_groups``, ``action_show_accesses``,
    ``action_show_rules``, ``action_get``,
    ``action_change_password_wizard``, ``api_key_wizard``,
    ``preference_save``, ``preference_change_password``,
    ``action_revoke_all_devices``, ``_compute_email_domain_placeholder``,
    ``_compute_signature``, ``_compute_role``, ``copy_data``,
    ``_default_groups``. Son el diálogo entre su ORM y su cliente web: un
    ``@api.onchange`` recalcula un formulario abierto, y una ``action_*``
    devuelve un diccionario que su cliente interpreta como «abre esta vista».
    Aquí el cliente es React sobre endpoints DRF: el equivalente del onchange
    es la validación del serializer, y el de la acción es la URL que el
    frontend ya conoce. Portarlas produciría métodos sin quién los llame — el
    defecto que este mismo archivo evitó con los wizards (:ref:`h-api-801`).

    **2. Ganchos del ciclo de vida de su ORM — 11 símbolos.** DIVERGENCIA DE
    MECANISMO. ``create``, ``write``, ``read``, ``init``, ``_register_hook``,
    ``name_search``, ``_search_display_name``, ``_search_all_group_ids``,
    ``_search_res_users_settings_id``, ``_compute_all_group_ids``,
    ``_compute_res_users_settings_id``. Django los tiene con otro nombre y
    otra forma: ``create``/``write`` son ``save()``, ``read`` es el queryset,
    ``init`` son las migraciones, ``_register_hook`` es ``AppConfig.ready()``,
    y un ``_search_*`` de campo calculado es un ``annotate()``. El
    comportamiento vive donde el stack lo pone, no ausente.

    **3. Contabilidad para su vista de ajustes — 5 símbolos.** DIVERGENCIA DE
    MECANISMO. ``_compute_companies_count``, ``_compute_accesses_count``,
    ``_compute_share``, ``_compute_tz_offset``, ``_check_action_id``. Los
    cuatro primeros alimentan contadores de su formulario; ``share`` sí existe
    aquí, como ``property``. ``_check_action_id`` valida el campo *home
    action*, que este árbol no tiene: BLOQUEADO por ``action_id`` — no hay
    campo que validar.

    **4. La superficie de cuenta propia — 4 de 6 portados, 2 divergen.**
    Son el control de qué campos puede leerse y escribirse un usuario **a sí
    mismo**. El grupo entero se declaraba detenido *"por canal RPC crudo — no
    está construido"*, y esa premisa **caducó**: el canal existe desde #85
    (:ref:`h-api-835`). La marca se retira porque ya no hay bloqueo que
    declarar, no porque se reescriba su forma.

    Portados: ``_rpc_api_keys_only`` (#85), ``SELF_READABLE_FIELDS`` y
    ``SELF_WRITEABLE_FIELDS`` (#66 y #85, extensibles con
    ``orm.model_classes.extend_property`` — :ref:`h-api-834`), y
    ``_self_accessible_fields``, que deriva las dos listas.

    DIVERGENCIA DE MECANISMO, los dos que quedan. ``_has_field_access`` es el
    enganche del control de acceso **por campo** de su ORM; aquí ese control
    lo ejerce el serializer con su ``Meta.fields`` explícito más la
    autorización por capacidad (DEC-11), que es fail-closed — no hay un
    despacho por campo al que engancharse. ``context_get`` compone el contexto
    de sesión de su ORM, que este árbol no tiene: el equivalente es
    ``request.user`` más ``orm.environments``.

    **5. Su cifrador de contraseñas — 9 símbolos.** DIVERGENCIA DE STACK.
    ``CryptContext`` entera —``__init__``, ``copy``, ``hash``, ``identify``,
    ``verify``, ``verify_and_update``, ``schemes``, ``update``— más
    ``_crypt_context``. Es su envoltura
    de ``passlib``; aquí el equivalente son los ``PASSWORD_HASHERS`` de Django,
    que ``set_password``/``check_password`` ya consumen — incluido el rehash
    automático que su ``verify_and_update`` hace a mano.

    **6. La caché de autorización — 3 símbolos.**
    ``_get_invalidation_fields`` está **portado** (tarea #58), y con él
    :meth:`_get_group_ids` memoriza como en la fuente: el bloque de módulo
    ``_group_ids_cache_key`` / ``_invalidate_group_ids`` y sus cuatro
    receptores son la forma que toma aquí el ``registry.clear_cache()`` que
    allá se dispara desde ``write``.

    Los otros dos —``_compute_session_token`` y
    ``_get_session_token_query_params``— son la memorización y el SQL crudo de
    un token que aquí calcula Django (ver :meth:`_get_session_token_fields`).
    Quedan como **divergencia de stack declarada**, no como trabajo.

    **7. El resto, triado uno por uno — 19 símbolos.** Este bloque decía
    *"18"* y listaba **19**; el conteo se corrigió al triarlos (tarea #59),
    y con él la afirmación de que *"el resto es trabajo, no divergencia"* —
    medido, nueve de los diecinueve ya tenían su desenlace declarado en
    **este mismo archivo**, y listarlos aquí como pendientes contradecía esa
    declaración.

    *Portados — 7:*

    - ``_deactivate_portal_user`` (``:934-987``) → :meth:`ResUsersQuerySet
      ._deactivate_portal_user`. Su consumidor **ya existía** y hacía dos de
      sus seis mitades a mano.
    - ``_set_encrypted_password`` (``:299-306``) y ``_set_new_password``
      (``:414-426``) → los dos aquí abajo, con sus guardas.
    - ``UsersMultiCompany`` — sus tres símbolos (``create``, ``write``,
      ``new``) son **el mismo cuerpo colgado de tres ganchos** de su ORM.
      Aquí es **un** receptor de ``m2m_changed``
      (:func:`_sync_multi_company_group`, al final del archivo), porque en
      Django el M2M nunca se escribe en el ``save()``: va siempre por su
      propio camino, y ese camino es justo la condición que su ``write``
      comprueba a mano con ``if 'company_ids' not in vals``. Tarea **#68**.
    - ``_action_revoke_all_devices`` (``:1028-1031``) →
      :meth:`_action_revoke_all_devices`. Estuvo BLOQUEADO por
      ``ResDevice._revoke``, que se portó en la tarea **#69**; el bloqueo era
      real y se cerró desbloqueándolo, no rebajándolo.

    *Divergencia declarada — 3:*

    - ``_set_password`` y ``_compute_password``: existen porque su ``password``
      es un campo **compute/inverse** que nunca guarda lo que se le asigna.
      Aquí es la columna de Django y el cifrado es explícito
      (:meth:`set_password`), así que no hay *inverse* que colgar ni valor que
      blanquear al leer.
    - ``_legacy_session_token_hash_compute`` (``:886-896``): su único
      consumidor es ``odoo19c: odoo/service/security.py:27-32``, que migra un
      token de sesión del formato viejo al nuevo **dentro de su propio
      almacén de sesiones**. Aquí las sesiones son de Django y no hay corpus
      heredado que convertir: portarlo daría un método sin quién lo llame.

    *Con desenlace ya declarado en este archivo — 9:*

    - los cuatro de los asistentes de contraseña (``_default_user_ids``,
      ``change_password_button``, ``_check_password_confirmation``,
      ``run_check``) → :ref:`h-api-801`;
    - los cinco de ``ResUsersApikeysDescription`` (``_selection_duration``,
      ``_compute_expiration_date``, ``_onchange_expiration_date``, ``create``,
      ``make_key``) → declarados en el docstring de
      :class:`_ResUsersApikeysBase`, punto 5, con su sucesor **#490** y con la
      mitad que **no** es presentación ya medida aparte.
    """

    _name                 = 'res.users'
    _description          = 'User'
    _inherits             = {'res.partner': 'partner'}
    _order                = 'name, login'
    _allow_sudo_commands  = False

    # Causas distintas de ``active=False`` (UC-AUTH-01 Alt-A, UC-AUTH-13/16).
    # No están en la referencia: allí ``active`` es un booleano sin motivo.
    # Se conservan porque el flujo de reactivación por email depende de
    # distinguir "no verificada" de "suspendida por un administrador".
    DEACTIVATION_UNVERIFIED   = 'unverified'
    DEACTIVATION_SUSPENDED    = 'suspended'
    DEACTIVATION_SELF_DELETED = 'self_deleted'
    DEACTIVATION_REASON_CHOICES = [
        (DEACTIVATION_UNVERIFIED,   'No verificada (email pendiente)'),
        (DEACTIVATION_SUSPENDED,    'Suspendida por administrador'),
        (DEACTIVATION_SELF_DELETED, 'Dada de baja por el usuario'),
    ]
    DEACTIVATION_REASONS_REACTIVABLE_BY_EMAIL = {
        DEACTIVATION_UNVERIFIED,
        DEACTIVATION_SELF_DELETED,
    }

    partner       = fields.Many2one(
        'base.ResPartner', on_delete=models.PROTECT, related_name='users',
        help_text=(
            'Party al que pertenece esta credencial (Odoo partner_id). '
            'Requerido: en la referencia no hay usuario sin partner.'
        ),
    )
    login         = fields.Char(
        max_length=254, unique=True, db_index=True,
        help_text='Identificador de acceso (Odoo login). Aquí es el email.',
    )
    password      = fields.Char(max_length=128, verbose_name='Contraseña')
    active        = fields.Boolean(
        default=True, db_index=True,
        help_text='Cuenta operativa (Odoo active).',
    )
    last_login    = fields.Datetime(null=True, blank=True)

    deactivated_reason = fields.Selection(
        max_length=20, choices=DEACTIVATION_REASON_CHOICES,
        null=True, blank=True,
        help_text=(
            'Causa por la que active=False; NULL cuando la cuenta está activa. '
            'Distingue las reactivables por email de las que exigen UC-AUTH-14.'
        ),
    )
    deactivated_at = fields.Datetime(null=True, blank=True)

    company       = fields.Many2one(
        'base.ResCompany', on_delete=models.PROTECT, null=True, blank=True,
        related_name='users',
        help_text=(
            'Company L1 del usuario (Odoo company_id). NULL = operador de '
            'plataforma L0 o sin asignar. Lo consume el resolver de company.'
        ),
    )

    objects = ResUsersManager()

    USERNAME_FIELD = 'login'
    EMAIL_FIELD    = 'login'
    REQUIRED_FIELDS = []

    # Sentinela de cambio de password (replica ``AbstractBaseUser._password``).
    _password = None

    class Meta:
        db_table            = 'res_users'
        # Derivado de ``_order = 'name, login'``: ``name`` vive en el partner
        # delegado, así que aquí es el lookup de la FK.
        ordering            = ['partner__name', 'login']
        verbose_name        = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self) -> str:
        return self.login

    # --- Delegación al partner (el ``_inherits`` que Django no tiene) ---
    @property
    def name(self):
        return self.partner.name

    @property
    def email(self):
        """La referencia relaciona ``email`` al del partner (``:253``)."""
        return self.partner.email or self.login

    @property
    def phone(self):
        return self.partner.phone

    # --- Contrato de auth (reimplementación manual, U-D puro) ---
    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    @property
    def is_active(self):
        """Alias del contrato de Django sobre el ``active`` de la referencia.

        Django consulta ``is_active`` en ``ModelBackend.user_can_authenticate``
        y en el login. La referencia llama al campo ``active``; se conserva ese
        nombre y se expone el alias, en vez de renombrar el campo.
        """
        return self.active

    def get_username(self):
        return getattr(self, self.USERNAME_FIELD)

    def natural_key(self):
        return (self.get_username(),)

    def set_password(self, raw_password):
        self.password = hashers.make_password(raw_password)
        self._password = raw_password

    def check_password(self, raw_password):
        """Verifica el password y re-hashea si el hasher quedó obsoleto."""
        def setter(raw):
            self.set_password(raw)
            # Evita disparar la señal de cambio en el re-hash.
            self._password = None
            self.save(update_fields=['password'])
        return hashers.check_password(raw_password, self.password, setter)

    def set_unusable_password(self):
        self.password = hashers.make_password(None)

    def has_usable_password(self):
        return hashers.is_password_usable(self.password)

    def _rpc_api_keys_only(self):
        """≙ ``_rpc_api_keys_only`` (``odoo19c: res_users.py:308-310``).

        Su docstring de la fuente, verbatim: *"To be overridden if RPC access
        needs to be restricted to API keys, e.g. for 2FA"*.

        Es el eslabón **vacío** de una cadena de tres, igual que ``_mfa_type``:
        ``base`` dice que no y cada addon de 2FA aporta su razón para decir que
        sí. Se encadena con ``combine=first_truthy`` porque la forma de la
        fuente es ``<lo propio> or super()`` — con el relevo por defecto, un
        ``False`` del eslabón externo cortaría la cadena y el interno nunca
        respondería.
        """
        return False

    def _check_credentials(self, credential, env):
        """≙ ``_check_credentials`` (``odoo19c: res_users.py:312-405``).

        El eslabón **terminal** de la cadena de verificación de credenciales:
        atiende ``type == 'password'`` y **rechaza** cualquier otro tipo. Los
        addons de la familia cuelgan los suyos encima con ``chain_method``,
        que es como este árbol materializa el ``super()`` de la referencia
        (``authz_totp`` → ``totp``, ``authz_totp_mail`` → ``totp_mail``,
        ``authz_passkey`` → ``webauthn``).

        **La dirección se invierte y el efecto es el mismo.** La fuente
        declara al revés —cada addon mira su tipo y llama a ``super()``, que
        termina aquí— y ``chain_method`` construye la misma pila desde el otro
        extremo: el eslabón instalado **más tarde** corre primero, devuelve
        ``None`` si el tipo no es suyo, y el relevo por defecto invoca al
        anterior. Este método es el último de esa cadena, así que su rechazo es
        el de la fuente (``:352-353``) y no relevo alguno.

        Sin esa distinción —``None`` es «no es mi tipo», ``AccessDenied`` es
        «es mío y está mal»— el despacho no puede separar las dos, que es
        exactamente el defecto que la orquestación a mano tenía (#722).

        **La rama no interactiva, portada (#85).** Cuando ``env['interactive']``
        es falso, este método es el canal RPC: acepta una **clave de API** en
        el lugar de la contraseña, y consulta ``_rpc_api_keys_only`` para
        negar la contraseña cuando el usuario tiene 2FA. Las dos mitades son
        de la fuente (``:356`` y ``:387-400``) y las dos son necesarias: sin la
        primera no hay canal, y sin la segunda el 2FA se rodea presentando la
        contraseña por RPC.

        Su bloqueo decía que el canal *"no está construido"*, y esa premisa
        **caducó sin que este archivo cambiara**: el modelo ``res.users.apikeys``
        se portó entero —``_check_credentials(scope, key)``, ``_generate``,
        ``revoke``, ``_assert_can_auth``— en las tareas #23, #26 y #34. Lo
        único que faltaba era esta rama. Es la sexta vez que una divergencia
        declarada caduca así (:ref:`h-api-835`).

        **Divergencia de mecanismo — el rehash.** La fuente hace
        ``verify_and_update`` y, si el algoritmo cambió, reescribe el hash y
        renueva el token de sesión (``:365-374``). Aquí lo cubre
        ``AbstractBaseUser.check_password``, que ya reescribe el hash por su
        ``setter``; el token de sesión de Django no se deriva de la contraseña,
        así que no hay nada que renovar.

        :returns: ``auth_info`` — ``{'uid', 'auth_method', 'mfa'}``. ``mfa``
            vale ``'skip'`` (el método ya cuenta como los dos factores),
            ``'default'`` (delegar en el segundo factor) o ``'enforce'``.
        """
        # ≙ ``:351-353`` verbatim: el tipo ajeno y la contraseña vacía son el
        # mismo rechazo. Este eslabón es el último, así que aquí no hay relevo.
        if not (credential.get('type') == 'password'
                and credential.get('password')):
            raise AccessDenied()

        env = env or {}
        if 'interactive' not in env:
            # ≙ el aviso de ``:357-361``: sin la clave se asume interactivo.
            _logger.warning(
                "_check_credentials sin la clave 'interactive'; se asume "
                'login interactivo. Revisar llamadores y extensiones.'
            )

        # ≙ ``:356`` — la contraseña sólo se mira si el login es interactivo o
        # si el usuario no exige clave de API. Con 2FA activo, un RPC por
        # contraseña rodearía el segundo factor entero.
        interactive = env.get('interactive', True)
        if interactive or not self._rpc_api_keys_only():
            if self.check_password(credential['password']):
                return {
                    'uid': self.pk,
                    'auth_method': 'password',
                    'mfa': 'default',
                }

        if not interactive:
            # ≙ ``:387-394``, con su comentario: *"'rpc' scope does not really
            # exist, we basically require a global key (scope NULL)"*. La clave
            # viaja en el campo de la contraseña, que es el canal de la fuente
            # — no una cabecera propia.
            ResUsersApikeys = apps.get_model('base', 'ResUsersApikeys')
            if ResUsersApikeys._check_credentials(
                    scope='rpc', key=credential['password']) == self.pk:
                return {
                    'uid': self.pk,
                    'auth_method': 'apikey',
                    'mfa': 'default',
                }

            if self._rpc_api_keys_only():
                # ≙ ``:396-400`` verbatim. El registro distingue este rechazo
                # del de credencial errónea; la respuesta al cliente NO, y
                # ésa es la mitad que protege: decirle que su contraseña es
                # correcta pero el canal exige clave le confirma la contraseña.
                _logger.info(
                    'Invalid API key or password-based authentication '
                    'attempted for a non-interactive (API) context that '
                    'requires API key authentication only.')

        raise AccessDenied()

    def change_password(self, old_passwd, new_passwd):
        """≙ ``change_password`` (``odoo19c: res_users.py:899-917``).

        Cambia la contraseña del usuario **exigiendo la anterior**. La fuente
        declara por qué en su docstring, y vale igual aquí: *"Old password must
        be provided explicitly to prevent hijacking an existing user session"* —
        una sesión robada no basta para quedarse con la cuenta.

        Es la vía **autoportante**: no depende de la re-autenticación de
        DEC-12, porque la credencial anterior es ella misma la prueba de
        identidad. La fuente tiene además una segunda vía —el asistente
        ``change.password.own``, decorado ``@check_identity``— que aquí no se
        porta como modelo: su equivalente es el gate de sesión fresca que ya
        existe (``authz_reauth.assert_session_fresh``), y el asistente en sí es
        la capa de formulario de su UI, que este árbol resuelve con un
        serializer. Ver :ref:`h-api-790`.

        :raises AccessDenied: si la contraseña anterior falta o es incorrecta.
        :raises UserError: si la nueva está vacía.
        :returns: ``True``.
        """
        if not old_passwd:
            raise AccessDenied()

        credential = {
            'login': self.get_username(),
            'password': old_passwd,
            'type': 'password',
        }
        self._check_credentials(credential, {'interactive': True})

        self._change_password(new_passwd)
        return True

    def _change_password(self, new_passwd):
        """≙ ``_change_password`` (``odoo19c: res_users.py:919-932``).

        El eslabón interno: **no** verifica identidad — eso es de quien llama.
        Recorta, rechaza el vacío y **deja constancia de quién cambió la
        contraseña de quién y desde dónde**, que es el rastro que hace
        auditable un cambio de credencial.

        La fuente lee la IP de su ``request`` de hilo; aquí sale de la misma
        ``ContextVar`` y el mismo ``_client_ip`` que usa el limitador de
        acceso, así que las dos entradas del registro se pueden cruzar por
        origen.

        DIVERGENCIA DE MECANISMO, declarada: la fuente asigna
        ``self.password = new_passwd`` y su ORM cifra en el ``write``. Aquí el
        cifrado es explícito —``set_password`` llama a ``hashers.make_password``—
        y hay que **persistir**: el modelo de la fuente escribe en la asignación
        y el de Django no.
        """
        new_passwd = (new_passwd or '').strip()
        if not new_passwd:
            raise UserError(
                'Dejar la contraseña vacía no está permitido, por seguridad.')

        request = get_current_request()
        source = _client_ip(request) if request is not None else 'n/a'
        actor = get_current_user()
        _logger.info(
            "Cambio de contraseña de %r (#%s) por %r (#%s) desde %s",
            self.get_username(), self.pk,
            getattr(actor, 'username', None) or '?',
            getattr(actor, 'pk', None) or '?',
            source)

        self.set_password(new_passwd)
        self.save(update_fields=['password'])

    @classmethod
    def _set_encrypted_password(cls, uid, pw):
        """≙ ``_set_encrypted_password`` (``odoo19c: res_users.py:299-306``).

        Escribe una contraseña **ya cifrada**, sin volver a pasarla por el
        cifrador. Es la vía por la que entra una credencial que se hasheó en
        otra parte —una importación, un directorio LDAP—: asignarla por
        :meth:`set_password` la hashearía otra vez y dejaría de validar.

        La fuente baja a SQL crudo (``UPDATE res_users SET password=%s``) por
        la misma razón por la que aquí se usa ``QuerySet.update()``: el camino
        normal de escritura del ORM cifraría lo que ya está cifrado. Ninguno de
        los dos pasa por el modelo.

        DIVERGENCIA DE MECANISMO, declarada, y es la única: la fuente afirma la
        precondición con ``assert self._crypt_context().identify(pw) !=
        'plaintext'``. Aquí es un ``UserError``, no un ``assert`` — un ``assert``
        desaparece con ``python -O`` y éste guarda una credencial: con la
        aserción compilada fuera, un texto plano entraría a la columna de
        contraseña y **validaría contra nada**. Quién identifica el hash
        también cambia: allá es su ``passlib``, aquí
        ``hashers.identify_hasher``, que es el registro de ``PASSWORD_HASHERS``
        de la instalación.

        :raises UserError: si ``pw`` no es un hash que la instalación reconozca.
        """
        try:
            hashers.identify_hasher(pw)
        except (ValueError, TypeError):
            raise UserError(
                'Sólo se admite una contraseña ya cifrada por esta vía: el '
                'valor recibido no lo reconoce ningún hasher de la '
                'instalación. Para una contraseña en claro va set_password.')
        cls.objects.filter(pk=uid).update(password=pw)

    def _set_new_password(self, new_password):
        """≙ ``_set_new_password`` (``odoo19c: res_users.py:414-426``).

        Fija la contraseña de **otra** persona — un administrador sobre la
        cuenta que administra. Dos reglas, las dos de la fuente:

        1. **Un valor vacío se ignora en silencio** (``:416-419``): *"Do not
           update the password if no value is provided, ignore silently. For
           example web client submits False values for all empty fields."*
        2. **Nadie cambia la suya por aquí** (``:421-424``). El comentario de
           la fuente da la razón, y vale igual: *"To change their own password,
           users must use the client-specific change password wizard, so that
           the new password is immediately used for further RPC requests,
           otherwise the user will face unexpected 'Access Denied'
           exceptions."* La vía propia es :meth:`change_password`, que exige la
           anterior y por eso no depende de re-autenticación.

        DIVERGENCIA DE MECANISMO, declarada: la fuente es el *inverse* del
        campo ``new_password`` de su formulario, así que su ORM la invoca al
        escribir y ella asigna ``user.password``, que su propio ``write``
        cifra. Aquí no hay campo de formulario ni cifrado implícito: es un
        método que se llama y que cifra y persiste explícitamente. Lo que se
        porta es la **regla**, no el gancho.

        :raises UserError: si el sujeto es el usuario en curso.
        """
        if not new_password:
            return
        actor = get_current_user()
        if getattr(actor, 'pk', None) == self.pk:
            raise UserError(
                'Para cambiar tu propia contraseña usa el cambio de '
                'contraseña con la anterior: por esta vía la sesión en curso '
                'se quedaría con la credencial vieja.')
        self._change_password(new_password)

    def _action_revoke_all_devices(self, request=None):
        """≙ ``_action_revoke_all_devices`` (``odoo19c: res_users.py:1028-1031``).

        Cierra **todas** las sesiones de esta persona menos la que está usando
        ahora: si también cerrara la actual, el gesto de «expulsar al intruso»
        expulsaría a quien lo pide.

        **Un solo cuerpo donde la fuente tiene dos.** Su ``action_revoke_all
        _devices`` (``:1021-1025``) es el público con ``@check_identity`` y
        éste el interno sin él; aquí la identidad fresca la exige
        ``authz_reauth.assert_session_fresh`` desde la vista (DEC-12), así que
        el gate lo pone quien lo exponga. Misma resolución que
        ``authz_totp.revoke_all_devices`` y que
        :meth:`ResDeviceQuerySet._revoke`.

        DIVERGENCIA DE MECANISMO, declarada en el retorno: la fuente devuelve
        ``{'type': 'ir.actions.client', 'tag': 'reload'}`` — una orden para su
        cliente web, no un dato. Aquí no hay tal cliente: devuelve **cuántas
        filas de log quedaron revocadas**, que es lo que el llamador puede
        verificar.

        :param request: la petición en curso; por defecto la del contexto. Es
            la que decide cuál dispositivo es el actual.
        """
        request = request if request is not None else get_current_request()
        device = apps.get_model('base', 'ResDevice')
        devices = device.objects.filter(user_id=self.pk)
        if request is not None:
            devices = devices.exclude(
                pk__in=[d.pk for d in devices if d.is_current(request)])
        return devices._revoke(request)

    @classmethod
    def _get_session_token_fields(cls):
        """≙ ``_get_session_token_fields`` (``odoo19c: res_users.py:829-830``).

        Los campos de los que **depende una sesión viva**: cambiar cualquiera
        de ellos la invalida. La fuente declara exactamente estos cuatro, y
        cada uno tiene su razón — ``password`` (cambio de credencial),
        ``active`` (cuenta archivada), ``login`` (identidad renombrada) e
        ``id`` (por si el hash viajara entre usuarios).

        Es un **punto de extensión**, no una constante: la fuente lo ensancha
        desde sus addons (``auth_passkey`` añade sus llaves para que revocar
        una cierre las sesiones que abrió). Aquí lo consume
        :meth:`_session_token_get_values`, que a su vez alimenta el
        ``get_session_auth_hash`` que Django valida en cada petición.
        """
        return {'id', 'login', 'password', 'active'}

    def _session_token_get_values(self):
        """≙ ``_session_token_get_values`` (``:858-869``) — el par nombre/valor.

        La fuente lee las columnas con SQL crudo y devuelve tuplas
        ``(nombre, valor)`` *"allowing for overrides to manipulate the
        values"*. Aquí no hace falta bajar a SQL —los campos son atributos del
        modelo— pero **sí** se conserva la forma del retorno: es lo que permite
        que una extensión añada un valor sin reescribir el cálculo del hash.

        Se ordena por nombre, igual que el ``sorted()`` de la fuente
        (``:836``): sin orden estable el mismo usuario daría hashes distintos
        entre procesos y toda sesión moriría al primer salto.
        """
        return tuple(
            (name, getattr(self, 'pk' if name == 'id' else name, None))
            for name in sorted(self._get_session_token_fields())
        )

    @staticmethod
    def _session_token_hash_compute(field_values, secret=None):
        """≙ ``_session_token_hash_compute`` (``:871-884``).

        Construye la llave con los pares cuyo valor **no es ``None``**. La
        fuente explica por qué el filtro existe, y vale igual aquí: *"To avoid
        invalidating sessions when installing a new feature modifying the
        session token computation while not still being used"* — un campo
        nuevo y vacío no debe cerrar las sesiones de todo el mundo.

        DIVERGENCIA DE MECANISMO, declarada, y es la única del bloque: la fuente
        hmaquea **el identificador de sesión** con esa llave, porque su
        ``http.py`` valida sesión contra token. Aquí la sesión la valida
        Django, que llama a ``get_session_auth_hash()`` **sin** identificador,
        así que el mensaje es la propia llave y el secreto es el de la
        instalación. Los dos hmac dependen del mismo conjunto de campos, que es
        lo que decide qué invalida una sesión; lo que cambia es quién aporta la
        entropía, y allá tampoco es el usuario.
        """
        clave = tuple((k, v) for k, v in field_values if v is not None)
        return salted_hmac(
            _SESSION_AUTH_KEY_SALT, str(clave),
            secret=secret, algorithm='sha256',
        ).hexdigest()

    def get_session_auth_hash(self):
        """El hash que Django compara en cada petición para validar la sesión.

        Hasta este pase hmaqueaba **sólo** ``self.password``, que es el default
        de ``AbstractBaseUser``. Con eso, archivar una cuenta o renombrar su
        login **no cerraba sus sesiones vivas** — la referencia sí las cierra,
        porque su token depende de los cuatro campos de
        :meth:`_get_session_token_fields`.

        El ensanche invalida **una vez** todas las sesiones abiertas, porque el
        mensaje del hmac cambia. Es el precio declarado de cerrar el hueco, y
        ocurre una sola vez: a partir de aquí el conjunto es estable y su
        extensión es el punto declarado de arriba.
        """
        return self._session_token_hash_compute(self._session_token_get_values())

    def get_session_auth_fallback_hash(self):
        """Hashes bajo ``SECRET_KEY_FALLBACKS`` — mantiene válidas las sesiones
        durante la rotación de ``SECRET_KEY``.

        ≙ ``_legacy_session_token_hash_compute`` (``:886-896``) en su propósito:
        la fuente conserva el cálculo viejo para no cerrar las sesiones que se
        abrieron con él. Aquí el eje del legado no es la fórmula sino el
        secreto, que es lo que Django rota — de ahí que sea el mismo cómputo
        con otro ``secret`` y no una segunda fórmula.
        """
        for fallback_secret in settings.SECRET_KEY_FALLBACKS:
            yield self._session_token_hash_compute(
                self._session_token_get_values(), secret=fallback_secret)

    # --- Compañías permitidas (≙ ``company_id`` + ``company_ids``) ---
    #
    # ``company_ids`` **existe** como reverso del M2M declarado en
    # ``ResCompany.user_ids`` (``related_name='company_ids'``, tabla
    # ``res_company_users_rel`` con columnas ``cid``/``user_id``). La
    # referencia lo declara desde ambos lados con esos mismos nombres
    # (``odoo19c: res_users.py:247`` y ``res_company.py:68``; idem
    # ``odoo18c:`` en ``:403`` y ``:54``).
    #
    # Los dos campos son ejes distintos, no redundantes: ``company`` es la
    # compañía **activa por defecto**, ``company_ids`` el **conjunto
    # alcanzable sin volver a autenticarse**. El resolutor de ``ir_http``
    # ya consume ambos.

    def _check_user_company(self):
        """Odoo ``_check_user_company`` (``odoo19c: res_users.py:501-511``).

        ``@api.constrains('company_id', 'company_ids', 'active')``: para un
        usuario activo, su compañía por defecto tiene que estar entre las
        permitidas. Se porta como método explícito y se invoca desde
        ``clean()`` — Django no valida M2M en ``full_clean()`` porque la
        relación no existe hasta que la fila tiene PK.
        """
        if not self.active or self.company_id is None or self.pk is None:
            return
        if self.company_ids.filter(pk=self.company_id).exists():
            return
        allowed = ', '.join(
            self.company_ids.values_list('partner__name', flat=True)) or '—'
        raise ValidationError(
            'La compañía %(company)s no está entre las permitidas para el '
            'usuario %(user)s (%(allowed)s).' % {
                'company': self.company.partner.name,
                'user': self.login,
                'allowed': allowed,
            })

    def _get_company_ids(self):
        """Odoo ``_get_company_ids`` (``odoo19c: res_users.py:726-730``).

        La referencia filtra por ``('active', '=', True)`` — una compañía
        archivada no otorga acceso aunque siga en la tabla de relación. La
        propia va primero, porque ``env.company`` es la primera activada.
        """
        if self.pk is None:
            return ()
        activas = tuple(
            self.company_ids.filter(active=True).values_list('pk', flat=True))
        if self.company_id is None:
            return activas
        return (self.company_id,) + tuple(
            pk for pk in activas if pk != self.company_id)

    def clean(self):
        super().clean()
        self._check_user_company()
        self._check_disjoint_groups()

    # ------------------------------------------------------------------
    # Las tres restricciones de integridad — ≙ :535-556 y :647-660
    # ------------------------------------------------------------------

    def _check_disjoint_groups(self):
        """≙ ``_check_disjoint_groups`` (``odoo19c: res_users.py:535-548``).

        Su docstring dice qué protege, y vale igual aquí: *"We check that no
        users are both portal and users (same with public). This could
        typically happen because of implied groups."*

        Un usuario en dos clases a la vez rompe todo lo que decide por clase —
        empezando por ``share``, que es literalmente «no es interno». La fuente
        resuelve las clases con tres xmlid reservados; aquí son los valores de
        ``ResGroups.user_type``, que es el mismo eje declarado de otra forma
        (ver el comentario de :meth:`_has_user_type`).

        Se invoca desde :meth:`clean`, no como decorador: Django no valida M2M
        en ``full_clean()`` porque la relación no existe hasta que hay PK — es
        la misma razón por la que ``_check_user_company`` se porta así.
        """
        if self.pk is None:
            return
        classes = set(
            self.group_ids.exclude(user_type__isnull=True)
            .values_list('user_type', flat=True))
        if len(classes) > 1:
            raise ValidationError(
                'El usuario %(user)s no puede estar a la vez en clases '
                'excluyentes: %(classes)s.' % {
                    'user': self.login,
                    'classes': ', '.join(sorted(classes)),
                })

    @classmethod
    def _check_at_least_one_administrator(cls):
        """≙ ``_check_at_least_one_administrator`` (``:550-555``).

        *"You must have at least an administrator user."* — quitarle el último
        grupo de sistema al último administrador deja la instalación sin quién
        la administre, y sin nadie que pueda devolverlo.

        La fuente se exime durante la actualización del módulo ``base``
        (``if not self.env.registry._init_modules: return``), porque a mitad de
        una migración el estado intermedio puede no tener administrador. Aquí
        el equivalente es la siembra: mientras no exista **ningún** grupo de
        sistema, no hay restricción que aplicar — el árbol todavía no llegó al
        punto en que la pregunta tiene sentido.
        """
        data_model = apps.get_model('base', 'IrModelData')
        system_group = data_model.ref(GROUP_SYSTEM_XMLID, raise_if_not_found=False)
        if system_group is None:
            return
        if not system_group.all_user_ids.exists():
            raise ValidationError(
                'Debe quedar al menos un usuario administrador.')

    def delete(self, *args, **kwargs):
        """≙ ``_unlink_except_master_data`` (``odoo19c: res_users.py:647-660``).

        Los usuarios de sistema no se borran. La fuente protege cuatro y da su
        razón para cada uno; se conservan los tres que este árbol tiene:

        - el **super-usuario** — *"it is used internally for resources created
          by Odoo (updates, module installation, ...)"*;
        - el **administrador** — *"it is utilized in various places (such as
          security configurations,...). Instead, archive it."*;
        - el **usuario público** — *"Deleting the public user is not allowed.
          Deleting this profile will compromise critical functionalities."*

        El cuarto de la fuente no se porta: BLOQUEADO por
        ``base.template_portal_user_id`` — es la plantilla de usuario portal de
        su asistente de invitación, y este árbol invita por endpoint, así que
        esa fila no existe. No es omisión: no hay a quién proteger.

        El cuerpo de la guarda **no vive aquí**: vive en
        :func:`_forbid_deleting_master_data`, un receptor de ``pre_delete``.
        Sobrescribir ``delete()`` sólo cubría la instancia, y el borrado en
        lote por ``QuerySet.delete()`` se saltaba la protección — que es
        justo lo que ``@api.ondelete`` **no** deja pasar en la fuente.

        Este método se conserva porque el árbol lo llama y porque su docstring
        es donde vive la razón de cada usuario protegido; la verificación la
        hace la señal, en los dos caminos.
        """
        return super().delete(*args, **kwargs)

    @classmethod
    def _check_company_domain(cls, companies):
        """≙ ``_check_company_domain`` (``odoo19c: res_users.py:169-173``).

        El predicado con que ``check_company`` valida a un usuario contra un
        conjunto de empresas. La fuente lo redefine **aquí** porque el default
        del ORM compara ``company_id`` —la empresa por defecto— y para un
        usuario la pregunta correcta es por ``company_ids``: el usuario es
        válido si **alguna** de sus empresas permitidas está en el conjunto.

        Sin empresas que exigir, la fuente devuelve ``Domain.TRUE``; el
        equivalente es un ``Q()`` vacío, que Django trata como «sin filtro».
        """
        if not companies:
            return Q()
        if isinstance(companies, str):
            ids = [companies]
        elif hasattr(companies, 'values_list'):
            ids = list(companies.values_list('pk', flat=True))
        else:
            ids = [getattr(c, 'pk', c) for c in companies]
        return Q(company_ids__in=ids)

    # ------------------------------------------------------------------
    # El punto de enganche de la cuenta propia — ``odoo19c: res_users.py:
    # 175-196``. Enterprise 19 lo extiende **13 veces** en 7 addons, más que
    # ningún otro símbolo de ``base`` (tarea #67); es el punto de extensión
    # más usado de este modelo y por eso existe como propiedad y no como
    # constante.
    # ------------------------------------------------------------------
    @property
    def SELF_READABLE_FIELDS(self):
        """≙ ``SELF_READABLE_FIELDS`` (``odoo19c: res_users.py:175-186``).

        Los campos que un usuario puede leer de **su propio** registro. La
        fuente lo dice en su docstring: *"In order to add fields, please
        override this property on model extensions"* — es un punto de
        extensión, y el modo de extenderlo es sumar a lo que devuelve
        ``super()``, nunca reemplazarlo.

        **Se declara aquí aunque el canal RPC crudo no exista.** El docstring
        de este archivo lo daba por bloqueado por esa razón, y era una
        afirmación falsa sobre el árbol: ``addons/hr`` ya lo implementaba
        —``hr/models/res_users.py:240``— con la nota *"sin base que extender"*.
        Dos referentes que se contradecían, y el coste no era teórico: sin base
        que extender, **dos addons que lo declararan se pisarían**, porque cada
        uno devuelve su lista entera en vez de sumarla. Ver la tarea #66.

        La lista se porta verbatim salvo los campos que este árbol no tiene, y
        cada ausencia se nombra: ``tz_offset`` (derivado que no declaramos),
        ``action_id`` (BLOQUEADO por ``ir.actions.act_window``, ver el bloque 3
        del docstring de este archivo) y ``share`` (su noción de usuario
        compartido, que aquí resuelve ``_is_portal``).
        """
        return [
            'signature', 'company_id', 'login', 'email', 'name',
            'image_1920', 'image_1024', 'image_512', 'image_256', 'image_128',
            'lang', 'tz', 'group_ids', 'partner_id', 'write_date',
            'avatar_1920', 'avatar_1024', 'avatar_512', 'avatar_256',
            'avatar_128', 'device_ids', 'api_key_ids', 'phone', 'display_name',
        ]

    @property
    def SELF_WRITEABLE_FIELDS(self):
        """≙ ``SELF_WRITEABLE_FIELDS`` (``odoo19c: res_users.py:188-193``).

        Los que puede **escribir**. Subconjunto propio, no derivado del de
        lectura: la fuente los declara por separado y un campo legible no es
        por ello escribible.
        """
        return ['signature', 'company_id', 'email', 'name', 'image_1920',
                'lang', 'tz', 'api_key_ids', 'phone']

    @classmethod
    def _self_accessible_fields(cls):
        """≙ ``_self_accessible_fields`` (``odoo19c: res_users.py:195-201``).

        Los dos conjuntos, congelados. La fuente lo memoriza con su
        ``ormcache``; aquí no hay memo porque el cálculo son dos listas
        literales y sus extensiones — el costo que su caché amortiza es el de
        su ORM resolviendo la herencia, no el de construir la lista.
        """
        probe = cls()
        return (frozenset(probe.SELF_READABLE_FIELDS),
                frozenset(probe.SELF_WRITEABLE_FIELDS))

    @classmethod
    def _get_invalidation_fields(cls):
        """≙ ``_get_invalidation_fields`` (``odoo19c: res_users.py:735-740``).

        Los campos cuyo cambio jubila lo memorizado del usuario. La fuente los
        cruza contra las claves escritas en su ``write`` —``if
        invalidation_fields & vals.keys(): registry.clear_cache()``
        (``:641-643``)— y con eso purga el registro entero.

        Se portan **los seis que declara** más los de sesión, aunque aquí sólo
        ``group_ids`` entre en el cómputo de la clausura: el conjunto es un
        **punto de extensión**, igual que :meth:`_get_session_token_fields`, y
        recortarlo a lo que hoy se usa lo convertiría en una lista privada de
        este memo. ``lang``, ``tz`` y las dos de empresa gobiernan otras
        memorizaciones que la fuente tiene y este árbol todavía no.
        """
        return {
            'group_ids', 'active', 'lang', 'tz', 'company_id', 'company_ids',
            *cls._get_session_token_fields(),
        }

    def _get_group_ids(self):
        """≙ ``_get_group_ids`` (``odoo19c: res_users.py:1098-1104``).

        Los ids de **todos** los grupos del usuario, implicados incluidos. Es
        el mismo conjunto que :attr:`all_group_ids` expone como registros; la
        fuente declara las dos formas porque su ``ormcache`` guarda ids, no
        recordsets.

        **Memorizado**, como allá. Lo que aquí es distinto es la forma del
        invalidador, no su existencia: la fuente purga el registro entero desde
        su ``write``; aquí purgan las señales del ORM —``post_save`` del
        usuario, ``m2m_changed`` de ``group_ids`` por los dos lados— y el
        contador de generación del grafo de implicación (ver
        ``_invalidate_group_ids``).

        **Sin PK no se memoriza.** Es la misma decisión que la fuente escribe
        en el consumidor: *"for new record don't fill the ormcache"*
        (``:1095-1096``). Una clave con ``None`` colisionaría entre todos los
        usuarios sin guardar.
        """
        if self.pk is None:
            return []
        key = _group_ids_cache_key(self.pk)
        ids = cache.get(key)
        if ids is None:
            ids = list(self.all_group_ids.values_list('pk', flat=True))
            cache.set(key, ids, _GROUP_IDS_CACHE_TTL)
        return ids

    # --- Presentación ---
    def get_full_name(self):
        return self.partner.name

    def get_short_name(self):
        return self.partner.name.split(' ', 1)[0] if self.partner.name else ''

    def deactivate(self, reason):
        """Desactiva la cuenta registrando la causa."""
        self.active = False
        self.deactivated_reason = reason
        self.deactivated_at = timezone.now()
        self.save(update_fields=[
            'active', 'deactivated_reason', 'deactivated_at', 'updated_at',
        ])

    # --- Pertenencia a grupo por identificador externo (≙ :1034-1096) ---
    #
    # La referencia resuelve el xmlid contra
    # ``res.groups._get_group_definitions().get_id(...)``, una caché del grafo
    # de grupos que este árbol no tiene. Aquí la resolución va por
    # ``ir.model.data`` —el mismo camino que ``env.ref`` toma allá— y la
    # clausura transitiva sale de ``ResGroups.all_implied_by_ids``, que ya
    # estaba portada.
    #
    # El puente entre ambas es una identidad, no una aproximación: la fuente
    # pregunta ``group_id in user.all_group_ids`` con
    # ``all_group_ids = group_ids.all_implied_ids`` (``:447-449``), es decir
    # «¿algún grupo mío implica a G?». Leída desde G, esa misma arista es
    # ``G.all_implied_by_ids``. Es exactamente el cómputo que
    # ``ResGroups.all_user_ids`` ya hacía en este árbol, visto desde el
    # usuario en vez de desde el grupo.
    #
    # ``ResGroups`` se resuelve por el registro de apps y no por import:
    # ``res_groups.py`` importa ``ResUsers`` para declarar su M2M, así que un
    # import en esta dirección cerraría el ciclo. Mismo criterio —y mismo
    # mecanismo— que ``_partner_model()`` de arriba.

    @property
    def all_group_ids(self):
        """≙ ``all_group_ids`` (``:258-259``) — los grupos del usuario, cerrados
        transitivamente.

        La fuente lo declara como ``Many2many`` calculado, y su cómputo es una
        línea: ``user.all_group_ids = user.group_ids.all_implied_ids``
        (``_compute_all_group_ids``, ``:447-449``). Aquí es una ``property``
        sobre la misma clausura ya portada — mismo resultado, sin motor de
        cómputo almacenado.

        Es **reflexiva**: incluye los grupos propios del usuario, no sólo los
        implicados. Lo garantiza ``ResGroups._closure``, cuyo BFS marca cada
        semilla como visitada antes de expandirla.

        ``ResGroups`` se resuelve por el registro de apps y no por import, por
        la misma razón que el bloque de arriba: ``res_groups.py`` importa
        ``ResUsers`` para declarar su M2M, así que un import en esta dirección
        cerraría el ciclo. Mismo mecanismo que ``_partner_model()``.

        Su primer consumidor es ``ResUsersApikeys._check_expiration_date``, que
        lee ``api_key_duration`` de estos grupos.
        """
        groups = apps.get_model('base', 'ResGroups')
        seeds = list(self.group_ids.all())
        return groups.objects.filter(
            pk__in=groups._closure(seeds, lambda g: g.implied_ids.all()))

    def has_groups(self, group_spec: str) -> bool:
        """¿Satisface ``self`` las restricciones de grupo de ``group_spec``?

        Verdadero cuando el usuario pertenece a **al menos uno** de los grupos
        positivos y a **ninguno** de los precedidos por ``!``.

        ``group_spec`` es una lista separada por comas de identificadores
        externos totalmente calificados, cada uno opcionalmente precedido por
        ``!`` — p. ej. ``"base.group_user,base.group_portal,!base.group_system"``.

        Tres detalles de la fuente que se conservan porque cambian el
        resultado, no la forma:

        - El punto solo (``"."``) es falso por definición: es el marcador de
          "ningún grupo satisface esto" del cargador de vistas.
        - Los negativos se evalúan **primero**, por coste: un negativo que
          acierta corta sin tocar los positivos.
        - Un ``group_spec`` **sólo** de negativos que no aciertan es
          verdadero (``return not positives``). No es un caso de borde
          decorativo: ``"!base.group_system"`` significa "cualquiera que no
          sea administrador", y con la lectura contraria no designaría a nadie.

        Igual que en :meth:`has_group`, ``base.group_no_one`` no es efectivo
        aquí — ver el porqué en ese método.
        """
        if group_spec == '.':
            return False

        positives = []
        negatives = []
        for group_ext_id in group_spec.split(','):
            group_ext_id = group_ext_id.strip()
            if group_ext_id.startswith('!'):
                negatives.append(group_ext_id[1:])
            else:
                positives.append(group_ext_id)

        # Por coste, los negativos primero — verbatim de la fuente.
        if any(self.has_group(ext_id) for ext_id in negatives):
            return False
        if any(self.has_group(ext_id) for ext_id in positives):
            return True
        return not positives

    def has_group(self, group_ext_id: str) -> bool:
        """¿Pertenece ``self`` al grupo de ese identificador externo?

        ``group_ext_id`` va **totalmente calificado** (``modulo.ext_id``): no
        hay módulo implícito con el que completarlo.

        Dos diferencias con :meth:`_has_group`, y las dos son de la fuente:

        **1. La guarda de acceso.** La referencia levanta ``AccessError`` si
        quien llama no está elevado, no se está preguntando por sí mismo, y no
        es un usuario interno (``:1077-1080``); su comentario dice para qué:
        *"this prevents RPC calls from non-internal users to retrieve
        information about other users"*.

        Aquí el actor sale de ``orm.environments`` (``is_su`` / la PK del
        usuario en contexto), no de un ``env`` recibido. Eso añade un cuarto
        estado que la referencia no tiene: **no hay actor en contexto**. Le
        pasa a todo lo que corre fuera de una petición —cron, migraciones,
        tests— y se resuelve como permitido, porque ahí no existe la llamada
        RPC de la que la guarda protege. Denegarlo haría inusable el método
        justo donde nadie está autenticándose.

        **2. ``base.group_no_one``.** La fuente lo hace efectivo **sólo** en
        modo depuración (``result and bool(request and request.session.debug)``).
        Este árbol **no tiene modo desarrollador**: el matiz queda BLOQUEADO
        por ``request.session.debug`` — no existe tal interruptor aquí.
        Sucesor: tarea #450.

        Mientras tanto la decisión es **fail-closed y explícita**: este método
        devuelve ``False`` para ``base.group_no_one`` aunque el usuario esté en
        el grupo. Es la lectura fiel de "sólo efectivo en depuración" cuando no
        hay depuración, y **no es una precaución teórica**: el propio XML de la
        fuente declara ``group_no_one.implied_by_ids = [group_user,
        group_system]`` (``base_groups.xml:58``), así que **todo** usuario
        interno lo tiene por implicación. Sin el matiz, las funciones técnicas
        quedarían encendidas para todos y para siempre — que es exactamente lo
        que la comprobación de depuración impide allá.

        Quien necesite la pertenencia cruda tiene :meth:`_has_group`, que es
        justo el método que la fuente deja sin el matiz.
        """
        if not (is_su() or self._caller_may_query_groups()):
            raise AccessError(
                'has_group() sólo puede consultarse sobre el usuario actual.')
        if group_ext_id == GROUP_NO_ONE_XMLID:
            # Sin modo desarrollador el grupo nunca es efectivo (ver docstring).
            return False
        return self._has_group(group_ext_id)

    def _caller_may_query_groups(self) -> bool:
        """¿Puede el actor en contexto preguntar por los grupos de ``self``?

        **No es un símbolo de la referencia**: allá la condición cabe en la
        línea de la guarda porque ``self.env.user`` siempre existe. Aquí hay
        que distinguir el caso "sin actor" del caso "actor ajeno", y meter esa
        distinción dentro del ``if`` lo volvía ilegible.

        Sin actor en contexto → permitido (código de servidor, no RPC).
        Con actor → o es uno mismo, o es interno (``base.group_user``).
        """
        actor = get_current_user()
        if actor is None:
            return True
        if actor.pk == self.pk:
            return True
        return actor._has_group(GROUP_USER_XMLID)

    def _has_group(self, group_ext_id: str) -> bool:
        """Pertenencia cruda al grupo, sin guarda ni matiz de depuración.

        :param str group_ext_id: identificador externo (XML ID) del grupo,
           **totalmente calificado** (``modulo.ext_id``).
        :return: ``True`` si ``self`` es miembro del grupo, explícita o
           implícitamente (algún grupo suyo lo implica, directa o
           transitivamente).

        Devuelve ``False`` —en vez de fallar— cuando el identificador no
        resuelve, resuelve a algo que no es un grupo, o el usuario todavía no
        tiene PK. Es la misma postura fail-closed que la fuente da a un
        ``group_id`` ausente de ``all_group_ids``: un grupo que no existe no
        otorga pertenencia.

        **La pregunta se hace contra** :meth:`_get_group_ids`, como en la
        fuente (``group_id in self._get_group_ids()``, ``:1096``). Antes se
        hacía desde el otro extremo —``group.all_implied_by_ids`` y un
        ``.exists()`` sobre ``group_ids``—, que da **el mismo conjunto** (es la
        identidad que el bloque de arriba ya argumenta) y recorría la clausura
        entera en cada llamada: medido sobre una cadena de cinco grupos, **9
        consultas por llamada, sin amortizar**. Por el memo son 9 la primera y
        las del ``ref`` del xmlid después.
        """
        if self.pk is None:
            return False
        data_model = apps.get_model('base', 'IrModelData')
        group = data_model.ref(group_ext_id, raise_if_not_found=False)
        if not isinstance(group, apps.get_model('base', 'ResGroups')):
            return False
        return group.pk in self._get_group_ids()

    # --- Eje interno / portal / público (≙ res_users.py:1165-1179) ---
    #
    # La referencia resuelve ``_is_internal``/``_is_portal``/``_is_public``
    # como ``has_group(base.group_user | group_portal | group_public)`` —
    # tres xmlid fijos. Aquí el eje NO es un grupo con nombre reservado: cada
    # ``res.groups`` declara su ``user_type`` (``ResGroups.USER_TYPE_*``), y
    # dos tipos distintos son disjuntos por construcción (ver
    # ``res_groups.py``). Así que "es interno" = "pertenece a ≥1 grupo cuyo
    # ``user_type`` es 'internal'". Esto es lo que el eje interno/portal
    # necesitaba y no existía: los consumidores (p. ej.
    # ``authz_totp_mail.totp_mail_policy_applies``, la re-ruta de invitación
    # por audiencia, los puentes ``_portal``) usaban ``partner.employee`` como
    # proxy — este es el criterio real.

    def _has_user_type(self, user_type):
        """True si pertenece a algún grupo con ese ``user_type``.

        ``group_ids`` es el reverso del M2M declarado en ``res_groups.py``
        (``related_name='group_ids'``); su ``user_type`` es la Selection de
        ``ResGroups.USER_TYPE_CHOICES``.
        """
        return self.group_ids.filter(user_type=user_type).exists()

    def _is_internal(self):
        """≙ ``_is_internal`` (res_users.py:1165-1167)."""
        return self._has_user_type('internal')

    def _is_portal(self):
        """≙ ``_is_portal`` (res_users.py:1169-1171)."""
        return self._has_user_type('portal')

    def _is_public(self):
        """≙ ``_is_public`` (res_users.py:1173-1175)."""
        return self._has_user_type('public')

    def _is_system(self):
        """≙ ``_is_system`` (``odoo19c: res_users.py:1177-1179``).

        Pertenencia a ``base.group_system`` — el grupo de administración del
        sistema. A diferencia de los tres de arriba, **no** se resuelve por
        ``user_type``: los tres anteriores preguntan por la *clase* de usuario
        (interno / portal / público), que la fuente resuelve por grupo y este
        árbol por la Selection ``ResGroups.user_type``. Éste pregunta por un
        grupo **concreto**, así que va por ``_has_group``.

        Se usa ``_has_group`` y no ``has_group`` a propósito: la fuente
        antepone ``.sudo()``, que salta su guarda de acceso, y el equivalente
        exacto de esa elevación es el método sin la guarda.
        """
        return self._has_group(GROUP_SYSTEM_XMLID)

    def _is_admin(self):
        """≙ ``_is_admin`` (``odoo19c: res_users.py:1181-1183``).

        El super-usuario **o** el administrador funcional. La fuente evalúa en
        ese orden y aquí también: ``_is_superuser`` no consulta la base.
        """
        return self._is_superuser() or self._has_group(GROUP_ERP_MANAGER_XMLID)

    def _is_superuser(self):
        """≙ ``_is_superuser`` (``odoo19c: res_users.py:1185-1187``).

        Identidad por id, no por grupo: ``SUPERUSER_ID`` es el 1 codificado que
        ``orm/utils.py`` ya declara con la misma razón que la fuente.

        NO es el ``is_superuser`` de Django: ese flag no existe en este modelo
        —la cabecera de la clase lo declara— porque la autorización va por
        capacidad (DEC-11), no por banderas del usuario.
        """
        return self.pk == SUPERUSER_ID

    @classmethod
    def get_company_currency_id(cls):
        """≙ ``get_company_currency_id`` (``odoo19c: res_users.py:1189-1191``).

        La moneda de la empresa activa. La fuente la lee de ``self.env.company``
        —la empresa del entorno de la petición— y aquí sale de la misma
        ``ContextVar`` que el resto del árbol usa para el alcance por empresa.

        Devuelve ``None`` cuando no hay empresa en contexto; la fuente no tiene
        ese caso porque su ``env.company`` siempre resuelve, y allá el
        equivalente sería un ``env`` sin empresa, que su ORM no admite.
        """
        company = get_current_company()
        return getattr(getattr(company, 'currency', None), 'pk', None)

    @property
    def share(self):
        """≙ ``_compute_share`` (res_users.py:460-464): compartido = NO
        interno. Un usuario sin ningún grupo de tipo es 'share' (portal/
        público), igual que la referencia marca ``share=True`` a todo lo que
        no está en ``group_user``."""
        return not self._is_internal()

    # ------------------------------------------------------------------
    # Segundo factor — el eslabón BASE de una cadena de tres
    #
    # Los TRES métodos devuelven ``None`` a propósito: son el fondo sobre el
    # que cada addon de 2FA aporta lo suyo. La referencia declara aquí los dos
    # primeros con el mismo cuerpo vacío
    # (``odoo19c: odoo/addons/base/models/res_users.py:1313,1317`` —
    # ``_mfa_type`` y ``_mfa_url``), y los extiende dos veces:
    #
    #   base (None) → auth_totp ('totp') → auth_totp_mail ('totp_mail')
    #
    # Cada eslabón consulta ``super()`` PRIMERO y sólo aporta si el interno
    # calló, así que la precedencia la gana el más interno. Aquí eso se
    # expresa con ``combine=keep_previous`` en ``extend_model`` — ver
    # ``orm.method_chain.keep_previous``, que documenta por qué el relevo por
    # defecto daría la precedencia contraria.
    #
    # El tercero NO lleva ``keep_previous``, y la asimetría es del propósito,
    # no un descuido: los dos primeros **eligen un valor** —hay una precedencia
    # que decidir— mientras que el tercero es un **efecto** que devuelve
    # ``None`` siempre. Con el relevo por defecto, cada eslabón corre y luego
    # cae en el anterior, que es lo que un aviso quiere: si mañana un segundo
    # método de 2FA quisiera avisar a su manera, los dos avisos salen.
    # ------------------------------------------------------------------

    def _mfa_type(self):
        """Si hay un método de MFA activo, devuelve su tipo como cadena."""
        return

    def _mfa_url(self):
        """Si hay un método de MFA activo, devuelve la URL de su segundo paso."""
        return

    def _notify_security_new_connection(self, request):
        """Avisa al titular si la credencial se aceptó en un dispositivo nuevo.

        Tercer eslabón vacío de la misma familia, y **la referencia NO lo
        declara aquí**: lo declara sólo en ``auth_totp_mail``
        (``odoo19c: auth_totp_mail/models/res_users.py:50-67``), porque allá el
        punto de extensión ya es un método de modelo de este archivo —
        ``authenticate`` (``:1240``), que el addon envuelve con ``super()``.

        Aquí el punto de entrada del login es una **vista DRF**
        (``addons/web/controllers/session.py::session_authenticate``), no un
        método de ``res.users``. Una vista no se encadena, así que la costura
        tiene que ser algo que la vista pueda **llamar** — y va donde ya están
        las otras dos de MFA, para que ``web`` siga preguntándole a la cadena
        sin conocer a ningún addon de 2FA.

        El parámetro es la segunda divergencia, y también es del stack: la
        fuente lee la petición de su ``request`` de hilo
        (``odoo.http.request``) y recibe ``auth_info`` para resolver al usuario.
        Aquí no hay tal proxy —medido: 0 símbolos de petición ambiental en
        ``src/orm`` y ``src/tools``— así que la petición se pasa explícita y el
        usuario es ``self``, igual que en ``_mfa_type``/``_mfa_url``.
        """
        return

    @classmethod
    @contextlib.contextmanager
    def _assert_can_auth(cls, user=None):
        """≙ ``_assert_can_auth`` (``odoo19c: res_users.py:1214-1281``).

        Enfriamiento lineal de acceso: tras N fallos consecutivos desde el
        mismo origen, los intentos se **ignoran** durante un plazo y se
        registran. Es un gestor de contexto, igual que en la fuente, para que
        envuelva al procedimiento de acceso sin que éste tenga que invocarlo.

        Fuera de una petición no hay origen que contar, así que cede el paso —
        la fuente hace lo mismo con ``if not request``. Eso deja al cron y al
        arranque fuera del limitador a propósito.

        DIVERGENCIA, y es del stack: la fuente lee su ``request`` de hilo
        (``odoo.http.request``); aquí el equivalente es la ``ContextVar`` que
        ``ir_http`` fija por petición (``get_current_request()``). Mismo
        alcance —una petición, un valor— y el mismo desenlace cuando no hay
        ninguna.

        DIVERGENCIA DE FIRMA, declarada: la fuente lo declara método de
        instancia —``_assert_can_auth(self, user=None)``— porque allá se llama
        sobre un recordset, que puede estar vacío: ``self.env['res.users']``
        es el modelo y ``user`` es un registro, y los dos aceptan la misma
        llamada. Aquí no existe el recordset vacío, así que lo que la fuente
        invoca sobre el modelo se declara ``classmethod`` — la forma que este
        árbol ya usa para ese caso: **126** en ``base/models``, entre ellas
        ``SystemParameter._get_param``, que es el análogo exacto de
        ``self.env['ir.config_parameter'].sudo()``. Los dos puntos de llamada
        de la fuente siguen valiendo: ``ResUsers._assert_can_auth(...)`` sobre
        la clase y ``usuario._assert_can_auth(...)`` sobre una instancia
        resuelven al mismo método.

        :param user: id o login, sólo para el registro.
        """
        request = get_current_request()
        if request is None:
            yield
            return

        source = _client_ip(request)
        failures, previous = _LOGIN_FAILURES.get(source, (0, datetime.datetime.min))
        if cls._on_login_cooldown(failures, previous):
            _logger.warning(
                "Intento de acceso ignorado para %s (usuario %r): "
                "%d fallo(s) desde el último acierto, el último a las %s. "
                "El número de fallos antes del enfriamiento y su duración se "
                "configuran en los parámetros del sistema; para desactivarlo, "
                "poner `base.login_cooldown_after` a 0.",
                source, user or "?", failures, previous)
            # El aviso del proxy mal configurado es de la fuente, y es útil:
            # si la IP limitada es privada, lo más probable es que se esté
            # contando la del proxy inverso y no la del cliente — con lo que
            # el limitador castiga a todo el mundo a la vez.
            try:
                is_private = ipaddress.ip_address(source).is_private
            except ValueError:
                is_private = False
            if is_private:
                _logger.warning(
                    "La IP limitada %s es privada y *podría* ser un proxy. Si "
                    "este servicio corre detrás de un proxy inverso, revisar "
                    "que reenvíe X-Forwarded-For y que se esté leyendo.",
                    source)
            raise AccessDenied(
                'Demasiados intentos fallidos, espera un poco antes de volver '
                'a intentarlo.')

        try:
            yield
        except AccessDenied:
            failures, __ = _LOGIN_FAILURES.get(source, (0, datetime.datetime.min))
            _LOGIN_FAILURES[source] = (failures + 1, datetime.datetime.now())
            raise
        else:
            _LOGIN_FAILURES.pop(source, None)

    @classmethod
    def _on_login_cooldown(cls, failures, previous):
        """≙ ``_on_login_cooldown`` (``odoo19c: res_users.py:1283-1306``).

        Decide si el origen está en enfriamiento. Es el punto de extensión que
        la fuente separa a propósito: para cambiar el **criterio** se
        sobrescribe esto; para cambiar el **almacén** —a base de datos o a una
        caché compartida— se sobrescribe ``_assert_can_auth``.

        ``base.login_cooldown_after`` a 0 desactiva el mecanismo entero, y es
        la vía documentada para hacerlo.

        :param int failures: fallos registrados desde el último acierto.
        :param previous: marca de tiempo del fallo anterior.
        :returns: si el origen está en enfriamiento.
        """
        icp = apps.get_model('base', 'SystemParameter')
        try:
            min_failures = int(icp.get_param('base.login_cooldown_after', 5))
        except (TypeError, ValueError):
            min_failures = 5
        if min_failures == 0:
            return False

        try:
            delay = int(icp.get_param('base.login_cooldown_duration', 60))
        except (TypeError, ValueError):
            delay = 60
        return (failures >= min_failures
                and (datetime.datetime.now() - previous)
                < datetime.timedelta(seconds=delay))

    # ------------------------------------------------------------------
    # El procedimiento de acceso — ≙ ``:742-827``
    # ------------------------------------------------------------------

    def _update_last_login(self):
        """≙ ``_update_last_login`` (``odoo19c: res_users.py:742-746``).

        Deja constancia del acceso creando **una fila nueva** en
        ``res.users.log``. El comentario de la fuente explica por qué crea en
        vez de actualizar, y vale igual aquí: *"only create new records to
        avoid any side-effect on concurrent transactions"* — dos accesos
        simultáneos del mismo usuario no compiten por la misma fila. El exceso
        lo recorta ``ResUsersLog._gc_user_logs``, que conserva la última.

        DIVERGENCIA DE MECANISMO, declarada: la fuente crea el registro vacío y
        su ORM lo puebla con los campos mágicos ``create_uid``/``create_date``.
        Aquí ``create_uid`` es la FK ``user``, que se pasa explícita; la fecha
        la pone ``TimeStampedModel``.

        DIVERGENCIA DE FIRMA, declarada: la fuente lo declara ``@api.model`` y
        resuelve el actor desde el entorno del recordset. Aquí no hay entorno,
        así que el actor es ``self`` — y es el mismo dato: sus dos puntos de
        llamada (``_login`` y el RPC) lo invocan sobre el usuario que acaba de
        entrar, que es exactamente lo que su ``create_uid`` acaba valiendo.
        """
        ResUsersLog.objects.create(user=self)

    @classmethod
    def _get_login_domain(cls, login):
        """≙ ``_get_login_domain`` (``:748-750``) — cómo se busca al usuario.

        Punto de extensión de la fuente: un addon que admita entrar con el
        correo lo ensancha aquí. ``Domain('login', '=', login)`` es
        ``Q(login=login)``; el ``Domain`` de la referencia y el ``Q`` de Django
        son el mismo objeto de predicado componible.
        """
        return Q(login=login)

    @classmethod
    def _get_email_domain(cls, email):
        """≙ ``_get_email_domain`` (``:752-754``) — búsqueda por correo.

        La fuente usa ``=ilike`` con ``tools.escape_psql`` sobre el valor: el
        escape existe porque ``ilike`` interpreta ``%`` y ``_`` como comodines
        y un correo puede llevarlos. El equivalente exacto es ``__iexact``,
        que compara sin distinguir mayúsculas y **sin** interpretar comodines,
        así que no hay nada que escapar — Django parametriza la consulta.

        DIVERGENCIA DE MECANISMO, declarada, y es la frontera de ``_inherits``:
        allá ``email`` es un campo **delegado** de ``res.users``, así que su
        ``Domain('email', …)`` lo busca como si fuera columna propia. Aquí la
        delegación (``orm/inherits.py``) resuelve **atributos**, no lookups de
        consulta: ``user.email`` lee, pero ``Q(email=…)`` no resuelve. El
        equivalente que sí consulta es recorrer la FK — ``partner__email``.
        """
        return Q(partner__email__iexact=email or '')

    @classmethod
    def _get_login_order(cls):
        """≙ ``_get_login_order`` (``:756-758``) — el orden del desempate.

        La fuente devuelve ``self._order``; aquí es ``Meta.ordering``, que ya
        lleva el ``'name, login'`` de la referencia traducido
        (``['partner__name', 'login']``). Importa cuando el dominio de acceso
        devuelve más de una fila: decide **cuál** de ellas autentica.
        """
        return tuple(cls._meta.ordering or ())

    @classmethod
    def _login(cls, credential, user_agent_env):
        """≙ ``_login`` (``odoo19c: res_users.py:760-781``).

        Resuelve la credencial a un usuario, con el limitador de acceso
        envolviendo el intento. Los cuatro pasos de la fuente se conservan:
        el gestor de contexto ``_assert_can_auth``, la búsqueda por
        ``_get_login_domain`` con ``_get_login_order``, la verificación de la
        credencial, y el registro del acceso.

        **Cierra la tarea #26**: ``_assert_can_auth`` se portó con la familia
        de claves de API y hasta hoy sólo tenía allí consumidor. El acceso por
        contraseña —el que la fuente protege— pasaba sin contar fallos.

        DIVERGENCIA DE MECANISMO, declarada, y es la que ``authz_ldap`` ya tenía
        escrita: la fuente verifica con ``_check_credentials``, que es la
        cadena que sus addons extienden con ``super()``; aquí esa cadena son
        los ``AUTHENTICATION_BACKENDS``
        (``addons/authz_ldap/models/res_users.py:9-12`` lo declara verbatim:
        *"la cadena ``AUTHENTICATION_BACKENDS`` ES la cadena de
        ``super()._login`` de Odoo"*). Por eso la verificación delega en
        ``django_authenticate``, que recorre local → LDAP → OAuth → passkey, y
        no en ``_check_credentials`` a secas, que sólo es el eslabón de
        contraseña.

        El ``auth_info`` que la fuente devuelve lo construye el eslabón
        terminal (``_check_credentials``), así que aquí se reconstruye con el
        ``backend`` que ``django_authenticate`` dejó puesto — el dato
        equivalente a su ``auth_method``.

        :param dict credential: ``{'type', 'login', 'password'}``.
        :param dict user_agent_env: entorno de la petición; ``interactive``.
        :raises AccessDenied: credencial inválida, o origen en enfriamiento.
        :returns: ``auth_info`` — ``{'uid', 'auth_method', 'mfa', 'user'}``.
        """
        login = credential['login']
        request = get_current_request()
        source = _client_ip(request) if request is not None else 'n/a'
        try:
            with cls._assert_can_auth(user=login):
                user = django_authenticate(
                    request,
                    username=login,
                    password=credential.get('password'),
                    **{k: v for k, v in credential.items()
                       if k not in ('type', 'login', 'password')})
                if user is None:
                    raise AccessDenied()
                auth_info = {
                    'uid': user.pk,
                    'auth_method': getattr(user, 'backend', None) or 'password',
                    'mfa': 'default',
                    'user': user,
                }
                cls._set_tz_from_request(user, request)
                user._update_last_login()
        except AccessDenied:
            _logger.info("Login failed for login:%s from %s", login, source)
            raise

        _logger.info("Login successful for login:%s from %s", login, source)
        return auth_info

    @staticmethod
    def _set_tz_from_request(user, request):
        """≙ las cuatro líneas de zona horaria de ``_login`` (``:772-775``).

        *"first login or missing tz -> set tz to browser tz"*. Se extrae a un
        método propio porque aquí ``tz`` no vive en ``res_users``: llega por la
        delegación ``_inherits`` al partner, y la escritura la enruta
        ``orm/inherits.py``. Dejarlo en línea escondería esa indirección.

        DIVERGENCIA DE STACK, declarada: la fuente valida contra
        ``pytz.all_timezones``; ``pytz`` no está instalado —medido— y el
        equivalente de la biblioteca estándar es
        ``zoneinfo.available_timezones()``, que lee la misma base de datos IANA.

        Y ``not user.login_date`` de la fuente se lee aquí sobre
        ``res.users.log``: allá ``login_date`` es un campo **relacionado** a la
        fecha de creación de esa misma tabla (``:229``), así que «nunca ha
        entrado» es «no tiene filas de acceso». NO se lee sobre ``last_login``,
        que es el campo de Django y aquí **nadie lo escribe** — leerlo daría
        siempre vacío y la zona se sobreescribiría en cada acceso, que es lo
        contrario de lo que la condición pide.

        El orden importa y es el de la fuente: esto corre **antes** de
        ``_update_last_login``, así que en el primer acceso todavía no hay fila.
        """
        if request is None:
            return
        tz = request.COOKIES.get('tz')
        if tz and tz in available_timezones() and (
                not user.tz or not user.logs.exists()):
            user.tz = tz
            user.save()

    @classmethod
    def authenticate(cls, credential, user_agent_env):
        """≙ ``authenticate`` (``odoo19c: res_users.py:784-810``).

        Envoltura pública de ``_login``. Su único aporte propio es adivinar la
        URL base al entrar un usuario del grupo de sistema, para que los
        enlaces que el servidor genera apunten a donde el usuario realmente
        llegó — y sólo si nadie la congeló con ``web.base.url.freeze``.

        La fuente traga cualquier excepción de ese bloque y la registra: fijar
        un parámetro de configuración no debe tumbar un acceso válido. Se
        conserva, con el mismo ``_logger.exception``.

        :param dict credential: ver ``_login``.
        :param dict user_agent_env: puede traer ``base_location``.
        :returns: ``auth_info`` de ``_login``.
        """
        auth_info = cls._login(credential, user_agent_env=user_agent_env)
        if user_agent_env and user_agent_env.get('base_location'):
            user = auth_info['user']
            if user._is_system():
                try:
                    icp = apps.get_model('base', 'SystemParameter')
                    if not icp.get_param('web.base.url.freeze'):
                        icp.set_param('web.base.url',
                                      user_agent_env['base_location'])
                except Exception:
                    _logger.exception(
                        "Failed to update web.base.url configuration parameter")
        return auth_info

    @classmethod
    def _check_uid_passwd(cls, uid, passwd):
        """≙ ``_check_uid_passwd`` (``odoo19c: res_users.py:813-827``).

        Verifica el par (id, contraseña) **sin abrir sesión**: es la guarda que
        el RPC usa antes de dejar pasar una llamada, y por eso su rechazo es
        una excepción y no un valor de retorno.

        Los tres rechazos de la fuente se conservan y en su orden: contraseña
        vacía —*"empty passwords disallowed for obvious security reasons"*—,
        usuario inactivo, y credencial incorrecta. El limitador envuelve los
        dos últimos, igual que en ``_login``; **cierra la otra mitad de #26**.

        DIVERGENCIA DE MECANISMO, declarada: la fuente memoriza el resultado con
        ``@tools.ormcache('uid', 'passwd')`` para no rehashear en cada llamada
        RPC. Aquí NO se memoriza, y la razón es de seguridad, no de alcance:
        guardar en caché un par (id, contraseña) es guardar la contraseña en
        claro en la memoria del proceso durante la vida de la entrada.

        Su segunda razón —*"el canal RPC de integración externa no está
        construido"*— **caducó al portarse #85** y se retira: el canal existe.
        Lo que no cambia es la primera, que es la que sostiene la divergencia.
        El coste del rehash por llamada queda como lo que es: el precio de no
        tener la contraseña en memoria.
        """
        if not passwd:
            raise AccessDenied()

        with cls._assert_can_auth(user=uid):
            user = cls.objects.filter(pk=uid).first()
            if user is None or not user.active:
                raise AccessDenied()
            credential = {
                'login': user.get_username(),
                'password': passwd,
                'type': 'password',
            }
            user._check_credentials(credential, {'interactive': False})


class ResUsersLog(TimeStampedModel):
    """``res.users.log`` — que hubo un acceso, no una auditoría.

    Fiel a ``odoo19c: odoo/addons/base/models/res_users.py:134-152``, y la
    fidelidad aquí **quita** cosas. La referencia declara **un solo campo**
    (``create_uid``) y se apoya en la fecha automática; su comentario lo dice::

        # Uses the magical fields `create_uid` and `create_date` for recording
        # logins. See `mail.presence` for more recent activity tracking.

    Y su ``_gc_user_logs`` conserva **una fila por usuario**, borrando el resto.
    No es un registro de auditoría: es un "último acceso" con historia mínima.

    El ``AuthEvent`` que murió con el addon ``users`` guardaba tipo de evento,
    IP y user-agent. Eso **no** vive aquí: la referencia lo pone en el
    dispositivo (``ResDeviceLog``: ``ip_address``, ``browser``, ``platform``).
    Portar ambos al mismo modelo habría fundido dos responsabilidades que la
    referencia mantiene separadas.
    """

    user = fields.Many2one(
        'base.ResUsers', on_delete=models.CASCADE, db_index=True,
        related_name='logs',
        help_text='Usuario que accedió (Odoo create_uid).',
    )

    class Meta:
        db_table            = 'res_users_log'
        ordering            = ['-id']
        verbose_name        = 'Registro de acceso'
        verbose_name_plural = 'Registros de acceso'

    def __str__(self) -> str:
        return f'acceso de {self.user_id} el {self.created_at}'

    @classmethod
    @api.autovacuum
    def _gc_user_logs(cls):
        """≙ ``_gc_user_logs`` (``odoo19c: res_users.py:143-152``).

        Conserva **la fila más reciente por usuario** y borra el resto. Es lo
        que hace de este modelo un "último acceso" y no una auditoría: la
        historia se recorta en cada barrido.

        La fuente lo resuelve con un ``DELETE ... WHERE EXISTS`` correlacionado
        sobre ``create_uid``/``create_date``. Aquí el mismo predicado se
        expresa con el ORM —una subconsulta correlacionada por ``user``, con
        ``id`` como desempate para las filas del mismo segundo— y el conteo
        sale del propio ``delete()``, que es el ``cr.rowcount`` de la fuente.
        """
        mas_nueva = cls.objects.filter(user=models.OuterRef('user')).order_by(
            '-created_at', '-id').values('id')[:1]
        deleted, _ = cls.objects.exclude(
            pk=models.Subquery(mas_nueva)).delete()
        _logger.info("GC'd %d user log entries", deleted)


# =========================================================================
# Soporte de claves de API — ≙ ``# API keys support`` (``:1518-1750``)
#
# La referencia declara este bloque **en este mismo archivo**, después de
# ``res.users``: constantes de módulo, el modelo ``res.users.apikeys``, la
# función ``_check_apikey_credentials`` y dos modelos transitorios de su
# formulario web. El sitio se conserva por
# ``atributos-de-clase-de-modelo.md`` cláusula 2 — inventar un
# ``res_users_apikeys.py`` habría creado un archivo que la referencia no
# tiene, que es el defecto de :ref:`h-api-578`.
#
# Su primer consumidor NO es la integración externa sino el **dispositivo de
# confianza** del segundo factor: ``auth_totp.device`` declara
# ``_inherit = ["res.users.apikeys"]`` y guarda ahí la cookie ``td_id``
# (``odoo19c: auth_totp/models/auth_totp.py:16``). Por eso este bloque entra
# con la tarea #716 y no con #490, que es la superficie RPC.
# =========================================================================

#: ≙ ``API_KEY_SIZE`` (``:1519``) — bytes de entropía de la clave.
API_KEY_SIZE = 20

#: ≙ ``INDEX_SIZE`` (``:1520``) — dígitos hexadecimales del prefijo indexado,
#: «4 bytes, o el 20 % de la clave». Es lo que permite buscar la fila sin
#: comparar el hash de todas.
INDEX_SIZE = 8

#: ≙ ``DEFAULT_PROGRAMMATIC_API_KEYS_LIMIT`` (``:1527``).
DEFAULT_PROGRAMMATIC_API_KEYS_LIMIT = 10


#: Limite de longitud del nombre de un indice, y NO es el de la fuente.
#:
#: DIVERGENCIA DEL STACK, declarada: la referencia acota a **63** —el limite de
#: identificador de PostgreSQL— y trunca por encima
#: (``odoo19c: res_users.py:1546-1550``). Django acota a **30** en su propio
#: check ``models.E034``, que es transversal a todos sus motores y por tanto
#: mas estricto que el del motor que usamos. Manda el mas estricto: por debajo
#: de 30 el nombre vale en los dos.
INDEX_NAME_MAX = 30


def index_name_for(table):
    """Nombre del indice ``(user_id, index)`` de una tabla de claves.

    Porta el algoritmo de la fuente **entero**, incluida su rama de
    truncamiento, que el porte anterior habia omitido: la fuente calcula
    ``<tabla>_user_id_index_idx`` y, si se pasa del limite, lo sustituye por
    ``<tabla>[:50] + "_idx_" + sha256(<tabla>)[:8]`` — determinista, para que
    dos arranques generen el mismo nombre.

    Omitir esa rama dejaba dos nombres de 35 y 34 caracteres, y con ellos
    ``manage.py migrate`` **abortaba** con ``models.E034`` antes de tocar la
    base. Es el desenlace que ``porte-completo-no-parcial.md`` describe: un
    porte parcial que pasa por completo hasta que algo lo ejerce.
    """
    name = f'{table}_user_id_index_idx'
    if len(name) > INDEX_NAME_MAX:
        return table[:50] + '_idx_' + hashlib.sha256(
            table.encode()).hexdigest()[:8]
    return name

#: ≙ ``KEY_CRYPT_CONTEXT`` (``:1521-1526``).
#:
#: La referencia usa ``passlib.CryptContext(['pbkdf2_sha512'],
#: pbkdf2_sha512__rounds=6000)`` y explica la elección: *"default is 29000
#: rounds which is 25~50ms, which is probably unnecessary given in this case
#: all the keys are completely random data: dictionary attacks on API keys
#: isn't much of a concern"*.
#:
#: ``passlib`` no está en este árbol (medido: 0 en ``pyproject.toml``); el
#: mecanismo equivalente son los *hashers* de Django, que este archivo ya usa
#: para la contraseña. Se instancia la clase directamente en vez de
#: registrarla en ``PASSWORD_HASHERS``: así el número de rondas queda atado a
#: **este** uso y no cambia el coste de verificar una contraseña.
#:
#: La familia cambia de ``sha512`` a ``sha256`` porque es la que Django trae;
#: el argumento de la referencia —entropía completa, no hay ataque de
#: diccionario— no distingue entre las dos.
KEY_HASHER = hashers.PBKDF2PasswordHasher()
KEY_HASHER_ITERATIONS = 6000


def _hash_api_key(key):
    """Codifica una clave con :data:`KEY_HASHER` — ≙ ``KEY_CRYPT_CONTEXT.hash``."""
    hasher = hashers.PBKDF2PasswordHasher()
    hasher.iterations = KEY_HASHER_ITERATIONS
    return hasher.encode(key, hasher.salt())


def _verify_api_key(key, encoded):
    """≙ ``KEY_CRYPT_CONTEXT.verify`` — comparación en tiempo constante."""
    return hashers.check_password(key, encoded)


class _ResUsersApikeysBase(TimeStampedModel):
    """Campos y mecanismo de ``res.users.apikeys`` — abstracta, sin tabla.

    Portación de ``odoo19c: odoo/addons/base/models/res_users.py:1519-1720``
    (LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

    **Por qué es abstracta.** La referencia declara un segundo modelo sobre
    éste: ``auth_totp.device`` lleva ``_name`` propio **y**
    ``_inherit = ["res.users.apikeys"]`` (``odoo19c:
    auth_totp/models/auth_totp.py:15-16``). Ese constructo es herencia por
    **prototipo**: el hijo copia campos y métodos y obtiene **tabla aparte**,
    no comparte filas con el padre. La forma Django del prototipo es una base
    abstracta, que es la misma adaptación que ``res_device.py`` ya hace para
    ``res.device`` sobre ``res.device.log``.

    Sus métodos son ``classmethod`` precisamente por esto: ``cls`` es el
    modelo sobre el que se invocan, así que ``auth_totp.device._generate``
    escribe en la tabla de dispositivos y ``res.users.apikeys._generate`` en la
    de claves, sin que ninguno de los dos sepa del otro. Es el mismo reparto
    que la fuente logra pasando el nombre de tabla a
    ``_check_apikey_credentials``.

    La FK a usuario **no** vive aquí: la declara cada concreto, para conservar
    su propio ``related_name`` (``api_keys`` / ``totp_trusted_devices``). Una
    base abstracta obligaría a nombrarlo con ``%(class)s``, que es lo que
    ``res_device.py`` evita por la misma razón.

    **Lo que la hace distinta de un token cualquiera** es el par
    ``index``/``key``: la clave completa **nunca** se guarda. Se guarda su
    hash (``key``) y su prefijo de 8 hexadecimales en claro (``index``), que
    es lo único por lo que se puede buscar. Sin ese prefijo habría que
    verificar el hash de cada fila de la tabla en cada petición.

    Divergencias declaradas
    =======================

    1. **``_auto = False`` y ``init()``.** La referencia desactiva la creación
       automática de tabla y la emite a mano con ``CREATE TABLE`` porque
       ``key`` e ``index`` **no pueden ser campos del ORM**: cualquier lectura
       genérica los expondría. Aquí el ORM es Django y la tabla la crea su
       migración, así que las dos columnas se declaran como campos y su
       protección es la misma que la del secreto TOTP
       (``authz_totp/models/totp_secret.py``): ningún serializer las nombra.

       El contenido de ``init()`` no se pierde — se reparte en su forma
       declarativa, que es lo que ``atributos-de-clase-de-modelo.md`` prescribe
       para los objetos de tabla:

       - ``CREATE INDEX … (user_id, index)`` → ``Meta.indexes``
       - ``CHECK (char_length(index) = 8)`` → ``Meta.constraints``
       - ``ON DELETE CASCADE`` sobre ``user_id`` → ``on_delete=CASCADE``

    2. **``remove()`` pierde su ``@check_identity``.** En la referencia el
       decorador vive en ``base`` y envuelve el método del modelo, porque su
       RPC expone modelos directamente. Aquí la identidad fresca la exige
       ``authz_reauth.assert_session_fresh`` desde la **vista** (DEC-12), y
       ``base`` no puede depender de ``authz_reauth`` sin invertir el grafo.
       Así que ``remove()`` y ``_remove()`` quedan como los dos métodos que la
       referencia declara —el público con su comprobación de propiedad, el
       interno sin ella— y el gate de identidad lo pone quien los exponga.

    3. **``_assert_can_auth`` — CERRADA, ya no es divergencia.** Era el
       limitador de intentos que la referencia envuelve alrededor de
       ``generate``/``revoke``, y al portar este bloque no existía aquí
       (medido entonces: 0 hits). Portado con la tarea **#726**:
       ``ResUsers._assert_can_auth`` y su ``_on_login_cooldown``, y los dos
       métodos ya lo envuelven. Lo que sí queda como divergencia declarada es
       **dónde vive el contador** — ver ``_LOGIN_FAILURES``.

    4. **El SQL crudo se expresa con el ORM.** La referencia lo necesita
       porque ``key``/``index`` no son campos suyos; aquí sí lo son, así que
       ``INSERT`` → ``objects.create``, el ``SELECT`` con ``JOIN res_users`` →
       ``filter(user__active=True, …)`` y el ``DELETE`` del barrido →
       ``.delete()``. Mismo predicado, misma semántica.

    5. **Los dos modelos de asistente NO se portan** —
       ``res.users.apikeys.description`` (``:1753``, transitorio, 6 defs) y
       ``res.users.apikeys.show`` (``:1837``, abstracto, 0 defs)—. Su cuerpo
       entero es la forma del diálogo del backoffice OWL: un selector de
       duración, un ``make_key`` que devuelve un ``ir.actions.act_window``
       hacia el segundo modelo, y un segundo modelo cuya única razón de existir
       es sostener un campo de sólo lectura dentro de esa ventana modal. Aquí
       el cliente es React (#488) y el equivalente es un endpoint que devuelve
       la clave en el cuerpo de la respuesta, con su ``@extend_schema`` y su
       gate de capacidad — sucesor **#490**.

       **Lo que NO es presentación se mide aparte**, porque un veredicto de
       "asistente" lo habría barrido con el resto:

       - el tope de duración por grupo (``api_key_duration``) **sí está
         portado**: ``_selection_duration`` sólo filtra la lista que ofrece,
         y la regla que decide vive en ``_check_expiration_date``;
       - ``check_access_make_key`` —*"Only internal users can create API
         keys"*— **no tiene contraparte todavía**. Es una regla de negocio, no
         de diálogo: la pone quien exponga el endpoint, y ``_is_internal()``
         ya existe en este árbol para expresarla.
    """

    name = fields.Char(
        verbose_name='Descripción',
        help_text='Odoo name ("Description") — para qué es esta clave.',
    )
    scope = fields.Char(
        null=True, blank=True,
        verbose_name='Ámbito',
        help_text='Odoo scope. NULL da acceso a cualquier RPC; con valor, '
                  'sólo a ese ámbito ("rpc", "browser").',
    )
    expiration_date = fields.Datetime(
        null=True, blank=True,
        verbose_name='Fecha de caducidad',
        help_text='Odoo expiration_date. NULL es una clave permanente, que '
                  'sólo un usuario de sistema puede crear.',
    )
    index = fields.Char(
        max_length=INDEX_SIZE, db_index=True,
        verbose_name='Prefijo',
        help_text='Odoo index — los primeros 8 hexadecimales de la clave, en '
                  'claro. Es por lo que se busca la fila; NO es la clave.',
    )
    key = fields.Char(
        verbose_name='Clave (hash)',
        help_text='Odoo key — el hash de la clave completa. SECRETO: ningún '
                  'serializer lo expone, igual que el secreto TOTP.',
    )

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return f'{self.name} ({self.index})'

    def remove(self):
        """≙ ``remove`` (``:1556-1558``) — el punto de entrada público.

        La referencia lo decora con ``@check_identity``; aquí ese gate vive en
        la vista (divergencia 2). El método se conserva porque la referencia
        declara **dos** —público e interno— y fundirlos borraría la distinción
        que su propio docstring explica.
        """
        return self._remove()

    def _remove(self):
        """≙ ``_remove`` (``:1559-1572``).

        Su docstring de la fuente, verbatim: *"Use the remove() method to
        remove an API Key. This method implement logic, but won't check the
        identity (mainly used to remove trusted devices)"* — y ese paréntesis
        es exactamente el consumidor que la tarea #716 desbloquea.
        """
        actor = get_current_user()
        if is_su() or self.user_id == getattr(actor, 'pk', None):
            _logger.info(
                "API key(s) removed: scope: <%s> for '%s' (#%s)",
                self.scope, getattr(actor, 'login', 'n/a'),
                getattr(actor, 'pk', None),
            )
            self.delete()
            return
        raise AccessError(
            'No puede retirar claves de API que no sean suyas, salvo que sea '
            'un usuario de sistema.'
        )

    @classmethod
    def _check_credentials(cls, *, scope, key):
        """≙ ``_check_credentials`` (``:1574-1575``).

        Es ``classmethod`` y no método de instancia porque la referencia lo
        llama sobre el modelo vacío (``self.env['res.users.apikeys']``), que
        aquí no tiene equivalente de instancia.
        """
        return _check_apikey_credentials(scope=scope, key=key, model=cls)

    @classmethod
    def _check_expiration_date(cls, date):
        """≙ ``_check_expiration_date`` (``:1577-1587``).

        Tres reglas de la fuente, conservadas: un usuario de sistema puede
        todo; el resto **debe** poner fecha; y esa fecha no puede exceder el
        máximo que sus grupos permitan (``api_key_duration``, en días).

        ``api_key_duration`` ya estaba portado en ``res.groups`` con un
        docstring que decía *"este árbol … no tiene API keys que lo
        consuman"*. Este método es ese consumidor — el stub deja de
        racionalizar su ausencia (:ref:`h-api-638`).
        """
        if is_su():
            return
        actor = get_current_user()
        if not date:
            raise ValidationError('La clave de API debe tener fecha de caducidad.')
        durations = [
            group.api_key_duration
            for group in actor.all_group_ids
            if group.api_key_duration
        ] if actor is not None else []
        max_duration = max(durations) if durations else 1.0
        if date > timezone.now() + timedelta(days=max_duration):
            raise ValidationError(
                f'No puede exceder {max_duration} días.'
            )

    @classmethod
    def _generate(cls, scope, name, expiration_date):
        """≙ ``_generate`` (``:1589-1616``) — genera una clave y la devuelve.

        Su docstring de la fuente conserva la advertencia que importa: *"This
        method must be called in sudo to use a duration greater than that
        allowed by the user's privileges. For a persistent key (infinite
        duration), no value for expiration date."*

        La clave en claro se devuelve **una sola vez**: lo que queda en la
        tabla es su hash. La fuente lo dice con un comentario en el sitio —
        *"no need to clear the LRU when adding a key, only when removing"*—
        que aquí no tiene receptor porque no hay caché de claves.
        """
        cls._check_expiration_date(expiration_date)
        k = binascii.hexlify(os.urandom(API_KEY_SIZE)).decode()
        actor = get_current_user()
        cls.objects.create(
            name=name,
            user_id=getattr(actor, 'pk', None),
            scope=scope,
            expiration_date=expiration_date or None,
            key=_hash_api_key(k),
            index=k[:INDEX_SIZE],
        )
        _logger.info(
            "%s generated: scope: <%s> for '%s' (#%s)",
            cls._description, scope, getattr(actor, 'login', 'n/a'),
            getattr(actor, 'pk', None),
        )
        return k

    @classmethod
    def check_access_make_key(cls):
        """≙ ``check_access_make_key`` (``odoo19c: res_users.py:1832-1834``).

        *"Only internal users can create API keys"*. Es la guarda de la vía
        **interactiva** —un usuario creando su primera clave— y es otra puerta
        que ``_ensure_can_manage_keys_programmatically``, que gobierna la vía
        **programática** (una clave viva generando otra). La referencia tiene
        las dos y no las confunde.

        Va aquí y **no dentro de ``_generate``**, que es donde la tentación
        estaría: la fuente la pone en ``make_key`` a propósito, porque
        ``_generate`` también sirve al dispositivo de confianza de 2FA, y ése
        lo usa un usuario de portal con todo derecho. Meter la guarda en la
        primitiva rompería ese flujo — medido: ``authz_totp`` lo llama con
        ``BROWSER_SCOPE`` para cualquier usuario que active el segundo factor.

        Su consumidor es el endpoint que exponga la creación de claves, igual
        que en la fuente lo es el asistente. Ese endpoint es la tarea **#490**;
        hasta entonces la regla existe, se puede probar, y no está inventada en
        el sitio equivocado.
        """
        actor = get_current_user()
        if actor is None or not getattr(actor, '_is_internal', lambda: False)():
            raise AccessError(
                'Sólo un usuario interno puede crear claves de API.')

    @classmethod
    def _ensure_can_manage_keys_programmatically(cls):
        """≙ ``_ensure_can_manage_keys_programmatically`` (``:1618-1633``).

        El comentario largo de la fuente explica por qué el administrador es
        una excepción y no depende del parámetro: habilitar, llamar y
        restaurar son tres pasos no atómicos, y un fallo entre el segundo y el
        tercero dejaría la gestión abierta para todos.
        """
        icp = apps.get_model('base', 'SystemParameter')
        enabled = icp.get_param('base.enable_programmatic_api_keys', 'False')
        if not (is_su() or str(enabled).lower() in ('1', 'true', 'yes')):
            raise UserError('La gestión programática de claves de API no está habilitada.')

    @classmethod
    @api.model
    def generate(cls, key, scope, name, expiration_date):
        """≙ ``generate`` (``:1634-1684``) — una clave nueva a partir de otra viva.

        Las reglas de compatibilidad de ámbito son las de la fuente, verbatim
        en su comentario: *"A global key can generate credentials for any
        scope (including global). A scoped key can only generate credentials
        for its own scope."*

        Envuelta por el limitador de intentos de la fuente
        (``ResUsers._assert_can_auth``), portado con la tarea #726: un
        ``AccessDenied`` desde aquí cuenta como fallo del origen, y tras
        ``base.login_cooldown_after`` fallos el origen entra en enfriamiento.
        """
        cls._ensure_can_manage_keys_programmatically()
        with ResUsers._assert_can_auth(user=key[:INDEX_SIZE]):
            return cls._generate_checked(key, scope, name, expiration_date)

    @classmethod
    def _generate_checked(cls, key, scope, name, expiration_date):
        """El cuerpo de ``generate``, ya dentro del limitador.

        La fuente escribe el ``with`` alrededor del cuerpo entero; aquí se
        parte en dos porque el cuerpo es largo y anidarlo lo desplazaría
        completo, ensuciando el diff sin cambiar la semántica. El ``AccessDenied``
        que este método levanta atraviesa el gestor de contexto igual.
        """
        actor = get_current_user()
        uid = getattr(actor, 'pk', None)
        now = timezone.now()
        nb_keys = cls.objects.filter(
            models.Q(expiration_date__isnull=True) | models.Q(expiration_date__gte=now),
            user_id=uid,
        ).count()
        icp = apps.get_model('base', 'SystemParameter')
        try:
            nb_keys_limit = int(icp.get_param(
                'base.programmatic_api_keys_limit',
                DEFAULT_PROGRAMMATIC_API_KEYS_LIMIT))
        except (TypeError, ValueError):
            _logger.warning(
                "Invalid value for 'base.programmatic_api_keys_limit', "
                "using default value.")
            nb_keys_limit = DEFAULT_PROGRAMMATIC_API_KEYS_LIMIT
        if nb_keys >= nb_keys_limit:
            raise UserError(
                f'Se alcanzó el límite de {nb_keys_limit} claves de API para '
                f'creación programática.')

        checked_uid = cls._check_credentials(scope=scope or 'rpc', key=key)
        if not checked_uid or checked_uid != uid:
            raise AccessDenied(
                'La clave de API dada no es válida o no pertenece al usuario actual.')
        new_key = cls._generate(scope, name, expiration_date)
        _logger.info("%s %r generated from %r", cls._description,
                             new_key[:INDEX_SIZE], key[:INDEX_SIZE])
        return new_key

    @classmethod
    @api.model
    def revoke(cls, key):
        """≙ ``revoke`` (``:1685-1711``) — retira una clave viva.

        Recorre las filas cuyo prefijo coincide y verifica el hash de cada
        una, porque el prefijo **no** es único: es el mismo bucle de la
        fuente. Envuelta por el limitador de intentos igual que ``generate``
        (``ResUsers._assert_can_auth``, tarea #726).
        """
        cls._ensure_can_manage_keys_programmatically()
        assert key, 'key required'
        with ResUsers._assert_can_auth(user=key[:INDEX_SIZE]):
            return cls._revoke_checked(key)

    @classmethod
    def _revoke_checked(cls, key):
        """El cuerpo de ``revoke``, ya dentro del limitador. Ver
        ``_generate_checked`` para por qué va partido."""
        now = timezone.now()
        candidates = cls.objects.filter(
            models.Q(expiration_date__isnull=True) | models.Q(expiration_date__gte=now),
            index=key[:INDEX_SIZE],
        )
        for candidate in candidates:
            if _verify_api_key(key, candidate.key):
                candidate._remove()
                return True
        raise AccessDenied('La clave de API dada no es válida.')

    @classmethod
    @api.autovacuum
    def _gc_user_apikeys(cls):
        """≙ ``_gc_user_apikeys`` (``:1712-1720``) — barre las caducadas."""
        deleted, _ = cls.objects.filter(
            expiration_date__isnull=False,
            expiration_date__lt=timezone.now(),
        ).delete()
        _logger.info("GC %r delete %d entries", cls._name, deleted)


class ResUsersApikeys(_ResUsersApikeysBase):
    """``res.users.apikeys`` — la clave de API de integración externa.

    El concreto del prototipo: aporta el nombre del modelo, su tabla y la FK a
    usuario; los campos y los diez métodos vienen de
    :class:`_ResUsersApikeysBase`, que documenta el mecanismo y sus cuatro
    divergencias.

    Su hermano por prototipo es ``auth_totp.device``
    (``addons/authz_totp/models/auth_totp.py``), que declara la **misma** forma
    sobre **otra** tabla.
    """

    _name = 'res.users.apikeys'
    _description = 'Users API Keys'
    #: La referencia lo declara ``False`` para emitir la tabla a mano
    #: (divergencia 1). Aquí la tabla la gestiona Django, así que el atributo
    #: se conserva **verbatim** como declaración de procedencia y su forma
    #: efectiva es ``Meta.managed = True``.
    _auto = False
    _allow_sudo_commands = False

    user = fields.Many2one(
        'base.ResUsers', on_delete=models.CASCADE, db_index=True,
        related_name='api_keys',
        help_text='Odoo user_id — el dueño de la clave.',
    )

    class Meta:
        db_table            = 'res_users_apikeys'
        ordering            = ['-id']
        verbose_name        = 'Clave de API'
        verbose_name_plural = 'Claves de API'
        indexes = [
            # ≙ el ``CREATE INDEX … ON %(table)s (user_id, index)`` de
            # ``init()`` (``:1548-1555``). El nombre lo fija la referencia por
            # convención ``<tabla>_user_id_index_idx``; aquí se conserva.
            models.Index(fields=['user', 'index'],
                         name=index_name_for('res_users_apikeys')),
        ]
        constraints = [
            # ≙ ``CHECK (char_length(index) = %(index_size)s)`` (``:1541``).
            #
            # NO se usa ``Q(index__length=…)``: Django no registra ``__length``
            # como lookup de ``CharField`` — medido, ``FieldError: Unsupported
            # lookup 'length'``. La forma que sí compila es la que
            # ``account_group.py`` ya verificó con ``constraint_sql()``:
            # ``Exact`` sobre ``Length``, que emite el ``char_length`` de la
            # fuente sin mutar el lookup global.
            models.CheckConstraint(
                condition=Exact(Length(F('index')), INDEX_SIZE),
                name='res_users_apikeys_index_size',
                violation_error_code='API_KEY_INDEX_SIZE',
            ),
        ]


def _check_apikey_credentials(*, scope, key, model=None):
    """≙ ``_check_apikey_credentials`` (``:1722-1750``).

    Devuelve el ``user_id`` si la clave es válida, ``None`` si no. El
    predicado es el de la fuente, término a término: el usuario **activo**, el
    prefijo coincidente, el ámbito nulo o igual, y la fecha nula o futura.

    La fuente recibe un cursor y el nombre de tabla porque el modelo hijo
    (``auth_totp.device``) comparte esta función con **otra** tabla; aquí ese
    parámetro es el modelo, por la misma razón y con la misma consecuencia: un
    dispositivo de confianza no valida contra las claves de RPC.
    """
    assert scope and key, 'scope and key required'
    if model is None:
        model = ResUsersApikeys
    now = timezone.now()
    candidates = model.objects.filter(
        models.Q(scope__isnull=True) | models.Q(scope=scope),
        models.Q(expiration_date__isnull=True) | models.Q(expiration_date__gte=now),
        user__active=True,
        index=key[:INDEX_SIZE],
    ).values_list('user_id', 'key')
    for user_id, current_key in candidates:
        if _verify_api_key(key, current_key):
            return user_id
    return None


# ==========================================================================
# Los tres asistentes de credencial — ≙ odoo19c: res_users.py:1615-1732
# ==========================================================================
#
# La referencia los declara como ``TransientModel`` en este mismo archivo, y
# aqui se portan con el precedente que el arbol ya fijo en
# ``base_partner_merge.py`` y en ``account_check_printing.print_prenumbered_
# checks``: **formulario, no tabla**. Los campos de un wizard son parametros;
# lo que es contenedor de datos se queda como ``dataclass`` congelada.
#
# Por que ese precedente y no un ``TransientModel`` mas: un wizard de la
# referencia existe porque su RPC expone modelos y su cliente OWL necesita una
# fila que sostener entre dos llamadas. Aqui el cliente es React y el canal es
# un endpoint DRF, asi que la fila intermedia no tiene a quien sostener. Lo
# que **si** cruza es la conducta, y esa es la que va abajo.
#
# Antes de este porte las tres clases estaban **ausentes y sin declarar**, que
# es el defecto que ``porte-completo-no-parcial.md`` nombra: no eran una
# divergencia declarada, eran un hueco silencioso. Ver :ref:`h-api-801`.


@dataclass(frozen=True)
class PasswordChangeLine:
    """≙ ``change.password.user`` (``odoo19c: res_users.py:1699-1712``).

    Una linea del asistente de cambio masivo: a que usuario, con que login se
    mostro, y cual es su contrasena nueva. La referencia la guarda como fila
    transitoria con ``wizard_id``; aqui es un valor inmutable, igual que
    ``MergeGroup`` en ``base_partner_merge.py`` — sin wizard que agrupe, no hay
    a quien apuntar.

    ``user_login`` se conserva aunque sea derivable de ``user``: la fuente lo
    declara ``readonly`` a proposito, porque el operador tiene que ver **con
    que login** esta cambiando la contrasena antes de confirmar, y ese login
    puede haber cambiado entre que se abrio el dialogo y que se envio.
    """

    user: object
    new_password: str
    user_login: str = ''


class PasswordChangeWizard:
    """≙ ``change.password.wizard`` (``odoo19c: res_users.py:1676-1697``).

    El cambio de contrasena **de otro**: un administrador fija credenciales
    nuevas para N usuarios de una vez. Es la tercera via de la fuente, distinta
    de las otras dos que este archivo ya porta:

    ======================================  ==================================
    Via de la fuente                          Aqui
    ======================================  ==================================
    ``change_password(old, new)``             ``ResUsers.change_password``
    ``change.password.own`` + identidad       gate de sesion fresca (DEC-12)
    ``change.password.wizard`` (esta)         esta clase
    ======================================  ==================================

    Lo que NO se porta, y se declara: ``_default_user_ids``, que lee
    ``context['active_ids']`` para prellenar el dialogo desde una seleccion de
    lista del backoffice, y el ``return`` de ``change_password_button``, que es
    un descriptor ``ir.actions.client`` para que el cliente OWL recargue. Los
    dos son la forma del dialogo; el ``reload`` aqui lo decide el cliente React
    al ver que su propia sesion cambio.
    """

    @staticmethod
    def lines_for(users, passwords):
        """≙ ``_default_user_ids`` (``:1682-1687``) — sin el contexto.

        La fuente saca los usuarios de ``context['active_ids']``; aqui los
        recibe quien llama, porque no hay seleccion de lista que leer. Lo que
        se conserva es **que la linea nace con el login ya capturado**, que es
        lo unico que ese metodo hace de sustantivo.
        """
        return [
            PasswordChangeLine(user=u, new_password=p,
                               user_login=u.get_username())
            for u, p in zip(users, passwords)
        ]

    @classmethod
    def apply(cls, lines):
        """≙ ``change_password_button`` de las dos clases (``:1689`` y ``:1714``).

        La fuente lo parte en dos —el wizard itera sus lineas y cada linea
        llama a ``_change_password``— y las dos mitades se conservan: el bucle
        aqui, la escritura en ``ResUsers._change_password``, que ya deja su
        rastro de auditoria.

        Tres cosas de la fuente que **si** cruzan, y no son cosmeticas:

        1. **Una linea sin contrasena se salta**, no falla
           (``if line.new_passwd``). Un operador que deja un campo vacio en un
           dialogo de N usuarios esta diciendo *"a este no"*, no *"aborta
           todo"*.
        2. **Las contrasenas temporales no sobreviven a la operacion**
           (``self.write({'new_passwd': False})``, con su comentario *"don't
           keep temporary passwords in the database longer than necessary"*).
           Aqui la linea es inmutable y nunca toco la base, asi que la
           equivalencia es no devolverla: ``apply`` devuelve **cuantas**
           cambio, no cuales.
        3. **Si el actor se cambio a si mismo, hay que decirlo**
           (``if self.env.user in self.user_ids.user_id``). La fuente devuelve
           un ``reload`` porque su sesion acaba de quedar invalida. Aqui se
           devuelve esa señal como dato —``self_changed``— y el cliente decide.

        :returns: ``(cambiadas, self_changed)``.
        """
        actor = get_current_user()
        changed = 0
        self_changed = False
        for line in lines:
            if not line.new_password:
                continue
            line.user._change_password(line.new_password)
            changed += 1
            if actor is not None and actor.pk == line.user.pk:
                self_changed = True
        return changed, self_changed


class IdentityCheck:
    """≙ ``res.users.identitycheck`` (``odoo19c: res_users.py:1615-1673``).

    Su docstring en la fuente dice para que existe, y vale igual aqui:

        Wizard used to re-check the user's credentials (password) and
        eventually revoke access to his account to every device he has an
        active session on. Might be useful before the more security-sensitive
        operations, users might be leaving their computer unlocked &
        unattended.

    **La mitad que cruza es ``_check_identity``**: verificar la credencial del
    actor y levantar un error legible si no coincide. Eso es una regla de
    seguridad, no una pantalla.

    **La mitad que NO cruza, declarada:** ``run_check`` (``:1654-1673``).
    Deserializa de ``self.request`` un ``(ctx, model, ids, method, args,
    kwargs)`` guardado, resuelve el metodo por ``getattr`` y lo invoca. Es un
    despachador de RPC generico: la referencia lo necesita porque su cliente
    hace la llamada, recibe *"hace falta re-autenticar"*, abre el dialogo y la
    llamada original tiene que sobrevivir en algun sitio mientras tanto.

    Aqui no sobrevive en ningun sitio y es deliberado: el cliente React reemite
    su propia peticion despues de re-autenticar, y el gate que la deja pasar es
    ``authz_reauth.assert_session_fresh`` desde la vista (DEC-12). Guardar una
    llamada serializada y despacharla por ``getattr`` seria construir un
    ejecutor de metodos arbitrarios por nombre — exactamente lo que este arbol
    evita en ``IrActionsServer.run()``, que levanta ``NotImplementedError`` por
    la misma razon.

    Tambien se marca ``request`` con ``groups=fields.NO_ACCESS`` en la fuente
    (``:1628``), que es el reconocimiento explicito de que ese campo es
    peligroso. No portar el despachador cierra ese riesgo en vez de replicarlo.
    """

    #: ≙ ``auth_method`` (``:1629``). La fuente declara un ``Selection`` con un
    #: solo valor y un ``default`` calculado por ``_get_default_auth_method``,
    #: preparado para que un addon anada mas (``totp``, en Enterprise). Aqui es
    #: la misma lista de un elemento, extensible por el mismo motivo.
    AUTH_METHODS = (('password', 'Contraseña'),)

    @staticmethod
    def _get_default_auth_method():
        """≙ ``_get_default_auth_method`` (``:1632-1633``)."""
        return 'password'

    @staticmethod
    def _check_identity(user, password):
        """≙ ``_check_identity`` (``:1635-1644``).

        La fuente construye la credencial con el ``login`` del usuario en
        sesion y la contrasena del **contexto**, y llama a
        ``_check_credentials`` sobre ``create_uid`` — el que abrio el
        asistente. Aqui el usuario llega como parametro porque no hay fila del
        asistente de la que leerlo, y la contrasena tambien: el contexto de la
        fuente es su canal de transporte, no parte de la regla.

        El mensaje de error se conserva verbatim en su intencion: la fuente
        remite a *"Forgot Password"* porque su pantalla lo ofrece.

        :raises UserError: si la credencial no coincide.
        """
        credential = {
            'login': user.get_username(),
            'password': password,
            'type': 'password',
        }
        try:
            user._check_credentials(credential, {'interactive': True})
        except AccessDenied:
            raise UserError(
                'Contraseña incorrecta. Vuelve a intentarlo, o restablece '
                'tu contraseña si la olvidaste.'
            ) from None


@receiver(pre_delete, sender=ResUsers, dispatch_uid='base.res_users.master_data')
def _forbid_deleting_master_data(sender, instance, **kwargs):
    """≙ ``_unlink_except_master_data`` (``odoo19c: res_users.py:647-660``).

    Los usuarios de sistema no se borran, ni de uno en uno ni en lote.

    **Por qué una señal y no un ``delete()``.** El gancho de la fuente es
    ``@api.ondelete(at_uninstall=True)``, y su ``unlink`` lo invoca **una vez
    con el recordset entero**, antes de tocar la base
    (``odoo19c: odoo/orm/models.py:4206-4209`` — ``func(self)``). Por eso allá
    da igual borrar uno o mil: el gancho ve el lote completo.

    En este ORM ``Model.delete()`` **no** es ese punto: ``QuerySet.delete()``
    no pasa por él, así que la guarda escrita ahí protegía la instancia y
    dejaba pasar el lote. El equivalente real es ``pre_delete``, medido en el
    paquete instalado:

    - ``Collector.can_fast_delete`` (``django/db/models/deletion.py:186``)
      exige que el modelo **no tenga listeners**; registrar este receptor
      desactiva el borrado rápido y fuerza a Django a instanciar las filas.
    - ``Collector.delete`` (``:459-466``) emite ``pre_delete`` por instancia
      **dentro de** ``transaction.atomic`` y **antes** de cualquier borrado, así
      que si esto lanza, el lote entero revierte.

    DIVERGENCIA DE MECANISMO, declarada: la fuente valida **el lote de una
    vez**; aquí se valida **una instancia por emisión**. El efecto es el mismo
    —un solo usuario de sistema aborta todo el lote, porque comparten
    transacción— pero el mensaje nombra al primer infractor que Django emita,
    no a todos.

    **Qué protege, y contra qué población.** Gobierna ``odoo19c``, que declara
    cuatro; se conservan los tres que este árbol tiene:

    - el **super-usuario** — *"it is used internally for resources created by
      Odoo (updates, module installation, ...)"*;
    - el **administrador** — *"it is utilized in various places (such as
      security configurations,...). Instead, archive it."*;
    - el **usuario público** — *"Deleting the public user is not allowed."*

    El cuarto de 19 no se porta, y no es omisión: DIVERGENCIA DE MECANISMO
    declarada. ``base.template_portal_user_id`` es la plantilla del asistente
    de invitación de la fuente; este árbol invita por endpoint, así que esa
    fila no existe y no hay a quién proteger.

    Medido también en 18, porque 19 sola no lo mostraba:

    - ``odoo18c: res_users.py:810-823`` protege **además** ``base.default_user``
      junto a la plantilla portal. **19 lo retiró**, y gobierna 19: no se porta.
    - ``odoo18e`` (misma versión, otra edición) **no** protege ``public_user``.
      Las dos ediciones de 18 no coinciden entre sí, así que citar «18» sin
      decir cuál mezclaría dos poblaciones.
    - ``odoo19e`` **no participa**: no trae el núcleo — no existe ahí
      ``addons/base/models/res_users.py``. Es un árbol de addons sobre
      Community, a diferencia de ``odoo18e``, que sí lleva su propia copia del
      núcleo. Y de sus addons que extienden ``res.users``, **ninguno** declara
      ``@api.ondelete``: Enterprise 19 no añade ni quita guardas.

    Cuatro poblaciones medidas, entonces, y el veredicto no cambia: gobierna
    ``odoo19c``.

    Lo que la fuente hace y aquí no: ``self.env.registry.clear_cache()`` en
    mitad del gancho. DIVERGENCIA DE STACK — ese registro es el suyo, y su
    equivalente aquí se invalida por otra vía.
    """
    if instance.pk == SUPERUSER_ID:
        raise UserError(
            'No se puede eliminar al super-usuario: es quien crea los '
            'recursos internos (actualizaciones, instalación de módulos). '
            'Archívalo en su lugar.')
    if instance.login in _SYSTEM_LOGINS:
        raise UserError(
            'No se puede eliminar al usuario %r: se usa en la '
            'configuración de seguridad y en el acceso anónimo. '
            'Archívalo en su lugar.' % instance.login)


@receiver(m2m_changed, sender='base.ResCompanyUsersRel',
          dispatch_uid='base.res_users.multi_company')
def _sync_multi_company_group(sender, instance, action, reverse, pk_set,
                              **kwargs):
    """≙ ``UsersMultiCompany`` (``odoo19c: res_users.py:1352-1397``).

    Un usuario con más de una empresa pertenece a ``base.group_multi_company``;
    con una o ninguna, no. La pertenencia se **deriva del conteo**: no se
    escribe a mano en ningún sitio.

    **Por qué un gancho y no tres.** La fuente cuelga el mismo cuerpo de
    ``create``, ``write`` y ``new`` porque su ORM escribe el M2M **dentro** de
    los dos primeros — de ahí su ``if 'company_ids' not in vals: return``, que
    es literalmente «actúa sólo cuando la escritura tocó el M2M».

    En Django un M2M **nunca** se escribe en el ``save()``: va siempre por su
    propio camino, y ese camino emite ``m2m_changed``. Así que esta señal es
    exactamente la condición que su ``write`` comprueba a mano, y cubre por
    construcción los dos ganchos de escritura. El tercero, ``new``, no tiene
    contraparte: construye un recordset **en memoria** que su cliente web
    consulta antes de guardar, y aquí no hay tal objeto.

    **Los dos lados del M2M.** ``company.user_ids`` es el lado directo
    (``reverse=False``: los usuarios afectados vienen en ``pk_set``);
    ``user.company_ids`` es el inverso (``reverse=True``: el afectado es
    ``instance``). La señal reporta ambos, así que la pertenencia se mantiene
    se escriba por donde se escriba.

    **El ``clear()`` desde la empresa** llega con ``pk_set = None`` — Django no
    dice a quién vació. Por eso se anota la membresía en ``pre_clear``, que aún
    la ve, y se recalcula en ``post_clear``. Es MÁS completo que la fuente: su
    ``write`` de ``res.users`` no se entera de un ``company.user_ids = [(5,)]``
    escrito del lado de la empresa.

    **Ciego a** una escritura de la tabla intermedia por SQL crudo o por
    ``ResCompanyUsersRel.objects.create()``, que no pasan por el descriptor y
    no emiten la señal. La fuente tiene el mismo hueco con su ``cr.execute``.
    """
    if action == 'pre_clear' and not reverse:
        instance._multi_company_cleared = list(
            instance.user_ids.values_list('pk', flat=True))
        return

    if action not in ('post_add', 'post_remove', 'post_clear'):
        return

    group_id = apps.get_model('base', 'IrModelData').xmlid_to_res_id(
        'base.group_multi_company', raise_if_not_found=False)
    if not group_id:
        # ≙ el ``if group_multi_company_id:`` de la fuente — mientras la
        # siembra no haya dejado el xmlid, la pregunta no tiene sentido.
        return

    if reverse:
        user_ids = [instance.pk]
    elif action == 'post_clear':
        user_ids = getattr(instance, '_multi_company_cleared', [])
    else:
        user_ids = list(pk_set or ())

    for user in ResUsers.objects.filter(pk__in=user_ids):
        company_count = user.company_ids.count()
        belongs = user.group_ids.filter(pk=group_id).exists()
        if company_count <= 1 and belongs:
            user.group_ids.remove(group_id)
        elif company_count > 1 and not belongs:
            user.group_ids.add(group_id)


# ---------------------------------------------------------------------------
# El invalidador del memo de grupos (≙ ``_get_invalidation_fields`` + el
# ``registry.clear_cache()`` que la fuente dispara desde su ``write``).
#
# La fuente tiene **un** punto de purga porque su ORM hace pasar toda
# escritura por ``write``. Aquí no: un M2M nunca se escribe en el ``save()``
# —va por su descriptor, que emite ``m2m_changed``— así que el invalidador se
# reparte entre las señales que sí cubren cada camino. Son cuatro receptores
# porque hay cuatro caminos, no cuatro reglas.
# ---------------------------------------------------------------------------

@receiver(post_save, sender='base.ResUsers',
          dispatch_uid='base.res_users.invalidate_group_ids')
def _invalidate_on_user_save(sender, instance, **kwargs):
    """Purga al guardar el usuario, si tocó un campo del invalidador.

    ``update_fields`` es ``None`` cuando quien guarda no lo declara — el caso
    común de ``obj.save()``. Ahí se purga **siempre**: es la postura
    conservadora, y equivale a lo que la fuente hace con su
    ``registry.clear_cache()``, que tampoco distingue por usuario.
    """
    campos = kwargs.get('update_fields')
    if campos is None or set(campos) & ResUsers._get_invalidation_fields():
        _invalidate_group_ids([instance.pk])


@receiver(m2m_changed, sender='base.ResGroups_user_ids',
          dispatch_uid='base.res_users.invalidate_group_ids_m2m')
def _invalidate_on_groups_changed(sender, instance, action, reverse, pk_set,
                                  **kwargs):
    """Purga cuando cambia la pertenencia, desde cualquiera de los dos lados.

    ``post_clear`` llega con ``pk_set = None`` —Django no dice a quién vació—
    y desde el lado del grupo el conjunto afectado son **sus** usuarios, que ya
    no se pueden enumerar después del vaciado. Por eso ese caso jubila la
    generación entera en vez de intentar una purga por usuario: es más ancho
    de lo necesario y **nunca deja un permiso retirado vivo**, que es la única
    dirección en la que un error aquí importa.
    """
    if action not in ('post_add', 'post_remove', 'post_clear'):
        return
    if action == 'post_clear':
        _invalidate_group_ids()
        return
    _invalidate_group_ids([instance.pk] if reverse else list(pk_set or ()))


@receiver(m2m_changed, sender='base.ResGroups_implied_ids',
          dispatch_uid='base.res_groups.invalidate_group_graph')
def _invalidate_on_implication_changed(sender, action, **kwargs):
    """Purga TODO cuando cambia el grafo de implicación.

    Una arista nueva entre dos grupos cambia la clausura de cualquier usuario
    que alcance el origen, y quiénes son ésos es justamente lo que el memo
    guarda. Enumerarlos exigiría recorrer todos los usuarios — la operación
    que ``ResGroups.check_user_disjoint_groups`` evita por escala, siguiendo el
    comentario de la propia fuente.
    """
    if action in ('post_add', 'post_remove', 'post_clear'):
        _invalidate_group_ids()


@receiver(post_delete, sender='base.ResGroups',
          dispatch_uid='base.res_groups.invalidate_group_graph_delete')
def _invalidate_on_group_deleted(sender, **kwargs):
    """Un grupo borrado desaparece de la clausura de quien lo tuviera.

    Django emite ``m2m_changed`` al vaciar las tablas intermedias en cascada,
    pero **no está garantizado** para todo camino de borrado (un
    ``QuerySet.delete()`` con borrado rápido no instancia las filas). Este
    receptor cierra el hueco por el lado que sí es fiable.
    """
    _invalidate_group_ids()
