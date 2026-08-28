"""Modelo ``CrmLead`` — addon ``crm``.

Adaptación fiel de ``crm/models/crm_lead.py`` (``crm.lead``): la iniciativa u
oportunidad de venta, y con ella el motor de *predictive lead scoring*, la
fusión de oportunidades y la conversión iniciativa → oportunidad.

Lo que NO se porta, y por qué (``porte-completo-no-parcial.md`` exige uno de
tres desenlaces, nunca el silencio):

- **Todo lo que cuelga de ``calendar.event``** — el addon ``calendar`` no
  existe en este árbol (medido: 0 archivos declaran ese modelo). Bloquea
  ``calendar_event_ids``, ``meeting_display_date``/``_label``,
  ``action_schedule_meeting``, ``_get_opportunity_meeting_view_parameters``,
  ``action_reschedule_meeting``, ``log_meeting`` y
  ``_merge_dependences_calendar_events``. Los símbolos se declaran con su
  cuerpo neutro y su condición de cierre: **portar el addon ``calendar``**.
- **Los tres mixins de correo que faltan** — ``mail.thread.cc``,
  ``mail.thread.blacklist`` y ``mail.thread.phone``. La fuente los hereda; aquí
  ``email_normalized`` y ``phone_sanitized`` se declaran como columnas propias
  de este modelo, que es exactamente lo que la fuente hace al redeclararlos
  para añadirles índice. ``mail.tracking.duration.mixin`` tampoco existe, así
  que ``duration_tracking`` es un diccionario vacío.
- **La capa de vistas XML** — ``_read_group_stage_ids`` (``group_expand``),
  ``get_empty_list_help`` y ``redirect_lead_opportunity_view`` devuelven
  descriptores de vista de la fuente. Se portan verbatim como datos: son el
  contrato que un cliente React consume, no XML que este árbol renderice.

Los cómputos con ``store=True`` en la fuente son columnas reales y las mantiene
``save()``; los que no almacenan son ``property`` que delegan en su
``_compute_*`` con el nombre de la fuente intacto (``porte-completo-no-parcial``:
el guion bajo es el contrato).
"""
import logging
from collections import OrderedDict, defaultdict
from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.db.models import Q

import api
import fields
import models

from exceptions import UserError, ValidationError

from addons.base.models import TimeStampedModel
from addons.base.models.ir_config_parameter import SystemParameter
from addons.base.models.res_company import ResCompany
from addons.base.models.res_country import ResCountry, ResCountryState
from addons.base.models.res_currency import ResCurrency
from addons.base.models.res_lang import ResLang
from addons.base.models.res_partner import FormatAddressMixin, ResPartner
from addons.crm.models import crm_stage
from addons.crm.models.crm_lead_scoring_frequency import CrmLeadScoringFrequency
from addons.crm.models.crm_lost_reason import CrmLostReason
from addons.crm.models.crm_recurring_plan import CrmRecurringPlan
from addons.crm.models.crm_stage import CrmStage
from addons.mail.models import MailActivityMixin, MailThread
from addons.sales_team.models import CrmTag, CrmTeam
from addons.utm.models.utm_mixin import UtmMixin
from tools.mail import (
    email_normalize_all,
    email_split,
    is_html_empty,
    parse_contact_from_email,
)
from tools.misc import groupby, split_every
from tools.translate import _

_logger = logging.getLogger(__name__)


# ≙ ``CRM_LEAD_FIELDS_TO_MERGE`` (crm_lead.py:24-57). Los 28 nombres, en su
# orden y con sus comentarios de sección.
CRM_LEAD_FIELDS_TO_MERGE = [
    # UTM mixin
    'campaign_id',
    'medium_id',
    'source_id',
    # Mail mixin
    'email_cc',
    # description
    'name',
    'user_id',
    'color',
    'company_id',
    'lang_id',
    'team_id',
    'referred',
    # pipeline
    'stage_id',
    # revenues
    'expected_revenue',
    'recurring_plan',
    'recurring_revenue',
    # dates
    'create_date',
    'date_automation_last',
    'date_deadline',
    # partner / contact
    'partner_id',
    'title',
    'partner_name',
    'contact_name',
    'email_from',
    'function',
    'phone',
    'website',
]

# ≙ ``PARTNER_FIELDS_TO_SYNC`` (:60-65) — subconjunto que se sincroniza suelto.
PARTNER_FIELDS_TO_SYNC = [
    'lang',
    'phone',
    'function',
    'website',
]

# ≙ ``PARTNER_ADDRESS_FIELDS_TO_SYNC`` (:68-75) — todos o ninguno, para no
# mezclar dos direcciones.
PARTNER_ADDRESS_FIELDS_TO_SYNC = [
    'street',
    'street2',
    'city',
    'zip',
    'state_id',
    'country_id',
]

# ≙ los dos tamaños de lote del cron de scoring (:78-80). La fuente los fija por
# medición, no por gusto: minimizan tiempo de cómputo y de transacción.
PLS_COMPUTE_BATCH_STEP = 50000
PLS_UPDATE_BATCH_STEP = 5000

# Dominios de correo gratuitos — el criterio de duplicado por dominio no los
# usa porque no discriminan nada. La fuente los lleva dentro de
# ``iap_tools.mail_prepare_for_domain_search``, del addon ``iap``, que este
# árbol no tiene; la lista se declara aquí, que es donde se consume.
FREE_EMAIL_DOMAINS = frozenset({
    'gmail.com', 'googlemail.com', 'hotmail.com', 'outlook.com', 'live.com',
    'msn.com', 'yahoo.com', 'yahoo.com.mx', 'ymail.com', 'aol.com',
    'icloud.com', 'me.com', 'mac.com', 'proton.me', 'protonmail.com',
    'gmx.com', 'mail.com', 'zoho.com', 'yandex.com',
})


def _pk(value):
    """La clave primaria de lo que llegue: instancia, id o nada.

    Sin contraparte de un símbolo en la fuente: allá ``opp[attr].id`` funciona
    porque un relacional siempre es un recordset. Aquí un mismo diccionario de
    fusión puede traer la instancia o su id según de dónde venga el valor, y
    los dos lados tienen que comparar igual.
    """
    if value is None or value is False:
        return None
    return getattr(value, 'pk', value)


