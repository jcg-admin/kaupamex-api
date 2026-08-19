"""``hr.job.platform`` — una bolsa de trabajo externa que reenvía candidatos
por correo (Odoo ``hr_recruitment``).

Adaptación fiel de Odoo ``hr_recruitment/models/hr_job_platform.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 30 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 6 de 6
====================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``name``/``email``/``regex`` (``:9-14``)
     - portados
   * - ``_email_uniq`` (``:16-19``)
     - portado — ``Meta.constraints``
   * - ``create`` (``:21-26``)
     - portado — ``save()``
   * - ``write`` (``:28-30``)
     - portado — ``save()``

Divergencia declarada
========================

``tools.email_normalize`` (``odoo.tools.mail``) no está portado en este árbol
(medido: ``grep -rn "def email_normalize" src/`` → 0 hits fuera del privado
provisional de ``ir_mail_server.py``, que se declara canónico para
``tools/mail.py`` cuando exista). Aquí se usa una normalización mínima
(``strip().lower()``) — misma forma que ``hr: models/models.py::
_alias_get_error`` ya adoptó para el mismo símbolo ausente.
"""
import fields
import models
from addons.base.models import TimeStampedModel


def _normalize_email(text):
    """Normalización mínima de correo — ver divergencia del docstring."""
    return (text or '').strip().lower()


class HrJobPlatform(TimeStampedModel):
    """``hr.job.platform`` — plataforma de origen de candidaturas por correo."""

    _name = 'hr.job.platform'
    _description = 'Job Platforms'

    name = fields.Char(max_length=255)
    email = fields.Char(
        max_length=255,
        help_text="Applications received from this Email won't be linked to "
                  'a contact. There will be no email address set on the '
                  'Applicant either.',
    )
    regex = fields.Char(
        max_length=255, blank=True, default='',
        help_text='The regex facilitates to extract information from the '
                  "subject or body of the received email to autopopulate "
                  "the Applicant's name field.",
    )

    class Meta:
        db_table = 'hr_job_platform'
        verbose_name = 'Plataforma de reclutamiento'
        verbose_name_plural = 'Plataformas de reclutamiento'
        constraints = [
            models.UniqueConstraint(
                fields=['email'], name='hr_job_platform_email_uniq',
                violation_error_message='The Email must be unique, this one '
                                        'already corresponds to another Job '
                                        'Platform.',
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        """≙ ``create``/``write`` (``odoo19c: :21-30``) — normaliza el
        correo en ambas rutas (Django unifica alta y edición en ``save``)."""
        if self.email:
            self.email = _normalize_email(self.email) or self.email
        return super().save(*args, **kwargs)
