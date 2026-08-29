"""``crm.team`` — lo que ``crm`` le cuelga (≙ ``_inherit``).

Adaptación de ``odoo19c: addons/crm/models/crm_team.py`` (LGPL-3, 759 líneas)
— atribución y aviso de licencia preservados (DEC-KX-03).

Es el motor de **reparto automático de iniciativas**: reparte las no asignadas
entre equipos ponderando por capacidad, deduplica al hacerlo, y luego reparte
las de cada equipo entre sus miembros por turno rotatorio respetando cupos.

Porte BLOQUEADO — 28 de 36 símbolos
===================================

(36 = 24 métodos + 12 campos. Los 8 bloqueados declaran su arista abajo.)

.. list-table::
   :header-rows: 1
   :widths: 40 14 46

   * - Símbolo
     - Estado
     - Nota
   * - ``use_leads`` · ``use_opportunities`` (``:23-24``)
     - portados
     - columnas
   * - ``assignment_optout`` · ``assignment_domain`` (``:29``, ``:33``)
     - portados
     - columnas
   * - ``lead_properties_definition`` (``:45``)
     - portado
     - ``PropertiesDefinition``; es el destino del ``definition=`` de
       ``CrmLead.lead_properties``
   * - ``alias_id`` (``:25``)
     - BLOQUEADO por ``mail.alias.mixin`` — la fuente sólo redefine su
       ``help``; el campo lo declara el mixin de alias de correo, que este
       árbol no tiene. Sucesor: tarea **#161**
   * - ``assignment_enabled`` · ``assignment_auto_enabled`` (``:27-28``)
     - portados
     - ``compute`` sin ``store`` → ``property``
   * - ``assignment_max`` (``:30``)
     - portado
     - ídem; suma la capacidad de sus miembros
   * - ``lead_unassigned_count`` (``:36``)
     - portado
     - ídem
   * - ``lead_all_assigned_month_count`` · ``_exceeded`` (``:38``, ``:41``)
     - portados
     - ídem
   * - ``_compute_assignment_max`` (``:47``)
     - portado
     -
   * - ``_compute_assignment_enabled`` (``:52``)
     - portado
     - **con una rama bloqueada**: el interruptor de reparto automático mira
       si el cron ``crm.ir_cron_crm_lead_assign`` está activo, y ese cron no
       está sembrado. Devuelve ``False`` — fail-closed. Sucesor: **#161**
   * - ``_compute_lead_unassigned_count`` (``:61``)
     - portado
     - ``_read_group`` → ``values_list().annotate(Count())``
   * - ``_compute_lead_all_assigned_month_count`` (``:70``)
     - portado
     -
   * - ``_onchange_use_leads_opportunities`` (``:76``)
     - BLOQUEADO por ``alias_name`` — su único efecto es vaciarlo, y el campo
       viene del mixin de alias ausente. Sucesor: **#161**
   * - ``_constrains_assignment_domain`` (``:81``)
     - portado
     - la restricción se instala; su disparo automático, ver divergencia 2
   * - ``write`` (``:94``)
     - BLOQUEADO por ``_alias_get_creation_values`` — su cuerpo entero
       reescribe ``alias_name``/``alias_defaults``. Sucesor: **#161**
   * - ``unlink`` (``:105``)
     - portado
     - como receptor de ``pre_delete``; funde las frecuencias de puntuación
       del equipo en las de "sin equipo"
   * - ``_alias_get_creation_values`` (``:147``)
     - BLOQUEADO por ``mail.alias.mixin``. Sucesor: **#161**
   * - ``_cron_assign_leads`` (``:163``)
     - portado
     -
   * - ``action_assign_leads`` (``:186``)
     - portado
     - devuelve la notificación de cliente; el ``_message_log_batch`` es la
       divergencia 4
   * - ``_action_assign_leads`` (``:222``)
     - portado
     -
   * - ``_action_assign_leads_logs`` (``:255``)
     - portado
     - los ocho mensajes, verbatim en su lógica
   * - ``_allocate_leads`` (``:311``)
     - portado
     - ver divergencia 3 (el ``commit`` por lotes)
   * - ``_allocate_leads_deduplicate`` (``:494``)
     - portado
     -
   * - ``_get_lead_to_assign_domain`` (``:546``)
     - portado
     -
   * - ``_assign_and_convert_leads`` (``:553``)
     - portado
     - el turno rotatorio con cupo y dominio preferente, entero
   * - ``action_your_pipeline`` · ``action_opportunity_forecast``
       (``:690``, ``:695``)
     - portados
     - devuelven el ``act_window`` con su XML ID, sin resolverlo
   * - ``action_open_leads`` · ``action_open_unassigned_leads``
       (``:700``, ``:708``)
     - portados
     - ídem; el ``_render_template`` del texto de ayuda es la divergencia 5
   * - ``_action_update_to_pipeline`` (``:721``)
     - portado
     -
   * - ``_compute_dashboard_button_name`` (``:743``)
     - BLOQUEADO por ``dashboard_button_name`` — el campo lo declara
       ``sales_team`` en la referencia y aquí todavía no. Sucesor: **#163**
   * - ``action_primary_channel_button`` (``:748``)
     - BLOQUEADO por ``action_primary_channel_button`` — no hay eslabón
       previo del que relevarse: ``sales_team`` no lo declara aquí.
       Sucesor: **#163**

Divergencias declaradas
=======================

1. **Los seis campos calculados son ``property``, no columna** — la fuente los
   declara ``compute=`` sin ``store=True``.
2. **``@api.constrains`` se porta como método, no como disparo automático** —
   mismo desenlace que en ``crm_team_member.py`` y en
   ``account_edi_ubl_cii``.
3. **El ``commit`` por lotes no se transcribe.** La fuente hace
   ``self.env.cr.commit()`` cada ``crm.assignment.commit.bundle`` iteraciones
   para no perder el trabajo si el cron muere a media faena. Aquí la unidad de
   transacción la fija Django (``ATOMIC_REQUESTS`` / el ``atomic`` de quien
   llama), y un ``commit`` a mano dentro de un bloque atómico rompe la
   invariante del ORM. Lo que **sí se conserva** es el troceado: el bucle lee
   ``crm.assignment.commit.bundle`` y borra los duplicados por lotes de ese
   tamaño, que es la mitad del propósito que no depende de la transacción. La
   otra mitad —el punto de guardado— es DESCONOCIDO con condición de cierre:
   se decide al cablear el cron (tarea **#162**), que es quien tiene el bucle
   largo que justifica trocear la transacción.
4. **``_message_log_batch`` no se llama.** La fuente deja nota en el hilo de
   cada equipo; ``mail.thread`` está aquí, pero ``crm.team`` **no lo adopta**
   todavía (``sales_team.CrmTeam`` no declara ``_inherit``). El texto del log
   se construye igual y se devuelve en la notificación, que es donde el
   usuario lo ve. Sucesor: **#162**.
5. **``_render_template`` del texto de ayuda no se resuelve.** ``action_open_leads``
   pide a ``ir.ui.view`` que renderice ``crm.crm_action_helper``; sin las
   vistas XML de la fuente no hay plantilla. Se devuelve la acción sin
   ``help``, que es lo que un cliente sin esa plantilla recibiría.
6. **``random.choices`` con pesos se conserva verbatim.** Es el corazón del
   reparto proporcional entre equipos y no admite sustituto determinista sin
   cambiar el resultado.
"""
import datetime
import logging
import random
import sys
from ast import literal_eval

