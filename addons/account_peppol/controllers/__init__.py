"""Controladores del addon ``account_peppol``.

≙ ``odoo19c: addons/account_peppol/controllers/__init__.py``, que importa los
tres. Aquí no se importa nada: **los tres están bloqueados** y son
documentación.

El bloqueo que comparten es de alcance, no de mecanismo: este árbol monta cada
controlador en ``src/config/urls.py`` (precedente:
``addons/account_debit_note/controllers/urls.py``), archivo **fuera del
write-set de este pase**. Una vista sin ese ``include`` es código inalcanzable.

- ``webhooks.py`` — las tres rutas de aviso del proxy. Su trabajo de negocio
  **ya está portado** (``_get_user_from_token`` y los tres crons, en
  ``models/account_edi_proxy_user.py``); falta sólo la ruta.
- ``authentication.py`` — la vuelta del proveedor de identidad; bloqueada
  además por el asistente de alta.
- ``portal.py`` — los campos Peppol en la dirección de facturación del
  portal; bloqueado por ``account_edi_ubl_cii``, por ``PEPPOL_LIST`` de
  ``account`` y por el motor QWeb.

Cada archivo lleva su desenlace medido en el docstring.
"""
