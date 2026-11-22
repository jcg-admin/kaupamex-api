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
from exceptions import UserError

from addons.base.models import SystemParameter, _reject_hierarchy_cycle
from orm.environments import env
from orm.models import _parent_store_update
from orm.registry import clear_cache
from tools.cache import ormcache
from tools.misc import frozendict
from tools.sql import SQL
from tools.translate import _

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
        """≙ ``_compute_root_id`` (``:129-132``). La fuente asigna el id;
        el descriptor del ``Many2one`` recibe aquí el registro."""
        for plan in self.sudo():
            root_id = (int(plan.parent_path[:-1].split('/')[0])
                       if plan.parent_path else plan.id)
            plan.root_id = plan.browse(root_id)

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
        # ``env.cr.execute`` + ``fetchall`` de la fuente es
        # ``env.execute_query`` aquí (``orm/environments.py:1626``), y su
        # ``IN %s`` con tupla es ``= ANY(%s)`` con lista: psycopg 3 no
        # expande una tupla, como psycopg2 (mismo idioma que
        # ``orm/models.py:9342``).
        all_children_ids = dict(self.env.execute_query(SQL("""
            SELECT parent.id,
                   array_agg(child.id) as children_ids
              FROM account_analytic_plan parent
              JOIN account_analytic_plan child
                ON child.parent_path LIKE parent.parent_path || '%%'
             WHERE parent.id = ANY(%s)
          GROUP BY parent.id
        """, list(self.ids))))

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

    # ---- Etapa D-1 (``designs/analytic-plan-methods.md``) ----------------

    @ormcache()
    def __get_all_plans(self):
        """≙ ``__get_all_plans``
        (``odoo19c: addons/analytic/models/analytic_plan.py:104-110``)."""
        project_plan = self.browse(int(
            SystemParameter.get_param('analytic.project_plan', 0) or 0))
        if not project_plan:
            raise UserError(_(
                "A 'Project' plan needs to exist and its id needs to be set "
                "as `analytic.project_plan` in the system variables"))
        other_plans = self.sudo().search(
            [('parent_id', '=', False)]) - project_plan
        return project_plan.id, other_plans.ids

    def _get_all_plans(self):
        """≙ ``_get_all_plans`` (``:112-113``)."""
        return map(self.browse, self.__get_all_plans())

    def _strict_column_name(self):
        """≙ ``_strict_column_name`` (``:115-118``)."""
        self.ensure_one()
        project_plan, _other_plans = self._get_all_plans()
        return ('account_id' if self == project_plan
                else f"x_plan{self.id}_id")

    def _column_name(self):
        """≙ ``_column_name`` (``:120-121``)."""
        return self.root_id._strict_column_name()

    @api.onchange('parent_id')
    def _onchange_parent_id(self):
        """≙ ``_onchange_parent_id`` (``:184-188``)."""
        project_plan, __ = self._get_all_plans()
        if self._origin.id == project_plan.id:
            raise UserError(_(
                "You cannot add a parent to the base plan '%s'",
                project_plan.name))

    def action_view_analytical_accounts(self):
        """≙ ``action_view_analytical_accounts`` (``:190-199``)."""
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.analytic.account",
            "domain": [('plan_id', "child_of", self.id)],
            "context": {'default_plan_id': self.id},
            "name": _("Analytical Accounts"),
            'view_mode': 'list,form',
        }

    def action_view_children_plans(self):
        """≙ ``action_view_children_plans`` (``:201-211``)."""
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.analytic.plan",
            "domain": [('parent_id', '=', self.id)],
            "context": {'default_parent_id': self.id,
                        'default_color': self.color},
            "name": _("Analytical Plans"),
            'view_mode': 'list,form',
        }

    def _get_applicability(self, **kwargs):
        """≙ ``_get_applicability`` (``:246-265``): la aplicabilidad de la
        regla de mayor puntaje, o la del plan."""
        self.ensure_one()
        if 'applicability' in kwargs:
            return kwargs['applicability']
        score = 0
        applicability = self.default_applicability
        for applicability_rule in self.applicability_ids.filtered(
                lambda rule:
                not rule.company_id
                or not kwargs.get('company_id')
                or rule.company_id.id == kwargs.get('company_id')
        ):
            score_rule = applicability_rule._get_score(**kwargs)
            if score_rule > score:
                applicability = applicability_rule.applicability
                score = score_rule
        return applicability

    def _hierarchy_name(self):
        """≙ ``_hierarchy_name`` (``:277-282``)."""
        depth = self.parent_path.count('/') - 1
        fname = f"{self._column_name()}_{depth}"
        if fname.startswith('account_id'):
            fname = f'x_{fname}'
        return depth, fname

    @api.model
    def get_relevant_plans(self, **kwargs):
        """≙ ``get_relevant_plans``
        (``odoo19c: addons/analytic/models/analytic_plan.py:214-244``).

        *"Returns the list of plans that should be available. This list is
        computed based on the applicabilities of root plans."*
        """
        cache = self.env.cr.cache.setdefault('get_relevant_plans', {})
        key = frozendict(kwargs)
        if key in cache:
            return cache[key]
        record_account_ids = kwargs.get('existing_account_ids', [])
        project_plan, other_plans = self.env[
            'account.analytic.plan']._get_all_plans()
        root_plans = (project_plan + other_plans).filtered(lambda p: (
            p.all_account_count > 0
            and not p.parent_id
            and p._get_applicability(**kwargs) != 'unavailable'
        ))
        # Con cuentas ya elegidas (antes de que cambiaran las reglas, o desde
        # un modelo) sus planes se muestran aunque no estén disponibles, y
        # como opcionales: el porcentaje previo puede no ser 0.
        forced_plans = self.env['account.analytic.account'].browse(
            record_account_ids).exists().mapped('root_plan_id') - root_plans
        cache[key] = [
            {
                "id": plan.id,
                "name": plan.name,
                "color": plan.color,
                "applicability": (plan._get_applicability(**kwargs)
                                  if plan in root_plans else 'optional'),
                "all_account_count": plan.all_account_count,
                "column_name": plan._column_name(),
            }
            for plan in (root_plans + forced_plans).sorted('sequence')
        ]
        return cache[key]

    @api.model_create_multi
    @classmethod
    def create(cls, vals_list):
        """≙ ``create`` (``:372-375``): vacía la caché de
        ``get_relevant_plans``. Limpia además la de ``__get_all_plans``: en
        la fuente la limpia la recarga del registro que provoca crear la
        columna dinámica del plan (etapa B); sin esa columna el efecto se
        pide aquí (``designs/analytic-plan-methods.md``)."""
        env().cr.cache.pop('get_relevant_plans', None)
        plans = super().create(vals_list)
        clear_cache()
        return plans

    def write(self, vals):
        """≙ ``write`` (``:377-379``): vacía la caché de
        ``get_relevant_plans`` si cambia ``default_applicability``. El paso
        de ``parent_id`` (``:380-401``) mueve cuentas entre columnas
        dinámicas y es la etapa B."""
        if 'default_applicability' in vals:
            self.env.cr.cache.pop('get_relevant_plans', None)
        return super().write(vals)

    def unlink(self):
        """≙ ``unlink`` (``:267-275``): vacía las dos cachés. Retirar la
        columna dinámica y los campos de agrupación es la etapa B."""
        res = super().unlink()
        clear_cache()
        self.env.cr.cache.pop('get_relevant_plans', None)
        return res


