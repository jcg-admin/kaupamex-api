"""Asistentes del addon ``project_todo``.

≙ ``odoo19c: addons/project_todo/wizard/__init__.py``. Un solo asistente:
``mail.activity.todo.create``, que crea a la vez el to-do y la actividad que
lo recuerda.

Como en ``account_debit_note/wizard/``, el paquete no lo importa el arranque
de Django (``models/`` es lo único que la app carga sola): el asistente es una
clase sin tabla y la importa quien lo usa. Su ``mail_activity_todo_create.xml``
—el formulario del cliente web de Odoo— no se porta.
"""
from . import mail_activity_todo_create  # noqa: F401
