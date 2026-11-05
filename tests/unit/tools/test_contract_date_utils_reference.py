"""``tools.date_utils`` medido contra la fuente ejecutada.

Se carga ``odoo19c: odoo/tools/date_utils.py`` por ruta y se compara cada
función con la nuestra sobre una rejilla de entradas. La fuente importa
``.float_utils`` de forma relativa; para resolverlo se registra un paquete
sustituto con la ``float_utils`` de la propia referencia, que sólo importa la
biblioteca estándar, y se retira en cuanto el módulo queda cargado.

Las dos divergencias que el docstring del puerto declara se respetan, no se
esconden:

- **``zoneinfo`` en lugar de ``pytz``.** Cada lado recibe su huso con su
  propio mecanismo —``pytz.timezone(...).localize`` para la fuente,
  ``ZoneInfo`` para el puerto— y la comparación es sobre la representación
  ISO, que lleva el desplazamiento: dos husos distintos que digan la misma
  hora de pared con el mismo desplazamiento se consideran iguales, que es lo
  que la divergencia promete.
- **``parse_date`` sin ``env``.** La fuente pide la hora, la zona y el primer
  día de semana a un ``env`` y a ``fields_temporal``; el puerto, a
  ``orm.environments``. Aquí la fuente recibe un ``env`` sustituto y un
  ``fields_temporal`` sustituto durante cada llamada, y al puerto se le
  sustituyen ``_current_timezone`` y ``_current_week_start`` con los mismos
  valores.

*Métrica:* el valor devuelto —o el nombre de la excepción— de las 20
funciones públicas sobre su rejilla, normalizado a ISO.
*Ciega a:* el instante exacto de ``parse_date`` cuando el resultado no se
trunca —los dos lados leen el reloj en momentos distintos, así que se admite
una diferencia de dos segundos—, a husos fuera de los tres de la rejilla, y a
toda divergencia que la fuente comparta con nosotros.
"""
import contextlib
import importlib.util
import pathlib
import sys
import types
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import babel
import pytest
import pytz
from dateutil.relativedelta import relativedelta

from tools import date_utils as ported

pytestmark = pytest.mark.unit

_REPO = pathlib.Path(__file__).resolve().parents[3]
_SPEC = importlib.util.spec_from_file_location(
    'reference_roots_for_date_utils', _REPO / 'scripts' / 'reference_roots.py')
reference_roots = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(reference_roots)

PACKAGE = 'reference_tools_package'
ZONES = ('America/Mexico_City', 'Asia/Kathmandu', 'UTC')
GRANULARITIES = ('year', 'quarter', 'month', 'week', 'day', 'hour')
MOMENTS = (
    date(2024, 2, 29), date(2023, 12, 31), date(2024, 1, 1), date(2025, 6, 15),
    datetime(2024, 2, 29, 13, 45, 12, 500), datetime(2023, 12, 31, 23, 59),
    datetime(2024, 3, 10, 2, 30), datetime(2025, 11, 2, 0, 0),
)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def reference_module():
    """Carga la fuente con su ``float_utils`` en un paquete sustituto."""
    try:
        root = pathlib.Path(reference_roots.tree('odoo19c'))
    except Exception:
        return None
    tools = root / 'odoo' / 'tools'
    if not (tools / 'date_utils.py').is_file():
        return None
    package = types.ModuleType(PACKAGE)
    package.__path__ = []
    sys.modules[PACKAGE] = package
    try:
        load(f'{PACKAGE}.float_utils', tools / 'float_utils.py')
        return load(f'{PACKAGE}.date_utils', tools / 'date_utils.py')
    finally:
        for name in [n for n in sys.modules if n.split('.')[0] == PACKAGE]:
            del sys.modules[name]


@pytest.fixture(scope='module')
def reference():
    module = reference_module()
    if module is None:
        pytest.skip('la referencia no está montada en esta sesión')
    return module


