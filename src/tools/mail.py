"""``tools.mail`` — espejo de ``odoo/tools/mail.py`` (sólo símbolos con consumidor).

Archivo separado de ``tools/misc.py`` a propósito: en la referencia
``single_email_re`` vive en ``odoo/tools/mail.py:722``, no en ``misc`` — y
este árbol no agrupa lo que la referencia mantiene separado.

Adaptado de Odoo Community ``odoo/tools/mail.py`` (LGPL-3) — atribución y
aviso de licencia preservados (DEC-KX-03).
"""
import re

# ``single_email_re`` — ¿el string ES un (1) email y nada más?
#
# Porte verbatim de ``odoo/tools/mail.py:722``. Decisión de equivalencia
# (2026-08-02): Django trae ``django.core.validators.validate_email``, que es
# el validador **rico** (IDN, literales IP, mensajes de error) y sigue siendo
# la herramienta para VALIDAR un email de entrada. Este regex cumple otro rol
# en los call-sites portados: un check barato de FORMA ("¿el login parece un
# email?" → copiarlo al campo email al crear el usuario federado,
# ``auth_ldap/models/res_company_ldap.py:216``). Cambiarlo por el validador
# de Django alteraría qué logins se consideran email (p. ej. IDN pasa en
# Django y no aquí) — se preserva el comportamiento de la referencia y se
# deja la validación rica donde toca: los serializers DRF (``EmailField``).
single_email_re = re.compile(
    r"""^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,63}$""", re.VERBOSE)
