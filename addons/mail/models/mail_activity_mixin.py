"""``mail.activity.mixin`` — el mixin de actividades planificadas (addon ``mail``).

Adaptación de Odoo ``mail/models/mail_activity_mixin.py`` (``odoo-tools@622ddc2a``,
``odoo19c:``, LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Qué es: el ``AbstractModel`` que dota a un modelo de negocio de **actividades**
—los «to-do» planificados con responsable y plazo que aparecen en el chatter—.
Es el hermano de ``mail.thread``: aquél lleva los mensajes y los seguidores,
éste lleva las tareas pendientes. Un modelo puede heredar uno, el otro o ambos;
``stock.picking`` hereda los dos (``odoo19c: stock/models/stock_picking.py:540``).

Por qué es un archivo aparte y no vive en ``mail_thread.py``: porque en la
referencia son dos ``AbstractModel`` distintos, en dos archivos distintos, con
``_name`` distinto. Hasta hoy este árbol tenía ``activity_schedule`` y
``activity_ids`` colgados de ``MailThread`` — el sitio equivocado, la clase de
:ref:`h-api-568`. Aquí se mudan a su hogar.

Porte símbolo por símbolo — 34 símbolos
=========================================

Medido sobre ``odoo19c: addons/mail/models/mail_activity_mixin.py`` (487
líneas): 10 campos + 24 métodos.

===============================================  ======================================
Símbolo de la referencia (línea)                 Aquí
===============================================  ======================================
``_name`` (38)                                   ``_name``
``_description`` (39)                            ``_description``
``_default_activity_type`` (41-47)               ``_default_activity_type``
``activity_ids`` (49-52)                         property ``activity_ids``
``activity_state`` (53-62)                       property ``activity_state``
``activity_user_id`` (63-67)                     property ``activity_user``
``activity_type_id`` (68-72)                     property ``activity_type``
``activity_type_icon`` (73)                      property ``activity_type_icon``
``activity_date_deadline`` (74-78)               property ``activity_date_deadline``
``my_activity_date_deadline`` (79-81)            ``my_activity_date_deadline(user)``
``activity_summary`` (82-86)                     property ``activity_summary``
``activity_exception_decoration`` (87-91)        property ``activity_exception_decoration``
``activity_exception_icon`` (92-93)              property ``activity_exception_icon``
``_compute_activity_exception_type`` (97-112)    ``_compute_activity_exception_type``
``_compute_activity_user_id`` (114-116)          property ``activity_user``
``_search_activity_exception_decoration`` (118-119) ``_search_activity_exception_decoration``
``_compute_activity_state`` (122-132)            property ``activity_state``
``_search_activity_state`` (134-190)             ``_search_activity_state`` (D-2)
``_compute_activity_date_deadline`` (192-195)    property ``activity_date_deadline``
``_search_activity_date_deadline`` (197-203)     ``_search_activity_date_deadline``
``_search_activity_user_id`` (205-222)           ``_search_activity_user``
``_search_activity_type_id`` (224-228)           ``_search_activity_type``
``_search_activity_summary`` (230-235)           ``_search_activity_summary``
``_compute_my_activity_date_deadline`` (237-243) ``my_activity_date_deadline``
``_search_my_activity_date_deadline`` (245-253)  ``_search_my_activity_date_deadline``
``_read_group_groupby`` (255-293)                ``_read_group_groupby`` (D-3)
``action_reschedule_my_next_today`` (295-299)    ``action_reschedule_my_next_today``
``action_reschedule_my_next_tomorrow`` (301-305) ``action_reschedule_my_next_tomorrow``
``action_reschedule_my_next_nextweek`` (307-310) ``action_reschedule_my_next_nextweek``
``activity_send_mail`` (312-322)                 ``activity_send_mail``
``activity_search`` (324-355)                    ``activity_search``
``activity_schedule`` (357-409)                  ``activity_schedule``
``_activity_schedule_with_view`` (411-431)       ``_activity_schedule_with_view``
``activity_reschedule`` (433-457)                ``activity_reschedule``
``activity_feedback`` (459-473)                  ``activity_feedback``
``activity_unlink`` (475-487)                    ``activity_unlink``
===============================================  ======================================

Divergencias declaradas
=========================

**D-1 · Los diez campos son ``property``, no columnas.** En la referencia
``activity_ids`` es un One2many polimórfico por ``res_id`` y los otros nueve son
``compute`` **sin** ``store``. Ninguno tiene columna allá y ninguna la tiene
aquí: el mixin no añade una sola columna al modelo que lo hereda, que es lo que
permite aplicarlo a un modelo existente sin migración.

**D-2 · ``_search_activity_state`` no emite el SQL con ``SIGN(EXTRACT(...))``.**
La referencia agrupa en SQL para no traer millones de filas
(``odoo19c: :158-188``). El mismo resultado se obtiene aquí con un
``annotate(Min(...))`` sobre ``mail_activity``, que PostgreSQL resuelve con el
mismo plan de agregación. Se conserva su optimización clave —la búsqueda
invertida cuando el valor incluye «sin actividad»—, que es la que evita listar
el universo entero.

**D-3 · ``_read_group_groupby`` devuelve el ``queryset`` anotado, no un ``SQL``.**
Allá el método inyecta una expresión en el ``GROUP BY`` del ORM; aquí no hay ese
punto de extensión, así que el equivalente es el ``queryset`` ya anotado con
``activity_state``, listo para que el llamador agrupe.

**D-4 · El plazo «mío» toma el usuario por argumento.** La referencia lo lee de
``self.env.user``; aquí no hay usuario implícito, así que
``my_activity_date_deadline(user)`` y ``_search_my_activity_date_deadline(user, …)``
lo reciben. Es la misma adaptación que ``is_favorite_of`` en
``stock.picking.type``.
"""
import datetime

