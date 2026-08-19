"""Asistentes del addon ``account_peppol``.

≙ ``odoo19c: addons/account_peppol/wizard/__init__.py``, que importa los
cuatro. Aquí no se importa nada: **los cuatro están bloqueados** y son
documentación.

- ``peppol_registration.py`` — el alta en la red. Bloqueado por
  ``account_edi_ubl_cii`` (``peppol_eas`` / ``peppol_endpoint``). Sus dos
  llamadas al proxy sí están portadas, en ``tools/peppol_iap_connector.py``.
- ``peppol_config_wizard.py`` — los servicios dados de alta. Proyección de
  campos ya portados en ``models/res_company.py``; su llamada real
  (``_peppol_get_services``) está portada.
- ``account_move_send_wizard.py`` / ``account_move_send_batch_wizard.py`` —
  la capa de formulario del flujo de salida, bloqueado entero (ver
  ``models/account_move_send.py``).

Cada archivo lleva su desenlace medido en el docstring.
"""
