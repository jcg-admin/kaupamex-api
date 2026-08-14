# -*- coding: utf-8 -*-
"""``account_check_printing`` — impresión de cheques (Odoo ``account_check_printing``).

Adaptación de ``odoo19c: addons/account_check_printing/`` (``odoo-tools@622ddc2a``,
LGPL-3 — atribución y aviso de licencia preservados, DEC-KX-03). Ofrece las
funcionalidades básicas para pagar imprimiendo cheques: numeración de
diario/pago, diseño de talón por empresa y el asistente de cheques
prenumerados.

Sin ``post_init_hook`` — Django no lo tiene
================================================

La referencia usa ``'post_init_hook': 'create_check_sequence_on_bank_journals'``
(``__manifest__.py:24``) para dar de alta la secuencia de cheques en los
diarios de banco YA existentes al instalar el módulo. Django no tiene un
gancho de post-instalación equivalente — el análogo es una **migración de
datos** (``migrations/0002_seed_check_payment_method.py``), que hace el
mismo backfill una sola vez. Los diarios de banco creados DESPUÉS de esa
migración los cubre la señal ``post_save`` que conecta
``AccountCheckPrintingConfig.ready()`` (ver ``apps.py`` y
``models/account_journal.py``, "Divergencia 2").

Wiring pendiente (fuera del alcance de este agente)
========================================================

Registrar ``'addons.account_check_printing'`` en ``INSTALLED_APPS``
(``config/settings/base.py``) — mismo criterio que ``account_debit_note``,
``account_qr_code_sepa`` y ``account_qr_code_emv``: sin ese registro Django
no descubre esta app ni corre sus migraciones.
"""
# Odoo importa aquí ``models``/``wizard``; en Django NO se puede: el
# ``__init__`` del app corre durante la FASE 1 de la carga del registro
# (``apps.populate`` importando los ``AppConfig``), antes de que los modelos
# estén poblados. Medido: ``from . import models`` aquí revienta con
# ``AppRegistryNotReady: Apps aren't loaded yet`` — la cadena la dispara
# ``models/res_company.py`` → ``fields`` → ``orm.fields_reference`` →
# ``django.contrib.contenttypes.models.ContentType``, que llama a
# ``apps.get_containing_app_config`` cuando el registro aún no está listo.
#
# Los tres modelos con tabla los descubre Django por convención en la FASE 2
# (importa ``<app>.models``, y ese ``models/__init__.py`` sí los importa). El
# wizard (``TransientModel``, ``abstract = True``) no tiene tabla, así que no
# necesita descubrimiento: lo importa directamente quien lo usa. Las tres
# extensiones sobre modelos AJENOS se cuelgan desde ``AppConfig.ready()``
# (``apps.py``), que corre cuando el registro ya está poblado.
#
# Mismo patrón que ``account_test``/``account_update_tax_tags`` y el resto de
# satélites del árbol, cuyo ``__init__`` está vacío a propósito.
