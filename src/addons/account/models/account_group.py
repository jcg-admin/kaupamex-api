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

Portado en Python: el anti-ciclo (``_check_parent_not_circular``, vía el
mixin transversal ``_reject_hierarchy_cycle`` — mismo patrón que
``AccountAnalyticPlan``) y una versión simplificada, en Python, de
``_adapt_parent_account_group`` (Odoo la resuelve con una consulta SQL de
ventana; aquí se itera en ``save()`` sobre los grupos de la misma empresa
buscando el prefijo más específico que contiene al del grupo actual).

**Corrección 2026-08-06 (H-API-323, tarea #113) — las dos restricciones de
prefijo SÍ se hacen cumplir; ninguna quedaba fuera del ORM.** Redacciones
previas declaraban ``_check_length_prefix`` "no portable en un
``CheckConstraint``" y ``_constraint_prefix_overlap`` "pendiente". Medido:
Django SÍ expresa ``LENGTH(a) = LENGTH(b)`` en un ``CheckConstraint`` —
``django.db.models.lookups.Exact`` tiene ``conditional = True`` y acepta dos
``Func`` (aquí ``Length``) como operandos, así que ``Exact(Length(F('a')),
Length(F('b')))`` es un `condition=` válido (verificado con
``constraint.constraint_sql()``: compila a
``CHECK (LENGTH(code_prefix_start) = (LENGTH(code_prefix_end)))``). No exigía
registrar el lookup ``__length`` global de ``CharField`` (que no viene
registrado por defecto) ni relajar el corte — exigía construir la expresión
con las piezas que el ORM ya trae, igual que ``api.depends``/``Command``
antes. Ver ``_check_prefix_length`` (duplicado en ``clean()``, ver docstring
del método) y el ``CheckConstraint`` de ``Meta.constraints``.

``_constraint_prefix_overlap`` (self-join SQL crudo contra las filas
hermanas) se porta a Python en ``clean()`` — no es expresable como
``CheckConstraint`` (compara una fila contra el resto de la tabla, no
consigo misma); es la misma familia de restricción que
``_check_parent_not_circular``, y se resuelve con el mismo patrón: una
consulta del ORM sobre ``type(self).objects``.

NO se porta: ``_search_display_name``/``_compute_display_name`` (formato de
UI del cliente web de Odoo, sin análogo en esta API).
"""
from django.core.exceptions import ValidationError
from django.db.models import F
from django.db.models.functions import Length
from django.db.models.lookups import Exact

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
        verbose_name = 'Grupo de cuentas'
        verbose_name_plural = 'Grupos de cuentas'
        constraints = [
            # Odoo _check_length_prefix (odoo19c: 1510-1513) — CHECK SQL a
            # nivel DB: char_length(start) == char_length(end). Sin COALESCE
            # (que la referencia sí usa): nuestros campos son NOT NULL con
            # default='' (Django CharField sin null=True nunca persiste
            # NULL), así que LENGTH() ya nunca ve NULL.
            models.CheckConstraint(
                condition=Exact(
                    Length(F('code_prefix_start')), Length(F('code_prefix_end')),
                ),
                name='account_group_prefix_length_eq',
                violation_error_code='ACCOUNT_GROUP_PREFIX_LENGTH_MISMATCH',
            ),
        ]

    def __str__(self) -> str:
        prefix = self.code_prefix_start or ''
        if self.code_prefix_end and self.code_prefix_end != self.code_prefix_start:
            prefix = f'{prefix}-{self.code_prefix_end}'
        return f'{prefix} {self.name}'.strip()

    def clean(self):
        super().clean()
        _reject_hierarchy_cycle(self, 'parent', 'ACCOUNT_GROUP_CYCLE')
        self._check_prefix_length()
        self._check_prefix_overlap()

    def _check_prefix_length(self):
        """``code_prefix_start`` y ``code_prefix_end`` deben tener la misma
        longitud — Odoo ``_check_length_prefix`` (odoo19c: 1510-1513).

        El ``CheckConstraint`` de ``Meta.constraints`` es la garantía real
        (nivel DB, se cumple sin importar el camino de escritura). Esta
        duplicación en Python existe para que ``clean()`` — el punto que
        esta clase y sus hermanas (``AccountAnalyticPlan``, ``HrDepartment``)
        ya usan para exponer un error legible con ``ValidationError`` y
        ``codigo_error`` — la detecte también; ``clean()`` NO ejecuta
        ``Meta.constraints`` (eso sólo ocurre vía ``validate_constraints()``/
        ``full_clean()``, que este proyecto no invoca desde ``save()``, ver
        precedente en ``_check_parent_not_circular``)."""
        start = self.code_prefix_start or ''
        end = self.code_prefix_end or ''
        if len(start) != len(end):
            raise ValidationError({
                'code_prefix_end': 'ACCOUNT_GROUP_PREFIX_LENGTH_MISMATCH',
            })

    def _check_prefix_overlap(self):
        """Rechaza que el rango de prefijo de ``self`` se solape con el de
        otro grupo de la misma empresa y granularidad (misma longitud de
        prefijo) — Odoo ``_constraint_prefix_overlap`` (odoo19c: 1549-1568).

        La referencia lo resuelve con un self-join SQL crudo contra la
        propia tabla; aquí se porta a una consulta del ORM sobre las filas
        hermanas — no es expresable como ``CheckConstraint`` (que sólo ve
        la fila que se escribe, no el resto de la tabla). Mismo criterio de
        solape que la referencia, verbatim: dos rangos se solapan si el
        inicio de uno cae dentro del rango del otro, en cualquier
        dirección."""
        start = self.code_prefix_start
        if not self.company_id or not start:
            return
        end = self.code_prefix_end or start
        conflict = (
            type(self).objects
            .filter(company_id=self.company_id)
            .exclude(pk=self.pk)
            .annotate(_prefix_length=Length('code_prefix_start'))
            .filter(_prefix_length=len(start))
            .filter(
                models.Q(code_prefix_start__lte=start, code_prefix_end__gte=start)
                | models.Q(code_prefix_start__gte=start, code_prefix_start__lte=end)
            )
        )
        if conflict.exists():
            raise ValidationError({
                'code_prefix_start': 'ACCOUNT_GROUP_PREFIX_OVERLAP',
            })

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
