"""Candado por tiempo configurable por grupo — el eje que ``authz_reauth`` no cubre.

Adaptación de Odoo ``auth_timeout/models/res_groups.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 236 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

La referencia agrega a ``res.groups`` **dos umbrales ortogonales**, cada uno
con su bandera de segundo factor:

- ``lock_timeout`` — tiempo absoluto desde la autenticación tras el cual se
  vuelve a exigir identidad, haya o no actividad.
- ``lock_timeout_inactivity`` — tiempo de **inactividad** tras el cual se
  exige confirmar identidad.

El umbral efectivo de un usuario es el **más corto** entre todos los grupos que
implica, y se reporta por separado según exija o no MFA
(``_get_lock_timeouts``). Ese es el contrato que consume la capa HTTP.

Porte símbolo por símbolo — 16 de 16 defs, 13 de 13 atributos de clase
======================================================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea en la referencia)
     - Estado
   * - ``_inherit = "res.groups"`` (``:34``)
     - portado — lo expresa ``extend_model('base', 'ResGroups', …)``
   * - ``lock_timeout`` (``:36``) · ``lock_timeout_mfa`` (``:41``)
     - portados — columnas almacenadas
   * - ``lock_timeout_inactivity`` (``:46``) · ``lock_timeout_inactivity_mfa``
       (``:51``)
     - portados — columnas almacenadas
   * - ``has_lock_timeout`` (``:57``)
     - portado como ``property`` (la fuente lo declara ``compute`` **sin**
       ``store``; H-API-611)
   * - ``lock_timeout_delay_unit`` (``:63``) ·
       ``lock_timeout_delay_in_unit`` (``:64``)
     - ídem
   * - ``lock_timeout_2fa_selection`` (``:65``)
     - ídem; su ``inverse`` se porta como método
   * - ``has_lock_timeout_inactivity`` (``:71``) ·
       ``lock_timeout_inactivity_delay_unit`` (``:76``) ·
       ``lock_timeout_inactivity_delay_in_unit`` (``:81``) ·
       ``lock_timeout_inactivity_2fa_selection`` (``:85``)
     - ídem
   * - los 6 ``_compute_*`` (``:91-131``)
     - portados con su nombre; **devuelven** el valor en vez de asignarlo
       sobre el recordset (la traducción de las 3 convenciones del ORM
       fuente, tarea #360/#384)
   * - los 2 ``_inverse_*`` (``:108``, ``:131``)
     - portados con su nombre; escriben la columna almacenada
   * - los 4 ``_onchange_*`` (``:135-166``)
     - portados con su nombre y su decorador ``@api.onchange`` — que en este
       árbol **anota** y no dispara (``src/orm/decorators.py:37``). Los
       invoca quien edita el grupo, no un motor
   * - ``create`` (``:171``) · ``write`` (``:180``) · ``unlink`` (``:186``)
     - portados como **2** símbolos, no 3 — ver la divergencia 2
   * - ``_get_lock_timeouts`` (``:190``)
     - portado como ``classmethod`` sobre el conjunto de grupos — ver la
       divergencia 3
   * - ``human_readable_delay`` (``:7``) ·
       ``human_readable_delay_to_minutes`` (``:18``) · ``DELAY_UNITS``
       (``:26``) · ``CACHE_INVALIDATE_FIELDS`` (``:4``)
     - portados verbatim (constantes y funciones de módulo, no ORM)

Divergencias declaradas
=======================

1. **Los 8 campos técnicos son ``property``, no columnas.** La fuente los
   declara ``compute=`` sin ``store``, que es exactamente lo que una
   ``property`` es aquí. Sólo las **4** columnas de arriba llegan a la
   migración. Los ``readonly=False`` de la fuente son azúcar de su formulario
   web —el usuario teclea «2 días» y el ``inverse``/``onchange`` traduce a
   minutos— y aquí ese papel lo cumplen los ``_onchange_*`` portados, que el
   llamador invoca.

2. **``create``/``write``/``unlink`` → ``save``/``delete``.** Los tres existen
   en la fuente **sólo** para invalidar la caché de ``_get_lock_timeouts``, y
   Django no separa alta de modificación en su API: ambas son ``save()``. Son
   3 símbolos de la fuente contra 2 nuestros, no un símbolo omitido.

   La fuente invalida sólo si un campo de ``CACHE_INVALIDATE_FIELDS`` viene en
   ``vals``. Aquí ese predicado tiene receptor **cuando** el llamador pasa
   ``update_fields``; sin él, Django no dice qué cambió y se invalida siempre
   — más conservador que la fuente, nunca menos.

3. **``@ormcache("self._ids")`` → caché por proceso.** El decorador
   ``ormcache`` no está construido en este árbol (medido: 0 definiciones en
   ``src/``; 11 archivos lo citan en prosa). Su equivalente ya establecido es
   un diccionario de módulo con invalidación explícita — el mismo patrón que
   ``src/addons/base/models/ir_config_parameter.py:57``, con su mismo caveat:
   es **por proceso**, así que la invalidación no cruza workers de Gunicorn.

   Y el recordset pasa a ser un conjunto de ids: la fuente llama
   ``groups._get_lock_timeouts()`` sobre un recordset, y aquí es
   ``ResGroups._get_lock_timeouts(group_ids)``. Misma clave de caché
   (``self._ids`` ≙ ``frozenset(group_ids)``), mismo resultado.
"""
import api
import fields
from orm.model_classes import extend_model

