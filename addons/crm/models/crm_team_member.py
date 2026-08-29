"""``crm.team.member`` — lo que ``crm`` le cuelga (≙ ``_inherit``).

Adaptación de ``odoo19c: addons/crm/models/crm_team_member.py`` (LGPL-3, 99
líneas) — atribución y aviso de licencia preservados (DEC-KX-03).

Es la mitad *por miembro* del reparto automático de iniciativas: cuánta carga
admite cada vendedor, con qué dominio filtra, y cuántas lleva ya.

Cobertura: 6 métodos + 7 campos — **13 portados, 0 bloqueados**
==============================================================

.. list-table::
   :header-rows: 1
   :widths: 42 12 46

   * - Símbolo
     - Estado
     - Nota
   * - ``assignment_enabled`` (``:19``)
     - portado
     - ``related=`` → ``property`` que lee el equipo
   * - ``assignment_domain`` (``:20``)
     - portado
     - columna; su ``tracking=True`` es del motor de ``mail.thread``
   * - ``assignment_domain_preferred`` (``:21``)
     - portado
     - ídem
   * - ``assignment_optout`` (``:22``)
     - portado
     - columna
   * - ``assignment_max`` (``:23``)
     - portado
     - columna, ``default=30`` verbatim
   * - ``lead_day_count`` (``:24``)
     - portado
     - ``compute`` sin ``store`` → ``property``
   * - ``lead_month_count`` (``:27``)
     - portado
     - ídem
   * - ``_compute_lead_day_count`` (``:31``)
     - portado
     -
   * - ``_compute_lead_month_count`` (``:38``)
     - portado
     -
   * - ``_get_lead_from_date`` (``:45``)
     - portado
     - ``_read_group`` → ``values_list().annotate(Count())``
   * - ``_constrains_assignment_domain`` (``:59``)
     - portado
     - la restricción se instala; su disparo, ver divergencia 2
   * - ``_constrains_assignment_domain_preferred`` (``:71``)
     - portado
     - ídem
   * - ``_get_assignment_quota`` (``:87``)
     - portado
     - ``float_round`` con ``HALF-UP``, verbatim

Divergencias declaradas
=======================

1. **Los tres campos calculados son ``property``, no columna** — la fuente los
   declara ``compute=`` sin ``store=True``. Vía ya establecida
   (``extend_model(propiedades=…)``).
2. **``@api.constrains`` se porta como método, no como disparo automático.**
   La restricción existe con su nombre y su cuerpo; **quién la invoca** al
   escribir es el motor de ``@api.constrains``, que este árbol resuelve caso a
   caso. Mismo desenlace declarado que ``_check_peppol_fields`` en
   ``account_edi_ubl_cii``. Los dos métodos se pueden llamar a mano y desde el
   ``save()`` de quien los necesite.
3. **``_get_lead_from_date`` recibe los pares en vez de leerlos de ``self``.**
   La fuente opera sobre un recordset (``self.crm_team_id.ids``); aquí el lote
   es explícito, que es la misma divergencia de firma que
   ``ResPartner._compute_application_statistics_hook``. Se conserva la clave
   compuesta ``(user_id, team_id)`` del resultado, que es lo que sus dos
   consumidores indexan.
4. **``active_test=False`` no tiene análogo**: este ORM no oculta los
   archivados, así que la búsqueda ya los ve. El parámetro se conserva en la
   firma —es parte del contrato de la fuente— y se documenta que aquí no
   cambia el conjunto.
"""
import datetime
from ast import literal_eval

from django.db.models import Count
from django.utils import timezone

import fields
import models
from exceptions import ValidationError
from orm.domains import to_q
from orm.model_classes import extend_model
from tools.float_utils import float_round
from tools.translate import _


def _lead_model():
    """``crm.lead`` por el registro de Django.

    Es una LLAMADA, no un statement ``import``: respeta ``no-lazy-imports``
    (misma resolución sancionada que su excepción #4) y evita el ciclo
    ``crm_team_member`` → ``crm_lead`` → ``crm_team``.
    """
    return models.apps.get_model('crm', 'CrmLead')


def _get_lead_from_date(cls, members, date_from, active_test=False):
    """≙ ``_get_lead_from_date`` (``:45-57``).

    Devuelve ``{(user_id, team_id): conteo}`` de las iniciativas abiertas desde
    ``date_from`` para los pares que ``members`` nombra.

    ``active_test`` se acepta por fidelidad de firma y no filtra nada: este ORM
    no oculta los archivados (ver divergencia 4 del módulo).
    """
    team_ids = [m.crm_team_id_id for m in members if m.crm_team_id_id]
    user_ids = [m.user_id_id for m in members if m.user_id_id]
    if not team_ids or not user_ids:
        return {}
    grouped = (_lead_model().objects
               .filter(date_open__gte=date_from,
                       team_id__in=team_ids, user_id__in=user_ids)
               .values_list('user_id', 'team_id')
               .annotate(n=Count('pk')))
    return {(user_id, team_id): n for user_id, team_id, n in grouped}


