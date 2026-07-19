"""``mail.mail`` — mensaje de correo saliente + cola de envio (Odoo ``mail``).

Portacion fiel de ``MailMail``
(``scratchpad/odoo19x/addons/mail/models/mail_mail.py:25-95``, Odoo 19; identico
en estados a 18) — el registro RFC2822 de correo saliente que Odoo encola y envia
con ``process_email_queue``. Es el hogar canonico de la cola de reintento que hoy
vive como ``notifications.EmailTask`` (en disolucion, SOL-096 familia ``mail``).

Fuente Odoo community (LGPL-3): copia + adaptacion con atribucion.

Fidelidad y adaptaciones (documentadas, principio-rector Clausula 2):

- **Estados** ``state`` — los 5 de Odoo (``outgoing``/``sent``/``received``/
  ``exception``/``cancel``), default ``outgoing``. ``EmailTask.Status``
  (pending/sent/failed/retrying) mapea: ``pending``/``retrying`` → ``outgoing``
  (la cola de reintento son filas ``outgoing`` con ``attempts`` > 0),
  ``sent`` → ``sent``, ``failed`` (max reintentos) → ``exception``.
- **``failure_type``/``failure_reason``** — fieles a Odoo (subconjunto ``mail_*``
  aplicable a este stack; sin ``snail``/``sms`` que no son correo). ``last_error``
  de ``EmailTask`` ≙ ``failure_reason``.
- **No ``_inherits`` de ``mail.message``** — Odoo delega ``subject``/``body`` al
  ``mail.message`` enlazado. Este monolito NO porta la delegacion Odoo (H-BASE):
  ``subject``/``body_html``/``email_from`` viven como columnas propias, igual que
  ya hacia ``EmailTask``. El puente al chatter existe por el otro lado
  (``mail.notification`` referencia el envio saliente).
- **``attempts``/``max_attempts``** — adaptacion de proyecto: cola de reintento
  **sin broker** (sin Celery/Redis), heredada de ``EmailTask`` (Alt 2 de
  ``email_executor``). Odoo reintenta con su cron; aqui el conteo acota los
  reintentos y ``exception`` es terminal al agotarlos.
- El **envio** real NO vive aqui — lo hace ``email_executor`` (capa de servicio,
  ≙ ``mail.mail.process_email_queue``) para no importar addons al poblar el
  registro de apps.
"""
from django.db.models import Q
from django.utils import timezone

import fields
import models
from addons.base.models import TimeStampedModel


