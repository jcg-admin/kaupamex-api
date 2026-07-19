"""Modelos del addon ``mail`` (fiel al addon ``mail`` de Odoo).

El envío de correo de Odoo vive en ``models/mail_mail.py`` (``mail.mail`` con
``process_email_queue``). Aquí reside el servicio de envío async ``email_executor``
(≙ ``mail.mail.process_email_queue``) como módulo de la capa de modelos.

No se importa ``email_executor`` en este ``__init__`` a propósito: importa
``EmailTask`` de ``addons.notifications`` y no debe cargarse al poblar el
registro de apps. Los consumidores importan la ruta completa
``addons.mail.models.email_executor``.
"""
