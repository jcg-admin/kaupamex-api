"""``new()`` con un Many2one hacia un modelo de Django sin ``BaseModel``.

≙ ``BaseModel._update_cache`` (``odoo19c: odoo/orm/models.py``): tras poner
cada valor en caché, ajusta el inverso sólo en los registros **nuevos** del
comodelo (``self[field.name].filtered(lambda r: not r.id)``). Aquí un
comodelo de Django devuelve una fila, no un recordset, y una fila ya existe:
no hay inverso nuevo que ajustar.

*Métrica:* que ``new()`` termine y el valor quede en el registro.
*Ciega a:* el inverso de comodelos BaseModel, que mide otra prueba.
"""
import pytest
from django.contrib.auth import get_user_model

from orm.environments import env as current_env
from orm.environments import sudo, user_scope

pytestmark = pytest.mark.django_db


def test_new_takes_a_many2one_to_a_django_model():
    user = get_user_model().objects.create_user(
        login='new-django-comodel', password=None, name='author')
    with user_scope(user.pk), sudo():
        message = current_env()['test_orm.message'].new({'author': user.pk})
        assert message.author.pk == user.pk


def test_new_takes_an_empty_many2one_to_a_django_model():
    user = get_user_model().objects.create_user(
        login='new-django-comodel-empty', password=None, name='author')
    with user_scope(user.pk), sudo():
        message = current_env()['test_orm.message'].new({'author': False})
        assert not message.author
