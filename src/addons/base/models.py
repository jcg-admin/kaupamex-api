"""SystemParameter (L2) — config runtime global key/value (app ``addons.base``).

Portación **fiel** de Odoo ``ir.config_parameter``
(``scratchpad/odoo19x/odoo/addons/base/models/ir_config_parameter.py`` y
``scratchpad/odoo18/extracted/odoo/addons/base/models/ir_config_parameter.py`` —
arquitectura idéntica en v19 y v18). Diseño: capa L2 de
``analisis-estrategia-configuracion-capas``. Hallazgos de la portación:
``hallazgos-implementar-systemparameter-l2``.

Correspondencia Odoo -> Django (adaptación sin azúcar sintáctica):

- ``_name='ir.config_parameter'`` / ``_description='System Parameter'`` ->
  modelo ``SystemParameter`` (``verbose_name='System Parameter'``).
- ``key = Char(required=True)`` + ``unique (key)`` -> ``CharField(unique=True)``.
  Odoo ``Char`` no fija longitud; en MariaDB un índice único requiere longitud,
  así que se fija ``max_length=255`` (adaptación de motor, H-CFG-IMPL-05).
- ``value = Text(required=True)`` -> ``TextField``.
- ``_order='key'`` -> ``Meta.ordering=['key']``; ``_rec_name='key'`` ->
  ``__str__`` devuelve ``key``.
- ``_default_parameters`` (dict clave->callable) -> ``_DEFAULT_PARAMETERS``
  módulo-nivel. **Fuente de verdad de la protección**: NO existe una columna
  ``is_system`` en Odoo (H-CFG-IMPL-01 corrige el análisis, que la había
  especulado). Una clave está protegida ssi pertenece a este dict.
- ``get_param``/``set_param``/``init`` (``@api.model``) -> ``classmethod`` s
  (``seed`` == ``init``).
- ``@ormcache('key', cache='stable')`` + ``clear_cache('stable')`` -> caché
  módulo-nivel ``_PARAM_CACHE`` invalidada en toda mutación (H-CFG-IMPL-02).
- ``write`` rechaza renombrar una clave protegida; ``unlink_default_parameters``
  (``@api.ondelete``) rechaza borrar una clave protegida -> guards en ``save``
  y ``delete``.
"""
import math
import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import DEFAULT_DB_ALIAS, models

# Parámetros sembrados al inicializar la instancia (Odoo ``_default_parameters``,
# líneas 18-25 de ir_config_parameter.py, v19/v18 idénticas). Pertenecer a este
# dict == estar protegido contra borrado y renombrado. El valor es un callable
# perezoso (se evalúa al sembrar), fiel a Odoo.
#
# ``authz.reauth_ttl`` y ``backup.alert_email`` migran aquí desde
# ``config.settings.base`` (slice 2 de ``implementar-systemparameter-l2`,
# cierra el drift H-API-CFG-01/02 de
# :ref:`hallazgos-estrategia-configuracion-kaupamex`): eran tunables globales
# con ``default=`` cableado en código (el de ``backup.alert_email`` además
# stale — ``practicayoruba.com`` tras el rename L0 a Kaupamex, SOL-087). Se
# preserva el valor operativo previo (900 s) y se corrige el dominio del
# email a ``kaupamex.com``.
_DEFAULT_PARAMETERS = {
    'database.uuid': lambda: str(uuid.uuid1()),
    'database.secret': lambda: str(uuid.uuid4()),
    'authz.reauth_ttl': lambda: '900',
    'backup.alert_email': lambda: 'admin@kaupamex.com',
}

# Caché por-proceso, equivalente a ``ormcache('key', cache='stable')`` de Odoo.
# Clave: ``(using, key)`` -> value (o ``None`` para "clave ausente", igual que
# Odoo cachea el resultado del SELECT incluyendo la ausencia). Invalidación
# global en cada mutación (Odoo ``clear_cache('stable')``). H-CFG-IMPL-02: como
# ormcache, es per-proceso; la invalidación cross-worker (registry signaling de
# Odoo) queda fuera de scope de esta slice.
_PARAM_CACHE = {}


def _clear_cache():
    """Invalida toda la caché (Odoo ``clear_cache('stable')`` — namespace entero)."""
    _PARAM_CACHE.clear()


