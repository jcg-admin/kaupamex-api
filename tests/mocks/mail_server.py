"""Captura del envío SMTP en las pruebas — ≙ ``MockSmtplibCase``.

Porte de ``odoo19c: odoo/addons/base/tests/common.py:378-470``. A diferencia
de un doble de ``send_email``, sustituye ``smtplib.SMTP`` y ``SMTP_SSL`` por
una sesión que registra cada ``send_message``, de modo que el correo recorre
``ir.mail_server`` completo: búsqueda del servidor, conexión, preparación del
sobre y envío.

Se usa con el fixture ``mock_smtplib_connection`` de ``tests/conftest.py``.
Cada entrada de ``emails`` tiene las claves de la fuente: ``message``,
``msg_cc``, ``msg_from``, ``msg_from_fmt``, ``msg_to``, ``smtp_from``,
``smtp_to_list`` y ``from_filter``.
"""
import email
import email.policy
import inspect
from contextlib import contextmanager
from unittest.mock import Mock, patch

from addons.base.models.ir_mail_server import IrMailServer
from tools.mail import email_split_and_format


class MockSmtplibCase:
    """≙ ``MockSmtplibCase``: mock de ``smtplib`` para probar el transporte."""

    @contextmanager
    def mock_smtplib_connection(self):
        self.emails = []

        origin = self

        class TestingSMTPSession:
            """La sesión SMTP de las pruebas: no conecta, registra."""

            def quit(self):
                pass

            def send_message(self, message, smtp_from, smtp_to_list):
                origin.emails.append({
                    # mensaje
                    'message': message.as_string(),
                    'msg_cc': message['Cc'],
                    'msg_from': message['From'],
                    'msg_from_fmt': email_split_and_format(
                        message['From'])[0],
                    'msg_to': message['To'],
                    # smtp
                    'smtp_from': smtp_from,
                    'smtp_to_list': smtp_to_list,
                    'from_filter': self.from_filter,
                })

            def set_debuglevel(self, smtp_debug):
                pass

            def ehlo_or_helo_if_needed(self):
                pass

            def login(self, user, password):
                pass

            def starttls(self, keyfile=None, certfile=None, context=None):
                pass

        self.testing_smtp_session = TestingSMTPSession()

        connect_origin = inspect.getattr_static(IrMailServer, '_connect__')
        find_mail_server_origin = inspect.getattr_static(
            IrMailServer, '_find_mail_server')

        with patch('smtplib.SMTP_SSL',
                   side_effect=lambda *a, **k: self.testing_smtp_session), \
                patch('smtplib.SMTP',
                      side_effect=lambda *a, **k: self.testing_smtp_session), \
                patch.object(IrMailServer, '_disable_send',
                             classmethod(lambda cls: False)), \
                patch.object(IrMailServer, '_connect__',
                             _mock_function(connect_origin)) as connect, \
                patch.object(IrMailServer, '_find_mail_server',
                             _mock_function(find_mail_server_origin)) as find:
            self.connect_mocked = _mock_of(connect)
            self.find_mail_server_mocked = _mock_of(find)
            yield self


def _mock_function(func):
    """Envuelve ``func`` registrando sus argumentos sin perder el contexto.

    ≙ ``mock_function`` de la fuente, que omite el ``self``. Aquí
    ``_find_mail_server`` es un ``classmethod``, así que la envoltura conserva
    el descriptor: se envuelve la función y se vuelve a declarar como método
    de clase.
    """
    mock = Mock()
    if isinstance(func, classmethod):
        inner = func.__func__

        def _call_cls(cls, *args, **kwargs):
            mock(*args, **kwargs)
            return inner(cls, *args, **kwargs)

        _call_cls.mock = mock
        return classmethod(_call_cls)

    def _call(*args, **kwargs):
        mock(*args[1:], **kwargs)
        return func(*args, **kwargs)

    _call.mock = mock
    return _call


def _mock_of(wrapper):
    return getattr(wrapper, '__func__', wrapper).mock


def parsed_message(entry):
    """El mensaje de una entrada de ``emails``, decodificado.

    La fuente guarda ``message.as_string()``; las pruebas que leen el asunto
    o el cuerpo lo vuelven a analizar con la política por defecto, que
    decodifica las cabeceras codificadas.
    """
    return email.message_from_string(
        entry['message'], policy=email.policy.default)
