"""``account.analytic.plan`` / ``account.analytic.applicability`` (Odoo
``analytic``).

Adaptación fiel de Odoo analytic/models/analytic_plan.py (odoo-tools@622ddc2a,
odoo19c:, LGPL-3), con un recorte deliberado y documentado.

Lo que SÍ se porta (estructura + jerarquía):
    ``name``, ``description``, ``parent``/``parent_path`` (jerarquía árbol,
    igual patrón que ``hr.HrDepartment``), ``color``, ``sequence``,
    ``default_applicability`` y el modelo ``account.analytic.applicability``
    completo (incluyendo ``_get_score``, que es Python puro).

Lo que NO se porta — **el sistema de columna dinámica por plan**
(``_column_name``, ``_strict_column_name``, ``_sync_plan_column``,
``_sync_all_plan_column``, ``_find_plan_column``, ``_find_related_field``,
``_hierarchy_name``, ``unlink`` override, ``get_relevant_plans``,
``_get_all_plans``/``__get_all_plans``, ``_is_subplan_field_used``):

    En la referencia, cada plan raíz agrega una **columna nueva** a
    ``account.analytic.line`` (``x_planN_id``) vía ``ir.model.fields`` +
    DDL en caliente — un mecanismo de meta-programación de esquema que Django
    no tiene como característica del ORM (las migraciones son estáticas,
    generadas por ``makemigrations``, no runtime). Reimplementarlo exigiría un
    generador de migraciones a medida, fuera del alcance de este corte.

    **Simplificación adoptada**: ``account.analytic.line`` usa una FK única
    ``account`` (ver ``analytic_line.py``) en vez de una columna por plan
    raíz. Un ``AccountAnalyticAccount`` sigue perteneciendo a un
    ``AccountAnalyticPlan`` (jerárquico), pero la línea no distingue "en qué
    plan" están sus cuentas más que a través de ``account.plan``.

    También quedan fuera ``action_view_analytical_accounts`` /
    ``action_view_children_plans`` (acciones de ventana del cliente web de
    Odoo, sin análogo en esta API) y ``_onchange_parent_id`` (onchange de
    formulario, sin análogo en DRF).

``company_dependent`` (Odoo) en ``default_applicability``: Django no tiene
"valor por defecto distinto por compañía activa" a nivel de campo (eso es
infraestructura ``ir.property`` de Odoo). Se simplifica a un default fijo
(``'optional'``) igual para todas las compañías — documentado, no fabricado
como feature nueva.
"""
from random import randint

from django.core.exceptions import ValidationError

import fields
import models

from addons.base.models import _reject_hierarchy_cycle

#: Compartido entre ``AccountAnalyticPlan.default_applicability`` y
#: ``AccountAnalyticApplicability.applicability`` — misma enumeración que la
#: referencia (``odoo19c: analytic_plan.py:77-82,419-423``).
APPLICABILITY_CHOICES = [
    ('optional', 'Opcional'),
    ('mandatory', 'Obligatorio'),
    ('unavailable', 'No disponible'),
]


def _default_color():
    """Color aleatorio 1-11, fiel a ``_default_color`` (odoo19c: línea 20-21)."""
    return randint(1, 11)


