"""``applicant.send.mail`` — enviar un correo a uno o más candidatos (Odoo
``hr_recruitment``).

Adaptación de Odoo ``hr_recruitment/wizard/applicant_send_mail.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 62 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 2 de 3, 1 BLOQUEADO
===================================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``_compute_render_model`` (``:17-19``)
     - BLOQUEADO — override de ``mail.composer.mixin``, ausente en este
       árbol (medido: ``ls addons/mail/models/`` no trae ``composer``);
       mismo bloqueo que ``account.move.send.wizard`` ya declaró para el
       mismo mixin
   * - ``action_send`` (``:20-59``)
     - portado (divergencia: sin plantilla usa el asunto/cuerpo dados
       directo; con plantilla usa ``MailTemplate.render()``, que sí
       existe — ver ``addons.mail.models.mail_template``)

Divergencia declarada
========================

``self._render_field('subject', ...)``/``self._render_field('body', ...)``
(mixin ausente) → ``MailTemplate.render(record)`` por candidato, que ya
resuelve la sintaxis ``{{ object.campo }}`` (``mail: models/mail_template.py``,
su propio docstring lo declara). Sin plantilla, el asunto/cuerpo son
literales — sin variables por candidato (mismo límite que la referencia
sin ``template_id``).
"""
from orm.models_transient import TransientModel


class ApplicantSendMail(TransientModel):
    """Envía un correo (con o sin plantilla) a un grupo de candidatos."""

    class Meta:
        abstract = True
        managed = False

    _name = 'applicant.send.mail'
    _description = 'Send mails to applicants'

    @classmethod
    def missing_emails(cls, applicants):
        """≙ la guarda ``without_emails`` de ``action_send`` (``odoo19c:
        :22-30``)."""
        return [a for a in applicants
                if not a.email_from and not (a.partner_id and a.partner.email)]

    @classmethod
    def action_send(cls, applicants, author, subject='', body='', template=None):
        """≙ ``action_send`` (``odoo19c: :20-59``).

        :param author: ``base.ResPartner`` que firma el mensaje.
        :param template: ``mail.MailTemplate`` opcional.
        :return: ``{'sent': [...], 'missing_emails': [...]}``.
        """
        missing = cls.missing_emails(applicants)
        if missing:
            return {'sent': [], 'missing_emails': missing}
        sent = []
        for applicant in applicants:
            if not applicant.partner_id:
                applicant.ensure_partner()
            if template is not None:
                applicant.message_post_with_template(template, author=author)
            else:
                applicant.message_post(subject=subject, body=body, author=author)
            sent.append(applicant)
        return {'sent': sent, 'missing_emails': []}
