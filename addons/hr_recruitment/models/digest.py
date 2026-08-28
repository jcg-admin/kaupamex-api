"""``digest.digest`` — el KPI de nuevos empleados en el correo periódico
(Odoo ``hr_recruitment``).

Adaptación de Odoo ``hr_recruitment/models/digest.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 26 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 1 de 4, 3 BLOQUEADOS
====================================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``kpi_hr_recruitment_new_colleagues`` (``:9``)
     - portado
   * - ``kpi_hr_recruitment_new_colleagues_value`` (``:10``)
     - BLOQUEADO — su ``compute`` depende del símbolo siguiente
   * - ``_compute_kpi_hr_recruitment_new_colleagues_value`` (``:12-17``)
     - BLOQUEADO — delega en ``_calculate_company_based_kpi``, que
       ``addons.digest.models.digest.DigestDigest`` declara **divergencia
       de mecanismo, no portado** (su propio docstring, punto 4: "los dos
       KPIs base escalan… no por el ``_calculate_company_based_kpi``
       genérico de la referencia"). Sin el genérico, este KPI no tiene de
       dónde heredar el álgebra de "empresas visibles del usuario".
   * - ``_compute_kpis_actions`` (``:19-22``)
     - BLOQUEADO — el propio ``digest.py`` de ``addons.digest`` lista
       ``_compute_kpis_actions`` entre los ~230 LOC "PENDIENTE DE
       INTEGRAR" (su punto 7); no hay método previo del que relevarse.

Sólo se porta la columna booleana — es la única pieza sin dependencia de
las dos ausentes.
"""
import fields
from orm.model_classes import extend_model


def apply_hr_recruitment_digest_extensions():
    """Cuelga sobre ``digest.digest`` lo que ``hr_recruitment`` le añade —
    ≙ ``_inherit`` (parcial declarado, ver docstring del módulo)."""
    extend_model('digest', 'DigestDigest', campos={
        'kpi_hr_recruitment_new_colleagues': fields.Boolean(
            default=False, verbose_name='Nuevos empleados',
            help_text='Odoo kpi_hr_recruitment_new_colleagues ("New '
                      'Employees"). Su valor calculado '
                      '(kpi_hr_recruitment_new_colleagues_value) queda '
                      'BLOQUEADO por ``el motor de compute`` — ver docstring '
                      'del módulo.',
        ),
    })
