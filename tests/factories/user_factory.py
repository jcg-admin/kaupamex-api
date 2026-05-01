"""
Factories de usuarios — PracticaYoruba API.
Usan la BD UTA (practicayoruba_uta).
"""
import factory
from django.contrib.auth import get_user_model

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    """
    Fabrica de usuarios de prueba.

    Uso:
        user = UserFactory()
        user = UserFactory(username='nestor', email='nestor@test.mx')
        users = UserFactory.create_batch(5)
    """
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f'user_{n}')
    email = factory.LazyAttribute(lambda o: f'{o.username}@practicayoruba.mx')
    first_name = factory.Faker('first_name', locale='es_MX')
    last_name = factory.Faker('last_name', locale='es_MX')
    password = factory.django.Password('TestPass123!')
    is_active = True
    is_staff = False


class AdminUserFactory(UserFactory):
    """Usuario con permisos de staff."""
    username = factory.Sequence(lambda n: f'admin_{n}')
    is_staff = True