from django.db import models as dj_models
from django.db.models import Count
from django.utils import timezone

import fields
import models
from exceptions import UserError, ValidationError
from orm.domains import to_q
from orm.environments import get_current_user, is_su
from orm.model_classes import extend_model
from tools.float_utils import float_compare, float_round
from tools.safe_eval import safe_eval
from tools.translate import _

from addons.base.models.ir_config_parameter import SystemParameter
from addons.sales_team.models.crm_team import CrmTeam

logger = logging.getLogger(__name__)

#: Los identificadores externos que la fuente consulta, verbatim.
GROUP_SALE_MANAGER = 'sales_team.group_sale_manager'
GROUP_USE_LEAD = 'crm.group_use_lead'


def _lead_model():
    """``crm.lead`` por el registro de Django — llamada, no ``import``."""
    return models.apps.get_model('crm', 'CrmLead')


def _frequency_model():
    """``crm.lead.scoring.frequency`` por el registro de Django."""
    return models.apps.get_model('crm', 'CrmLeadScoringFrequency')


def _can_commit():
    """≙ ``not modules.module.current_test`` (``:401``, ``:578``).

    Misma sustitución que ``account_document_import_mixin._can_commit``:
    ``sys.modules`` contiene ``pytest`` sólo durante una corrida de test.
    """
    return 'pytest' not in sys.modules


# ---------------------------------------------------------------------------
# Campos calculados
# ---------------------------------------------------------------------------

def _compute_assignment_max(self):
    """≙ ``_compute_assignment_max`` (``:47-50``) — la capacidad del equipo es
    la suma de la de sus miembros."""
    return sum(m.assignment_max or 0
               for m in self.crm_team_member_ids.all())


