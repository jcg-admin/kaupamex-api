"""``tools.facade`` medido contra la fuente ejecutada.

Se carga ``odoo19c: odoo/tools/facade.py`` por ruta —sólo importa
``functools`` e ``inspect``— y se declara, con cada módulo, la misma fachada
sobre la misma clase envuelta: atributos con y sin conversión, y métodos de
instancia, estáticos y de clase con las tres variantes de ``cast`` (ninguna,
una función, y ``None``, que descarta el resultado).

Se compara lo que la fachada hace —lecturas, escrituras que llegan a la
instancia envuelta, valores devueltos, ``repr``/``str``, ``__class__``— y lo
que copia de la clase envuelta: nombre, documentación y firma.

*Métrica:* el valor —o el nombre de la excepción— de cada operación de la
rejilla, y el estado de la instancia envuelta después de cada escritura.
*Ciega a:* clases envueltas con descriptores distintos de los tres de la
rejilla, y a toda divergencia que la fuente comparta con nosotros.
"""
import importlib.util
import inspect
import pathlib

import pytest

from tools import facade as ported

pytestmark = pytest.mark.unit

_REPO = pathlib.Path(__file__).resolve().parents[3]
_SPEC = importlib.util.spec_from_file_location(
    'reference_roots_for_facade', _REPO / 'scripts' / 'reference_roots.py')
reference_roots = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(reference_roots)


def reference_module():
    try:
        root = pathlib.Path(reference_roots.tree('odoo19c'))
    except Exception:
        return None
    path = root / 'odoo' / 'tools' / 'facade.py'
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location('reference_facade', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope='module')
def reference():
    module = reference_module()
    if module is None:
        pytest.skip('la referencia no está montada en esta sesión')
    return module


class Account:
    """La clase envuelta: un poco de cada forma que la fachada distingue."""

    def __init__(self, number, balance):
        self.number = number
        self.balance = balance
        self.note = None
        self.calls = []

    def deposit(self, amount, *, memo=''):
        """Suma ``amount`` y devuelve el saldo."""
        self.calls.append(('deposit', amount, memo))
        self.balance += amount
        return self.balance

    def missing(self):
        self.calls.append(('missing',))
        return None

    @staticmethod
    def fee(amount):
        return amount / 10

    @classmethod
    def kind(cls, suffix=''):
        return cls.__name__ + suffix

    def __repr__(self):
        return f'<Account {self.number}>'

    def __str__(self):
        return f'account {self.number}'


def facade_class(module):
    """La misma fachada, declarada con las piezas del módulo dado."""

    class AccountFacade(module.Proxy):
        _wrapped__ = Account

        number = module.ProxyAttr()
        balance = module.ProxyAttr(cast=str)
        note = module.ProxyAttr(cast=int)
        deposit = module.ProxyFunc()
        missing = module.ProxyFunc(cast=str)
        fee = module.ProxyFunc(cast=int)
        kind = module.ProxyFunc(cast=None)

    return AccountFacade


def trace(module):
    """Lo observable de la fachada, en orden, con el estado envuelto."""
    cls = facade_class(module)
    account = Account('A-1', 100)
    proxy = cls(account)
    steps = []

    def step(label, call):
        try:
            value = call()
        except Exception as error:
            value = ('raises', type(error).__name__)
        steps.append((label, value, account.balance, account.note,
                      tuple(account.calls)))

    step('read number', lambda: proxy.number)
    step('read balance cast', lambda: proxy.balance)
    step('read note None', lambda: proxy.note)

    def write_note():
        proxy.note = '7'

    step('write note', write_note)
    step('read note cast', lambda: proxy.note)
    step('deposit', lambda: proxy.deposit(5, memo='x'))
    step('missing cast', lambda: proxy.missing())
    step('fee static cast', lambda: proxy.fee(55))
    step('fee on the class', lambda: cls.fee(99))
    step('kind discarded', lambda: proxy.kind('!'))
    step('kind on the class', lambda: cls.kind())
    step('repr', lambda: repr(proxy))
    step('str', lambda: str(proxy))
    step('class', lambda: proxy.__class__ is Account)
    step('isinstance', lambda: isinstance(proxy, Account))
    step('type', lambda: type(proxy) is cls)
    step('unexposed', lambda: proxy.calls)
    step('name', lambda: (cls.__name__, cls.__qualname__, cls.__doc__))
    step('wrapped', lambda: cls.__wrapped__ is Account)
    step('method name', lambda: (cls.deposit.__name__, cls.deposit.__doc__))
    step('method signature', lambda: str(inspect.signature(cls.deposit)))
    step('descriptors', lambda: tuple(
        type(inspect.getattr_static(cls, name)).__name__
        for name in ('number', 'deposit', 'fee', 'kind', '__repr__')))
    step('base object', lambda: module.Proxy._wrapped__ is object)
    return steps


class TestFacadeBehavesLikeTheReference:

    def test_every_step_matches_the_reference(self, reference):
        theirs, ours = trace(reference), trace(ported)
        divergences = [
            (mine[0], theirs_step[1:], mine[1:])
            for theirs_step, mine in zip(theirs, ours)
            if theirs_step != mine]
        assert len(ours) >= 23
        assert not divergences, divergences[:3]


class TestFacadeLiterally:
    """Casos escritos a mano: el diferencial no dice cuál se rompió."""

    def test_a_write_reaches_the_wrapped_instance(self):
        account = Account('B', 1)
        facade_class(ported)(account).note = 3
        assert account.note == 3

    def test_cast_none_discards_the_result(self):
        assert facade_class(ported)(Account('C', 0)).kind() is None

    def test_the_proxy_reports_the_wrapped_class(self):
        proxy = facade_class(ported)(Account('D', 0))
        assert proxy.__class__ is Account
