"""``utm.campaign`` — protección de la campaña de reclutamiento (Odoo
``hr_recruitment``).

Adaptación fiel de Odoo ``hr_recruitment/models/utm_campaign.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 19 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 1 de 1 (forma), con su dato BLOQUEADO
====================================================================

``_unlink_except_utm_campaign_job`` (``:11-19``) veta borrar la campaña
``hr_recruitment.utm_campaign_job`` — un identificador externo (dato XML)
que este addon no siembra (fuera de write-set: no crea data/migraciones).
Sin la fila, ``IrModelData.ref(..., raise_if_not_found=False)`` devuelve
``None`` y el veto no aplica — la FORMA del guard se porta igual; el
DATO que protege queda pendiente de sembrar (mismo criterio que
``ir_ui_menu.py`` de este addon).

Divergencia declarada
========================

``@api.ondelete(at_uninstall=False)`` no existe en este ORM: el gancho se
conserva como método normal que quien orqueste el borrado invoca antes de
``delete()`` (mismo patrón que ``hr/models/res_partner.py::
_unlink_contact_rel_employee``).
"""
from django.apps import apps

from exceptions import UserError
from tools.translate import _


def check_utm_campaign_job_not_deleted(campaigns):
    """≙ ``_unlink_except_utm_campaign_job`` (``odoo19c: utm_campaign.py:
    11-19``) — se invoca antes de borrar ``campaigns``."""
    IrModelData = apps.get_model('base', 'IrModelData')
    utm_campaign_job = IrModelData.ref(
        'hr_recruitment.utm_campaign_job', raise_if_not_found=False,
    )
    if utm_campaign_job is not None and utm_campaign_job in list(campaigns):
        raise UserError(_(
            'No puedes eliminar la campaña UTM "%(name)s" porque se usa '
            'en el proceso de reclutamiento.', name=utm_campaign_job.name,
        ))


__all__ = ['check_utm_campaign_job_not_deleted']