#: ≙ ``CACHE_INVALIDATE_FIELDS`` (``:4``) — los cuatro campos almacenados cuya
#: escritura invalida el resultado cacheado de ``_get_lock_timeouts``.
CACHE_INVALIDATE_FIELDS = (
    'lock_timeout',
    'lock_timeout_mfa',
    'lock_timeout_inactivity',
    'lock_timeout_inactivity_mfa',
)


def human_readable_delay(minutes):
    """≙ ``human_readable_delay`` (``:7-15``) — minutos a la unidad más gruesa
    que los divide exacto."""
    if not minutes:
        return minutes, 'minutes'
    if minutes % 1440 == 0:
        return minutes // 1440, 'days'
    elif minutes % 60 == 0:
        return minutes // 60, 'hours'
    else:
        return minutes, 'minutes'


def human_readable_delay_to_minutes(delay, unit):
    """≙ ``human_readable_delay_to_minutes`` (``:18-23``) — la vuelta."""
    if unit == 'days':
        return delay * 1440
    elif unit == 'hours':
        return delay * 60
    else:
        return delay


#: ≙ ``DELAY_UNITS`` (``:26-30``).
DELAY_UNITS = [
    ('minutes', 'minutes'),
    ('hours', 'hours'),
    ('days', 'days'),
]

#: Caché por proceso de ``_get_lock_timeouts``, equivalente al
#: ``@ormcache("self._ids")`` de la fuente (divergencia 3 del docstring).
#: Clave: ``frozenset`` de ids de grupo -> el diccionario de umbrales.
_LOCK_TIMEOUTS_CACHE = {}


def _clear_lock_timeouts_cache():
    """Invalida la caché entera — ≙ ``self.env.registry.clear_cache()``."""
    _LOCK_TIMEOUTS_CACHE.clear()


# === Los 6 cómputos ======================================================
# La fuente los escribe como bucle sobre el recordset asignando el campo; aquí
# devuelven el valor y la ``property`` homónima los expone (#360/#384).

def _compute_has_lock_timeout(self):
    """≙ ``_compute_has_lock_timeout`` (``:91-94``)."""
    return bool(self.lock_timeout)


def _compute_lock_timeout_delay_unit(self):
    """≙ ``_compute_lock_timeout_delay_unit`` (``:96-102``).

    Devuelve la tupla ``(cantidad, unidad)``; la fuente asigna sus dos campos
    de una vez porque un solo ``compute`` alimenta a ambos.
    """
    return human_readable_delay(self.lock_timeout)


