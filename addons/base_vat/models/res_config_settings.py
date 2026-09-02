"""Extensión de ``res.config.settings`` — la casilla VIES en el formulario.

Adaptación de ``odoo19c: addons/base_vat/models/res_config_settings.py``
(``odoo-tools@622ddc2a``, LGPL-3, 10 líneas) — atribución y aviso de licencia
preservados (DEC-KX-03).

Porte — 2 de 2 símbolos, 0 bloqueados
======================================

.. list-table::
   :header-rows: 1
   :widths: 44 14 42

   * - Símbolo (línea)
     - Estado
     - Nota
   * - ``_inherit = 'res.config.settings'`` (``:7``)
     - portado
     - lo lleva la clase destino, que ya lo declara
   * - ``vat_check_vies`` (``:9-10``)
     - portado
     - ``related='company_id.vat_check_vies'``, ``readonly=False``

Por qué NO usa ``extend_model``
================================

El destino —``addons.base_setup.models.res_config_settings.ResConfigSettings``—
es un modelo **abstracto** (``class Meta: abstract = True``, ``:198-200``), y
``extend_model`` direcciona por el registro de Django, que sólo conoce modelos
concretos. Aquí se llama a :func:`orm.model_classes.add_field_if_absent`
directamente, que es el mismo mecanismo un nivel más abajo — el que
``extend_model(campos=…)`` usa por dentro.

Que el destino sea abstracto **no** impide que el campo llegue a las clases
concretas: ``related=`` sobre un campo sin ``store`` produce un descriptor
(``orm.fields_nonstored.NonStored``), y un descriptor colgado del padre se
resuelve por MRO en cada subclase. Es lo mismo que hace ``report_footer``
(``base_setup/models/res_config_settings.py:256``), declarado en esa misma
clase abstracta y leído desde ``SiteConfigSettings``.

Divergencia declarada
======================

**El nombre de la clase destino.** La fuente declara su propia
``ResConfigSettings`` con ``_inherit``; aquí el formulario ya existe como una
sola clase abstracta que todos los addons amplían, así que este archivo no
declara clase — cuelga el campo sobre la que hay. Mismo criterio que
``base_geolocalize/models/res_partner.py``.
"""
import fields

from addons.base_setup.models.res_config_settings import ResConfigSettings
from orm.model_classes import add_field_if_absent


def apply_base_vat_res_config_settings_extensions():
    """Cuelga ``vat_check_vies`` sobre el formulario de ajustes."""
    add_field_if_absent(ResConfigSettings, 'vat_check_vies', fields.Boolean(
        related='company_id.vat_check_vies', readonly=False,
        verbose_name='Verify VAT Numbers',
        help_text='Odoo vat_check_vies — refleja la casilla de la empresa que '
                  'enciende la comprobación VIES.'))
