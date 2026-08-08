"""
Factories de usuarios — PracticaYoruba API (modelo party, T-201).

La credencial ``base.ResUsers`` (``res.users``) sólo tiene ``login`` +
credenciales; el nombre humano vive en ``base.ResPartner`` (``res.partner``),
al que delega por ``partner`` — el ``_inherits`` de la referencia
(``odoo19c: odoo/addons/base/models/res_users.py``). Estas factories construyen
la credencial y su partner. Se aceptan los kwargs legacy
``username``/``email``/``first_name``/``last_name`` para no romper los
call-sites previos: ``username`` se ignora, ``email`` se enruta a ``login``, y
``first_name``/``last_name`` se concatenan en ``ResPartner.name`` (la
referencia no separa nombre y apellido en el partner).
"""
import factory
from django.contrib.auth import get_user_model

from addons.authz.models import Capability, Module, Role, RoleAssignment
from addons.authz.services import (
    BUYER_ROLE_CODE, SUPERADMIN_ROLE_CODE, assign_buyer_role,
    invalidate_capabilities,
)
from addons.base.authz_catalog import CAPABILITIES as _BASE_CAPS

User = get_user_model()

# Capacidades del dominio 'account' (rol comprador), derivadas de la
# declaración de su addon dueño para no duplicar la lista. Desde SOL-100 el
# catálogo lo declara su addon dueño en ``authz_catalog.py``, no el seed
# central; tras la disolución de ``users`` el dueño es ``base`` (H-API-209).
_ACCOUNT_CAPS = [c for c in _BASE_CAPS if c.module == 'account']


def make_buyer(user):
    """Deja a ``user`` como comprador con todas las capacidades ``account.*``,
    reflejando producción (ADR-020: todo usuario registrado y validado recibe
    ``comprador``). Siembra sólo el dominio ``account`` (idempotente) — no el
    catálogo admin — y asigna el rol. Reutilizable por conftest y por los tests
    que crean usuarios ad-hoc (``other``/``attacker``) que en producción también
    son compradores."""
    module, _ = Module.objects.get_or_create(
        code='account', defaults={'name': 'Mi cuenta'},
    )
    caps = []
    for spec in _ACCOUNT_CAPS:
        cap, _ = Capability.objects.get_or_create(
            code=spec.code,
            defaults={
                'module': module, 'name': spec.name,
                'is_sensitive': spec.is_sensitive,
            },
        )
        caps.append(cap)
    role, _ = Role.objects.get_or_create(
        code=BUYER_ROLE_CODE, defaults={'name': 'Comprador'},
    )
    role.capabilities.add(*caps)
    assign_buyer_role(user)
    invalidate_capabilities(user.pk)
    return user


class UserFactory(factory.django.DjangoModelFactory):
    """Fábrica de credenciales de prueba (``res.users`` + ``res.partner``).

    Uso:
        user = UserFactory()
        user = UserFactory(login='nestor@test.mx', first_name='Nestor')
        users = UserFactory.create_batch(5)
    """
    class Meta:
        model = User
        skip_postgeneration_save = True

    login = factory.Sequence(lambda n: f'user_{n}@practicayoruba.mx')
    password = factory.django.Password('TestPass123!')
    active = True

    class Params:
        # Traits/params legacy que NO son campos de ``res.users``. Se declaran
        # aquí para que factory-boy no los pase al constructor del modelo.
        username = None

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Enruta por ``create_user``, no por el ``manager.create()`` genérico
        que usa ``DjangoModelFactory`` por defecto.

        ``partner`` es un ``Many2one`` requerido (H-API-119): un
        ``model_class(**kwargs).save()`` sin partner explícito revienta con
        ``IntegrityError: Column 'partner_id' cannot be null`` — sólo
        ``create_user``/``_create_user`` auto-crean el partner mínimo cuando
        no se pasa uno. De paso corrige un segundo defecto latente: sin este
        override, ``password`` (texto plano de ``factory.django.Password``)
        se habría guardado sin hashear — ``create_user`` sí llama
        ``set_password``.
        """
        manager = cls._get_manager(model_class)
        return manager.create_user(*args, **kwargs)

    @factory.post_generation
    def partner_name(self, create, extracted, **kwargs):
        """Fija ``ResPartner.name``. Acepta first_name/last_name legacy.

        La referencia no separa nombre y apellido en ``res.partner``: declara
        un solo ``name`` (``odoo19c: base/models/res_partner.py``). Los dos
        kwargs legacy se concatenan.
        """
        if not create:
            return
        first = kwargs.get('first_name', 'Test')
        last = kwargs.get('last_name', 'User')
        name = ' '.join(p for p in (first, last) if p)
        if name and self.partner.name != name:
            self.partner.name = name
            self.partner.save(update_fields=['name'])

    @factory.post_generation
    def buyer_role(self, create, extracted, **kwargs):
        """Refleja producción (ADR-020): todo usuario registrado y validado
        recibe ``comprador``. ``assign_buyer_role`` es tolerante: si el catálogo
        authz no está sembrado (rol ausente) es no-op, así que no altera los
        tests que no siembran. En los tests que siembran el rol primero, el
        usuario queda con las capacidades ``account.*`` como en producción."""
        if not create:
            return
        assign_buyer_role(self)

    @classmethod
    def _adjust_kwargs(cls, **kwargs):
        # Enruta los kwargs legacy first_name/last_name al post_generation
        # ``partner_name`` para preservar la interfaz previa de las factories.
        for legacy in ('first_name', 'last_name'):
            if legacy in kwargs:
                kwargs[f'partner_name__{legacy}'] = kwargs.pop(legacy)
        # ``email`` era el USERNAME_FIELD de ``IdentityUser``; en ``res.users``
        # el identificador de acceso es ``login`` (odoo19c: res_users.py).
        if 'email' in kwargs:
            kwargs['login'] = kwargs.pop('email')
        if 'is_active' in kwargs:
            kwargs['active'] = kwargs.pop('is_active')
        kwargs.pop('username', None)
        kwargs.pop('is_staff', None)
        kwargs.pop('is_superuser', None)
        return kwargs


class AdminUserFactory(UserFactory):
    """Credencial de personal interno (``res.partner.employee = True``).

    ``EmployeeProfile`` no existe en la referencia: el empleado es el campo
    booleano ``employee`` de ``res.partner``
    (``odoo19c: base/models/res_partner.py``).

    NOTA: la autorización admin ya NO es un flag ``is_staff``; se resuelve por
    ``addons.authz`` (Role/Capability, DEC-01=B). Esta factory marca el partner
    como empleado; la asignación del rol ``superadmin`` u otros la hace el test
    o el seed de authz según lo que verifique.
    """

    login = factory.Sequence(lambda n: f'admin_{n}@practicayoruba.mx')

    @factory.post_generation
    def employee(self, create, extracted, **kwargs):
        if not create:
            return
        self.partner.employee = True
        self.partner.save(update_fields=['employee'])
        # is_staff ya no existe: el gate admin es una capacidad. Se le asigna el
        # rol superadmin (bypass del resolver) para que las vistas ``HasCapability``
        # lo autoricen, replicando la semántica del antiguo ``is_staff=True``.
        role, _ = Role.objects.get_or_create(
            code=SUPERADMIN_ROLE_CODE, defaults={'name': 'Superadministrador'},
        )
        RoleAssignment.objects.get_or_create(user=self, role=role)
