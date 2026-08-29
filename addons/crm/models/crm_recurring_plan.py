"""Modelo ``CrmRecurringPlan`` — addon ``crm``.

Adaptación fiel de Odoo ``crm/models/crm_recurring_plan.py``
(``crm.recurring.plan``): plan de ingreso recurrente de una oportunidad. Se
portan los cuatro campos, los tres atributos de clase y su restricción.
"""
import fields
import models

from addons.base.models import TimeStampedModel


class CrmRecurringPlan(TimeStampedModel):
    """``crm.recurring.plan`` — plan de ingreso recurrente."""

    _name = 'crm.recurring.plan'
    _description = "CRM Recurring revenue plans"
    _order = "sequence"

    # Odoo name (crm_recurring_plan.py:11, required, translate).
    name             = fields.Char(
        max_length=255, help_text='Nombre del plan (Odoo name).',
    )
    # Odoo number_of_months (crm_recurring_plan.py:12, required).
    number_of_months = fields.Integer(
        help_text='Número de meses del plan (Odoo number_of_months).',
    )
    # Odoo active (crm_recurring_plan.py:13, default True).
    active           = fields.Boolean(
        default=True, help_text='Archivar sin borrar (Odoo active).',
    )
    # Odoo sequence (crm_recurring_plan.py:14, default 10).
    sequence         = fields.Integer(
        default=10, help_text='Orden de listado (Odoo sequence).',
    )

    class Meta:
        db_table = 'crm_recurring_plan'
        ordering = ['sequence']
        verbose_name = 'Plan de ingreso recurrente'
        verbose_name_plural = 'Planes de ingreso recurrente'
        constraints = [
            # ≙ ``_check_number_of_months`` (crm_recurring_plan.py:16-19).
            models.CheckConstraint(
                condition=models.Q(number_of_months__gte=0),
                name='crm_recurring_plan_check_number_of_months',
                violation_error_message="El número de meses no puede ser negativo.",
            ),
        ]

    def __str__(self) -> str:
        return self.name
