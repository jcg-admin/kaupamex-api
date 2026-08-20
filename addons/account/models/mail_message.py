r"""``mail.message`` colgado por ``account`` — el rastro de auditoría restringido.

Adaptación de ``addons/account/models/mail_message.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3 — atribución y aviso de
licencia preservados, DEC-KX-03).

Qué protege este archivo
=========================

Cuando una empresa marca su libro mayor como ``restrictive_audit_trail``, la
referencia impide borrar o mutar el contenido de negocio de los mensajes del
chatter que documentan asientos ya publicados — es el rastro de auditoría
contable. El archivo hace tres cosas: (1) resuelve, por mensaje, a qué
asiento/cuenta/impuesto/socio/empresa apunta; (2) decide si ese mensaje está
protegido; (3) lanza si alguien intenta borrarlo o mutar sus campos
sensibles.

**OPERABLE desde 2026-08-20 (tarea #611) — antes estaba inerte por dos campos
ausentes.** El interruptor que activa la protección es
``res.company.restrictive_audit_trail`` y el escape que la desactiva para un
asiento nunca publicado es ``account.move.posted_before``. Cuando este archivo
se escribió, ninguno de los dos existía:

.. code-block:: text

   grep -rn "restrictive_audit_trail" src/ addons/    → 0 hits    [entonces]
   grep -n  "posted_before" addons/account/models/account_move.py → 0 hits

Los dos aterrizaron sin tocar una línea de este archivo, que es lo que su
sucesor declaró que pasaría:

- ``restrictive_audit_trail`` — ``addons/account/models/res_company.py``, vía
  ``_add_if_absent`` dentro de ``apply_account_extensions()``; su migración es
  de **base**, porque el ``app_label`` de ``ResCompany`` es base
  (``src/addons/base/migrations/0037_rescompany_restrictive_audit_trail.py``).
- ``posted_before`` — ``addons/account/models/account_move.py``, puesto en el
  mismo ``save()`` que ``state='posted'`` (``odoo19c:
  account_move.py:5714-5717``), y su migración en
  ``addons/account/migrations/0021_accountmove_posted_before.py``.

Los ``getattr(..., False)`` de ``account_audit_log_restricted`` y de
``_except_audit_log`` se conservan: eran la forma de tolerar la ausencia y hoy
son la forma de tolerar un objeto de otra clase. No cambian de comportamiento
con los campos presentes.

Los cinco resolutores ``account_audit_log_<x>_id`` — portados como propiedades
==================================================================================

La referencia los declara ``compute=`` sin ``store=True`` — no son columna,
se calculan al leer. El equivalente Django directo es una ``@property``, no
un campo con ``add_to_class`` (no hay nada que registrar en el esquema). Los
cinco comparten la misma forma: si ``self.model`` coincide, devuelven
``self.res_id``; si no, ``None``. Se implementan con una fábrica compartida
(``_related_record_id``) en vez de repetir el cuerpo cinco veces.

``account_audit_log_preview`` — portado
===========================================

Arma el resumen legible de los cambios rastreados a partir de
``tracking_value_ids`` (``MailTrackingValue``, ya con su ``related_name``
recíproco en este árbol). Sin la maquinaria de traducción de Odoo
(``self.env._``); el texto va literal en español, mismo criterio que el
resto del proyecto (``redaccion-tecnica-es.md``).

Los siete ``_search_*`` y ``DOMAINS``/``_subselect_domain`` — NO portados
============================================================================

Son el lado "buscable" de un campo ``compute=`` de Odoo: le dicen al motor de
búsqueda cómo traducir ``domain=[('account_audit_log_restricted', '=',
True)]`` en SQL, usando ``Domain``+``_search``+subselect — un sistema de
consultas componibles que este ORM no tiene (medido:
``grep -rn "class Domain\|def subselect" src/ addons/`` → 0 hits) y que aquí
no tiene consumidor (no hay caja de búsqueda de admin sobre ``mail.message``).
**Divergencia de mecanismo, no omisión**: el reemplazo Django-idiomático de
"campo buscable" es un método de manager/queryset explícito, no un parámetro
del campo. Se ofrecen dos classmethods (``find_restricted_for_move`` y
``find_by_related_record``) que cubren el caso de uso real (filtrar mensajes
por asiento) sin reconstruir el subselect genérico de la referencia.
Sucesor: construir el fraccionador ``Domain``/subselect cuando exista un
consumidor real (mismo criterio que ``account_move_line_tax_details.py``
declara para ``Query.from_clause``/``where_clause``).
"""
from addons.account.models.account_move import AccountMove
from addons.mail.models.mail_message import MailMessage
from exceptions import UserError
from orm.method_chain import chain_method
from tools.translate import _

