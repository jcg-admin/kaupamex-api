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
- **``_inherits`` de ``mail.message`` — PORTADA** (directiva del ejecutor
  2026-08-01: *"queremos delegar las cosas, como lo tienes en odoo-tools"*).
  La referencia declara ``_inherits = {'mail.message': 'mail_message_id'}``
  (``mail_mail.py:31``) con el enlace ``Many2one('mail.message', required=True,
  ondelete='cascade')`` (``:46``); ``subject`` y ``email_from`` **no son de**
  ``mail.mail`` — viven en ``mail.message`` (``mail_message.py:91,144``).

  Se porta con el patron ya establecido en este arbol para ``_inherits``: **FK
  real + delegacion por propiedad**, NO herencia multi-tabla de Django (que
  crea un ``OneToOneField(parent_link=True)``, una hija por padre, cuando el
  ``_inherits`` de Odoo es un ``Many2one``). Mismo criterio que
  ``product_product.py`` → ``product.template`` y ``res_users.py`` →
  ``res.partner``.

  **Revierte la divergencia anterior**, que declaraba estas columnas como
  propias "igual que ya hacia ``EmailTask``". Prevalece el analisis actual
  (principio rector, Clausula 1). Ver H-API-202.
- ``body_html`` **si** es propio de ``mail.mail`` en la referencia — no se
  delega. ``mail.message.body`` es otro campo (el del chatter).
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
from addons.mail.models.mail_message import MailMessage


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

    # Enlace de _inherits (Odoo mail_message_id, mail_mail.py:46) — Many2one
    # required + cascade. NO es herencia multi-tabla (ver docstring).
    mail_message = fields.Many2one(
        MailMessage, on_delete=models.CASCADE, db_index=True,
        related_name='mails',
        help_text='Mensaje del que este correo es el envio (Odoo mail_message_id, '
                  '_inherits). subject/email_from se delegan a el.',
    )
    # content — Odoo email_to (Text), email_cc (Char), body_html (Text).
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

    # ---- Campos delegados (≙ _inherits de mail.message) ----
    # Solo lectura, como el resto de delegaciones del arbol (product_product,
    # res_users). Para escribirlos se toca el mensaje: mail.mail_message.subject.

    @property
    def subject(self):
        """El asunto del mensaje (delegado por ``_inherits``)."""
        return self.mail_message.subject

    @property
    def email_from(self):
        """El remitente del mensaje (delegado por ``_inherits``)."""
        return self.mail_message.email_from

    # ---- API de cola (≙ mail.mail create/send/process_email_queue) ----

    @classmethod
    def enqueue(cls, *, to, subject='', body_html='', email_from='',
                email_cc='', scheduled_date=None, max_attempts=3,
                failure_reason='', mail_message=None):
        """Encola un correo saliente (Odoo ``mail.mail.create`` con ``state='outgoing'``).

        Reemplaza a ``EmailTask.objects.create(...)`` como punto de entrada de la
        cola de reintento. El envio efectivo lo hace ``email_executor``.
        ``failure_reason`` preserva el error del intento previo del thread pool
        cuando ``email_executor`` reencola tras un fallo (fiel a Odoo, que
        conserva ``failure_reason`` entre reintentos).

        ``subject``/``email_from`` viven en el ``mail.message`` enlazado
        (``_inherits``): si no se pasa uno con ``mail_message``, se crea. Es lo
        que hace la referencia al crear un ``mail.mail`` sin mensaje previo.
        """
        if mail_message is None:
            mail_message = MailMessage.objects.create(
                subject=subject, email_from=email_from,
                message_type=MailMessage.TYPE_EMAIL_OUTGOING,
            )
        return cls.objects.create(
            mail_message=mail_message,
            email_to=to, body_html=body_html, email_cc=email_cc,
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