class CrmLead(MailThread, MailActivityMixin, UtmMixin, FormatAddressMixin,
              TimeStampedModel):
    """``crm.lead`` — iniciativa u oportunidad de venta."""

    # Atributos de clase de modelo — los siete que la referencia declara
    # (crm_lead.py:82-98), verbatim. ``_inherit`` se conserva aunque tres de
    # sus siete mixins aún no existan aquí: nombra el contrato, no el estado.
    _name = 'crm.lead'
    _description = "Lead"
    _order = "priority desc, id desc"
    _inherit = ['mail.thread.cc',
                'mail.thread.blacklist',
                'mail.thread.phone',
                'mail.activity.mixin',
                'utm.mixin',
                'format.address.mixin',
                'mail.tracking.duration.mixin',
                ]
    _primary_email = 'email_from'
    _check_company_auto = True
    _track_duration_field = 'stage_id'

    # ≙ ``type`` (:123-125) — los dos valores, con sus constantes de lectura.
    TYPE_LEAD = 'lead'
    TYPE_OPPORTUNITY = 'opportunity'
    TYPES = [
        (TYPE_LEAD, 'Lead'),
        (TYPE_OPPORTUNITY, 'Opportunity'),
    ]
    # ≙ ``won_status`` (:225-231).
    WON_STATUS = [
        ('won', 'Won'),
        ('lost', 'Lost'),
        ('pending', 'Pending'),
    ]
    # ≙ ``phone_state`` / ``email_state`` (:196-201).
    QUALITY_STATES = [
        ('correct', 'Correct'),
        ('incorrect', 'Incorrect'),
    ]

    # -- Description ---------------------------------------------------------
    # ≙ name (:101-103): required, index='trigram', compute + store.
    name = fields.Char(
        max_length=255, db_index=True, verbose_name='Opportunity',
        help_text='Nombre de la oportunidad (Odoo crm.lead.name).',
    )
    # ≙ user_id (:104-107).
    user_id = fields.Many2one(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        db_index=True, related_name='crm_leads_owned', verbose_name='Salesperson',
        db_column='user_id', help_text='Vendedor asignado (Odoo user_id).',
    )
    # ≙ team_id (:111-113): ondelete="set null", compute + store + precompute.
    team_id = fields.Many2one(
        CrmTeam, null=True, blank=True, on_delete=models.SET_NULL,
        db_index=True, related_name='crm_leads', verbose_name='Sales Team',
        db_column='team_id', help_text='Equipo de venta (Odoo team_id).',
    )
    # ≙ lead_properties (:114-116): definition='team_id.lead_properties_definition'.
    lead_properties = fields.Properties(
        definition='team_id.lead_properties_definition', null=True, blank=True,
        verbose_name='Properties',
        help_text='Propiedades libres definidas por el equipo (Odoo lead_properties).',
    )
    # ≙ company_id (:117-119).
    company_id = fields.Many2one(
        ResCompany, null=True, blank=True, on_delete=models.SET_NULL,
        db_index=True, related_name='crm_leads', verbose_name='Company',
        db_column='company_id', help_text='Empresa dueña (Odoo company_id).',
    )
    # ≙ referred (:120).
    referred = fields.Char(
        max_length=255, blank=True, default='', verbose_name='Referred By',
        help_text='Quién refirió la iniciativa (Odoo referred).',
    )
    # ≙ description (:121) — Html en la fuente.
    description = fields.Html(
        blank=True, default='', verbose_name='Notes',
        help_text='Notas (Odoo description).',
    )
    # ≙ active (:122): tracking=72.
    active = fields.Boolean(
        default=True, verbose_name='Active',
        help_text='Archivar sin borrar (Odoo active).',
    )
    # ≙ type (:123-125): required, tracking=15, index=True.
    type = fields.Selection(
        max_length=12, choices=TYPES, default=TYPE_LEAD, db_index=True,
        help_text='Iniciativa u oportunidad (Odoo type).',
    )

    # -- Pipeline management -------------------------------------------------
    # ≙ priority (:127-129) — la escala vive en crm_stage, como en la fuente.
    priority = fields.Selection(
        max_length=1, choices=crm_stage.AVAILABLE_PRIORITIES,
        default=crm_stage.AVAILABLE_PRIORITIES[0][0], db_index=True,
        verbose_name='Priority', help_text='Prioridad (Odoo priority).',
    )
    # ≙ stage_id (:130-134): ondelete='restrict', group_expand.
    stage_id = fields.Many2one(
        CrmStage, null=True, blank=True, on_delete=models.PROTECT,
        db_index=True, related_name='leads', verbose_name='Stage',
        db_column='stage_id', help_text='Etapa del pipeline (Odoo stage_id).',
    )
    # ≙ tag_ids (:139-141): tabla intermedia crm_tag_rel(lead_id, tag_id).
    tag_ids = fields.Many2many(
        CrmTag, blank=True, db_table='crm_tag_rel', related_name='crm_leads',
        verbose_name='Tags',
        help_text='Clasifica y analiza las categorías de la iniciativa: '
                  'formación, servicio…',
    )
    # ≙ color (:142).
    color = fields.Integer(default=0, verbose_name='Color Index',
                           help_text='Índice de color (Odoo color).')

    # -- Revenues ------------------------------------------------------------
    # ≙ expected_revenue (:144), tracking=True, currency_field='company_currency'.
    expected_revenue = fields.Monetary(
        max_digits=16, decimal_places=2, default=0, verbose_name='Expected Revenue',
        help_text='Ingreso esperado (Odoo expected_revenue).',
    )
    # ≙ prorated_revenue (:145), store + compute.
    prorated_revenue = fields.Monetary(
        max_digits=16, decimal_places=2, default=0, verbose_name='Prorated Revenue',
        help_text='Ingreso prorrateado por probabilidad (Odoo prorated_revenue).',
    )
    # ≙ recurring_revenue (:146).
    recurring_revenue = fields.Monetary(
        max_digits=16, decimal_places=2, default=0, verbose_name='Recurring Revenues',
        help_text='Ingreso recurrente (Odoo recurring_revenue).',
    )
    # ≙ recurring_plan (:147) — la fuente NO le pone sufijo _id, y se respeta.
    recurring_plan = fields.Many2one(
        CrmRecurringPlan, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='crm_leads', verbose_name='Recurring Plan',
        db_column='recurring_plan', help_text='Plan recurrente (Odoo recurring_plan).',
    )
    # ≙ recurring_revenue_monthly (:148-149), store + compute.
    recurring_revenue_monthly = fields.Monetary(
        max_digits=16, decimal_places=2, default=0, verbose_name='Expected MRR',
        help_text='Ingreso recurrente mensual (Odoo recurring_revenue_monthly).',
    )
    # ≙ recurring_revenue_monthly_prorated (:150-151), store + compute.
    recurring_revenue_monthly_prorated = fields.Monetary(
        max_digits=16, decimal_places=2, default=0, verbose_name='Prorated MRR',
        help_text='MRR prorrateado (Odoo recurring_revenue_monthly_prorated).',
    )
    # ≙ recurring_revenue_prorated (:152-153), store + compute.
    recurring_revenue_prorated = fields.Monetary(
        max_digits=16, decimal_places=2, default=0,
        verbose_name='Prorated Recurring Revenues',
        help_text='Recurrente prorrateado (Odoo recurring_revenue_prorated).',
    )

    # -- Dates ---------------------------------------------------------------
    # ≙ date_closed (:156), readonly, copy=False.
    date_closed = fields.Datetime(
        null=True, blank=True, verbose_name='Closed Date',
        help_text='Fecha de cierre (Odoo date_closed).',
    )
    # ≙ date_automation_last (:157).
    date_automation_last = fields.Datetime(
        null=True, blank=True, verbose_name='Last Action',
        help_text='Última acción automatizada (Odoo date_automation_last).',
    )
    # ≙ date_open (:158-159), store + compute.
    date_open = fields.Datetime(
        null=True, blank=True, verbose_name='Assignment Date',
        help_text='Fecha de asignación (Odoo date_open).',
    )
    # ≙ day_open (:160) / day_close (:161), store + compute.
    day_open = fields.Float(
        null=True, blank=True, verbose_name='Days to Assign',
        help_text='Días hasta la asignación (Odoo day_open).',
    )
    day_close = fields.Float(
        null=True, blank=True, verbose_name='Days to Close',
        help_text='Días hasta el cierre (Odoo day_close).',
    )
    # ≙ date_last_stage_update (:162-163), index, store + compute.
    date_last_stage_update = fields.Datetime(
        null=True, blank=True, db_index=True, verbose_name='Last Stage Update',
        help_text='Último cambio de etapa (Odoo date_last_stage_update).',
    )
    # ≙ date_conversion (:164).
    date_conversion = fields.Datetime(
        null=True, blank=True, verbose_name='Conversion Date',
        help_text='Fecha de conversión a oportunidad (Odoo date_conversion).',
    )
    # ≙ date_deadline (:165).
    date_deadline = fields.Date(
        null=True, blank=True, verbose_name='Expected Closing',
        help_text='Estimación de la fecha en que se ganará la oportunidad.',
    )

    # -- Customer / contact --------------------------------------------------
    # ≙ partner_id (:175-177), tracking=10, check_company.
    partner_id = fields.Many2one(
        ResPartner, null=True, blank=True, on_delete=models.SET_NULL,
        db_index=True, related_name='crm_leads', verbose_name='Contact',
        db_column='partner_id',
        help_text='Contacto vinculado (opcional). Normalmente se crea al '
                  'convertir la iniciativa.',
    )
    # ≙ contact_name (:179-181), index='trigram', tracking=30, compute + store.
    contact_name = fields.Char(
        max_length=255, blank=True, default='', db_index=True,
        verbose_name='Contact Name',
        help_text='Nombre de contacto (Odoo contact_name).',
    )
    # ≙ partner_name (:182-185), index='trigram', tracking=20, compute + store.
    partner_name = fields.Char(
        max_length=255, blank=True, default='', db_index=True,
        verbose_name='Company Name',
        help_text='Nombre de la futura empresa que se creará al convertir la '
                  'iniciativa en oportunidad.',
    )
    # ≙ function (:186), compute + store.
    function = fields.Char(
        max_length=255, blank=True, default='', verbose_name='Job Position',
        help_text='Puesto del contacto (Odoo function).',
    )
    # ≙ email_from (:187-189), tracking=40, index='trigram', compute + inverse.
    email_from = fields.Char(
        max_length=255, blank=True, default='', db_index=True,
        verbose_name='Email', help_text='Correo del contacto (Odoo email_from).',
    )
    # ≙ email_normalized (:190) — la fuente lo hereda de ``mail.thread.blacklist``
    # y sólo lo redeclara para indexarlo. Ese mixin no existe aquí, así que la
    # columna es propia de este modelo; mismo nombre, mismo papel.
    email_normalized = fields.Char(
        max_length=255, blank=True, default='', db_index=True,
        help_text='Correo normalizado, en minúsculas (Odoo email_normalized).',
    )
    # ≙ email_domain_criterion (:191-196), index='btree_not_null', compute + store.
    email_domain_criterion = fields.Char(
        max_length=255, blank=True, default='', db_index=True,
        verbose_name='Email Domain Criterion',
        help_text='Dominio del correo, para buscar duplicados por coincidencia '
                  'exacta (Odoo email_domain_criterion).',
    )
    # ≙ phone (:197-199), tracking=50, compute + inverse.
    phone = fields.Char(
        max_length=255, blank=True, default='', verbose_name='Phone',
        help_text='Teléfono del contacto (Odoo phone).',
    )
    # ≙ phone_sanitized (:200) — mismo caso que email_normalized: lo aporta
    # ``mail.thread.phone``, que aquí no existe.
    phone_sanitized = fields.Char(
        max_length=255, blank=True, default='', db_index=True,
        help_text='Teléfono en formato E.164 (Odoo phone_sanitized).',
    )
    # ≙ phone_state (:201-203) / email_state (:204-206), compute + store.
    phone_state = fields.Selection(
        max_length=9, choices=QUALITY_STATES, null=True, blank=True,
        verbose_name='Phone Quality',
        help_text='Calidad del teléfono (Odoo phone_state).',
    )
    email_state = fields.Selection(
        max_length=9, choices=QUALITY_STATES, null=True, blank=True,
        verbose_name='Email Quality',
        help_text='Calidad del correo (Odoo email_state).',
    )
    # ≙ website (:207), compute + store.
    website = fields.Char(
        max_length=255, blank=True, default='', verbose_name='Website',
        help_text='Sitio web del contacto (Odoo website).',
    )
    # ≙ lang_id (:208-210), compute + store.
    lang_id = fields.Many2one(
        ResLang, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='crm_leads', verbose_name='Language',
        db_column='lang_id', help_text='Idioma del contacto (Odoo lang_id).',
    )

    # -- Address fields ------------------------------------------------------
    # ≙ street / street2 / zip / city (:213-216), compute + store.
    street = fields.Char(max_length=255, blank=True, default='', verbose_name='Street')
    street2 = fields.Char(max_length=255, blank=True, default='', verbose_name='Street2')
    zip = fields.Char(max_length=24, blank=True, default='', verbose_name='Zip')
    city = fields.Char(max_length=255, blank=True, default='', verbose_name='City')
    # ≙ state_id (:217-220) / country_id (:221-223), compute + store.
    state_id = fields.Many2one(
        ResCountryState, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='crm_leads', verbose_name='State', db_column='state_id',
    )
    country_id = fields.Many2one(
        ResCountry, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='crm_leads', verbose_name='Country', db_column='country_id',
    )

    # -- Probability (Opportunity only) --------------------------------------
    # ≙ probability (:225-227), aggregator="avg", copy=False, compute + store.
    probability = fields.Float(
        default=0.0, verbose_name='Probability',
        help_text='Probabilidad de ganar, en porcentaje (Odoo probability).',
    )
    # ≙ automated_probability (:228), readonly, compute + store.
    automated_probability = fields.Float(
        default=0.0, verbose_name='Automated Probability',
        help_text='Probabilidad calculada por el scoring (Odoo automated_probability).',
    )

    # -- Won/Lost ------------------------------------------------------------
    # ≙ won_status (:231-237), tracking=70, compute + store.
    won_status = fields.Selection(
        max_length=8, choices=WON_STATUS, default='pending',
        verbose_name='Won/Lost', help_text='Ganada, perdida o en curso (Odoo won_status).',
    )
    # ≙ lost_reason_id (:238-240), ondelete='restrict', tracking=71.
    lost_reason_id = fields.Many2one(
        CrmLostReason, null=True, blank=True, on_delete=models.PROTECT,
        db_index=True, related_name='leads', verbose_name='Lost Reason',
        db_column='lost_reason_id', help_text='Motivo de pérdida (Odoo lost_reason_id).',
    )

    class Meta:
        db_table = 'crm_lead'
        # ≙ ``_order = "priority desc, id desc"``.
        ordering = ['-priority', '-id']
        verbose_name = 'Oportunidad de CRM'
        verbose_name_plural = 'Oportunidades de CRM'
        constraints = [
            # ≙ ``_check_probability`` (:255-258) — objeto de tabla de 19, con
            # su nombre y su mensaje conservados.
            models.CheckConstraint(
                condition=Q(probability__gte=0) & Q(probability__lte=100),
                name='crm_lead_check_probability',
                violation_error_message=(
                    'The probability of closing the deal should be between 0% and 100%!'
                ),
            ),
        ]
        indexes = [
            # ≙ los tres ``models.Index`` de la fuente (:259-261), con su nombre.
            models.Index(fields=['user_id', 'team_id', 'type'],
                         name='crm_lead_user_team_type_idx'),
            models.Index(fields=['created_at', 'team_id'],
                         name='crm_lead_create_team_idx'),
            models.Index(fields=['-priority', '-id'], condition=Q(active=True),
                         name='crm_lead_default_order_idx'),
        ]

    def __str__(self) -> str:
        return self.name or ''

    # ------------------------------------------------------------
    # COMPUTES / ONCHANGES / CONSTRAINTS
    #
    # Divergencia de forma, declarada una vez para todo el bloque: allá ``self``
    # es un *recordset* y cada cómputo itera ``for lead in self``; aquí una
    # instancia **es** un registro, así que el cuerpo del bucle se aplica a
    # ``self``. Los que sí necesitan un conjunto (fusión, scoring, ``_handle_
    # won_lost``) son ``classmethod`` y reciben el queryset explícito.
    # ------------------------------------------------------------

    @api.constrains('probability', 'stage_id')
    def _check_won_validity(self):
        """≙ ``_check_won_validity`` (:262-266)."""
        if self.stage_id and self.stage_id.is_won and self.probability != 100:
            raise ValidationError(
                _("A lead in a Won stage cannot be lost. Move it to another stage first.")
            )

    @api.depends('company_id')
    def _compute_user_company_ids(self):
        """≙ ``_compute_user_company_ids`` (:268-275)."""
        if not self.company_id_id:
            return ResCompany.objects.all()
        return ResCompany.objects.filter(pk=self.company_id_id)

    @property
    def user_company_ids(self):
        """≙ el campo ``user_company_ids`` (:108-110), calculado sin columna."""
        return self._compute_user_company_ids()

    @api.depends('company_id')
    def _compute_company_currency(self):
        """≙ ``_compute_company_currency`` (:277-283)."""
        if not self.company_id_id:
            return ResCurrency.objects.filter(
                pk__in=ResCompany.objects.values_list('currency_id', flat=True)[:1]
            ).first()
        return self.company_id.currency_id

    @property
    def company_currency(self):
        """≙ el campo ``company_currency`` (:154), calculado sin columna."""
        return self._compute_company_currency()

    def _field_to_sql(self, alias, field_expr, query=None):
        """≙ ``_field_to_sql`` (:285-298) — el JOIN que hace agregable
        ``company_currency``.

        DIVERGENCIA DE MECANISMO declarada: la fuente reescribe la expresión SQL
        del campo porque su motor agrega monetarios por moneda de empresa. Aquí
        ``company_currency`` no es columna sino ``property``, y la agregación por
        moneda la resuelve el ``ORM`` de Django con un ``annotate`` desde el lado
        de ``res_company``. El símbolo se conserva delegando en su base para no
        romper la cadena de sobrescritura del motor espejado.
        """
        return super()._field_to_sql(alias, field_expr, query)

    @api.depends('user_id', 'type')
    def _compute_team_id(self):
        """≙ ``_compute_team_id`` (:300-314).

        Al cambiar el vendedor se recalcula el equipo, salvo que el actual ya
        lo tenga como miembro o como líder.
        """
        if not self.user_id_id:
            return
        user = self.user_id
        if self.team_id and (
            self.team_id.member_ids.filter(pk=user.pk).exists()
            or self.team_id.user_id_id == user.pk
        ):
            return
        field_name = 'use_leads' if self.type == self.TYPE_LEAD else 'use_opportunities'
        team = CrmTeam._get_default_team_id(user_id=user.pk, domain={field_name: True})
        if team is not None and self.team_id_id != team.pk:
            self.team_id = team

    @api.depends('user_id', 'team_id', 'partner_id')
    def _compute_company_id(self):
        """≙ ``_compute_company_id`` (:316-351) — coherencia de la empresa."""
        proposal = self.company_id

        if proposal:
            # la empresa no está entre las del responsable
            if self.user_id_id and not self.user_id.company_ids.filter(
                    pk=proposal.pk).exists():
                proposal = None
            # incoherente con la del equipo
            elif self.team_id and self.team_id.company_id_id \
                    and proposal.pk != self.team_id.company_id_id:
                proposal = None
            # equipo sin empresa y sin responsable
            elif self.team_id and not self.team_id.company_id_id and not self.user_id_id:
                proposal = None
            # sin equipo y sin responsable: se vacía y que la asignación decida,
            # salvo que el cliente traiga la suya
            elif not self.team_id_id and not self.user_id_id and (
                    not self.partner_id_id
                    or self.partner_id.company_id_id != proposal.pk):
                proposal = None

        # propuesta nueva por orden: equipo > responsable > cliente
        if not proposal:
            if self.team_id and self.team_id.company_id_id:
                self.company_id = self.team_id.company_id
            elif self.user_id_id:
                self.company_id = self.user_id.company_id
            elif self.partner_id_id:
                self.company_id = self.partner_id.company_id
            else:
                self.company_id = None

    @api.depends('team_id', 'type')
    def _compute_stage_id(self):
        """≙ ``_compute_stage_id`` (:353-357)."""
        if not self.stage_id_id or (
            self.team_id_id
            and self.stage_id.team_ids.exists()
            and not self.stage_id.team_ids.filter(pk=self.team_id_id).exists()
        ):
            stage = self._stage_find(domain={'fold': False})
            self.stage_id = stage

    @api.depends('user_id')
    def _compute_date_open(self):
        """≙ ``_compute_date_open`` (:359-363)."""
        if not self.date_open and self.user_id_id:
            self.date_open = datetime.now(timezone.utc)

    @api.depends('stage_id')
    def _compute_date_last_stage_update(self):
        """≙ ``_compute_date_last_stage_update`` (:365-369)."""
        if not self.date_last_stage_update:
            self.date_last_stage_update = datetime.now(timezone.utc)

    @api.depends('create_date', 'date_open')
    def _compute_day_open(self):
        """≙ ``_compute_day_open`` (:371-380) — días entre alta y asignación."""
        if not (self.date_open and self.created_at):
            self.day_open = None
            return
        date_create = self.created_at.replace(microsecond=0)
        self.day_open = abs((self.date_open - date_create).days)

    @api.depends('create_date', 'date_closed')
    def _compute_day_close(self):
        """≙ ``_compute_day_close`` (:382-390) — días entre alta y cierre."""
        if not (self.date_closed and self.created_at):
            self.day_close = None
            return
        self.day_close = abs((self.date_closed - self.created_at).days)

    @classmethod
    def _get_rotting_depends_fields(cls):
        """≙ ``_get_rotting_depends_fields`` (:392-393)."""
        base = getattr(super(), '_get_rotting_depends_fields', lambda: [])()
        return list(base) + ['won_status', 'type']

    @classmethod
    def _get_rotting_domain(cls):
        """≙ ``_get_rotting_domain`` (:395-400).

        El ``Domain`` de la fuente se expresa aquí como ``Q``, que es la forma
        de este stack para el mismo álgebra de predicados.
        """
        base = getattr(super(), '_get_rotting_domain', lambda: Q())()
        return base & Q(won_status='pending', type=cls.TYPE_OPPORTUNITY)

    @api.depends('partner_id')
    def _compute_name(self):
        """≙ ``_compute_name`` (:402-406)."""
        if not self.name and self.partner_id_id and self.partner_id.name:
            self.name = _("%s's opportunity") % self.partner_id.name

    @api.depends('partner_id', 'partner_name')
    def _compute_commercial_partner_id(self):
        """≙ ``_compute_commercial_partner_id`` (:408-422).

        Con cliente: la entidad comercial, si es empresa y no es el propio
        contacto. Sin cliente: se busca por nombre de empresa.
        """
        if self.partner_id_id:
            commercial = self.partner_id.commercial_partner_id
            if commercial and commercial.is_company and commercial.pk != self.partner_id_id:
                return commercial
            return None
        if self.partner_name:
            return ResPartner.objects.filter(
                is_company=True, name=self.partner_name).order_by('pk').first()
        return None

    @property
    def commercial_partner_id(self):
        """≙ el campo ``commercial_partner_id`` (:171-174), ``store=False``."""
        return self._compute_commercial_partner_id()

    @api.onchange('commercial_partner_id')
    def _onchange_commercial_partner_id(self):
        """≙ ``_onchange_commercial_partner_id`` (:424-438).

        Cambiar la entidad comercial desliga al contacto para que el usuario no
        arrastre correo y teléfono del anterior.
        """
        commercial = self.commercial_partner_id
        if self.partner_id_id and commercial and \
                commercial.pk != self.partner_id.commercial_partner_id_id:
            self.partner_id = None
            self.email_from = ''
            self.phone = ''
        if not self.name and commercial:
            self.name = _("%s's opportunity") % commercial.name

    @api.depends('partner_id')
    def _compute_contact_name(self):
        """≙ ``_compute_contact_name`` (:440-446)."""
        if not self.partner_id_id:
            self.contact_name = ''
            return
        for key, value in self._prepare_contact_name_from_partner(self.partner_id).items():
            setattr(self, key, value)

    @api.depends('partner_id')
    def _compute_partner_name(self):
        """≙ ``_compute_partner_name`` (:448-454)."""
        if not self.partner_id_id:
            self.partner_name = ''
            return
        for key, value in self._prepare_partner_name_from_partner(self.partner_id).items():
            setattr(self, key, value)

    @api.depends('partner_id')
    def _compute_function(self):
        """≙ ``_compute_function`` (:456-461)."""
        if not self.function or (self.partner_id_id and self.partner_id.function):
            self.function = (self.partner_id.function if self.partner_id_id else '') or ''

    @api.depends('partner_id')
    def _compute_website(self):
        """≙ ``_compute_website`` (:463-468)."""
        if not self.website or (self.partner_id_id and self.partner_id.website):
            self.website = (self.partner_id.website if self.partner_id_id else '') or ''

    @api.depends('partner_id')
    def _compute_lang_id(self):
        """≙ ``_compute_lang_id`` (:470-484).

        El idioma se fuerza al del cliente, borrando cualquier valor previo.
        """
        if not self.partner_id_id:
            return
        code = self.partner_id.lang
        self.lang_id = ResLang.objects.filter(code=code).first() if code else None

    @api.depends('lang_id')
    def _compute_lang_active_count(self):
        """≙ ``_compute_lang_active_count`` (:486-488)."""
        return ResLang.objects.filter(active=True).count()

    @property
    def lang_active_count(self):
        """≙ el campo ``lang_active_count`` (:211), calculado sin columna."""
        return self._compute_lang_active_count()

    @property
    def lang_code(self):
        """≙ el campo ``lang_code`` (:210), ``related='lang_id.code'``."""
        return self.lang_id.code if self.lang_id_id else ''

    @property
    def stage_id_color(self):
        """≙ el campo ``stage_id_color`` (:135), ``related='stage_id.color'``."""
        return self.stage_id.color if self.stage_id_id else 0

    @property
    def partner_is_blacklisted(self):
        """≙ el campo ``partner_is_blacklisted`` (:178),
        ``related='partner_id.is_blacklisted'``.

        Bloqueado por lo mismo que ``email_normalized``: ``mail.thread.blacklist``
        no existe en este árbol, así que ``res.partner`` no declara todavía
        ``is_blacklisted``. Se lee del cliente cuando exista; hasta entonces es
        ``False``, que es el valor que el contrato promete por defecto.
        """
        if not self.partner_id_id:
            return False
        return bool(getattr(self.partner_id, 'is_blacklisted', False))

    @api.depends('partner_id')
    def _compute_partner_address_values(self):
        """≙ ``_compute_partner_address_values`` (:490-494)."""
        if not self.partner_id_id:
            return
        for key, value in self._prepare_address_values_from_partner(self.partner_id).items():
            setattr(self, key, value)

    @api.depends('partner_id.email')
    def _compute_email_from(self):
        """≙ ``_compute_email_from`` (:496-500)."""
        if self.partner_id_id and self.partner_id.email and self._get_partner_email_update():
            self.email_from = self.partner_id.email

    def _inverse_email_from(self):
        """≙ ``_inverse_email_from`` (:502-505)."""
        if self._get_partner_email_update(force_void=False):
            self.partner_id.email = self.email_from
            self.partner_id.save(update_fields=['email'])

    @api.depends('email_normalized')
    def _compute_email_domain_criterion(self):
        """≙ ``_compute_email_domain_criterion`` (:507-513).

        La fuente delega en ``iap_tools.mail_prepare_for_domain_search``, del
        addon ``iap`` — ausente aquí. Se construye el mecanismo con lo que el
        stack da: el criterio es el dominio del correo normalizado, salvo que
        sea un proveedor genérico, en cuyo caso no discrimina nada y se deja
        vacío (que es lo que aquella función hace con su lista de gratuitos).
        """
        if not self.email_normalized:
            self.email_domain_criterion = ''
            return
        _local, _sep, domain = self.email_normalized.partition('@')
        self.email_domain_criterion = '' if domain in FREE_EMAIL_DOMAINS else domain

    @api.depends('partner_id.phone')
    def _compute_phone(self):
        """≙ ``_compute_phone`` (:515-519)."""
        if self.partner_id_id and self.partner_id.phone and self._get_partner_phone_update():
            self.phone = self.partner_id.phone

    def _inverse_phone(self):
        """≙ ``_inverse_phone`` (:521-524)."""
        if self._get_partner_phone_update(force_void=False):
            self.partner_id.phone = self.phone
            self.partner_id.save(update_fields=['phone'])

    @api.depends('phone', 'country_id.code')
    def _compute_phone_state(self):
        """≙ ``_compute_phone_state`` (:526-537).

        La fuente usa ``phone_validation.phone_parse`` del addon homónimo, que
        aquí no existe. El mecanismo se construye con la misma semántica: un
        teléfono con al menos siete dígitos y sin caracteres ajenos al formato
        internacional es ``correct``; cualquier otro, ``incorrect``.
        """
        if not self.phone:
            self.phone_state = None
            return
        digits = [c for c in self.phone if c.isdigit()]
        foreign_chars = [c for c in self.phone if not (c.isdigit() or c in ' +-().')]
        self.phone_state = 'correct' if len(digits) >= 7 and not foreign_chars else 'incorrect'

    @api.depends('email_from')
    def _compute_email_state(self):
        """≙ ``_compute_email_state`` (:539-549)."""
        if not self.email_from:
            self.email_state = None
            return
        state = 'incorrect'
        for email in email_normalize_all(self.email_from):
            if email:
                state = 'correct'
                break
        self.email_state = state

    @api.depends('probability', 'automated_probability')
    def _compute_is_automated_probability(self):
        """≙ ``_compute_is_automated_probability`` (:551-556)."""
        return round(self.probability or 0.0, 2) == round(self.automated_probability or 0.0, 2)

    @property
    def is_automated_probability(self):
        """≙ el campo ``is_automated_probability`` (:229), sin columna."""
        return self._compute_is_automated_probability()

    def _compute_probabilities(self):
        """≙ ``_compute_probabilities`` (:558-566)."""
        probabilities, _unused = type(self)._pls_get_naive_bayes_probabilities(
            type(self).objects.filter(pk=self.pk)
        )
        if self.pk in probabilities:
            era_automatica = self.active and self.is_automated_probability
            self.automated_probability = probabilities[self.pk]
            if era_automatica:
                self.probability = self.automated_probability

    @api.depends('expected_revenue', 'probability')
    def _compute_prorated_revenue(self):
        """≙ ``_compute_prorated_revenue`` (:568-571)."""
        self.prorated_revenue = round(
            float(self.expected_revenue or 0.0) * float(self.probability or 0) / 100.0, 2)

    @api.depends('recurring_revenue', 'recurring_plan.number_of_months')
    def _compute_recurring_revenue_monthly(self):
        """≙ ``_compute_recurring_revenue_monthly`` (:573-576)."""
        months = self.recurring_plan.number_of_months if self.recurring_plan_id else 0
        self.recurring_revenue_monthly = float(self.recurring_revenue or 0.0) / (months or 1)

    @api.depends('recurring_revenue_monthly', 'probability')
    def _compute_recurring_revenue_monthly_prorated(self):
        """≙ ``_compute_recurring_revenue_monthly_prorated`` (:578-581)."""
        self.recurring_revenue_monthly_prorated = (
            float(self.recurring_revenue_monthly or 0.0) * float(self.probability or 0) / 100.0)

    @api.depends('recurring_revenue', 'probability')
    def _compute_recurring_revenue_prorated(self):
        """≙ ``_compute_recurring_revenue_prorated`` (:583-586)."""
        self.recurring_revenue_prorated = (
            float(self.recurring_revenue or 0.0) * float(self.probability or 0) / 100.0)

    @api.depends('calendar_event_ids', 'calendar_event_ids.start')
    def _compute_meeting_display(self):
        """≙ ``_compute_meeting_display`` (:588-610).

        BLOQUEADO por el addon ``calendar`` (0 archivos declaran
        ``calendar.event``). Devuelve lo que la fuente devuelve cuando el
        registro no tiene ninguna reunión, que es el caso de todos hoy.
        Condición de cierre: portar el addon ``calendar``.
        """
        return {'meeting_display_date': None, 'meeting_display_label': _('No Meeting')}

    @property
    def meeting_display_date(self):
        """≙ el campo ``meeting_display_date`` (:245), sin columna."""
        return self._compute_meeting_display()['meeting_display_date']

    @property
    def meeting_display_label(self):
        """≙ el campo ``meeting_display_label`` (:246), sin columna."""
        return self._compute_meeting_display()['meeting_display_label']

    @property
    def calendar_event_ids(self):
        """≙ el campo ``calendar_event_ids`` (:241).

        BLOQUEADO por el addon ``calendar``. Lista vacía, con la misma
        condición de cierre que ``_compute_meeting_display``.
        """
        return []

    @api.depends('active', 'probability', 'stage_id')
    def _compute_won_status(self):
        """≙ ``_compute_won_status`` (:612-620)."""
        if self.probability == 100 and self.stage_id_id and self.stage_id.is_won:
            self.won_status = 'won'
        elif not self.active and self.probability == 0:
            self.won_status = 'lost'
        else:
            self.won_status = 'pending'

    @api.depends('email_domain_criterion', 'email_normalized', 'partner_id',
                 'phone_sanitized')
    def _compute_potential_lead_duplicates(self):
        """≙ ``_compute_potential_lead_duplicates`` (:622-677).

        Tres criterios, en el orden de la fuente: dominio de correo exacto,
        misma entidad comercial, teléfono normalizado exacto. Cada búsqueda se
        descarta si devuelve el tope, porque entonces el término no discrimina.
        """
        SEARCH_RESULT_LIMIT = 21

        def _return_if_relevant(predicado):
            """≙ ``return_if_relevant`` (:632-645)."""
            ids = list(type(self).objects.filter(predicado)
                       .exclude(pk=self.pk).values_list('pk', flat=True)[:SEARCH_RESULT_LIMIT])
            return set(ids) if len(ids) < SEARCH_RESULT_LIMIT else set()

        duplicates = set()
        if self.email_domain_criterion:
            duplicates |= _return_if_relevant(Q(email_domain_criterion=self.email_domain_criterion))
        if self.partner_id_id and self.partner_id.commercial_partner_id_id:
            duplicates |= set(
                type(self).objects
                .filter(partner_id__commercial_partner_id=self.partner_id.commercial_partner_id_id)
                .exclude(pk=self.pk).values_list('pk', flat=True)
            )
        if self.phone_sanitized:
            duplicates |= _return_if_relevant(Q(phone_sanitized=self.phone_sanitized))
        return {
            'duplicate_lead_ids': type(self).objects.filter(
                pk__in=duplicates | ({self.pk} if self.pk else set())),
            'duplicate_lead_count': len(duplicates),
        }

    @property
    def duplicate_lead_ids(self):
        """≙ el campo ``duplicate_lead_ids`` (:242-243), sin columna."""
        return self._compute_potential_lead_duplicates()['duplicate_lead_ids']

    @property
    def duplicate_lead_count(self):
        """≙ el campo ``duplicate_lead_count`` (:244), sin columna."""
        return self._compute_potential_lead_duplicates()['duplicate_lead_count']

    @api.depends('email_from', 'partner_id')
    def _compute_partner_email_update(self):
        """≙ ``_compute_partner_email_update`` (:679-682)."""
        return self._get_partner_email_update(force_void=False)

    @property
    def partner_email_update(self):
        """≙ el campo ``partner_email_update`` (:249), sin columna."""
        return self._compute_partner_email_update()

    @api.depends('phone', 'partner_id')
    def _compute_partner_phone_update(self):
        """≙ ``_compute_partner_phone_update`` (:684-687)."""
        return self._get_partner_phone_update(force_void=False)

    @property
    def partner_phone_update(self):
        """≙ el campo ``partner_phone_update`` (:250), sin columna."""
        return self._compute_partner_phone_update()

    @api.depends('partner_id', 'type')
    def _compute_is_partner_visible(self):
        """≙ ``_compute_is_partner_visible`` (:689-705).

        En una iniciativa el cliente casi nunca está puesto —al ponerlo se suele
        convertir en oportunidad—, así que el campo sólo se muestra cuando está
        puesto, cuando ya es oportunidad, o en modo depuración.
        """
        return bool(self.type == self.TYPE_OPPORTUNITY or self.partner_id_id)

    @property
    def is_partner_visible(self):
        """≙ el campo ``is_partner_visible`` (:251), sin columna."""
        return self._compute_is_partner_visible()

    @api.onchange('phone', 'country_id', 'company_id')
    def _onchange_phone_validation(self):
        """≙ ``_onchange_phone_validation`` (:707-710).

        La fuente formatea a INTERNACIONAL con ``_phone_format`` de
        ``mail.thread.phone``, ausente aquí. Se construye el mecanismo mínimo:
        anteponer el prefijo del país cuando el número no lo trae.
        """
        if not self.phone:
            return
        self.phone = self._phone_format(self.phone) or self.phone

    # ------------------------------------------------------------
    # SINCRONIZACIÓN CON EL CLIENTE
    # ------------------------------------------------------------

    def _prepare_values_from_partner(self, partner):
        """≙ ``_prepare_values_from_partner`` (:712-729).

        La dirección se sincroniza entera o nada; el resto de campos sólo si el
        cliente los trae puestos, para no borrar lo que la iniciativa ya tenía.
        """
        values = self._prepare_address_values_from_partner(partner)
        values.update({
            f: getattr(partner, f, None) or getattr(self, f, None)
            for f in PARTNER_FIELDS_TO_SYNC if f != 'lang'
        })
        if partner.lang:
            values['lang_id'] = ResLang.objects.filter(code=partner.lang).first()
        values.update(self._prepare_contact_name_from_partner(partner))
        values.update(self._prepare_partner_name_from_partner(partner))
        return values

    def _prepare_address_values_from_partner(self, partner):
        """≙ ``_prepare_address_values_from_partner`` (:731-737).

        Todos o ninguno: mezclar dos direcciones produce una tercera que no es
        de nadie.
        """
        if any(getattr(partner, f, None) for f in PARTNER_ADDRESS_FIELDS_TO_SYNC):
            source = partner
        else:
            source = self
        return {f: getattr(source, f, None) for f in PARTNER_ADDRESS_FIELDS_TO_SYNC}

    def _prepare_contact_name_from_partner(self, partner):
        """≙ ``_prepare_contact_name_from_partner`` (:739-741)."""
        contact_name = '' if partner.is_company else partner.name
        return {'contact_name': contact_name or self.contact_name}

    def _prepare_partner_name_from_partner(self, partner):
        """≙ ``_prepare_partner_name_from_partner`` (:743-751).

        Nombre de empresa: el del padre del cliente si lo tiene; si no, el suyo
        cuando es empresa; si no, su ``company_name``.
        """
        partner_name = partner.parent_id.name if partner.parent_id_id else ''
        if not partner_name and partner.is_company:
            partner_name = partner.name
        elif not partner_name and partner.company_name:
            partner_name = partner.company_name
        return {'partner_name': partner_name or self.partner_name}

    def _get_partner_email_update(self, force_void=True):
        """≙ ``_get_partner_email_update`` (:753-770).

        ¿Hay que escribir el correo en el cliente? Vive aparte porque lo
        consumen el cómputo, el inverso y el aviso de la interfaz.

        :param bool force_void: con ``False`` se omite cuando la iniciativa
          tiene el correo vacío, para no propagar un vacío sobre un valor bueno.
        """
        if self.partner_id_id and (force_void or self.email_from) \
                and self.email_from != self.partner_id.email:
            own = (email_normalize_all(self.email_from) or [None])[0] \
                or self.email_from or False
            from_partner = (email_normalize_all(self.partner_id.email) or [None])[0] \
                or self.partner_id.email or False
            return own != from_partner
        return False

    def _get_partner_phone_update(self, force_void=True):
        """≙ ``_get_partner_phone_update`` (:772-790). Gemelo del anterior."""
        if self.partner_id_id and (force_void or self.phone) \
                and self.phone != self.partner_id.phone:
            own = self._phone_format(self.phone) or self.phone or False
            from_partner = self._phone_format(self.partner_id.phone) \
                or self.partner_id.phone or False
            return own != from_partner
        return False

    def _phone_format(self, number):
        """Formato E.164 mínimo — el ``_phone_format`` de ``mail.thread.phone``.

        DIVERGENCIA DE MECANISMO declarada: la fuente lo hereda de ese mixin,
        que envuelve la librería ``phonenumbers``. Aquí el mixin no existe, así
        que se construye lo que el contrato necesita: quitar separadores y
        anteponer el prefijo del país cuando el número no lo trae.
        """
        if not number:
            return ''
        clean = ''.join(c for c in number if c.isdigit() or c == '+')
        if clean.startswith('+') or not self.country_id_id:
            return clean
        prefix = getattr(self.country_id, 'phone_code', None)
        return f'+{prefix}{clean}' if prefix else clean

    # ------------------------------------------------------------
    # ORM
    # ------------------------------------------------------------

    def save(self, *args, **kwargs):
        """≙ ``create`` (:795-826) + ``write`` (:828-891), fundidos.

        DIVERGENCIA DE FORMA declarada: la fuente separa alta y modificación en
        dos métodos porque su ORM los expone así; Django los une en ``save()``
        y distingue por ``self._state.adding``. El **orden de los efectos** se
        conserva exacto, que es lo que el contrato promete:

        1. saneado del sitio web;
        2. en modificación: fecha de último cambio de etapa, promoción a ganada
           cuando la etapa nueva es de victoria, fecha de asignación al cambiar
           el responsable, y fecha de cierre;
        3. estado previo de ganada/perdida, para la tabla de frecuencias;
        4. la escritura;
        5. los cómputos almacenados;
        6. ``_handle_won_lost`` con el estado nuevo.
        """
        es_alta = self._state.adding

        if self.website:
            self.website = ResPartner._clean_website(self.website)

        now = datetime.now(timezone.utc)
        stage_updated, stage_is_won = False, False
        previous = None

        if not es_alta:
            previous = type(self).objects.filter(pk=self.pk).values(
                'stage_id', 'user_id', 'won_status', 'active', 'probability').first()

        if previous is not None:
            # cambio de etapa: sella la fecha del último cambio
            stage_updated = previous['stage_id'] != self.stage_id_id
            if stage_updated:
                self.date_last_stage_update = now
            if stage_updated and self.stage_id_id and self.stage_id.is_won:
                self.active = True
                self.probability = 100
                self.automated_probability = 100
                stage_is_won = True
            # cambio de responsable: sella la fecha de asignación
            if not self.user_id_id:
                self.date_open = None
            elif previous['user_id'] != self.user_id_id:
                self.date_open = now

        # fecha de cierre, con la misma cascada de la fuente
        if (self.probability or 0) >= 100 or not self.active:
            self.date_closed = now
        elif (self.probability or 0) > 0:
            self.date_closed = None
        elif stage_updated and not stage_is_won:
            self.date_closed = None

        previous_status = {}
        if previous is not None:
            previous_status = {self.pk: {
                'is_lost': previous['won_status'] == 'lost',
                'is_won': previous['won_status'] == 'won',
            }}

        self._compute_stored_fields()
        res = super().save(*args, **kwargs)

        # alta directamente en etapa ganada: sella la fecha de cierre
        if es_alta and not self.date_closed and self.stage_id_id and self.stage_id.is_won:
            self.date_closed = now
            super().save(update_fields=['date_closed'])

        type(self)._handle_won_lost(
            type(self).objects.filter(pk=self.pk),
            previous_status,
            {self.pk: {
                'is_lost': self.won_status == 'lost',
                'is_won': self.won_status == 'won',
            }},
        )
        return res

    def _compute_stored_fields(self):
        """Ejecuta, en orden de dependencia, los cómputos que sí son columna.

        No tiene contraparte de un solo símbolo en la fuente: allá el ORM
        resuelve el grafo de ``@api.depends`` y dispara cada cómputo cuando toca.
        Aquí ese motor no existe, así que el orden se escribe a mano — y se
        escribe **una vez**, en vez de repetirlo en cada llamador.
        """
        self._compute_name()
        self._compute_team_id()
        self._compute_company_id()
        self._compute_stage_id()
        self._compute_date_open()
        self._compute_date_last_stage_update()
        self._compute_contact_name()
        self._compute_partner_name()
        self._compute_function()
        self._compute_website()
        self._compute_lang_id()
        self._compute_partner_address_values()
        self._compute_email_from()
        self._compute_email_domain_criterion()
        self._compute_phone()
        self._compute_phone_state()
        self._compute_email_state()
        self._compute_prorated_revenue()
        self._compute_recurring_revenue_monthly()
        self._compute_recurring_revenue_monthly_prorated()
        self._compute_recurring_revenue_prorated()
        self._compute_won_status()
        self._compute_day_open()
        self._compute_day_close()

    @classmethod
    def search_fetch(cls, domain, field_names=None, offset=0, limit=None, order=None):
        """≙ ``search_fetch`` (:893-971) — orden por vencimiento de MI actividad.

        BLOQUEADO por ``search_fetch`` — el ORM espejado no lo declara: es la
        superficie de ``search_read`` del canal RPC, que este árbol resuelve por
        DRF. La fuente intercepta el orden
        ``my_activity_date_deadline`` y resuelve la búsqueda en dos pasos
        (primero las iniciativas con actividad propia, ordenadas por su
        vencimiento más temprano; luego el resto). Condición de cierre: que
        exista un listado que ofrezca ese orden; hoy ningún consumidor lo pide.

        El símbolo se conserva delegando en el orden normal, que es lo que la
        propia fuente hace cuando el orden pedido no lo menciona (:920-921).
        """
        qs = cls.objects.filter(domain) if isinstance(domain, Q) else cls.objects.all()
        if order:
            qs = qs.order_by(*[o.strip() for o in order.split(',')])
        return qs[offset:(offset + limit)] if limit else qs[offset:]

    @classmethod
    def _handle_won_lost(cls, leads, old_status_by_lead, new_status_by_lead):
        """≙ ``_handle_won_lost`` (:973-1021).

        Toda transición de ganada/perdida mueve la tabla de frecuencias:
        llegar a perdida incrementa su cuenta, salir de ella la decrementa, y
        lo mismo para ganada. Pueden ocurrir a la vez (de perdida a ganada).
        """
        alcanzan_won, dejan_won = [], []
        alcanzan_lost, dejan_lost = [], []

        for lead in leads:
            nuevo = new_status_by_lead.get(lead.pk, {'is_lost': False, 'is_won': False})
            viejo = old_status_by_lead.get(lead.pk, {'is_lost': False, 'is_won': False})
            if nuevo['is_lost'] and nuevo['is_won']:
                raise ValidationError(
                    _("The lead %s cannot be won and lost at the same time.") % lead
                )
            if nuevo['is_lost'] and not viejo['is_lost']:
                alcanzan_lost.append(lead)
            elif not nuevo['is_lost'] and viejo['is_lost']:
                dejan_lost.append(lead)
            if nuevo['is_won'] and not viejo['is_won']:
                alcanzan_won.append(lead)
            elif not nuevo['is_won'] and viejo['is_won']:
                dejan_won.append(lead)

        cls._pls_increment_frequencies(alcanzan_won, to_state='won')
        cls._pls_increment_frequencies(dejan_won, from_state='won')
        cls._pls_increment_frequencies(alcanzan_lost, to_state='lost')
        cls._pls_increment_frequencies(dejan_lost, from_state='lost')
        return True

    def copy_data(self, default=None):
        """≙ ``copy_data`` (:1023-1038).

        Al duplicar: la etapa vuelve a la inicial, la fecha de asignación es
        hoy si ya era oportunidad, y un responsable inactivo no se arrastra.
        """
        default = dict(default or {})
        vals = super().copy_data(default=default) if hasattr(super(), 'copy_data') else dict(default)
        now = datetime.now(timezone.utc)
        vals.setdefault('type', self.type)
        vals.setdefault('team_id', self.team_id_id)
        is_active = bool(self.user_id_id and getattr(self.user_id, 'is_active', True))
        vals['date_open'] = now if self.type == self.TYPE_OPPORTUNITY and is_active else None
        if not is_active:
            vals['user_id'] = None
        return vals

    def delete(self, *args, **kwargs):
        """≙ ``unlink`` (:1040-1053).

        La fuente desliga primero las reuniones, para no dejar un enlace que no
        lleva a ninguna parte. BLOQUEADO por el addon ``calendar``: no hay
        reunión que desligar. Misma condición de cierre que
        ``_compute_meeting_display``.
        """
        return super().delete(*args, **kwargs)

    @classmethod
    def _read_group_stage_ids(cls, stages, domain=None, team_id=None,
                              show_user_team_stages=False, user=None):
        """≙ ``_read_group_stage_ids`` (:1055-1069) — el ``group_expand``.

        Devuelve las columnas que el kanban debe mostrar aunque estén vacías:
        las ya presentes, más las que no están plegadas, más las del equipo en
        contexto. El contexto implícito de la fuente se recibe aquí por
        argumento, que es lo que este stack tiene en su lugar.
        """
        team_ids = set()
        if show_user_team_stages and user is not None:
            team_ids |= set(CrmTeam.objects.filter(member_ids=user).values_list('pk', flat=True))
        if team_id:
            team_ids.add(team_id)
        presentes = Q(pk__in=[s.pk for s in stages])
        if team_ids:
            criterion = presentes | Q(team_ids__isnull=True) | Q(team_ids__in=list(team_ids))
        else:
            criterion = presentes | Q(team_ids__isnull=True)
        return CrmStage.objects.filter(criterion).distinct().order_by('sequence', 'pk')

    def _stage_find(self, team_id=False, domain=None, order=('sequence', 'id'), limit=1):
        """≙ ``_stage_find`` (:1071-1099).

        Busca la etapa que corresponde: las del equipo dado más las del propio
        registro, y las que no están atadas a ningún equipo.
        """
        team_ids = set()
        if team_id:
            team_ids.add(team_id)
        if self.team_id_id:
            team_ids.add(self.team_id_id)
        if team_ids:
            criterion = Q(team_ids__isnull=True) | Q(team_ids__in=list(team_ids))
        else:
            criterion = Q(team_ids__isnull=True)
        qs = CrmStage.objects.filter(criterion)
        if domain:
            qs = qs.filter(**domain)
        order_by = ['sequence', 'pk'] if tuple(order) == ('sequence', 'id') else list(order)
        qs = qs.distinct().order_by(*order_by)
        if limit is None:
            return qs
        return qs.first() if limit == 1 else qs[:limit]

    # ------------------------------------------------------------
    # ACTIONS
    # ------------------------------------------------------------

    def action_unarchive(self):
        """≙ ``action_unarchive`` (:1101-1110).

        Al reactivar se fuerza el recálculo de la probabilidad. Archivar no
        dispara nada: una iniciativa puede estar archivada sin estar perdida.
        """
        activada = not self.active
        self.active = True
        if activada:
            self.lost_reason_id = None
            self._compute_probabilities()
        self.save()
        return True

    def action_restore(self):
        """≙ ``action_restore`` (:1112-1119).

        Restaurar una perdida la devuelve a su ciclo normal: reactiva **y**
        vuelve a alinear la probabilidad con la automática, que es lo que
        ``action_unarchive`` por sí sola no hace.
        """
        self.action_unarchive()
        self.probability = self.automated_probability
        self.save(update_fields=['probability'])

    def action_set_lost(self, **additional_values):
        """≙ ``action_set_lost`` (:1121-1125).

        Semántica de perdida: ``probability = 0`` Y ``active = False``.
        """
        self.active = False
        for key, value in additional_values.items():
            setattr(self, key, value)
        self.probability = 0
        self.automated_probability = 0
        self.save()
        return True

    def action_set_won(self):
        """≙ ``action_set_won`` (:1127-1151).

        Semántica de ganada: la etapa es de victoria (y la probabilidad 100,
        implícito por la restricción).

        El comentario ABD de la fuente se conserva porque explica el porqué del
        rodeo: un pipeline puede alternar etapas «ganada» y «normal», así que se
        busca la primera de victoria **por encima** de la actual y, si no la
        hay, la última por debajo.
        """
        self.action_unarchive()
        won_stages = list(self._stage_find(domain={'is_won': True}, limit=None))
        current_sequence = self.stage_id.sequence if self.stage_id_id else 0
        stage = next((s for s in won_stages if s.sequence > current_sequence), None)
        if stage is None:
            stage = next((s for s in reversed(won_stages) if s.sequence <= current_sequence),
                         won_stages[0] if won_stages else None)
        if stage is not None:
            self.stage_id = stage
            self.probability = 100
            self.save()
        return True

    def action_set_automated_probability(self):
        """≙ ``action_set_automated_probability`` (:1153-1157)."""
        self._compute_probabilities()
        self.probability = self.automated_probability
        self.save(update_fields=['probability', 'automated_probability'])

    def action_set_won_rainbowman(self):
        """≙ ``action_set_won_rainbowman`` (:1159-1173)."""
        self.action_set_won()
        message = self._get_rainbowman_message()
        if message:
            return {
                'effect': {
                    'fadeout': 'slow',
                    'message': message,
                    'img_url': '/web/static/img/smile.svg',
                    'type': 'rainbow_man',
                }
            }
        return True

    def get_rainbowman_message(self):
        """≙ ``get_rainbowman_message`` (:1175-1179)."""
        if self.stage_id_id and self.stage_id.is_won:
            return self._get_rainbowman_message()
        return False

    def _get_rainbowman_message(self):
        """≙ ``_get_rainbowman_message`` (:1181-1264).

        El mensaje de celebración, con la **misma cascada de prioridad** de la
        fuente: primer trato del vendedor, récord del equipo a 31 y a 7 días,
        récord personal a 31 y a 7, cinco cierres hoy, racha de tres días,
        cierre más rápido del mes, salto directo de la primera etapa a la
        victoria, primer país y primera fuente del año.

        La consulta de la fuente es un ``SELECT`` con nueve agregados sobre
        ``crm_lead``; aquí se expresa con el ORM, que es el mecanismo de este
        stack para el mismo agregado.
        """
        if not self.user_id_id:
            return False

        tz_midnight = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0)

        won_leads = type(self).objects.filter(
            type=self.TYPE_OPPORTUNITY, active=True, probability=100,
        )
        won_this_year = won_leads.filter(created_at__year=tz_midnight.year)
        mine = won_this_year.filter(user_id=self.user_id_id)

        def _max_revenue(qs, dias):
            since = tz_midnight - timedelta(days=dias)
            fila = qs.exclude(pk=self.pk).filter(created_at__gte=since).order_by(
                '-expected_revenue').values_list('expected_revenue', flat=True).first()
            return fila

        def _is_lower_than_expected_revenue(value):
            """≙ ``_is_lower_than_expected_revenue`` (:1233-1234)."""
            return bool(self.expected_revenue) and value is not None \
                and value < self.expected_revenue

        team_stages = won_this_year.filter(team_id=self.team_id_id) if self.team_id_id \
            else won_this_year.filter(team_id__isnull=True)

        closed_today = mine.filter(created_at__gte=tz_midnight).count()
        closed_yesterday = mine.filter(
            created_at__gte=tz_midnight - timedelta(days=1),
            created_at__lt=tz_midnight).count()
        closed_minus2day = mine.filter(
            created_at__gte=tz_midnight - timedelta(days=2),
            created_at__lt=tz_midnight - timedelta(days=1)).count()
        closed_minus3day = mine.filter(
            created_at__gte=tz_midnight - timedelta(days=3),
            created_at__lt=tz_midnight - timedelta(days=2)).count()

        if mine.count() == 1:
            return _('Go, go, go! Congrats for your first deal.')
        if _is_lower_than_expected_revenue(_max_revenue(team_stages, 31)):
            return _('Boom! Team record for the past 30 days.')
        if _is_lower_than_expected_revenue(_max_revenue(team_stages, 7)):
            return _('Yeah! Best deal out of the last 7 days for the team.')
        if _is_lower_than_expected_revenue(_max_revenue(mine, 31)):
            return _('You just beat your personal record for the past 30 days.')
        if _is_lower_than_expected_revenue(_max_revenue(mine, 7)):
            return _('You just beat your personal record for the past 7 days.')
        if closed_today == 5:
            return _("You're on fire! Fifth deal won today")
        if closed_today == 1 and closed_yesterday and closed_minus2day and not closed_minus3day:
            return _("You're on a winning streak. 3 deals in 3 days, congrats!")
        # el cierre más rápido del mes, con la guarda del minuto de la fuente:
        # sólo cuenta si transcurrió tiempo real desde el alta
        min_days = won_this_year.filter(
            created_at__gte=tz_midnight - timedelta(days=31),
        ).order_by('day_close').values_list('day_close', flat=True).first()
        if min_days is not None and min_days == self.day_close \
                and (self.day_close or 31) < 31 and self.date_closed \
                and (self.date_closed - self.created_at).total_seconds() > 60:
            return _('Wow, that was fast. That deal did not stand a chance!')
        # salto de la primera etapa directamente a la victoria
        stages = [int(k) for k, dur in self.duration_tracking.items() if dur >= 60]
        if len(stages) == 1:
            first_stage = CrmStage.objects.filter(
                Q(team_ids__isnull=True) | Q(team_ids=self.team_id_id)
            ).order_by('sequence').first()
            if first_stage is not None and first_stage.pk == stages[0]:
                return _('No detours, no delays - from %(stage_name)s straight to the win!') % {
                    'stage_name': first_stage.name}
        if self.country_id_id and won_this_year.filter(country_id=self.country_id_id).count() == 1:
            return _('You just expanded the map! First win in %(country)s.') % {
                'country': self.country_id.name}
        if self.source_id_id and won_this_year.filter(source_id=self.source_id_id).count() == 1:
            return _('Yay, your first win from %(utm_source_name)s!') % {
                'utm_source_name': self.source_id.name}
        return False

    @property
    def duration_tracking(self):
        """≙ ``duration_tracking`` de ``mail.tracking.duration.mixin``.

        BLOQUEADO por ``mail.tracking.duration.mixin`` — ese mixin no existe en
        este árbol. Devuelve el diccionario vacío, que es lo que la fuente
        devuelve para un registro sin historial de etapas. Condición de cierre:
        portarlo.
        """
        return {}

    def action_schedule_meeting(self, smart_calendar=True):
        """≙ ``action_schedule_meeting`` (:1266-1294).

        BLOQUEADO por el addon ``calendar``. Se conserva el **descriptor de
        acción** verbatim —que es el contrato que un cliente consume— y se omite
        sólo el tramo de calendario inteligente, que necesita leer reuniones.
        Condición de cierre: portar el addon ``calendar``.
        """
        opportunity_id = self.pk if self.type == self.TYPE_OPPORTUNITY else False
        partner_ids = [self.partner_id_id] if self.partner_id_id else []
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'calendar.event',
            'context': {
                'search_default_opportunity_id': opportunity_id,
                'default_opportunity_id': opportunity_id,
                'default_partner_id': self.partner_id_id,
                'default_partner_ids': partner_ids,
                'default_team_id': self.team_id_id,
                'default_name': self.name,
            },
        }

    def _get_opportunity_meeting_view_parameters(self):
        """≙ ``_get_opportunity_meeting_view_parameters`` (:1296-1365).

        BLOQUEADO por el addon ``calendar``. Sin reuniones la fuente devuelve
        exactamente esto (:1300-1301), así que el valor es el correcto, no un
        marcador. Condición de cierre: portar el addon ``calendar``.
        """
        return "week", False

    def action_reschedule_meeting(self):
        """≙ ``action_reschedule_meeting`` (:1367-1373).

        BLOQUEADO por ``calendar.event`` — el addon ``calendar`` no existe en
        este árbol. Misma condición de cierre que ``action_schedule_meeting``.
        """
        return self.action_schedule_meeting(smart_calendar=False)

    def action_show_potential_duplicates(self):
        """≙ ``action_show_potential_duplicates`` (:1375-1390)."""
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'crm.lead',
            'domain': [('id', 'in', list(
                self.duplicate_lead_ids.values_list('pk', flat=True)))],
            'context': {'active_test': False, 'create': False},
        }

    # ------------------------------------------------------------
    # VIEWS
    # ------------------------------------------------------------

    def redirect_lead_opportunity_view(self):
        """≙ ``redirect_lead_opportunity_view`` (:1392-1404)."""
        return {
            'name': _('Lead or Opportunity'),
            'view_mode': 'form',
            'res_model': 'crm.lead',
            'domain': [('type', '=', self.type)],
            'res_id': self.pk,
            'view_id': False,
            'type': 'ir.actions.act_window',
            'context': {'default_type': self.type},
        }

    @classmethod
    def get_empty_list_help(cls, help_message, default_type=None):
        """≙ ``get_empty_list_help`` (:1406-1440).

        El texto que se muestra cuando el listado está vacío. La fuente añade
        el alias de correo del equipo para invitar a probar la pasarela; ese
        tramo queda **bloqueado** mientras ``crm.team`` no declare alias, y su
        condición de cierre es el porte de ``crm_team.py`` (759 líneas en la
        fuente, con ``alias_id``).
        """
        if not is_html_empty(help_message):
            return help_message
        if default_type == cls.TYPE_LEAD:
            titulo = _('Create a new lead')
        else:
            titulo = _('Create an opportunity to start playing with your pipeline.')
        return (f'<p class="o_view_nocontent_smiling_face">{titulo}</p>'
                f'<p class="oe_view_nocontent_alias"></p>')

    # ------------------------------------------------------------
    # BUSINESS
    # ------------------------------------------------------------

    @classmethod
    def _assign_userless_lead_in_team(cls, leads, creation_source):
        """≙ ``_assign_userless_lead_in_team`` (:1442-1452).

        Sin asignación por reglas, una iniciativa sin vendedor se la queda el
        líder de su equipo, y queda registrado en el hilo.
        """
        if cls._is_rule_based_assignment_activated():
            return
        userless = [lead for lead in leads if not lead.user_id_id and lead.team_id_id]
        for team, team_stages in groupby(userless, lambda lead: lead.team_id):
            if not team or not team.user_id_id:
                continue
            for lead in team_stages:
                lead.user_id_id = team.user_id_id
                lead.save(update_fields=['user_id'])
                lead.message_post(body=_(
                    'This new lead created by %(creation_source)s was automatically '
                    'assigned to team leader %(user_name)s'
                ) % {'user_name': team.user_id.name, 'creation_source': creation_source})

    def log_meeting(self, meeting):
        """≙ ``log_meeting`` (:1454-1477).

        BLOQUEADO por el addon ``calendar``: no hay reunión que registrar.
        Condición de cierre: portar el addon ``calendar``.
        """
        return None

    # ------------------------------------------------------------
    # MERGE AND CONVERT LEADS / OPPORTUNITIES
    # ------------------------------------------------------------

    @classmethod
    def _merge_data(cls, leads, fnames=None):
        """≙ ``_merge_data`` (:1479-1522).

        Cada tipo de campo se funde distinto: el texto se concatena, los
        relacionales múltiples se ignoran salvo callable propio, y el resto toma
        el primer valor no vacío — donde «primero» es el orden de confianza.
        """
        if fnames is None:
            fnames = cls._merge_get_fields()
        fcallables = cls._merge_get_fields_specific()
        address_values = cls._merge_get_fields_address(leads)

        def _get_first_not_null(attr):
            """≙ ``_get_first_not_null`` (:1499-1505)."""
            for lead in leads:
                value = getattr(lead, attr, None)
                if value:
                    return value
            return None

        data = {}
        for field_name in fnames:
            fcallable = fcallables.get(field_name)
            if fcallable and callable(fcallable):
                data[field_name] = fcallable(field_name, leads)
            elif field_name in address_values:
                data[field_name] = address_values[field_name]
            elif not cls._has_field(field_name):
                continue
            else:
                data[field_name] = _get_first_not_null(field_name)
        return data

    @classmethod
    def _has_field(cls, name_value):
        """Auxiliar del stack: ¿el modelo declara ese campo concreto?

        Sustituye a ``self._fields.get(field_name)`` de la fuente (:1508-1510),
        que es la puerta por la que su ORM descarta un nombre que no existe.
        """
        try:
            cls._meta.get_field(name_value)
            return True
        except Exception:
            return False

    @classmethod
    def merge_opportunity(cls, leads, user_id=False, team_id=False, auto_unlink=True):
        """≙ ``merge_opportunity`` (:1524-1538).

        Fundir iniciativas da una iniciativa; fundir cualquier cosa con al menos
        una oportunidad da una oportunidad. La superviviente es la más confiable,
        actualizada con lo que aporten las demás.
        """
        return cls._merge_opportunity(leads, user_id=user_id, team_id=team_id,
                                      auto_unlink=auto_unlink)

    @classmethod
    def _merge_opportunity(cls, leads, user_id=False, team_id=False,
                           auto_unlink=True, max_length=5):
        """≙ ``_merge_opportunity`` (:1540-1594).

        Versión privada: relaja el tope de cinco. No la llama un botón.
        """
        leads = list(leads)
        if len(leads) <= 1:
            raise UserError(
                _('Select at least two Leads/Opportunities from the list to merge them.'))
        if max_length and len(leads) > max_length:
            raise UserError(_(
                'To prevent data loss, Leads and Opportunities can only be merged '
                'by groups of %(max_length)s.') % {'max_length': max_length})

        sorted_leads = cls._sort_by_confidence_level(leads, reverse=True)
        head, tail = sorted_leads[0], sorted_leads[1:]

        merged_data = cls._merge_data(sorted_leads, cls._merge_get_fields())
        if user_id:
            merged_data['user_id'] = user_id
        if team_id:
            merged_data['team_id'] = team_id

        merged_followers = head._merge_followers(tail)
        head._merge_log_summary(merged_followers, tail)
        head._merge_dependences(tail)

        # si la etapa no pertenece al equipo resultante, se baja a la de menor
        # secuencia entre las que sí
        if merged_data.get('team_id'):
            team_stages = list(CrmStage.objects.filter(
                Q(team_ids=merged_data['team_id']) | Q(team_ids__isnull=True)
            ).distinct().order_by('sequence', 'pk'))
            ids = [s.pk for s in team_stages]
            stage = merged_data.get('stage_id')
            etapa_pk = stage.pk if hasattr(stage, 'pk') else stage
            if etapa_pk not in ids:
                merged_data['stage_id'] = team_stages[0] if team_stages else None

        # no reescribir lo que la cabeza ya tiene, para no recomputar de balde
        if 'user_id' in merged_data and head.user_id_id == _pk(merged_data['user_id']):
            merged_data.pop('user_id')
        if 'team_id' in merged_data and head.team_id_id == _pk(merged_data['team_id']):
            merged_data.pop('team_id')

        for key, value in merged_data.items():
            if cls._has_field(key):
                setattr(head, key, value)
        head.save()

        if auto_unlink:
            for lead in tail:
                lead.delete()
        return head

    @classmethod
    def _merge_get_fields_address(cls, leads):
        """≙ ``_merge_get_fields_address`` (:1596-1607).

        La dirección se propaga entera, tomada de la iniciativa con más campos
        de dirección puestos (a igualdad, la de mayor confianza).
        """
        source = max(leads, key=lambda lead: len(
            [f for f in PARTNER_ADDRESS_FIELDS_TO_SYNC if getattr(lead, f, None)]))
        return {f: getattr(source, f, None) for f in PARTNER_ADDRESS_FIELDS_TO_SYNC}

    @classmethod
    def _merge_get_fields_specific(cls):
        """≙ ``_merge_get_fields_specific`` (:1609-1618)."""
        return {
            'description': lambda fname, leads: '<br/><br/>'.join(
                d for d in (lead.description for lead in leads) if not is_html_empty(d)),
            'type': lambda fname, leads: cls.TYPE_OPPORTUNITY if any(
                lead.type == cls.TYPE_OPPORTUNITY for lead in leads) else cls.TYPE_LEAD,
            'priority': lambda fname, leads: max(
                [lead.priority for lead in leads if lead.priority], default=False),
            'tag_ids': lambda fname, leads: [
                t for lead in leads for t in lead.tag_ids.all()],
            'lost_reason_id': lambda fname, leads: (
                None if leads and leads[0].probability
                else next((lead.lost_reason_id for lead in leads
                           if lead.lost_reason_id_id), None)),
        }

    @classmethod
    def _merge_get_fields(cls):
        """≙ ``_merge_get_fields`` (:1620-1625)."""
        return (CRM_LEAD_FIELDS_TO_MERGE
                + list(cls._merge_get_fields_specific().keys())
                + PARTNER_ADDRESS_FIELDS_TO_SYNC)

    def _merge_dependences(self, opportunities):
        """≙ ``_merge_dependences`` (:1627-1639).

        Traslada a ``self`` —la superviviente— el historial, los adjuntos y las
        reuniones de las fundidas.
        """
        self._merge_dependences_history(opportunities)
        self._merge_dependences_attachments(opportunities)
        self._merge_dependences_calendar_events(opportunities)

    def _merge_dependences_history(self, opportunities):
        """≙ ``_merge_dependences_history`` (:1641-1668).

        Mueve mensajes y actividades, prefijando el asunto con el nombre de
        origen para que en el hilo se lea de dónde vino cada uno.
        """
        for opportunity in opportunities:
            for message in opportunity.message_ids:
                if message.subject:
                    subject = _("From %(source_name)s: %(source_subject)s") % {
                        'source_name': opportunity.name, 'source_subject': message.subject}
                else:
                    subject = _("From %(source_name)s") % {'source_name': opportunity.name}
                message.res_id = self.pk
                message.subject = subject
                message.save(update_fields=['res_id', 'subject'])
            for activity in opportunity._activity_queryset():
                activity.res_id = self.pk
                activity.save(update_fields=['res_id'])
        return True

    def _merge_dependences_attachments(self, opportunities):
        """≙ ``_merge_dependences_attachments`` (:1670-1693).

        Mueve los adjuntos y les renombra para no pisar a los propios: el
        sufijo dice de qué iniciativa venían, recortado a 20 caracteres como en
        la fuente.
        """
        IrAttachment = models.apps.get_model('base', 'IrAttachment')
        for opportunity in opportunities:
            attachments = IrAttachment.objects.filter(
                res_model=self._name, res_id=opportunity.pk)
            for attachment in attachments:
                attachment.res_id = self.pk
                attachment.name = _("%(attach_name)s (from %(lead_name)s)") % {
                    'attach_name': attachment.name,
                    'lead_name': (opportunity.name or '')[:20],
                }
                attachment.save(update_fields=['res_id', 'name'])
        return True

    def _merge_dependences_calendar_events(self, opportunities):
        """≙ ``_merge_dependences_calendar_events`` (:1695-1705).

        BLOQUEADO por el addon ``calendar``: no hay reunión que mover.
        Condición de cierre: portar el addon ``calendar``.
        """
        return None

    def _merge_followers(self, opportunities):
        """≙ ``_merge_followers`` (:1707-1749).

        Sólo se arrastran los seguidores **activos**: los que escribieron algo
        en los últimos 30 días y no siguen ya a la superviviente. La fuente lo
        resuelve con un ``SELECT MAX(id) … GROUP BY partner_id``; aquí con el
        agregado equivalente del ORM.
        """
        MailFollowers = models.apps.get_model('mail', 'MailFollowers')
        MailMessage = models.apps.get_model('mail', 'MailMessage')

        since = datetime.now(timezone.utc) - timedelta(days=30)
        source_ids = [lead.pk for lead in opportunities]

        active_authors = set(
            MailMessage.objects
            .filter(model=self._name, res_id__in=source_ids, created_at__gt=since)
            .values_list('author_id', flat=True)
        )
        already_following = set(
            MailFollowers.objects
            .filter(res_model=self._name, res_id=self.pk)
            .values_list('partner_id', flat=True)
        )
        to_move = (
            MailFollowers.objects
            .filter(res_model=self._name, res_id__in=source_ids,
                    partner_id__in=active_authors - already_following)
            .order_by('partner_id', '-pk')
        )
        by_old_lead = defaultdict(list)
        seen = set()
        for follower in to_move:
            if follower.partner_id in seen:
                continue
            seen.add(follower.partner_id)
            by_old_lead[follower.res_id].append(follower)
            follower.res_id = self.pk
            follower.save(update_fields=['res_id'])
        return dict(by_old_lead)

    def _merge_log_summary(self, merged_followers, opportunities_tail):
        """≙ ``_merge_log_summary`` (:1751-1762).

        La fuente renderiza la plantilla QWeb ``crm.crm_lead_merge_summary``.
        DIVERGENCIA DE MECANISMO: aquí no hay QWeb, así que el resumen se
        compone con el mismo contenido —qué se fundió y qué seguidores
        llegaron— en el cuerpo del mensaje.
        """
        names = ', '.join(lead.name or str(lead.pk) for lead in opportunities_tail)
        body = _('Merged with: %(names)s') % {'names': names}
        if merged_followers:
            body += '<br/>' + _('Followers moved: %(count)s') % {
                'count': sum(len(v) for v in merged_followers.values())}
        return self.message_post(body=body)

    def _format_properties(self):
        """≙ ``_format_properties`` (:1764-1831).

        Aplana las propiedades libres a una lista de ``{label, value}`` o
        ``{label, values}``, que es lo que el resumen de fusión pinta. Cada
        rama de tipo de la fuente se conserva: booleano, many2one, many2many,
        selección y etiquetas.
        """
        formatted = []
        for definition in (self.lead_properties or []):
            label = definition.get('string')
            value = definition.get('value')
            property_type = definition.get('type')
            if not value and property_type != 'boolean':
                continue

            property_dict = {'label': label}
            if property_type == 'boolean':
                property_dict['value'] = _('Yes') if value else _('No')
            elif value and property_type == 'many2one':
                property_dict['value'] = value[1]
            elif value and property_type == 'many2many':
                property_dict['values'] = [{'name': rec[1]} for rec in value]
            elif value and property_type in ('selection', 'tags'):
                options = {op[0]: op[1:] for op in (definition.get(property_type) or [])}
                if property_type == 'selection':
                    option = options.get(value)
                    property_dict['value'] = option[0] if option else None
                else:
                    property_dict['values'] = [
                        {'name': options[tag][0], 'color': options[tag][1]}
                        for tag in value if tag in options
                    ]
            else:
                property_dict['value'] = value
            formatted.append(property_dict)
        return formatted

    # CONVERT
    # ----------------------------------------------------------------------

    def _convert_opportunity_data(self, customer, team_id=False):
        """≙ ``_convert_opportunity_data`` (:1833-1848)."""
        new_team_id = team_id if team_id else self.team_id_id
        upd_values = {
            'type': self.TYPE_OPPORTUNITY,
            'date_conversion': datetime.now(timezone.utc),
        }
        if customer is not None and customer != self.partner_id:
            upd_values['partner_id'] = customer
        if not self.stage_id_id:
            upd_values['stage_id'] = self._stage_find(team_id=new_team_id)
        return upd_values

    @classmethod
    def convert_opportunity(cls, leads, partner, user_ids=False, team_id=False):
        """≙ ``convert_opportunity`` (:1850-1861).

        Una ganada no se reconvierte, ni una archivada.
        """
        for lead in leads:
            if not lead.active or lead.won_status == 'won':
                continue
            for key, value in lead._convert_opportunity_data(partner, team_id).items():
                setattr(lead, key, value)
            lead.save()
        if user_ids or team_id:
            cls._handle_salesmen_assignment(leads, user_ids=user_ids, team_id=team_id)
        return True

    @classmethod
    def _handle_partner_assignment(cls, leads, force_partner_id=False,
                                   create_missing=True, with_parent=None):
        """≙ ``_handle_partner_assignment`` (:1863-1878)."""
        for lead in leads:
            if force_partner_id:
                lead.partner_id_id = force_partner_id
            if not lead.partner_id_id and create_missing:
                lead.partner_id = lead._create_customer(with_parent=with_parent)
            lead.save(update_fields=['partner_id'])

    @classmethod
    def _handle_salesmen_assignment(cls, leads, user_ids=False, team_id=False):
        """≙ ``_handle_salesmen_assignment`` (:1880-1904).

        Reparto round-robin: con 4 vendedores y 6 iniciativas sale
        L1-S1, L2-S2, L3-S3, L4-S4, L5-S1, L6-S2.
        """
        leads = list(leads)
        if not user_ids and team_id:
            for lead in leads:
                lead.team_id_id = team_id
                lead.save(update_fields=['team_id'])
            return
        steps = len(user_ids)
        for idx in range(steps):
            for lead in leads[idx:len(leads):steps]:
                if team_id:
                    lead.team_id_id = team_id
                lead.user_id_id = user_ids[idx]
                lead.save(update_fields=['team_id', 'user_id'] if team_id else ['user_id'])

    # ------------------------------------------------------------
    # MERGE / CONVERT TOOLS — CLASSIFICATION
    # ------------------------------------------------------------

    @classmethod
    def _get_lead_duplicates(cls, partner=None, email=None, include_lost=False):
        """≙ ``_get_lead_duplicates`` (:1911-1941).

        :param include_lost: con ``True`` la búsqueda incluye oportunidades
          archivadas (sólo iniciativas activas). Con ``False``, sólo activas y
          no ganadas.
        """
        if not email and not partner:
            return cls.objects.none()

        criterion = Q(pk__in=[])
        normalizados = email_normalize_all(email) if email else []
        if normalizados:
            criterion |= Q(email_normalized__in=normalizados)
        if partner is not None:
            criterion |= Q(partner_id=_pk(partner))

        qs = cls.objects.filter(criterion)
        if include_lost:
            qs = qs.exclude(won_status='won').filter(
                Q(type=cls.TYPE_OPPORTUNITY) | Q(active=True))
        else:
            qs = qs.filter(won_status='pending', active=True)
        return qs

    @classmethod
    def _sort_by_confidence_level(cls, leads, reverse=False):
        """≙ ``_sort_by_confidence_level`` (:1943-1968).

        Heurística incremental de confianza, en el orden de la fuente:

        * «no perdida» primero — una iniciativa inactiva está perdida, y va al
          final; una oportunidad inactiva sigue siendo válida;
        * la oportunidad manda sobre la iniciativa, que es una pre-etapa de
          clasificación;
        * secuencia de etapa: cuanto mayor, más cerca de la victoria;
        * probabilidad: cuanto mayor, mejor;
        * id: a igualdad, la más reciente es la más confiable.
        """
        def key(lead):
            return (
                lead.type == cls.TYPE_OPPORTUNITY or lead.active,
                lead.type == cls.TYPE_OPPORTUNITY,
                lead.stage_id.sequence if lead.stage_id_id else 0,
                lead.probability or 0,
                -(lead.pk or 0),
            )
        return sorted(leads, key=key, reverse=reverse)

    # CUSTOMER TOOLS
    # --------------------------------------------------

    def _find_matching_partner(self):
        """≙ ``_find_matching_partner`` (:1970-1983)."""
        if self.partner_id_id:
            return self.partner_id
        email = self.email_normalized or self.email_from
        if not email:
            return None
        return ResPartner.objects.filter(email__iexact=email).first()

    def _create_customer(self, with_parent=None):
        """≙ ``_create_customer`` (:1985-2010).

        Crea el contacto a partir de los datos de la iniciativa. La empresa
        padre sale, en orden: del argumento, del nombre de empresa declarado,
        del cliente ya puesto, o de nada.
        """
        contact_name = self.contact_name
        if not contact_name and self.email_from:
            contact_name = parse_contact_from_email(self.email_from)[0]

        if with_parent:
            partner_company = with_parent
        elif self.partner_name:
            partner_company = ResPartner.objects.create(
                **self._prepare_customer_values(self.partner_name, is_company=True))
        elif self.partner_id_id:
            partner_company = self.partner_id
        else:
            partner_company = None

        if contact_name:
            return ResPartner.objects.create(**self._prepare_customer_values(
                contact_name, is_company=False, parent_id=_pk(partner_company)))
        if partner_company is not None:
            return partner_company
        return ResPartner.objects.create(
            **self._prepare_customer_values(self.name, is_company=False))

    def _get_customer_information(self):
        """≙ ``_get_customer_information`` (:2012-2033).

        Datos con los que la pasarela de correo rellena un contacto nuevo,
        indexados por correo. No se inventa la empresa padre aunque haya nombre
        de empresa — la fuente lo dice explícitamente.
        """
        base = getattr(super(), '_get_customer_information', dict)()
        key = self.email_normalized or self.email_from
        if not key:
            return base
        contact_name = (self.contact_name
                        or (parse_contact_from_email(self.email_from)[0]
                            if self.email_from else '')
                        or self.email_from)
        is_company = bool(self.partner_name) and contact_name == self.partner_name
        values = base.setdefault(key, {})
        values.update({
            k: v for k, v in self._prepare_customer_values(
                contact_name, is_company=is_company, parent_id=False).items()
            if v and k != 'email'   # el correo es el criterio; no se fuerza
        })
        values['is_company'] = is_company
        commercial = self.commercial_partner_id
        if not is_company and commercial is not None:
            values['parent_id'] = commercial.pk
            values.pop('company_name', None)
        return base

    def _prepare_customer_values(self, partner_name, is_company=False, parent_id=False):
        """≙ ``_prepare_customer_values`` (:2035-2068).

        :returns: el diccionario con el que se crea el ``res.partner``.
        """
        email_parts = email_split(self.email_from) if self.email_from else []
        res = {
            'name': partner_name,
            'user_id': self.user_id_id,
            'comment': self.description,
            'phone': self.phone,
            'email': email_parts[0] if email_parts else False,
            'function': self.function,
            # dirección
            'street': self.street,
            'street2': self.street2,
            'zip': self.zip,
            'city': self.city,
            'country_id': self.country_id_id,
            'state_id': self.state_id_id,
            'website': self.website,
            # empresa / jerarquía
            'parent_id': parent_id,
            'is_company': is_company,
            'company_name': not is_company and not parent_id and self.partner_name,
            'type': 'contact',
        }
        if self.lang_id_id and self.lang_id.active:
            res['lang'] = self.lang_id.code
        return res

    @classmethod
    def _is_rule_based_assignment_activated(cls):
        """≙ ``_is_rule_based_assignment_activated`` (:2070-2073)."""
        return bool(SystemParameter.get_param('crm.lead.auto.assignment', False))

    # ------------------------------------------------------------
    # MAILING
    # ------------------------------------------------------------

    def _creation_subtype(self):
        """≙ ``_creation_subtype`` (:2079-2080)."""
        return 'crm.mt_lead_create'

    def _creation_message(self):
        """≙ ``_creation_message`` (:2082-2086)."""
        if self.team_id_id:
            return _('A new lead has been created for the team "%(team_name)s".') % {
                'team_name': self.team_id.name}
        return _('A new lead has been created and is not assigned to any team.')

    def _track_subtype(self, init_values):
        """≙ ``_track_subtype`` (:2088-2100).

        La cascada de subtipos, en el orden exacto de la fuente: ganada, motivo
        de pérdida, cambio de etapa, restaurada, perdida.
        """
        if 'stage_id' in init_values and self.won_status == 'won':
            return 'crm.mt_lead_won'
        if 'lost_reason_id' in init_values and self.lost_reason_id_id:
            return 'crm.mt_lead_lost'
        if 'stage_id' in init_values:
            return 'crm.mt_lead_stage'
        if 'won_status' in init_values and self.won_status != 'lost':
            return 'crm.mt_lead_restored'
        if 'won_status' in init_values and self.won_status == 'lost':
            return 'crm.mt_lead_lost'
        base = getattr(super(), '_track_subtype', None)
        return base(init_values) if base else None

    def _notify_by_email_prepare_rendering_context(self, message, msg_vals=False, **kwargs):
        """≙ ``_notify_by_email_prepare_rendering_context`` (:2102-2113).

        Añade la fecha límite como subtítulo del correo de notificación.
        """
        base = getattr(super(), '_notify_by_email_prepare_rendering_context', None)
        render_context = base(message, msg_vals=msg_vals, **kwargs) if base else {}
        render_context.setdefault('subtitles', [])
        if self.date_deadline:
            render_context['subtitles'].append(
                _('Deadline: %s') % self.date_deadline.isoformat())
        return render_context

    def _notify_get_reply_to(self, default=None, author_id=False):
        """≙ ``_notify_get_reply_to`` (:2115-2123).

        La respuesta va al alias del equipo si lo tiene.

        BLOQUEADO por ``crm.team.alias_id`` — ``crm.team`` todavía no declara
        el alias de correo. Misma condición de cierre que
        ``get_empty_list_help``: el porte de ``crm_team.py``.
        """
        base = getattr(super(), '_notify_get_reply_to', None)
        return base(default=default, author_id=author_id) if base else {self.pk: default}

    @classmethod
    def message_new(cls, msg_dict, custom_values=None):
        """≙ ``message_new`` (:2124-2146).

        Alta desde la pasarela de correo. El autor por defecto se retira a
        propósito: la asignación la hace el scoring o una persona, nunca el
        usuario de la pasarela.
        """
        if custom_values is None:
            custom_values = {}
        defaults = {
            'name': msg_dict.get('subject') or _("No Subject"),
            'email_from': msg_dict.get('from'),
            'partner_id': msg_dict.get('author_id', False),
        }
        if msg_dict.get('priority') in dict(crm_stage.AVAILABLE_PRIORITIES):
            defaults['priority'] = msg_dict.get('priority')
        defaults.update(custom_values)

        base = getattr(super(), 'message_new', None)
        new_lead = base(msg_dict, custom_values=defaults) if base \
            else cls.objects.create(**{k: v for k, v in defaults.items()
                                       if cls._has_field(k)})
        cls._assign_userless_lead_in_team([new_lead], _('incoming email'))
        return new_lead

    def _message_post_after_hook(self, message, msg_vals):
        """≙ ``_message_post_after_hook`` (:2148-2165).

        Publicar con un destinatario explícito sobre una iniciativa sin cliente
        se lee como «se creó desde el chatter con destinatario sugerido», así
        que ese contacto se propaga a todas las iniciativas sin cliente que
        compartan su correo y estén en una etapa no plegada.
        """
        if self.email_from and not self.partner_id_id:
            new_partners = [p for p in getattr(message, 'partner_ids', [])
                      if p.email == self.email_from]
            if new_partners:
                nuevo = new_partners[0]
                type(self).objects.filter(
                    partner_id__isnull=True, email_from=nuevo.email,
                    stage_id__fold=False,
                ).update(partner_id=nuevo.pk)
        base = getattr(super(), '_message_post_after_hook', None)
        return base(message, msg_vals) if base else None

    @classmethod
    def get_import_templates(cls):
        """≙ ``get_import_templates`` (:2167-2172)."""
        return [{
            'label': _('Import Template for Leads & Opportunities'),
            'template': '/crm/static/xls/crm_lead.xls',
        }]

    # ------------------------------------------------------------
    # PLS — PREDICTIVE LEAD SCORING
    #
    # El comentario de encuadre de la fuente (:2174-2192) se conserva porque
    # explica el diseño entero: cada iniciativa ganada o perdida incrementa una
    # tabla de frecuencias, donde por cada par (campo, valor) se guarda cuántas
    # se ganaron y cuántas se perdieron. Una ganada de Bélgica sube en 1 la
    # cuenta de ganadas de la frecuencia ``country_id='Bélgica'``. Las
    # frecuencias se separan por equipo, así que el equipo A no contamina al B.
    #
    # Hay dos vías de construcción de la tabla:
    #   - Incremento en vivo: al ganar o perder se incrementa directo, JUSTO
    #     ANTES de escribir. Mantiene la tabla siempre al día.
    #   - Reconstrucción completa: se vacía y se rehace desde todas las ya
    #     cerradas. La hace el cron, y se usa de una vez cuando cambian los
    #     criterios (qué campos, desde qué fecha).
    # ------------------------------------------------------------

    @classmethod
    def _pls_get_naive_bayes_probabilities(cls, leads, batch_mode=False, is_tooltip=False):
        """≙ ``_pls_get_naive_bayes_probabilities`` (:2194-2371).

        Clasificador bayesiano ingenuo. La probabilidad de que un suceso ocurra
        bajo ciertas condiciones es proporcional a la de que ocurra bajo cada
        condición por separado, por la probabilidad a priori:

            S(Won | A∩B) = P(A∩B | Won) · P(Won)

        y el porcentaje sale de contrastarlo con el mismo cálculo para perder:

            Probabilidad = S(Won | A∩B) / (S(Won | A∩B) + S(Lost | A∩B))

        El problema clásico es la **frecuencia cero**: un suceso nunca
        observado anula el producto. Por eso se suma 0.1 a cada frecuencia. Con
        pocos datos el cálculo no es realista; cuantos más registros, más
        precisa la estimación.

        :param bool is_tooltip: recalcula la probabilidad de un único registro y
          devuelve además la lista de tríos (score, campo, valor) de todos los
          campos que entran en el cálculo. El score indica si el impacto es
          positivo (>.5) o negativo (<.5).
        :return: probabilidad en porcentaje, redondeada a 2 decimales.
        """
        lead_probabilities = {}
        leads = list(leads)
        if not leads:
            return lead_probabilities, {}

        tooltip_data = {}
        if is_tooltip:
            tooltip_data = {'probability': 0.0, 'scores': []}

        criterion = None
        if batch_mode:
            criterion = Q(active=True, won_status='pending',
                         pk__in=[lead.pk for lead in leads])
        leads_values_dict = cls._pls_get_lead_pls_values(leads, criterion=criterion)
        if not leads_values_dict:
            return lead_probabilities, tooltip_data

        # pares únicos a buscar en la tabla de frecuencias, y las ya ganadas
        leads_fields = set()
        won_leads = set()
        won_stage_ids = set(CrmStage.objects.filter(is_won=True).values_list('pk', flat=True))
        for lead_id, values in leads_values_dict.items():
            for field, value in values['values']:
                if field == 'stage_id' and value in won_stage_ids:
                    won_leads.add(lead_id)
                leads_fields.add(field)
        leads_fields = sorted(leads_fields)

        frequencies = list(
            CrmLeadScoringFrequency.objects
            .filter(variable__in=leads_fields).order_by('team_id', 'pk')
        )
        frequency_team_ids = [t for t in {f.team_id_id for f in frequencies} if t]

        # 1. contar cada valor por separado. No todas las variables entran (se
        # descartan las vacías), así que la probabilidad de cada valor se
        # calcula contra el total de SU propia variable. El equipo -1 acumula
        # todo, para las iniciativas cuyo equipo no está en la tabla.
        result = {tid: {f: {'won_total': 0, 'lost_total': 0} for f in leads_fields}
                  for tid in frequency_team_ids}
        result[-1] = {f: {'won_total': 0, 'lost_total': 0} for f in leads_fields}

        for frequency in frequencies:
            field = frequency.variable
            value = frequency.value    # siempre texto

            # una etiqueta con muestra pequeña pesaría demasiado
            if field == 'tag_id' and (frequency.won_count + frequency.lost_count) < 50:
                continue

            if frequency.team_id_id:
                team_result = result[frequency.team_id_id]
                team_result[field][value] = {'won': frequency.won_count,
                                             'lost': frequency.lost_count}
                team_result[field]['won_total'] += frequency.won_count
                team_result[field]['lost_total'] += frequency.lost_count

            if value not in result[-1][field]:
                result[-1][field][value] = {'won': 0, 'lost': 0}
            result[-1][field][value]['won'] += frequency.won_count
            result[-1][field][value]['lost'] += frequency.lost_count
            result[-1][field]['won_total'] += frequency.won_count
            result[-1][field]['lost_total'] += frequency.lost_count

        for team_id in result:
            (result[team_id]['team_won'],
             result[team_id]['team_lost'],
             result[team_id]['team_total']) = cls._pls_get_won_lost_total_count(
                result[team_id])

        save_team_id = None
        p_won, p_lost = 1, 1
        for lead_id, lead_values in leads_values_dict.items():
            lead_fields = [v[0] for v in lead_values.get('values', [])]
            # sin etapa no hay cálculo posible
            if 'stage_id' not in lead_fields:
                lead_probabilities[lead_id] = 0
                continue
            # en etapa ganada, 100 por definición
            if lead_id in won_leads:
                lead_probabilities[lead_id] = 100
                continue

            lead_team_id = lead_values['team_id'] if lead_values['team_id'] in result else -1
            if lead_team_id != save_team_id:
                save_team_id = lead_team_id
                team_won = result[save_team_id]['team_won']
                team_lost = result[save_team_id]['team_lost']
                team_total = result[save_team_id]['team_total']
                # con una cuenta en cero no se puede calcular
                if not team_won or not team_lost:
                    continue
                p_won = team_won / team_total
                p_lost = team_lost / team_total

            # 2. puntuación de ganada y de perdida con cada variable
            s_lead_won, s_lead_lost = p_won, p_lost
            for field, value in lead_values['values']:
                field_result = result.get(save_team_id, {}).get(field)
                value_result = field_result.get(str(value)) if field_result else False
                if not value_result:
                    continue
                total_won = team_won if field == 'stage_id' else field_result['won_total']
                total_lost = team_lost if field == 'stage_id' else field_result['lost_total']
                if not total_won or not total_lost:
                    continue
                p_field_value_won = value_result['won'] / total_won
                p_field_value_lost = value_result['lost'] / total_lost
                s_lead_won *= p_field_value_won
                s_lead_lost *= p_field_value_lost

                if is_tooltip:
                    score = (1 - p_field_value_lost if field == 'stage_id'
                             else p_field_value_won
                             / (p_field_value_won + p_field_value_lost))
                    tooltip_data['scores'].append((score, field, value))

            # 3. probabilidad de ganar
            probability = s_lead_won / (s_lead_won + s_lead_lost)
            lead_probabilities[lead_id] = min(
                max(round(100 * probability, 2), 0.01), 99.99)

        if tooltip_data and leads[0].pk in lead_probabilities:
            tooltip_data['probability'] = lead_probabilities[leads[0].pk]
        return lead_probabilities, tooltip_data

    # PLS: Live Increment
    # ---------------------------------

    @classmethod
    def _pls_increment_frequencies(cls, leads, from_state=None, to_state=None):
        """≙ ``_pls_increment_frequencies`` (:2373-2395).

        Al ganar o perder se incrementa cada parámetro del scoring; al
        reactivar una perdida por error, se decrementa.

        El incremento va ANTES de escribir porque hace falta conocer el cambio
        de estado (de dónde a dónde). Al llegar a un estado cerrado bastaría el
        estado final; el problema es al **salir** de él: una vez escritos los
        valores nuevos ya no se sabe cuál era el anterior. De ahí los dos
        parámetros ``from_state`` / ``to_state``.
        """
        leads = list(leads)
        if not leads:
            return
        new_frequencies, existing_frequencies = cls._pls_prepare_update_frequency_table(
            leads, target_state=from_state or to_state)
        cls._pls_update_frequency_table(
            new_frequencies, 1 if to_state else -1, existing_frequencies_by_team=existing_frequencies)

    # PLS: One shot rebuild
    # ---------------------------------

    @classmethod
    def _cron_update_automated_probabilities(cls):
        """≙ ``_cron_update_automated_probabilities`` (:2397-2405).

        Reconstruye la tabla de frecuencias y recalcula todas las
        probabilidades automáticas, alineando la manual cuando iban juntas.
        """
        started_at = datetime.now(timezone.utc)
        cls._rebuild_pls_frequency_table()
        cls._update_automated_probabilities()
        _logger.info("Predictive Lead Scoring : Cron duration = %d seconds",
                     (datetime.now(timezone.utc) - started_at).total_seconds())

    @classmethod
    def _rebuild_pls_frequency_table(cls):
        """≙ ``_rebuild_pls_frequency_table`` (:2407-2420)."""
        CrmLeadScoringFrequency.objects.all().delete()
        new_frequencies, _unused = cls._pls_prepare_update_frequency_table(
            cls.objects.none(), rebuild=True)
        cls._pls_update_frequency_table(new_frequencies, 1)
        _logger.info("Predictive Lead Scoring : crm.lead.scoring.frequency table rebuilt")

    @classmethod
    def _update_automated_probabilities(cls):
        """≙ ``_update_automated_probabilities`` (:2422-2496).

        Recalcula la probabilidad automática de todas las activas (ni ganadas ni
        perdidas). Va **por lotes** y cada lote en su transacción, para no
        bloquear la tabla minutos enteros: si hay concurrencia, entra en cola
        en vez de tumbar la escritura.
        """
        pls_start_date = cls._pls_get_safe_start_date()
        if not pls_start_date:
            return

        # 1. las candidatas: con etapa, creadas tras la fecha de arranque, ni
        # ganadas ni perdidas
        leads_to_update = list(cls.objects.filter(
            stage_id__isnull=False, created_at__gte=pls_start_date,
            won_status='pending',
        ))
        total = len(leads_to_update)

        # 2. por lotes, para no reventar la memoria
        lead_probabilities = {}
        for i in range(0, total, PLS_COMPUTE_BATCH_STEP):
            batch = leads_to_update[i:i + PLS_COMPUTE_BATCH_STEP]
            partial_probabilities, _unused = cls._pls_get_naive_bayes_probabilities(
                batch, batch_mode=True)
            lead_probabilities.update(partial_probabilities)
        _logger.info("Predictive Lead Scoring : New automated probabilities computed")

        # 3. agrupar por probabilidad, para reducir viajes al servidor
        probability_leads = defaultdict(list)
        for lead_id, probability in sorted(lead_probabilities.items()):
            probability_leads[probability].append(lead_id)

        # 4. escribir la automática, y la manual sólo si iban alineadas
        transactions, failed = 0, 0
        started_at = datetime.now(timezone.utc)
        for probability, ids in probability_leads.items():
            for batch_ids in split_every(PLS_UPDATE_BATCH_STEP, ids):
                transactions += 1
                try:
                    qs = cls.objects.filter(pk__in=list(batch_ids))
                    qs.filter(Q(probability=models.F('automated_probability'))
                              | Q(probability__isnull=True)).update(
                        automated_probability=probability, probability=probability)
                    qs.exclude(Q(probability=models.F('automated_probability'))
                               | Q(probability__isnull=True)).update(
                        automated_probability=probability)
                except Exception as e:
                    _logger.warning(
                        "Predictive Lead Scoring : update transaction failed. Error: %s", e)
                    failed += 1

        _logger.info(
            "Predictive Lead Scoring : All automated probabilities updated "
            "(%d leads / %d transactions (%d failed) / %d seconds)",
            total, transactions, failed,
            (datetime.now(timezone.utc) - started_at).total_seconds())

    # PLS: Common parts for both mode
    # ---------------------------------

    @classmethod
    def _pls_prepare_update_frequency_table(cls, leads, rebuild=False, target_state=False):
        """≙ ``_pls_prepare_update_frequency_table`` (:2498-2585).

        Común a las dos vías. Prepara dos diccionarios: las frecuencias NUEVAS
        (que hay que insertar) y las EXISTENTES (que hay que actualizar). En
        reconstrucción sólo hacen falta las nuevas, porque la tabla se vació.

        Las candidatas son, en vivo, las que se pasan; en reconstrucción, todas
        las cerradas de la base.
        """
        pls_start_date = cls._pls_get_safe_start_date()
        if not pls_start_date:
            return {}, {}

        if rebuild:
            pls_leads = list(cls.objects.filter(
                created_at__gte=pls_start_date, won_status__in=['lost', 'won']))
            team_ids = list(CrmTeam.objects.values_list('pk', flat=True)) + [0]
            criterion = Q(created_at__gte=pls_start_date, won_status__in=['lost', 'won'])
        else:
            pls_leads = [lead for lead in leads
                         if lead.created_at and lead.created_at.date() >= pls_start_date]
            if not pls_leads:
                return {}, {}
            team_ids = [lead.team_id_id for lead in pls_leads if lead.team_id_id] + [0]
            criterion = Q(pk__in=[lead.pk for lead in pls_leads])

        leads_values_dict = cls._pls_get_lead_pls_values(pls_leads, criterion=criterion)

        # repartir los valores por equipo
        leads_frequency_values_by_team = {tid: [] for tid in team_ids}
        leads_pls_fields = set()
        for values in leads_values_dict.values():
            team_id = values.get('team_id', 0) or 0
            if team_id not in leads_frequency_values_by_team:
                leads_frequency_values_by_team[team_id] = []
            lead_frequency_values = {'count': 1}
            lead_probability = 0
            for field, value in values['values']:
                if field != 'probability':
                    leads_pls_fields.add(field)
                else:
                    # se añadió para saber el estado en modo lote; no es un
                    # campo del scoring, pero hace falta para la etiqueta
                    lead_probability = value
                if field == 'tag_id':
                    leads_frequency_values_by_team[team_id].append(
                        {field: value, 'count': 1, 'probability': lead_probability})
                else:
                    lead_frequency_values[field] = value
            leads_frequency_values_by_team[team_id].append(lead_frequency_values)
        leads_pls_fields = sorted(leads_pls_fields)

        new_frequencies_by_team = {}
        for team_id in leads_frequency_values_by_team:
            new_frequencies_by_team[team_id] = cls._pls_prepare_frequencies(
                leads_frequency_values_by_team[team_id], leads_pls_fields,
                target_state=target_state)

        existing_frequencies_by_team = {}
        if not rebuild:
            own_team_ids = [lead.team_id_id for lead in pls_leads if lead.team_id_id]
            for frequency in CrmLeadScoringFrequency.objects.filter(
                Q(variable__in=leads_pls_fields)
                & (Q(team_id__in=own_team_ids) | Q(team_id__isnull=True))
            ):
                team_id = frequency.team_id_id or 0
                if team_id not in existing_frequencies_by_team:
                    existing_frequencies_by_team[team_id] = {
                        f: {} for f in leads_pls_fields}
                existing_frequencies_by_team[team_id][frequency.variable][frequency.value] = {
                    'frequency_id': frequency.pk,
                    'won': frequency.won_count,
                    'lost': frequency.lost_count,
                }
        return new_frequencies_by_team, existing_frequencies_by_team

    @classmethod
    def _pls_update_frequency_table(cls, new_frequencies_by_team, step,
                                    existing_frequencies_by_team=None):
        """≙ ``_pls_update_frequency_table`` (:2587-2633).

        Crea o actualiza la tabla, por equipo y cruzando empresas.
        """
        values_to_update = {}
        values_to_create = []
        existing_frequencies_by_team = existing_frequencies_by_team or {}

        for team_id, new_frequencies in new_frequencies_by_team.items():
            for field, value in new_frequencies.items():
                current_frequencies = existing_frequencies_by_team.get(team_id, {})
                for param, result in value.items():
                    current_sequence = current_frequencies.get(field, {}).get(param, {})
                    if current_sequence:
                        new_won = current_sequence['won'] + (result['won'] * step)
                        new_lost = current_sequence['lost'] + (result['lost'] * step)
                        # la frecuencia nunca baja de cero
                        values_to_update[current_sequence['frequency_id']] = {
                            'won_count': new_won if new_won > 0 else 0.1,
                            'lost_count': new_lost if new_lost > 0 else 0.1,
                        }
                        continue
                    # frecuencia nueva. El 0.1 esquiva la frecuencia cero;
                    # debería ser 1, pero pesa demasiado con pocos registros.
                    values_to_create.append(CrmLeadScoringFrequency(
                        variable=field,
                        value=param,
                        won_count=result['won'] + 0.1,
                        lost_count=result['lost'] + 0.1,
                        team_id_id=team_id or None,
                    ))

        for frequency_id, values in values_to_update.items():
            CrmLeadScoringFrequency.objects.filter(pk=frequency_id).update(**values)
        if values_to_create:
            CrmLeadScoringFrequency.objects.bulk_create(values_to_create)

    # Utility Tools for PLS — config
    # ---------------------

    @classmethod
    def _pls_get_safe_start_date(cls):
        """≙ ``_pls_get_safe_start_date`` (:2635-2644).

        El parámetro de configuración no admite un campo Date, así que se lee la
        cadena y se valida que sea una fecha antes de usarla en la consulta —
        que es lo que la protege de una inyección.
        """
        str_date = SystemParameter.get_param('crm.pls_start_date')
        if not str_date:
            return False
        try:
            return datetime.strptime(str_date[:10], '%Y-%m-%d').date()
        except (TypeError, ValueError):
            return False

    @classmethod
    def _pls_get_safe_fields(cls):
        """≙ ``_pls_get_safe_fields`` (:2646-2655).

        Misma guarda que el anterior: sólo se devuelven los nombres que el
        modelo declara de verdad.
        """
        raw = SystemParameter.get_param('crm.pls_fields')
        requested = raw.split(',') if raw else []
        return [f for f in requested if cls._has_field(f)]

    # Compute Automated Probability Tools
    # -----------------------------------

    @classmethod
    def _pls_get_won_lost_total_count(cls, team_results):
        """≙ ``_pls_get_won_lost_total_count`` (:2658-2673).

        La primera etapa basta para conocer el total: las ganadas son iguales en
        todas las etapas, y la primera siempre se incrementa en las perdidas.
        """
        first_stage = CrmStage.objects.filter(team_ids__isnull=True).order_by(
            'sequence', 'pk').first()
        if first_stage is None or str(first_stage.pk) not in team_results.get('stage_id', {}):
            return 0, 0, 0
        stage_result = team_results['stage_id'][str(first_stage.pk)]
        return stage_result['won'], stage_result['lost'], \
            stage_result['won'] + stage_result['lost']

    # PLS: Rebuild Frequency Table Tools
    # ----------------------------------

    @classmethod
    def _pls_prepare_frequencies(cls, lead_values, leads_pls_fields, target_state=None):
        """≙ ``_pls_prepare_frequencies`` (:2675-2716).

        ``target_state`` se usa para las que están **cambiando** a ganada o
        perdida; queda en ``None`` cuando ya lo estaban.
        """
        pls_fields = list(leads_pls_fields)
        frequencies = {field: {} for field in pls_fields}

        stages = list(CrmStage.objects.order_by('sequence', 'pk')
                      .values('pk', 'sequence', 'name'))
        stage_sequences = {s['pk']: s['sequence'] for s in stages}

        for values in lead_values:
            if target_state:
                # con estado destino se ignora la probabilidad: es la vieja
                won_count = values['count'] if target_state == 'won' else 0
                lost_count = values['count'] if target_state == 'lost' else 0
            else:
                won_count = values['count'] if values.get('probability', 0) == 100 else 0
                lost_count = values['count'] if values.get('probability', 1) == 0 else 0

            if 'tag_id' in values:
                frequencies = cls._pls_increment_frequency_dict(
                    frequencies, 'tag_id', values['tag_id'], won_count, lost_count)
                continue

            other_fields = [f for f in pls_fields if f != 'tag_id']   # ya tratado arriba
            for field in other_fields:
                if field not in values:
                    continue
                value = values[field]
                if not (value or field in ('email_state', 'phone_state')):
                    continue
                if field == 'stage_id':
                    if won_count:   # ganada: sube en todas las etapas
                        stages_to_increment = [s['pk'] for s in stages]
                    else:           # perdida: sólo la actual y las anteriores
                        current_sequence = stage_sequences.get(value, 0)
                        stages_to_increment = [s['pk'] for s in stages
                                         if s['sequence'] <= current_sequence]
                    for stage_id in stages_to_increment:
                        frequencies = cls._pls_increment_frequency_dict(
                            frequencies, field, stage_id, won_count, lost_count)
                else:
                    frequencies = cls._pls_increment_frequency_dict(
                        frequencies, field, value, won_count, lost_count)
        return frequencies

    @classmethod
    def _pls_increment_frequency_dict(cls, frequencies, field, value, won, lost):
        """≙ ``_pls_increment_frequency_dict`` (:2718-2726)."""
        value = str(value)   # siempre se comparan cadenas
        if value not in frequencies[field]:
            frequencies[field][value] = {'won': won, 'lost': lost}
        else:
            frequencies[field][value]['won'] += won
            frequencies[field][value]['lost'] += lost
        return frequencies

    # Common PLS Tools
    # ----------------

    @classmethod
    def _pls_get_lead_pls_values(cls, leads, criterion=None):
        """≙ ``_pls_get_lead_pls_values`` (:2729-2811).

        Construye, por iniciativa, la lista de pares (campo, valor).

        La fuente ofrece dos caminos: con dominio hace dos consultas SQL que
        esquivan el ORM (una para las etiquetas, otra para el resto) porque en
        el cron hay que evitar leer dentro del bucle; sin dominio va registro a
        registro. Los dos se conservan: ``criterio`` es el dominio.

        :return: ``{lead_id: {'values': [(campo, valor), …], 'team_id': N}}``
        """
        leads_values_dict = OrderedDict()
        pls_fields = ['stage_id', 'team_id'] + cls._pls_get_safe_fields()

        # las etiquetas se tratan aparte
        use_tags = 'tag_ids' in pls_fields
        if use_tags:
            pls_fields.remove('tag_ids')

        columns = [f if not cls._is_relational(f) else f'{f}_id' for f in pls_fields]

        if criterion is not None:
            rows = list(cls.objects.filter(criterion)
                         .order_by('team_id', '-pk')
                         .values('pk', 'probability', *columns))
            for fila in rows:
                lead_values = []
                for field, columna in zip(pls_fields + ['probability'],
                                          columns + ['probability']):
                    if field == 'team_id':
                        continue    # va aparte, en la clave team_id
                    value = fila[columna]
                    if value or field == 'probability':
                        lead_values.append((field, value))
                    elif field in ('email_state', 'phone_state'):
                        # el ORM lee None como False; aquí igual
                        lead_values.append((field, False))
                leads_values_dict[fila['pk']] = {
                    'values': lead_values, 'team_id': fila['team_id'] or 0}

            if use_tags:
                for lead_id, tag_id in cls.objects.filter(criterion).filter(
                    tag_ids__isnull=False
                ).values_list('pk', 'tag_ids'):
                    if tag_id and lead_id in leads_values_dict:
                        leads_values_dict[lead_id]['values'].append(('tag_id', tag_id))
            return leads_values_dict

        for lead in leads:
            lead_values = []
            for field, columna in zip(pls_fields, columns):
                if field == 'team_id':
                    continue
                value = getattr(lead, columna, None)
                if value or field in ('email_state', 'phone_state'):
                    lead_values.append((field, value))
            if use_tags:
                for tag in lead.tag_ids.all():
                    lead_values.append(('tag_id', tag.pk))
            leads_values_dict[lead.pk] = {
                'values': lead_values, 'team_id': lead.team_id_id or 0}
        return leads_values_dict

    @classmethod
    def _is_relational(cls, name_value):
        """Auxiliar del stack: ¿el campo es una FK, y por tanto su columna
        lleva el sufijo ``_id`` de Django?

        Sin contraparte de un símbolo en la fuente: allá ``lead[field]`` da el
        recordset o el valor según el tipo, sin que el llamador lo distinga.
        """
        try:
            return cls._meta.get_field(name_value).is_relation
        except Exception:
            return False

    # PLS Backend Tooltip
    # -------------------

    def prepare_pls_tooltip_data(self):
        """≙ ``prepare_pls_tooltip_data`` (:2813-2890).

        Lo que pinta el globo del botón de scoring: sustituye ids por nombres,
        recalcula la probabilidad y la escribe, y devuelve los tres criterios
        que más suman y los tres que más restan.

        :returns: ``{low_3_data, probability, team_name, top_3_data}``
        """
        _unused, tooltip_data = type(self)._pls_get_naive_bayes_probabilities(
            [self], is_tooltip=True)
        sorted_scores_with_name = []

        # el globo muestra nombres, no ids. El último elemento del trío es sólo
        # para que la etiqueta conserve su color.
        for score, field, value in sorted(tooltip_data['scores']):
            # resultados sin sentido de calidad de teléfono y correo: pasan con
            # bases pequeñas
            if field in ('phone_state', 'email_state'):
                if value in (False, 'incorrect') and round(score, 2) > 0.50:
                    continue
                if value == 'correct' and round(score, 2) < 0.50:
                    continue
            if field == 'tag_id':
                tag = self.tag_ids.filter(pk=value).first()
                sorted_scores_with_name.append(
                    (score, field, tag.name if tag else str(value),
                     tag.color if tag else False))
            elif self._is_relational(field):
                related_record = getattr(self, field, None)
                sorted_scores_with_name.append(
                    (score, field, str(related_record) if related_record else '', False))
            else:
                sorted_scores_with_name.append((score, field, str(value), False))

        # la automática pudo cambiar desde el último cálculo; se alinea para que
        # el globo y el registro no muestren cifras distintas
        self.automated_probability = tooltip_data['probability']
        if self.is_automated_probability:
            self.probability = tooltip_data['probability']
        self.save(update_fields=['automated_probability', 'probability'])

        # si no se pudo calcular (probabilidad 0.00) se usan valores de muestra
        if round(tooltip_data['probability'], 2) == 0:
            sorted_scores_with_name = [
                (.1, 'email_state', False, False),
                (.2, 'tag_id', _('Exploration'), 4),
                (.3, 'stage_id', _('New'), False),
                (.7, 'phone_state', 'correct', False),
                (.8, 'country_id', _('Belgium'), False),
                (.9, 'tag_id', _('Consulting'), 3),
            ]

        return {
            'low_3_data': [
                {'field': e[1], 'value': e[2], 'color': e[3]}
                for e in sorted_scores_with_name[:3] if round(e[0], 2) < 0.50
            ],
            'probability': tooltip_data['probability'],
            'team_name': self.team_id.name if self.team_id_id else '',
            'top_3_data': [
                {'field': e[1], 'value': e[2], 'color': e[3]}
                for e in sorted_scores_with_name[::-1][:3] if round(e[0], 2) > 0.50
            ],
        }
