"""Un modelo concreto no nace con el ``_name`` de un mixin.

En la fuente la identidad la decide el metaclase: un modelo con ``_name``
propio es un modelo, uno sin él extiende el de su ``_inherit``; nunca hay un
modelo nuevo con la identidad de otro. Aquí ``ModelBase`` hereda el atributo
por MRO, así que ``_register`` (en ``class_prepared``) rehúsa la clase
concreta que lo hereda sin declararlo. designs/analytic-account-header.md.
"""
import pytest
from django.apps import apps
from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.db.migrations.state import ProjectState
from django.test.utils import isolate_apps


def _mixin():
    class NamedMixin(models.Model):
        _name = 'test.named.mixin'

        class Meta:
            abstract = True
            app_label = 'base'

    return NamedMixin


@isolate_apps()
def test_a_concrete_model_that_inherits_a_name_is_refused():
    mixin = _mixin()
    with pytest.raises(ImproperlyConfigured, match='test.named.mixin'):
        class Inheritor(mixin):
            class Meta:
                app_label = 'base'


@isolate_apps()
def test_a_concrete_model_with_its_own_name_is_accepted():
    mixin = _mixin()

    class Owner(mixin):
        _name = 'test.owner'

        class Meta:
            app_label = 'base'

    assert Owner._name == 'test.owner'


@isolate_apps()
def test_an_abstract_child_may_keep_the_mixin_name():
    mixin = _mixin()

    class AbstractChild(mixin):
        class Meta:
            abstract = True
            app_label = 'base'

    assert AbstractChild._name == 'test.named.mixin'


@isolate_apps()
def test_a_proxy_shares_the_identity_of_its_model():
    mixin = _mixin()

    class Owner(mixin):
        _name = 'test.proxied'

        class Meta:
            app_label = 'base'

    class Proxy(Owner):
        class Meta:
            proxy = True
            app_label = 'base'

    assert Proxy._name == 'test.proxied'


def test_the_migration_state_renders_its_historical_models():
    """Los modelos históricos de una migración heredan, por las bases que el
    estado conserva, el ``_name`` de sus mixins sin declararlo; no son
    modelos del registro y no se rehúsan."""
    historical = ProjectState.from_apps(apps).apps
    model = historical.get_model('mail', 'MailMessage')
    assert model._meta.apps is historical
