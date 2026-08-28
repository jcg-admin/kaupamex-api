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

El guion bajo, que es el contrato
=================================

Cuatro métodos se declaraban aquí sin él —``get_rules``, ``eval_context``,
``compute_domain``, ``get_failing``— y la referencia los declara ``_get_rules``,
``_eval_context``, ``_compute_domain`` y ``_get_failing``. Quitarlo no renombra:
**promueve el símbolo a API pública** (``porte-completo-no-parcial.md``,
:ref:`h-api-581`), y compromete a este puerto a sostener una firma que la
fuente nunca expuso. Se devuelve. ``_build_domain`` es **nuestro** —la fuente
lo tiene en línea dentro de ``_compute_domain``— y lleva guion bajo por lo
mismo: es un detalle interno, no contrato.

Qué NO se porta, con su medición
================================

- **``model_id`` como FK a ``ir.model``.** ``grep -rn "^class IrModel\b" src/``
  → **1** clase, así que el destino existe. El campo **sigue** siendo
  ``model_name`` (``Char`` indexado) con el label del modelo Django: cambiarlo
  a FK migra esta tabla y va en su propio pase, igual que
  ``ir_filters.action_id``. Mismo estado en ``ir_filters.model_id`` e
  ``ir_attachment.res_model``. Consecuencia visible aquí: ``_order`` de la
  fuente es ``'model_id DESC,id'`` —el **id** de la FK— y su forma Django es
  ``['-model_name', 'id']``, que ordena por el **texto**. Es otro orden, no el
  mismo escrito distinto, y se corrige cuando el campo sea FK.
- **``create``/``write``/``unlink``** — divergencia de stack ya declarada en
  todo este árbol: Django unifica los dos caminos de escritura en
  :meth:`save` y ``unlink`` es :meth:`delete`. Lo que la fuente hace en los
  tres —``self.env.registry.clear_cache()``— va con ellos, y ahí sí es
  obligatorio: sin esa invalidación la caché de :meth:`_compute_domain`
  serviría el dominio de una regla ya borrada.
- **``_compute_global``** — la fuente declara ``global`` como campo almacenado
  con su compute; aquí es la ``property`` :attr:`global_`, porque
  ``_get_rules`` resuelve la globalidad con ``groups__isnull=True`` y no
  necesita la columna. El nombre lleva guion bajo porque ``global`` es palabra
  reservada de Python — la fuente tiene el mismo problema y lo resuelve
  declarando el campo **fuera** de la clase (``ir_rule.py:276``).
