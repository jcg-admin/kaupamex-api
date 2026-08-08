"""``mail.thread`` — mixin de chatter/actividad (Odoo ``mail``).

Portacion fiel de ``MailThread``
(``scratchpad/odoo19x/addons/mail/models/mail_thread.py:120-2621``, Odoo 19) —
el ``AbstractModel`` que Odoo hace heredar a casi todos los modelos de negocio
(``sale.order``, ``crm.lead``, ``project.task``, ``helpdesk.ticket``…) para
dotarlos de historial de mensajes (``message_post``) y seguidores
(``message_subscribe``). Parte de la familia ``mail`` (SOL-096).

Fuente Odoo community (LGPL-3): reimplementacion fiel del contrato. En Odoo es
un ``AbstractModel`` sin tabla; aqui es una **clase base abstracta de Django**
(``Meta.abstract = True``) que NO agrega columnas al modelo concreto — el hilo
se materializa en las tablas ``mail_message`` / ``mail_followers`` via el par
polimorfico (``model``/``res_model`` + ``res_id``), exactamente como Odoo, que
tampoco guarda los mensajes en la tabla del documento. Por eso aplicar el mixin
a un modelo existente (p. ej. ``support.SupportTicket``) NO genera migracion.

Alcance portado: ``message_post`` + suscripcion + **reparto a destinatarios**
(``_notify_thread`` → una ``mail.notification`` inbox por seguidor, gateada por
subtipo, fiel a Odoo) + ``message_notify`` (notificacion transitoria a partners
que no siguen el hilo). NO se porta la auto-suscripcion por ``_track_*``
(tracking de campos, micro-paso siguiente) ni el alias de correo entrante
(``mail.alias``). El contrato publico (``message_post``/``message_subscribe``/
``message_ids``/``message_notify``) se conserva fiel.
"""
import fields  # noqa: F401  (coherencia de vocabulario del addon; el mixin no declara campos)
import models

from .mail_activity import MailActivity
from .mail_followers import MailFollowers
from .mail_message import MailMessage
from .mail_notification import MailNotification
from .mail_tracking_value import MailTrackingValue