def _compute_lock_timeout_2fa_selection(self):
    """≙ ``_compute_lock_timeout_2fa_selection`` (``:104-107``)."""
    return 'with_2fa' if self.lock_timeout_mfa else 'without_2fa'


def _compute_lock_timeout_inactivity_bool(self):
    """≙ ``_compute_lock_timeout_inactivity_bool`` (``:112-115``)."""
    return bool(self.lock_timeout_inactivity)


def _compute_lock_timeout_inactivity_delay_unit(self):
    """≙ ``_compute_lock_timeout_inactivity_delay_unit`` (``:117-123``)."""
    return human_readable_delay(self.lock_timeout_inactivity)


def _compute_lock_timeout_inactivity_2fa_selection(self):
    """≙ ``_compute_lock_timeout_inactivity_2fa_selection`` (``:125-130``)."""
    return 'with_2fa' if self.lock_timeout_inactivity_mfa else 'without_2fa'


# === Los 2 inversos ======================================================

def _inverse_lock_timeout_2fa_selection(self, value):
    """≙ ``_inverse_lock_timeout_2fa_selection`` (``:109-111``).

    Recibe el valor porque aquí el campo técnico es una ``property`` de sólo
    lectura: quien edita pasa la selección y este método escribe la columna.
    """
    self.lock_timeout_mfa = value == 'with_2fa'


def _inverse_lock_timeout_inactivity_2fa_selection(self, value):
    """≙ ``_inverse_lock_timeout_inactivity_2fa_selection`` (``:132-134``)."""
    self.lock_timeout_inactivity_mfa = value == 'with_2fa'


# === Los 4 onchange ======================================================
# El decorador anota y no dispara (``src/orm/decorators.py:37``): lo invoca
# quien edita el grupo. Los defaults son los de la fuente, verbatim.

@api.onchange('has_lock_timeout')
def _onchange_has_lock_timeout(self, enabled):
    """≙ ``_onchange_has_lock_timeout`` (``:136-144``).

    Al encender: 1440 minutos (un día) y MFA exigido. Al apagar: ambos a cero.
    """
    if not enabled:
        self.lock_timeout = 0
        self.lock_timeout_mfa = False
    else:
        self.lock_timeout = 1440           # un día por defecto
        self.lock_timeout_mfa = True       # exige 2FA por defecto


@api.onchange('lock_timeout_delay_unit', 'lock_timeout_delay_in_unit')
def _onchange_lock_timeout_delay_unit(self, delay, unit):
    """≙ ``_onchange_lock_timeout_delay_unit`` (``:146-152``)."""
    self.lock_timeout = human_readable_delay_to_minutes(delay, unit)


@api.onchange('has_lock_timeout_inactivity')
def _onchange_has_lock_timeout_inactivity(self, enabled):
    """≙ ``_onchange_has_lock_timeout_inactivity`` (``:154-161``).

    Al encender: 15 minutos y **sin** MFA — asimetría deliberada de la fuente
    frente al candado absoluto, que sí lo exige.
    """
    if not enabled:
        self.lock_timeout_inactivity = 0
        self.lock_timeout_inactivity_mfa = False
    else:
        self.lock_timeout_inactivity = 15      # 15 minutos por defecto
        self.lock_timeout_inactivity_mfa = False   # no exige 2FA por defecto


@api.onchange('lock_timeout_inactivity_delay_unit',
              'lock_timeout_inactivity_delay_in_unit')
def _onchange_lock_timeout_inactivity_delay_unit(self, delay, unit):
    """≙ ``_onchange_lock_timeout_inactivity_delay_unit`` (``:163-169``)."""
    self.lock_timeout_inactivity = human_readable_delay_to_minutes(delay, unit)


# === Invalidación de la caché ============================================

def save(self, *args, **kwargs):
    """≙ ``create`` (``:171-177``) + ``write`` (``:179-184``) — divergencia 2.

    Invalida la caché cuando la escritura toca un campo de umbral. Con
    ``update_fields`` presente se aplica el predicado de la fuente; sin él,
    Django no dice qué cambió y se invalida siempre.

    Devuelve ``None`` a propósito: es la semántica de **relevo** de
    ``chain_method`` (``src/orm/method_chain.py``), que entonces delega en el
    ``save`` previo. Ese ``return super().save(...)`` de la fuente aquí lo
    hace el encadenador, no este cuerpo.
    """
    update_fields = kwargs.get('update_fields')
    if update_fields is None or set(update_fields) & set(CACHE_INVALIDATE_FIELDS):
        _clear_lock_timeouts_cache()


