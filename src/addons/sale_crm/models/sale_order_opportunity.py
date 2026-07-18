"""Modelo ``SaleOrderOpportunity`` — addon ``sale_crm``.

Adaptación de Odoo ``sale_crm``, que **extiende** ``sale.order`` con
``opportunity_id`` (Many2one a ``crm.lead``) y ``crm.lead`` con el conteo de
órdenes. Como módulo-extensión (DEC-SALE-01), en Django es una app propia con
**modelo relacionado** (OneToOne a ``sale.order`` → ``crm.CrmLead``).

Bridge ``sale`` + ``crm``: atribuye cada orden a la oportunidad que la originó.
"""
from django.db import models

from core.models import TimeStampedModel


class SaleOrderOpportunity(TimeStampedModel):
    """Vincula una ``sale.order`` a su ``crm.lead`` (Odoo opportunity_id)."""

    order       = models.OneToOneField(
        'sale.SaleOrder', on_delete=models.CASCADE, related_name='opportunity_link',
        help_text='Orden de venta (Odoo sale.order).',
    )
    opportunity = models.ForeignKey(
        'crm.CrmLead', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='sale_orders', help_text='Oportunidad (Odoo opportunity_id).',
    )

    class Meta:
        db_table = 'sale_order_opportunity'
        verbose_name = 'Oportunidad de orden de venta'
        verbose_name_plural = 'Oportunidades de órdenes de venta'

    def __str__(self) -> str:
        return f'{self.order} ← {self.opportunity or "sin oportunidad"}'

    @classmethod
    def order_count_for(cls, lead) -> int:
        """Conteo de órdenes de una oportunidad (Odoo crm.lead.sale_order_count)."""
        return cls.objects.filter(opportunity=lead).count()
