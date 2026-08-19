"""``hr.job`` — lo que ``hr_recruitment`` le cuelga al puesto (Odoo
``hr_recruitment``).

Adaptación de Odoo ``hr_recruitment/models/hr_job.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 420 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03). La referencia declara
``_name = 'hr.job'`` con ``_inherit = ["mail.alias.mixin", "hr.job",
"mail.activity.mixin"]`` — es una EXTENSIÓN del ``hr.job`` ya portado en
``addons.hr`` (que declara ``name``, ``department``, ``company``,
``no_of_recruitment``, ``description``, ``requirements``, ``user``,
``active`` — esos símbolos ya existen y no se re-declaran).

``_inherit`` lo expresa ``extend_model('hr', 'HrJob', …)`` — par de Django
porque ``hr.HrJob`` no declara ``_name`` propio en este árbol.

Porte símbolo por símbolo — 27 de 43 medidos, 16 BLOQUEADOS
================================================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``requirements``/``user_id`` (``:35-36``)
     - ya existente en ``hr.HrJob`` (``requirements``/``user``) — no-op
   * - ``expected_employees``/``no_of_employee`` (``:33-34``)
     - portados — columnas nuevas
   * - ``address_id`` (``:38-41``)
     - portado (sin ``domain=``/``default=`` dinámico de formulario)
   * - ``application_ids``…``old_application_count`` (7 campos+computes,
       ``:42-52,175-272``)
     - portados
   * - ``manager_id`` (``:54-56``)
     - BLOQUEADO — ``related='department_id.manager_id'``;
       ``hr.HrDepartment.manager`` sigue DEFERIDO (fuera de este write-set)
   * - ``document_ids``/``documents_count``/``_compute_document_ids``
       (``:57-58,157-173``)
     - portados
   * - ``employee_count``/``_compute_employee_count`` (``:59,202-215``)
     - portado (divergencia: sin acotar por empresa — ``HrEmployee`` no
       declara FK directa a ``company`` en este árbol, medido)
   * - ``alias_id``/``_alias_get_creation_values`` (``:60,274-285``)
     - BLOQUEADOS — ``mail.alias.mixin`` ausente (mismo bloqueo que
       ``hr_recruitment_source.py``)
   * - ``color``/``is_favorite``/``favorite_user_ids``/
       ``_compute_is_favorite``/``_inverse_is_favorite`` (``:61-63,143-155``)
     - portados
   * - ``interviewer_ids`` (``:64-70``)
     - portado
   * - ``extended_interviewer_ids``/``_compute_extended_interviewer_ids``
       (``:71,130-141``)
     - portado (sin ``with_user(SUPERUSER_ID)`` — no hay elevación de
       acceso en este ORM)
   * - ``industry_id`` (``:72``)
     - BLOQUEADO — ``res.partner.industry`` no existe (medido: 0 hits)
   * - ``expected_degree`` (``:73``)
     - portado
   * - ``activity_count``/``_compute_activities`` (``:75,103-128``)
     - portado — traducido a ORM Django (la fuente usa SQL crudo)
   * - ``job_properties``/``applicant_properties_definition`` (``:77,79``)
     - portados — ``fields.Properties``/``PropertiesDefinition`` (``JSONField``)
   * - ``no_of_hired_employee``/``_compute_no_of_hired_employee``
       (``:80-84,88-101``)
     - portado
   * - ``job_source_ids`` (``:86``)
     - portado sin código — reverso automático de
       ``HrRecruitmentSource.job`` (``related_name='recruitment_sources'``)
   * - ``create``/``write`` (``:287-336``)
     - BLOQUEADOS — la única lógica de negocio propia (fuera de la
       sincronía de alias, ya bloqueada) es
       ``ResUsers._create_recruitment_interviewers``/
       ``_remove_recruitment_interviewers`` (``res_users.py`` de este
       addon); su forma pura queda ahí, disponible para cablearla aquí en
       el sucesor que decida el punto exacto de la escritura
   * - ``_order_field_to_sql`` (``:338-346``)
     - BLOQUEADO — ordenamiento SQL de vista de lista; sin consumidor
   * - ``_creation_subtype`` (``:348-349``)
     - BLOQUEADO — dato XML (``mt_job_new``) no sembrado
   * - ``action_open_attachments``/``action_open_activities``/
       ``_action_load_recruitment_scenario``/``action_open_employees``
       (``:351-420``)
     - BLOQUEADOS — familia (b): framework de acciones cliente Odoo
"""
from django.apps import apps
from django.db.models import Q

import fields
import models
from orm.environments import get_current_user
from orm.model_classes import extend_model


