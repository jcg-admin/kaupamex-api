"""Un método de clase pedido sobre un recordset corre en el entorno de éste.

≙ ``records.search(...)`` de la referencia (``odoo19c: odoo/orm/models.py:
1363``), que es un método de instancia y lee ``self.env``. El contrato del
paso ``with_context search`` de la rejilla persistida mide el contexto contra
la referencia; esta suite mide los otros dos ejes —``sudo`` y ``with_user``—,
que la rejilla no puede ver porque corre como superusuario, y que los canales
se restauran al salir, también cuando el método lanza (H-API-1160).

*Métrica:* lo que un método de clase lee de los canales de
:mod:`orm.environments` durante la llamada y después de ella.
*Ciega a:* qué métodos de clase concretos dependen de cada canal: eso lo mide
la rejilla, eje por eje.
"""
import pytest
from django.apps import apps

from orm.environments import (
    context_scope, get_context, get_current_uid, is_su, user_scope)
from orm.models import _EnvClassmethod

MODEL = 'test_orm.model_active_field'


def _channels(cls):
    return get_current_uid(), is_su(), dict(get_context())


def _failing(cls):
    raise RuntimeError(_channels(cls))


@pytest.fixture
def model(monkeypatch):
    model = next(model for model in apps.get_models()
                 if getattr(model, '_name', None) == MODEL)
    monkeypatch.setattr(model, '_probe_channels',
                        _EnvClassmethod(classmethod(_channels)),
                        raising=False)
    monkeypatch.setattr(model, '_probe_failing',
                        _EnvClassmethod(classmethod(_failing)),
                        raising=False)
    return model


def test_the_models_inherit_the_wrapped_classmethods(model):
    assert isinstance(vars(model.__mro__[next(
        index for index, klass in enumerate(model.__mro__)
        if 'search' in vars(klass))])['search'], _EnvClassmethod)


def test_from_the_class_it_reads_the_ambient_channels(model):
    with user_scope(7), context_scope(lang='es_MX'):
        assert model._probe_channels() == (7, False, {'lang': 'es_MX'})


def test_sudo_reaches_the_classmethod(model):
    with user_scope(7):
        records = model.browse(()).sudo()
        assert model._probe_channels()[1] is False
        assert records._probe_channels()[1] is True


def test_with_user_reaches_the_classmethod(model):
    with user_scope(7):
        uid, su, _ = model.browse(()).with_user(9)._probe_channels()
    assert (uid, su) == (9, False)


def test_with_context_replaces_the_context(model):
    with user_scope(7), context_scope(lang='es_MX', tz='UTC'):
        records = model.browse(()).with_context({'active_test': False})
        assert records._probe_channels()[2] == {'active_test': False}


def test_the_channels_are_restored_after_the_call(model):
    with user_scope(7), context_scope(lang='es_MX'):
        records = model.browse(()).sudo().with_context(active_test=False)
        records._probe_channels()
        assert _channels(model) == (7, False, {'lang': 'es_MX'})


def test_the_channels_are_restored_when_the_method_raises(model):
    with user_scope(7), context_scope(lang='es_MX'):
        records = model.browse(()).with_user(9).with_context(lang='en_US')
        with pytest.raises(RuntimeError) as raised:
            records._probe_failing()
        assert raised.value.args[0][:2] == (9, False)
        assert _channels(model) == (7, False, {'lang': 'es_MX'})


def test_the_adopted_display_name_classmethods_are_wrapped():
    """``ir.attachment`` no hereda ``DisplayNameMixin``: sus métodos de
    ``display_name`` los cuelga ``adopt_display_name`` después de crear la
    clase, fuera del alcance de ``__init_subclass__``."""
    attachment = apps.get_model('base', 'IrAttachment')
    assert 'name_create' in vars(attachment)
    assert isinstance(vars(attachment)['name_create'], _EnvClassmethod)


def test_a_classmethod_declared_by_the_model_is_wrapped():
    """Un método de clase que el modelo declara en su cuerpo no hereda la
    envoltura de ``BaseModel``: la recibe de ``__init_subclass__``. Se mide
    sobre ``test_orm.bar``, que hereda ``DisplayNameMixin`` y por eso no
    pasa por ``adopt_display_name``, que también envuelve."""
    bar = next(model for model in apps.get_models()
               if getattr(model, '_name', None) == 'test_orm.bar')
    assert isinstance(vars(bar)['_search_foo'], _EnvClassmethod)
