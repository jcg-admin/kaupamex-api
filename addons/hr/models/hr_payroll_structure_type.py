"""``hr.payroll.structure.type`` — tipo de estructura salarial (Odoo ``hr``).

Adaptación fiel de Odoo hr/models/hr_payroll_structure_type.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3).

.. list-table:: Desenlaces de símbolos no portados verbatim
   :header-rows: 1

   * - Símbolo
     - Desenlace
     - Detalle
   * - ``default_resource_calendar_id`` (``Many2one`` a ``resource.calendar``)
     - PORTADO
     - ``default_resource_calendar``, con ``resource`` declarado en el
       ``depends`` del manifest. Su ``default`` resuelve
       ``env.company.resource_calendar_id`` por la propiedad
       ``ResCompany.resource_calendar`` que
       ``addons/resource/models/res_company.py:52`` instala. El campo se
       declaró BLOQUEADO en el pase que portó este archivo por no tener el
       manifest en su lista de escribibles; el bloqueo era de **una línea**,
       así que se cerró en el mismo pase de consolidación en vez de
       diferirse (``hallazgo-abierto-genera-sucesor.md``: DESCONOCIDO es el
       último recurso, no el cómodo).
   * - ``country_code`` (``related='country_id.code'``)
     - DIVERGENCIA de mecanismo
     - Sin campo ``related`` persistido en este stack, se expone como
       ``@property`` de sólo lectura — mismo patrón exacto que
       ``ResCompany.country_code`` en ``res_company.py`` de este árbol.
   * - ``country_id`` (``domain=``)
     - DIVERGENCIA de mecanismo
     - El ``domain=[('id','in', env.companies.country_id.ids)]`` de la
       referencia es un filtro de UI, no una restricción de datos — mismo
       criterio que ``hr_contract_type.py`` en este mismo tramo.
"""
import fields
import models

from addons.base.models import ResCompany, TimeStampedModel
from orm.environments import get_current_company


def _current_company():
    """La compañía activa, o ``None`` si no hay contexto de empresa."""
    company_id = get_current_company()
    if company_id is None:
        return None
    return ResCompany.objects.filter(pk=company_id).first()


def _default_country():
    """País de la compañía activa — ≙ ``env.company.country_id``."""
    company = _current_company()
    return company.country if company is not None else None


def _default_resource_calendar():
    """Horario por defecto de la compañía activa.

    ≙ ``default=lambda self: self.env.company.resource_calendar_id``
    (``odoo19c: hr/models/hr_payroll_structure_type.py:10``). La propiedad
    ``ResCompany.resource_calendar`` la instala
    ``addons/resource/models/res_company.py:52``; devuelve ``None`` cuando la
    compañía todavía no tiene calendario, igual que el ``Many2one`` vacío de
    la fuente.
    """
    company = _current_company()
    return company.resource_calendar if company is not None else None


class HrPayrollStructureType(TimeStampedModel):
    """``hr.payroll.structure.type`` — familia de estructuras salariales."""

    # Atributos de clase de modelo — los dos que la referencia declara
    # (``odoo19c: hr/models/hr_payroll_structure_type.py:5-6``), verbatim.
    # Sin ``_order`` — la fuente no lo declara para este modelo.
    _name = 'hr.payroll.structure.type'
    _description = 'Salary Structure Type'

    name = fields.Char(
        'Tipo de estructura salarial', max_length=150, blank=True,
        default='', help_text='Nombre del tipo de estructura salarial (Odoo name).',
    )
    country = fields.Many2one(
        'base.ResCountry', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='hr_payroll_structure_types', default=_default_country,
        verbose_name='País',
        help_text='País de la compañía activa al crear el registro (Odoo country_id).',
    )

    # ≙ ``default_resource_calendar_id`` (``odoo19c: :8-10``). El nombre pierde
    # el sufijo ``_id`` por la convención de este árbol; el ``default`` resuelve
    # el calendario de la compañía activa.
    default_resource_calendar = fields.Many2one(
        'resource.ResourceCalendar', on_delete=models.SET_NULL, null=True,
        blank=True, related_name='hr_payroll_structure_types',
        default=_default_resource_calendar, verbose_name='Horario de trabajo',
        help_text='Horario por defecto del tipo de estructura salarial '
                  '(Odoo default_resource_calendar_id).',
    )

    class Meta:
        db_table = 'hr_payroll_structure_type'
        verbose_name = 'Tipo de estructura salarial'
        verbose_name_plural = 'Tipos de estructura salarial'

    def __str__(self):
        return self.name

    @property
    def country_code(self):
        """``related='country_id.code'``."""
        country = self.country
        return getattr(country, 'code', '') if country else ''
