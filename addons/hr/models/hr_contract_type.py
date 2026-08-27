"""``hr.contract.type`` — catálogo de tipos de contrato (Odoo ``hr``).

Adaptación fiel de Odoo hr/models/hr_contract_type.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3).

Cuatro símbolos en la referencia: ``name``, ``code`` (compute+store,
readonly=False), ``sequence``, ``country_id``, y el método
``_compute_code``. Los cuatro se portan.

.. list-table:: Desenlaces de símbolos no portados verbatim
   :header-rows: 1

   * - Símbolo
     - Desenlace
     - Detalle
   * - ``country_id`` (``domain=``)
     - DIVERGENCIA de mecanismo
     - El ``domain=lambda self: [('id','in', self.env.companies.country_id.ids)]``
       de la referencia es un filtro de **UI** (qué opciones ofrece el
       desplegable), no una restricción de datos — mismo criterio ya
       documentado en ``fleet_vehicle.py``/``product_document.py`` de este
       árbol. No hay ``domain=`` de campo en este ORM; se declara aquí y no
       se enforce a nivel de columna.
   * - ``_compute_code`` (``@api.depends('name')``, ``store=True``)
     - DIVERGENCIA de mecanismo
     - Sin ``@api.depends``/columna computada persistida en este stack, el
       relleno automático se resuelve en ``save()`` — mismo patrón que
       ``hr_department.py::_compute_parent_path`` y
       ``digest.py::save()`` (``next_run_date``) en este mismo árbol.
"""
import fields
import models

from addons.base.models import TimeStampedModel


class HrContractType(TimeStampedModel):
    """``hr.contract.type`` — tipo de contrato (temporal, indefinido, ...)."""

    # Atributos de clase de modelo — los tres que la referencia declara
    # (``odoo19c: hr/models/hr_contract_type.py:8-10``), verbatim.
    _name = 'hr.contract.type'
    _description = 'Contract Type'
    _order = 'sequence'

    name = fields.Char(
        'Nombre', required=True, translate=True,
        help='Nombre del tipo de contrato (Odoo name).',
    )
    code = fields.Char(
        blank=True, default='', verbose_name='Código',
        help_text=(
            'Código corto (Odoo code). Se auto-rellena desde name si se '
            'deja vacío — ver save() (Odoo _compute_code).'
        ),
    )
    sequence = fields.Integer(default=0, verbose_name='Secuencia')
    country = fields.Many2one(
        'base.ResCountry', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='hr_contract_types', verbose_name='País',
        help_text=(
            'País asociado al tipo de contrato (Odoo country_id). El '
            'domain= de la referencia es un filtro de UI — ver docstring '
            'del módulo.'
        ),
    )

    class Meta:
        db_table = 'hr_contract_type'
        verbose_name = 'Tipo de contrato'
        verbose_name_plural = 'Tipos de contrato'
        ordering = ['sequence']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """Auto-rellena ``code`` desde ``name`` si está vacío.

        ≙ ``_compute_code`` (``@api.depends('name')``, ``store=True``,
        ``readonly=False`` en la referencia): recomputa cuando ``name``
        cambia, pero sólo si ``code`` sigue vacío — el usuario puede
        sobreescribirlo y esa elección se respeta.
        """
        if not self.code:
            self.code = self.name
        super().save(*args, **kwargs)
