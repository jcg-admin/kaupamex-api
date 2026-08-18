"""``hr.work.location`` — sede física de trabajo (Odoo ``hr``).

Adaptación fiel de Odoo hr/models/hr_work_location.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3).

.. list-table:: Desenlaces de símbolos no portados verbatim
   :header-rows: 1

   * - Símbolo
     - Desenlace
     - Detalle
   * - ``company_id`` → ``company`` (``required=True``)
     - DIVERGENCIA de mecanismo
     - Se porta opcional + ``SET_NULL`` — mismo criterio D-2 ya fijado en
       ``hr_department.py``/``hr_job.py`` de este addon: "igual que el
       resto de FKs de company del proyecto (sale.order)".
   * - ``address_id`` → ``address`` (``required=True``, ``check_company=True``)
     - DIVERGENCIA de mecanismo
     - Mismo criterio D-2 que ``company`` — opcional + ``SET_NULL``. El
       marcador ``check_company=True`` lo consume ``_check_company_auto``
       en la fuente; esta clase no declara ese atributo, así que aquí es
       sólo anotación — no se fabrica un ``clean()`` que la referencia
       misma no activa automáticamente.
   * - ``location_type`` (``string="Cover Image"``)
     - DIVERGENCIA — corrección de etiqueta
     - La referencia declara el ``string`` del selection como *"Cover
       Image"*, que no describe el campo (probable inconsistencia
       upstream — no hay ningún campo de imagen en este modelo). Se
       traduce por su significado real, no por su etiqueta literal.
"""
import fields
import models

from addons.base.models import TimeStampedModel


class HrWorkLocation(TimeStampedModel):
    """``hr.work.location`` — sede de trabajo (casa, oficina, otra)."""

    # Atributos de clase de modelo — los tres que la referencia declara
    # (``odoo19c: hr/models/hr_work_location.py:8-10``), verbatim.
    _name = 'hr.work.location'
    _description = "Work Location"
    _order = 'name'

    class LocationType(models.TextChoices):
        """``location_type`` — ≙ el Selection de la referencia (``:15-18``)."""

        HOME = 'home', 'Casa'
        OFFICE = 'office', 'Oficina'
        OTHER = 'other', 'Otra'

    active = fields.Boolean(default=True, verbose_name='Activo')
    name = fields.Char(
        'Sede de trabajo', max_length=150, required=True,
        help='Nombre de la sede de trabajo (Odoo name).',
    )
    company = fields.Many2one(
        'base.ResCompany', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='hr_work_locations', verbose_name='Empresa',
        help_text='Empresa dueña de la sede (Odoo company_id, required=True '
                  'en la fuente — ver docstring del módulo).',
    )
    location_type = fields.Selection(
        max_length=6, choices=LocationType.choices, default=LocationType.OFFICE,
        verbose_name='Tipo de ubicación',
        help_text='Casa / oficina / otra (Odoo location_type).',
    )
    address = fields.Many2one(
        'base.ResPartner', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='hr_work_locations', verbose_name='Dirección de trabajo',
        help_text='Dirección de la sede (Odoo address_id, check_company=True '
                  'en la fuente — ver docstring del módulo).',
    )
    location_number = fields.Char(
        max_length=64, blank=True, default='', verbose_name='Número de ubicación',
    )

    class Meta:
        db_table = 'hr_work_location'
        verbose_name = 'Sede de trabajo'
        verbose_name_plural = 'Sedes de trabajo'
        ordering = ['name']

    def __str__(self):
        return self.name
