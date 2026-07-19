"""Modelo ``ProductExpiryConfig`` — addon ``product_expiry``.

Adaptación fiel de Odoo ``product_expiry`` sobre ``product.template``
(``product_expiry/models/product_product.py:16-40``, idéntico en 18 y 19):
la configuración de caducidad del producto. En Odoo son campos ``_inherit``
inyectados en ``product.template``; por DEC-SALE-01 (Django no inyecta columnas
cross-app) se materializan como modelo RELATED OneToOne a ``catalogue.Product``.

- ``use_expiration_date`` (o18:20) — habilita la gestión de fechas de caducidad.
- ``expiration_time`` (o18:24) — días tras la recepción hasta la caducidad.
- ``use_time`` (o18:28) — días antes de la caducidad en que empieza a deteriorarse.
- ``removal_time`` (o18:31) — días antes de la caducidad para retirarlo del stock.
- ``alert_time`` (o18:34) — días antes de la caducidad para levantar una alerta.
"""
import fields
import models

from addons.base.models import TimeStampedModel


class ProductExpiryConfig(TimeStampedModel):
    """``product.template`` caducidad — config de fechas (Odoo product_expiry)."""

    product             = models.OneToOneField(
        'catalogue.Product', on_delete=models.CASCADE, related_name='expiry_config',
        help_text='Producto (Odoo product_tmpl_id).',
    )
    use_expiration_date = fields.Boolean(
        default=False,
        help_text='Gestiona fechas de caducidad (Odoo use_expiration_date).',
    )
    expiration_time     = fields.Integer(
        default=0,
        help_text='Días tras la recepción hasta la caducidad (Odoo expiration_time).',
    )
    use_time            = fields.Integer(
        default=0,
        help_text='Días antes de la caducidad — consumo preferente (Odoo use_time).',
    )
    removal_time        = fields.Integer(
        default=0,
        help_text='Días antes de la caducidad para retirar del stock (Odoo removal_time).',
    )
    alert_time          = fields.Integer(
        default=0,
        help_text='Días antes de la caducidad para alertar (Odoo alert_time).',
    )

    class Meta:
        db_table = 'product_expiry_config'
        verbose_name = 'Config de caducidad de producto'
        verbose_name_plural = 'Configs de caducidad de productos'

    def __str__(self) -> str:
        return f'expiry({self.product}): {self.expiration_time}d'
