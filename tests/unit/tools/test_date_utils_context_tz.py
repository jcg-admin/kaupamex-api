"""``parse_date`` resuelve ``today`` en la zona del contexto.

La fuente parte de ``Date.context_today(env['base'])`` y de
``Datetime.context_timestamp`` (``odoo19c: odoo/tools/date_utils.py:
146-151``), que leen ``env.tz``: la clave ``tz`` del contexto y, si falta, la
del usuario (``odoo/orm/environments.py:285-294``). El puerto leía sólo la del
usuario, así que con ``tz`` en el contexto y sin usuario resolvía en UTC. El
diferencial con fecha de ``test_contract_domains_model_reference.py`` sólo lo
ve mientras la fecha UTC y la del huso difieren; esta prueba lo fija sin
depender de la hora, con una zona a la que se le pide el desplazamiento.

*Métrica:* la zona que ``_current_timezone`` devuelve dentro y fuera de un
``context_scope`` con ``tz``.
*Ciega a:* la zona del usuario, que no se siembra aquí.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from orm.environments import context_scope
from tools import date_utils

MEXICO = 'America/Mexico_City'
INSTANT = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)


def _offset(tz):
    return INSTANT.astimezone(tz).utcoffset()


def test_the_context_timezone_is_used():
    with context_scope(tz=MEXICO):
        zone = date_utils._current_timezone()
    assert _offset(zone) == _offset(ZoneInfo(MEXICO))


def test_without_context_or_user_it_is_utc():
    assert _offset(date_utils._current_timezone()).total_seconds() == 0


def test_an_invalid_context_timezone_falls_back_to_utc():
    with context_scope(tz='Not/AZone'):
        zone = date_utils._current_timezone()
    assert _offset(zone).total_seconds() == 0