def _compute_assignment_enabled(self):
    """≙ la primera mitad de ``_compute_assignment_enabled`` (``:52-59``).

    ``assign_enabled`` sale de ``CrmLead._is_rule_based_assignment_activated``,
    que ya está portado.
    """
    return bool(_lead_model()._is_rule_based_assignment_activated())


def _compute_assignment_auto_enabled(self):
    """≙ la segunda mitad de ``_compute_assignment_enabled`` (``:54-57``).

    BLOQUEADO por ``crm.ir_cron_crm_lead_assign`` — el cron de reparto no está
    sembrado, así que no hay ``active`` que leer. Devuelve ``False``, que es lo
    mismo que la fuente devuelve cuando el cron no existe
    (``auto_assign_enabled = assign_cron.active if assign_cron else False``).
    Sucesor: tarea **#162**.
    """
    return False


def _compute_lead_unassigned_count(self):
    """≙ ``_compute_lead_unassigned_count`` (``:61-68``) — iniciativas de este
    equipo sin responsable."""
    return _lead_model().objects.filter(
        team_id=self.pk, user_id__isnull=True).count()


def _compute_lead_all_assigned_month_count(self):
    """≙ la primera mitad de ``_compute_lead_all_assigned_month_count``
    (``:70-74``) — lo asignado a sus miembros en los últimos 30 días."""
    return sum(m.lead_month_count for m in self.crm_team_member_ids.all())


def _compute_lead_all_assigned_month_exceeded(self):
    """≙ la segunda mitad (``:74``) — ¿el mes supera la capacidad?"""
    return self.lead_all_assigned_month_count > self.assignment_max


def _constrains_assignment_domain(self):
    """≙ ``_constrains_assignment_domain`` (``:81-88``).

    Valida CORRIENDO la búsqueda, como la fuente: un dominio mal formado
    revienta al compilarse, y ``.exists()`` fuerza el viaje a la base para que
    un campo inexistente también levante.
    """
    try:
        domain = literal_eval(self.assignment_domain or '[]')
        if domain:
            Lead = _lead_model()
            Lead.objects.filter(to_q(domain, Lead))[:1].exists()
    except Exception:
        raise ValidationError(_(
            'El dominio de asignación del equipo %(team)s está mal formado',
            team=self.name))


# ---------------------------------------------------------------------------
# Ciclo de vida
# ---------------------------------------------------------------------------

def merge_frequencies_on_unlink(sender, instance, **kwargs):
    """≙ ``unlink`` (``:105-141``).

    Al borrar un equipo, sus ``crm.lead.scoring.frequency`` se **funden** en
    las de "sin equipo" en vez de perderse: la puntuación predictiva se
    calibra sobre todo el histórico, y tirar el de un equipo disuelto sesgaría
    el modelo.

    Los ``0.1`` no son un umbral arbitrario: son el valor con que la tabla de
    frecuencias se inicializa, y la fuente los trata como *casi cero* con
    ``float_compare(x, 0.1, 2) != 1``. Se conserva verbatim, redondeos
    ``HALF-UP`` incluidos.

    Va en ``pre_delete`` porque necesita leer las frecuencias del equipo antes
    de que la cascada las borre — es el "antes del ``super().unlink()``" de la
    fuente.
    """
    Frequency = _frequency_model()
    frequencies = list(Frequency.objects.filter(team_id=instance.pk))
    if not frequencies:
        return
    variables = {f.variable for f in frequencies}
    existing_noteam = list(Frequency.objects.filter(
        team_id__isnull=True, variable__in=variables))

    for frequency in frequencies:
        # Saltar los valores casi-vacíos, como la fuente.
        if (float_compare(frequency.won_count, 0.1, 2) != 1
                and float_compare(frequency.lost_count, 0.1, 2) != 1):
            continue
        match = next((f for f in existing_noteam
                      if f.variable == frequency.variable
                      and f.value == frequency.value), None)
        if match is not None:
            # Quitar el 0.1 extra que la inicialización deja en la base: el
            # valor final 0 se guarda como 0.1.
            exist_won = float_round(match.won_count, precision_digits=0,
                                    rounding_method='HALF-UP')
            exist_lost = float_round(match.lost_count, precision_digits=0,
                                     rounding_method='HALF-UP')
            add_won = float_round(frequency.won_count, precision_digits=0,
                                  rounding_method='HALF-UP')
            add_lost = float_round(frequency.lost_count, precision_digits=0,
                                   rounding_method='HALF-UP')
            new_won = exist_won + add_won
            new_lost = exist_lost + add_lost
            match.won_count = new_won if float_compare(new_won, 0.1, 2) == 1 else 0.1
            match.lost_count = new_lost if float_compare(new_lost, 0.1, 2) == 1 else 0.1
            match.save()
        else:
            existing_noteam.append(Frequency.objects.create(
                lost_count=(frequency.lost_count
                            if float_compare(frequency.lost_count, 0.1, 2) == 1
                            else 0.1),
                team_id=None,
                value=frequency.value,
                variable=frequency.variable,
                won_count=(frequency.won_count
                           if float_compare(frequency.won_count, 0.1, 2) == 1
                           else 0.1),
            ))


