"""``res.groups`` — grupos de acceso con implicación transitiva.

Adaptación de ``odoo/addons/base/models/res_groups.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 397 líneas).

Colisión con ``authz`` — declarada, no resuelta aquí
====================================================

Este árbol autoriza por **capacidad** (DEC-11: ``HasCapability``, fail-closed)
sobre ``authz.Role`` y ``authz.Capability``, no por grupos de Odoo. Portar
``res.groups`` **no** cambia eso: se porta el archivo completo, y el
re-apuntado de los consumidores (``IrUiMenu.group``, que hoy apunta a
``authz.Capability``) es una decisión de producto que va en su propio pase.

Lo que este archivo aporta de inmediato, independientemente de esa decisión, es
el **álgebra de implicación**, que ``authz`` no tiene: un rol que implica a
otro transitivamente, y dos roles declarados mutuamente excluyentes.

El grafo de implicación, portado entero
=======================================

La referencia dibuja el grafo en un comentario ASCII: si Z implica a C,
"todos los gerentes son usuarios". De ahí salen cuatro relaciones, y las
cuatro se portan:

- ``implied_ids`` — los grupos que este implica (arista directa).
- ``implied_by_ids`` — el **reverso de la misma tabla**: en la referencia son
  el mismo ``Many2many`` sobre ``res_groups_implied_rel`` con las columnas
  invertidas (``gid``/``hid`` ↔ ``hid``/``gid``). Aquí es el ``related_name``
  del propio M2M — misma tabla, misma arista leída al revés.
- ``all_implied_ids`` — **clausura transitiva reflexiva**: el grupo *más* todo
  lo que implica, directa o indirectamente. Reflexiva importa: el grupo se
  incluye a sí mismo (``g.ids + …`` en la fuente).
- ``all_implied_by_ids`` — la clausura en el otro sentido.

Las dos clausuras son ``compute`` **sin** ``store`` allá, así que aquí son
propiedades. El recorrido es una BFS con conjunto de visitados: un grafo de
implicación puede tener ciclos y sin el visitado la clausura no termina.

Grupos disjuntos
================

``disjoint_ids`` declara pares mutuamente excluyentes — el ejemplo de la
fuente es que un usuario no puede ser portal e interno a la vez. En la
referencia el conjunto disjunto sale de tres ``xmlid`` fijos
(``base.group_user`` / ``group_portal`` / ``group_public``) resueltos contra
``ir.model.data``. Medido con
``grep -rn "^class IrModelData\b" src/`` → **0** clases.
[PROVEN]

Por eso la pertenencia al conjunto disjunto se declara **en el propio
registro**, con un campo ``user_type`` que marca al grupo como tipo de usuario:
dos grupos con ``user_type`` no nulo son disjuntos entre sí. Es la misma
semántica sin depender de identificadores XML que este árbol no tiene, y deja
el conjunto extensible sin tocar código.

``check_user_disjoint_groups`` conserva la decisión de escala de la fuente, que
su comentario explica: **no** se recorren todos los usuarios del grupo —no
escala pasados 10 000— sino que se **busca uno** que viole la exclusión. Si
aparece, hay violación; si no, no la hay. Una consulta en vez de N.

Qué NO se porta, con su medición
================================

- ``model_access`` (``ir.model.access``), ``rule_groups`` (``ir.rule``),
  ``view_access`` (``ir.ui.view``): son **reversos** de FK que viven en
  modelos aún sin portar — los tres están en la lista de pendientes de
  ``base``. Aparecen solos cuando esos archivos lleguen, sin tocar éste.
- ``menu_access`` (``ir.ui.menu``): ``IrUiMenu`` **sí** está portado, pero su
  campo ``group`` apunta hoy a ``authz.Capability``. Re-apuntarlo es
  exactamente la decisión de producto que este docstring difiere; añadir aquí
  un segundo M2M crearía dos caminos de autorización al mismo menú, que es
  peor que uno provisional.
- ``view_group_hierarchy`` / ``_get_view_group_hierarchy`` (Json computado
  para el formulario de ajustes) y ``action_show_all_users`` (devuelve una
  ``ir.actions.act_window``): ``IrActionsActWindow`` **ya existe** desde el
  porte de ``ir_actions.py``, pero ambos métodos dependen además de la capa de
  **vistas** (``ir.ui.view``), que sigue sin portar —
  ``grep -rn "^class IrUiView" src/`` → **0**.
- ``_ensure_xml_id`` y ``get_external_id``: mismo motivo que ``disjoint_ids``,
  no hay ``ir.model.data``.
- ``api_key_duration``: la duración máxima de una API key. Este árbol autentica
  por sesión de servidor (ADR-018) y las API keys no existen; el campo se
  porta como columna —es dato del grupo— pero sin lógica que lo consuma, y así
  se declara en su ``help_text``.
"""
import logging
from collections import deque

