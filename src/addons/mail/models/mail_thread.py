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

Alcance de este slice: ``message_post`` + suscripcion. NO se porta aun la
maquinaria ``@api`` de Odoo de: computo de destinatarios por subtipo y envio
(``_notify_thread`` — depende de la capa de notificaciones/correo, wiring
posterior), auto-suscripcion por ``_track_*`` (tracking de campos, micro-paso
siguiente), y alias de correo entrante (``mail.alias``). El contrato publico
(``message_post``/``message_subscribe``/``message_ids``) se conserva fiel.
"""
import fields  # noqa: F401  (coherencia de vocabulario del addon; el mixin no declara campos)
import models

from .mail_followers import MailFollowers
from .mail_message import MailMessage


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
                     author=None, email_from='', parent=None, subtype=None):
        """Publica un mensaje en el hilo del registro (Odoo ``message_post``).

        Crea una fila ``mail.message`` polimorfica apuntando a este registro.
        Devuelve el ``MailMessage`` creado.
        """
        return MailMessage.objects.create(
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

    @property
    def message_ids(self):
        """Mensajes del hilo, mas reciente primero (Odoo ``message_ids``)."""
        return MailMessage.objects.filter(
            model=self._mail_thread_res_model(), res_id=self.pk,
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

    @staticmethod
    def _normalize_partners(partners):
        """Acepta un partner suelto o un iterable; normaliza a lista."""
        if partners is None:
            return []
        if isinstance(partners, (list, tuple, set)):
            return list(partners)
        return [partners]
