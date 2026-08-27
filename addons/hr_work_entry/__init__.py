"""Addon ``hr_work_entry`` — entradas de trabajo (≙ Odoo ``hr_work_entry``).

Adaptación de Odoo Community ``hr_work_entry`` (odoo-tools@622ddc2a, odoo19c:,
LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Qué hay en la fuente y qué se porta aquí (medido con ``ls`` + ``wc -l``):

- ``models/`` — 8 archivos ``.py`` de contenido (1408 líneas junto al wizard):
  3 modelos concretos (``hr.work.entry``, ``hr.work.entry.type``,
  ``hr.user.work.entry.employee``) y 5 extensiones (``hr.employee``,
  ``hr.version``, ``resource.calendar``, ``resource.calendar.attendance``,
  ``resource.calendar.leaves``). **Se portan los 8** — las extensiones se
  aplican tarde desde ``HrWorkEntryConfig.ready()`` (``apps.py``).
- ``wizard/`` — 1 archivo (``hr.work.entry.regeneration.wizard``,
  ``TransientModel``). **Se porta** con el patrón clase-sin-tabla de
  ``hr/wizard/hr_departure_wizard.py``.
- ``data/``, ``security/``, ``views/``, ``static/``, ``i18n/``, ``tests/`` —
  artefactos del cliente/carga XML de Odoo; **no se portan** (mismo criterio
  que ``account_debit_note/__init__.py``). Consecuencia declarada: los XML ids
  de ``data/hr_work_entry_type_data.xml`` no existen aquí — los ``env.ref``
  de la fuente se resuelven por ``code`` (``WORK100``/``OVERTIME``/
  ``LEAVE100``), divergencia declarada en cada método que los usa.

Odoo importa aquí ``models``/``wizard``; en Django NO se puede: el registro de
apps aún no está poblado en tiempo de import de este paquete (patrón
``addons/utm/__init__.py``, sin imports).
"""
