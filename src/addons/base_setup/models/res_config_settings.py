"""Ajustes generales del sitio — formulario, no tabla.

Adaptación fiel de ``res.config.settings`` de la referencia: en ``odoo19c:``
y ``odoo18c:`` (medido por símbolo, ``odoo/addons/base/models/res_config.py``)
la clase es ``models.TransientModel`` — **no almacena**. Es el formulario que
compone los ajustes; los valores viven en tres destinos, medidos sobre
``base_setup/models/res_config_settings.py`` de la referencia:

======================================  ==================  ========  ========
Destino                                 Declarado como      odoo19c:  odoo18c:
======================================  ==================  ========  ========
parámetro global clave-valor            ``config_parameter``       2         3
campo de la compañía                    ``related=company_id``     5         4
grupo implícito                         ``implied_group``          1         1
======================================  ==================  ========  ========

Aquí se usan los mismos tres destinos con los análogos vivos del árbol:

- ``config_parameter`` → ``SystemParameter`` (``ir.config_parameter``),
  ámbito **L0** — política de la plataforma.
- campo de la compañía → ``CompanySetting``, ámbito **L1/L3** — configuración
  del tenant. Django no tiene ``related=`` sobre un formulario transitorio;
  el destino se atendería por los hooks que la propia referencia deja
  abiertos (``get_values``/``set_values``, categoría ``other``).
  **Hoy no es alcanzable**: ver "El destino per-company está bloqueado".
- ``implied_group`` → ``ResGroups.apply_group`` — ya soportado por el motor
  portado en ``base/models/res_config.py``; hoy sin campos que lo usen.

**Por qué esto reemplaza a ``SiteSettings``.** Aquella era una fila tipada y
persistente con 13 campos de 10 dominios distintos: 10 razones para cambiar
en una tabla, y una migración de esquema por cada cambio de política. Ver
``analisis-sitesettings-viola-srp-vs-res-config-settings`` (H-API-265) para
la medición completa.

**Clasificación L0 vs L1 (DEC-KX-05).** Infra/ops y plazos de la plataforma
→ L0; lo que un tenant configura para su tienda (identidad, fiscalidad,
umbrales comerciales, contacto) → L1. El criterio no se inventa aquí: es el
que DEC-KX-05 ya fija, aplicado campo por campo.

**El destino per-company está bloqueado — medido, no supuesto.**
``CompanySetting.set_setting`` exige una company resoluble, y
``CompanySetting._resolve_company_id(None)`` devuelve ``None`` en un request
admin: el resolutor subdominio→company (UC-PLT-06) **no existe todavía**, y
el propio docstring de ``get_setting`` lo dice ("mientras el resolutor
subdominio→company no exista"). Escribir ahí hoy sería perder el valor en
silencio — exactamente lo que ``check_silent_oks`` prohíbe.

Por eso **los trece campos usan el destino de parámetro** (``SystemParameter``)
con su clave prefijada por dominio dueño. Esto **ya cumple el objetivo de
SRP**: no hay una tabla con diez razones para cambiar, sino trece claves
independientes — ``account.iva_rate`` cambia sin tocar
``delivery.free_shipping_threshold`` ni migrar esquema. Lo que queda
pendiente es **de qué ámbito** es cada clave, y eso se decide cuando el
resolutor exista: mover una clave de ``SystemParameter`` a ``CompanySetting``
es un cambio de una línea en la declaración, no un refactor.
"""
from decimal import Decimal, InvalidOperation

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from addons.base.models.res_config import ResConfigSettings

#: Clave y conversor por campo. La clave lleva el **prefijo del dominio
#: dueño** — el mismo criterio con el que la referencia nombra sus
#: ``config_parameter`` (``base_setup.show_effect``) — y es lo que da el SRP:
#: cada dominio cambia la suya sin tocar las demás ni migrar esquema.
#:
#: El conversor existe porque la clave-valor no tiene esquema:
#: ``SystemParameter`` guarda cadenas y el contrato publicado promete el tipo
#: del campo (la referencia hace lo mismo con ``convert_to_cache``).
#:
#: La columna de ámbito es la clasificación DEC-KX-05; hoy todas escriben en
#: ``SystemParameter`` porque el destino per-company no es alcanzable (ver el
#: docstring del módulo). Las marcadas **L1** son las que se moverán a
#: ``CompanySetting`` cuando exista el resolutor (UC-PLT-06).
CONFIG_CASTERS = {
    # ámbito L0 — política de la plataforma
    'payment_timeout_minutes': ('payment.timeout_minutes', int),
    'order_timeout_minutes': ('sale.order_timeout_minutes', int),
    # ámbito L1 (pendiente de resolutor) — configuración de la tienda
    'site_name': ('website.site_name', str),
    'iva_rate': ('account.iva_rate', Decimal),
    'max_return_days': ('stock.max_return_days', int),
    'min_stock_threshold': ('stock.min_stock_threshold', int),
    'free_shipping_threshold': ('delivery.free_shipping_threshold', Decimal),
    'support_email': ('crm.support_email', str),
    'phone': ('crm.phone', str),
    'address': ('crm.address', str),
}