class MailMail(TimeStampedModel):
    """``mail.mail`` — correo saliente encolado para envio/reintento."""

    # Odoo state (mail_mail.py) — ciclo de vida del envio.
    STATE_OUTGOING = 'outgoing'
    STATE_SENT = 'sent'
    STATE_RECEIVED = 'received'
    STATE_EXCEPTION = 'exception'
    STATE_CANCEL = 'cancel'
    STATE_CHOICES = [
        (STATE_OUTGOING, 'Outgoing'),
        (STATE_SENT, 'Sent'),
        (STATE_RECEIVED, 'Received'),
        (STATE_EXCEPTION, 'Delivery Failed'),
        (STATE_CANCEL, 'Cancelled'),
    ]

    # Odoo failure_type — subconjunto de correo (sin snail/sms).
    FAILURE_UNKNOWN = 'unknown'
    FAILURE_MAIL_SPAM = 'mail_spam'
    FAILURE_MAIL_EMAIL_INVALID = 'mail_email_invalid'
    FAILURE_MAIL_EMAIL_MISSING = 'mail_email_missing'
    FAILURE_MAIL_FROM_INVALID = 'mail_from_invalid'
    FAILURE_MAIL_FROM_MISSING = 'mail_from_missing'
    FAILURE_MAIL_SMTP = 'mail_smtp'
    FAILURE_TYPE_CHOICES = [
        (FAILURE_UNKNOWN, 'Unknown error'),
        (FAILURE_MAIL_SPAM, 'Detected As Spam'),
        (FAILURE_MAIL_EMAIL_INVALID, 'Invalid email address'),
        (FAILURE_MAIL_EMAIL_MISSING, 'Missing email'),
        (FAILURE_MAIL_FROM_INVALID, 'Invalid from address'),
        (FAILURE_MAIL_FROM_MISSING, 'Missing from address'),
        (FAILURE_MAIL_SMTP, 'Connection failed (outgoing mail server problem)'),
    ]

    # content — Odoo email_to (Text), email_cc (Char), body_html (Text). subject/
    # email_from viven aqui (sin _inherits de mail.message, ver docstring).
    subject = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Asunto del correo (Odoo mail.message.subject).',
    )
    email_from = fields.Char(
        max_length=254, blank=True, default='',
        help_text='Remitente (Odoo mail.message.email_from).',
    )
    email_to = fields.Text(
        blank=True, default='',
        help_text='Destinatarios, coma-separados (Odoo email_to).',
    )
    email_cc = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Copia CC (Odoo email_cc).',
    )
    body_html = fields.Text(
        blank=True, default='',
        help_text='Cuerpo del correo, rich-text/HTML (Odoo body_html).',
    )
    # process — Odoo state/failure_type/failure_reason/scheduled_date/auto_delete.
    state = fields.Selection(
        max_length=10, choices=STATE_CHOICES, default=STATE_OUTGOING,
        help_text='Estado del envio (Odoo state).',
    )
    failure_type = fields.Selection(
        max_length=32, choices=FAILURE_TYPE_CHOICES, null=True, blank=True,
        help_text='Clasificacion del fallo de entrega (Odoo failure_type).',
    )
    failure_reason = fields.Text(
        blank=True, default='',
        help_text='Detalle del fallo, tipicamente la excepcion SMTP (Odoo failure_reason).',
    )
    scheduled_date = fields.Datetime(
        null=True, blank=True,
        help_text='Envio diferido: la cola envia despues de esta fecha (Odoo scheduled_date).',
    )
    auto_delete = fields.Boolean(
        default=False,
        help_text='Eliminar el registro tras enviar (Odoo auto_delete).',
    )
    # Adaptacion de proyecto: cola de reintento sin broker (ex-EmailTask).
    attempts = fields.Integer(
        default=0, help_text='Intentos de envio realizados (adaptacion de proyecto).',
    )
    max_attempts = fields.Integer(
        default=3, help_text='Tope de reintentos antes de exception (adaptacion de proyecto).',
    )

    class Meta:
        db_table = 'mail_mail'
        ordering = ['-id']
        verbose_name = 'Correo saliente'
        verbose_name_plural = 'Correos salientes'
        indexes = [
            models.Index(fields=['state', 'scheduled_date'], name='mail_mail_queue_idx'),
        ]

    def __str__(self) -> str:
        return f'MailMail#{self.pk} {self.state} → {self.email_to[:50]}'

    # ---- API de cola (≙ mail.mail create/send/process_email_queue) ----

    @classmethod
    def enqueue(cls, *, to, subject='', body_html='', email_from='',
                email_cc='', scheduled_date=None, max_attempts=3,
                failure_reason=''):
        """Encola un correo saliente (Odoo ``mail.mail.create`` con ``state='outgoing'``).

        Reemplaza a ``EmailTask.objects.create(...)`` como punto de entrada de la
        cola de reintento. El envio efectivo lo hace ``email_executor``.
        ``failure_reason`` preserva el error del intento previo del thread pool
        cuando ``email_executor`` reencola tras un fallo (fiel a Odoo, que
        conserva ``failure_reason`` entre reintentos).
        """
        return cls.objects.create(
            email_to=to, subject=subject, body_html=body_html,
            email_from=email_from, email_cc=email_cc,
            scheduled_date=scheduled_date, max_attempts=max_attempts,
            failure_reason=(failure_reason or '')[:1000],
        )

    @classmethod
    def pending(cls):
        """Filas listas para enviar: ``outgoing`` cuya fecha diferida ya paso
        (o es nula). Es la consulta de ``process_email_queue`` de Odoo."""
        now = timezone.now()
        return cls.objects.filter(state=cls.STATE_OUTGOING).filter(
            Q(scheduled_date__isnull=True) | Q(scheduled_date__lte=now)
        )

    @property
    def should_retry(self) -> bool:
        """El envio puede reintentarse: sigue ``outgoing`` y no agoto intentos."""
        return self.state == self.STATE_OUTGOING and self.attempts < self.max_attempts

    def mark_sent(self, *, count_attempt=False) -> None:
        """Marca el correo como enviado (Odoo ``state='sent'``). ``count_attempt``
        suma el intento exitoso al contador (lo usa el cron para reflejar el total
        de tries, como hacia ``EmailTask``)."""
        self.state = self.STATE_SENT
        self.failure_type = None
        self.failure_reason = ''
        fields = ['state', 'failure_type', 'failure_reason', 'updated_at']
        if count_attempt:
            self.attempts = self.attempts + 1
            fields.append('attempts')
        self.save(update_fields=fields)

    def mark_exception(self, failure_type, reason='') -> None:
        """Registra un fallo de entrega (Odoo ``state='exception'``) y suma un
        intento. Reencolar para reintento con ``requeue`` si aun quedan."""
        self.state = self.STATE_EXCEPTION
        self.failure_type = failure_type
        self.failure_reason = (reason or '')[:1000]
        self.attempts = self.attempts + 1
        self.save(update_fields=[
            'state', 'failure_type', 'failure_reason', 'attempts', 'updated_at',
        ])

    def requeue(self) -> None:
        """Devuelve un correo en ``exception`` a la cola (``outgoing``) para su
        siguiente reintento. Adaptacion de proyecto (cola sin broker)."""
        self.state = self.STATE_OUTGOING
        self.save(update_fields=['state', 'updated_at'])

    def register_failed_attempt(self, failure_type, reason='', *, backoff=None):
        """Contabiliza un intento de envio fallido de la cola (≙ el manejo de
        fallo de ``process_email_queue``). Suma un intento y guarda el error; si
        se agoto ``max_attempts`` el correo pasa a ``exception`` (terminal), si
        no permanece ``outgoing`` para el siguiente reintento — difiriendo el
        envio con ``backoff`` (``timedelta``) si se pasa. Adaptacion de proyecto:
        la cola de reintento sin broker (ex-``EmailTask``)."""
        self.attempts = self.attempts + 1
        self.failure_type = failure_type
        self.failure_reason = (reason or '')[:1000]
        fields = ['attempts', 'failure_type', 'failure_reason', 'state', 'updated_at']
        if self.attempts >= self.max_attempts:
            self.state = self.STATE_EXCEPTION
        else:
            self.state = self.STATE_OUTGOING
            if backoff is not None:
                self.scheduled_date = timezone.now() + backoff
                fields.append('scheduled_date')
        self.save(update_fields=fields)
