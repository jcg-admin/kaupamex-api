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

from apps.authz.models import Role, RoleAssignment
from apps.authz.services import SUPERADMIN_ROLE_CODE
from apps.users.models import EmployeeProfile, Person

User = get_user_model()


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
    ``apps.authz`` (Role/Capability, DEC-01=B). Esta factory crea la identidad +
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