"""
import logging

from django.apps import apps

import fields
import models

from addons.base.models.res_groups import ResGroups
from addons.base.models.timestamped_mixin import TimeStampedModel
from exceptions import AccessError, ValidationError
from orm import domains, registry
from orm.models import AccessQuerySet
from orm.environments import (get_current_companies, get_current_company,
                              get_current_user, is_su)
from tools.cache import ormcache
from tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)

#: Los cuatro verbos del rechazo, para la frase del error. La fuente los
#: traduce uno a uno (``_("read")`` …) por la misma razón por la que
#: ``ACCESS_ERROR_HEADER`` declara las cuatro cabeceras enteras: un traductor
#: necesita la palabra, no el hueco.
RULE_ERROR_OPERATIONS = {
    'read': 'consultar',
    'write': 'modificar',
    'create': 'crear',
    'unlink': 'borrar',
}

#: ≙ ``operation_error`` (``odoo19c: ir_rule.py:221-222``). La fuente abre con
#: una broma —*"Uh-oh! Looks like you have stumbled upon some top-secret
#: records"*— y aquí no se replica el chiste, sólo su función: decir que el
#: rechazo es por **fila** y no por modelo, que es la distinción que el
#: usuario necesita para saber a qué pedir acceso.
RULE_ERROR_HEADER = ('Estos registros existen, pero las reglas de registro no '
                     'se los muestran.\n\n%(user)s no tiene permiso de '
                     '«%(operation)s» sobre:')
RULE_ERROR_MODEL = '- %(description)s (%(model)s)'
RULE_ERROR_RESOLUTION = ('Contacte a su administrador para solicitar el '
                         'acceso si lo necesita.')
RULE_ERROR_BLAME = 'Lo impiden estas reglas:\n%(rules)s'

#: Las tres salidas del ramal multi-company (``odoo19c: ir_rule.py:247-251``).
RULE_ERROR_MULTICOMPANY_AMBIGUOUS = (
    '\n\nEsto puede ser un problema multi-empresa: cambiar de empresa activa '
    'quizá lo resuelva.')
RULE_ERROR_MULTICOMPANY_SUGGESTED = (
    '\n\nEsto parece un problema multi-empresa: quizá pueda ver el registro '
    'cambiando a la empresa %s.')
RULE_ERROR_MULTICOMPANY_FORBIDDEN = (
    '\n\nEsto parece un problema multi-empresa, pero no tiene acceso a la '
    'empresa que haría falta para ver el registro.')


def _company_of(record):
    """La empresa de un registro, por cualquiera de sus dos nombres.

    La fuente escribe ``rec.company_id`` y ahí acaba, porque su campo se llama
    así. Aquí la FK se declara ``company`` y su ``attname`` es ``company_id``
    —medido: **80 de 81** modelos con esa columna usan el nombre corto—, y un
    ``getattr`` por un solo nombre sería ciego al otro. Es la misma distinción
    que ``_add_missing_default_values`` tuvo que hacer (:ref:`h-api-874`).
    """
    for name in ('company', 'company_id'):
        company = getattr(record, name, None)
        if company is not None:
            return company
    return None


class IrRule(TimeStampedModel):
    """Regla de registro: acota qué filas ve un usuario (``ir.rule``)."""

    _name = 'ir.rule'
    _description = 'Record Rule'
    _order = 'model_id DESC,id'
    _MODES = ('read', 'write', 'create', 'unlink')
    _allow_sudo_commands = False

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
                  'restringe.',
    )
    perm_read = fields.Boolean(default=True, verbose_name='Leer')
    perm_write = fields.Boolean(default=True, verbose_name='Escribir')
    perm_create = fields.Boolean(default=True, verbose_name='Crear')
    perm_unlink = fields.Boolean(default=True, verbose_name='Borrar')

    class Meta:
        db_table = 'ir_rule'
        # ≙ ``_order = 'model_id DESC,id'``; ver el docstring del módulo para
        # por qué ordena por texto y no por id de la FK.
        ordering = ['-model_name', 'id']
        verbose_name = 'Regla de registro'
        verbose_name_plural = 'Reglas de registro'
        constraints = [
            # ≙ ``_no_access_rights = models.Constraint('CHECK (...)', …)``
            # (``odoo19c: ir_rule.py:32-35``). El nombre de la fuente se
            # conserva, prefijado por la tabla como exige el namespace global
            # de constraints de PostgreSQL.
            models.CheckConstraint(
                condition=(models.Q(perm_read=True) | models.Q(perm_write=True)
                           | models.Q(perm_create=True)
                           | models.Q(perm_unlink=True)),
                name='ir_rule_no_access_rights',
                violation_error_message='La regla debe conceder al menos un '
                                        'permiso.',
            ),
        ]

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

    # === validación: los dos ``@api.constrains`` de la fuente ==============

    def _check_model_name(self):
        """``@api.constrains('model_id')`` — ``:58-62``.

        Una regla sobre ``ir.rule`` sería recursiva: para saber si se puede
        leer la regla haría falta leer la regla. La fuente lo prohíbe en vez de
        detectarlo, y aquí igual.
        """
        if self.model_name == self._name:
            raise ValidationError(
                'No se pueden aplicar reglas sobre el modelo de reglas.')

    def _check_domain(self):
        """``@api.constrains('active', 'domain_force', 'model_id')`` — ``:64-73``.

        Valida que el dominio **parsee y se traduzca**, no que devuelva filas.
        La fuente hace ``Domain(domain).validate(model)``; aquí el equivalente
        es ``domains.to_q``, que revienta ante un campo inexistente o un
        operador desconocido.

        Por qué importa que se valide al guardar y no al evaluar: un dominio
        roto en una regla **activa** rompe toda consulta sobre su modelo, y el
        error aparecería lejos de donde se escribió.
        """
        if not (self.active and self.domain_force):
            return
        try:
            domain = safe_eval(self.domain_force, self._eval_context())
            q = domains.to_q(domain)
            # ``domains.to_q`` traduce SIN mirar el modelo: medido, un campo
            # inexistente sale como ``('no_existe__in', [1])`` sin quejarse. La
            # validación contra el modelo es la segunda mitad, y es la que la
            # fuente pide explícitamente: ``model = self.env[rule.model_id.model]
            # .sudo(); Domain(domain).validate(model)`` (``:70-71``). Aquí el
            # equivalente es armar la consulta: ``filter`` resuelve los lookups
            # al construirse y levanta ``FieldError`` sin tocar la base.
            app_label, model_name = self.model_name.split('.', 1)
            apps.get_model(app_label, model_name).objects.none().filter(q)
        except Exception as exc:
            raise ValidationError('Dominio inválido: %s' % exc)

    def clean(self):
        """El hogar de los dos ``@api.constrains`` en este stack."""
        super().clean()
        self._check_model_name()
        self._check_domain()

    # === escritura: la caché se invalida en el camino real =================

    def save(self, *args, **kwargs):
        """Guarda e invalida el dominio memorizado.

        ≙ el ``self.env.registry.clear_cache()`` que la fuente dispara desde
        ``create`` (``:190-197``) y ``write`` (``:198-206``). Aquí va en
        :meth:`save`, que es el camino de escritura real de Django: los dos de
        la fuente colapsan en él.

        Sin esto, :meth:`_compute_domain` serviría el dominio anterior a la
        edición — y en una regla de registro eso no es una caché fría: es
        acceso concedido a filas que la regla nueva prohíbe.
        """
        self._check_model_name()
        self._check_domain()
        result = super().save(*args, **kwargs)
        registry.clear_cache()
        return result

    def delete(self, *args, **kwargs):
        """Borra e invalida — ≙ ``unlink`` (``:184-188``)."""
        result = super().delete(*args, **kwargs)
        registry.clear_cache()
        return result

    # === el contexto de evaluación y la clave de caché =====================

    @classmethod
    def _eval_context(cls, user=None):
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

    @classmethod
    def _compute_domain_keys(cls):
        """Las claves de contexto que entran en la clave de caché — ``:75-77``.

        La fuente devuelve ``['allowed_company_ids']`` y keya ``self.env.su``
        **aparte**, porque allá la elevación es un atributo del ``Environment``
        y no una clave de contexto. Aquí las dos son lo mismo: ``_su`` y
        ``_current_companies`` son dos ``ContextVar`` del mismo módulo
        (``orm/environments.py:66-67``), así que ``su`` entra por esta puerta.
        El **conjunto** de lo que discrimina la clave es idéntico al de la
        fuente; sólo cambia por dónde entra cada pieza.
        """
        return ['allowed_company_ids', 'su']

    @classmethod
    def _compute_domain_context_values(cls):
        """Los valores de :meth:`_compute_domain_keys` — ``:175-183``.

        La fuente convierte las listas a tupla *"it seems safer if possibly
        slightly more miss-y to use a tuple"*: una lista no es hashable y el
        orden de ``allowed_company_ids`` no debe partir la caché en dos.
        """
        for key in cls._compute_domain_keys():
            if key == 'allowed_company_ids':
                yield tuple(get_current_companies())
            elif key == 'su':
                yield is_su()

    # === las reglas aplicables, y su combinación ===========================

    @classmethod
    def _get_rules(cls, model_name, mode='read', group_ids=()):
        """Reglas que aplican a ``model_name`` para ``mode`` y esos grupos.

        Fiel a ``_get_rules`` (``:112-131``): activas, con el permiso de la
        operación, y **o bien globales o bien de alguno de los grupos del
        usuario**. Ordenadas por id, como allá.

        Bajo elevación no hay reglas —``if self.env.su: return
        self.browse(())``—, y la guarda va aquí y no en el llamador porque es
        donde la fuente la pone: así **toda** vía queda cubierta, no sólo las
        que se acordaron de comprobarlo.

        :raises ValueError: si ``mode`` no es una de las cuatro operaciones —
            la referencia también revienta en vez de asumir ``read``.
        """
        if mode not in cls._MODES:
            raise ValueError('Modo inválido: %r' % (mode,))
        if is_su():
            return cls.objects.none()
        qs = cls.objects.filter(
            model_name=model_name, active=True, **{f'perm_{mode}': True})
        return qs.filter(
            models.Q(groups__isnull=True) | models.Q(groups__in=list(group_ids))
        ).distinct().order_by('id')

    def _build_domain(self, eval_context=None):
        """Evalúa ``domain_force`` y lo traduce a un filtro ``Q``.

        **Nuestro**: la fuente lo tiene en línea dentro de ``_compute_domain``
        (``odoo19c: ir_rule.py:164``): ``Domain(safe_eval(rule.domain_force,
        eval_context)) if rule.domain_force else Domain.TRUE``. Una regla sin
        ``domain_force`` es verdadera —no restringe—; aquí ``Domain`` es
        ``orm.domains.to_q``.
        """
        if not self.domain_force:
            return models.Q()
        domain = safe_eval(self.domain_force, eval_context or {})
        return domains.to_q(domain)

    @classmethod
    @ormcache('model_name', 'mode', 'tuple(group_ids)',
              'user.pk if user is not None else None',
              'tuple(cls._compute_domain_context_values())')
    def _compute_domain(cls, model_name, mode='read', group_ids=(), user=None):
        """Combina las reglas aplicables en un solo filtro — ``_compute_domain``.

        Globales con AND; de grupo con OR entre sí; y el OR resultante, AND
        contra las globales. Invertir cualquiera de los dos operadores rompe
        el modelo: ver el docstring del módulo.

        Memorizado como en la fuente (``@tools.ormcache('self.env.uid',
        'self.env.su', 'model_name', 'mode',
        'tuple(self._compute_domain_context_values())')``, ``:134-140``). La
        clave lleva **todo lo que puede cambiar el resultado**, que aquí son
        cinco piezas y allá cuatro sólo porque los grupos del usuario se
        derivan del ``uid``: aquí ``group_ids`` es parámetro explícito —este
        árbol no tiene ``Environment``— y por eso entra en la clave. El
        ``eval_context`` **no** es parámetro por la misma razón: se deriva
        dentro, como allá, para que ningún llamador pueda pasar uno que la
        clave no vea.

        Quien la invalida son :meth:`save` y :meth:`delete` de esta clase, más
        el invalidador del grafo de grupos de ``res_users``.
        """
        eval_context = cls._eval_context(user=user)
        rules = cls._get_rules(model_name, mode=mode, group_ids=group_ids)
        user_groups = set(group_ids)

        global_domains = []
        group_domains = []
        for rule in rules:
            rule_groups = set(rule.groups.values_list('pk', flat=True))
            if rule_groups and not (rule_groups & user_groups):
                # Regla de un grupo que el usuario no tiene: ni aporta ni
                # restringe, se descarta antes de evaluarla.
                continue
            domain = rule._build_domain(eval_context)
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
    def _get_failing(cls, queryset, mode='read', group_ids=(), user=None):
        """Las filas de ``queryset`` que las reglas **no** dejan pasar.

        Fiel a ``_get_failing`` (``:79-110``): se aplica el dominio combinado
        y se devuelve la diferencia, que es lo que el llamador necesita para
        explicar el rechazo.

        La fuente además distingue **qué regla** falla —separa las de grupo de
        las globales para poder nombrarlas—; eso vive aquí en
        :meth:`_failing_rules`, que es a quien :meth:`_make_access_error`
        pregunta.
        """
        model_name = queryset.model._meta.label
        domain = cls._compute_domain(
            model_name, mode=mode, group_ids=group_ids, user=user)
        allowed = queryset.filter(domain).values_list('pk', flat=True)
        return queryset.exclude(pk__in=list(allowed))

    @classmethod
    def _failing_rules(cls, queryset, mode='read', group_ids=(), user=None):
        """Qué reglas concretas fallan sobre ``queryset`` — ``:79-110``.

        **Nuestro por separación**, no por invención: es la segunda mitad del
        ``_get_failing`` de la fuente, la que devuelve *reglas* en vez de
        filas. Allá el método devuelve las dos cosas a la vez porque un
        recordset de reglas es su valor de retorno natural; aquí
        :meth:`_get_failing` devuelve filas del modelo consultado, así que las
        reglas necesitan su propia puerta.

        El criterio es el de la fuente, verbatim: *"Can return any global rule
        and/or all local rules (since local rules are OR-ed together, the
        entire group succeeds or fails, while global rules get AND-ed and can
        each fail)"*. Es decir, las de grupo se juzgan **en bloque** —si su OR
        deja pasar todas las filas, ninguna falla— y cada global **por
        separado**.
        """
        eval_context = cls._eval_context(user=user)
        model = queryset.model
        pks = list(queryset.values_list('pk', flat=True))
        total = len(pks)
        rules = list(cls._get_rules(
            model._meta.label, mode=mode, group_ids=group_ids))
        user_groups = set(group_ids)

        group_rules = [
            r for r in rules
            if set(r.groups.values_list('pk', flat=True)) & user_groups]
        if group_rules:
            combined = models.Q()
            for rule in group_rules:
                combined |= rule._build_domain(eval_context)
            passing = model._base_manager.filter(
                combined, pk__in=pks).values_list('pk', flat=True)
            if len(set(passing)) == total:
                # El OR de las de grupo devuelve todas: en bloque no fallan.
                group_rules = []

        def is_failing(rule):
            passing = model._base_manager.filter(
                rule._build_domain(eval_context),
                pk__in=pks).values_list('pk', flat=True)
            return len(set(passing)) < total

        failing = list(group_rules)
        failing += [r for r in rules
                    if not r.groups.exists() and is_failing(r)]
        return failing

    @classmethod
    def _make_access_error(cls, operation, records, group_ids=(), user=None):
        """El error que explica el rechazo POR FILA — ``_make_access_error``.

        ``odoo19c: addons/base/models/ir_rule.py:208-268``. Es el hermano del
        ``_make_access_error`` de ``ir.model.access``: aquél explica que el
        **modelo** está cerrado y qué grupos lo abrirían; éste explica que el
        modelo está abierto y las **filas** no, que es un rechazo distinto y
        con otra salida.

        Las cuatro partes de la fuente, en su orden:

        1. quién no puede hacer qué (``operation_error`` + ``failing_model``);
        2. **qué filas**, si el usuario puede verlas — la fuente lo condiciona
           a ``base.group_no_one`` **y** ``_is_internal()``, porque el
           ``display_name`` de una fila prohibida es en sí mismo información;
        3. **qué reglas** lo impiden, bajo la misma condición;
        4. cómo resolverlo, con el ramal multi-empresa.

        El ramal multi-empresa (``:242-251``) es el que convierte un 403 opaco
        en accionable: si la regla que falla menciona ``company_id`` y el
        usuario **tiene** la empresa del registro entre las suyas, el problema
        no es de permiso sino de empresa activa, y el mensaje lo dice —además
        de dejar la sugerencia en ``exception.context`` para que la interfaz
        pueda ofrecer el cambio.
        """
        actor = get_current_user() if user is None else user
        model = records.model._meta.label
        _logger.info(
            'Acceso denegado por reglas de registro — operación: %s, ids: %r, '
            'usuario: %s, modelo: %s',
            operation, list(records.values_list('pk', flat=True)[:6]),
            getattr(actor, 'pk', None), model)

        IrModel = apps.get_model('base', 'IrModel')
        description = IrModel.objects.filter(model=model).values_list(
            'name', flat=True).first() or model
        user_description = (f'{actor} (id={actor.pk})' if actor is not None
                            else 'El usuario anónimo')
        operation_error = RULE_ERROR_HEADER % {
            'user': user_description,
            'operation': RULE_ERROR_OPERATIONS[operation],
        }
        failing_model = RULE_ERROR_MODEL % {
            'description': description, 'model': model}
        resolution_info = RULE_ERROR_RESOLUTION

        rules = cls._failing_rules(
            records, mode=operation, group_ids=group_ids, user=user)
        display_records = list(records[:6])
        company_related = any(
            'company_id' in (rule.domain_force or '') for rule in rules)

        context = None
        if company_related:
            suggested = cls._suggested_companies(display_records, actor)
            if len(suggested) > 1:
                resolution_info += RULE_ERROR_MULTICOMPANY_AMBIGUOUS
            elif len(suggested) == 1 and cls._user_has_company(
                    actor, suggested[0]):
                company = suggested[0]
                context = {'suggested_company': {
                    'id': company.pk, 'display_name': str(company)}}
                resolution_info += RULE_ERROR_MULTICOMPANY_SUGGESTED % company
            elif suggested:
                resolution_info += RULE_ERROR_MULTICOMPANY_FORBIDDEN

        if cls._may_see_the_detail(actor):
            failing_records = '\n'.join(
                f'- {cls._describe_record(rec, description, model, company_related, actor)}'
                for rec in display_records)
            blame = RULE_ERROR_BLAME % {
                'rules': '\n'.join(f'- {rule}' for rule in rules)}
            message = (f'{operation_error}\n{failing_records}\n\n{blame}\n\n'
                       f'{resolution_info}')
        else:
            message = (f'{operation_error}\n{failing_model}\n\n'
                       f'{resolution_info}')

        error = AccessError(message)
        if context:
            error.context = context
        return error

    # --- las cuatro piezas que ``_make_access_error`` usa -------------------
    #
    # La fuente las tiene en línea: una clausura (``get_record_description``),
    # dos expresiones sobre ``self.env.user`` y una llamada a
    # ``_get_redirect_suggested_company``. Se extraen porque aquí no hay
    # ``env`` que las haga triviales, y porque cada una tiene su propio caso
    # de prueba: en línea, ninguna se puede ejercitar sin montar un rechazo.

    @staticmethod
    def _may_see_the_detail(user):
        """¿Puede ver qué filas y qué reglas? — ``:255``.

        ``not self.env.user.has_group('base.group_no_one') or not
        self.env.user._is_internal()`` decide el mensaje corto; la negación de
        eso es esta guarda. **No es cosmética**: el ``display_name`` de una
        fila que el usuario no puede leer es información sobre esa fila.
        """
        if user is None:
            return False
        return bool(user.has_group('base.group_no_one')
                    and user._is_internal())

    @staticmethod
    def _user_has_company(user, company):
        """¿Está la empresa entre las del usuario? — ``in self.env.user.company_ids``."""
        if user is None or company is None:
            return False
        return user.company_ids.filter(pk=company.pk).exists()

    @staticmethod
    def _describe_record(record, description, model, company_related, user):
        """≙ la clausura ``get_record_description`` (``:236-241``).

        *"If the user has access to the company of the record, add this
        information in the description to help them to change company"* — la
        empresa sólo se nombra cuando el usuario la tiene, porque si no la
        tiene el nombre de la empresa también es información que no le toca.
        """
        company = _company_of(record)
        if (company_related and company is not None
                and IrRule._user_has_company(user, company)):
            return (f'{description}, {record} ({model}: {record.pk}, '
                    f'empresa={company})')
        return f'{description}, {record} ({model}: {record.pk})'

    @staticmethod
    def _suggested_companies(records, user):
        """Las empresas que sugerir — ≙ ``_get_redirect_suggested_company``.

        El método vive en ``BaseModel`` en la fuente
        (``odoo19c: odoo/orm/models.py:5825-5839``) y aquí en
        ``orm.models.AccessQuerySet``, que es lo que en este árbol hace de
        recordset. Esta función sólo lo llama sobre las hasta seis filas que el
        error muestra: allá sale gratis porque ``display_records.company_id`` ya
        devuelve la unión sobre el recordset entero.
        """
        if not records:
            return []
        model = type(records[0])
        pks = [record.pk for record in records]
        # ``AccessQuerySet`` directo y no ``_default_manager``: es el ``sudo()``
        # que la fuente pone sobre ``display_records`` —una fila prohibida o
        # borrada tiene que poder describirse— y a la vez la clase que declara
        # el método. ``_base_manager`` daría lo primero y no lo segundo: es un
        # ``Manager`` pelado (medido).
        return AccessQuerySet(model).filter(
            pk__in=pks)._get_redirect_suggested_company(user=user)


class RuleScopedManager(models.AccessManager):
    """Aplica las record rules del modelo al queryset — el rol de
    ``_check_access`` (``odoo19c: odoo/orm/models.py:4114``).

    Sustituye al ``CompanyScopedManager`` codificado (DEC-AISL-04 §4): el
    filtrado ya no vive en el manager sino en las reglas almacenadas
    (``ir_rule``); este manager sólo las evalúa y las aplica. Semántica de la
    referencia, verbatim:

    - ``su`` activo → sin filtro. En la fuente ``_check_access`` ni se llama
      bajo ``su`` (``if not self.env.su and (result := ...)``), y además
      ``_get_rules`` devuelve vacío, así que la guarda está en los dos sitios.
    - Reglas de grupo cuyos grupos el llamador no pasa → descartadas
      (``_compute_domain``). Las reglas multi-company canónicas son globales
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

    **Hereda de** ``orm.models.AccessManager`` desde la tarea #93, así que los
    modelos que ya lo declaran tienen también las cuatro formas de la fuente
    (``check_access`` / ``has_access`` / ``_filtered_access`` / el
    ``_check_access`` que las compone). La diferencia entre las dos superficies
    es real y conviene tenerla clara: ``for_current_company`` aplica **sólo** la
    mitad de reglas; ``_filtered_access`` aplica **las dos**, ACL primero. Un
    llamador que quiera la resolución completa de la referencia usa la segunda.
    """

    def for_current_company(self, mode='read', group_ids=(), user=None):
        if is_su():
            return self.get_queryset()
        domain = IrRule._compute_domain(
            self.model._meta.label, mode=mode, group_ids=tuple(group_ids),
            user=user)
        return self.get_queryset().filter(domain)