# ---------------------------------------------------------------------------
# Reparto de iniciativas
# ---------------------------------------------------------------------------

def _cron_assign_leads(cls, force_quota=False, creation_delta_days=7):
    """≙ ``_cron_assign_leads`` (``:163-184``).

    Reparte entre todos los equipos que usan iniciativas u oportunidades y no
    se han excluido del reparto automático.
    """
    teams = list(cls.objects.filter(
        (dj_models.Q(use_leads=True) | dj_models.Q(use_opportunities=True))
        & dj_models.Q(assignment_optout=False)))
    cls._action_assign_leads(teams, force_quota=force_quota,
                             creation_delta_days=creation_delta_days)
    return True


def _action_assign_leads(cls, teams, force_quota=False, creation_delta_days=7):
    """≙ ``_action_assign_leads`` (``:222-253``).

    Dos etapas: repartir entre equipos, luego entre los miembros de cada uno.
    """
    user = get_current_user()
    autorizado = is_su() or (user is not None
                             and user.has_group(GROUP_SALE_MANAGER))
    if not autorizado:
        raise UserError(_(
            'El reparto automático de iniciativas y oportunidades está '
            'limitado a los responsables o administradores'))
    miembros = [m for team in teams for m in team.crm_team_member_ids.all()]
    logger.info(
        '### START Lead Assignment (%d teams, %d sales persons, '
        'force daily quota: %s)',
        len(teams), len(miembros), 'ON' if force_quota else 'OFF')
    teams_data = cls._allocate_leads(teams, creation_delta_days=creation_delta_days)
    logger.info('### Team repartition done. Starting salesmen assignment.')
    members_data = cls._assign_and_convert_leads(teams, force_quota=force_quota)
    logger.info('### END Lead Assignment')
    return teams_data, members_data


def action_assign_leads(cls, teams):
    """≙ ``action_assign_leads`` (``:186-220``).

    Reparto manual. Devuelve la notificación de cliente con el resumen.
    """
    teams_data, members_data = cls._action_assign_leads(
        teams, force_quota=True, creation_delta_days=0)
    logs = cls._action_assign_leads_logs(teams, teams_data, members_data)
    notif_message = ' '.join(logs)
    return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': {
            'type': 'success',
            'title': _('Iniciativas asignadas'),
            'message': notif_message,
            'next': {'type': 'ir.actions.act_window_close'},
        },
    }


def _action_assign_leads_logs(cls, teams, teams_data, members_data):
    """≙ ``_action_assign_leads_logs`` (``:255-309``).

    Los cuatro bloques de mensaje de la fuente, con su misma lógica de
    singular/plural por número de equipos.
    """
    assigned = sum(len(d['assigned']) + len(d['merged'])
                   for d in teams_data.values())
    duplicates = sum(len(d['duplicates']) for d in teams_data.values())
    members = len(members_data)
    members_assigned = sum(len(d['assigned']) for d in members_data.values())
    uno = teams[0] if len(teams) == 1 else None

    partes = []
    # 1- eliminación de duplicados
    if duplicates:
        partes.append(_('Se fusionaron %(duplicates)s iniciativas duplicadas.',
                        duplicates=duplicates))
    # 2- no se asignó nada
    if not assigned and not members_assigned:
        if uno is not None:
            if not uno.assignment_max:
                partes.append(_(
                    'No se asignó ninguna iniciativa al equipo %(team_name)s '
                    'porque no tiene capacidad. Añade capacidad a sus '
                    'vendedores.', team_name=uno.name))
            else:
                partes.append(_(
                    'No se asignó ninguna iniciativa al equipo %(team_name)s '
                    'ni a sus vendedores porque ninguna sin asignar cumple su '
                    'dominio.', team_name=uno.name))
        else:
            partes.append(_(
                'No se asignó ninguna iniciativa a ningún equipo ni vendedor. '
                'Revisa la configuración de equipos y vendedores, y las '
                'iniciativas sin asignar.'))
    # 3- reparto entre equipos
    if not assigned and members_assigned:
        if uno is not None:
            partes.append(_(
                'No se asignó ninguna iniciativa nueva al equipo '
                '%(team_name)s porque ninguna sin asignar cumple su dominio.',
                team_name=uno.name))
        else:
            partes.append(_(
                'No se asignó ninguna iniciativa nueva a los equipos porque '
                'ninguna cumple sus dominios.'))
    elif assigned:
        if uno is not None:
            partes.append(_(
                'Se asignaron %(assigned)s iniciativas al equipo '
                '%(team_name)s.', assigned=assigned, team_name=uno.name))
        else:
            partes.append(_(
                'Se repartieron %(assigned)s iniciativas entre '
                '%(team_count)s equipos.',
                assigned=assigned, team_count=len(teams)))
    # 4- reparto entre vendedores
    if not members_assigned and assigned:
        partes.append(_(
            'No se asignó ninguna iniciativa a los vendedores porque ninguna '
            'sin asignar cumple sus dominios.'))
    elif members_assigned:
        partes.append(_(
            'Se repartieron %(members_assigned)s iniciativas entre '
            '%(member_count)s vendedores.',
            members_assigned=members_assigned, member_count=members))
    return partes


