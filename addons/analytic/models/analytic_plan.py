"""``account.analytic.plan`` / ``account.analytic.applicability`` (Odoo
``analytic``).

Adaptación fiel de Odoo analytic/models/analytic_plan.py (odoo-tools@622ddc2a,
odoo19c:, LGPL-3), por etapas. Inventario y etapas:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
analytic-plan-basemodel.md``.

Etapa A (portada): ``BaseModel`` con la cabecera de la fuente
(``_parent_store``, ``_rec_name = 'complete_name'``, ``_order``), ``name``,
``description``, ``parent_id``/``children_ids``/``parent_path``,
``complete_name`` almacenado y recursivo, ``root_id`` con búsqueda,
``children_count``, ``account_count``, ``all_account_count``, ``color``,
``sequence`` y ``default_applicability``.

Pendiente, con su etapa en el diseño — **el sistema de columna dinámica por
plan** (etapa B: ``_column_name``, ``_strict_column_name``,
``_sync_plan_column``, ``_sync_all_plan_column``, ``_find_plan_column``,
``_find_related_field``, ``_auto_init``, los inversos de ``name`` y
``parent_id``), ``account.analytic.applicability`` sobre ``BaseModel``
(etapa C) y los métodos por verificar uno a uno (etapa D: ``_hierarchy_name``,
``unlink``, ``get_relevant_plans``, ``_get_all_plans``/``__get_all_plans``,
``_is_subplan_field_used``, ``create``, ``write``, ``_onchange_parent_id``):

    En la referencia, cada plan raíz agrega una **columna nueva** a
    ``account.analytic.line`` (``x_planN_id``) vía ``ir.model.fields`` +
    DDL en caliente — un mecanismo de meta-programación de esquema que Django
    no tiene como característica del ORM. Construirlo es la etapa B.

    **Corrección 2026-08-06 — el DDL en caliente NO es la barrera.** Una
    redacción previa decía *"las migraciones son estáticas, generadas por
    ``makemigrations``, no runtime"*, dando a entender que Django no puede
    alterar el esquema en ejecución. Es falso y se midió:
    ``connection.schema_editor().add_field()`` creó ``x_plan3_id_id`` con su
    FK real contra MariaDB, y ``remove_field()`` la eliminó.
    ``ir.model.fields``
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
    plan" están sus cuentas más que a través de ``account.plan_id``.

    ``action_view_analytical_accounts`` / ``action_view_children_plans``
    devuelven acciones de ventana del cliente web; se verifican en la etapa D
    junto con ``_onchange_parent_id``.

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

- **La columna deja de ser ``varchar``**: es ``jsonb`` con ``{empresa:
  valor}``,
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

import api
import fields
import models

from addons.base.models import _reject_hierarchy_cycle
from orm.models import _parent_store_update

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


class AccountAnalyticPlan(models.BaseModel, models.RecordLoaderMixin):
    """``account.analytic.plan`` — árbol de planes analíticos (sin columna
    dinámica; ver docstring del módulo)."""

    #: ≙ la cabecera de ``odoo19c: addons/analytic/models/
    #: analytic_plan.py:14-18``, verbatim. ``Meta.ordering`` es su forma en
    #: Django; los dos conviven.
    _name = 'account.analytic.plan'
    _description = 'Analytic Plans'
    _parent_store = True
    _rec_name = 'complete_name'
    _order = 'sequence asc, id'

    name = fields.Char(
        max_length=255,
        verbose_name='Nombre',
        help_text='Nombre del plan (Odoo name, requerido, traducible).',
    )
    description = fields.Text(
        blank=True,
        default='',
        verbose_name='Descripción',
    )
    #: ≙ ``parent_id`` (``:29-36``) con su columna explícita; el
    #: ``related_name`` es ``children_ids`` (``:43-47``).
    parent_id = fields.Many2one(
        'self',
        db_column='parent_id',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children_ids',
        verbose_name='Plan padre',
        help_text='Odoo parent_id (ondelete=cascade).',
    )
    parent_path = fields.Char(
        max_length=255,
        blank=True,
        default='',
        db_index=True,
    )
    #: ≙ ``complete_name`` (``:52-57``): almacenado y recursivo.
    complete_name = fields.Char(
        'Complete Name', compute='_compute_complete_name', recursive=True,
        store=True, max_length=1024, blank=True, null=True)
    #: ≙ ``root_id`` (``:38-42``): calculado, sin columna, con búsqueda.
    root_id = fields.Many2one(
        'self', store=False, compute='_compute_root_id',
        search='_search_root_id', on_delete=models.SET_NULL,
        related_name='+')
    children_count = fields.Integer(
        'Children Plans Count', compute='_compute_children_count',
        store=False)
    account_count = fields.Integer(
        'Analytic Accounts Count', compute='_compute_analytic_account_count',
        store=False)
    all_account_count = fields.Integer(
        'All Analytic Accounts Count',
        compute='_compute_all_analytic_account_count', store=False)
    color = fields.Integer(default=_default_color, verbose_name='Color')
    sequence = fields.Integer(default=10, verbose_name='Secuencia')
    default_applicability = fields.Selection(
        company_dependent=True,
        choices=APPLICABILITY_CHOICES,
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
        return self.complete_name or self.name or ''

    def clean(self):
        super().clean()
        _reject_hierarchy_cycle(self, 'parent_id', 'ANALYTIC_PLAN_CYCLE')

    def save(self, *args, **kwargs):
        """Mantiene la ruta materializada en el camino de Django.

        ``objects.create`` y ``save()`` no pasan por ``create``/``write`` del
        ORM, que son quienes mantienen el árbol de un ``BaseModel`` con
        ``_parent_store``. Mismo patrón que ``product.category``: una fila que
        cambia de padre delega en :func:`orm.models._parent_store_update`.
        """
        stored = (type(self)._base_manager.filter(pk=self.pk)
                  .values_list('parent_id', 'parent_path').first()
                  if self.pk is not None else None)
        super().save(*args, **kwargs)
        if stored and stored[1] and stored[0] != self.parent_id_id:
            _parent_store_update(self)
        else:
            path = (f'{self.parent_id.parent_path}{self.pk}/'
                    if self.parent_id else f'{self.pk}/')
            if path != self.parent_path:
                self.parent_path = path
                super().save(update_fields=['parent_path'])

    @api.depends('parent_id', 'parent_path')
    def _compute_root_id(self):
        """≙ ``_compute_root_id`` (``:129-132``)."""
        for plan in self.sudo():
            plan.root_id = (int(plan.parent_path[:-1].split('/')[0])
                            if plan.parent_path else plan)

    def _search_root_id(self, operator, value):
        """≙ ``_search_root_id`` (``:134-137``)."""
        if operator != '=':
            return NotImplemented
        return [('parent_path', '=like', f'{value}/%')]

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        """≙ ``_compute_complete_name`` (``:139-145``)."""
        for plan in self:
            if plan.parent_id:
                plan.complete_name = '%s / %s' % (
                    plan.parent_id.complete_name, plan.name)
            else:
                plan.complete_name = plan.name

    @api.depends('account_ids')
    def _compute_analytic_account_count(self):
        """≙ ``_compute_analytic_account_count`` (``:147-150``)."""
        for plan in self:
            plan.account_count = len(plan.account_ids)

    @api.depends('account_ids', 'children_ids')
    def _compute_all_analytic_account_count(self):
        """≙ ``_compute_all_analytic_account_count`` (``:152-178``)."""
        if not self.ids:
            self.all_account_count = 0
            return
        self.env.cr.execute("""
            SELECT parent.id,
                   array_agg(child.id) as children_ids
              FROM account_analytic_plan parent
              JOIN account_analytic_plan child
                ON child.parent_path LIKE parent.parent_path || '%%'
             WHERE parent.id IN %s
          GROUP BY parent.id
        """, [tuple(self.ids)])
        all_children_ids = dict(self.env.cr.fetchall())

        plans_count = dict(
            self.env['account.analytic.account']._read_group(
                domain=[('plan_id', 'child_of', self.ids)],
                aggregates=['id:count'],
                groupby=['plan_id'],
            )
        )
        plans_count = {k.id: v for k, v in plans_count.items()}
        for plan in self:
            plan.all_account_count = sum(
                plans_count.get(child_id, 0)
                for child_id in all_children_ids.get(plan.id, []))

    @api.depends('children_ids')
    def _compute_children_count(self):
        """≙ ``_compute_children_count`` (``:180-182``)."""
        for plan in self:
            plan.children_count = len(plan.children_ids)


class AccountAnalyticApplicability(models.RecordLoaderMixin, models.Model):
    """``account.analytic.applicability`` — regla de aplicabilidad por plan
    raíz + dominio de negocio + compañía. Portado completo: es Python puro,
    sin dependencia del sistema de columna dinámica."""

    analytic_plan = fields.Many2one(
        'analytic.AccountAnalyticPlan',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='applicability_ids',
        verbose_name='Plan analítico',
    )
    business_domain = fields.Selection(
        max_length=32,
        required=True,
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
        max_length=16,
        choices=APPLICABILITY_CHOICES,
        required=True,
        verbose_name='Aplicabilidad',
    )
    company = fields.Many2one(
        'base.ResCompany',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='analytic_applicabilities',
        verbose_name='Empresa',
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
        return (
            score + 1
            if kwargs.get('business_domain') == self.business_domain
            else -1
        )
