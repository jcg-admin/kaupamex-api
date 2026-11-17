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

from django.db import models as dj_models
from tools.translate import _

from addons.base.models.ir_model import IrModelData

from .mail_followers import MailFollowers
from .mail_message import MailMessage
from .mail_message_subtype import MailMessageSubtype
from .mail_template import MailTemplate
from .mail_notification import MailNotification
from .mail_tracking_value import MailTrackingValue


class MailThread(models.Model):
    """Mixin abstracto: dota a un modelo de hilo de mensajes + seguidores."""

    # Atributos de clase de modelo — los SEIS de ORM que la referencia declara
    # (``odoo19c: addons/mail/models/mail_thread.py:127-132``), verbatim con su
    # comentario. Los otros dos ``_`` de esa cabecera NO son atributos de ORM
    # y por eso no van aquí: ``_CUSTOMER_HEADERS_LIMIT_COUNT`` es una
    # constante de módulo y ``_Attachment`` un ``namedtuple`` — la distinción
    # de tres vías que fija ``atributos-de-clase-de-modelo.md``.
    _name = 'mail.thread'
    _description = 'Email Thread'
    _mail_flat_thread = True  # link orphan messages to the first message
    # subscribe customer when being in post recipients
    _mail_thread_customer = False
    # access required on the document to post on it
    _mail_post_access = 'write'
    # Must be set for the models that can be created by alias
    _primary_email = 'email'

    class Meta:
        abstract = True

    # --- identidad polimorfica -----------------------------------------------

    @classmethod
    def _mail_thread_res_model(cls) -> str:
        """Valor que se guarda en ``mail_message.model`` /
        ``mail_followers.res_model``.

        La referencia guarda el ``_name`` del modelo que hereda. Aquí se busca
        ese ``_name`` **propio** y se cae al label Django (``app_label.Model``)
        cuando el modelo no declara ninguno.

        El recorrido **salta todo mixin abstracto**: desde que este mixin
        declara su propio ``_name = 'mail.thread'``, un ``getattr`` plano lo
        heredaría y **todos** los modelos que lo usan compartirían un mismo
        ``res_model``, mezclando sus hilos en una sola conversación.

        Lo que distingue a un mixin es que es **abstracto**, no su identidad.
        Parar en ``MailThread`` por nombre sólo protege de este mixin y deja
        pasar a cualquier otro que vaya delante en el MRO: un consumidor como
        ``SupportTicket(MailActivityMixin, MailThread, …)`` habría encontrado
        primero el ``_name = 'mail.activity.mixin'`` del otro. Hoy los dos
        consumidores declaran ``MailThread`` primero, así que el defecto está
        latente y no activo — pero es el mismo que :ref:`h-api-597` registra en
        ``mail_activity_mixin.py``, donde sí se disparó.
        """
        for klass in cls.__mro__:
            if getattr(getattr(klass, '_meta', None), 'abstract', False):
                continue
            nombre = klass.__dict__.get('_name')
            if nombre:
                return nombre
        return cls._meta.label

    # --- mensajes (chatter) --------------------------------------------------

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
        """Reparte ``message`` a los seguidores del registro (Odoo
        ``_notify_thread``).

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
        """Notifica a ``partners`` fuera del set de seguidores (Odoo
        ``message_notify``).

        Publica un ``mail.message`` (sin repartir a seguidores,
        ``notify=False``) y crea una ``mail.notification`` inbox por cada
        partner dado — util para
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

    def message_post_with_template(self, template, author=None,
                                   message_type=None):
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

    # --- seguidores ----------------------------------------------------------

    def message_subscribe(self, partners, subtypes=None):
        """Suscribe uno o varios partners al registro (Odoo
        ``message_subscribe``).

        Idempotente: la unicidad ``(res_model, res_id, partner)`` evita
        duplicados. Devuelve la lista de ``MailFollowers`` (creados o
        existentes).
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
        """Elimina la suscripcion de los partners dados (Odoo
        ``message_unsubscribe``)."""
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

    # --- tracking de campos (auditoria de cambios) ---------------------------

    def _message_track(self, changes, author=None):
        """Registra cambios de campo en el chatter (Odoo ``_message_track``).

        ``changes`` es un iterable de dicts con claves ``field`` (nombre),
        ``field_desc`` (etiqueta), ``field_type`` (char/integer/float/text/
        datetime/monetary/boolean), ``old`` y ``new``. Publica UN
        ``mail.message`` de tipo notification en el hilo y le adjunta un
        ``mail.tracking.value`` por cada cambio. Devuelve el mensaje (o
        ``None``
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

    # --- actividades: NO viven aquí ------------------------------------------
    #
    # ``activity_schedule`` y ``activity_ids`` estuvieron colgados de esta
    # clase hasta 2026-08-14. Era el sitio equivocado —la clase de
    # :ref:`h-api-568`—: la referencia los declara en ``mail.activity.mixin``,
    # un ``AbstractModel`` distinto, en su propio archivo
    # (``odoo19c: mail/models/mail_activity_mixin.py``).
    # Un modelo que quiera actividades hereda ``MailActivityMixin``; uno que
    # quiera ambas cosas hereda los dos, como hace ``stock.picking``.

    @staticmethod
    def _normalize_partners(partners):
        """Acepta un partner suelto o un iterable; normaliza a lista."""
        if partners is None:
            return []
        if isinstance(partners, (list, tuple, set)):
            return list(partners)
        return [partners]

    def message_post_with_source(self, source_ref, *, render_values=None,
                                 message_type='notification',
                                 subtype_xmlid=False, subtype_id=False,
                                 **kwargs):
        """Publica un mensaje en el hilo con el cuerpo de una fuente.

        ≙ ``message_post_with_source`` (``odoo19c: addons/mail/models/
        mail_thread.py:2621-2711``). La fuente es una ``mail.template`` o una
        vista; el subtipo es ``subtype_xmlid`` si se da y, si no hay ninguno,
        ``mail.mt_note``. Devuelve los ``MailMessage`` publicados.

        **La vista no se dibuja con QWeb** (DEC-EM-01, DEC-AF-08): su cuerpo
        lo compone el constructor registrado con su xmlid
        (:func:`register_source_body`), con el mismo contenido.

        **La rama de plantilla no tiene compositor**: la fuente crea un
        ``mail.compose.message`` y llama a ``_action_send_mail``, que aquí no
        existen. Se renderiza la plantilla (``MailTemplate.render``) y se
        publica su cuerpo y asunto; los destinatarios, adjuntos y el envío de
        correo de esa rama siguen abiertos en TASK-API-0121.
        """
        template, view = self._get_source_from_ref(source_ref)
        self._raise_for_invalid_parameters(
            set(kwargs), forbidden_names=_SOURCE_FORBIDDEN_NAMES)
        if subtype_xmlid:
            subtype_id = IrModelData._xmlid_to_res_id(subtype_xmlid)
        if not subtype_id:
            subtype_id = IrModelData._xmlid_to_res_id('mail.mt_note')
        subtype = (MailMessageSubtype.objects.filter(pk=subtype_id).first()
                   if subtype_id else None)
        messages = []
        # Un modelo de Django con el mixin es una fila; un ``BaseModel``, un
        # recordset que se recorre como en la fuente.
        records = self if isinstance(self, models.BaseModel) else (self,)
        for record in records:
            if template:
                rendered = template.render(record)
                messages.append(record.message_post(
                    body=rendered['body_html'], subject=rendered['subject'],
                    message_type=message_type, subtype=subtype, **kwargs))
            else:
                messages.append(record.message_post(
                    body=view(record, dict(render_values or {})),
                    message_type=message_type, subtype=subtype, **kwargs))
        return messages

    def _get_source_from_ref(self, source_ref):
        """La pareja ``(template, view)`` de una fuente; sólo una se da.

        ≙ ``_get_source_from_ref`` (``odoo19c: :3097-3150``). La vista es el
        constructor de cuerpo registrado con su xmlid; un xmlid sin fila en
        ``ir.model.data`` pero con constructor es una vista, porque la fila
        de una vista QWeb no se siembra en este árbol.
        """
        template, view = False, False
        if isinstance(source_ref, dj_models.Model):
            model_name = (getattr(type(source_ref), '_name', None)
                          or source_ref._meta.label)
            if isinstance(source_ref, MailTemplate):
                template = source_ref
            elif model_name == 'ir.ui.view':
                xmlid = source_ref.get_external_id().get(source_ref.pk)
                view = SOURCE_BODIES.get(xmlid)
                if view is None:
                    raise ValueError(_(
                        'The view %(svalue)s has no registered body: QWeb '
                        'views are not rendered here (DEC-EM-01)',
                        svalue=source_ref))
            else:
                raise ValueError(_(
                    'Invalid template or view source record %(svalue)s, is '
                    '%(model)s instead', svalue=source_ref, model=model_name))
        elif isinstance(source_ref, str):
            res_model, res_id = IrModelData._xmlid_to_res_model_res_id(
                source_ref)
            if res_model is None and source_ref in SOURCE_BODIES:
                view = SOURCE_BODIES[source_ref]
            elif res_model is None:
                raise ValueError(_(
                    'Invalid template or view source Xml ID %(source_ref)s '
                    'does not exist anymore', source_ref=source_ref))
            elif res_model == 'mail.template':
                template = MailTemplate.objects.get(pk=res_id)
            elif res_model == 'ir.ui.view' and source_ref in SOURCE_BODIES:
                view = SOURCE_BODIES[source_ref]
            else:
                raise ValueError(_(
                    'Invalid template or view source reference %(svalue)s, '
                    'is %(model)s instead', svalue=source_ref,
                    model=res_model))
        else:
            raise ValueError(_(
                'Invalid template or view source %(svalue)s (type '
                '%(stype)s), should be a record or an XMLID',
                svalue=source_ref, stype=type(source_ref)))
        return template, view

    def _raise_for_invalid_parameters(self, parameter_names,
                                      forbidden_names=None,
                                      restricting_names=None):
        """≙ ``_raise_for_invalid_parameters`` (``odoo19c: :3197-3214``)."""
        conflicting_names = set()
        if forbidden_names:
            conflicting_names = parameter_names & forbidden_names
        elif restricting_names:
            conflicting_names = parameter_names - restricting_names
        if conflicting_names:
            raise ValueError(_(
                'Those values are not supported when posting or notifying: '
                '%(param_names)s', param_names=', '.join(conflicting_names)))


#: Los constructores de cuerpo que sustituyen a las vistas QWeb, por el xmlid
#: de la vista. QWeb no se porta (DEC-EM-01, DEC-AF-08): cada addon que en la
#: fuente publica con una vista registra aquí la función que compone el mismo
#: marcado en Python, el mecanismo que ya usa ``crm_lead._merge_log_summary``.
#: Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
#: message-post-with-source.md``.
SOURCE_BODIES = {}

#: ≙ ``forbidden_names`` de ``message_post_with_source`` (``:2658-2665``).
_SOURCE_FORBIDDEN_NAMES = frozenset({
    'body', 'composition_mode', 'incoming_email_cc', 'incoming_email_to',
    'model', 'res_id', 'outgoing_email_to', 'values',
})


def register_source_body(xmlid):
    """Registra el constructor del cuerpo de la vista ``xmlid``.

    El constructor recibe ``(record, render_values)`` y devuelve el marcado
    que la vista QWeb de la fuente produciría con ese contexto.
    """
    def decorator(builder):
        SOURCE_BODIES[xmlid] = builder
        return builder
    return decorator
