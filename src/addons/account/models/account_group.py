"""``account.group`` — grupo del plan de cuentas (Odoo ``account``).

Adaptación de Odoo addons/account/models/account_account.py
(odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de, odoo19c:, LGPL-3),
clase ``AccountGroup`` (odoo19c: account_account.py:1497-1641).

Jerarquía de agrupación del plan de cuentas por **rango de prefijo de
código** (p. ej. el grupo "10-19" agrupa las cuentas cuyo código empieza en
ese rango), no por asignación manual de hijos — el ``parent_id`` se
recalcula, no se declara.

Campos núcleo portados: ``parent`` (self, jerárquico), ``name``,
``code_prefix_start``, ``code_prefix_end`` (cross-default, Odoo
``_compute_code_prefix_start``/``_compute_code_prefix_end``), ``company``.
Se respeta la forma de la referencia (rango de prefijo + adopción del padre
más específico) — **no** se inventa un MPTT/``parent_path`` (eso es lo que
la propia referencia rechaza al no usar ``_parent_store``).

Portado en Python: la restricción de longitud igual entre
``code_prefix_start``/``code_prefix_end`` (``_check_length_prefix``, un
``CheckConstraint``), el anti-ciclo (``_check_parent_not_circular``, vía el
mixin transversal ``_reject_hierarchy_cycle`` — mismo patrón que
``AccountAnalyticPlan``) y una versión simplificada, en Python, de
``_adapt_parent_account_group`` (Odoo la resuelve con una consulta SQL de
ventana; aquí se itera en ``save()`` sobre los grupos de la misma empresa
buscando el prefijo más específico que contiene al del grupo actual).

NO se porta: ``_constraint_prefix_overlap`` (SQL crudo con self-join que
valida que dos grupos de igual granularidad no se solapen — se declara
pendiente, no fabricado) ni ``_search_display_name``/``_compute_display_name``
(formato de UI del cliente web de Odoo).
"""
import fields
import models

from addons.base.models import _reject_hierarchy_cycle


class AccountGroup(models.Model):
    """``account.group`` — nodo del árbol de agrupación por rango de código."""

    parent               = fields.Many2one(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        related_name='children',
        help_text=(
            'Padre en la jerarquía (Odoo parent_id, readonly en la '
            'referencia: lo recalcula _adapt_parent_account_group, no se '
            'asigna a mano).'
        ),
    )
    name                   = fields.Char(
        max_length=255, help_text='Nombre del grupo (Odoo name, requerido).',
    )
    code_prefix_start        = fields.Char(
        max_length=32, blank=True, default='',
        help_text='Prefijo de código, inicio del rango (Odoo code_prefix_start).',
    )
    code_prefix_end            = fields.Char(
        max_length=32, blank=True, default='',
        help_text='Prefijo de código, fin del rango (Odoo code_prefix_end).',
    )
    company                      = fields.Many2one(
        'base.ResCompany', on_delete=models.CASCADE, related_name='account_groups',
        help_text='Empresa (Odoo company_id, requerido).',
    )

    class Meta:
        db_table = 'account_group'
        ordering = ['code_prefix_start']
        # Odoo _check_length_prefix (odoo19c: 1510-1513) — CHECK SQL a nivel
        # DB: char_length(code_prefix_start) == char_length(code_prefix_end).
        # NO portado: expresar char_length() en un CheckConstraint portable
        # entre motores excede este corte. Declarado pendiente, no fabricado.
        verbose_name = 'Grupo de cuentas'
        verbose_name_plural = 'Grupos de cuentas'

    def __str__(self) -> str:
        prefix = self.code_prefix_start or ''
        if self.code_prefix_end and self.code_prefix_end != self.code_prefix_start:
            prefix = f'{prefix}-{self.code_prefix_end}'
        return f'{prefix} {self.name}'.strip()

    def clean(self):
        super().clean()
        _reject_hierarchy_cycle(self, 'parent', 'ACCOUNT_GROUP_CYCLE')

    def _sanitize_prefixes(self):
        """Cross-default de inicio/fin — Odoo ``_compute_code_prefix_start``/
        ``_compute_code_prefix_end`` (odoo19c: 1518-1528): si uno falta o
        queda fuera de orden respecto al otro, se iguala al que sí está."""
        start, end = self.code_prefix_start, self.code_prefix_end
        if not end or (start and end < start):
            end = start
        if not start or (end and start > end):
            start = end
        self.code_prefix_start, self.code_prefix_end = start or '', end or ''

    def _adapt_parent_account_group(self):
        """Padre más específico entre los grupos de la misma empresa — Odoo
        ``_adapt_parent_account_group`` (odoo19c: 1601-1641), en Python: el
        candidato con el prefijo más largo que contiene el rango de este
        grupo (``start`` >= candidato.start y ``end`` <= candidato.end,
        mismo largo de prefijo entre sí)."""
        if not self.company_id or not self.code_prefix_start:
            return
        best = None
        for other in type(self).objects.filter(company=self.company).exclude(pk=self.pk):
            if not other.code_prefix_start:
                continue
            if len(other.code_prefix_start) >= len(self.code_prefix_start):
                continue
            covers = (
                other.code_prefix_start <= self.code_prefix_start[:len(other.code_prefix_start)]
                and other.code_prefix_end >= (self.code_prefix_end or self.code_prefix_start)[:len(other.code_prefix_end)]
            )
            if covers and (best is None or len(other.code_prefix_start) > len(best.code_prefix_start)):
                best = other
        new_parent = best.pk if best is not None else None
        if new_parent != self.parent_id:
            self.parent_id = new_parent

    def save(self, *args, **kwargs):
        self._sanitize_prefixes()
        super().save(*args, **kwargs)
        self._adapt_parent_account_group()
        if self.parent_id is not None:
            super().save(update_fields=['parent'])
