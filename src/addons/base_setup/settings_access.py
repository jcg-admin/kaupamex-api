"""Lectura tipada de un ajuste por su clave de dominio.

Los consumidores de un ajuste (``sale``, ``purchase``, …) no deben conocer el
destino ni el conversor: piden su clave y reciben el tipo. Es el equivalente
de leer un campo del formulario en la referencia, sin acoplarse al almacén —
y lo que permite mover una clave de ``SystemParameter`` a ``CompanySetting``
cuando exista el resolutor (UC-PLT-06) sin tocar a quien la lee.
"""
from addons.base_setup.models.res_config_settings import (
    CONFIG_CASTERS,
    SiteConfigSettings,
    _coerce,
)


def get_setting(field_name):
    """Valor actual del ajuste ``field_name``, en el tipo de su campo.

    ``field_name`` es el nombre del campo del formulario (``iva_rate``), no
    la clave del parámetro: el consumidor habla del ajuste, no de dónde vive.
    """
    if field_name not in CONFIG_CASTERS:
        raise KeyError(
            f'{field_name!r} no es un ajuste declarado; las claves válidas '
            f'son {sorted(CONFIG_CASTERS)}.'
        )
    key, caster = CONFIG_CASTERS[field_name]
    from_store = SiteConfigSettings.current_values([field_name]).get(field_name)
    default = SiteConfigSettings._meta.get_field(field_name).get_default()
    return _coerce(from_store, caster, default)