#: Los cinco modelos que la referencia resuelve desde ``account_audit_log_*``.
#: ≙ ``odoo19c: account/models/mail_message.py:38-70``.
AUDIT_LOG_RELATED_MODELS = {
    'account_audit_log_move_id': 'account.move',
    'account_audit_log_account_id': 'account.account',
    'account_audit_log_tax_id': 'account.tax',
    'account_audit_log_company_id': 'res.company',
    'account_audit_log_partner_id': 'res.partner',
}


def _related_record_id(self, model):
    """``_compute_audit_log_related_record_id`` (``odoo19c: mail_message.py:158-162``).

    ``None`` cuando el mensaje no apunta a ``model`` — mismo criterio que la
    referencia (``(self - messages_of_related)[fname] = False``).
    """
    if self.model == model and self.res_id:
        return self.res_id
    return None


def _make_related_property(field_name, model):
    """Fábrica de las cinco propiedades ``account_audit_log_<x>_id``.

    Evita repetir el cuerpo cinco veces — el comportamiento es idéntico,
    sólo cambia el modelo objetivo.
    """
    def getter(self):
        return _related_record_id(self, model)
    getter.__name__ = field_name
    return property(getter)


def account_audit_log_preview(self):
    """≙ ``_compute_account_audit_log_preview`` (``odoo19c: mail_message.py:78-99``).

    Sólo para mensajes de notificación (``message_type == 'notification'``);
    para el resto, ``None`` — mismo recorte que ``(self - audit_messages)
    .account_audit_log_preview = False`` de la referencia.
    """
    if self.message_type != MailMessage.TYPE_NOTIFICATION:
        return None
    title = self.subject or ''
    tracking_values = list(self.tracking_value_ids.all())
    if not title and tracking_values:
        title = _('Actualizado')
    if not title and self.subtype is not None:
        title = str(self.subtype)
    lines = [title]
    for value in tracking_values:
        lines.append('%s ⇨ %s (%s)' % (
            value.get_old_value(), value.get_new_value(),
            value.field_desc or value.field,
        ))
    return '\n'.join(lines)


def account_audit_log_restricted(self):
    """≙ ``_compute_account_audit_log_restricted`` (``odoo19c: mail_message.py:141-145``).

    **Cobertura reducida, declarada.** La referencia evalúa las cinco ramas
    de ``DOMAINS`` (asiento, cuenta, impuesto, socio, empresa). Aquí se
    implementa **sólo la rama de asiento** — ``account.move`` — que es la que
    ``_except_audit_log`` consume; las otras cuatro requieren el subselect
    genérico documentado como no portado en el docstring del módulo.

    ``restrictive_audit_trail`` **ya existe** en ``ResCompany`` (tarea #611); el
    ``getattr(..., False)`` se conserva porque ``move.company`` puede ser
    ``None`` o un objeto de otra clase, no porque el campo falte.
    """
    move_id = _related_record_id(self, 'account.move')
    if move_id is None:
        return False
    move_model = self.model  # ya sabemos que es 'account.move'
    move = _resolve_move(move_id)
    if move is None:
        return False
    company = getattr(move, 'company', None)
    return bool(company is not None
                and getattr(company, 'restrictive_audit_trail', False))


def _resolve_move(move_id):
    """``self.env['account.move'].browse(...)`` — ``AccountMove`` importado al
    top del módulo (verificado sin ciclo: ``account_move.py`` no importa este
    archivo, directa ni transitivamente)."""
    return AccountMove.objects.filter(pk=move_id).first()


def _except_audit_log(self):
    """≙ ``_except_audit_log`` (``odoo19c: mail_message.py:180-186``).

    ``bypass_audit`` de la referencia viaja por ``self.env.context`` — aquí
    no hay contexto ambiente equivalente; el bypass explícito de
    ``merge_partner_automatic.py`` (que SÍ necesita saltarse esta guarda) se
    declara allá con su propia divergencia, no aquí.

    ``posted_before`` **ya existe** en ``AccountMove`` (tarea #611), y es lo que
    parte las dos ramas de la referencia: un asiento que nunca se publicó
    devuelve ``False`` y el borrado **se permite** (el ``continue`` de la
    fuente); uno publicado alguna vez cae al ``account_audit_log_restricted``.
    """
    move_id = _related_record_id(self, 'account.move')
    if move_id is not None:
        move = _resolve_move(move_id)
        if move is not None and not getattr(move, 'posted_before', False):
            return
    if account_audit_log_restricted(self):
        raise UserError(_(
            'No se puede eliminar parte de un rastro de auditoría '
            'restringido. Archive el registro en su lugar.'))


_TRACKED_FIELDS = ('res_id', 'model', 'message_type', 'subtype_id', 'subject', 'body')


