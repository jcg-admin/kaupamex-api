"""``ir.rule`` — reglas de registro: acceso a nivel de fila.

Adaptación de ``odoo/addons/base/models/ir_rule.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 279 líneas). Una regla declara un
dominio que acota **qué filas** de un modelo ve un usuario, por operación
(leer, escribir, crear, borrar).

Relación con el aislamiento L3 que este árbol ya tiene
======================================================

``company.CompanyScopedManager`` implementa hoy el aislamiento por fila:
``for_current_company()`` filtra por la company del contexto, fail-closed.
Eso es **una** regla de registro concreta, cableada en un manager. ``ir.rule``
es el mecanismo general: la misma idea, declarada como dato en vez de código,
con un dominio por regla y por grupo.

Portarlo no reemplaza al manager ni cambia la autorización por capacidad
(DEC-11). Añade la pieza declarativa; conectarla al queryset de cada modelo es
un pase aparte.

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

- **``model_id`` como FK a ``ir.model``.** Medido con
  ``grep -rn "^class IrModel\b" src/`` → **0** clases (el ancla de columna 0
  distingue una definición de una cita indentada — ver H-API-141).
  [PROVEN] Se porta como ``model_name`` (``Char`` indexado) con el label del
  modelo Django, mismo criterio que ``ir_filters.model_id`` e
  ``ir_attachment.res_model`` ya usan en este árbol: el "modelo técnico" es un
  string que se resuelve en runtime, no una relación.
- **``domain_force`` evaluado con ``safe_eval``.** La referencia guarda el
  dominio como **texto de una expresión Python** y lo evalúa con su
  ``safe_eval`` contra un contexto acotado. Aquí el campo se porta —es el dato
  de la regla— pero **este archivo no lo evalúa**: montar un evaluador de
  expresiones sobre entrada almacenada es superficie de ejecución de código, y
  hacerlo bien exige la decisión explícita de qué evaluador y con qué contexto.
  ``build_domain`` deja el punto de extensión declarado y levanta si nadie lo
  conectó, en vez de evaluar por su cuenta.
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

    def build_domain(self, eval_context=None):
        """Punto de extensión: traduce ``domain_force`` a un filtro.

        La referencia evalúa el texto con ``safe_eval``. Aquí **no** se evalúa
        (ver el docstring del módulo): quien conecte las reglas al queryset
        decide con qué evaluador y con qué contexto, y lo declara.

        Una regla sin ``domain_force`` es verdadera —no restringe—, así que
        devuelve un ``Q`` vacío sin necesitar evaluador.
        """
        if not self.domain_force:
            return models.Q()
        raise NotImplementedError(
            'ir.rule.domain_force requiere un evaluador de dominios; este '
            'archivo no lo provee a propósito. Ver el docstring del módulo.'
        )

    @classmethod
    def compute_domain(cls, model_name, mode='read', group_ids=(),
                       eval_context=None):
        """Combina las reglas aplicables en un solo filtro — ``_compute_domain``.

        Globales con AND; de grupo con OR entre sí; y el OR resultante, AND
        contra las globales. Invertir cualquiera de los dos operadores rompe
        el modelo: ver el docstring del módulo.
        """
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
