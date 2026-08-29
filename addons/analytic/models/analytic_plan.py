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
    no tiene como característica del ORM. Reimplementarlo exigiría un
    generador de migraciones a medida, fuera del alcance de este corte.

    **Corrección 2026-08-06 — el DDL en caliente NO es la barrera.** Una
    redacción previa decía *"las migraciones son estáticas, generadas por
    ``makemigrations``, no runtime"*, dando a entender que Django no puede
    alterar el esquema en ejecución. Es falso y se midió:
    ``connection.schema_editor().add_field()`` creó ``x_plan3_id_id`` con su
    FK real contra MariaDB, y ``remove_field()`` la eliminó. ``ir.model.fields``
    también está portado (``base/models/ir_model.py:377``).

    Lo que sí falta es el **re-registro de campos en el arranque** —que la
    columna nueva exista no basta: el modelo Python tiene que conocerla en el
    proceso siguiente (``contribute_to_class``)— y, sobre todo, una **decisión
    de producto**: el árbol ya optó por no construir un metaregistro paralelo
    al de Django (``ir_model.py:111-117``). Es un gap de alcance con una
    decisión pendiente del ejecutor, no una imposibilidad. Ver
    ``docs: …/analisis-recortes-declarados-vs-capacidad-del-stack.rst``
    (recorte 1).

    **Simplificación adoptada**: ``account.analytic.line`` usa una FK única
    ``account`` (ver ``analytic_line.py``) en vez de una columna por plan
    raíz. Un ``AccountAnalyticAccount`` sigue perteneciendo a un
    ``AccountAnalyticPlan`` (jerárquico), pero la línea no distingue "en qué
    plan" están sus cuentas más que a través de ``account.plan``.

    También quedan fuera ``action_view_analytical_accounts`` /
    ``action_view_children_plans`` (acciones de ventana del cliente web de
    Odoo, sin análogo en esta API) y ``_onchange_parent_id`` (onchange de
    formulario, sin análogo en DRF).

``company_dependent`` en ``default_applicability`` — construido (tarea #129)
=============================================================================

Hasta esta tarea el campo era un ``Selection`` escalar y este docstring decía
*"Django no tiene valor por defecto distinto por compañía activa a nivel de
campo"*. Eso describía el punto de partida y lo presentaba como cierre —
exactamente lo que ``porte-completo-no-parcial.md`` prohíbe: *"la respuesta
«este ORM no tiene ese constructor» no cierra nada"*.

El mecanismo se construyó: ``orm/fields_company_dependent.py`` (tarea #111,
la columna ``jsonb`` y la indirección de lectura) y los diez despachadores
(tarea #129, entre ellos ``Selection``). El campo se declara ahora con la
firma de la fuente (``odoo19c: analytic/models/analytic_plan.py:77-86``), sin
``default=`` — la fuente tampoco lo tiene: su valor inicial lo pone el
archivo de datos (``analytic/data/analytic_data.xml:16`` →
``<field name="default_applicability">optional</field>``), y para una empresa
sin valor propio responde ``ir.default``.

Dos consecuencias medibles del cambio, y las dos son de la fuente:

- **La columna deja de ser ``varchar``**: es ``jsonb`` con ``{empresa: valor}``,
  así que ``choices`` ya no la restringe. La enumeración sigue siendo el
  contrato del valor (``APPLICABILITY_CHOICES``, compartida con
  ``AccountAnalyticApplicability.applicability``, que **sí** sigue escalar
  porque allá tampoco es company_dependent).
- **Leer sin empresa activa da el fallback**, no ``'optional'`` fijo. Antes el
  default de columna respondía siempre lo mismo; ahora responde lo que la
  empresa tenga, que es el punto del campo.
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
    """Color aleatorio 1-11 — ≙ ``_default_color`` (``odoo19c: :20-21``).

    **Divergencia de sitio, medida (#164).** La referencia lo declara dentro
    de ``account.analytic.plan``; aquí es función de módulo porque las dos
    rutas para dejarlo en la clase están cerradas, y se comprobó ejecutando,
    no suponiendo:

    - referenciarlo como ``AccountAnalyticPlan._default_color`` en el cuerpo
      de su propia clase → ``NameError``: el nombre aún no está ligado;
    - referenciarlo desnudo como ``@staticmethod`` sí resuelve en Python, pero
      el serializador de migraciones de Django rechaza el objeto:
      ``ValueError: Cannot serialize: <staticmethod(...)>``.

    El gate de porte lo reporta ``FUERA DE SITIO`` y hace bien en verlo; el
    veredicto es que el mecanismo diverge, con la medición que lo sostiene.
    """
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
        company_dependent=True, choices=APPLICABILITY_CHOICES,
        verbose_name='Aplicabilidad por defecto',
        help_text=(
            'Odoo default_applicability, company_dependent: cada empresa fija '
            'la suya. Sin valor propio responde ir.default.'
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
        """≙ ``children_count`` / ``_compute_children_count``
        (``:48``, ``:180-182``)."""
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
            'Odoo business_domain; único valor que declara la raíz '
            'analytic. Otros addons amplían el vocabulario con '
            'extend_model(selection_add=…) ≙ selection_add: account suma '
            'invoice y bill, sale suma sale_order.'
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
