"""``digest.tip`` — un consejo rotativo mostrado en el correo del digest
(Odoo ``digest``).

Adaptación de Odoo digest/models/digest_tip.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3).

Divergencia declarada
======================

**``group_id`` (``Many2one('res.groups')``, ``digest_tip.py:20-22``) NO se
porta.** La referencia usa un grupo ACL de Odoo (``default=base.group_user``,
external ID XML) para acotar qué usuarios ven cada tip. Este proyecto
autoriza por capacidad (``authz``, DEC-11), no por grupos Odoo — ``ResGroups``
existe en ``base`` por fidelidad de esquema pero no está wireado a
``HasCapability`` como eje de negocio. Sin un consumidor de "qué tips ve un
usuario según su rol" construido, la columna no aporta (mismo criterio que
el ``domain=`` de grupo no portado en ``fleet_vehicle.py``, divergencia 5).
``user_ids`` (quién ya vio el tip) sí se porta — es dato propio del tip, sin
dependencia de grupos.
"""
import fields

from addons.base.models import TimeStampedModel


class DigestTip(TimeStampedModel):
    """``digest.tip`` — un consejo mostrado una vez por usuario, en orden
    de ``sequence``."""

    sequence = fields.Integer(
        default=1, verbose_name='Secuencia',
        help_text='Odoo sequence — orden de despliegue en el correo.',
    )
    name = fields.Char(max_length=255, blank=True, default='', verbose_name='Nombre')
    user_ids = fields.Many2many(
        'base.ResUsers', blank=True, related_name='seen_digest_tips',
        verbose_name='Ya lo vieron',
        help_text='Odoo user_ids — usuarios que ya recibieron este tip.',
    )
    tip_description = fields.Html(
        blank=True, default='', verbose_name='Descripción',
    )

    class Meta:
        db_table = 'digest_tip'
        ordering = ['sequence', 'id']
        verbose_name = 'Consejo de digest'
        verbose_name_plural = 'Consejos de digest'

    def __str__(self) -> str:
        return self.name or f'Tip #{self.pk}'
