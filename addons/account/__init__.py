"""Paquete raiz del addon ``account`` -- registra sus submodulos propios.

Importa ``tools`` (verificado seguro: no declara ningun modelo Django, solo
funciones puras y un adaptador HTTP). ``report`` NO se importa aqui --
verificado EMPIRICAMENTE que romperia el arranque:

.. code-block:: text

    django.core.exceptions.AppRegistryNotReady: Apps aren't loaded yet.

``addons/account/__init__.py`` se ejecuta durante la FASE 1 de
``apps.populate()`` (como efecto colateral de importar
``addons.account.apps`` para instanciar el ``AppConfig``), ANTES de que
``apps_ready`` se ponga en ``True``. ``report/account_invoice_report.py``
declara un modelo Django (``AccountInvoiceReport``), y ``ModelBase.__new__``
exige ``apps_ready`` para resolver su ``app_label`` -- crashea el arranque
completo, no solo el de ``account``. Reproducido y revertido en este mismo
pase (ver el hallazgo H-API-682, seccion de verificacion).

El unico punto seguro para registrar ``report`` en el registro vivo de
Django es ``addons/account/models/__init__.py`` (FASE 2, ``import_models``)
-- fuera de mi alcance de escritura en la tarea #398. Ver el docstring de
``report/__init__.py`` para el detalle completo del bloqueo.
"""
from . import tools  # noqa: F401