def delete(self, *args, **kwargs):
    """≙ ``unlink`` (``:186-189``) — divergencia 2.

    La fuente sólo invalida si el grupo borrado tenía algún umbral puesto; el
    mismo predicado se aplica aquí, que sobre una instancia sí tiene receptor.

    Devuelve ``None`` por la misma razón que ``save``: el relevo de
    ``chain_method`` delega en el ``delete`` previo y es su tupla la que sale.
    """
    if any(getattr(self, name, None) for name in CACHE_INVALIDATE_FIELDS):
        _clear_lock_timeouts_cache()


def _get_lock_timeouts(cls, group_ids):
    """≙ ``_get_lock_timeouts`` (``:191-236``) — divergencia 3.

    Umbrales de sesión e inactividad del usuario, en **segundos**, tomando el
    más corto de todos los grupos implicados por los grupos dados. Para cada
    eje se distingue el que exige MFA del que no.

    Devuelve un diccionario con el eje como clave y una lista de tuplas
    ``(segundos, exige_mfa)`` ordenada de menor a mayor::

        {
            'lock_timeout': [(43200, False), (86400, True)],
            'lock_timeout_inactivity': [(900, False)],
        }

    Un eje sin ningún grupo que lo configure sale con lista vacía.
    """
    key = frozenset(group_ids)
    cached = _LOCK_TIMEOUTS_CACHE.get(key)
    if cached is not None:
        return cached

    seeds = list(cls.objects.filter(pk__in=key))
    # ≙ ``self.with_context({}).all_implied_ids``: la clausura transitiva
    # reflexiva sobre los grupos dados. El ``with_context({})`` de la fuente
    # existe porque su ``ormcache`` no puede depender del contexto; aquí no
    # hay contexto de recordset que neutralizar.
    implied = cls.objects.filter(
        pk__in=cls._closure(seeds, lambda group: group.implied_ids.all()))

    result = {}
    for field_name, mfa_field_name in (
        ('lock_timeout', 'lock_timeout_mfa'),
        ('lock_timeout_inactivity', 'lock_timeout_inactivity_mfa'),
    ):
        values = [
            (getattr(group, field_name), getattr(group, mfa_field_name))
            for group in implied
            if getattr(group, field_name)
        ]
        min_non_mfa = min((v for v, mfa in values if not mfa), default=None)
        min_mfa = min((v for v, mfa in values if mfa), default=None)

        result[field_name] = []
        if min_mfa:
            result[field_name].append((min_mfa * 60, True))
        if min_non_mfa and (not min_mfa or min_non_mfa < min_mfa):
            result[field_name].append((min_non_mfa * 60, False))

        result[field_name].sort()

    _LOCK_TIMEOUTS_CACHE[key] = result
    return result


# === Las 8 propiedades — los campos que la fuente computa sin almacenar ====

def has_lock_timeout(self):
    """≙ ``has_lock_timeout`` — la propiedad que expone el cómputo."""
    return _compute_has_lock_timeout(self)


def lock_timeout_delay_unit(self):
    """≙ ``lock_timeout_delay_unit``."""
    return _compute_lock_timeout_delay_unit(self)[1]


def lock_timeout_delay_in_unit(self):
    """≙ ``lock_timeout_delay_in_unit``."""
    return _compute_lock_timeout_delay_unit(self)[0]


def lock_timeout_2fa_selection(self):
    """≙ ``lock_timeout_2fa_selection``."""
    return _compute_lock_timeout_2fa_selection(self)


def has_lock_timeout_inactivity(self):
    """≙ ``has_lock_timeout_inactivity``."""
    return _compute_lock_timeout_inactivity_bool(self)