class AccountAnalyticPlan(models.Model):
    """``account.analytic.plan`` — árbol de planes analíticos (sin columna
    dinámica; ver docstring del módulo)."""

    name = fields.Char(
        max_length=255, verbose_name='Nombre',
        help_text='Nombre del plan (Odoo name, requerido, traducible).',
    )
    description = fields.Text(
        blank=True, default='', verbose_name='Descripción',
    )
    parent = fields.Many2one(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        related_name='children', verbose_name='Plan padre',
        help_text='Odoo parent_id (ondelete=cascade).',
    )
    parent_path = fields.Char(
        max_length=255, blank=True, default='', db_index=True,
    )
    color = fields.Integer(default=_default_color, verbose_name='Color')
    sequence = fields.Integer(default=10, verbose_name='Secuencia')
    default_applicability = fields.Selection(
        max_length=16, choices=APPLICABILITY_CHOICES, default='optional',
        verbose_name='Aplicabilidad por defecto',
        help_text=(
            'Odoo default_applicability; en la referencia es '
            'company_dependent — aquí un default fijo (ver docstring).'
        ),
    )

    class Meta:
        db_table = 'account_analytic_plan'
        ordering = ['sequence', 'id']
        verbose_name = 'Plan analítico'
        verbose_name_plural = 'Planes analíticos'

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        _reject_hierarchy_cycle(self, 'parent', 'ANALYTIC_PLAN_CYCLE')

    def _compute_parent_path(self):
        """Ruta materializada del ancestro, terminada en ``/``.

        Espeja el patrón a mano de ``hr.HrDepartment`` (no el flag
        ``_parent_store`` que la referencia da vía ORM).
        """
        if self.parent_id is None:
            return f'{self.pk}/'
        return f'{self.parent.parent_path}{self.pk}/'

    def save(self, *args, **kwargs):
        """Mantiene la ruta materializada, que en la referencia mantiene el ORM."""
        super().save(*args, **kwargs)
        path = self._compute_parent_path()
        if path != self.parent_path:
            self.parent_path = path
            super().save(update_fields=['parent_path'])

    @property
    def complete_name(self):
        """``[abuelo] / [padre] / [self]`` — fiel a ``_compute_complete_name``
        (odoo19c: líneas 139-145), iterativo en vez de recursivo por nodo."""
        names = []
        node = self
        seen = set()
        while node is not None and node.pk not in seen:
            names.append(node.name)
            seen.add(node.pk)
            node = node.parent
        return ' / '.join(reversed(names))

    @property
    def root(self):
        """Plan raíz del árbol — análogo de ``root_id`` (odoo19c: líneas
        129-132), usado por ``AnalyticMixin._merge_distribution``."""
        node = self
        seen = set()
        while node.parent_id is not None and node.pk not in seen:
            seen.add(node.pk)
            node = node.parent
        return node

    @property
    def account_count(self):
        """Cuentas directas de este plan (Odoo ``account_count``, no
        ``all_account_count`` recursivo — ver docstring del módulo)."""
        return self.accounts.count()

    @property
    def children_count(self):
        return self.children.count()


class AccountAnalyticApplicability(models.Model):
    """``account.analytic.applicability`` — regla de aplicabilidad por plan
    raíz + dominio de negocio + compañía. Portado completo: es Python puro,
    sin dependencia del sistema de columna dinámica."""

    analytic_plan = fields.Many2one(
        'analytic.AccountAnalyticPlan', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='applicability_ids',
        verbose_name='Plan analítico',
    )
    business_domain = fields.Selection(
        max_length=32,
        choices=[('general', 'Miscelánea')],
        verbose_name='Dominio de negocio',
        help_text=(
            'Odoo business_domain; único valor en la referencia base '
            '(otros addons de Odoo extienden la selección — no aplica aquí).'
        ),
    )
    applicability = fields.Selection(
        max_length=16, choices=APPLICABILITY_CHOICES,
        verbose_name='Aplicabilidad',
    )
    company = fields.Many2one(
        'base.ResCompany', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='analytic_applicabilities', verbose_name='Empresa',
    )

    class Meta:
        db_table = 'account_analytic_applicability'
        verbose_name = 'Aplicabilidad de plan analítico'
        verbose_name_plural = 'Aplicabilidades de plan analítico'
        # Ver el comentario extenso en ``AccountAnalyticPlan.Meta``.

    def __str__(self):
        return f'{self.analytic_plan_id} / {self.business_domain}'

    def clean(self):
        super().clean()
        if not self.business_domain:
            raise ValidationError({'business_domain': 'REQUIRED'})
        if not self.applicability:
            raise ValidationError({'applicability': 'REQUIRED'})

    def _get_score(self, **kwargs):
        """Puntaje de esta regla contra ``kwargs`` — fiel a ``_get_score``
        (odoo19c: líneas 446-455). ``self.company_id`` es el atributo FK
        crudo de Django (no dispara query), igual semántica que el ``id``
        booleano de Odoo."""
        score = 0.5 if self.company_id and kwargs.get('company_id') else 0
        if not kwargs.get('business_domain'):
            return score
        return score + 1 if kwargs.get('business_domain') == self.business_domain else -1
