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

**Bloqueado por pieza concreta ausente — medido antes de escribir este
archivo.** El interruptor que activa la protección es
``res.company.restrictive_audit_trail`` y el escape que la desactiva para un
asiento nunca publicado es ``account.move.posted_before``:

.. code-block:: text

   grep -rn "restrictive_audit_trail" src/ addons/    → 0 hits
   grep -n  "posted_before" addons/account/models/account_move.py → 0 hits

Ninguno de los dos existe en este árbol (``ResCompany``:
``src/addons/base/models/res_company.py``; ``AccountMove``:
``addons/account/models/account_move.py``, 22-134 líneas, no declara el
campo). Por tanto la protección queda **estructuralmente completa e inerte**:
compila, se cuelga, y ``account_audit_log_restricted`` es siempre ``False``
hasta que esos dos campos aterricen. Sucesor: portar
``restrictive_audit_trail``/``posted_before`` (Bloque de campos de
``res.company``/``account.move`` — mismo hueco que ``product.py`` documenta
para ``income_account_id``) y entonces esta guarda queda operable sin tocar
este archivo.

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

    Con ``restrictive_audit_trail`` ausente (ver docstring del módulo),
    ``getattr(company, 'restrictive_audit_trail', False)`` devuelve siempre
    ``False`` — la guarda queda inerte, no rota.
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

    ``posted_before`` ausente (ver docstring del módulo): ``getattr(move,
    'posted_before', False)`` — un asiento sin el campo se trata como "nunca
    publicado", que es la rama que la referencia usa para **permitir** el
    borrado (``continue``). Es la lectura conservadora: no bloquea por un
    campo que no existe.
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
                self._except_audit_log()
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

    **Todavía no cableado** en ``AccountConfig._EXTENSIONES`` (mismo estado
    declarado que los cuatro ``account_analytic_*`` — ver
    ``account/models/__init__.py``). Sucesor: cablear junto con
    ``mail_tracking_value.py`` (comparten el mismo guardián) cuando
    ``restrictive_audit_trail``/``posted_before`` aterricen.
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