def _get_lead_to_assign_domain(cls, teams):
    """≙ ``_get_lead_to_assign_domain`` (``:546-551``)."""
    return [
        ('user_id', '=', False),
        ('date_open', '=', False),
        ('team_id', 'in', [t.pk for t in teams]),
    ]


def _allocate_leads(cls, teams, creation_delta_days=7):
    """≙ ``_allocate_leads`` (``:311-492``).

    Reparte las iniciativas sin equipo ni responsable entre los equipos,
    eligiendo equipo al azar **ponderado por su capacidad** y asignando de una
    en una. Así dos equipos con dominios solapados reciben los dos, en
    proporción a su tamaño.

    ``crm.assignment.delay`` (horas) y ``crm.assignment.commit.bundle``
    (tamaño de lote) se leen igual que en la fuente. Ver la divergencia 3 del
    módulo sobre el punto de guardado.
    """
    bundle_hours_delay = float(
        SystemParameter.get_param('crm.assignment.delay', default=0) or 0)
    bundle_commit_size = int(
        SystemParameter.get_param('crm.assignment.commit.bundle', 100) or 100)
    Lead = _lead_model()

    max_create_dt = timezone.now() - datetime.timedelta(hours=bundle_hours_delay)
    duplicates_lead_cache = {}

    teams_data, population, weights = {}, [], []
    for team in teams:
        if not team.assignment_max:
            continue
        filtros = dj_models.Q(created_at__lte=max_create_dt)
        filtros &= dj_models.Q(team_id__isnull=True, user_id__isnull=True)
        filtros &= ~dj_models.Q(won_status='won')
        if creation_delta_days > 0:
            filtros &= dj_models.Q(
                created_at__gt=timezone.now()
                - datetime.timedelta(days=creation_delta_days))
        extra = literal_eval(team.assignment_domain or '[]')
        if extra:
            filtros &= to_q(extra, Lead)
        leads = list(Lead.objects.filter(filtros))
        for lead in leads:
            if lead.pk not in duplicates_lead_cache:
                duplicates_lead_cache[lead.pk] = lead._get_lead_duplicates(
                    email=lead.email_from)
        teams_data[team.pk] = {
            'team': team, 'leads': leads,
            'assigned': set(), 'merged': set(), 'duplicates': set(),
        }
        population.append(team)
        weights.append(team.assignment_max)

    global_data = {'assigned': set(), 'merged': set(), 'duplicates': set()}
    leads_done_ids, lead_unlink_ids, counter = set(), set(), 0
    while population:
        counter += 1
        team = random.choices(population, weights=weights, k=1)[0]
        team_data = teams_data[team.pk]
        team_data['leads'] = [l for l in team_data['leads']
                          if l.pk not in leads_done_ids]
        if not team_data['leads']:
            indice = population.index(team)
            population.pop(indice)
            weights.pop(indice)
            continue
        candidate_lead = team_data['leads'][0]
        assign_res = cls._allocate_leads_deduplicate(
            team, [candidate_lead], duplicates_cache=duplicates_lead_cache)
        for key in ('assigned', 'merged', 'duplicates'):
            team_data[key].update(assign_res[key])
            leads_done_ids.update(assign_res[key])
            global_data[key].update(assign_res[key])
        lead_unlink_ids.update(assign_res['duplicates'])
        # Se conserva el TROCEADO de la fuente (borrar duplicados por lotes);
        # el punto de guardado no — ver divergencia 3.
        if counter % bundle_commit_size == 0:
            Lead.objects.filter(pk__in=lead_unlink_ids).delete()
            lead_unlink_ids = set()

    Lead.objects.filter(pk__in=lead_unlink_ids).delete()

    logger.info('## Assigned %s leads',
                len(global_data['assigned']) + len(global_data['merged']))
    for pk, team_data in teams_data.items():
        logger.info('## Assigned %s leads to team %s',
                    len(team_data['assigned']) + len(team_data['merged']), pk)
        logger.info(
            '\tLeads: direct assign %s / merge result %s / duplicates merged: %s',
            team_data['assigned'], team_data['merged'], team_data['duplicates'])
    return teams_data


