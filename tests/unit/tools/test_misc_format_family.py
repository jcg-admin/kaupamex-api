"""La familia de formato de ``tools.misc`` — ≙ ``odoo19c:
odoo/tools/misc.py:1342-1665`` y sus pruebas
(``odoo/addons/base/tests/test_misc.py:43-150``, ``TestFormatLangDate``).

Los casos de ``TestFormatLangDate`` se portan con su texto esperado. Lo que
cambia es cómo se fija la zona del usuario: allá ``self.env.user.tz``, aquí
la del partner del usuario que actúa (``user_scope``).
"""

import datetime
import zoneinfo

import pytest
from django.contrib.auth import get_user_model

from orm.environments import Environment, env, user_scope
from orm.utils import SUPERUSER_ID
from tools import misc

pytestmark = pytest.mark.django_db


@pytest.fixture
def brussels_user(db):
    user = get_user_model().objects.create_user(
        login='formato.bruselas@kaupamex.mx', password='Formato123!')
    user.partner.tz = 'Europe/Brussels'
    user.partner.save()
    with Environment(None, SUPERUSER_ID, {}), user_scope(user.pk):
        yield env()


def test_00_accepted_types(brussels_user):
    """≙ ``test_00_accepted_types``."""
    environment = brussels_user
    datetime_str = '2017-01-31 12:00:00'
    date_datetime = datetime.datetime.strptime(datetime_str,
                                               '%Y-%m-%d %H:%M:%S')
    date_date = date_datetime.date()
    date_str = '2017-01-31'
    time_part = datetime.time(16, 30, 22)
    t_medium = 'h:mm:ss a'
    medium = f'MMM d, YYYY, {t_medium}'

    assert misc.format_date(environment, date_datetime) == '01/31/2017'
    assert misc.format_date(environment, date_date) == '01/31/2017'
    assert misc.format_date(environment, date_str) == '01/31/2017'
    assert misc.format_date(environment, '') == ''
    assert misc.format_date(environment, False) == ''
    assert misc.format_date(environment, None) == ''

    assert misc.format_datetime(environment, date_datetime,
                                dt_format=medium) == 'Jan 31, 2017, 1:00:00 PM'
    assert misc.format_datetime(environment, datetime_str,
                                dt_format=medium) == 'Jan 31, 2017, 1:00:00 PM'
    assert misc.format_datetime(environment, '', dt_format=medium) == ''
    assert misc.format_datetime(environment, False, dt_format=medium) == ''
    assert misc.format_datetime(environment, None, dt_format=medium) == ''

    assert misc.format_time(environment, time_part,
                            time_format=t_medium) == '4:30:22 PM'
    assert misc.format_time(environment, '', time_format=t_medium) == ''
    assert misc.format_time(environment, False, time_format=t_medium) == ''
    assert misc.format_time(environment, None, time_format=t_medium) == ''


def test_02_tz(brussels_user):
    """≙ ``test_02_tz``: mientras Londres sigue en 2016, Bruselas ya está en
    2017; un instante con zona ignora la del usuario."""
    environment = brussels_user
    date_datetime = datetime.datetime.strptime('2016-12-31 23:55:00',
                                               '%Y-%m-%d %H:%M:%S')
    assert misc.format_date(environment, date_datetime) == '01/01/2017'
    aware = date_datetime.replace(tzinfo=zoneinfo.ZoneInfo('UTC'))
    assert misc.format_date(environment, aware) == '12/31/2016'


def test_an_aware_value_from_the_column_is_converted_not_refused(
        brussels_user):
    """La divergencia de :func:`~tools.misc._as_utc`: la columna devuelve el
    instante con zona (``USE_TZ = True``) y ``pytz.localize`` de la fuente lo
    rechazaría."""
    aware = datetime.datetime(2017, 1, 31, 12, 0,
                              tzinfo=datetime.timezone.utc)
    formatted = misc.format_datetime(brussels_user, aware,
                                     dt_format='HH:mm')
    assert formatted == '13:00'


def test_format_decimalized_number_doctest():
    """Los ejemplos del docstring de la fuente."""
    assert misc.format_decimalized_number(123_456.789) == '123.5k'
    assert misc.format_decimalized_number(123_000.789) == '123k'
    assert misc.format_decimalized_number(-123_456.789) == '-123.5k'
    assert misc.format_decimalized_number(0.789) == '0.8'


def test_format_duration():
    assert misc.format_duration(1.5) == '01:30'
    assert misc.format_duration(-1.5) == '-01:30'
    assert misc.format_duration(0.9999) == '01:00'


def test_format_time_ago_reads_the_installed_language(brussels_user):
    words = misc._format_time_ago(brussels_user,
                                  datetime.timedelta(hours=3))
    assert words == '3 hours ago'


def test_format_lang_rounds_groups_and_places_the_symbol(brussels_user):
    class Currency:
        decimal_places = 2
        symbol = '$'
        position = 'before'

    assert misc.formatLang(brussels_user, 1234567.891) == '1,234,567.89'
    with_symbol = misc.formatLang(brussels_user, 1234.5,
                                  currency_obj=Currency())
    assert with_symbol == '$\N{NO-BREAK SPACE}1,234.50'
    assert misc.formatLang(brussels_user, 2500000,
                           rounding_unit='millions') == '2'
    assert misc.formatLang(brussels_user, '') == ''


def test_format_decimalized_amount_places_the_symbol():
    """≙ el ejemplo del docstring de la fuente: ``$123.5k``."""
    class Before:
        position = 'before'
        symbol = '$'

    class After:
        position = 'after'
        symbol = '€'

    assert misc.format_decimalized_amount(123_456.789, Before()) == '$123.5k'
    assert misc.format_decimalized_amount(123_456.789, After()) == '123.5k €'
    assert misc.format_decimalized_amount(123_456.789) == '123.5k'
