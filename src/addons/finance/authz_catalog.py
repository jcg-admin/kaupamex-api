"""Declaración del catálogo L0 que dueña ``finance`` (#179, SOL-100).

Recogido por ``seed_authz`` vía ``addons.authz.declaration.discover()``.
Antes vivía en el propio seed como lista central; se movió aquí para que el
catálogo lo declare quien dueña el dominio, y no un archivo que hay que
recordar editar (H-API-106).

Por qué estos códigos son de este addon:

- ``finance`` — el addon homónimo dueña los movimientos financieros.
"""
from addons.authz.declaration import CapabilitySpec, ModuleSpec

MODULES = [
    ModuleSpec(
        code='finance',
        name='Finanzas',
        is_application=True,
        category='Finance',
    ),
]

CAPABILITIES = [
    CapabilitySpec(code='finance', name='Finanzas', is_sensitive=True),
    CapabilitySpec(
        code='finance.close',
        name='Sellar corte de caja / cerrar ejercicio',
        is_sensitive=True,
    ),
    CapabilitySpec(
        code='finance.disburse',
        name='Pagar flete / cancelar-reembolsar cobro',
        is_sensitive=True,
    ),
    CapabilitySpec(
        code='finance.reconcile',
        name='Conciliar liquidaciones del gateway',
        is_sensitive=True,
    ),
    CapabilitySpec(
        code='finance.record',
        name='Registrar movimiento/concepto financiero',
        is_sensitive=True,
    ),
]
