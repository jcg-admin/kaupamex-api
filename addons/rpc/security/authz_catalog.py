"""Catálogo authz de ``rpc`` — recogido por ``seed_authz`` (SOL-100).

El despacho genérico es **una** superficie con **un** permiso de entrada: quien
lo tiene puede pedir cualquier modelo/método que los gates de abajo permitan.
Por eso es una acción nombrada (``rpc.call``, membresía) y no un sustantivo
graduable: no hay un "leer" y un "escribir" del dispatcher — hay el dispatcher.

Es **sensible** a propósito: abre la superficie programática entera, así que no
se siembra en el rol comprador. La referencia no tiene análogo porque allá el
endpoint es público (``auth='bearer'``) y el control vive en el ORM; aquí el
control vive en la vista, y DEC-11 lo exige explícito.
"""
from addons.authz.declaration import CapabilitySpec, ModuleSpec

MODULES = [
    ModuleSpec(
        code='rpc',
        name='Despacho programático',
        is_application=False,
        # NO 'Extra Tools' —la categoría de la referencia—: este árbol tiene su
        # propio canon de familias ERP y el gate
        # `test_all_categories_are_canonical_erp_families` lo hace cumplir.
        # El despacho programático es infraestructura del operador L0, no un
        # dominio de negocio, así que su familia es `Platform`.
        category='Platform',
    ),
]

CAPABILITIES = [
    CapabilitySpec(
        code='rpc.call',
        name='Invocar métodos de modelo por el endpoint programático',
        is_sensitive=True,
    ),
]
