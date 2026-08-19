"""``applicant.get.refuse.reason`` — rechazar candidatos en lote, con aviso
opcional por correo (Odoo ``hr_recruitment``).

Adaptación de Odoo ``hr_recruitment/wizard/applicant_refuse_reason.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 181 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 8 de 10, 2 BLOQUEADOS
=====================================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``_default_refuse_reason_id``…``_compute_duplicate_applicant_ids``
       (9 campos + computes, ``:14-79``)
     - resueltos como argumentos/valores calculados del classmethod
       principal — sin motor de formulario reactivo en este ORM (mismo
       criterio que ``hr.HrDepartureWizard``)
   * - ``_compute_render_model``/``_compute_template_id``/
       ``_compute_from_template_id`` (``:81-113``)
     - BLOQUEADOS — overrides de ``mail.composer.mixin``, ausente (mismo
       bloqueo que ``applicant_send_mail.py`` de este addon)
   * - ``action_refuse_reason_apply`` (``:115-143``)
     - portado
   * - ``_get_related_original_applicants`` (``:145-160``)
     - portado
   * - ``_prepare_send_refusal_mails``/``_prepare_mail_values``
       (``:162-181``)
     - portados (divergencia: sin ``_render_field``/``_render_lang`` del
       mixin ausente — usa ``MailTemplate.render()`` cuando hay plantilla,
       literal si no; mismo criterio que ``applicant_send_mail.py``)
"""
from datetime import datetime

from django.apps import apps

from orm.models_transient import TransientModel
from tools.translate import _


class ApplicantGetRefuseReason(TransientModel):
    """Rechaza uno o más candidatos con un motivo común, y opcionalmente
    detecta y rechaza sus duplicados."""

    class Meta:
        abstract = True
        managed = False

    _name = 'applicant.get.refuse.reason'
    _description = 'Get Refuse Reason'

    @classmethod
    def default_refuse_reason(cls):
        """≙ ``_default_refuse_reason_id`` (``odoo19c: :14-15``)."""
        HrApplicantRefuseReason = apps.get_model('hr_recruitment', 'HrApplicantRefuseReason')
        return HrApplicantRefuseReason.objects.order_by('sequence').first()

    @classmethod
    def applicants_without_email(cls, applicants):
        """≙ ``_compute_applicant_without_email`` (``odoo19c: :51-61``)."""
        return [a for a in applicants
                if not a.email_from and not (a.partner_id and a.partner.email)]

    @classmethod
    def duplicate_applicants(cls, applicants):
        """≙ ``_compute_duplicate_applicant_ids`` (``odoo19c: :74-79``,
        vía el domain de ``_compute_duplicate_applicant_ids_domain``,
        ``:63-72``) — candidatos similares, excluidos los ya en curso de
        rechazo y los ya cerrados."""
        if not applicants:
            return []
        seeds = list(applicants)
        first = seeds[0]
        queryset = first.get_similar_applicants()
        for other in seeds[1:]:
            queryset = queryset | other.get_similar_applicants()
        seed_pks = {a.pk for a in seeds}
        return list(
            queryset.exclude(pk__in=seed_pks)
            .exclude(refuse_reason__isnull=False)
            .exclude(date_closed__isnull=False)
            .distinct(),
        )

    @classmethod
    def related_original_applicants(cls, applicants, duplicate_applicants):
        """≙ ``_get_related_original_applicants`` (``odoo19c: :145-160``) —
        para cada duplicado, el candidato "original" de ``applicants`` con
        el que comparte correo/teléfono/linkedin (o ``id``)."""
        fields_to_check = ['pk', 'email_normalized', 'partner_phone_sanitized', 'linkedin_profile']
        by_field = {f: {} for f in fields_to_check}
        for original in applicants:
            for field in fields_to_check:
                value = getattr(original, field)
                if value:
                    by_field[field][value] = original
        related = {}
        for duplicate in duplicate_applicants:
            for field in fields_to_check:
                value = getattr(duplicate, field)
                if value in by_field[field]:
                    related[duplicate] = by_field[field][value]
                    break
        return related

    @classmethod
    def prepare_mail_values(cls, applicant, refuse_reason, template=None,
                            subject='', body='', author=None):
        """≙ ``_prepare_mail_values`` (``odoo19c: :167-181``)."""
        if template is not None:
            rendered = template.render(applicant)
            return {
                'subject': rendered.get('subject') or subject,
                'body': rendered.get('body_html') or body,
                'author': author,
            }
        return {'subject': subject, 'body': body, 'author': author}

    @classmethod
    def action_refuse_reason_apply(cls, applicants, refuse_reason, send_mail=False,
                                   duplicates=False, template=None, subject='',
                                   body='', author=None):
        """≙ ``action_refuse_reason_apply`` (``odoo19c: :115-143``).

        :param applicants: candidatos elegidos explícitamente.
        :param duplicates: si ``True``, también rechaza sus duplicados
            (``duplicate_applicants``), con un mensaje automático de
            trazabilidad hacia el original.
        :return: los candidatos efectivamente rechazados.
        """
        applicants = list(applicants)
        if send_mail:
            for applicant in applicants:
                if not applicant.email_from and not (applicant.partner_id and applicant.partner.email):
                    raise ValueError(_(
                        'Al menos un candidato no tiene correo; no puedes '
                        'usar la opción de enviar correo.',
                    ))
        refused = list(applicants)
        duplicate_list = cls.duplicate_applicants(applicants) if duplicates else []
        if duplicate_list:
            refused += duplicate_list
            originals = cls.related_original_applicants(applicants, duplicate_list)
            for duplicate in duplicate_list:
                original = originals.get(duplicate)
                if original is not None:
                    duplicate.message_post(body=_(
                        'Rechazado automáticamente por ser un duplicado de %(name)s',
                        name=original.partner_name or '',
                    ))

        now = datetime.now()
        for applicant in refused:
            applicant.refuse_reason = refuse_reason
            applicant.active = False
            applicant.refuse_date = now
            applicant.save(update_fields=['refuse_reason', 'active', 'refuse_date'])

        if send_mail:
            for applicant in applicants:
                mail_values = cls.prepare_mail_values(
                    applicant, refuse_reason, template=template,
                    subject=subject, body=body, author=author,
                )
                applicant.message_post(**mail_values)

        return refused
