"""``analytic.plan.fields.mixin`` / ``account.analytic.line`` (Odoo
``analytic``).

Adaptación fiel de Odoo analytic/models/analytic_line.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3), recortada por la misma razón que
``analytic_plan.py``/``analytic_account.py``: sin columna dinámica por plan.

``AnalyticPlanFieldsMixin`` en la referencia agrega **una columna por cada
plan raíz existente** (``account_id`` para el plan "Proyecto" + ``x_planN_id``
por cada plan adicional) más el campo sintético ``auto_account_id`` que las
unifica según el contexto (``analytic_plan_id``). Aquí se simplifica a una
**FK única** ``account`` — la línea pertenece a UNA cuenta analítica (que a
su vez pertenece a un plan jerárquico), no a "hasta N cuentas, una por plan".

Dependientes de la columna dinámica — divergencia de MECANISMO
--------------------------------------------------------------

Los siete se apoyan en el conjunto de columnas ``x_planN_id`` que aquí no
existe, porque la FK es única. No hay mecanismo que construir: la estructura
que operan no está.

``_compute_auto_account``, ``_inverse_auto_account``, ``_search_auto_account``,
``_get_plan_fnames``, ``_get_mandatory_plans``, ``_get_plan_domain``,
``_get_account_node_context``.

Los cuatro del arch — su veredicto medido
-------------------------------------------

``default_get``, ``fields_get``, ``_get_view`` y ``_patch_view`` **no** son
"sin análogo en una API DRF" — esa lectura estaba mal y era el camino barato.
Medido contra el stack:

===============  ==========  ==================================================
Símbolo          Veredicto   Por qué
===============  ==========  ==================================================
``default_get``  **TRAE**    ya existe: ``orm/models.py:462``. Lo que falta es
                             la mitad de esta clase, no el mecanismo.
``fields_get``   CONSTRUYE   0 defs en el árbol; las primitivas están
                             (``_meta.get_fields`` de Django + el serializer
                             de DRF). Sin dependencia de fuera.
``_get_view``    CONSTRUYE   el arch lo guarda ``ir.ui.view``; ver la arista
``_patch_view``              de abajo.
===============  ==========  ==================================================

BLOQUEADO por ``get_views`` — el arch se lo entrega esa familia, que aún no se
porta. Sucesor: tarea **#178**.

``category`` — ya se amplía, y el docstring decía lo contrario
---------------------------------------------------------------

Decía *"otros addons de Odoo extienden esa selección; no aplica aquí"*. Es
falso contra este mismo árbol: ``account/models/account_analytic_line.py``
**ya** amplía el vocabulario con ``extend_selection_choices``, que es el
receptor de ``selection_add`` (``orm/model_classes.py``).

El campo se declara **sin** ``required``, y eso es fiel: la fuente tampoco lo
declara (``odoo19c: analytic/models/analytic_line.py:218-221`` — un
``fields.Selection`` pelado con ``default='other'``). Por eso los valores que
otros addons le suman toman la política de borrado por defecto, ``'set null'``.

``fiscal_year_search`` — su veredicto medido
----------------------------------------------

No es "campo virtual sólo de filtro de vista": la fuente lo declara
``store=False`` con ``search='_search_fiscal_date'``
(``odoo19c: :222-226``), y su cuerpo (``:272-274``) es un filtro de dominio
real sobre ``date``. Faltan dos mecanismos, ambos con sucesor registrado:

BLOQUEADO por ``compute_fiscalyear_dates`` — el rango del ejercicio fiscal
sale de ``res.company`` y aquí da 0 defs. Sucesor: tarea **#207**.

BLOQUEADO por ``search`` — el enganche de filtro de un campo no persistido;
``store=False`` ya está construido (``orm/fields_nonstored.py``), el filtro no.
Sucesor: tarea **#208**.

Los dos son CONSTRUYE, no EXCLUIDO: ``datetime`` + ``dateutil`` y el ``Q`` de
Django bastan, sin dependencia nueva.
"""
import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError

import fields
import models

from addons.base.models import DecimalPrecision


class AnalyticPlanFieldsMixin(models.Model):
    """Mixin abstracto: agrega la FK a la cuenta analítica (Odoo
    ``analytic.plan.fields.mixin``, simplificado — ver docstring del módulo)."""

    account = fields.Many2one(
        'analytic.AccountAnalyticAccount', on_delete=models.PROTECT,
        null=True, blank=True, related_name='lines',
        verbose_name='Cuenta analítica',
        help_text='Odoo account_id (ondelete=restrict). Simplificación de '
                   'columna única — ver docstring del módulo.',
    )

    class Meta:
        abstract = True

    def clean(self):
        """Fiel a ``_check_account_id`` (odoo19c: líneas 93-98), reducido a
        un único campo: "debe haber una cuenta analítica establecida"."""
        super().clean()
        if not self.account_id:
            raise ValidationError({'account': 'ANALYTIC_LINE_ACCOUNT_REQUIRED'})

    def _get_distribution_key(self):
        """Fiel a ``_get_distribution_key`` (odoo19c: línea 68-69)."""
        return str(self.account_id) if self.account_id else ''

    def _get_analytic_distribution(self):
        """Fiel a ``_get_analytic_distribution`` (odoo19c: líneas 71-73)."""
        key = self._get_distribution_key()
        return {} if not key else {key: 100}


class AccountAnalyticLine(AnalyticPlanFieldsMixin, models.Model):
    """``account.analytic.line`` — apunte analítico (Odoo ``analytic``)."""

    CATEGORIES = [('other', 'Otro')]

    name = fields.Char(
        max_length=255, verbose_name='Descripción',
        help_text='Odoo name (requerido).',
    )
    date = fields.Date(
        default=datetime.date.today, db_index=True, verbose_name='Fecha',
    )
    amount = fields.Monetary(
        max_digits=16, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Importe', help_text='Odoo amount (requerido).',
    )
    unit_amount = fields.Float(default=0.0, verbose_name='Cantidad')
    product_uom = fields.Many2one(
        'uom.Uom', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='analytic_lines', verbose_name='Unidad',
    )
    partner = fields.Many2one(
        'base.ResPartner', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='analytic_lines', verbose_name='Contacto',
    )
    user = fields.Many2one(
        'base.ResUsers', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='analytic_lines', verbose_name='Usuario',
        help_text='Odoo user_id. Sin default a env.user (ver docstring: '
                   'esta API no acopla el modelo al usuario ambiental).',
    )
    company = fields.Many2one(
        'base.ResCompany', on_delete=models.CASCADE,
        related_name='analytic_lines', verbose_name='Empresa',
        help_text='Odoo company_id (requerido, readonly).',
    )
    category = fields.Selection(
        max_length=16, choices=CATEGORIES, default='other',
        verbose_name='Categoría',
    )

    class Meta:
        db_table = 'account_analytic_line'
        ordering = ['-date', '-id']
        verbose_name = 'Apunte analítico'
        verbose_name_plural = 'Apuntes analíticos'

    def __str__(self):
        return self.name

    @property
    def currency(self):
        """Odoo ``currency_id`` (``related="company_id.currency_id"``)."""
        return self.company.currency

    @property
    def analytic_precision(self):
        """Odoo ``analytic_precision`` (``store=False``, decimal.precision
        "Percentage Analytic"). Mismo patrón que ``Uom._precision_digits``
        (``addons/uom/models/uom_uom.py``): consulta directa, sin helper
        ``precision_get`` en este árbol."""
        precision = DecimalPrecision.objects.filter(
            name='Percentage Analytic',
        ).first()
        return precision.digits if precision else 2
