"""``hr.work.entry.type`` — el catálogo de tipos de entrada de trabajo.

Adaptación de Odoo hr_work_entry/models/hr_work_entry_type.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3, 68 líneas) — atribución y aviso de
licencia preservados (DEC-KX-03).

Atributos de clase: 2/2 (``_name``, ``_description``) verbatim — la fuente no
declara ``_order`` ni objetos de tabla.

Porte símbolo por símbolo — 13 campos + 4 métodos
==================================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``name`` (``:11``) / ``display_code`` (``:12``) / ``code`` (``:13``) /
       ``external_code`` (``:14``) / ``color`` (``:15``) / ``sequence``
       (``:16``) / ``active`` (``:17-19``) / ``is_leave`` (``:26-27``) /
       ``amount_rate`` (``:31-34``) / ``is_extra_hours`` (``:35-37``)
     - portados como columna
   * - ``country_id`` (``:20-24``)
     - portado como columna ``country`` — SIN el ``domain=`` de sesión (D-2)
   * - ``country_code`` (``:25``, ``related='country_id.code'``)
     - portado como ``property`` (related sin store no genera columna)
   * - ``is_work`` (``:28-30``) con ``_compute_is_work`` (``:61-64``) /
       ``_inverse_is_work`` (``:66-68``)
     - portado como ``property`` con setter (D-1)
   * - ``_check_work_entry_type_country`` (``:39-44``)
     - portado — ver D-3/D-4
   * - ``_check_code_unicity`` (``:46-59``)
     - portado — invocado desde ``clean()`` (≙ ``@api.constrains``)

Divergencias declaradas
========================

1. **``is_work`` es ``property`` + setter**, no ``compute=... inverse=...
   readonly=False`` — mismo criterio que ``ResourceCalendar.flexible_hours``:
   es la negación exacta de ``is_leave``, sin columna espejo que pueda
   desincronizarse. ``_compute_is_work``/``_inverse_is_work`` son el getter y
   el setter.
2. **El ``domain=`` de ``country_id`` no se porta** — es un filtro de
   formulario que lee ``self.env.companies``; el filtro equivalente lo aplica
   la capa DRF con ``orm.environments.get_current_companies()``.
3. **``env.ref('hr_work_entry.work_entry_type_attendance')`` → ``code ==
   'WORK100'``** — los XML ids de ``data/`` no se cargan aquí; el registro
   protegido se identifica por su ``code`` (``odoo19c:
   hr_work_entry/data/hr_work_entry_type_data.xml:3-7`` declara ese código).
4. **``self.env.context.get('install_mode')`` no existe** — no hay contexto de
   instalación de módulos; la exención de ``install_mode`` de la fuente no
   aplica y la validación de uso corre siempre.
5. **``@api.constrains`` → ``clean()``** — las dos validaciones se invocan
   desde ``clean()``; quien escriba sin ``full_clean()`` puede llamarlas
   directo (los nombres se conservan verbatim).
6. **``translate=True``** se anota en el campo sin traducir todavía (aviso de
   ``orm/fields_textual.py::Char``, tarea #333).
"""
import fields
import models

from addons.base.models import ResCountry, TimeStampedModel
from exceptions import UserError


#: ``code`` del registro ``hr_work_entry.work_entry_type_attendance`` de la
#: fuente (``odoo19c: hr_work_entry/data/hr_work_entry_type_data.xml:7``) —
#: aquí identifica al tipo protegido en vez del XML id (D-3).
ATTENDANCE_TYPE_CODE = 'WORK100'


