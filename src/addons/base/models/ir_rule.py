"""``ir.rule`` — reglas de registro: acceso a nivel de fila.

Adaptación de ``odoo/addons/base/models/ir_rule.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 279 líneas). Una regla declara un
dominio que acota **qué filas** de un modelo ve un usuario, por operación
(leer, escribir, crear, borrar).

Relación con el aislamiento L3 de este árbol (DEC-AISL-04 §4)
=============================================================

``ir.rule`` ES el aislamiento por fila: el filtrado multi-company es **dato**
(reglas con dominio ``[('company_id', 'in', company_ids)]``, como
``account_security.xml:131`` en la referencia), no código. El manager
codificado que lo implementaba antes (``CompanyScopedManager``) y el motor
paralelo ``authz.record_rules`` se retiraron en este pase — eran dos
expresiones redundantes de la misma idea.

``RuleScopedManager`` (abajo) es el punto de integración con el queryset — el
rol de ``_check_access`` en la referencia (``odoo19c: odoo/orm/models.py:4114``:
``if not self.env.su and (result := self._check_access(operation))`` — bajo
``su`` las reglas NO se evalúan). La autorización por capacidad (DEC-11) no
cambia: capa distinta.

La combinación de dominios, que es el corazón del archivo
=========================================================

``_compute_domain`` implementa una regla asimétrica que es fácil de portar al
revés, así que se conserva literal:

- las reglas **globales** (sin grupo) se combinan con **AND** — toda global
  restringe siempre;
- las reglas **de grupo** se combinan entre sí con **OR** — pertenecer a
  cualquiera de los grupos habilita su dominio;
- y el ``OR`` resultante se añade al conjunto de globales, es decir, se
  combina con **AND** contra ellas.

En consecuencia: una regla global **quita** filas que ninguna regla de grupo
puede devolver, mientras que dos grupos **suman** el acceso de cada uno.
Invertir cualquiera de los dos operadores da un sistema que o bien no
restringe nada, o bien deniega todo a quien esté en dos grupos.

Una regla **sin dominio** (``domain_force`` vacío) equivale a *verdadero*, no
a *falso*: no restringe. Y una regla de grupo cuyo grupo el usuario **no**
tiene se descarta antes de evaluarse — no aporta ni restringe.

Qué NO se porta, con su medición
================================

- **``model_id`` como FK a ``ir.model``.** **Actualizado** (porte de
  ``ir_model.py``): ``grep -rn "^class IrModel\b" src/`` → **1** clase (el
  ancla de columna 0 distingue una definición de una cita indentada — ver
  H-API-141). [PROVEN] La medición de **0** que sostenía el ``Char`` dejó de
  ser cierta al portar ``ir_model``; se corrige en vez de dejarla envejecer.
  El campo **sigue** siendo ``model_name`` (``Char`` indexado) con el label
  del modelo Django: cambiarlo a FK migra esta tabla y va en su propio pase,
  igual que ``ir_filters.action_id``. Mismo estado en ``ir_filters.model_id``
  e ``ir_attachment.res_model``.
- **(SUPERADO en este pase)** ``domain_force`` ya SÍ se evalúa. La decisión
  explícita que este archivo exigía se tomó (tarea #31, con autorización del
  ejecutor de copiar la implementación de la referencia): el evaluador es
  ``tools.safe_eval`` (adaptación acotada del ``odoo/tools/safe_eval.py`` de
  la fuente — AST whitelist en vez de opcodes, más estrecho, ver su
  docstring) y el contexto es ``eval_context()``, fiel a ``_eval_context``
  (``odoo19c: addons/base/models/ir_rule.py:38-51``):
  ``{'user', 'company_ids', 'company_id'}`` — *"company_ids contains the ids
  of the activated companies … filtered and trusted"* (el canal del dato,
  DEC-AISL-04). El dominio resultante se traduce a ``Q`` con
  ``orm.domains.to_q``.
- **``ormcache`` sobre ``_compute_domain``** y ``_compute_domain_keys`` — la
  caché por usuario y valores de contexto del ORM de Odoo. Se deja el cómputo
  puro; cachearlo depende del punto de integración con el queryset.
- **``_make_access_error``** (68 líneas) — compone el mensaje de error con los
  registros que fallan y sugiere a quién pedir acceso, leyendo ``ir.model.data``
  y la capa de vistas. ``_get_failing`` sí se porta, que es la parte que
  responde *qué* filas fallan.
"""
import logging

