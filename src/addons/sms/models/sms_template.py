"""Modelo ``SmsTemplate`` — addon ``sms``.

Adaptación de Odoo ``sms/models/sms_template.py`` (``sms.template``): plantilla
de texto para SMS. Odoo la ancla a un ``ir.model`` y renderiza con QWeb/jinja
sobre un registro; aquí se conserva el núcleo portable — ``name`` + ``body`` con
placeholders ``str.format`` (``{campo}``) — sin el motor de plantillas de Odoo,
que no existe en este stack.
"""
from django.db import models

from core.models import TimeStampedModel


class _SafeDict(dict):
    """Dict que deja el literal ``{campo}`` intacto si el placeholder falta."""

    def __missing__(self, key):
        return '{' + key + '}'


class SmsTemplate(TimeStampedModel):
    """``sms.template`` — plantilla de texto para un SMS."""

    # Odoo sms.template.name (sms_template.py:22).
    name   = models.CharField(
        max_length=100, help_text='Nombre de la plantilla (Odoo sms.template.name).',
    )
    # Odoo sms.template.body (sms_template.py:27, required). Placeholders
    # ``{campo}`` resueltos con ``str.format`` (no QWeb).
    body   = models.TextField(
        help_text='Cuerpo con placeholders {campo} (Odoo sms.template.body).',
    )
    # Sin equivalente directo: bandera local para desactivar sin borrar.
    active = models.BooleanField(
        default=True, help_text='Plantilla activa.',
    )

    class Meta:
        db_table = 'sms_template'
        verbose_name = 'Plantilla de SMS'
        verbose_name_plural = 'Plantillas de SMS'

    def __str__(self) -> str:
        return self.name

    def render(self, context) -> str:
        """Renderiza el cuerpo con ``context`` (dict) vía ``str.format``.

        Equivale al render de Odoo sobre un registro, pero con placeholders
        simples ``{campo}``. Un placeholder ausente deja el literal intacto en
        vez de romper (comportamiento tolerante para plantillas parciales).
        """
        return self.body.format_map(_SafeDict(context or {}))
