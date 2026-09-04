"""El dispatcher de correo vive en el addon ``mail`` (DEC-11, slice 4)."""
import importlib.util

import addons.mail.models.email_executor as mailmod


def test_dispatch_email_importable_from_addons_mail():
    assert callable(mailmod.dispatch_email)
    # hogar canónico (capa de modelos del addon mail, ≙ models/mail_mail.py):
    assert mailmod.dispatch_email.__module__ == 'addons.mail.models.email_executor'


def test_email_executor_ya_no_vive_en_core():
    """``core.email_executor`` fue movido a ``addons.mail`` (ya no existe)."""
    assert importlib.util.find_spec('core.email_executor') is None