def application_count(job):
    """≙ ``_compute_application_count`` (``odoo19c: :187-191``)."""
    HrApplicant = apps.get_model('hr_recruitment', 'HrApplicant')
    return HrApplicant.objects.filter(job=job).count()


def open_application_count(job):
    """≙ ``_compute_open_application_count`` (``odoo19c: :193-200``)."""
    HrApplicant = apps.get_model('hr_recruitment', 'HrApplicant')
    HrRecruitmentStage = apps.get_model('hr_recruitment', 'HrRecruitmentStage')
    hired_stage_ids = HrRecruitmentStage.objects.filter(
        hired_stage=True,
    ).values_list('pk', flat=True)
    return HrApplicant.objects.filter(job=job).exclude(
        stage__in=hired_stage_ids,
    ).count()


def all_application_count(job):
    """≙ ``_compute_all_application_count`` (``odoo19c: :175-185``).

    DIVERGENCIA: el ``with_context(active_test=False)`` de la fuente se
    resuelve solo — el manager Django por defecto ya devuelve las filas
    inactivas (no hay filtro implícito por ``active`` en este ORM, a
    diferencia del ``_search`` de Odoo). El filtro que sí porta la
    referencia es el negocio: activo, o inactivo con motivo de rechazo.
    """
    HrApplicant = apps.get_model('hr_recruitment', 'HrApplicant')
    return HrApplicant.objects.filter(job=job).filter(
        Q(active=True) | Q(active=False, refuse_reason__isnull=False),
    ).count()


def get_first_stage(job):
    """≙ ``_get_first_stage`` (``odoo19c: :217-222``) — la primera etapa
    (por secuencia) elegible para este puesto: la suya, o una sin puestos
    específicos."""
    HrRecruitmentStage = apps.get_model('hr_recruitment', 'HrRecruitmentStage')
    return HrRecruitmentStage.objects.filter(
        Q(jobs__isnull=True) | Q(jobs=job),
    ).order_by('sequence').first()


def new_application_count(job):
    """≙ ``_compute_new_application_count`` (``odoo19c: :224-257``).

    DIVERGENCIA: la fuente arma la primera etapa "vigente" por SQL crudo
    (``DISTINCT ON`` + fallback). Aquí se resuelve con ``get_first_stage``
    (mismo criterio, ya portado) y se cuenta lo que está en ella.
    """
    HrApplicant = apps.get_model('hr_recruitment', 'HrApplicant')
    first_stage = get_first_stage(job)
    if first_stage is None:
        return 0
    return HrApplicant.objects.filter(job=job, stage=first_stage).count()


def old_application_count(job):
    """≙ ``_compute_old_application_count`` (``odoo19c: :269-272``)."""
    return application_count(job) - new_application_count(job)


def applicant_hired(job):
    """≙ ``_compute_applicant_hired`` (``odoo19c: :259-267``)."""
    HrApplicant = apps.get_model('hr_recruitment', 'HrApplicant')
    HrRecruitmentStage = apps.get_model('hr_recruitment', 'HrRecruitmentStage')
    hired_stage_ids = HrRecruitmentStage.objects.filter(
        hired_stage=True,
    ).values_list('pk', flat=True)
    return HrApplicant.objects.filter(job=job, stage__in=hired_stage_ids).count()


def no_of_hired_employee(job):
    """≙ ``_compute_no_of_hired_employee`` (``odoo19c: :88-101``)."""
    HrApplicant = apps.get_model('hr_recruitment', 'HrApplicant')
    return HrApplicant.objects.filter(job=job, date_closed__isnull=False).count()


def document_ids(job):
    """≙ ``_compute_document_ids`` (``odoo19c: :157-173``) — adjuntos del
    puesto más los de sus candidatos sin empleado vinculado."""
    IrAttachment = apps.get_model('base', 'IrAttachment')
    HrApplicant = apps.get_model('hr_recruitment', 'HrApplicant')
    applicant_ids = list(HrApplicant.objects.filter(
        job=job, employee__isnull=True,
    ).values_list('pk', flat=True))
    return IrAttachment.objects.filter(
        Q(res_model='hr.job', res_id=job.pk)
        | Q(res_model='hr.applicant', res_id__in=applicant_ids),
    )


def documents_count(job):
    return document_ids(job).count()


def employee_count(job):
    """≙ ``_compute_employee_count`` (``odoo19c: :202-215``).

    DIVERGENCIA: sin acotar por ``self.env.companies`` — ``hr.HrEmployee``
    no declara una FK directa a ``company`` en este árbol (medido: sólo
    ``company_country_code``, un ``Char``). El conteo es global.
    """
    HrEmployee = apps.get_model('hr', 'HrEmployee')
    return HrEmployee.objects.filter(version__job=job).count()