def _allocate_leads_deduplicate(cls, team, leads, duplicates_cache=None):
    """≙ ``_allocate_leads_deduplicate`` (``:494-544``).

    Clasifica las iniciativas en asignables directas y grupos de duplicados,
    pone el equipo en unas y otras, y funde cada grupo de duplicados en una
    sola. Deduplicar aquí reduce el número de iniciativas antes de repartirlas
    entre vendedores.
    """
    Lead = _lead_model()
    duplicates_cache = duplicates_cache if duplicates_cache is not None else {}

    leads_assigned = []
    leads_done_ids, leads_merged_ids, leads_dup_ids = set(), set(), set()
    leads_dups = {}
    for lead in leads:
        if lead.pk in leads_done_ids:
            continue
        if lead.pk not in duplicates_cache:
            duplicates_cache[lead.pk] = lead._get_lead_duplicates(
                email=lead.email_from)
        lead_duplicates = list(duplicates_cache[lead.pk])
        if len(lead_duplicates) > 1:
            leads_dups[lead.pk] = (lead, lead_duplicates)
            leads_done_ids.add(lead.pk)
            leads_done_ids.update(d.pk for d in lead_duplicates)
        else:
            leads_assigned.append(lead)
            leads_done_ids.add(lead.pk)

    # El equipo se pone en las directas Y en las cabeza de grupo, para que lo
    # conserven si ganan la fusión.
    a_asignar = leads_assigned + [par[0] for par in leads_dups.values()]
    if a_asignar:
        Lead._handle_salesmen_assignment(a_asignar, user_ids=None,
                                         team_id=team.pk)

    for lead, lead_duplicates in leads_dups.values():
        merged = Lead._merge_opportunity(
            lead_duplicates, user_id=False, team_id=False,
            auto_unlink=False, max_length=0)
        leads_dup_ids.update(d.pk for d in lead_duplicates
                             if d.pk != getattr(merged, 'pk', None))
        if merged is not None:
            leads_merged_ids.add(merged.pk)

    return {
        'assigned': {l.pk for l in leads_assigned},
        'merged': leads_merged_ids,
        'duplicates': leads_dup_ids,
    }