def normalize(value):
    """Forma comparable: ISO para lo temporal, recursiva para colecciones."""
    if isinstance(value, datetime):
        return ('datetime', value.isoformat())
    if isinstance(value, (date, time)):
        return (type(value).__name__, value.isoformat())
    if isinstance(value, (timedelta, relativedelta)):
        return ('delta', repr(value))
    if isinstance(value, float):
        return ('float', round(value, 9))
    if isinstance(value, (list, tuple)):
        return tuple(normalize(item) for item in value)
    if hasattr(value, '__next__'):
        return ('iterates', tuple(normalize(item) for item in value))
    return value


def outcome(call):
    try:
        return ('value', normalize(call()))
    except Exception as error:
        return ('raises', type(error).__name__)


def aware(module, moment, zone):
    """El mismo instante de pared en la zona, con el mecanismo de cada lado."""
    if module is ported:
        tz = ported.utc if zone == 'UTC' else ZoneInfo(zone)
        return moment.replace(tzinfo=tz)
    if zone == 'UTC':
        return moment.replace(tzinfo=pytz.utc)
    return pytz.timezone(zone).localize(moment)


def calls(module):
    """La rejilla: ``(etiqueta, invocación)`` sobre el módulo dado."""
    grid = []
    for hours in (0, 1.5, 7.25, 12.999999, 23.99, 24.0, 9.008333):
        grid.append((f'float_to_time({hours})',
                     lambda h=hours: module.float_to_time(h)))
    for duration in (time(0), time(7, 15, 30, 250000), time.max,
                     timedelta(hours=26, minutes=3), timedelta(0)):
        grid.append((f'time_to_float({duration!r})',
                     lambda d=duration: module.time_to_float(d)))
    for text in ('2024-02-29', '2024-02-29 13:45:00', '2024-02-29T13:45:00',
                 '2024-02-29T13:45:00+01:00', '2024-13-01', 'nonsense'):
        grid.append((f'parse_iso_date({text})',
                     lambda t=text: module.parse_iso_date(t)))
    for moment in MOMENTS:
        grid += [
            (f'get_month({moment})', lambda m=moment: module.get_month(m)),
            (f'get_quarter_number({moment})',
             lambda m=moment: module.get_quarter_number(m)),
            (f'get_quarter({moment})', lambda m=moment: module.get_quarter(m)),
            (f'add({moment})',
             lambda m=moment: module.add(m, months=1, days=-2)),
            (f'subtract({moment})',
             lambda m=moment: module.subtract(m, years=1, hours=5)),
        ]
        for day, month in ((31, 12), (30, 6), (29, 2), (31, 3), (28, 2)):
            grid.append((f'get_fiscal_year({moment}, {day}, {month})',
                         lambda m=moment, d=day, mo=month:
                         module.get_fiscal_year(m, d, mo)))
        for granularity in GRANULARITIES + ('decade',):
            grid.append((f'start_of({moment}, {granularity})',
                         lambda m=moment, g=granularity:
                         module.start_of(m, g)))
            grid.append((f'end_of({moment}, {granularity})',
                         lambda m=moment, g=granularity: module.end_of(m, g)))
    for qty, granularity in ((3, 'hour'), (2, 'day'), (1, 'week'),
                             (4, 'month'), (1, 'year'), (1, 'decade')):
        grid.append((f'get_timedelta({qty}, {granularity})',
                     lambda q=qty, g=granularity: module.get_timedelta(q, g)))
    for zone in ZONES:
        moment = datetime(2024, 3, 10, 1, 30)
        grid += [
            (f'localized({zone})',
             lambda z=zone, m=moment: module.localized(aware(module, m, z))),
            (f'to_timezone({zone})',
             lambda z=zone, m=moment: module.to_timezone(
                 ported.utc if module is ported and z == 'UTC'
                 else ZoneInfo(z) if module is ported
                 else pytz.timezone(z))(module.localized(m))),
            (f'date_range aware {zone}',
             lambda z=zone: module.date_range(
                 aware(module, datetime(2024, 1, 31, 8), z),
                 aware(module, datetime(2024, 6, 30, 8), z))),
        ]
    grid += [
        ('localized(naive)',
         lambda: module.localized(datetime(2024, 1, 1, 12))),
        ('to_timezone(None)', lambda: module.to_timezone(None)(
            aware(module, datetime(2024, 7, 1, 12), 'Asia/Kathmandu'))),
        ('date_range dates', lambda: module.date_range(
            date(2024, 1, 31), date(2024, 5, 31))),
        ('date_range weekly', lambda: module.date_range(
            datetime(2024, 1, 1), datetime(2024, 2, 1),
            relativedelta(weeks=1))),
        ('date_range mixed zones', lambda: module.date_range(
            aware(module, datetime(2024, 1, 1), 'UTC'),
            aware(module, datetime(2024, 2, 1), 'Asia/Kathmandu'))),
        ('date_range naive and aware', lambda: module.date_range(
            datetime(2024, 1, 1),
            aware(module, datetime(2024, 2, 1), 'Asia/Kathmandu'))),
        ('date_range date step in hours', lambda: module.date_range(
            date(2024, 1, 1), date(2024, 1, 2), relativedelta(hours=6))),
        ('sum_intervals', lambda: module.sum_intervals([
            (datetime(2024, 1, 1, 8), datetime(2024, 1, 1, 12, 30), 'a'),
            (datetime(2024, 1, 2, 9), datetime(2024, 1, 2, 9, 45))])),
        ('sum_intervals empty', lambda: module.sum_intervals([])),
    ]
    for code in ('en_US', 'de_DE', 'ar_SA', 'en_GB'):
        locale = babel.Locale.parse(code)
        for moment in (date(2024, 1, 1), date(2024, 12, 30), date(2021, 1, 3),
                       date(2026, 1, 1)):
            grid += [
                (f'weeknumber({code}, {moment})',
                 lambda lo=locale, m=moment: module.weeknumber(lo, m)),
                (f'weeknumber({code}, {moment}, 6)',
                 lambda lo=locale, m=moment: module.weeknumber(lo, m, 6)),
                (f'weekstart({code}, {moment})',
                 lambda lo=locale, m=moment: module.weekstart(lo, m)),
                (f'weekend({code}, {moment})',
                 lambda lo=locale, m=moment: module.weekend(lo, m)),
            ]
    return grid


