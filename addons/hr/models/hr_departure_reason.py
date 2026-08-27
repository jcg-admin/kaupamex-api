"""``hr.departure.reason`` — motivo de baja de un empleado (Odoo ``hr``).

Adaptación fiel de Odoo hr/models/hr_departure_reason.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3).

Los tres motivos maestros (despido, renuncia, jubilación) los siembra la
migración ``0003_seed_default_departure_reasons`` con sus identificadores
externos (``hr.departure_fired``/``_resigned``/``_retired``), leídos por
``_get_default_departure_reasons`` vía ``IrModelData.ref`` — el equivalente
de ``env.ref`` en este stack (``addons.base.models.ir_model.IrModelData``).
No pueden borrarse (ver ``delete()``).

.. list-table:: Desenlaces de símbolos no portados verbatim
   :header-rows: 1

   * - Símbolo
     - Desenlace
     - Detalle
   * - ``country_code`` (``related='country_id.code'``)
     - DIVERGENCIA de mecanismo
     - Sin campo ``related`` persistido en este stack, se expone como
       ``@property`` de sólo lectura — mismo patrón exacto que
       ``ResCompany.country_code`` en ``res_company.py`` de este árbol.
   * - ``_get_default_departure_reasons`` (``@api.model``)
     - DIVERGENCIA de mecanismo
     - Sin decorador ``@api.model`` en este stack, se porta como
       ``classmethod``. ``self.env.ref(xmlid)`` → ``IrModelData.ref(xmlid)``.
   * - ``_unlink_except_default_departure_reasons`` (``@api.ondelete``)
     - DIVERGENCIA de mecanismo
     - Sin decorador ``@api.ondelete`` en este stack, la guarda cuelga del
       ``delete()`` del modelo — mismo patrón exacto que
       ``account_account_tag.py::delete()`` (``MASTER_XMLIDS``) en este
       árbol. El guion bajo del nombre original no sobrevive porque el
       símbolo cambia de mecanismo (``delete()`` ES el hook equivalente,
       no un método propio que ``delete()`` llame).
"""
import fields
import models
from exceptions import UserError
from tools.translate import _

from addons.base.models import ResCompany, TimeStampedModel
from addons.base.models.ir_model import IrModelData
from orm.environments import get_current_company


def _default_country():
    """País de la compañía activa — ≙ ``env.company.country_id``."""
    company_id = get_current_company()
    if company_id is None:
        return None
    company = ResCompany.objects.filter(pk=company_id).first()
    return company.country if company is not None else None


class HrDepartureReason(TimeStampedModel):
    """``hr.departure.reason`` — catálogo de motivos de baja."""

    # Atributos de clase de modelo — los tres que la referencia declara
    # (``odoo19c: hr/models/hr_departure_reason.py:8-10``), verbatim.
    _name = 'hr.departure.reason'
    _description = "Departure Reason"
    _order = "sequence"

    #: Identificadores externos de los tres motivos maestros — ≙ los tres
    #: ``self.env.ref(...)`` que la referencia agrupa en un ``set``.
    DEFAULT_XMLIDS = (
        'hr.departure_fired',
        'hr.departure_resigned',
        'hr.departure_retired',
    )

    sequence = fields.Integer(default=10, verbose_name='Secuencia')
    name = fields.Char(
        'Motivo', required=True, translate=True,
        help='Nombre del motivo de baja (Odoo name).',
    )
    country = fields.Many2one(
        'base.ResCountry', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='hr_departure_reasons', default=_default_country,
        verbose_name='País',
        help_text='País de la compañía activa al crear el registro (Odoo country_id).',
    )

    class Meta:
        db_table = 'hr_departure_reason'
        verbose_name = 'Motivo de baja'
        verbose_name_plural = 'Motivos de baja'
        ordering = ['sequence']

    def __str__(self):
        return self.name

    @property
    def country_code(self):
        """``related='country_id.code'``."""
        country = self.country
        return getattr(country, 'code', '') if country else ''

    @classmethod
    def _get_default_departure_reasons(cls):
        """Los tres motivos maestros — ≙ ``_get_default_departure_reasons``.

        ``raise_if_not_found=False``: a diferencia de la fuente (que asume
        sembrados los tres y dejaría propagar el ``ValueError`` de
        ``env.ref``), aquí una siembra parcial o pendiente no rompe la
        consulta — devuelve el subconjunto que sí existe.
        """
        motivos = set()
        for xmlid in cls.DEFAULT_XMLIDS:
            reason = IrModelData.ref(xmlid, raise_if_not_found=False)
            if reason is not None:
                motivos.add(reason)
        return motivos

    def delete(self, *args, **kwargs):
        """Impide borrar un motivo de baja maestro.

        ≙ ``_unlink_except_default_departure_reasons`` (``@api.ondelete``
        en la referencia). Ver la tabla de divergencias del docstring del
        módulo.
        """
        maestros = {r.pk for r in self._get_default_departure_reasons()}
        if self.pk in maestros:
            raise UserError(
                _('No se pueden borrar los motivos de baja por defecto.'))
        return super().delete(*args, **kwargs)
