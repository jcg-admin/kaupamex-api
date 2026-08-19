"""``account_edi/wizard/`` — vacío a propósito.

``account_resequence.py`` (único archivo) sólo EXTIENDE ``account.
resequence.wizard`` (de ``account``) — no declara ningún wizard propio. Se
carga desde ``AccountEdiConfig.ready()`` (``apps.py``), no aquí — mismo
criterio que ``account_edi/models/__init__.py`` para sus archivos de
extensión.
"""