def _compute_lead_day_count(self):
    """≙ ``_compute_lead_day_count`` (``:31-36``) — las últimas 24 horas."""
    day_date = timezone.now() - datetime.timedelta(hours=24)
    counts = type(self)._get_lead_from_date([self], day_date)
    return counts.get((self.user_id_id, self.crm_team_id_id), 0)


def _compute_lead_month_count(self):
    """≙ ``_compute_lead_month_count`` (``:38-43``) — los últimos 30 días."""
    month_date = timezone.now() - datetime.timedelta(days=30)
    counts = type(self)._get_lead_from_date([self], month_date)
    return counts.get((self.user_id_id, self.crm_team_id_id), 0)


def _assignment_enabled(self):
    """≙ el campo ``assignment_enabled`` (``:19``), ``related=`` al equipo."""
    team = self.crm_team_id
    return bool(team is not None and team.assignment_enabled)


def _check_domain(self, raw, etiqueta):
    """El cuerpo común de las dos restricciones (``:59-83``).

    La fuente lo escribe dos veces, una por campo, porque su decorador
    ``@api.constrains`` va sobre un método por campo. Aquí el par de métodos se
    conserva —son dos símbolos de la fuente— y comparten este cuerpo, que es
    idéntico salvo el campo y el texto del mensaje.
    """
    try:
        domain = literal_eval(raw or '[]')
        if domain:
            # La fuente valida CORRIENDO la búsqueda (``search(domain, limit=1)``):
            # el dominio mal formado revienta al compilarse. Aquí el compilador
            # es ``orm.domains.to_q``, y ``.exists()`` fuerza el viaje a la base
            # para que un campo inexistente también levante — compilar sin
            # ejecutar dejaría pasar la mitad de los errores que la fuente ve.
            Lead = _lead_model()
            Lead.objects.filter(to_q(domain, Lead))[:1].exists()
    except Exception:
        raise ValidationError(_(
            '%(etiqueta)s del usuario %(user)s y el equipo %(team)s está mal '
            'formado', etiqueta=etiqueta,
            user=getattr(self.user_id, 'name', self.user_id_id),
            team=getattr(self.crm_team_id, 'name', self.crm_team_id_id),
        ))


def _constrains_assignment_domain(self):
    """≙ ``_constrains_assignment_domain`` (``:59-69``)."""
    _check_domain(self, self.assignment_domain, _('El dominio de asignación'))


def _constrains_assignment_domain_preferred(self):
    """≙ ``_constrains_assignment_domain_preferred`` (``:71-83``)."""
    _check_domain(self, self.assignment_domain_preferred,
                  _('El dominio de asignación preferente'))


def _get_assignment_quota(self, force_quota=False):
    """≙ ``_get_assignment_quota`` (``:87-99``).

    Cupo diario restante: el máximo de 30 días repartido por día, menos lo ya
    asignado en las últimas 24 h. ``force_quota`` devuelve el cupo entero, sin
    descontar — su semántica la fija ``CrmTeam._action_assign_leads``.
    """
    quota = float_round(self.assignment_max / 30.0, precision_digits=0,
                        rounding_method='HALF-UP')
    if force_quota:
        return quota
    return quota - self.lead_day_count


def apply_crm_extensions():
    """Cuelga los campos y los métodos. La llama ``CrmConfig.ready()``."""
    extend_model(
        'crm.team.member',
        campos={
            'assignment_domain': fields.Char(
                max_length=255, blank=True, default='',
                verbose_name='Dominio de asignación',
                help_text='Odoo assignment_domain ("Assignment Domain").',
            ),
            'assignment_domain_preferred': fields.Char(
                max_length=255, blank=True, default='',
                verbose_name='Dominio de asignación preferente',
                help_text='Odoo assignment_domain_preferred '
                          '("Preference assignment Domain").',
            ),
            'assignment_optout': fields.Boolean(
                default=False, verbose_name='Pausar asignación',
                help_text='Odoo assignment_optout ("Pause assignment").',
            ),
            'assignment_max': fields.Integer(
                default=30, verbose_name='Capacidad media (30 días)',
                help_text='Odoo assignment_max ("Average Leads Capacity '
                          '(on 30 days)").',
            ),
        },
        propiedades={
            'assignment_enabled': _assignment_enabled,
            'lead_day_count': _compute_lead_day_count,
            'lead_month_count': _compute_lead_month_count,
        },
        metodos={
            '_get_lead_from_date': classmethod(_get_lead_from_date),
            '_compute_lead_day_count': _compute_lead_day_count,
            '_compute_lead_month_count': _compute_lead_month_count,
            '_constrains_assignment_domain': _constrains_assignment_domain,
            '_constrains_assignment_domain_preferred':
                _constrains_assignment_domain_preferred,
            '_get_assignment_quota': _get_assignment_quota,
        },
    )