class MailThread(models.Model):
    """Mixin abstracto: dota a un modelo de hilo de mensajes + seguidores."""

    class Meta:
        abstract = True

    # --- identidad polimorfica -------------------------------------------------

    @classmethod
    def _mail_thread_res_model(cls) -> str:
        """Valor que se guarda en ``mail_message.model`` / ``mail_followers.res_model``.

        Fiel a Odoo, que guarda el ``_name`` del modelo. Aqui el identificador
        estable y unico del modelo es su label Django (``app_label.ModelName``),
        p. ej. ``"support.SupportTicket"``. Sobrescribible si un modelo quiere
        un nombre canonico distinto.
        """
        return cls._meta.label

    # --- mensajes (chatter) ----------------------------------------------------

    def message_post(self, *, body='', subject='', message_type=None,
                     author=None, email_from='', parent=None, subtype=None,
                     notify=True):
        """Publica un mensaje en el hilo del registro (Odoo ``message_post``).

        Crea una fila ``mail.message`` polimorfica apuntando a este registro y,
        si ``notify`` (default), reparte una ``mail.notification`` inbox a cada
        seguidor del registro (menos el autor), gateada por subtipo — fiel al
        ``_notify_thread`` de Odoo. Devuelve el ``MailMessage`` creado.
        """
        message = MailMessage.objects.create(
            model=self._mail_thread_res_model(),
            res_id=self.pk,
            body=body,
            subject=subject,
            message_type=message_type or MailMessage.TYPE_COMMENT,
            author=author,
            email_from=email_from,
            parent=parent,
            subtype=subtype,
            record_name=str(self),
        )
        if notify:
            self._notify_thread(message)
        return message

    def _notify_thread(self, message):
        """Reparte ``message`` a los seguidores del registro (Odoo ``_notify_thread``).

        Crea una ``mail.notification`` de canal ``inbox`` por cada seguidor
        (excluyendo al autor). El reparto se **gatea por subtipo**: un seguidor
        recibe el mensaje si no filtro subtipos, o si el subtipo del mensaje
        esta entre los que sigue — igual que Odoo enruta por
        ``mail.followers.subtype_ids``. Devuelve las notificaciones creadas.
        """
        followers = self.message_follower_ids
        author_id = message.author_id
        notifications = []
        for follower in followers.prefetch_related('subtype_ids'):
            if author_id is not None and follower.partner_id == author_id:
                continue
            if message.subtype_id is not None:
                subscribed = set(
                    follower.subtype_ids.values_list('pk', flat=True)
                )
                if subscribed and message.subtype_id not in subscribed:
                    continue
            notifications.append(MailNotification(
                message=message,
                partner_id=follower.partner_id,
                notification_type=MailNotification.TYPE_INBOX,
                notification_status=MailNotification.STATUS_SENT,
            ))
        if notifications:
            MailNotification.objects.bulk_create(notifications)
        return notifications

    def message_notify(self, partners, *, body='', subject='',
                       message_type=None, author=None):
        """Notifica a ``partners`` fuera del set de seguidores (Odoo ``message_notify``).

        Publica un ``mail.message`` (sin repartir a seguidores, ``notify=False``)
        y crea una ``mail.notification`` inbox por cada partner dado — util para
        avisos transitorios (p. ej. una asignacion) sin suscribir al partner al
        hilo. Devuelve el ``MailMessage`` creado.
        """
        message = self.message_post(
            body=body, subject=subject,
            message_type=message_type or MailMessage.TYPE_NOTIFICATION,
            author=author, notify=False,
        )
        rows = [
            MailNotification(
                message=message, partner=partner,
                notification_type=MailNotification.TYPE_INBOX,
                notification_status=MailNotification.STATUS_SENT,
            )
            for partner in self._normalize_partners(partners)
        ]
        if rows:
            MailNotification.objects.bulk_create(rows)
        return message

    @property
    def message_ids(self):
        """Mensajes del hilo, mas reciente primero (Odoo ``message_ids``)."""
        return MailMessage.objects.filter(
            model=self._mail_thread_res_model(), res_id=self.pk,
        )

    def message_post_with_template(self, template, author=None, message_type=None):
        """Renderiza una ``mail.template`` contra este registro y publica el
        mensaje resultante en el hilo (Odoo ``message_post_with_source`` /
        ``message_post_with_template``). Devuelve el ``MailMessage``.
        """
        rendered = template.render(self)
        return self.message_post(
            subject=rendered['subject'],
            body=rendered['body_html'],
            email_from=rendered['email_from'],
            message_type=message_type or MailMessage.TYPE_EMAIL,
            author=author,
        )

    # --- seguidores ------------------------------------------------------------

    def message_subscribe(self, partners, subtypes=None):
        """Suscribe uno o varios partners al registro (Odoo ``message_subscribe``).

        Idempotente: la unicidad ``(res_model, res_id, partner)`` evita
        duplicados. Devuelve la lista de ``MailFollowers`` (creados o existentes).
        """
        res_model = self._mail_thread_res_model()
        followers = []
        for partner in self._normalize_partners(partners):
            follower, _created = MailFollowers.objects.get_or_create(
                res_model=res_model, res_id=self.pk, partner=partner,
            )
            if subtypes:
                follower.subtype_ids.add(*subtypes)
            followers.append(follower)
        return followers

    def message_unsubscribe(self, partners):
        """Elimina la suscripcion de los partners dados (Odoo ``message_unsubscribe``)."""
        MailFollowers.objects.filter(
            res_model=self._mail_thread_res_model(), res_id=self.pk,
            partner__in=self._normalize_partners(partners),
        ).delete()

    @property
    def message_follower_ids(self):
        """Seguidores del registro (Odoo ``message_follower_ids``)."""
        return MailFollowers.objects.filter(
            res_model=self._mail_thread_res_model(), res_id=self.pk,
        )

    def message_is_follower(self, partner) -> bool:
        """¿El partner sigue este registro? (Odoo ``message_is_follower``)."""
        return MailFollowers.objects.filter(
            res_model=self._mail_thread_res_model(), res_id=self.pk,
            partner=partner,
        ).exists()

    # --- tracking de campos (auditoria de cambios) -----------------------------

    def message_track(self, changes, author=None):
        """Registra cambios de campo en el chatter (Odoo ``_message_track``).

        ``changes`` es un iterable de dicts con claves ``field`` (nombre),
        ``field_desc`` (etiqueta), ``field_type`` (char/integer/float/text/
        datetime/monetary/boolean), ``old`` y ``new``. Publica UN
        ``mail.message`` de tipo notification en el hilo y le adjunta un
        ``mail.tracking.value`` por cada cambio. Devuelve el mensaje (o ``None``
        si no hubo cambios). Lo que falta no es el decorador —``@api.depends``
        existe (``orm/decorators.py:23``)— sino el **motor** que lo lee: las 26
        anotaciones del arbol son inertes, 0 lectores (ver ``h-api-363``). Por
        eso el llamador invoca este metodo al detectar el cambio: mismo
        resultado, disparador explicito en vez de automatico.
        """
        changes = list(changes or [])
        if not changes:
            return None
        message = self.message_post(
            body='', message_type=MailMessage.TYPE_NOTIFICATION, author=author,
        )
        for change in changes:
            tracking = MailTrackingValue(
                message=message,
                field=change['field'],
                field_desc=change.get('field_desc', ''),
                field_type=change.get('field_type', 'char'),
            )
            tracking.set_values(change.get('old'), change.get('new'))
            tracking.save()
        return message

    # --- actividades (to-dos planificados) -------------------------------------

    def activity_schedule(self, *, activity_type=None, summary='', note='',
                          date_deadline=None, user=None):
        """Planifica una actividad sobre el registro (Odoo ``activity_schedule``).

        Crea una ``mail.activity`` polimorfica apuntando a este registro.
        Devuelve la ``MailActivity`` creada.
        """
        kwargs = dict(
            res_model=self._mail_thread_res_model(),
            res_id=self.pk,
            activity_type=activity_type,
            summary=summary,
            note=note,
            user=user,
        )
        if date_deadline is not None:
            kwargs['date_deadline'] = date_deadline
        return MailActivity.objects.create(**kwargs)

    @property
    def activity_ids(self):
        """Actividades abiertas del registro, por plazo (Odoo ``activity_ids``)."""
        return MailActivity.objects.filter(
            res_model=self._mail_thread_res_model(), res_id=self.pk,
        )

    @staticmethod
    def _normalize_partners(partners):
        """Acepta un partner suelto o un iterable; normaliza a lista."""
        if partners is None:
            return []
        if isinstance(partners, (list, tuple, set)):
            return list(partners)
        return [partners]
