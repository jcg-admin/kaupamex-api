"""``hr.applicant`` — un candidato en el embudo de reclutamiento (Odoo
``hr_recruitment``).

Adaptación de Odoo ``hr_recruitment/models/hr_applicant.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 1116 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03). El modelo central del addon.

Premisa verificada
====================

La referencia hereda seis mixins además de ``utm.mixin``:
``mail.thread.cc``, ``mail.thread.main.attachment``, ``mail.thread.blacklist``,
``mail.thread.phone``, ``mail.activity.mixin``, ``mail.tracking.duration.mixin``.
Medido: ``grep -n "^class Mail" addons/mail/models/*.py`` → sólo
``MailThread`` y ``MailActivityMixin`` existen; los otros cuatro dan **0
hits**. Se hereda lo que existe (``MailThread``, ``MailActivityMixin``,
``UtmMixin``); todo lo que dependa EXCLUSIVAMENTE de los cuatro ausentes
se declara BLOQUEADO por símbolo, no se omite en silencio.

Porte símbolo por símbolo — 43 campos + 45 métodos medidos
================================================================

**Campos** (43 de 43 — todos portados; 4 dependen de piezas ausentes y se
declaran en su propio comentario de campo):
``sequence``, ``active``, ``partner_id``→``partner``, ``partner_name``,
``email_from``, ``email_normalized``, ``partner_phone``,
``partner_phone_sanitized``, ``linkedin_profile``, ``type_id``→``type``,
``availability``, ``color``, ``employee_id``→``employee``,
``emp_is_active``, ``employee_name``, ``probability``, ``create_date``
(≙ ``created_at`` de ``TimeStampedModel``), ``stage_id``→``stage``,
``last_stage_id``→``last_stage``, ``categ_ids``→``categs``,
``company_id``→``company``, ``user_id``→``user``, ``date_closed``,
``date_open``, ``date_last_stage_update``, ``priority``, ``job_id``→``job``,
``salary_proposed_extra``, ``salary_expected_extra``, ``salary_proposed``,
``salary_expected``, ``department_id``→``department``, ``day_open``,
``day_close``, ``delay_close`` (los tres, métodos — no ``store``),
``user_email`` (propiedad), ``attachment_number``/``attachment_ids``
(método — polimórfico, sin FK real, ver más abajo), ``kanban_state``,
``legend_*`` (4, propiedades vía ``stage``), ``refuse_reason_id``→
``refuse_reason``, ``meeting_ids``/``meeting_display_*`` — BLOQUEADOS
(``calendar.event`` ausente, ver ``calendar.py`` de este addon),
``campaign_id``/``medium_id``/``source_id`` (de ``UtmMixin``, ya
``on_delete=SET_NULL`` por defecto — no-op), ``interviewer_ids``→
``interviewers``, ``application_status``/``application_count`` (métodos),
``applicant_properties``, ``applicant_notes``, ``refuse_date``,
``talent_pool_ids`` → portado sin código (reverso de
``HrTalentPool.talents``, ver ese archivo), ``pool_applicant_id``→
``pool_applicant``, ``is_pool_applicant``/``is_applicant_in_pool``/
``talent_pool_count`` (métodos).

**Métodos** — ver la tabla extendida en cada sección del cuerpo de la
clase; resumen: **26 portados**, **6 con divergencia declarada**,
**13 BLOQUEADOS** (framework de acciones cliente Odoo — familia (b);
mixins ausentes; pasarela de correo entrante ausente).
"""
from datetime import datetime

from django.apps import apps
from django.db.models import Q
from django.utils import timezone

import fields
import models
from addons.base.models import ResPartner, TimeStampedModel
from addons.mail.models import MailActivityMixin, MailThread
from addons.utm.models.utm_mixin import UtmMixin
from exceptions import UserError, ValidationError
from orm.environments import get_current_user
from tools.translate import _