import fields
import models
from django.core.exceptions import ValidationError

from addons.base.models.res_groups_privilege import ResGroupsPrivilege
from addons.base.models.res_users import ResUsers
from addons.base.models.timestamped_mixin import TimeStampedModel

_logger = logging.getLogger(__name__)


class ResGroups(TimeStampedModel):
    """Un grupo de acceso (``res.groups``).

    ``full_name`` es ``privilegio / nombre`` cuando hay privilegio, y el
    nombre a secas cuando no — igual que ``_compute_full_name`` de la fuente.
    """

    #: Tipos de usuario mutuamente excluyentes. En la referencia son tres
    #: ``xmlid`` fijos; aquí el grupo declara su tipo y dos tipos distintos
    #: son disjuntos por construcción.
    USER_TYPE_INTERNAL = 'internal'
    USER_TYPE_PORTAL = 'portal'
    USER_TYPE_PUBLIC = 'public'
    USER_TYPE_CHOICES = [
        (USER_TYPE_INTERNAL, 'Interno'),
        (USER_TYPE_PORTAL, 'Portal'),
        (USER_TYPE_PUBLIC, 'Público'),
    ]

    name = fields.Char(max_length=120, verbose_name='Nombre')
    comment = fields.Text(blank=True, default='', verbose_name='Comentario')
    sequence = fields.Integer(null=True, blank=True, verbose_name='Secuencia')
    share = fields.Boolean(
        default=False, verbose_name='Grupo compartido',
        help_text='Odoo share. Grupo creado para dar acceso al compartir datos '
                  'con algunos usuarios.',
    )
    api_key_duration = fields.Float(
        null=True, blank=True,
        verbose_name='Duración máxima de las API keys (días)',
        help_text='Odoo api_key_duration. Se porta como dato del grupo; este '
                  'árbol autentica por sesión de servidor (ADR-018) y no tiene '
                  'API keys que lo consuman.',
    )
    privilege = fields.Many2one(
        ResGroupsPrivilege, on_delete=models.SET_NULL, null=True, blank=True,
        db_index=True, related_name='group_ids', verbose_name='Privilegio',
        help_text='Odoo privilege_id. Agrupa grupos en el formulario.',
    )
    user_type = fields.Selection(
        max_length=16, choices=USER_TYPE_CHOICES, null=True, blank=True,
        db_index=True, verbose_name='Tipo de usuario',
        help_text='Dos grupos con tipo de usuario distinto son disjuntos: un '
                  'usuario no puede pertenecer a ambos.',
    )
    implied_ids = fields.Many2many(
        'self', symmetrical=False, blank=True, related_name='implied_by_ids',
        db_table='res_groups_implied_rel', verbose_name='Grupos implicados',
        help_text='Los usuarios de este grupo pertenecen también, de forma '
                  'implícita, a estos grupos (Odoo implied_ids).',
    )
    # La referencia declara este M2M **del lado de res.groups**
    # (``res_groups_users_rel``, columnas ``gid``/``uid``), así que aquí va
    # igual: no hace falta tocar ``res_users.py``, que recibe el reverso
    # ``group_ids`` por el ``related_name``.
    user_ids = fields.Many2many(
        ResUsers, blank=True, related_name='group_ids',
        db_table='res_groups_users_rel', verbose_name='Usuarios',
        help_text='Usuarios explícitamente en este grupo (Odoo user_ids).',
    )

    class Meta:
        db_table = 'res_groups'
        ordering = ['sequence', 'name', 'id']
        verbose_name = 'Grupo'
        verbose_name_plural = 'Grupos'

    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        """``privilegio / nombre``, o el nombre solo — ``_compute_full_name``."""
        if self.privilege_id and self.privilege:
            return '%s / %s' % (self.privilege.name, self.name)
        return self.name

    # === Clausura transitiva ==============================================

    @staticmethod
    def _closure(seeds, edge):
        """Clausura transitiva **reflexiva** por BFS.

        ``edge(grupo)`` devuelve los vecinos a seguir. El conjunto de visitados
        no es una optimización: el grafo de implicación admite ciclos, y sin él
        el recorrido no termina.
        """
        seen = set()
        queue = deque(seeds)
        while queue:
            group = queue.popleft()
            if group.pk in seen:
                continue
            seen.add(group.pk)
            queue.extend(edge(group))
        return seen

    @property
    def all_implied_ids(self):
        """El grupo con todos sus implicados, directos e indirectos.

        Reflexiva: incluye al propio grupo, como el ``g.ids + …`` de la fuente.
        """
        return type(self).objects.filter(
            pk__in=self._closure([self], lambda g: g.implied_ids.all()))

    @property
    def all_implied_by_ids(self):
        """Todos los grupos que implican a éste, directa o indirectamente."""
        return type(self).objects.filter(
            pk__in=self._closure([self], lambda g: g.implied_by_ids.all()))

    @property
    def disjoint_ids(self):
        """Grupos con los que éste es mutuamente excluyente.

        Vacío si el grupo no declara tipo de usuario — igual que la fuente
        devuelve falso para un grupo que no es de tipo.
        """
        model = type(self)
        if not self.user_type:
            return model.objects.none()
        return model.objects.filter(
            user_type__isnull=False).exclude(user_type=self.user_type)

    # === Invariantes ======================================================

    def check_user_disjoint_groups(self):
        """Verifica que ningún usuario esté en dos grupos disjuntos.

        Conserva la decisión de escala de la fuente, que su comentario
        justifica: recorrer todos los usuarios del grupo no escala pasados
        ~10 000, así que se **busca uno** que viole la exclusión. Si la
        búsqueda devuelve algo, hay violación.

        :raises ValidationError: si existe tal usuario.
        """
        disjoint = list(self.disjoint_ids.values_list('pk', flat=True))
        if not disjoint:
            return
        offender = (
            self.user_ids.filter(group_ids__in=disjoint)
            .values_list('pk', flat=True)
            .first()
        )
        if offender is not None:
            raise ValidationError(
                'El usuario %s no puede pertenecer a este grupo y a uno de sus '
                'grupos disjuntos a la vez.' % offender
            )

    # === Usuarios de la clausura ==========================================

    @property
    def all_user_ids(self):
        """Usuarios del grupo y de todos los que lo implican.

        ``all_user_ids`` de la fuente: quien está en un grupo que implica a
        éste, está implícitamente en éste.
        """
        implying = self.all_implied_by_ids.values_list('pk', flat=True)
        return ResUsers.objects.filter(group_ids__in=list(implying)).distinct()

    @property
    def all_users_count(self):
        """Cuántos usuarios lo tienen, implícita o explícitamente."""
        return self.all_user_ids.count()

    # === Mutación del grafo ===============================================

    def apply_group(self, implied_group):
        """Añade ``implied_group`` a los implicados — ``_apply_group``.

        No-op si ya está en la clausura: la fuente filtra por
        ``implied_group not in g.all_implied_ids``, es decir, no vuelve a
        declarar una arista que la transitividad ya da.
        """
        if implied_group.pk in {g.pk for g in self.all_implied_ids}:
            return
        self.implied_ids.add(implied_group)

    def remove_group(self, implied_group):
        """Quita ``implied_group`` de los implicados — ``_remove_group``.

        La fuente lo quita de **todos** los grupos de la clausura que lo
        declaren directamente, no sólo de éste: si un implicado intermedio
        mantiene la arista, el grupo seguiría implicándolo por transitividad.
        """
        for group in self.all_implied_ids:
            if group.implied_ids.filter(pk=implied_group.pk).exists():
                group.implied_ids.remove(implied_group)
