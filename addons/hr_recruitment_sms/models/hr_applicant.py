"""``hr.applicant`` — enviar un SMS al candidato.

Adaptación de Odoo hr_recruitment_sms/models/hr_applicant.py
(odoo-tools, odoo19c:, LGPL-3, 17 líneas) — atribución y aviso de licencia
preservados (DEC-KX-03).

Porte símbolo por símbolo — 1 método (medido por AST)
======================================================

.. list-table::
   :header-rows: 1

   * - Símbolo de la referencia (línea)
     - Dónde queda aquí
   * - ``action_send_sms`` (``:9-17``)
     - portado — materializado (ver divergencia única)

Divergencia declarada
======================

**El composer de SMS es UI del cliente Odoo; aquí el envío se
materializa.** La referencia no envía nada: devuelve un
``ir.actions.act_window`` que abre el wizard ``sms.composer`` en modo masa
(``default_composition_mode='mass'``, ``default_res_ids=self.ids``) y es el
wizard quien crea los ``sms.sms``. Sin cliente Odoo, el equivalente local
es crear directamente el registro de envío — el MISMO criterio con que
``sale_sms`` materializó su composer (``sale_sms/models/
sale_order_sms_confirmation.py``): ``SmsSms`` es el registro de intención
de envío y el transporte real lo cablea el proveedor que se integre.

- El modo masa (``default_res_ids`` = N candidatos) se resuelve iterando el
  queryset: el método es por instancia; el llamador DRF que quiera masa
  itera ``for applicant in queryset: applicant.action_send_sms(...)``.
- ``default_mass_keep_log=True`` (log en el chatter) queda cubierto por el
  propio registro ``SmsSms`` persistido, que ES la bitácora del envío aquí.
- El número destino es ``partner_phone`` del candidato (el mismo campo que
  el composer de la referencia resuelve para ``hr.applicant``).
"""
from addons.sms.models import SmsSms
from exceptions import UserError
from orm.model_classes import extend_model
from tools.translate import _


def action_send_sms(self, body=None, template=None, context=None):
    """≙ ``action_send_sms`` (``:9-17``) — crea el SMS saliente para este
    candidato. Ver la divergencia única del docstring del módulo.

    :param body: texto del mensaje; alternativamente ``template``.
    :param template: ``sms.template`` a renderizar con ``context``.
    :param context: dict para ``template.render()`` (placeholders).
    :returns: el ``SmsSms`` creado (estado ``pending``).
    """
    if not self.partner_phone:
        raise UserError(
            _('El candidato %s no tiene teléfono al cual enviar el SMS.')
            % (self.partner_name or self.pk),
        )
    if body is None and template is None:
        raise UserError(_('Indica el cuerpo del SMS o una plantilla.'))
    if body is None:
        body = template.render(context or {'applicant': self.partner_name})
    return SmsSms.objects.create(number=self.partner_phone, body=body)


def apply_hr_recruitment_sms_hr_applicant_extensions():
    """Cuelga sobre ``hr.applicant`` el envío de SMS — ≙ ``_inherit``. Se
    invoca desde ``HrRecruitmentSmsConfig.ready()``."""
    extend_model(
        'hr_recruitment', 'HrApplicant',
        metodos={
            'action_send_sms': action_send_sms,
        },
    )
