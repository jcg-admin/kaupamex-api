"""Controllers de ``base``.

Hoy sólo hospeda ``schema.py`` (extensiones drf-spectacular de la
autenticación — ``base`` es el dueño de la credencial: ``ResUsers`` +
``CsrfExemptSessionAuthentication``). La superficie HTTP de cuenta del
comprador vive en ``portal`` (como en la referencia: ``/my/account`` es
de ``portal``, no de ``base``).
"""
