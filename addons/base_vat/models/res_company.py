"""Extensión de ``res.company`` — la casilla que enciende la comprobación VIES.

Adaptación de ``odoo19c: addons/base_vat/models/res_company.py``
(``odoo-tools@622ddc2a``, LGPL-3, 10 líneas) — atribución y aviso de licencia
preservados (DEC-KX-03). El manifiesto de la fuente declara ``LGPL-3``, así que
el mecanismo es **copia + adaptación**, no reimplementación.

Porte — 2 de 2 símbolos, 0 bloqueados
======================================

.. list-table::
   :header-rows: 1
   :widths: 40 14 46

   * - Símbolo (línea)
     - Estado
     - Nota
   * - ``_inherit = 'res.company'`` (``:8``)
     - portado
     - se expresa con ``extend_model``; aquí no hay clase que lo declare
   * - ``vat_check_vies`` (``:10``)
     - portado
     - columna ``Boolean`` sobre ``base.ResCompany``

La fuente cuelga el campo con ``_inherit``; el análogo de este árbol es
``extend_model(campos=…)`` → ``add_field_if_absent``, el mismo mecanismo de
``addons/hr/models/res_company.py`` y ``addons/account/models/res_company.py``.

**Par de Django y no nombre punteado**: ``base.ResCompany`` no declara
``_name``, así que el nombre punteado no la alcanza (misma divergencia D-3 que
``stock/models/res_users.py``).

Quién lo consume, medido en la fuente
======================================

Tres sitios, y los tres se portan en este mismo pase:

- ``base_vat/models/res_partner.py:194`` — ``_compute_perform_vies_validation``
  lee ``self.env.company.vat_check_vies`` para decidir si el rótulo VIES es
  relevante.
- ``base_vat/models/res_partner.py:200`` — ``_compute_vies_valid`` sale
  temprano si **ninguna** empresa lo tiene encendido.
- ``base_vat/models/res_config_settings.py:9`` — el campo relacionado que lo
  expone en el formulario de ajustes.

La migración aditiva se genera en ``src/addons/base/migrations/`` — es donde
Django escribe el ``AddField`` de una columna colgada sobre un modelo de
``base``, igual que las nueve de ``hr`` (``0036_alter_rescompany_…``).
"""
import fields

from orm.model_classes import extend_model


def apply_base_vat_res_company_extensions():
    """Cuelga sobre ``res.company`` lo que ``base_vat`` le añade — ≙ ``_inherit``."""
    extend_model('base', 'ResCompany', campos={
        'vat_check_vies': fields.Boolean(
            default=False, verbose_name='Verify VAT Numbers',
            help_text='Odoo vat_check_vies — comprobar los identificadores '
                      'fiscales intracomunitarios contra la base VIES.',
        ),
    })
