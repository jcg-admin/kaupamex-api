"""``utm.source`` — protección de fuentes ligadas a reclutamiento (Odoo
``hr_recruitment``).

Adaptación fiel de Odoo ``hr_recruitment/models/utm_source.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 23 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03). Porte completo — 1 de 1 símbolo.

Divergencia declarada
========================

``@api.ondelete(at_uninstall=False)`` no existe en este ORM — mismo
criterio que ``utm_campaign.py`` de este addon: queda disponible como
guard que quien orqueste el borrado invoca antes de ``delete()``.
"""
from django.apps import apps

from exceptions import UserError
from tools.translate import _


def check_sources_not_linked_to_recruitment(sources):
    """≙ ``_unlink_except_linked_recruitment_sources`` (``odoo19c:
    utm_source.py:18-23``) — se invoca antes de borrar ``sources``
    (``utm.UtmSource``)."""
    HrRecruitmentSource = apps.get_model('hr_recruitment', 'HrRecruitmentSource')
    source_pks = [source.pk for source in sources]
    linked = HrRecruitmentSource.objects.filter(source__pk__in=source_pks)
    if linked.exists():
        job_names = ', '.join(f'"{job.name}"' for job in linked.values_list('job__name', flat=True).distinct())
        raise UserError(_(
            'No puedes eliminar estas fuentes UTM porque están ligadas a '
            'los siguientes orígenes de reclutamiento en Reclutamiento:\n'
            '%(recruitment_sources)s', recruitment_sources=job_names,
        ))


__all__ = ['check_sources_not_linked_to_recruitment']
