"""
Factories de usuarios — PracticaYoruba API (modelo party, T-201).

El modelo de identidad ``IdentityUser`` (U-D puro) sólo tiene ``email`` +
credenciales; el nombre humano vive en ``Person`` (1:1). Estas factories
construyen la identidad y, cuando se pasan ``first_name``/``last_name`` (o por
defecto), el ``Person`` asociado. Se aceptan los kwargs legacy
``username``/``first_name``/``last_name`` para no romper los call-sites previos:
``username`` se ignora (ya no existe; el login es por email) y
``first_name``/``last_name`` se enrutan al ``Person``.
"""
import factory
from django.contrib.auth import get_user_model

from apps.platform.authz.models import Capability, Module, Role, RoleAssignment
from apps.platform.authz.services import (
    BUYER_ROLE_CODE, SUPERADMIN_ROLE_CODE, assign_buyer_role,
    invalidate_capabilities,
)
from apps.platform.authz.management.commands.seed_authz import NAMED_ACTIONS
from apps.addons.users.models import EmployeeProfile, Person

User = get_user_model()

# Capacidades del dominio 'account' (rol comprador), derivadas del catálogo
# canónico de seed_authz para no duplicar la lista.
_ACCOUNT_CAPS = [c for c in NAMED_ACTIONS if c[0].startswith('account.')]


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
    for code, name, sensitive in _ACCOUNT_CAPS:
        cap, _ = Capability.objects.get_or_create(
            code=code,
            defaults={'module': module, 'name': name, 'is_sensitive': sensitive},
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
    """Fábrica de identidades de prueba (party).

    Uso:
        user = UserFactory()
        user = UserFactory(email='nestor@test.mx', first_name='Nestor')
        users = UserFactory.create_batch(5)
    """
    class Meta:
        model = User
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f'user_{n}@practicayoruba.mx')
    password = factory.django.Password('TestPass123!')
    is_active = True

    class Params:
        # Traits/params legacy que NO son campos de IdentityUser. Se declaran
        # aquí para que factory-boy no los pase al constructor del modelo.
        username = None

    @factory.post_generation
    def person(self, create, extracted, **kwargs):
        """Crea el Person 1:1 con nombre. Acepta first_name/last_name legacy."""
        if not create:
            return
        first = kwargs.get('first_name', 'Test')
        last = kwargs.get('last_name', 'User')
        Person.objects.create(identity=self, first_name=first, last_name=last)

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
        # ``person`` para preservar la interfaz previa de las factories.
        for legacy in ('first_name', 'last_name'):
            if legacy in kwargs:
                kwargs[f'person__{legacy}'] = kwargs.pop(legacy)
        kwargs.pop('username', None)
        kwargs.pop('is_staff', None)
        kwargs.pop('is_superuser', None)
        return kwargs


class AdminUserFactory(UserFactory):
    """Identidad de personal interno (EmployeeProfile).

    NOTA: la autorización admin ya NO es un flag ``is_staff``; se resuelve por
    ``apps.platform.authz`` (Role/Capability, DEC-01=B). Esta factory crea la identidad +
    EmployeeProfile; la asignación del rol ``superadmin`` u otros la hace el test
    o el seed de authz según lo que verifique.
    """

    email = factory.Sequence(lambda n: f'admin_{n}@practicayoruba.mx')

    @factory.post_generation
    def employee(self, create, extracted, **kwargs):
        if not create:
            return
        EmployeeProfile.objects.create(identity=self)
        # is_staff ya no existe: el gate admin es una capacidad. Se le asigna el
        # rol superadmin (bypass del resolver) para que las vistas ``HasCapability``
        # lo autoricen, replicando la semántica del antiguo ``is_staff=True``.
        role, _ = Role.objects.get_or_create(
            code=SUPERADMIN_ROLE_CODE, defaults={'name': 'Superadministrador'},
        )
        RoleAssignment.objects.get_or_create(user=self, role=role)
