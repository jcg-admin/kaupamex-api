# Adaptado de Odoo Community `hr_recruitment/__manifest__.py` (LGPL-3) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Reclutamiento (hr.applicant, hr.job.platform, hr.talent.pool)',
    'version': '1.1',
    'category': 'Human Resources/Recruitment',
    'summary': 'Pipeline de reclutamiento: hr.applicant + '
               'hr.recruitment.stage/source/degree + hr.talent.pool + '
               'hr.job.platform',
    # `depends` MEDIDO contra los imports reales de este addon, no copiado de
    # la referencia (que declara ['hr', 'calendar', 'utm',
    # 'attachment_indexation', 'web_tour', 'digest']). Medidos ausentes de
    # este árbol:
    # `calendar` (0 hits en addons/), `attachment_indexation` (0 hits),
    # `web_tour` (0 hits) — sus consumidores quedan BLOQUEADOS con la pieza
    # nombrada (ver models/calendar.py, models/ir_attachment.py).
    'depends': [
        # TimeStampedModel, ResCompany, ResUsers, ResPartner,
        # IrAttachment, IrUiMenu
        'base',
        'mail',   # MailThread, MailActivityMixin, MailAlias, MailTemplate
        'hr',     # HrEmployee, HrDepartment, HrJob (extendido, no re-creado)
        'utm',    # UtmMixin, UtmSourceMixin, UtmSource, UtmCampaign, UtmMedium
        # DigestDigest (extensión portada, 4 de 4 — ver models/digest.py)
        'digest',
    ],
    # Licencia de la fuente de la que se adapta este addon, tal como su
    # manifest la declara (DEC-KX-03 punto 1): `hr_recruitment` en Odoo
    # Community es LGPL-3.
    'license': 'LGPL-3',
    # Seguridad de la fuente
    # (``odoo19c: hr_recruitment/__manifest__.py:20-21``), por
    # ``load_data`` en el ciclo de instalación y en el mismo orden. El CSV es
    # copia fiel sin 12 filas cuyo modelo no tiene fila en ``ir.model``:
    # ``calendar.event[.type]`` (no portado), los cuatro asistentes
    # (``TransientModel`` abstractos) y ``mail.activity.plan[_template]``.
    # Las omisiones del XML se declaran en su cabecera.
    'data': [
        'security/hr_recruitment_security.xml',
        'security/ir.model.access.csv',
    ],
    'application': True,
    'installable': True,
    'auto_install': False,
}