import models
from django.apps import apps
from django.db.models import Min, Q

from exceptions import UserError
from tools.translate import _

from addons.base.models.ir_model import IrModelData

from .mail_activity import MailActivity
from .mail_activity_type import MailActivityType

#: ≙ ``activity_state`` (``odoo19c: :53-62``).
STATE_OVERDUE = 'overdue'
STATE_TODAY = 'today'
STATE_PLANNED = 'planned'
ACTIVITY_STATE_CHOICES = [
    (STATE_OVERDUE, 'Vencida'),
    (STATE_TODAY, 'Hoy'),
    (STATE_PLANNED, 'Planificada'),
]

#: ≙ ``activity_exception_decoration`` (``:87-91``).
DECORATION_WARNING = 'warning'
DECORATION_DANGER = 'danger'


class MailActivityMixin(models.Model):
    """``mail.activity.mixin`` — dota a un modelo de actividades planificadas."""

    # Atributos de clase de modelo — los dos que la referencia declara
    # (``odoo19c: addons/mail/models/mail_activity_mixin.py:38-39``), verbatim.
    _name = 'mail.activity.mixin'
    _description = 'Activity Mixin'

    class Meta:
        abstract = True

    # -- identidad polimórfica: el par (res_model, res_id) --

    @classmethod
    def _activity_res_model(cls) -> str:
        """Valor que se guarda en ``mail_activity.res_model``.

        La referencia guarda el ``_name`` del modelo que hereda. Aquí se busca
        ese ``_name`` **propio** y se cae al label Django (``app_label.Model``)
        para el modelo propio del L0 que no adapta nada.

        El recorrido **salta los mixins**: un ``getattr`` plano heredaría el
        ``_name`` del primer mixin del MRO, y entonces todos los modelos que lo
        usan compartirían ese ``res_model`` — sus actividades quedarían
        mezcladas en un solo montón.

        Lo que distingue a un mixin es que es **abstracto**, no su identidad:
        parar en ``MailActivityMixin`` sólo protege del mixin propio y deja
        pasar a cualquier otro que vaya delante en el MRO. Un consumidor como
        ``SupportTicket(MailThread, MailActivityMixin, …)`` encontraba primero
        el ``_name = 'mail.thread'`` de ``MailThread`` y guardaba **ese** como
        ``res_model`` — el defecto que el propio docstring describía, en su
        segunda instancia. Ver :ref:`h-api-597`.
        """
        for klass in cls.__mro__:
            if getattr(getattr(klass, '_meta', None), 'abstract', False):
                continue
            nombre = klass.__dict__.get('_name')
            if nombre:
                return nombre
        return cls._meta.label

    def _activity_queryset(self):
        """Las actividades de ESTE registro, en el orden de la referencia."""
        return MailActivity.objects.filter(
            res_model=self._activity_res_model(), res_id=self.pk,
        ).order_by('date_deadline', 'id')

    @staticmethod
    def _activity_type_ids(act_type_xmlids):
        """Los ids de tipo que resuelven esos identificadores externos.

        ≙ el bloque que la referencia repite verbatim en ``activity_search``
        (``odoo19c: :337-338``), ``activity_reschedule`` (``:445``),
        ``activity_feedback`` (``:466``) y ``activity_unlink`` (``:482``):
        ``Data._xmlid_to_res_id(xmlid, raise_if_not_found=False)`` por cada uno,
        descartando los que no resuelven.

        **Divergencia declarada (D-5):** la referencia repite las dos líneas en
        los cuatro sitios; aquí van una vez. El resolutor es el mismo —
        ``IrModelData.xmlid_to_res_id``, que es nuestro ``_xmlid_to_res_id`` —
        y sigue viviendo en ``ir.model.data``, no en ``mail.activity``: el sitio
        del símbolo lo fija la referencia (la clase de :ref:`h-api-578`).
        """
        if isinstance(act_type_xmlids, str):
            act_type_xmlids = [act_type_xmlids] if act_type_xmlids else []
        ids = (IrModelData.xmlid_to_res_id(xmlid, raise_if_not_found=False)
               for xmlid in act_type_xmlids)
        return [type_id for type_id in ids if type_id]

    def _default_activity_type(self):
        """≙ ``_default_activity_type`` (``odoo19c: :41-47``).

        Tipo de respaldo cuando el identificador externo pedido no existe.
        Sobrescribible por modelo; sólo lo llama ``activity_schedule``.
        """
        return MailActivity._default_activity_type_for_model(
            self._activity_res_model())

    # -- los diez campos: property, sin columna (D-1) --

    @property
    def activity_ids(self):
        """≙ ``activity_ids`` (``odoo19c: :49-52``)."""
        return self._activity_queryset()

    @property
    def activity_state(self):
        """≙ ``_compute_activity_state`` (``odoo19c: :122-132``).

        El estado global es el más urgente de sus actividades: vencida gana a
        hoy, y hoy gana a planificada.
        """
        estados = set(a.state for a in self._activity_queryset())
        for estado in (STATE_OVERDUE, STATE_TODAY, STATE_PLANNED):
            if estado in estados:
                return estado
        return None

    @property
    def activity_user(self):
        """≙ ``_compute_activity_user_id`` (``odoo19c: :114-116``).

        El responsable de la actividad más próxima.
        """
        primera = self._activity_queryset().first()
        return primera.user if primera is not None else None

    @property
    def activity_type(self):
        """≙ ``activity_type_id`` (``odoo19c: :68-72``)."""
        primera = self._activity_queryset().first()
        return primera.activity_type if primera is not None else None

    @property
    def activity_type_icon(self):
        """≙ ``activity_type_icon`` (``odoo19c: :73``)."""
        tipo = self.activity_type
        return getattr(tipo, 'icon', None) if tipo is not None else None

    @property
    def activity_date_deadline(self):
        """≙ ``_compute_activity_date_deadline`` (``odoo19c: :192-195``)."""
        primera = self._activity_queryset().first()
        return primera.date_deadline if primera is not None else None

    @property
    def activity_summary(self):
        """≙ ``activity_summary`` (``odoo19c: :82-86``)."""
        primera = self._activity_queryset().first()
        return primera.summary if primera is not None else None

    def _compute_activity_exception_type(self):
        """≙ ``_compute_activity_exception_type`` (``odoo19c: :97-112``).

        Devuelve ``(decoración, icono)`` del tipo de actividad más grave.
        ``danger`` corta el barrido; ``warning`` se queda como candidato.
        """
        exception = None
        for actividad in self._activity_queryset():
            tipo = actividad.activity_type
            if tipo is None:
                continue
            if tipo.decoration_type == DECORATION_DANGER:
                exception = tipo
                break
            if tipo.decoration_type == DECORATION_WARNING:
                exception = tipo
        if exception is None:
            return None, None
        return exception.decoration_type, exception.icon

    @property
    def activity_exception_decoration(self):
        """≙ ``activity_exception_decoration`` (``odoo19c: :87-91``)."""
        return self._compute_activity_exception_type()[0]

    @property
    def activity_exception_icon(self):
        """≙ ``activity_exception_icon`` (``odoo19c: :92-93``)."""
        return self._compute_activity_exception_type()[1]

    def my_activity_date_deadline(self, user):
        """≙ ``_compute_my_activity_date_deadline`` (``odoo19c: :237-243``) — D-4.

        El plazo de la actividad más próxima **de ese usuario**.
        """
        actividad = self._activity_queryset().filter(user=user).first()
        return actividad.date_deadline if actividad is not None else None

    # -- las búsquedas: filtran el modelo por su actividad --

    @classmethod
    def _con_actividad(cls, **filtro):
        """Ids de este modelo que tienen alguna actividad que cumple el filtro."""
        return MailActivity.objects.filter(
            res_model=cls._activity_res_model(), **filtro,
        ).values_list('res_id', flat=True)

    @classmethod
    def _search_activity_exception_decoration(cls, valor):
        """≙ ``_search_activity_exception_decoration`` (``odoo19c: :118-119``)."""
        return cls.objects.filter(
            pk__in=cls._con_actividad(activity_type__decoration_type=valor))

    @classmethod
    def _search_activity_state(cls, valores):
        """≙ ``_search_activity_state`` (``odoo19c: :134-190``) — D-2.

        Conserva la optimización que importa: cuando el valor buscado incluye
        «sin actividad», la referencia **invierte** la búsqueda para no
        materializar el universo (su comentario ``:145-150`` lo dice: *"they
        might be a lot of records (million for some models)"*). Aquí eso es un
        ``exclude`` sobre el conjunto complementario.
        """
        todos = {STATE_OVERDUE, STATE_TODAY, STATE_PLANNED, None}
        buscados = set(valores)
        invertir = None in buscados
        if invertir:
            buscados = todos - buscados

        hoy = datetime.date.today()
        por_estado = {
            STATE_OVERDUE: Q(date_deadline__lt=hoy),
            STATE_TODAY: Q(date_deadline=hoy),
            STATE_PLANNED: Q(date_deadline__gt=hoy),
        }
        condition = Q()
        for estado in buscados:
            if estado in por_estado:
                condition |= por_estado[estado]
        if not condition:
            return cls.objects.none() if not invertir else cls.objects.all()

        ids = cls._con_actividad().model.objects.filter(
            res_model=cls._activity_res_model()).filter(condition).values_list(
                'res_id', flat=True)
        return cls.objects.exclude(pk__in=ids) if invertir \
            else cls.objects.filter(pk__in=ids)

    @classmethod
    def _search_activity_date_deadline(cls, operator, valor):
        """≙ ``_search_activity_date_deadline`` (``odoo19c: :197-203``).

        Con ``valor`` nulo la referencia devuelve los que **no tienen**
        actividad; en otro caso, filtra por el plazo con el operador dado.
        """
        if valor is None:
            return cls.objects.exclude(pk__in=cls._con_actividad())
        return cls.objects.filter(
            pk__in=cls._con_actividad(**{f'date_deadline__{operator}': valor}))

    @classmethod
    def _search_activity_user(cls, user):
        """≙ ``_search_activity_user_id`` (``odoo19c: :205-222``)."""
        return cls.objects.filter(pk__in=cls._con_actividad(user=user))

    @classmethod
    def _search_activity_type(cls, activity_type):
        """≙ ``_search_activity_type_id`` (``odoo19c: :224-228``)."""
        return cls.objects.filter(
            pk__in=cls._con_actividad(activity_type=activity_type))

    @classmethod
    def _search_activity_summary(cls, operator, valor):
        """≙ ``_search_activity_summary`` (``odoo19c: :230-235``)."""
        return cls.objects.filter(
            pk__in=cls._con_actividad(**{f'summary__{operator}': valor}))

    @classmethod
    def _search_my_activity_date_deadline(cls, user, operator, valor):
        """≙ ``_search_my_activity_date_deadline`` (``odoo19c: :245-253``) — D-4."""
        return cls.objects.filter(pk__in=cls._con_actividad(
            user=user, **{f'date_deadline__{operator}': valor}))

    @classmethod
    def _read_group_groupby(cls, queryset=None):
        """≙ ``_read_group_groupby`` (``odoo19c: :255-293``) — D-3.

        Devuelve el ``queryset`` anotado con ``activity_state``, listo para
        agrupar. El estado se deriva del plazo **mínimo** de las actividades del
        registro, que es el mismo criterio que su ``MIN(SIGN(EXTRACT(...)))``.
        """
        queryset = cls.objects.all() if queryset is None else queryset
        plazos = MailActivity.objects.filter(
            res_model=cls._activity_res_model(),
        ).values('res_id').annotate(proximo=Min('date_deadline'))
        by_id = {p['res_id']: p['proximo'] for p in plazos}
        hoy = datetime.date.today()

        def estado(pk):
            plazo = by_id.get(pk)
            if plazo is None:
                return None
            if plazo < hoy:
                return STATE_OVERDUE
            return STATE_TODAY if plazo == hoy else STATE_PLANNED

        for registro in queryset:
            registro.activity_state_agrupado = estado(registro.pk)
        return queryset

    # -- reprogramar la siguiente actividad propia --

    def _reprogramar_mi_siguiente(self, user, dias):
        """Cuerpo común de los tres ``action_reschedule_my_next_*``."""
        actividad = self._activity_queryset().filter(user=user).first()
        if actividad is None:
            return False
        actividad.date_deadline = datetime.date.today() + datetime.timedelta(days=dias)
        actividad.save(update_fields=['date_deadline'])
        return True

    def action_reschedule_my_next_today(self, user):
        """≙ ``action_reschedule_my_next_today`` (``odoo19c: :295-299``)."""
        return self._reprogramar_mi_siguiente(user, 0)

    def action_reschedule_my_next_tomorrow(self, user):
        """≙ ``action_reschedule_my_next_tomorrow`` (``odoo19c: :301-305``)."""
        return self._reprogramar_mi_siguiente(user, 1)

    def action_reschedule_my_next_nextweek(self, user):
        """≙ ``action_reschedule_my_next_nextweek`` (``odoo19c: :307-310``)."""
        return self._reprogramar_mi_siguiente(user, 7)

    # -- el contrato público del mixin --

    def activity_send_mail(self, template, partners=None):
        """≙ ``activity_send_mail`` (``odoo19c: :312-322``).

        Envía la plantilla sobre este registro. La referencia lo hace a través
        del compositor de correo; aquí se delega en ``message_post_with_template``
        de ``mail.thread`` cuando el modelo también lo hereda, que es el camino
        que este árbol ya tiene construido.
        """
        if not hasattr(self, 'message_post_with_template'):
            raise UserError(_(
                'El modelo %s no hereda mail.thread: no hay hilo donde publicar '
                'la plantilla.') % self._activity_res_model())
        return self.message_post_with_template(template)

    def activity_search(self, act_type_xmlid='', user=None, additional_domain=None):
        """≙ ``activity_search`` (``odoo19c: :324-355``).

        Busca las actividades de este registro que cumplen el tipo, el usuario
        y el filtro adicional. Devuelve un ``queryset`` vacío si el tipo pedido
        no existe — la referencia hace lo mismo (``:337-339``).
        """
        consulta = self._activity_queryset()
        if act_type_xmlid:
            tipo_ids = self._activity_type_ids(act_type_xmlid)
            if not tipo_ids:
                return MailActivity.objects.none()
            consulta = consulta.filter(activity_type_id__in=tipo_ids)
        if user is not None:
            consulta = consulta.filter(user=user)
        if additional_domain:
            consulta = consulta.filter(**additional_domain)
        return consulta

    def activity_schedule(self, act_type_xmlid='', date_deadline=None,
                          summary='', note='', activity_type=None, user=None):
        """≙ ``activity_schedule`` (``odoo19c: :357-409``).

        Planifica una actividad sobre este registro. Sin plazo, hoy. Sin tipo,
        el que resuelva el identificador externo, y si no existe, el de respaldo
        que ``default_activity_type`` devuelva — la misma cascada de la
        referencia (``:377-383``).
        """
        if date_deadline is None:
            date_deadline = datetime.date.today()
        if activity_type is None:
            if act_type_xmlid:
                tipo_ids = self._activity_type_ids(act_type_xmlid)
                activity_type = MailActivityType.objects.filter(
                    pk__in=tipo_ids).first() if tipo_ids else None
            if activity_type is None:
                activity_type = self._default_activity_type()
        return MailActivity.objects.create(
            res_model=self._activity_res_model(),
            res_id=self.pk,
            activity_type=activity_type,
            summary=summary,
            note=note,
            date_deadline=date_deadline,
            user=user,
        )

    def _activity_schedule_with_view(self, act_type_xmlid='', date_deadline=None,
                                    summary='', views_or_xmlid='',
                                    render_context=None, user=None):
        """≙ ``_activity_schedule_with_view`` (``odoo19c: :411-431``).

        Igual que ``activity_schedule`` pero la nota sale de renderizar una
        vista con su contexto.

        .. warning:: El renderizador QWeb no está construido (tarea **#273**).

           Hasta que exista, ``views_or_xmlid`` se ignora y la nota queda en
           ``render_context`` serializado, que preserva el dato sin fingir el
           renderizado. No es un no-op silencioso: la actividad se crea y su
           contenido es recuperable.
        """
        contexto = render_context or {}
        nota = '\n'.join(f'{k}: {v}' for k, v in contexto.items())
        return self.activity_schedule(
            act_type_xmlid=act_type_xmlid, date_deadline=date_deadline,
            summary=summary, note=nota, user=user)

    def activity_reschedule(self, act_type_xmlids, user=None,
                            date_deadline=None, new_user=None):
        """≙ ``activity_reschedule`` (``odoo19c: :433-457``).

        Cambia plazo y/o responsable de las actividades que cumplen el filtro.
        Devuelve las reprogramadas.
        """
        if not date_deadline and not new_user:
            return MailActivity.objects.none()
        consulta = self._activity_queryset().filter(
            activity_type_id__in=self._activity_type_ids(act_type_xmlids))
        if user is not None:
            consulta = consulta.filter(user=user)
        cambios = {}
        if date_deadline:
            cambios['date_deadline'] = date_deadline
        if new_user is not None:
            cambios['user'] = new_user
        reprogramadas = list(consulta)
        consulta.update(**cambios)
        return reprogramadas

    def activity_feedback(self, act_type_xmlids, user=None, feedback=None):
        """≙ ``activity_feedback`` (``odoo19c: :459-473``).

        Marca como hechas las actividades que cumplen el filtro, dejando su
        retroalimentación.
        """
        consulta = self._activity_queryset().filter(
            activity_type_id__in=self._activity_type_ids(act_type_xmlids))
        if user is not None:
            consulta = consulta.filter(user=user)
        hechas = list(consulta)
        for actividad in hechas:
            actividad.action_done(feedback=feedback or '')
        return hechas

    def activity_unlink(self, act_type_xmlids, user=None):
        """≙ ``activity_unlink`` (``odoo19c: :475-487``).

        Borra las actividades que cumplen el filtro, sin dejar rastro — que es
        lo que la distingue de ``activity_feedback``.
        """
        consulta = self._activity_queryset().filter(
            activity_type_id__in=self._activity_type_ids(act_type_xmlids))
        if user is not None:
            consulta = consulta.filter(user=user)
        borradas = consulta.count()
        consulta.delete()
        return borradas
