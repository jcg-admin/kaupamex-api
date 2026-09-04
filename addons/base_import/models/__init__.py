"""Modelos del addon ``base_import`` — hoy sólo la inferencia de fechas.

Porte BLOQUEADO — 0 de 54 símbolos
===================================

Decisión del ejecutor en el pase de la tarea **#281** (2026-09-02): este addon
**no se abre aquí**; su porte es un pase dedicado y ya tiene sucesor registrado,
la tarea **#265** (*«Portar base_import, hoy un esqueleto con sólo
date_patterns»*).

Lo que hay portado, ``date_patterns.py``, **no cuenta como símbolo**: adapta el
cuerpo de un fragmento de método de la fuente
(``odoo19c: base_import/models/base_import.py:1728-1795``), no una clase ni un
método con nombre propio. Por eso el numerador es 0 y no 1.

Qué mide ese 54, y con qué comando
===================================

.. code-block:: text

   python3 scripts/compare_reference_symbols.py \\
       "$ODOO19C/addons/base_import/models/base_import.py"
   → 5 clases · 34 métodos · 49 símbolos declarados en total
     ImportValidationError  1 método
     Base                   1 método   (``get_import_templates``)
     Base_ImportMapping     3 campos
     ResUsers               1 método   (``_can_import_remote_urls``)
     Base_ImportImport     31 métodos  (lectura de 4 formatos, mapeo difuso,
                                        ``parse_preview``, ``execute_import``…)

   python3 scripts/compare_reference_symbols.py \\
       "$ODOO19C/addons/base_import/models/odf_ods_reader.py"
   → 1 clase ``ODSReader`` · 4 métodos  (5 símbolos)

   49 + 5 = 54

Fuera de ese conteo, y también sin portar: ``controllers/main.py``
(``ImportController.set_file``, 1 clase + 1 método).

El conteo del gate es POR ARCHIVO, no por símbolo — hallazgo de instrumento
============================================================================

``python3 scripts/check_porte_completo.py --addon base_import`` publica **2
hallazgos**, y eso hace que este addon parezca el más pequeño de los diez
``base_*`` cuando por símbolos es, con diferencia, el más grande. La causa es
la forma del hallazgo: cuando el archivo entero falta, el gate emite un
``ARCHIVO NO PORTADO`` y cuenta **1**, tenga la fuente un símbolo o cincuenta.

*Métrica:* hallazgos de ``check_porte_completo --addon``.
*Ciega a:* el tamaño de un archivo ausente. Un addon con 2 archivos sin portar
puntúa igual que uno con 2 métodos ausentes, así que el conteo **no sirve para
ordenar trabajo por esfuerzo** — que es exactamente para lo que se estaba
usando al planificar esta serie. Ordenar por esfuerzo exige el conteo de
símbolos, y ése lo da ``compare_reference_symbols.py``.

Licencia: LGPL-3 (leída del manifest de la fuente), así que el porte admite
copia + adaptación con atribución (DEC-KX-03).
"""
from addons.base_import.models import date_patterns  # noqa: F401