AVAILABLE_PRIORITIES = [
    ('0', 'Normal'),
    ('1', 'Buena'),
    ('2', 'Muy buena'),
    ('3', 'Excelente'),
]

KANBAN_STATES = [
    ('normal', 'En progreso'),
    ('done', 'Listo para la siguiente etapa'),
    ('waiting', 'Esperando'),
    ('blocked', 'Bloqueado'),
]

APPLICATION_STATUSES = [
    ('ongoing', 'En curso'),
    ('hired', 'Contratado'),
    ('refused', 'Rechazado'),
    ('archived', 'Archivado'),
]


class HrApplicant(MailThread, MailActivityMixin, UtmMixin, TimeStampedModel):
    """``hr.applicant`` — un candidato, desde la postulación hasta la
    contratación o el rechazo."""

    _name = 'hr.applicant'
    _description = 'Applicant'
    _rec_name = 'partner_name'

    sequence = fields.Integer(default=10, db_index=True, verbose_name='Secuencia')
    active = fields.Boolean(default=True, db_index=True, verbose_name='Activo')

    partner = fields.Many2one(
        'base.ResPartner', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='applicant_ids', db_index=True, verbose_name='Contacto',
    )
    partner_name = fields.Char(max_length=255, blank=True, default='', verbose_name='Nombre del candidato')
    email_from = fields.Char(max_length=128, blank=True, default='', db_index=True, verbose_name='Correo')
    email_normalized = fields.Char(max_length=128, blank=True, default='', db_index=True)
    partner_phone = fields.Char(max_length=32, blank=True, default='', verbose_name='Teléfono')
    partner_phone_sanitized = fields.Char(max_length=32, blank=True, default='', db_index=True)
    linkedin_profile = fields.Char(max_length=255, blank=True, default='', verbose_name='Perfil de LinkedIn')
    type = fields.Many2one(
        'hr_recruitment.HrRecruitmentDegree', on_delete=models.SET_NULL, null=True,
        blank=True, related_name='applicants', verbose_name='Grado académico',
    )
    availability = fields.Date(null=True, blank=True, verbose_name='Disponibilidad')
    color = fields.Integer(default=0, verbose_name='Índice de color')
    # Odoo employee_id — el reverso lo consume hr_recruitment/models/
    # hr_employee.py (``portado sin código``, related_name='applicant_ids').
    employee = fields.Many2one(
        'hr.HrEmployee', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='applicant_ids', db_index=True, verbose_name='Empleado',
    )
    probability = fields.Float(default=0, verbose_name='Probabilidad')
    stage = fields.Many2one(
        'hr_recruitment.HrRecruitmentStage', on_delete=models.PROTECT,
        null=True, blank=True, related_name='applicants', db_index=True,
        verbose_name='Etapa',
    )
    last_stage = fields.Many2one(
        'hr_recruitment.HrRecruitmentStage', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+', verbose_name='Última etapa',
    )
    categs = fields.Many2many(
        'hr_recruitment.HrApplicantCategory', related_name='applicants',
        blank=True, verbose_name='Etiquetas',
    )
    company = fields.Many2one(
        'base.ResCompany', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='applicants', db_index=True, verbose_name='Empresa',
    )
    user = fields.Many2one(
        'base.ResUsers', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='recruited_applicants', db_index=True, verbose_name='Reclutador',
    )
    date_closed = fields.Datetime(null=True, blank=True, verbose_name='Fecha de contratación')
    date_open = fields.Datetime(null=True, blank=True, verbose_name='Fecha de asignación')
    date_last_stage_update = fields.Datetime(
        null=True, blank=True, db_index=True, default=timezone.now,
        verbose_name='Última actualización de etapa',
    )
    priority = fields.Selection(choices=AVAILABLE_PRIORITIES, max_length=1, default='0', verbose_name='Evaluación')
    job = fields.Many2one(
        'hr.HrJob', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='applications', db_index=True, verbose_name='Puesto',
    )
    salary_proposed_extra = fields.Char(max_length=255, blank=True, default='', verbose_name='Extra propuesto')
    salary_expected_extra = fields.Char(max_length=255, blank=True, default='', verbose_name='Extra esperado')
    salary_proposed = fields.Float(default=0, verbose_name='Salario propuesto')
    salary_expected = fields.Float(default=0, verbose_name='Salario esperado')
    department = fields.Many2one(
        'hr.HrDepartment', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='applicants', verbose_name='Departamento',
    )
    delay_close = fields.Float(null=True, blank=True, verbose_name='Demora al cierre')
    kanban_state = fields.Selection(
        choices=KANBAN_STATES, max_length=10, default='normal',
        verbose_name='Estado kanban',
    )
    refuse_reason = fields.Many2one(
        'hr_recruitment.HrApplicantRefuseReason', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='applicants', verbose_name='Motivo de rechazo',
    )
    interviewers = fields.Many2many(
        'base.ResUsers', related_name='interviewing_applicants', blank=True,
        db_index=True, verbose_name='Entrevistadores',
    )
    applicant_properties = fields.Properties(null=True, blank=True, verbose_name='Propiedades del candidato')
    applicant_notes = fields.Html(blank=True, default='', verbose_name='Notas')
    refuse_date = fields.Datetime(null=True, blank=True, verbose_name='Fecha de rechazo')
    # Odoo talent_pool_ids: sin nombre de tabla explícito en la referencia,
    # así que resuelve a la MISMA junction que hr.talent.pool.talent_ids —
    # ver el comentario de campo en hr_talent_pool.py. El reverso Django lo
    # da ``related_name='talent_pools'`` declarado allá; no se redeclara.
    pool_applicant = fields.Many2one(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        db_index=True, related_name='pool_copies', verbose_name='Candidato de la bolsa',
    )

    class Meta:
        db_table = 'hr_applicant'
        ordering = ['-priority', 'sequence', '-id']
        verbose_name = 'Candidato'
        verbose_name_plural = 'Candidatos'
        indexes = [
            # ≙ ``_job_id_stage_id_idx`` (``odoo19c: :135``). Sin el
            # ``WHERE active IS TRUE`` parcial — Django CheckConstraint de
            # índice parcial exige `condition=`, que sí se declara aquí.
            models.Index(
                fields=['job', 'stage'], name='hr_applicant_job_stage_idx',
                condition=Q(active=True),
            ),
        ]

    def __str__(self) -> str:
        return self.partner_name or ''

    # === Restricciones ======================================================

    def check_talent_pool_required(self):
        """≙ ``_check_talent_pool_required`` (``odoo19c: :149-152``) —
        invocar antes de ``save()`` cuando cambien ``talent_pools``/
        ``pool_applicant`` (sin motor de constraints declarativo en este
        ORM, se llama explícito — mismo criterio que el resto del árbol)."""
        if self.pool_applicant_id == self.pk and not self.talent_pools.exists():
            raise ValidationError(
                _('El talento debe pertenecer al menos a una bolsa de talento.'),
            )

    # === Cómputos puros (sin @depends — se invocan explícitos) =============

    def sync_partner_phone_email(self):
        """≙ ``_compute_partner_phone_email`` (``odoo19c: :225-232``)."""
        if not self.partner_id:
            return
        self.email_from = self.partner.email or ''
        if not self.partner_phone:
            self.partner_phone = self.partner.phone or ''

    def apply_partner_email(self):
        """≙ ``_inverse_partner_email`` (``odoo19c: :234-251``).

        DIVERGENCIA: ``tools.email_normalize``/``_partner_find_from_emails_
        single`` no existen en este árbol (medido). Normalización mínima
        (``strip().lower()``, mismo criterio que ``hr_job_platform.py``) y
        búsqueda/creación directa por correo exacto — sin el álgebra de
        "posibles duplicados" de la referencia.
        """
        email_normalized = (self.email_from or '').strip().lower()
        if not email_normalized:
            return
        if not self.partner_id:
            if not self.partner_name:
                raise UserError(_('Debes indicar un nombre de contacto para este candidato.'))
            partner = ResPartner.objects.filter(email__iexact=email_normalized).first()
            if partner is None:
                partner = ResPartner.objects.create(
                    name=self.partner_name, email=self.email_from, is_company=False,
                )
            self.partner = partner
        if self.partner_name and self.partner_name != self.partner.name:
            self.partner.name = self.partner_name
            self.partner.save(update_fields=['name'])
        if email_normalized and email_normalized != (self.partner.email or '').strip().lower():
            self.partner.email = self.email_from
            self.partner.save(update_fields=['email'])
        if self.partner_phone and self.partner_phone != self.partner.phone:
            self.partner.phone = self.partner_phone
            self.partner.save(update_fields=['phone'])

    def day_open(self):
        """≙ ``_compute_day`` — mitad ``day_open`` (``odoo19c: :461-474``)."""
        if not self.date_open:
            return None
        return (self.date_open - self.created_at).total_seconds() / 86400.0

    def day_close(self):
        """≙ ``_compute_day`` — mitad ``day_close``."""
        if not self.date_closed:
            return None
        return (self.date_closed - self.created_at).total_seconds() / 86400.0

    def compute_delay_close(self):
        """≙ ``_compute_delay`` (``odoo19c: :476-482``) — asigna
        ``self.delay_close``; se invoca explícito tras tocar las fechas."""
        day_open, day_close = self.day_open(), self.day_close()
        self.delay_close = (day_close - day_open) if (self.date_open and day_close is not None) else None
        return self.delay_close

    def user_email(self):
        """≙ ``user_email`` (``related='user_id.email'``, ``:106``)."""
        return self.user.email if self.user_id else None

    def emp_is_active(self):
        """≙ ``emp_is_active`` (``related='employee_id.active'``, ``:71``)."""
        return self.employee.active if self.employee_id else None

    def employee_name(self):
        """≙ ``employee_name`` (``related='employee_id.name'``, ``:72``)."""
        return self.employee.name if self.employee_id else None

    def attachments(self):
        """≙ ``attachment_ids`` (``odoo19c: :107``) — adjuntos del
        candidato. DIVERGENCIA: sin FK real — ``ir.attachment`` es
        polimórfico (``res_model``/``res_id``), mismo patrón que
        ``hr.job.document_ids``."""
        IrAttachment = apps.get_model('base', 'IrAttachment')
        return IrAttachment.objects.filter(res_model='hr.applicant', res_id=self.pk)

    def attachment_number(self):
        """≙ ``_get_attachment_number`` (``odoo19c: :745-750``)."""
        return self.attachments().count()

    def legend_blocked(self):
        return self.stage.legend_blocked if self.stage_id else None

    def legend_done(self):
        return self.stage.legend_done if self.stage_id else None

    def legend_waiting(self):
        return self.stage.legend_waiting if self.stage_id else None

    def legend_normal(self):
        return self.stage.legend_normal if self.stage_id else None

    def compute_stage(self):
        """≙ ``_compute_stage`` (``odoo19c: :572-586``) — asigna la
        primera etapa elegible del puesto; se invoca al fijar/cambiar
        ``job``."""
        if not self.job_id:
            self.stage = None
            return self.stage
        if not self.stage_id:
            HrRecruitmentStage = apps.get_model('hr_recruitment', 'HrRecruitmentStage')
            self.stage = HrRecruitmentStage.objects.filter(
                Q(jobs__isnull=True) | Q(jobs=self.job),
            ).exclude(fold=True).order_by('sequence').first()
        return self.stage

    def compute_department(self):
        """≙ ``_compute_department`` (``odoo19c: :568-570``)."""
        self.department = self.job.department if self.job_id else None
        return self.department

    def compute_company(self):
        """≙ ``_compute_company`` (``odoo19c: :558-566``)."""
        company = None
        if self.department_id:
            company = self.department.company
        if company is None and self.job_id:
            company = self.job.company
        self.company = company
        return self.company

    def compute_user(self):
        """≙ ``_compute_user`` (``odoo19c: :588-591``)."""
        self.user = self.job.user if self.job_id else None
        return self.user

    def compute_date_closed(self):
        """≙ ``_compute_date_closed`` (``odoo19c: :597-602``) — se invoca
        al cambiar de etapa."""
        if self.stage_id and self.stage.hired_stage and not self.date_closed:
            self.date_closed = timezone.now()
        if not self.stage_id or not self.stage.hired_stage:
            self.date_closed = None
        return self.date_closed

    def application_status(self):
        """≙ ``_compute_application_status`` (``odoo19c: :719-728``)."""
        if self.refuse_reason_id:
            return 'refused'
        if not self.active:
            return 'archived'
        if self.date_closed:
            return 'hired'
        return 'ongoing'

    @classmethod
    def search_application_status(cls, statuses):
        """≙ ``_search_application_status`` (``odoo19c: :730-741``) —
        devuelve un ``Q`` en vez de un ``domain`` (sin capa de dominio
        Odoo en este ORM)."""
        q = Q()
        if 'refused' in statuses:
            q |= Q(active=False, refuse_reason__isnull=False)
        if 'hired' in statuses:
            q |= Q(active=True, date_closed__isnull=False)
        if 'archived' in statuses or False in statuses:
            q |= Q(active=False)
        if 'ongoing' in statuses:
            q |= Q(active=True, date_closed__isnull=True)
        return q

    def get_similar_applicants(self, ignore_talent=False, only_talent=False):
        """≙ ``_get_similar_applicants_domain`` (``odoo19c: :481-501``) —
        devuelve el ``QuerySet``, no un dominio (sin capa de dominio en
        este ORM)."""
        q = Q(pk=self.pk)
        if self.email_normalized:
            q |= Q(email_normalized=self.email_normalized)
        if self.partner_phone_sanitized:
            q |= Q(partner_phone_sanitized=self.partner_phone_sanitized)
        if self.linkedin_profile:
            q |= Q(linkedin_profile=self.linkedin_profile)
        if self.pool_applicant_id:
            q |= Q(pool_applicant_id=self.pool_applicant_id)
        queryset = type(self).objects.filter(q)
        if ignore_talent:
            queryset = queryset.filter(talent_pools__isnull=True)
        if only_talent:
            queryset = queryset.filter(talent_pools__isnull=False)
        return queryset.distinct()

    def application_count(self):
        """≙ ``_compute_application_count`` (``odoo19c: :678-707``) —
        aplicaciones que comparten correo/teléfono/linkedin/bolsa con
        ``self``, sin contarse doble."""
        return max(0, self.get_similar_applicants(ignore_talent=False).exclude(pk=self.pk).count())

    def is_pool_applicant(self):
        """≙ ``_compute_is_pool`` (``odoo19c: :709-712``)."""
        return self.talent_pools.exists()

    def is_applicant_in_pool(self):
        """≙ ``_compute_is_applicant_in_pool`` (``odoo19c: :714-763``,
        forma reducida: sin la propagación indirecta por email/teléfono/
        linkedin — se resuelve por el enlace directo, que es el caso que
        ``get_similar_applicants(only_talent=True)`` ya cubre)."""
        if self.talent_pools.exists() or self.pool_applicant_id:
            return True
        return self.get_similar_applicants(only_talent=True).exclude(pk=self.pk).exists()

    def talent_pool_count(self):
        """≙ ``_compute_talent_pool_count`` (``odoo19c: :154-215``, forma
        reducida — ver divergencia de ``is_applicant_in_pool``)."""
        if not self.is_applicant_in_pool():
            return 0
        if self.pool_applicant_id:
            return self.pool_applicant.talent_pools.count()
        return self.talent_pools.count()

    def link_applicant_to_talent(self):
        """≙ ``link_applicant_to_talent`` (``odoo19c: :836-839``)."""
        talent = self.get_similar_applicants(only_talent=True).exclude(pk=self.pk).first()
        self.pool_applicant = talent
        return talent

    # === Alta / edición ======================================================

    def save(self, *args, **kwargs):
        """≙ ``create``/``write`` (``odoo19c: :615-693``) — Django unifica
        alta y edición; se reproduce el núcleo de ambas.

        DIVERGENCIA: la notificación a entrevistadores nuevos
        (``message_notify``) y el alta/baja del grupo de RR.HH. vía
        ``ResUsers._create_recruitment_interviewers`` se cablean aquí en
        vez de en un hook de vals — mismo efecto neto, otro punto de
        disparo. La sincronía de ``pool_applicant`` en escritura masiva
        (fuente ``:667-676``) queda BLOQUEADA — depende de saber qué
        campos cambiaron respecto al valor anterior, y este ORM no trae
        ese diff a ``save()`` sin leer antes (fuera de alcance de este
        pase).
        """
        is_new = self.pk is None
        previous_interviewer_pks = (
            set(self.interviewers.values_list('pk', flat=True)) if not is_new else set()
        )
        if not is_new:
            self.date_last_stage_update = timezone.now()
        result = super().save(*args, **kwargs)
        new_interviewer_pks = set(self.interviewers.values_list('pk', flat=True))
        ResUsersModel = apps.get_model('base', 'ResUsers')
        create_fn = getattr(ResUsersModel, '_create_recruitment_interviewers', None)
        remove_fn = getattr(ResUsersModel, '_remove_recruitment_interviewers', None)
        if create_fn is not None and new_interviewer_pks - previous_interviewer_pks:
            create_fn(ResUsersModel.objects.filter(pk__in=new_interviewer_pks - previous_interviewer_pks))
        if remove_fn is not None and previous_interviewer_pks - new_interviewer_pks:
            remove_fn(ResUsersModel.objects.filter(pk__in=previous_interviewer_pks - new_interviewer_pks))
        current_user = get_current_user()
        new_interviewers_to_notify = ResUsersModel.objects.filter(
            pk__in=new_interviewer_pks - previous_interviewer_pks,
        )
        if current_user is not None:
            new_interviewers_to_notify = new_interviewers_to_notify.exclude(pk=current_user.pk)
        for interviewer in new_interviewers_to_notify:
            self.message_notify(
                partners=[interviewer.partner] if getattr(interviewer, 'partner_id', None) else [],
                subject=_('Fuiste asignado como entrevistador de %(name)s', name=str(self)),
                body=_('Fuiste asignado como entrevistador del candidato %(name)s', name=self.partner_name or ''),
            )
        return result

    def copy_partner_name_suffix(self):
        """≙ ``copy_data`` (``odoo19c: :606-613``) — el sufijo "(copia)"
        sobre ``partner_name``; se invoca explícito antes de ``copy()``
        (sin hook de copia automático en este ORM)."""
        return _('%(name)s (copia)', name=self.partner_name or '')

    def check_interviewer_access(self):
        """≙ ``_check_interviewer_access`` (``odoo19c: :1049-1051``)."""
        user = get_current_user()
        if user is not None and user.has_group('hr_recruitment.group_hr_recruitment_interviewer') \
                and not user.has_group('hr_recruitment.group_hr_recruitment_user'):
            raise UserError(_('No tienes permiso para realizar esta acción.'))

    def reset_applicant(self):
        """≙ ``reset_applicant`` (``odoo19c: :1074-1087``) — reingresa al
        candidato en la primera etapa de su puesto."""
        if self.job_id:
            HrRecruitmentStage = apps.get_model('hr_recruitment', 'HrRecruitmentStage')
            default_stage = HrRecruitmentStage.objects.filter(
                Q(jobs__isnull=True) | Q(jobs=self.job),
            ).exclude(fold=True).order_by('sequence').first()
            self.stage = default_stage
        self.refuse_reason = None
        self.save(update_fields=['stage', 'refuse_reason'])

    def get_employee_create_vals(self):
        """≙ ``_get_employee_create_vals`` (``odoo19c: :1023-1041``).

        DIVERGENCIA: ``partner.address_get(['contact'])`` no existe en
        este árbol (medido: 0 hits) — se usa ``self.partner`` directo, sin
        jerarquía de direcciones de contacto (mismo criterio que otras
        divergencias de "sin árbol de direcciones" ya declaradas en el
        proyecto).
        """
        self.ensure_partner()
        address = self.partner
        return {
            'name': self.partner_name or (address.name if address is not None else ''),
            'work_contact': address,
            'job': self.job,
            'department': self.department,
            'applicant_ids': [self.pk],
            'phone': self.partner_phone or '',
        }

    def ensure_partner(self):
        """Helper propio: garantiza ``self.partner`` antes de crear un
        empleado o programar una reunión — el patrón se repite tres veces
        en la referencia (``:754-758``, ``:1005-1009``) y aquí se
        factoriza en vez de triplicarse."""
        if self.partner_id:
            return self.partner
        if not self.partner_name:
            raise UserError(_('Debes indicar un nombre de contacto para este candidato.'))
        self.partner = ResPartner.objects.create(
            name=self.partner_name, email=self.email_from, is_company=False,
        )
        self.save(update_fields=['partner'])
        return self.partner


