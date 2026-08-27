"""``res.users`` — la membresía al grupo de entrevistadores (Odoo
``hr_recruitment``).

Adaptación de Odoo ``hr_recruitment/models/res_users.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 37 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03). Porte completo — 2 de 2 símbolos.

``_inherit`` lo expresa ``extend_model``; par de Django porque
``base.ResUsers`` no declara ``_name``.

Divergencias declaradas
==========================

1. **``self.env.ref('hr_recruitment.group_hr_recruitment_interviewer')``**
   → ``IrModelData.ref(xmlid, raise_if_not_found=False)`` (el ``env.ref``
   de este árbol — ``src/addons/base/models/ir_model.py``). Sin la fila
   sembrada, ambos métodos son no-op silencioso: es data ausente, no
   esquema ausente (mismo criterio que ``ir_ui_menu.py`` de ``hr``).
2. **``(4, id)``/``(3, id)`` sobre ``group_ids``** → ``ResGroups.user_ids
   .add()``/``.remove()`` (el M2M explícito; ``all_user_ids`` es una
   ``@property`` computada — clausura transitiva de implicación, no un
   manager — y no admite ``.add()``/``.remove()``).
3. **``self - recruitment_group.all_user_ids``** → resta de conjuntos de
   PKs — sin álgebra de recordset en este ORM.
"""
from django.apps import apps

from orm.model_classes import extend_model


def _recruitment_groups():
    """Resuelve los dos grupos de la referencia, o ``(None, None)`` si no
    están sembrados (data, no esquema — ver divergencia 1)."""
    IrModelData = apps.get_model('base', 'IrModelData')
    interviewer_group = IrModelData.ref(
        'hr_recruitment.group_hr_recruitment_interviewer', raise_if_not_found=False,
    )
    recruitment_group = IrModelData.ref(
        'hr_recruitment.group_hr_recruitment_user', raise_if_not_found=False,
    )
    return interviewer_group, recruitment_group


def create_recruitment_interviewers(cls, users):
    """≙ ``_create_recruitment_interviewers`` (``odoo19c: :10-18``) — añade
    ``users`` al grupo de entrevistadores, salvo quien ya sea reclutador
    (ese grupo ya implica el de entrevistador)."""
    users = list(users)
    if not users:
        return
    interviewer_group, recruitment_group = _recruitment_groups()
    if interviewer_group is None or recruitment_group is None:
        return
    already_recruiters = set(recruitment_group.all_user_ids.values_list('pk', flat=True))
    for user in users:
        if user.pk not in already_recruiters:
            interviewer_group.user_ids.add(user)


def remove_recruitment_interviewers(cls, users):
    """≙ ``_remove_recruitment_interviewers`` (``odoo19c: :20-37``) — quita
    de ``users`` a quien ya no sea entrevistador de ningún puesto ni
    candidato, ni reclutador."""
    users = list(users)
    if not users:
        return
    interviewer_group, recruitment_group = _recruitment_groups()
    if interviewer_group is None or recruitment_group is None:
        return
    user_pks = {user.pk for user in users}
    HrJob = apps.get_model('hr', 'HrJob')
    HrApplicant = apps.get_model('hr_recruitment', 'HrApplicant')
    still_interviewing = set()
    for job in HrJob.objects.filter(interviewers__pk__in=user_pks).distinct():
        still_interviewing |= set(job.interviewers.values_list('pk', flat=True))
    for applicant in HrApplicant.objects.filter(interviewers__pk__in=user_pks).distinct():
        still_interviewing |= set(applicant.interviewers.values_list('pk', flat=True))
    still_recruiters = set(recruitment_group.all_user_ids.values_list('pk', flat=True))
    to_remove_pks = user_pks - (still_interviewing | still_recruiters)
    for user in users:
        if user.pk in to_remove_pks:
            interviewer_group.user_ids.remove(user)


def apply_hr_recruitment_res_users_extensions():
    """Cuelga sobre ``res.users`` lo que ``hr_recruitment`` le añade — ≙
    ``_inherit``."""
    extend_model('base', 'ResUsers', metodos={
        '_create_recruitment_interviewers': classmethod(create_recruitment_interviewers),
        '_remove_recruitment_interviewers': classmethod(remove_recruitment_interviewers),
    })