def _assign_and_convert_leads(cls, teams, force_quota=False):
    """≙ ``_assign_and_convert_leads`` (``:553-687``).

    Reparte entre los miembros de cada equipo las iniciativas ya asignadas a
    él, y las convierte en oportunidades. Turno rotatorio: se ordena a los
    miembros por cupo, se asigna al primero cuyo dominio acepte la iniciativa,
    y se le manda al final de la cola si le queda cupo (o se le saca si no).

    Dos vueltas, como la fuente: primero las que cumplen el **dominio
    preferente** de algún miembro, luego el resto.
    """
    Lead = _lead_model()
    result_data = {}
    commit_bundle_size = int(
        SystemParameter.get_param('crm.assignment.commit.bundle', 100) or 100)
    teams_with_members = [t for t in teams if t.crm_team_member_ids.exists()]
    if not teams_with_members:
        return result_data
    all_members = [m for t in teams for m in t.crm_team_member_ids.all()]
    quota_per_member = {
        m.pk: m._get_assignment_quota(force_quota=force_quota)
        for m in all_members
    }
    counter = 0

    domain = cls._get_lead_to_assign_domain(teams_with_members)
    leads_per_team = {}
    for lead in Lead.objects.filter(to_q(domain, Lead)):
        leads_per_team.setdefault(lead.team_id_id, []).append(lead)

    def _assign_lead(lead, members, member_leads, assign_lst, optional_lst=None):
        """≙ el ``_assign_lead`` interno de la fuente (``:594-616``)."""
        member_found = next(
            (m for m in members
             if any(l.pk == lead.pk for l in member_leads.get(m.pk, ()))),
            None)
        if member_found is None:
            return None
        lead.convert_opportunity(lead.partner_id,
                                 user_ids=[member_found.user_id_id])
        result_data[member_found.pk]['assigned'].append(lead)
        assign_lst.remove(member_found)
        if optional_lst is not None and member_found in optional_lst:
            optional_lst.remove(member_found)
        quota_per_member[member_found.pk] -= 1
        if quota_per_member[member_found.pk] > 0:
            assign_lst.append(member_found)
            if optional_lst is not None:
                optional_lst.append(member_found)
        return member_found

    for team in teams_with_members:
        leads_to_assign = leads_per_team.get(team.pk, [])
        members_to_assign = sorted(
            (m for m in team.crm_team_member_ids.all()
             if not m.assignment_optout and quota_per_member.get(m.pk, 0) > 0),
            key=lambda m: (quota_per_member.get(m.pk, 0), random.random()),
            reverse=True)
        if not members_to_assign:
            continue
        result_data.update({
            m.pk: {'assigned': [], 'quota': quota_per_member[m.pk]}
            for m in members_to_assign
        })
        to_assign = list(leads_to_assign)

        members_wpref = [
            m for m in members_to_assign
            if m.assignment_domain_preferred
            and literal_eval(m.assignment_domain_preferred or '')
        ]
        preferred_leads_per_member = {}
        for m in members_wpref:
            combinado = (literal_eval(m.assignment_domain or '[]')
                         + literal_eval(m.assignment_domain_preferred))
            q = to_q(combinado, Lead) if combinado else dj_models.Q()
            aceptadas = set(Lead.objects.filter(q).values_list('pk', flat=True))
            preferred_leads_per_member[m.pk] = [
                l for l in to_assign if l.pk in aceptadas]
        preferred_leads = []
        vistos = set()
        for lista in preferred_leads_per_member.values():
            for lead in lista:
                if lead.pk not in vistos:
                    vistos.add(lead.pk)
                    preferred_leads.append(lead)
        assigned_preferred = []

        # Primera vuelta: las preferentes, siempre con prioridad.
        for lead in sorted(preferred_leads,
                           key=lambda l: (-(l.probability or 0), l.pk)):
            counter += 1
            if _assign_lead(lead, members_wpref, preferred_leads_per_member,
                            members_to_assign, members_wpref) is None:
                continue
            assigned_preferred.append(lead)

        # Segunda vuelta: el resto.
        ya = {l.pk for l in assigned_preferred}
        to_assign = [l for l in to_assign if l.pk not in ya]
        leads_per_member = {}
        for m in members_to_assign:
            dominio = literal_eval(m.assignment_domain or '[]')
            if dominio:
                aceptadas = set(Lead.objects.filter(to_q(dominio, Lead))
                                .values_list('pk', flat=True))
                leads_per_member[m.pk] = [l for l in to_assign
                                          if l.pk in aceptadas]
            else:
                leads_per_member[m.pk] = list(to_assign)
        for lead in sorted(to_assign,
                           key=lambda l: (-(l.probability or 0), l.pk)):
            counter += 1
            _assign_lead(lead, members_to_assign, leads_per_member,
                         members_to_assign)

        logger.info(
            'Team %s: Assigned %s leads based on preference, on a potential '
            'of %s (limited by quota)',
            team.name, len(assigned_preferred), len(preferred_leads))

    logger.info('Assigned %s leads to %s salesmen',
                sum(len(r['assigned']) for r in result_data.values()),
                len(result_data))
    return result_data


# ---------------------------------------------------------------------------
# Acciones
# ---------------------------------------------------------------------------

def _action_update_to_pipeline(cls, action):
    """≙ ``_action_update_to_pipeline`` (``:721-741``).

    Si el usuario no pertenece a ningún equipo se le muestra el primero, con un
    texto de ayuda que explica por qué. El texto diverge según sea responsable.
    """
    user = get_current_user()
    user_team_id = getattr(getattr(user, 'sale_team_id', None), 'pk', None)
    if not user_team_id:
        primero = cls.objects.first()
        user_team_id = primero.pk if primero is not None else None
        action['help'] = (
            "<p class='o_view_nocontent_smiling_face'>%s</p><p>"
            % _('Crear una oportunidad'))
        if user_team_id:
            if user is not None and user.has_group(GROUP_SALE_MANAGER):
                action['help'] += '<p>%s</p>' % _(
                    'Como no perteneces a ningún equipo de ventas, se te '
                    'muestra el pipeline del primer equipo por defecto. Para '
                    'trabajar con el CRM deberías unirte a un equipo.')
            else:
                action['help'] += '<p>%s</p>' % _(
                    'Como no perteneces a ningún equipo de ventas, se te '
                    'muestra el pipeline del primer equipo por defecto. Para '
                    'trabajar con el CRM deberías unirte a un equipo.')
    try:
        action['context'] = safe_eval(action.get('context') or '{}',
                                      {'uid': getattr(user, 'pk', None)})
    except (NameError, ValueError):
        action['context'] = {}
    return action


def action_your_pipeline(cls):
    """≙ ``action_your_pipeline`` (``:690-693``)."""
    return cls._action_update_to_pipeline({
        'type': 'ir.actions.act_window',
        'xml_id': 'crm.crm_lead_action_pipeline',
        'res_model': 'crm.lead',
        'context': '{}',
    })


