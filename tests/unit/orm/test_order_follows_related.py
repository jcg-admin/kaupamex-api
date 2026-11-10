"""``order_to_django`` recorre el camino de un ``related`` sin columna.

≙ ``_order_field_to_sql`` → ``_field_to_sql`` (``odoo19c:
odoo/orm/models.py:2919-2922``): un campo ``related`` no almacenado se ordena
siguiendo su camino. ``res.users`` declara ``_order = 'name, login'`` y su
``name`` es el del partner delegado (``_inherits``), así que ordenar usuarios
—o un Many2many hacia ellos— exige ese recorrido. Diseño:
``designs/module-install-cycle.md``, L4e.
"""
import pytest
from django.contrib.auth import get_user_model
from django.db.models.expressions import OrderBy

from orm.models import order_to_django

pytestmark = pytest.mark.django_db


def _names(terms):
    return [(term.expression.name, term.descending) for term in terms
            if isinstance(term, OrderBy)]


def test_the_user_order_goes_through_the_partner():
    assert _names(order_to_django(get_user_model(), 'name, login')) == [
        ('partner__name', False), ('login', False)]


def test_the_direction_travels_with_the_path():
    assert _names(order_to_django(get_user_model(), 'name desc')) == [
        ('partner__name', True)]


def test_the_ordered_users_follow_their_partner_names():
    users = get_user_model()
    late = users.objects.create_user(
        login='order-related-a', password=None, name='Zeta')
    early = users.objects.create_user(
        login='order-related-b', password=None, name='Alfa')
    ordered = list(users.objects.filter(pk__in=[late.pk, early.pk]).order_by(
        *order_to_django(users, 'name, login')).values_list('pk', flat=True))
    assert ordered == [early.pk, late.pk]