class TestTheFunctionsMatchTheReference:
    """Cada función, sobre la misma rejilla, contra la fuente."""

    def test_every_call_returns_what_the_reference_returns(self, reference):
        theirs, ours = calls(reference), calls(ported)
        assert [label for label, _ in theirs] == [label for label, _ in ours]
        divergences = []
        for (label, their_call), (_label, our_call) in zip(theirs, ours):
            expected, actual = outcome(their_call), outcome(our_call)
            if expected != actual:
                divergences.append((label, expected, actual))
        assert len(theirs) >= 290
        assert not divergences, (
            f'{len(divergences)} de {len(theirs)} llamadas divergen; '
            f'las tres primeras: {divergences[:3]}')

    def test_the_grid_reaches_every_public_function(self, reference):
        public = sorted(
            name for name, value in vars(reference).items()
            if callable(value) and not name.startswith('_')
            and getattr(value, '__module__', None) == reference.__name__)
        labels = ' '.join(label for label, _ in calls(ported))
        missing = [name for name in public
                   if name != 'parse_date' and f'{name}(' not in labels
                   and f'{name} ' not in labels]
        assert not missing, f'la rejilla no visita {missing}'


# -- parse_date: el contexto lo dan sustitutos, el reloj es el real ----------

EXPRESSIONS = (
    '2024-02-29', '2024-02-29 13:45:00', 'today', 'today +3d', 'today -1m',
    'today =1d', 'today =6m', 'today =1d =1m +1y', 'today +2w', 'now =3H',
    'now =3H =15M', 'now =0S', 'today =monday', 'today +monday',
    'today -friday', 'today =week_start', 'now =tuesday', '=1d', '+2y -3d',
    'now +1d', '', 'today x', 'today +3q', 'today =2w', 'today +1.5d',
    'today +', 'yesterday',
)