def action_opportunity_forecast(cls):
    """≙ ``action_opportunity_forecast`` (``:695-698``)."""
    return cls._action_update_to_pipeline({
        'type': 'ir.actions.act_window',
        'xml_id': 'crm.crm_lead_action_forecast',
        'res_model': 'crm.lead',
        'context': '{}',
    })


def action_open_leads(self):
    """≙ ``action_open_leads`` (``:700-706``).

    Sin ``help``: su texto sale de renderizar la plantilla
    ``crm.crm_action_helper``, que no existe sin las vistas XML de la fuente
    (divergencia 5 del módulo).
    """
    return {
        'type': 'ir.actions.act_window',
        'xml_id': 'crm.crm_case_form_view_salesteams_opportunity',
        'res_model': 'crm.lead',
        'context': '{}',
    }


def action_open_unassigned_leads(self):
    """≙ ``action_open_unassigned_leads`` (``:708-719``)."""
    action = self.action_open_leads()
    context_str = action.get('context', '{}')
    if context_str:
        try:
            context = safe_eval(context_str, {
                'active_id': self.pk,
                'uid': getattr(get_current_user(), 'pk', None),
            })
        except (NameError, ValueError):
            context = {}
    else:
        context = {}
    action['context'] = context | {'search_default_unassigned': True}
    return action


def apply_crm_extensions():
    """Cuelga campos, propiedades, métodos y el receptor. La llama ``ready()``."""
    extend_model(
        'crm.team',
        campos={
            'use_leads': fields.Boolean(
                default=False, verbose_name='Iniciativas',
                help_text='Odoo use_leads ("Leads"): calificar las peticiones '
                          'entrantes antes de convertirlas en oportunidad.',
            ),
            'use_opportunities': fields.Boolean(
                default=True, verbose_name='Pipeline',
                help_text='Odoo use_opportunities ("Pipeline").',
            ),
            'assignment_optout': fields.Boolean(
                default=False, verbose_name='Excluir del reparto automático',
                help_text='Odoo assignment_optout ("Skip auto assignment").',
            ),
            'assignment_domain': fields.Char(
                max_length=255, blank=True, default='',
                verbose_name='Dominio de asignación',
                help_text='Odoo assignment_domain ("Assignment Domain"): '
                          'filtro adicional al buscar iniciativas sin asignar.',
            ),
            'lead_properties_definition': fields.PropertiesDefinition(
                null=True, blank=True, verbose_name='Propiedades de iniciativa',
                help_text='Odoo lead_properties_definition ("Lead Properties"): '
                          'define las propiedades libres de crm.lead.',
            ),
        },
        propiedades={
            'assignment_enabled': _compute_assignment_enabled,
            'assignment_auto_enabled': _compute_assignment_auto_enabled,
            'assignment_max': _compute_assignment_max,
            'lead_unassigned_count': _compute_lead_unassigned_count,
            'lead_all_assigned_month_count':
                _compute_lead_all_assigned_month_count,
            'lead_all_assigned_month_exceeded':
                _compute_lead_all_assigned_month_exceeded,
        },
        metodos={
            '_compute_assignment_max': _compute_assignment_max,
            '_compute_assignment_enabled': _compute_assignment_enabled,
            '_compute_lead_unassigned_count': _compute_lead_unassigned_count,
            '_compute_lead_all_assigned_month_count':
                _compute_lead_all_assigned_month_count,
            '_constrains_assignment_domain': _constrains_assignment_domain,
            '_cron_assign_leads': classmethod(_cron_assign_leads),
            'action_assign_leads': classmethod(action_assign_leads),
            '_action_assign_leads': classmethod(_action_assign_leads),
            '_action_assign_leads_logs': classmethod(_action_assign_leads_logs),
            '_allocate_leads': classmethod(_allocate_leads),
            '_allocate_leads_deduplicate': classmethod(_allocate_leads_deduplicate),
            '_get_lead_to_assign_domain': classmethod(_get_lead_to_assign_domain),
            '_assign_and_convert_leads': classmethod(_assign_and_convert_leads),
            'action_your_pipeline': classmethod(action_your_pipeline),
            'action_opportunity_forecast': classmethod(action_opportunity_forecast),
            '_action_update_to_pipeline': classmethod(_action_update_to_pipeline),
            'action_open_leads': action_open_leads,
            'action_open_unassigned_leads': action_open_unassigned_leads,
        },
    )
    dj_models.signals.pre_delete.connect(
        merge_frequencies_on_unlink, sender=CrmTeam,
        dispatch_uid='crm.merge_frequencies_on_unlink',
    )