import fields
import models

from addons.base.models.res_groups import ResGroups
from addons.base.models.timestamped_mixin import TimeStampedModel
from orm import domains
from orm.environments import get_current_companies, get_current_company, is_su
from tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)

#: Las cuatro operaciones — ``_MODES`` de la referencia.
MODES = ('read', 'write', 'create', 'unlink')


class IrRule(TimeStampedModel):
    """Regla de registro: acota qué filas ve un usuario (``ir.rule``)."""

    name = fields.Char(
        max_length=255, blank=True, default='', verbose_name='Nombre')
    active = fields.Boolean(
        default=True, verbose_name='Activa',
        help_text='Desmarcar desactiva la regla sin borrarla (Odoo active).',
    )
    model_name = fields.Char(
        max_length=120, db_index=True, verbose_name='Modelo',
        help_text="Odoo model_id. Label del modelo, p.ej. 'sale.SaleOrder'.",
    )
    groups = fields.Many2many(
        ResGroups, blank=True, related_name='rule_groups',
        db_table='rule_group_rel', verbose_name='Grupos',
        help_text='Sin grupos, la regla es global y restringe siempre.',
    )
    domain_force = fields.Text(
        blank=True, default='', verbose_name='Dominio',
        help_text='Expresión del dominio. Vacío equivale a verdadero: no '
                  'restringe. Este archivo NO la evalúa — ver el docstring.',
    )
    perm_read = fields.Boolean(default=True, verbose_name='Leer')
    perm_write = fields.Boolean(default=True, verbose_name='Escribir')
    perm_create = fields.Boolean(default=True, verbose_name='Crear')
    perm_unlink = fields.Boolean(default=True, verbose_name='Borrar')

    class Meta:
        db_table = 'ir_rule'
        ordering = ['id']
        verbose_name = 'Regla de registro'
        verbose_name_plural = 'Reglas de registro'

    def __str__(self):
        return self.name or f'{self.model_name} #{self.pk}'

    @property
    def global_(self):
        """¿Es global? — sin grupos, restringe a todo el mundo.

        El nombre lleva guion bajo porque ``global`` es palabra reservada; en
        la referencia el campo se llama ``global`` y se declara fuera de la
        clase por ese mismo motivo (``ir_rule.py:276``).
        """
        return not self.groups.exists()

    @classmethod
    def get_rules(cls, model_name, mode='read', group_ids=()):
        """Reglas que aplican a ``model_name`` para ``mode`` y esos grupos.

        Fiel a ``_get_rules``: activas, con el permiso de la operación, y **o
        bien globales o bien de alguno de los grupos del usuario**. Ordenadas
        por id, como allá.

        :raises ValueError: si ``mode`` no es una de las cuatro operaciones —
            la referencia también revienta en vez de asumir ``read``.
        """
        if mode not in MODES:
            raise ValueError('Modo inválido: %r' % (mode,))
        qs = cls.objects.filter(
            model_name=model_name, active=True, **{f'perm_{mode}': True})
        return qs.filter(
            models.Q(groups__isnull=True) | models.Q(groups__in=list(group_ids))
        ).distinct().order_by('id')

    @classmethod
    def eval_context(cls, user=None):
        """El contexto de evaluación de los dominios — ``_eval_context``.

        Fiel a la fuente (``odoo19c: addons/base/models/ir_rule.py:38-51``):
        ``company_ids`` son las compañías ACTIVADAS por el usuario — *"These
        companies are filtered and trusted"* — es decir, el canal del dato
        (``orm.environments``, DEC-AISL-04), ya validado contra lo permitido.
        ``company_id`` es la actual (la primera activada).

        ``user`` se pasa desde el llamador que lo tenga (una vista con
        ``request.user``); un dominio que use ``user.id`` sin usuario en
        contexto revienta al evaluarse, que es preferible a inventar uno.
        """
        return {
            'user': user,
            'company_ids': list(get_current_companies()),
            'company_id': get_current_company(),
        }

    def build_domain(self, eval_context=None):
        """Evalúa ``domain_force`` y lo traduce a un filtro ``Q``.

        Fiel a ``_compute_domain`` de la fuente:
        ``Domain(safe_eval(rule.domain_force, eval_context)) if
        rule.domain_force else Domain.TRUE`` (``odoo19c:
        addons/base/models/ir_rule.py:164``). Una regla sin ``domain_force``
        es verdadera —no restringe—; aquí ``Domain`` es ``orm.domains.to_q``.
        """
        if not self.domain_force:
            return models.Q()
        domain = safe_eval(self.domain_force, eval_context or {})
        return domains.to_q(domain)

    @classmethod
    def compute_domain(cls, model_name, mode='read', group_ids=(),
                       eval_context=None):
        """Combina las reglas aplicables en un solo filtro — ``_compute_domain``.

        Globales con AND; de grupo con OR entre sí; y el OR resultante, AND
        contra las globales. Invertir cualquiera de los dos operadores rompe
        el modelo: ver el docstring del módulo.
        """
        if eval_context is None:
            eval_context = cls.eval_context()
        rules = cls.get_rules(model_name, mode=mode, group_ids=group_ids)
        user_groups = set(group_ids)

        global_domains = []
        group_domains = []
        for rule in rules:
            rule_groups = set(rule.groups.values_list('pk', flat=True))
            if rule_groups and not (rule_groups & user_groups):
                # Regla de un grupo que el usuario no tiene: ni aporta ni
                # restringe, se descarta antes de evaluarla.
                continue
            domain = rule.build_domain(eval_context)
            if rule_groups:
                group_domains.append(domain)
            else:
                global_domains.append(domain)

        if group_domains:
            combined = group_domains[0]
            for domain in group_domains[1:]:
                combined |= domain
            global_domains.append(combined)

        result = models.Q()
        for domain in global_domains:
            result &= domain
        return result

    @classmethod
    def get_failing(cls, queryset, mode='read', group_ids=(),
                    eval_context=None):
        """Las filas de ``queryset`` que las reglas **no** dejan pasar.

        Fiel a ``_get_failing``: se aplica el dominio combinado y se devuelve
        la diferencia, que es lo que el llamador necesita para explicar el
        rechazo.
        """
        model_name = queryset.model._meta.label
        domain = cls.compute_domain(
            model_name, mode=mode, group_ids=group_ids,
            eval_context=eval_context)
        allowed = queryset.filter(domain).values_list('pk', flat=True)
        return queryset.exclude(pk__in=list(allowed))


