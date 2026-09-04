"""``res.config.settings`` — los ajustes de CRM (≙ ``_inherit``).

Adaptación de ``odoo19c: addons/crm/models/res_config_settings.py`` (LGPL-3,
173 líneas) — atribución y aviso de licencia preservados (DEC-KX-03).

Porte BLOQUEADO — 2 de 25 símbolos
==================================

(25 = 8 métodos + 17 campos.)

.. list-table::
   :header-rows: 1
   :widths: 46 14 40

   * - Símbolo
     - Estado
     - Nota
   * - los **17 campos** (``:14-56``)
     - BLOQUEADO por ``ResConfigSettings`` concreto — ver "La causa".
     - #278
   * - ``_compute_crm_auto_assignment_data`` (``:58``)
     - BLOQUEADO por ``ResConfigSettings`` concreto — sus cuatro campos.
     - #278; además su rama viva depende del cron (#162)
   * - ``_onchange_crm_auto_assignment_run_datetime`` (``:73``)
     - BLOQUEADO por ``ResConfigSettings`` concreto — sus campos.
     - #278
   * - ``_compute_pls_fields`` · ``_inverse_pls_fields_str`` (``:84``, ``:96``)
     - BLOQUEADO por ``ResConfigSettings`` concreto — sus campos.
     - #278
   * - ``_compute_pls_start_date`` · ``_inverse_pls_start_date_str``
       (``:104``, ``:120``)
     - BLOQUEADO por ``ResConfigSettings`` concreto — sus campos.
     - #278
   * - ``_compute_predictive_lead_scoring_field_labels`` (``:127``)
     - BLOQUEADO por ``ResConfigSettings`` concreto — sus campos.
     - #278
   * - ``set_values`` (``:136``)
     - BLOQUEADO por ``mail.alias.mixin`` — y por sus campos.
     - #278, #161
   * - ``_get_crm_auto_assignmment_run_datetime`` (``:164``)
     - **portado**
     - función pura del intervalo; no toca ningún campo del ajuste
   * - ``action_crm_assign_leads`` (``:170``)
     - **portado**
     - sólo necesita ``crm.team``, que ya está portado

La causa del bloqueo, medida
============================

``src/addons/base/models/res_config.py:196`` declara ``ResConfigSettings`` con
``class Meta: abstract = True``. Un campo colgado sobre una clase abstracta de
Django **no genera columna**: el ajuste existiría en el registro y no en la
base, y el primer ``.save()`` fallaría por columna inexistente.

Es la **cuarta** ocurrencia del mismo bloqueo, y se declara igual que las tres
anteriores para no fabricar una cuarta forma:
``account_check_printing``, ``l10n_mx`` y ``product_expiry``. Sucesor
registrado: tarea **#278**, donde se decide la forma para los cuatro a la vez.

Qué NO es este bloqueo
======================

**No es "los ajustes de CRM no se pueden configurar".** Cinco de los diecisiete
campos son espejos de un ``config_parameter``, y ese parámetro **sí existe y sí
se lee**: ``crm.pls_fields`` lo consume ``CrmLead._pls_get_safe_fields``,
``crm.pls_start_date`` su hermano, ``crm.assignment.delay`` y
``crm.assignment.commit.bundle`` los lee ``CrmTeam._allocate_leads``, y
``crm.lead.auto.assignment`` lo lee ``_is_rule_based_assignment_activated``.
Lo bloqueado es **el panel** que los edita, no el ajuste.

Divergencia declarada
=====================

``relativedelta`` → ``timedelta``. La fuente usa
``relativedelta(**{run_interval: run_interval_number})`` con cuatro unidades:
``minutes``, ``hours``, ``days`` y ``weeks``. Ninguna es de longitud variable
—no hay ``months`` ni ``years``— así que ``timedelta`` da el **mismo**
resultado, y ``dateutil`` no es dependencia del proyecto (mismo criterio que
``digest``, ``resource_calendar_leaves`` y ``certificate``).
"""
import datetime

from django.utils import timezone

import models
from tools.translate import _

#: Las cuatro unidades que la fuente admite (``:27-28``). Todas de longitud
#: fija, que es lo que permite sustituir ``relativedelta`` por ``timedelta``.
INTERVAL_UNITS = ('minutes', 'hours', 'days', 'weeks')


def _get_crm_auto_assignmment_run_datetime(run_datetime, run_interval,
                                           run_interval_number):
    """≙ ``_get_crm_auto_assignmment_run_datetime`` (``:164-169``).

    El nombre conserva la errata de la fuente (``assignmment``, con tres emes):
    es su símbolo público y renombrarlo rompería la correspondencia que el gate
    de porte mide.
    """
    if not run_interval:
        return False
    if run_interval == 'manual':
        return run_datetime if run_datetime else False
    return timezone.now() + datetime.timedelta(
        **{run_interval: run_interval_number})


def action_crm_assign_leads():
    """≙ ``action_crm_assign_leads`` (``:170-173``).

    Reparte en todos los equipos que no se han excluido. Sin ``self``: aquí no
    hay registro de ajuste sobre el que operar (ver el bloqueo del módulo), y
    el método no lee ninguno de sus campos.
    """
    CrmTeam = models.apps.get_model('sales_team', 'CrmTeam')
    equipos = list(CrmTeam.objects.filter(assignment_optout=False))
    return CrmTeam.action_assign_leads(equipos)


def apply_crm_extensions():
    """Los dos símbolos portados son funciones de módulo, no extensiones.

    No hay ``extend_model`` que hacer: los diecisiete campos están bloqueados
    (#278) y los seis métodos que los consumen, con ellos. Los dos que sí se
    portan no cuelgan de ``res.config.settings`` porque no lo necesitan — se
    llaman por su nombre desde este módulo.
    """
    return None


__all__ = ['INTERVAL_UNITS', '_get_crm_auto_assignmment_run_datetime',
           'action_crm_assign_leads', 'apply_crm_extensions']