def lock_timeout_inactivity_delay_unit(self):
    """≙ ``lock_timeout_inactivity_delay_unit``."""
    return _compute_lock_timeout_inactivity_delay_unit(self)[1]


def lock_timeout_inactivity_delay_in_unit(self):
    """≙ ``lock_timeout_inactivity_delay_in_unit``."""
    return _compute_lock_timeout_inactivity_delay_unit(self)[0]


def lock_timeout_inactivity_2fa_selection(self):
    """≙ ``lock_timeout_inactivity_2fa_selection``."""
    return _compute_lock_timeout_inactivity_2fa_selection(self)


def apply_authz_timeout_res_groups_extensions():
    """Cuelga sobre ``res.groups`` el eje de candado por tiempo — ≙ ``_inherit``."""
    extend_model(
        'base', 'ResGroups',
        campos={
            'lock_timeout': fields.Integer(
                default=0,
                verbose_name='Caducidad de sesión',
                help_text='Odoo lock_timeout ("Session timeout") — minutos '
                          'tras los cuales se vuelve a exigir identidad, haya '
                          'o no actividad.',
            ),
            'lock_timeout_mfa': fields.Boolean(
                default=False,
                verbose_name='Exigir MFA al caducar la sesión',
                help_text='Odoo lock_timeout_mfa ("Require MFA on session '
                          'timeout").',
            ),
            'lock_timeout_inactivity': fields.Integer(
                default=0,
                verbose_name='Caducidad por inactividad',
                help_text='Odoo lock_timeout_inactivity ("Inactivity '
                          'timeout") — minutos de inactividad tras los cuales '
                          'se vuelve a exigir identidad.',
            ),
            'lock_timeout_inactivity_mfa': fields.Boolean(
                default=False,
                verbose_name='Exigir MFA al caducar por inactividad',
                help_text='Odoo lock_timeout_inactivity_mfa ("Require MFA on '
                          'inactivity timeout").',
            ),
        },
        metodos={
            '_compute_has_lock_timeout': _compute_has_lock_timeout,
            '_compute_lock_timeout_delay_unit': _compute_lock_timeout_delay_unit,
            '_compute_lock_timeout_2fa_selection': _compute_lock_timeout_2fa_selection,
            '_compute_lock_timeout_inactivity_bool': _compute_lock_timeout_inactivity_bool,
            '_compute_lock_timeout_inactivity_delay_unit': _compute_lock_timeout_inactivity_delay_unit,
            '_compute_lock_timeout_inactivity_2fa_selection': _compute_lock_timeout_inactivity_2fa_selection,
            '_inverse_lock_timeout_2fa_selection': _inverse_lock_timeout_2fa_selection,
            '_inverse_lock_timeout_inactivity_2fa_selection': _inverse_lock_timeout_inactivity_2fa_selection,
            '_onchange_has_lock_timeout': _onchange_has_lock_timeout,
            '_onchange_lock_timeout_delay_unit': _onchange_lock_timeout_delay_unit,
            '_onchange_has_lock_timeout_inactivity': _onchange_has_lock_timeout_inactivity,
            '_onchange_lock_timeout_inactivity_delay_unit': _onchange_lock_timeout_inactivity_delay_unit,
            'save': save,
            'delete': delete,
            '_get_lock_timeouts': classmethod(_get_lock_timeouts),
        },
        propiedades={
            'has_lock_timeout': has_lock_timeout,
            'lock_timeout_delay_unit': lock_timeout_delay_unit,
            'lock_timeout_delay_in_unit': lock_timeout_delay_in_unit,
            'lock_timeout_2fa_selection': lock_timeout_2fa_selection,
            'has_lock_timeout_inactivity': has_lock_timeout_inactivity,
            'lock_timeout_inactivity_delay_unit': lock_timeout_inactivity_delay_unit,
            'lock_timeout_inactivity_delay_in_unit': lock_timeout_inactivity_delay_in_unit,
            'lock_timeout_inactivity_2fa_selection': lock_timeout_inactivity_2fa_selection,
        },
    )