class _Lang:
    def __init__(self, week_start):
        self.week_start = str(week_start)

    def _get_data(self, code):
        return self


class _Environment:
    """Lo único que ``parse_date`` de la fuente lee de su ``env``."""

    def __init__(self, week_start):
        self.user = types.SimpleNamespace(lang='es_MX')
        self._lang = _Lang(week_start)

    def __getitem__(self, model):
        return self._lang if model == 'res.lang' else model


@contextlib.contextmanager
def temporal_fields(zone):
    """``fields_temporal`` sustituto, registrado sólo durante la llamada."""
    tz = pytz.timezone(zone)

    class Datetime:
        @staticmethod
        def now():
            return datetime.now(timezone.utc).replace(tzinfo=None)

        @staticmethod
        def context_timestamp(record, timestamp):
            return pytz.utc.localize(timestamp).astimezone(tz)

    class Date:
        @staticmethod
        def context_today(record, timestamp):
            return pytz.utc.localize(timestamp).astimezone(tz).date()

    names = ('odoo', 'odoo.orm', 'odoo.orm.fields_temporal')
    saved = {name: sys.modules.get(name) for name in names}
    modules = {name: types.ModuleType(name) for name in names}
    modules['odoo.orm.fields_temporal'].Datetime = Datetime
    modules['odoo.orm.fields_temporal'].Date = Date
    sys.modules.update(modules)
    try:
        yield
    finally:
        for name, module in saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


def agree(expected, actual):
    """Iguales, o dos instantes sin truncar a menos de dos segundos."""
    if expected == actual:
        return True
    if expected[0] == actual[0] == 'value' \
            and expected[1][0] == actual[1][0] == 'datetime':
        left = datetime.fromisoformat(expected[1][1])
        right = datetime.fromisoformat(actual[1][1])
        return abs(left - right) <= timedelta(seconds=2)
    return False


class TestParseDateMatchesTheReference:

    @pytest.mark.parametrize('zone', ZONES)
    @pytest.mark.parametrize('week_start', [1, 7])
    def test_every_expression_parses_as_in_the_reference(
            self, reference, monkeypatch, zone, week_start):
        tz = ported.utc if zone == 'UTC' else ZoneInfo(zone)
        monkeypatch.setattr(ported, '_current_timezone', lambda: tz)
        monkeypatch.setattr(ported, '_current_week_start', lambda: week_start)
        env = _Environment(week_start)
        divergences = []
        for expression in EXPRESSIONS:
            for _attempt in range(2):
                with temporal_fields(zone):
                    expected = outcome(
                        lambda e=expression: reference.parse_date(e, env))
                actual = outcome(lambda e=expression: ported.parse_date(e))
                if agree(expected, actual):
                    break
            else:
                divergences.append((expression, expected, actual))
        assert not divergences, divergences[:3]


class TestDateUtilsLiterally:
    """Casos escritos a mano: el diferencial no dice cuál se rompió."""

    def test_the_quarter_starts_on_its_first_month(self):
        assert ported.get_quarter(date(2024, 5, 17)) == \
            (date(2024, 4, 1), date(2024, 6, 30))

    def test_a_fiscal_year_ending_in_february_follows_leap_years(self):
        assert ported.get_fiscal_year(date(2024, 2, 29), 28, 2) == \
            (date(2023, 3, 1), date(2024, 2, 29))

    def test_twenty_four_hours_is_the_end_of_the_day(self):
        assert ported.float_to_time(24.0) == time.max
        assert ported.time_to_float(time.max) == 24.0