def save(self, *args, **kwargs):
    """≙ ``write`` (``odoo19c: mail_message.py:188-196``).

    **Divergencia de mecanismo — ``write(vals)`` → ``save()`` sin ``vals``.**
    Django no pasa un diccionario de cambios a ``save()``; el estado nuevo
    ya está en ``self`` y el viejo hay que releerlo de la fila (mismo
    recurso que ``OnboardingOnboardingStep.save()`` usa para
    ``is_per_company``). Sólo se relee cuando ``self.pk`` existe — un
    ``INSERT`` no puede violar un rastro todavía inexistente, igual que la
    referencia sólo sobreescribe ``write`` (nunca ``create``).

    Tres disparadores, verbatim: cambiar el vínculo polimórfico o el
    tipo/subtipo del mensaje; cambiar el ``subject`` a algo distinto tras
    normalizar espacios (se tolera cualquier cambio de espaciado, la
    referencia lo dice explícitamente); o tener ``body`` no vacío cuando ya
    lo tenía (una edición del cuerpo, no su primera escritura).

    **La guarda se evalúa sobre el estado ALMACENADO, no sobre ``self``.** En
    la referencia los valores nuevos viajan en ``vals`` y el recordset todavía
    lleva los de la fila, así que ``_except_audit_log`` decide con el vínculo
    viejo. Aquí ``self`` ya está mutado cuando ``save()`` corre: preguntarle a
    ``self`` por su asiento después de asignar ``res_id = 0`` devuelve
    ``None``, la guarda no encuentra asiento y **deja pasar justo la evasión
    que existe para impedir** (``test_cant_unown_message``). Por eso el
    guardián recibe una instancia transitoria con ``model``/``res_id`` de la
    fila — los dos campos que ``_related_record_id`` consulta.
    """
    if self.pk is not None:
        previous = type(self).objects.filter(pk=self.pk).values(
            'res_id', 'model', 'message_type', 'subtype_id',
            'subject', 'body',
        ).first()
        if previous is not None:
            prev_subtype_id = previous['subtype_id']
            cur_subtype_id = self.subtype_id if self.subtype_id is not None else None
            normalized_prev_subject = ' '.join((previous['subject'] or '').split())
            normalized_cur_subject = ' '.join((self.subject or '').split())
            triggers = bool(
                previous['res_id'] != self.res_id
                or previous['model'] != self.model
                or previous['message_type'] != self.message_type
                or prev_subtype_id != cur_subtype_id
                or (self.subject and normalized_prev_subject != normalized_cur_subject)
                or (self.body and previous['body'])
            )
            if triggers:
                stored = type(self)(
                    pk=self.pk,
                    model=previous['model'],
                    res_id=previous['res_id'],
                    message_type=previous['message_type'],
                )
                stored._except_audit_log()
    # Devuelve None a propósito (semántica de relevo de chain_method): el
    # ``save()`` real de Django lo ejecuta la implementación previa.


@classmethod
def find_restricted_for_move(cls, move):
    """Reemplazo Django-idiomático de ``domain=[('account_audit_log_restricted',
    '=', True)] + [('account_audit_log_move_id', '=', move.pk)]`` — el caso
    de uso real que ``_search_account_audit_log_restricted`` serviría, sin
    reconstruir el subselect genérico (ver docstring del módulo).
    """
    company = getattr(move, 'company', None)
    if company is None or not getattr(company, 'restrictive_audit_trail', False):
        return cls.objects.none()
    return cls.objects.filter(model='account.move', res_id=move.pk)


@classmethod
def find_by_related_record(cls, model, record_id):
    """Reemplazo de ``_search_audit_log_related_record_id`` para el caso
    ``operator='in'``/``'='`` — el resto de operadores (``like``/``any``)
    de la referencia no tiene consumidor aquí (ver docstring del módulo)."""
    return cls.objects.filter(model=model, res_id=record_id)


def apply_account_extensions():
    """Cuelga el rastro de auditoría sobre ``mail.message`` — ≙ ``_inherit``.

    **Cableado** en ``AccountConfig._EXTENSIONES`` (``apps.py:57``), junto a
    ``mail_tracking_value`` (``:59``), que comparte el mismo guardián. El
    docstring anterior decía "todavía no cableado" y condicionaba el cableado a
    que aterrizaran ``restrictive_audit_trail``/``posted_before``: la primera
    mitad quedó atrás en la tanda #398, y la segunda se cumplió en la #611.
    """
    for field_name, model in AUDIT_LOG_RELATED_MODELS.items():
        if not hasattr(MailMessage, field_name):
            setattr(MailMessage, field_name, _make_related_property(field_name, model))
    if not hasattr(MailMessage, 'account_audit_log_preview'):
        MailMessage.account_audit_log_preview = property(account_audit_log_preview)
    if not hasattr(MailMessage, 'account_audit_log_restricted'):
        MailMessage.account_audit_log_restricted = property(account_audit_log_restricted)
    chain_method(MailMessage, '_except_audit_log', _except_audit_log)
    chain_method(MailMessage, 'save', save)
    MailMessage.find_restricted_for_move = find_restricted_for_move
    MailMessage.find_by_related_record = find_by_related_record