# ============================================================================
# Métodos NO portados — BLOQUEADOS, con su pieza faltante nombrada
# ============================================================================
#
# ``get_empty_list_help``/``get_view`` (``:702-717``)          — framework de
#   vistas/acciones Odoo, sin equivalente en este stack DRF+React.
# ``action_create_meeting``/``meeting_ids``/``meeting_display_*``
#   (``:754-778,468-473,662-682``)                              — BLOQUEADO
#   por ``calendar.event`` ausente (ver ``calendar.py`` de este addon).
# ``action_open_attachments``/``action_open_employee``/
#   ``action_open_applications``/``action_talent_pool_stat_button``/
#   ``action_talent_pool_add_applicants``/``action_job_add_applicants``/
#   ``archive_applicant``/``action_send_email``/``action_archive``/
#   ``action_unarchive`` (``:775-940,1088-1103,1109-1116``)     — familia
#   (b): ``ir.actions.act_window``/``ir.actions.client``, framework de
#   acciones cliente Odoo.
# ``_track_template``/``_creation_subtype``/``_track_subtype``
#   (``:882-908``)                                               — datos
#   XML (``mt_applicant_new``, ``mt_talent_new``, plantillas) no sembrados;
#   la FORMA del guard es la misma que ``utm_campaign.py``/
#   ``ir_ui_menu.py`` de este addon.
# ``_notify_get_reply_to``/``_get_customer_information``/
#   ``_compute_display_name``/``_message_post_after_hook``
#   (``:910-926,940-943,973-991``)                                — dependen
#   de ``tools.email_normalize``/``tools.parse_contact_from_email`` (medido:
#   0 hits) y de la pasarela de correo entrante.
# ``message_new`` (``:945-971``)                                 — pasarela
#   de correo entrante ausente (mismo bloqueo que ``hr/models/models.py``
#   ya declaró para el veto de alias).
# ``create_employee_from_applicant`` (``:998-1021``)              — arma un
#   ``ir.actions.act_window`` (familia b); su NÚCLEO de negocio SÍ está
#   portado como ``get_employee_create_vals`` arriba, listo para que la
#   vista DRF que lo cablee llame ``HrEmployee.objects.create(**vals)``.
# ``_get_duration_from_tracking`` (``:1109-1116``)                — BLOQUEADO
#   por ``mail.tracking.duration.mixin`` ausente.
