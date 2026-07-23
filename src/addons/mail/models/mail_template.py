"""``mail.template`` — plantilla de correo con placeholders (Odoo ``mail``).

Portacion fiel de ``MailTemplate``
(``scratchpad/odoo19x/addons/mail/models/mail_template.py:39-91``, Odoo 19;
identico en campos a 18) — la plantilla parametrizable (asunto/cuerpo/
destinatarios con placeholders) que se renderiza contra un registro para
producir un correo. Es el hogar canonico que unifica las plantillas ad-hoc de
``sms``/``newsletter``. Parte de la familia ``mail`` (SOL-096).

Fuente Odoo community (LGPL-3): copia + adaptacion con atribucion.

- ``model`` ← ``model_id``/``model`` (Odoo ``ir.model`` + Char related): este
  monolito NO porta ``ir.model`` (H-BASE-08), asi que el modelo aplicable se
  guarda como Char plano, p. ej. ``"orders.Order"``.
- **Rendering nativo, no QWeb:** Odoo renderiza los placeholders con
  qweb/inline_template (``{{ object.name }}``). Django tiene su motor de
  plantillas con **la misma sintaxis** ``{{ object.campo }}``; ``render()`` lo
  usa contra ``{'object': record}``. Reimplementacion fiel del contrato (mismo
  resultado) sin arrastrar el pipeline QWeb (el frontend es React). El **envio**
  real NO vive aqui (lo hace ``email_executor`` en la capa de servicio) para no
  importar ``notifications`` al poblar el registro de apps.
"""
from django.template import Context, Template

import fields
import models
from addons.base.models import TimeStampedModel


class MailTemplate(TimeStampedModel):
    """``mail.template`` — plantilla de correo renderizable contra un registro."""

    name = fields.Char(max_length=255, help_text='Nombre de la plantilla (Odoo name).')
    model = fields.Char(
        max_length=128, blank=True, default='',
        help_text='Modelo aplicable, p. ej. "orders.Order" (Odoo model/model_id).',
    )
    subject = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Asunto con placeholders {{ object.campo }} (Odoo subject).',
    )
    email_from = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Remitente, admite placeholders (Odoo email_from).',
    )
    use_default_to = fields.Boolean(
        default=False,
        help_text='Usar el destinatario por defecto del registro (Odoo use_default_to).',
    )
    email_to = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Destinatarios coma-separados, admite placeholders (Odoo email_to).',
    )
    partner_to = fields.Char(
        max_length=255, blank=True, default='',
        help_text='IDs de party destinatarios, admite placeholders (Odoo partner_to).',
    )
    email_cc = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Copia (CC), admite placeholders (Odoo email_cc).',
    )
    reply_to = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Reply-To (Odoo reply_to).',
    )
    body_html = fields.Html(
        blank=True, default='',
        help_text='Cuerpo HTML con placeholders {{ object.campo }} (Odoo body_html).',
    )
    lang = fields.Char(
        max_length=16, blank=True, default='',
        help_text='Expresion de idioma para la traduccion (Odoo lang).',
    )
    scheduled_date = fields.Char(
        max_length=64, blank=True, default='',
        help_text='Fecha/expresion de envio diferido (Odoo scheduled_date).',
    )
    auto_delete = fields.Boolean(
        default=True,
        help_text='Eliminar el mail.mail tras enviar (Odoo auto_delete).',
    )

    class Meta:
        db_table = 'mail_template'
        ordering = ['name', 'id']
        verbose_name = 'Plantilla de correo'
        verbose_name_plural = 'Plantillas de correo'
        indexes = [
            models.Index(fields=['model'], name='mail_template_model_idx'),
        ]

    def __str__(self) -> str:
        return self.name

    @staticmethod
    def _render_str(text, ctx) -> str:
        """Renderiza un campo con el motor de plantillas de Django (≙ Odoo _render_field)."""
        if not text:
            return ''
        return Template(text).render(ctx)

    def render(self, record, extra_context=None):
        """Renderiza la plantilla contra ``record`` (Odoo ``_render_template``).

        Devuelve un dict con los campos renderizados listos para el envio.
        El envio efectivo lo hace la capa de servicio (``email_executor``).
        """
        context = {'object': record}
        if extra_context:
            context.update(extra_context)
        ctx = Context(context)
        return {
            'subject': self._render_str(self.subject, ctx),
            'body_html': self._render_str(self.body_html, ctx),
            'email_from': self._render_str(self.email_from, ctx),
            'email_to': self._render_str(self.email_to, ctx),
            'email_cc': self._render_str(self.email_cc, ctx),
            'reply_to': self._render_str(self.reply_to, ctx),
        }