class RuleScopedManager(models.Manager):
    """Aplica las record rules del modelo al queryset — el rol de
    ``_check_access`` (``odoo19c: odoo/orm/models.py:4114``).

    Sustituye al ``CompanyScopedManager`` codificado (DEC-AISL-04 §4): el
    filtrado ya no vive en el manager sino en las reglas almacenadas
    (``ir_rule``); este manager sólo las evalúa y las aplica. Semántica de la
    referencia, verbatim:

    - ``su`` activo → sin filtro. En la fuente ``_check_access`` ni se llama
      bajo ``su`` (``if not self.env.su and (result := ...)``).
    - Reglas de grupo cuyos grupos el llamador no pasa → descartadas
      (``compute_domain``). Las reglas multi-company canónicas son globales
      (``account_security.xml`` no les declara grupos), así que aplican sin
      ``group_ids``.
    - **Sin regla para el modelo → sin restricción** (semántica Odoo). El
      fail-closed multi-company es DATO, no código: la regla sembrada
      ``[('company_id', 'in', company_ids)]`` con cero compañías activadas
      da ``company_id IN []`` → cero filas. Por eso la semilla de la regla
      es parte del DoD de todo modelo con columna ``company_id``.

    El nombre del método se conserva del manager retirado
    (``for_current_company``) para no tocar a los llamadores; lo que hace
    ahora es aplicar las reglas del modelo, no una compañía cableada.
    """

    def for_current_company(self, mode='read', group_ids=(), user=None):
        if is_su():
            return self.get_queryset()
        domain = IrRule.compute_domain(
            self.model._meta.label, mode=mode, group_ids=group_ids,
            eval_context=IrRule.eval_context(user=user))
        return self.get_queryset().filter(domain)