def _coerce(raw, caster, default):
    """Convierte el valor crudo de la clave-valor al tipo del formulario.

    Un valor ilegible equivale a "no configurado": el formulario cae al
    default en vez de reventar, porque la clave-valor no tiene esquema que
    garantice el tipo.
    """
    if raw is None or raw == '':
        return default
    try:
        return caster(raw)
    except (TypeError, ValueError, InvalidOperation):
        return default


class SiteConfigSettings(ResConfigSettings):
    """``res.config.settings`` del sitio — formulario de ajustes (UC-CFG-03).

    No crea tabla (``managed = False``). Se instancia con los datos del
    request y ``apply_values()`` escribe cada campo en su destino.
    """

    # — L0: política de la plataforma → SystemParameter —
    payment_timeout_minutes = models.PositiveIntegerField(default=30)
    order_timeout_minutes = models.PositiveIntegerField(default=60)

    # — L1: configuración del tenant → CompanySetting —
    #: Sin default de tenant: ``PracticaYoruba`` es el L1 de ejemplo, no el
    #: nombre de la plataforma. Vacío = lo pone cada Company (en la
    #: referencia el nombre sale de ``res.company.name``).
    site_name = models.CharField(max_length=100, blank=True, default='')
    iva_rate = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal('0.16'),
        validators=[MinValueValidator(Decimal('0')),
                    MaxValueValidator(Decimal('1'))],
    )
    max_return_days = models.PositiveIntegerField(default=30)
    min_stock_threshold = models.PositiveIntegerField(default=5)
    free_shipping_threshold = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('999.00'),
        validators=[MinValueValidator(Decimal('0'))],
    )
    support_email = models.EmailField(max_length=254, blank=True, default='')
    phone = models.CharField(max_length=30, blank=True, default='')
    address = models.TextField(blank=True, default='')

    #: Derivado de ``CONFIG_CASTERS`` — una sola fuente para la clave, para
    #: que el mapa y el metadato no puedan divergir.
    field_attrs = {
        name: {'config_parameter': key}
        for name, (key, _caster) in CONFIG_CASTERS.items()
    }

    class Meta:
        # El equivalente Django del ``TransientModel``: la clase existe y se
        # instancia en memoria, pero NO tiene tabla — Django no la crea ni la
        # consulta. Un ``abstract = True`` no serviría: no se puede
        # instanciar, y el formulario necesita instanciarse para aplicar.
        managed = False
        db_table = 'base_setup_siteconfigsettings_unmanaged'
        verbose_name = 'Ajustes generales del sitio'

    @classmethod
    def current_values(cls, fnames=None):
        """El estado actual, con cada valor en el tipo de su campo.

        La clave-valor no tiene esquema: ``SystemParameter`` devuelve el
        parámetro como cadena. La referencia resuelve esto con
        ``convert_to_cache`` (el campo conoce su tipo); aquí se castea con el
        mismo criterio, porque el contrato publicado promete
        ``payment_timeout_minutes`` entero, no ``'45'``.
        """
        values = super().current_values(fnames)
        for name, (_key, caster) in CONFIG_CASTERS.items():
            if name in values:
                default = cls._meta.get_field(name).get_default()
                values[name] = _coerce(values[name], caster, default)
        return values

    def set_values(self):
        """Sin campos de la categoría ``other``: todos son ``config``.

        El hook se conserva porque es el punto de enganche del destino
        per-company: cuando exista el resolutor (UC-PLT-06), las claves de
        ámbito L1 se atenderán aquí contra ``CompanySetting`` en vez de en
        ``SystemParameter``.
        """
        return None