def activity_count(job):
    """≙ ``_compute_activities`` (``odoo19c: :103-128``) — actividades de
    ``self.env.uid`` sobre los candidatos activos y no contratados de este
    puesto.

    DIVERGENCIA: la fuente arma la cuenta con SQL crudo contra tres
    tablas; aquí se expresa con el ORM de Django sobre los mismos modelos.
    """
    user = get_current_user()
    if user is None:
        return 0
    MailActivity = apps.get_model('mail', 'MailActivity')
    HrApplicant = apps.get_model('hr_recruitment', 'HrApplicant')
    applicant_ids = list(HrApplicant.objects.filter(
        job=job, active=True,
    ).exclude(stage__hired_stage=True).values_list('pk', flat=True))
    return MailActivity.objects.filter(
        user=user, res_model='hr.applicant', res_id__in=applicant_ids,
    ).count()


def extended_interviewer_ids(job):
    """≙ ``_compute_extended_interviewer_ids`` (``odoo19c: :130-141``).

    DIVERGENCIA: sin ``with_user(SUPERUSER_ID)`` — este ORM no tiene
    elevación de acceso por usuario técnico.
    """
    HrApplicant = apps.get_model('hr_recruitment', 'HrApplicant')
    ResUsersModel = apps.get_model('base', 'ResUsers')
    interviewer_pks = set()
    for applicant in HrApplicant.objects.filter(job=job).prefetch_related('interviewers'):
        interviewer_pks |= set(applicant.interviewers.values_list('pk', flat=True))
    return ResUsersModel.objects.filter(pk__in=interviewer_pks)


def is_favorite(job):
    """≙ ``_compute_is_favorite`` (``odoo19c: :143-145``)."""
    user = get_current_user()
    return user is not None and job.favorite_users.filter(pk=user.pk).exists()


def set_favorite(job, is_fav):
    """≙ ``_inverse_is_favorite`` (``odoo19c: :147-155``)."""
    user = get_current_user()
    if user is None:
        return
    if is_fav:
        job.favorite_users.add(user)
    else:
        job.favorite_users.remove(user)


def _wire_extra_methods(model):
    """≙ ``luego=`` de ``extend_model`` — los símbolos que no encajan como
    ``campos``/``metodos``/``propiedades`` (una property con setter, un
    helper interno reutilizable por otros archivos del addon)."""
    model.set_favorite = set_favorite
    model._get_first_stage = get_first_stage


def apply_hr_recruitment_hr_job_extensions():
    """Cuelga sobre ``hr.job`` lo que ``hr_recruitment`` le añade — ≙
    ``_inherit``."""
    extend_model(
        'hr', 'HrJob',
        campos={
            'expected_employees': fields.Integer(default=0, verbose_name='Empleados esperados'),
            'no_of_employee': fields.Integer(default=0, verbose_name='Número de empleados actual'),
            'address': fields.Many2one(
                'base.ResPartner', on_delete=models.SET_NULL, null=True, blank=True,
                related_name='hr_jobs_located', verbose_name='Ubicación',
                help_text='Odoo address_id: dirección donde trabajará el candidato.',
            ),
            'color': fields.Integer(default=0, verbose_name='Índice de color'),
            'favorite_users': fields.Many2many(
                'base.ResUsers', related_name='favorite_jobs', blank=True,
                verbose_name='Usuarios que lo marcaron favorito',
            ),
            'interviewers': fields.Many2many(
                'base.ResUsers', related_name='interviewer_jobs', blank=True,
                verbose_name='Entrevistadores',
                help_text='Ven todos los candidatos del puesto y pueden '
                          'rechazarlos, sin necesitar permisos de reclutamiento.',
            ),
            'expected_degree': fields.Many2one(
                'hr_recruitment.HrRecruitmentDegree', on_delete=models.SET_NULL,
                null=True, blank=True, related_name='jobs',
                verbose_name='Grado esperado',
            ),
            'job_properties': fields.Properties(null=True, blank=True, verbose_name='Propiedades del puesto'),
            'applicant_properties_definition': fields.PropertiesDefinition(
                null=True, blank=True, verbose_name='Definición de propiedades de candidato',
            ),
        },
        propiedades={
            'application_count': application_count,
            'open_application_count': open_application_count,
            'all_application_count': all_application_count,
            'new_application_count': new_application_count,
            'old_application_count': old_application_count,
            'applicant_hired': applicant_hired,
            'document_ids': document_ids,
            'documents_count': documents_count,
            'employee_count': employee_count,
            'activity_count': activity_count,
            'extended_interviewer_ids': extended_interviewer_ids,
            'is_favorite': is_favorite,
            'no_of_hired_employee': no_of_hired_employee,
        },
        luego=_wire_extra_methods,
    )