class SystemParameter(models.Model):
    """Almacén per-instancia de pares clave/valor de configuración (L2 global).

    Equivalente a ``ir.config_parameter``. Vive en el plano de control
    (``default``); no es per-empresa (eso es L3).
    """

    key = models.CharField(max_length=255, unique=True)
    value = models.TextField()

    class Meta:
        db_table = 'system_parameter'
        ordering = ['key']
        verbose_name = 'System Parameter'
        verbose_name_plural = 'System Parameters'

    def __str__(self):
        return self.key

    # -- Lectura (Odoo get_param / _get_param) ------------------------------

    @classmethod
    def get_param(cls, key, default=None, using=DEFAULT_DB_ALIAS):
        """Devuelve el valor de ``key``, o ``default`` si no existe.

        Fiel a Odoo ``get_param`` (línea 60): ``return self._get_param(key) or
        default``. El ``or default`` implica que un valor almacenado *falsy*
        (cadena vacía) también devuelve ``default`` — quirk heredado de Odoo
        (H-CFG-IMPL-03), documentado y preservado por fidelidad.
        """
        return cls._get_param(key, using=using) or default

    @classmethod
    def _get_param(cls, key, using=DEFAULT_DB_ALIAS):
        """Lee el valor crudo con caché. Odoo bypassa el ORM con SQL directo
        (líneas 73-79) porque ``get_param`` se usa en ``@api.depends`` con el ORM
        a medio inicializar; Django no tiene esa restricción, así que se usa el
        ORM normal (H-CFG-IMPL-04). Cachea también la ausencia (``None``)."""
        ckey = (using, key)
        if ckey in _PARAM_CACHE:
            return _PARAM_CACHE[ckey]
        value = (cls.objects.using(using)
                 .filter(key=key)
                 .values_list('value', flat=True)
                 .first())
        _PARAM_CACHE[ckey] = value
        return value

    # -- Escritura (Odoo set_param) -----------------------------------------

    @classmethod
    def set_param(cls, key, value, using=DEFAULT_DB_ALIAS):
        """Fija el valor de ``key``; devuelve el valor previo (o ``None``).

        Fiel a Odoo ``set_param`` (líneas 82-103): si la clave existe y el valor
        es *None/False* -> borra; si cambió -> actualiza; devuelve el valor
        previo. Si no existe y el valor no es *None/False* -> crea; devuelve
        ``None`` (Odoo devuelve ``False``).
        """
        param = cls.objects.using(using).filter(key=key).first()
        if param is not None:
            old = param.value
            if value is not None and value is not False:
                if str(value) != old:
                    param.value = str(value)
                    param.save(using=using)  # save() invalida la caché
            else:
                param.delete(using=using)    # delete() invalida la caché
            return old
        if value is not None and value is not False:
            cls.objects.using(using).create(key=key, value=str(value))
            _clear_cache()
        return None

    # -- Sembrado (Odoo init) -----------------------------------------------

    @classmethod
    def seed(cls, force=False, using=DEFAULT_DB_ALIAS):
        """Siembra ``_DEFAULT_PARAMETERS`` (Odoo ``init``, líneas 44-57).

        Idempotente: sólo crea las claves ausentes; ``force=True`` sobreescribe
        las existentes.
        """
        for key, func in _DEFAULT_PARAMETERS.items():
            exists = cls.objects.using(using).filter(key=key).exists()
            if force or not exists:
                cls.set_param(key, func(), using=using)

    # -- Guards de protección (Odoo write / unlink_default_parameters) ------

    def save(self, *args, **kwargs):
        """Invalida la caché e impide renombrar una clave protegida.

        Fiel a Odoo ``write`` (líneas 110-116): si se cambia ``key`` a/desde una
        clave de ``_DEFAULT_PARAMETERS``, rechaza. Sólo aplica a updates (pk no
        nulo); las inserciones no renombran nada.
        """
        if self.pk is not None:
            using = kwargs.get('using') or self._state.db or DEFAULT_DB_ALIAS
            old_key = (type(self).objects.using(using)
                       .filter(pk=self.pk)
                       .values_list('key', flat=True)
                       .first())
            if (old_key is not None and old_key != self.key
                    and old_key in _DEFAULT_PARAMETERS):
                raise ValidationError(
                    'No se puede renombrar el parámetro protegido "%s".' % old_key)
        _clear_cache()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Invalida la caché e impide borrar una clave protegida.

        Fiel a Odoo ``unlink_default_parameters`` (``@api.ondelete``, líneas
        122-125): una clave de ``_DEFAULT_PARAMETERS`` no se puede eliminar.
        """
        if self.key in _DEFAULT_PARAMETERS:
            raise ValidationError(
                'No se puede eliminar el parámetro protegido "%s".' % self.key)
        _clear_cache()
        return super().delete(*args, **kwargs)


# ---------------------------------------------------------------------------
# res.currency / res.country / res.country.state — núcleo geográfico/monetario
# de Odoo ``base`` (``odoo/addons/base/models/res_currency.py`` +
# ``res_country.py``, arquitectura idéntica en 18 y 19). Espina base de la
# adaptación de familias (SOL-096): account/sale/pricing/direcciones dependen
# de currency + country. Portación fiel (sin azúcar sintáctica).
# ---------------------------------------------------------------------------


class ResCurrency(models.Model):
    """``res.currency`` — moneda ISO 4217 (Odoo base).

    Fiel a ``res_currency.py`` (18:23-47 / 19:21-49): ``name`` (código ISO 4217,
    3 letras), ``full_name``, ``symbol``, ``rounding`` (factor), ``decimal_places``
    (compute = ``ceil(log10(1/rounding))``, o18:41 / o19:39), ``position``
    (before/after), ``active``, ``currency_unit_label``.
    """

    POSITION_AFTER  = 'after'
    POSITION_BEFORE = 'before'
    POSITION_CHOICES = [
        (POSITION_AFTER, 'Después del importe'),
        (POSITION_BEFORE, 'Antes del importe'),
    ]

    name                = models.CharField(
        max_length=3, unique=True,
        help_text='Código de moneda ISO 4217 (Odoo res.currency.name).',
    )
    full_name           = models.CharField(
        max_length=64, blank=True, default='',
        help_text='Nombre de la moneda (Odoo full_name).',
    )
    symbol              = models.CharField(
        max_length=8,
        help_text='Signo de la moneda (Odoo symbol).',
    )
    rounding            = models.DecimalField(
        max_digits=12, decimal_places=6, default=Decimal('0.01'),
        help_text='Factor de redondeo (Odoo rounding).',
    )
    decimal_places      = models.IntegerField(
        default=2,
        help_text='Decimales, computado de rounding (Odoo decimal_places).',
    )
    position            = models.CharField(
        max_length=6, choices=POSITION_CHOICES, default=POSITION_AFTER,
        help_text='Posición del símbolo (Odoo position).',
    )
    active              = models.BooleanField(
        default=True, help_text='Moneda activa (Odoo active).',
    )
    currency_unit_label = models.CharField(
        max_length=32, blank=True, default='',
        help_text='Etiqueta de la unidad (Odoo currency_unit_label).',
    )

    class Meta:
        db_table = 'res_currency'
        ordering = ['name']
        verbose_name = 'Moneda'
        verbose_name_plural = 'Monedas'

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        """Computa ``decimal_places`` desde ``rounding`` (Odoo _compute_decimal_places).

        o18:163-168 / o19:163-168: si ``0 < rounding <= 1`` →
        ``ceil(log10(1/rounding))``; en otro caso 0.
        """
        r = float(self.rounding or 0)
        if 0 < r <= 1:
            self.decimal_places = int(math.ceil(math.log10(1 / r)))
        else:
            self.decimal_places = 0
        return super().save(*args, **kwargs)


class ResCountry(models.Model):
    """``res.country`` — país (Odoo base).

    Fiel a ``res_country.py`` (18:32-68 / 19 idéntico): ``name`` (requerido),
    ``code`` (ISO 3166-1 alpha-2, único), ``currency`` (FK res.currency),
    ``phone_code``. ``state_ids`` es el reverso de ``ResCountryState.country``.
    """

    name        = models.CharField(
        max_length=120,
        help_text='Nombre del país (Odoo res.country.name).',
    )
    code        = models.CharField(
        max_length=2, unique=True, null=True, blank=True,
        help_text='Código ISO 3166-1 alpha-2 (Odoo code).',
    )
    currency    = models.ForeignKey(
        'base.ResCurrency', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='countries',
        help_text='Moneda del país (Odoo currency_id).',
    )
    phone_code  = models.IntegerField(
        null=True, blank=True,
        help_text='Código telefónico del país (Odoo phone_code).',
    )

    class Meta:
        db_table = 'res_country'
        ordering = ['name']
        verbose_name = 'País'
        verbose_name_plural = 'Países'

    def __str__(self) -> str:
        return self.name


class ResCountryState(models.Model):
    """``res.country.state`` — estado/provincia de un país (Odoo base).

    Fiel a ``res_country.py`` (18:162-171 / 19 idéntico): ``country`` (FK,
    requerido), ``name`` (requerido), ``code`` (requerido). Único (country, code)
    replica el ``_sql_constraints`` ``name_code_uniq`` de Odoo.
    """

    country = models.ForeignKey(
        'base.ResCountry', on_delete=models.CASCADE, related_name='state_ids',
        help_text='País (Odoo country_id).',
    )
    name    = models.CharField(
        max_length=120, help_text='Nombre del estado (Odoo name).',
    )
    code    = models.CharField(
        max_length=8, help_text='Código del estado (Odoo code).',
    )

    class Meta:
        db_table = 'res_country_state'
        constraints = [
            models.UniqueConstraint(
                fields=['country', 'code'], name='unique_state_country_code',
            ),
        ]
        ordering = ['country', 'code']
        verbose_name = 'Estado / provincia'
        verbose_name_plural = 'Estados / provincias'

    def __str__(self) -> str:
        return f'{self.name} ({self.country.code})'