def _default_company_id():
    """≙ ``default=lambda self: self.env.company``
    (``odoo19c: addons/analytic/models/analytic_plan.py:427-431``)."""
    company = env().company
    return company.pk if company is not None else None


class AccountAnalyticApplicability(
    models.BaseModel,
    models.CheckCompanyMixin,
    models.RecordLoaderMixin,
):
    """``account.analytic.applicability`` — regla de aplicabilidad por plan
    raíz + dominio de negocio + compañía, sobre ``BaseModel``
    (``designs/analytic-applicability-basemodel.md``)."""

    #: ≙ la cabecera de
    #: ``odoo19c: addons/analytic/models/analytic_plan.py:405-409``.
    _name = 'account.analytic.applicability'
    _description = "Analytic Plan's Applicabilities"
    _check_company_auto = True
    _check_company_domain = models.check_company_domain_parent_of

    analytic_plan_id = fields.Many2one(
        'analytic.AccountAnalyticPlan',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='analytic_plan_id',
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
    company_id = fields.Many2one(
        'base.ResCompany',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='company_id',
        default=_default_company_id,
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

    @api.model_create_multi
    @classmethod
    def create(cls, vals_list):
        """≙ ``create`` (``:433-436``): vacía la caché de
        ``get_relevant_plans``."""
        env().cr.cache.pop('get_relevant_plans', None)
        return super().create(vals_list)

    def write(self, vals):
        """≙ ``write`` (``:438-440``)."""
        self.env.cr.cache.pop('get_relevant_plans', None)
        return super().write(vals)

    def unlink(self):
        """≙ ``_unlink_clear_cache`` (``:442-444``): este stack no tiene
        ``@api.ondelete``, así que la limpieza cuelga de ``unlink``, como en
        ``addons/hr/models/hr_departure_reason.py``."""
        self.env.cr.cache.pop('get_relevant_plans', None)
        return super().unlink()

    def _get_score(self, **kwargs):
        """Puntaje de esta regla contra ``kwargs`` — fiel a ``_get_score``
        (odoo19c: líneas 446-455)."""
        self.ensure_one()
        score = 0.5 if self.company_id and kwargs.get('company_id') else 0
        if not kwargs.get('business_domain'):
            return score
        return (
            score + 1
            if kwargs.get('business_domain') == self.business_domain
            else -1
        )
