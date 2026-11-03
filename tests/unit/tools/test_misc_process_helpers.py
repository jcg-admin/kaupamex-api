"""Contrato de los ayudantes de proceso de ``tools.misc``.

≙ ``exec_pg_environ``, ``scan_languages``, ``dumpstacks`` y ``format_frame``
(``odoo19c: odoo/tools/misc.py:163-185, 453-474, 882-934, 1954-1956``).
Los valores de conexión del caso son de prueba, no credenciales reales.
"""

import inspect
import logging
import threading

import pytest
from django.db import DEFAULT_DB_ALIAS, connections

from service import db as service_db
from tools import misc


@pytest.fixture
def probe_settings(monkeypatch):
    sd = connections[DEFAULT_DB_ALIAS].settings_dict
    monkeypatch.setitem(sd, 'HOST', 'probe-host')
    monkeypatch.setitem(sd, 'PORT', 5433)
    monkeypatch.setitem(sd, 'USER', 'probe-user')
    monkeypatch.setitem(sd, 'PASSWORD', 'probe-pass')
    options = dict(sd.get('OPTIONS') or {})
    options['application_name'] = 'kaupamex-{pid}'
    monkeypatch.setitem(sd, 'OPTIONS', options)
    return sd


def test_exec_pg_environ_maps_the_connection_to_libpq_variables(
        probe_settings):
    env = misc.exec_pg_environ()
    assert env['PGHOST'] == 'probe-host'
    assert env['PGPORT'] == '5433'
    assert env['PGUSER'] == 'probe-user'
    assert env['PGPASSWORD'] == 'probe-pass'


def test_exec_pg_environ_names_the_subprocess_by_pid(probe_settings):
    """La fuente sustituye ``{pid}`` por ``env<pid>`` y corta a 63 bytes, el
    tope de ``application_name`` en PostgreSQL."""
    env = misc.exec_pg_environ()
    assert env['PGAPPNAME'].startswith('kaupamex-env')
    assert len(env['PGAPPNAME']) <= 63


def test_exec_pg_environ_keeps_the_signature_of_the_source():
    assert list(inspect.signature(misc.exec_pg_environ).parameters) == []


def test_backup_subprocess_uses_the_same_environment(probe_settings):
    assert service_db._pg_env()['PGPASSWORD'] == 'probe-pass'


@pytest.mark.django_db
def test_scan_languages_lists_the_reference_catalogue_sorted_by_name():
    langs = misc.scan_languages()
    assert len(langs) == 93
    assert ('en_US', 'English (US)') in langs
    names = [name for _, name in langs]
    assert names == sorted(names)


def test_scan_languages_falls_back_to_english_when_unreadable():
    """Sin acceso a la base el catálogo no se puede leer: la fuente registra
    el error y devuelve sólo ``en_US``, no propaga la excepción."""
    assert misc.scan_languages() == [('en_US', 'English')]


def test_format_frame_names_function_file_and_line():
    frame = inspect.currentframe()
    line = frame.f_lineno
    text = misc.format_frame(frame)
    assert text.startswith('test_format_frame_names_function_file_and_line ')
    assert text.endswith(f'test_misc_process_helpers.py:{line + 1}')


def test_dumpstacks_logs_the_current_thread(caplog):
    with caplog.at_level(logging.INFO, logger='tools.misc'):
        misc.dumpstacks(thread_idents=[threading.get_ident()])
    text = caplog.text
    assert '# Thread:' in text
    assert 'test_dumpstacks_logs_the_current_thread' in text