class HrWorkEntryType(TimeStampedModel):
    """``hr.work.entry.type`` — un tipo de entrada de trabajo (asistencia,
    horas extra, ausencia…) con su código de nómina y su tarifa."""

    _name = 'hr.work.entry.type'
    _description = 'HR Work Entry Type'

    name = fields.Char(
        required=True, translate=True,
        help_text='Odoo name (required, translate).',
    )
    display_code = fields.Char(
        'Display Code', max_length=3, blank=True, default='', translate=True,
        help='This code can be changed, it is only for a display purpose '
             '(3 letters max)',
    )
    code = fields.Char(
        'Payroll Code', required=True,
        help='Careful, the Code is used in many references, changing it '
             'could lead to unwanted changes.',
    )
    external_code = fields.Char(
        blank=True, default='',
        help='Use this code to export your data to a third party',
    )
    color = fields.Integer(default=0)
    sequence = fields.Integer(default=25)
    active = fields.Boolean(
        'Active', default=True,
        help_text='If the active field is set to false, it will allow you to '
                  'hide the work entry type without removing it.',
    )
    country = fields.Many2one(
        ResCountry, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='work_entry_types', verbose_name='Country',
        help_text='Odoo country_id. DIVERGENCIA D-2: sin el domain= de '
                  'sesión (env.companies) — lo aplica la capa DRF.',
    )
    is_leave = fields.Boolean(
        default=False, verbose_name='Time Off',
        help_text='Allow the work entry type to be linked with time off types.',
    )
    amount_rate = fields.Float(
        default=1.0, verbose_name='Rate',
        help_text='If you want the hours should be paid double, the rate '
                  'should be 200%.',
    )
    is_extra_hours = fields.Boolean(
        default=False, verbose_name='Added to Monthly Pay',
        help_text='Check this setting if you want the hours to be considered '
                  'as extra time and added as a bonus to the basic salary.',
    )

    class Meta:
        db_table = 'hr_work_entry_type'
        verbose_name = 'Tipo de entrada de trabajo'
        verbose_name_plural = 'Tipos de entrada de trabajo'

    def __str__(self):
        return self.name

    # ------------------------------------------------------------------
    # Propiedades — related / compute sin store
    # ------------------------------------------------------------------

    @property
    def country_code(self):
        """≙ ``country_code`` (``related='country_id.code'``, ``:25``)."""
        return self.country.code if self.country_id else ''

    @property
    def is_work(self):
        """≙ ``is_work`` / ``_compute_is_work`` (``:28-30``, ``:61-64``) —
        divergencia D-1: property, no columna compute+inverse."""
        return not self.is_leave

    @is_work.setter
    def is_work(self, value):
        """≙ ``_inverse_is_work`` (``:66-68``)."""
        self.is_leave = not value

    # ------------------------------------------------------------------
    # Validaciones (≙ ``@api.constrains``, vía ``clean()`` — D-5)
    # ------------------------------------------------------------------

    def _check_work_entry_type_country(self):
        """≙ ``_check_work_entry_type_country`` (``:39-44``).

        D-3: el registro protegido se identifica por ``code == 'WORK100'``.
        D-4: sin exención por ``install_mode``. El ``@api.constrains``
        dispara sólo cuando ``country_id`` cambia; aquí el cambio se detecta
        comparando contra el valor persistido (mismo efecto).
        """
        if not self.pk:
            return
        stored_country_id = (
            HrWorkEntryType.objects.filter(pk=self.pk)
            .values_list('country_id', flat=True).first()
        )
        if stored_country_id == self.country_id:
            return
        if self.code == ATTENDANCE_TYPE_CODE:
            raise UserError(
                "You can't change the country of this specific work entry "
                'type.'
            )
        if self.work_entries.exists():
            raise UserError(
                "You can't change the Country of this work entry type cause "
                "it's currently used by the system. You need to delete "
                'related working entries first.'
            )

    def _check_code_unicity(self):
        """≙ ``_check_code_unicity`` (``:46-59``) — el mismo ``code`` no puede
        repetirse entre tipos del mismo país (o sin país)."""
        similar = HrWorkEntryType.objects.filter(
            code=self.code,
        ).filter(
            models.Q(country__isnull=True) | models.Q(country=self.country_id),
        ).exclude(pk=self.pk)
        if similar.exists():
            raise UserError(
                'The same code cannot be associated to multiple work entry '
                f'types ({self.code})'
            )

    def clean(self):
        super().clean()
        self._check_work_entry_type_country()
        self._check_code_unicity()
